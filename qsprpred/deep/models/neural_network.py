"""This module holds the base class for DNN models as well as fully connected NN subclass."""

import inspect
import time
from collections import defaultdict

import numpy as np
import torch
from qsprpred.deep import DEFAULT_DEVICE, DEFAULT_GPUS
from qsprpred.logs import logger
from torch import nn, optim
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset


class Base(nn.Module):
    """Base structure for all of classification/regression DNN models.

    Mainly, it provides the general methods for training, evaluating model and
    predicting the given data.
    """

    def __init__(
        self,
        device=DEFAULT_DEVICE,
        gpus=DEFAULT_GPUS,
        n_epochs=1000,
        lr=1e-4,
        batch_size=256,
        patience=50,
        tol=0
    ):
        """Initialize the DNN model.

        Args:
            device (torch.device): device to run the model on
            gpus (list): list of gpus to run the model on
            n_epochs (int): (maximum) number of epochs to train the model
            lr (float): learning rate
            batch_size (int): batch size
            patience (int): number of epochs to wait before early stop if no progress on validation set score, 
                            if patience = -1, always train to n_epochs
            tol (float): minimum absolute improvement of loss necessary to count as progress on best validation score
        """
        super().__init__()
        self.n_epochs = n_epochs
        self.lr = lr
        self.batch_size = batch_size
        self.patience = patience
        self.tol = tol
        if device.type == "cuda":
            self.device = torch.device(f"cuda:{gpus[0]}")
        else:
            self.device = device
        self.gpus = gpus
        if len(self.gpus) > 1:
            logger.warning(
                f"At the moment multiple gpus is not possible: running DNN on gpu: {gpus[0]}."
            )

    def fit(self, X_train, y_train, X_valid=None, y_valid=None, log=False, log_prefix=None):
        """Training the DNN model.

        Training is, similar to the scikit-learn or Keras style.
        It saves the optimal value of parameters.

        Args:
            X_train (np.ndarray or pd.Dataframe): training data (m X n), m is the No. of samples, n is the No. of features
            y_train (np.ndarray or pd.Dataframe): training target (m X l), m is the No. of samples, l is the No. of classes or tasks
            X_valid (np.ndarray or pd.Dataframe): validation data (m X n), m is the No. of samples, n is the No. of features
            y_valid (np.ndarray or pd.Dataframe): validation target (m X l), m is the No. of samples, l is the No. of classes or tasks
            log (bool): whether to log the training process to {self.log_prefix}.log
            log_prefix (str): prefix for the log file if log is True
        """
        train_loader = self.get_dataloader(X_train, y_train)

        # if validation data is provided, use early stopping
        if X_valid is not None and y_valid is not None:
            valid_loader = self.get_dataloader(X_valid, y_valid)
            patience = self.patience
        else:
            patience = -1
        
        if "optim" in self.__dict__:
            optimizer = self.optim
        else:
            optimizer = optim.Adam(self.parameters(), lr=self.lr)

        # record the minimum loss value based on the calculation of the
        # loss function by the current epoch
        best_loss = np.inf
        best_weights = self.state_dict() 
        last_save = 0 # record the epoch when optimal model is saved.
        if log:
            log_file = open(log_prefix + ".log", "a")
        for epoch in range(self.n_epochs):
            t0 = time.time()
            # decrease learning rate over the epochs
            for param_group in optimizer.param_groups:
                param_group["lr"] = self.lr * (1 - 1 / self.n_epochs) ** (epoch * 10)
            for i, (Xb, yb) in enumerate(train_loader):
                # Batch of target tenor and label tensor
                Xb, yb = Xb.to(self.device), yb.to(self.device)
                optimizer.zero_grad()
                # predicted probability tensor
                y_ = self(Xb, istrain=True)

                # ignore all of the NaN values
                ix = yb == yb
                if self.n_class > 1:
                    yb, y_ = yb[ix], y_[ix[:, -1], :]
                else:
                    yb, y_ = yb[ix], y_[ix]

                # loss function calculation based on predicted tensor and label tensor
                if self.n_class > 1:
                    loss = self.criterion(y_, yb.long())
                else:
                    loss = self.criterion(y_, yb)

                loss.backward()
                optimizer.step()
            if patience == -1:
                if log:
                    print("[Epoch: %d/%d] %.1fs loss_train: %f" % (epoch, self.n_epochs, time.time() - t0, loss.item()),
                        file=log_file)
            else:
                # loss value on validation set based on which optimal model is saved.
                loss_valid = self.evaluate(valid_loader)
                if log:
                    print(
                        "[Epoch: %d/%d] %.1fs loss_train: %f loss_valid: %f"
                        % (epoch, self.n_epochs, time.time() - t0, loss.item(), loss_valid), file=log_file)
                if loss_valid + self.tol < best_loss:
                    best_weights = self.state_dict()
                    if log:
                        print("[Performance] loss_valid is improved from %f to %f"
                            % (best_loss, loss_valid), file=log_file)
                    best_loss = loss_valid
                    last_save = epoch
                else:
                    if log:
                        print("[Performance] loss_valid is not improved.", file=log_file)
                    if epoch - last_save > patience: # early stop
                        break
        if patience == -1:
            best_weights = self.state_dict()
        if log:
            print("Neural net fitting completed.", file=log_file)
            log_file.close()
        self.load_state_dict(best_weights)
        return last_save

    def evaluate(self, loader):
        """Evaluate the performance of the DNN model.

        Args:
            loader (torch.util.data.DataLoader): data loader for test set,
                including m X n target FloatTensor and l X n label FloatTensor
                (m is the No. of sample, n is the No. of features, l is the
                No. of classes or tasks)

        Return:
            loss (float): the average loss value based on the calculation of loss
                function with given test set.
        """
        loss = 0
        for Xb, yb in loader:
            Xb, yb = Xb.to(self.device), yb.to(self.device)
            y_ = self.forward(Xb)

            # remove NaN values
            ix = yb == yb
            if self.n_class > 1:
                yb, y_ = yb[ix], y_[ix[:, -1], :]
            else:
                yb, y_ = yb[ix], y_[ix]

            # weighting in original drugex v2 code, but was specific to data used there
            # wb = torch.Tensor(yb.size()).to(utils.dev)
            # wb[yb == 3.99] = 0.1
            # wb[yb != 3.99] = 1
            # loss += self.criterion(y_ * wb, yb * wb).item()

            if self.n_class > 1:
                loss += self.criterion(y_, yb.long()).item()
            else:
                loss += self.criterion(y_, yb).item()
        loss = loss / len(loader)
        return loss

    def predict(self, X_test):
        """Predicting the probability of each sample in the given dataset.

        Args:
            X_test (ndarray): m X n target array (m is the No. of sample,
                              n is the No. of features)

        Returns:
            score (ndarray): probability of each sample in the given dataset,
                it is a m X l FloatTensor (m is the No. of sample, l is the
                No. of classes or tasks.)
        """
        loader = self.get_dataloader(X_test)
        score = []
        for Xb in loader:
            Xb = Xb.to(self.device)
            y_ = self.forward(Xb)
            score.append(y_.detach().cpu())
        score = torch.cat(score, dim=0).numpy()
        return score

    @classmethod
    def _get_param_names(cls):
        """Get the class parameter names.

        Function copied from sklearn.base_estimator!
        """
        init_signature = inspect.signature(cls.__init__)
        parameters = [
            p
            for p in init_signature.parameters.values()
            if p.name != "self" and p.kind != p.VAR_KEYWORD
        ]
        return sorted([p.name for p in parameters])

    def get_params(self, deep=True):
        """Get parameters for this estimator.

        Function copied from sklearn.base_estimator!

        Args:
            deep (bool): If True, will return the parameters for this estimator

        Returns:
            params (dict): Parameter names mapped to their values.
        """
        out = dict()
        for key in self._get_param_names():
            value = getattr(self, key)
            if deep and hasattr(value, "get_params"):
                deep_items = value.get_params().items()
                out.update((key + "__" + k, val) for k, val in deep_items)
            out[key] = value
        return out

    def set_params(self, **params):
        """Set the parameters of this estimator.

        Function copied from sklearn.base_estimator!
        The method works on simple estimators as well as on nested objects
        (such as :class:`~sklearn.pipeline.Pipeline`). The latter have
        parameters of the form ``<component>__<parameter>`` so that it's
        possible to update each component of a nested object.

        Args:
            **params : dict Estimator parameters.

        Returns:
            self : estimator instance
        """
        if not params:
            # Simple optimization to gain speed (inspect is slow)
            return self
        valid_params = self.get_params(deep=True)

        nested_params = defaultdict(dict)  # grouped by prefix
        for key, value in params.items():
            key, delim, sub_key = key.partition("__")
            if key not in valid_params:
                local_valid_params = self._get_param_names()
                raise ValueError(
                    f"Invalid parameter {key!r} for estimator {self}. "
                    f"Valid parameters are: {local_valid_params!r}."
                )

            if delim:
                nested_params[key][sub_key] = value
            else:
                setattr(self, key, value)
                valid_params[key] = value

        for key, sub_params in nested_params.items():
            valid_params[key].set_params(**sub_params)

        return self

    def get_dataloader(self, X, y=None):
        """Convert data to tensors and get iterable over dataset with dataloader.

        Args:
        X (numpy 2d array): input dataset
        y (numpy 1d column vector): output data
        """
        # if pandas dataframe is provided, convert it to numpy array
        if hasattr(X, "values"):
            X = X.values
        if y is not None and hasattr(y, "values"):
            y = y.values
        
        if y is None:
            tensordataset = torch.Tensor(X)
        else:
            tensordataset = TensorDataset(torch.Tensor(X), torch.Tensor(y))
        return DataLoader(tensordataset, batch_size=self.batch_size)


class STFullyConnected(Base):
    """Single task DNN classification/regression model.

    It contains four fully connected layers between which are dropout layer for robustness.

    Args:
        n_dim (int): the No. of columns (features) for input tensor
        n_class (int): the No. of columns (classes) for output tensor.
        is_reg (bool, optional): Regression model (True) or Classification model (False)
        n_epochs (int): max number of epochs
        lr (float): neural net learning rate
        neurons_h1 (int): number of neurons in first hidden layer
        neurons_hx (int): number of neurons in other hidden layers
        extra_layer (bool): add third hidden layer
    """

    def __init__(
        self,
        n_dim,
        n_class=1,
        device=DEFAULT_DEVICE,
        gpus=DEFAULT_GPUS,
        n_epochs=1000,
        lr=None,
        batch_size=256,
        patience=50,
        tol=0,
        is_reg=True,
        neurons_h1=4000,
        neurons_hx=1000,
        extra_layer=False,
        dropout_frac=0.25,
    ):
        """Initialize the STFullyConnected model.

        Args:
            n_dim (int): the No. of columns (features) for input tensor
            n_class (int): the No. of columns (classes) for output tensor.
            device (str): device to run the model
            gpus (list): list of gpu ids to run the model
            n_epochs (int): max number of epochs
            lr (float): neural net learning rate
            batch_size (int): batch size
            patience (int): number of epochs to wait before early stop if no progress on validation set score, if patience = -1, always train to n_epochs
            tol (float): minimum absolute improvement of loss necessary to count as progress on best validation score
            is_reg (bool, optional): Regression model (True) or Classification model (False)
            neurons_h1 (int): number of neurons in first hidden layer
            neurons_hx (int): number of neurons in other hidden layers
            extra_layer (bool): add third hidden layer
            dropout_frac (float): dropout fraction
        """
        if not lr:
            lr = 1e-4 if is_reg else 1e-5
        super().__init__(
            device=device, gpus=gpus, n_epochs=n_epochs, lr=lr, batch_size=batch_size, patience=patience, tol=tol
        )
        self.n_dim = n_dim
        self.is_reg = is_reg
        self.n_class = n_class if not self.is_reg else 1
        self.neurons_h1 = neurons_h1
        self.neurons_hx = neurons_hx
        self.extra_layer = extra_layer
        self.dropout_frac = dropout_frac
        self.init_model()

    def init_model(self):
        """Define the layers of the model."""
        self.dropout = nn.Dropout(self.dropout_frac)
        self.fc0 = nn.Linear(self.n_dim, self.neurons_h1)
        self.fc1 = nn.Linear(self.neurons_h1, self.neurons_hx)
        if self.extra_layer:
            self.fc2 = nn.Linear(self.neurons_hx, self.neurons_hx)
        self.fc3 = nn.Linear(self.neurons_hx, self.n_class)
        if self.is_reg:
            # loss function for regression
            self.criterion = nn.MSELoss()
        elif self.n_class == 1:
            # loss and activation function of output layer for binary classification
            self.criterion = nn.BCELoss()
            self.activation = nn.Sigmoid()
        else:
            # loss and activation function of output layer for multiple classification
            self.criterion = nn.CrossEntropyLoss()
            self.activation = nn.Softmax(dim=1)
        self.to(self.device)

    def set_params(self, **params):
        """Set parameters and re-initialize model."""
        super().set_params(**params)
        self.init_model()
        return self

    def forward(self, X, istrain=False):
        """Invoke the class directly as a function.

        Args:
            X (FloatTensor): m X n FloatTensor, m is the No. of samples, n is
                the No. of features.
            istrain (bool, optional): is it invoked during training process (True) or
                just for prediction (False)
        Returns:
            y (FloatTensor): m X n FloatTensor, m is the No. of samples,
                n is the No. of classes
        """
        y = F.relu(self.fc0(X))
        if istrain:
            y = self.dropout(y)
        y = F.relu(self.fc1(y))
        if self.extra_layer:
            if istrain:
                y = self.dropout(y)
            y = F.relu(self.fc2(y))
        if istrain:
            y = self.dropout(y)
        if self.is_reg:
            y = self.fc3(y)
        else:
            y = self.activation(self.fc3(y))
        return y