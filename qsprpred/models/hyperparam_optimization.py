"""Module for hyperparameter optimization of QSPRModels."""

from datetime import datetime
from typing import Callable, Iterable

import numpy as np
import optuna.trial
from sklearn.model_selection import ParameterGrid

from ..logs import logger
from ..models.interfaces import HyperParameterOptimization, QSPRModel


class OptunaOptimization(HyperParameterOptimization):
    """Class for hyperparameter optimization of QSPRModels using Optuna.

    Attributes:
        nTrials (int):
            number of trials for bayes optimization
        nJobs (int):
            number of jobs to run in parallel. At the moment only n_jobs=1 is supported.
        bestScore (float):
            best score found during optimization
        bestParams (dict):
            best parameters found during optimization

    Example of OptunaOptimization for scikit-learn's MLPClassifier:
        >>> model = QSPRsklearn(base_dir=".", data=dataset,
        >>>                     alg = MLPClassifier(), alg_name="MLP")
        >>> search_space = {
        >>>    "learning_rate_init": ["float", 1e-5, 1e-3,],
        >>>    "power_t" : ["discrete_uniform", 0.2, 0.8, 0.1],
        >>>    "momentum": ["float", 0.0, 1.0],
        >>> }
        >>> optimizer = OptunaOptimization(
        >>>     scoring="average_precision",
        >>>     param_grid=search_space,
        >>>     n_trials=10
        >>> )
        >>> best_params = optimizer.optimize(model)

    Available suggestion types:
        ["categorical", "discrete_uniform", "float", "int", "loguniform", "uniform"]
    """
    def __init__(
        self,
        scoring: str | Callable[[Iterable, Iterable], float],
        param_grid: dict,
        n_trials: int = 100,
        n_jobs: int = 1,
    ):
        """Initialize the class for hyperparameter optimization
        of QSPRModels using Optuna.

        Args:
            scoring (str | Callable[[Iterable, Iterable], float]]):
                scoring function for the optimization.
            param_grid (dict):
                search space for bayesian optimization, keys are the parameter names,
                values are lists with first element the type of the parameter and the
                following elements the parameter bounds or values.
            n_trials (int):
                number of trials for bayes optimization
            n_jobs (int):
                number of jobs to run in parallel.
                At the moment only n_jobs=1 is supported.
        """
        super().__init__(scoring, param_grid)
        self.nTrials = n_trials
        if n_jobs > 1:
            logger.warning(
                "At the moment n_jobs>1 not available for bayes optimization, "
                "n_jobs set to 1."
            )
        self.nJobs = 1
        self.bestScore = -np.inf
        self.bestParams = None

    def optimize(self, model: QSPRModel) -> dict:
        """Bayesian optimization of hyperparameters using optuna.

        Args:
            model (QSPRModel): the model to optimize

        Returns:
            dict: best parameters found during optimization
        """
        import optuna

        logger.info(
            "Bayesian optimization can take a while "
            "for some hyperparameter combinations"
        )
        # create optuna study
        study = optuna.create_study(direction="maximize")
        logger.info(
            "Bayesian optimization started: %s" %
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        study.optimize(
            lambda t: self.objective(t, model), self.nTrials, n_jobs=self.nJobs
        )
        logger.info(
            "Bayesian optimization ended: %s" %
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        # save the best study
        trial = study.best_trial
        # log the best study
        logger.info("Bayesian optimization best params: %s" % trial.params)
        # save the best score and parameters, return the best parameters
        self.bestScore = trial.value
        self.bestParams = trial.params
        return self.bestParams

    def objective(self, trial : optuna.trial.Trial, model: QSPRModel) -> float:
        """Objective for bayesian optimization.

        Arguments:
            trial (optuna.trial.Trial): trial object for the optimization
            model (QSPRModel): the model to optimize

        Returns:
            float: score of the model with the current parameters
        """
        bayesian_params = {}
        # get the suggested parameters for the current trial
        for key, value in self.paramGrid.items():
            if value[0] == "categorical":
                bayesian_params[key] = trial.suggest_categorical(key, value[1])
            elif value[0] == "discrete_uniform":
                bayesian_params[key] = trial.suggest_float(
                    key, value[1], value[2], step=value[3]
                )
            elif value[0] == "float":
                bayesian_params[key] = trial.suggest_float(key, value[1], value[2])
            elif value[0] == "int":
                bayesian_params[key] = trial.suggest_int(key, value[1], value[2])
            elif value[0] == "loguniform":
                bayesian_params[key] = trial.suggest_float(
                    key, value[1], value[2], log=True
                )
            elif value[0] == "uniform":
                bayesian_params[key] = trial.suggest_float(key, value[1], value[2])
        # evaluate the model with the current parameters and return the score
        y, y_ind = model.data.getTargetPropertiesValues()
        score = self.scoreFunc(
            y, model.evaluate(save=False,
                              parameters=bayesian_params,
                              score_func=self.scoreFunc)
        )
        return score


class GridSearchOptimization(HyperParameterOptimization):
    """Class for hyperparameter optimization of QSPRModels using GridSearch."""
    def __init__(
        self, scoring: str | Callable[[Iterable, Iterable], float], param_grid: dict
    ):
        """Initialize the class.

        Args:
            scoring (Union[str, Callable[[Iterable, Iterable], Iterable]]):
                metric name from sklearn.metrics or user-defined scoring function.
            param_grid (dict):
                dictionary with parameter names as keys and lists
                of parameter settings to try as values
        """
        super().__init__(scoring, param_grid)

    def optimize(self, model: QSPRModel, save_params: bool = True) -> dict:
        """Optimize the hyperparameters of the model.

        Args:
            model (QSPRModel): the model to optimize
            save_params (bool): whether to set and save the best parameters to the model after optimization

        Returns:
            dict: best parameters found during optimization
        """
        logger.info(
            "Grid search started: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        for params in ParameterGrid(self.paramGrid):
            logger.info(params)
            y, y_ind = model.data.getTargetPropertiesValues()
            score = self.scoreFunc(y, model.evaluate(save=False,
                                                     parameters=params,
                                                     score_func=self.scoreFunc))
            logger.info("Score: %s" % score)
            if score > self.bestScore:
                self.bestScore = score
                self.bestParams = params
        # log some info and return the best parameters
        logger.info(
            "Grid search ended: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        logger.info(
            "Grid search best params: %s with score: %s" %
            (self.bestScore, self.bestScore)
        )
        # save the best parameters to the model if requested
        if save_params:
            model.saveParams(self.bestParams)
        return self.bestParams