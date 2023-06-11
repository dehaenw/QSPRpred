"""Descriptorssets. A descriptorset is a collection of descriptors that can be calculated for a molecule.

To add a new descriptor or fingerprint calculator:
* Add a descriptor subclass for your descriptor calculator
* Add a function to retrieve your descriptor by name to the descriptor retriever class
"""
from abc import ABC, abstractmethod
from typing import Union, List

import numpy as np
import pandas as pd
from qsprpred.data.utils.descriptor_utils import fingerprints
from qsprpred.data.utils.descriptor_utils.drugexproperties import Property
from qsprpred.data.utils.descriptor_utils.rdkitdescriptors import RDKit_desc
from rdkit import Chem, DataStructs
from rdkit.Chem import Mol


class DescriptorSet(ABC):

    __len__ = lambda self: self.get_len()

    @abstractmethod
    def __call__(self, *args, **kwargs):
        """
        Calculate the descriptors for a given input.

        Args:
            *args: arguments to be passed to perform the calculation
            **kwargs: keyword arguments to be passed to perform the calculation

        Returns:
            a data frame or array of descriptor values of shape (n_inputs, n_descriptors)
        """
        pass

    @property
    @abstractmethod
    def descriptors(self):
        """Return a list of descriptor names."""
        pass

    @descriptors.setter
    @abstractmethod
    def descriptors(self, value):
        """Set the descriptor names."""
        pass

    def get_len(self):
        """Return the number of descriptors."""
        return len(self.descriptors)

    @property
    @abstractmethod
    def is_fp(self):
        """Return True if descriptorset is fingerprint."""
        pass

    @property
    @abstractmethod
    def settings(self):
        """Return dictionary with arguments used to initialize the descriptorset."""
        pass

    @abstractmethod
    def __str__(self):
        """Return string representation of the descriptorset."""
        pass


class MoleculeDescriptorSet(DescriptorSet):
    """Abstract base class for descriptorsets.

    A descriptorset is a collection of descriptors that can be calculated for a molecule.
    """

    @abstractmethod
    def __call__(self, mols: List[Union[str, Mol]]):
        """
        Calculate the descriptor for a molecule.

        Args:
            mols: list of molecules (SMILES `str` or RDKit Mol)

        Returns:
            an array or data frame of descriptor values of shape (n_mols, n_descriptors)
        """
        pass

    @staticmethod
    def iterMols(mols: List[Union[str, Mol]], to_list=False):
        """
        Create a molecule iterator or list from RDKit molecules or SMILES.

        Args:
            mols: list of molecules (SMILES `str` or RDKit Mol)
            to_list: if True, return a list instead of an iterator

        Returns:
            an array or data frame of descriptor values of shape (n_mols, n_descriptors)
        """
        ret = (Chem.MolFromSmiles(mol) if isinstance(mol, str) else mol for mol in mols)
        if to_list:
            ret = list(ret)
        return ret


class DataFrameDescriptorSet(DescriptorSet):

    def __init__(self, df: pd.DataFrame):
        self._df = df
        self._descriptors = df.columns.tolist()

    def getDF(self):
        return self._df

    def getIndex(self):
        return self._df.index

    def __call__(self, index, *args, **kwargs):
        ret = pd.DataFrame(index=index)
        ret = ret.merge(self._df, how="left", left_index=True, right_index=True)
        return ret[self.descriptors]

    @property
    def descriptors(self):
        return self._descriptors

    @descriptors.setter
    def descriptors(self, value):
        self._descriptors = value

    @property
    def is_fp(self):
        return False

    @property
    def settings(self):
        return {}

    def __str__(self):
        return "DataFrame"


class FingerprintSet(MoleculeDescriptorSet):
    """Generic fingerprint descriptorset can be used to calculate any fingerprint type defined in descriptorutils.fingerprints."""

    def __init__(self, fingerprint_type, *args, **kwargs):
        """
        Initialize the descriptor with the same arguments as you would pass to your fingerprint type of choice.

        Args:
            fingerprint_type: fingerprint type
            *args: fingerprint specific arguments
            **kwargs: fingerprint specific arguments keyword arguments
        """
        self._is_fp = True
        self.fingerprint_type = fingerprint_type
        self.get_fingerprint = fingerprints.get_fingerprint(self.fingerprint_type, *args, **kwargs)

        self._keepindices = None

    def __call__(self, mols):
        """Calculate the fingerprint for a list of molecules."""
        mols = [Chem.AddHs(mol) for mol in self.iterMols(mols)]
        ret = self.get_fingerprint(mols)

        if self.keepindices:
            ret = ret[:,self.keepindices]

        return ret

    @property
    def keepindices(self):
        """Return the indices of the fingerprint to keep."""
        return self._keepindices

    @keepindices.setter
    def keepindices(self, val):
        """Set the indices of the fingerprint to keep."""
        self._keepindices = [int(x) for x in val] if val else None

    @property
    def is_fp(self):
        """Return True if descriptorset is fingerprint."""
        return self._is_fp

    @property
    def settings(self):
        """Return dictionary with arguments used to initialize the descriptorset."""
        return {"fingerprint_type": self.fingerprint_type, **self.get_fingerprint.settings}

    def get_len(self):
        """Return the length of the fingerprint."""
        return len(self.get_fingerprint)

    def __str__(self):
        return f"FingerprintSet_{self.fingerprint_type}"

    @property
    def descriptors(self):
        """Return the indices of the fingerprint that are kept."""
        indices = self.keepindices if self.keepindices else range(self.get_len())
        return [f"{idx}" for idx in indices]

    @descriptors.setter
    def descriptors(self, value):
        """Set the indices of the fingerprint to keep."""
        self.keepindices(value)


class DrugExPhyschem(MoleculeDescriptorSet):
    """
    Physciochemical properties originally used in DrugEx for QSAR modelling.

    Args:
        props: list of properties to calculate
    """

    def __init__(self, physchem_props=None):
        """Initialize the descriptorset with Property arguments (a list of properties to calculate) to select a subset.

        Args:
            physchem_props: list of properties to calculate
        """
        self._is_fp = False
        self.props = [x for x in Property(physchem_props).props]

    def __call__(self, mols):
        """Calculate the DrugEx properties for a molecule."""
        calculator = Property(self.props)
        return calculator.getScores(self.iterMols(mols, to_list=True))

    @property
    def is_fp(self):
        return self._is_fp

    @property
    def settings(self):
        return {"physchem_props": self.props}

    @property
    def descriptors(self):
        return self.props

    @descriptors.setter
    def descriptors(self, props):
        """Set new props as a list of names."""
        self.props = [x for x in Property(props).props]

    def __str__(self):
        return "DrugExPhyschem"


class rdkit_descs(MoleculeDescriptorSet):
    """
    Calculate RDkit descriptors.

    Args:
        rdkit_descriptors: list of descriptors to calculate, if none, all 2D rdkit descriptors will be calculated
        compute_3Drdkit: if True, 3D descriptors will be calculated
    """

    def __init__(self, rdkit_descriptors=None, compute_3Drdkit=False):
        self._is_fp = False
        self._calculator = RDKit_desc(rdkit_descriptors, compute_3Drdkit)
        self._descriptors = self._calculator.descriptors
        self.compute_3Drdkit = compute_3Drdkit

    def __call__(self, mols):
        return self._calculator.getScores(self.iterMols(mols, to_list=True))

    @property
    def is_fp(self):
        return self._is_fp

    @property
    def settings(self):
        return {"rdkit_descriptors": self.descriptors, "compute_3Drdkit": self.compute_3Drdkit}

    @property
    def descriptors(self):
        return self._descriptors

    @descriptors.setter
    def descriptors(self, descriptors):
        self._calculator.descriptors = descriptors
        self._descriptors = descriptors

    def __str__(self):
        return "RDkit"


class TanimotoDistances(MoleculeDescriptorSet):
    """
    Calculate Tanimoto distances to a list of SMILES sequences.

    Args:
        list_of_smiles (list of strings): list of SMILES sequences to calculate distance to
        fingerprint_type (str): fingerprint type to use
        *args: `fingerprint` arguments
        **kwargs: `fingerprint` keyword arguments, should contain fingerprint_type
    """

    def __init__(self, list_of_smiles, fingerprint_type, *args, **kwargs):
        """Initialize the descriptorset with a list of SMILES sequences and a fingerprint type.

        Args:
            list_of_smiles (list of strings): list of SMILES sequences to calculate distance to
            fingerprint_type (str): fingerprint type to use
        """
        self._descriptors = list_of_smiles
        self.fingerprint_type = fingerprint_type
        self._args = args
        self._kwargs = kwargs
        self._is_fp = False

        # intialize fingerprint calculator
        self.get_fingerprint = fingerprints.get_fingerprint(self.fingerprint_type, *self._args, **self._kwargs)
        self.calculate_fingerprints(list_of_smiles)

    def __call__(self, mols):
        """Calculate the Tanimoto distances to the list of SMILES sequences.

        Args:
            mols (List[str] or List[rdkit.Chem.rdchem.Mol]): SMILES sequences or RDKit molecules to calculate distances to
        """
        mols = [Chem.MolFromSmiles(mol) if isinstance(mol, str) else mol for mol in mols]
        # Convert np.arrays to BitVects
        fps = list(map(lambda x: DataStructs.CreateFromBitString(''.join(map(str, x))),
                   self.get_fingerprint(mols)))
        return [list(1 - np.array(DataStructs.BulkTanimotoSimilarity(fp, self.fps)))
                for fp in fps]

    def calculate_fingerprints(self, list_of_smiles):
        """Calculate the fingerprints for the list of SMILES sequences."""
        # Convert np.arrays to BitVects
        self.fps = list(map(lambda x: DataStructs.CreateFromBitString(''.join(map(str, x))),
                            self.get_fingerprint([Chem.MolFromSmiles(smiles) for smiles in list_of_smiles])
                            ))

    @property
    def is_fp(self):
        return self._is_fp

    @property
    def settings(self):
        return {"fingerprint_type": self.fingerprint_type,
                "list_of_smiles": self._descriptors, "args": self._args, "kwargs": self._kwargs}

    @property
    def descriptors(self):
        return self._descriptors

    @descriptors.setter
    def descriptors(self, list_of_smiles):
        """Set new list of SMILES sequences to calculate distance to."""
        self._descriptors = list_of_smiles
        self.list_of_smiles = list_of_smiles
        self.fps = self.calculate_fingerprints(self.list_of_smiles)

    def __str__(self):
        return "TanimotoDistances"


class PredictorDesc(MoleculeDescriptorSet):
    """MoleculeDescriptorSet that uses a Predictor object to calculate the descriptors for a molecule."""

    def __init__(self, model : Union["QSPRModel", str]):
        """
        Initialize the descriptorset with a `QSPRModel` object.

        Args:
            model: a fitted model instance or a path to the model's meta file
        """

        if isinstance(model, str):
            from qsprpred.models.interfaces import QSPRModel
            self.model = QSPRModel.fromFile(model)
        else:
            self.model = model

        self._descriptors = [self.model.name]

    def __call__(self, mols):
        """
        Calculate the descriptor for a list of molecules.

        Args:
            mols (list): list of smiles or rdkit molecules

        Returns:
            an array of descriptor values
        """
        mols = list(mols)
        if type(mols[0]) != str:
            mols = [Chem.MolToSmiles(mol) for mol in mols]
        return self.model.predictMols(mols, use_probas=False)

    @property
    def is_fp(self):
        return False

    @property
    def settings(self):
        """Return args and kwargs used to initialize the descriptorset."""
        return {
            'model': self.model.metaFile # FIXME: we save absolute path to meta file so this descriptor set is not really portable
        }

    @property
    def descriptors(self):
        return self._descriptors

    @descriptors.setter
    def descriptors(self, descriptors):
        self._descriptors = descriptors

    def get_len(self):
        return 1

    def __str__(self):
        return "PredictorDesc"


class _DescriptorSetRetriever:
    """Based on recipe 8.21 of the book "Python Cookbook".

    To support a new type of descriptor, just add a function "get_descname(self, *args, **kwargs)".
    """

    def get_descriptor(self, desc_type, *args, **kwargs):
        method_name = "get_" + desc_type
        method = getattr(self, method_name)
        if method is None:
            raise Exception(f"{desc_type} is not a supported descriptor set type.")
        return method(*args, **kwargs)

    def get_FingerprintSet(self, *args, **kwargs):
        return FingerprintSet(*args, **kwargs)

    def get_DrugExPhyschem(self, *args, **kwargs):
        return DrugExPhyschem(*args, **kwargs)

    def get_Mordred(self, *args, **kwargs):
        from qsprpred.extra.data.utils.descriptorsets import Mordred
        return Mordred(*args, **kwargs)

    def get_Mold2(self, *args, **kwargs):
        from qsprpred.extra.data.utils.descriptorsets import Mold2
        return Mold2(*args, **kwargs)

    def get_PaDEL(self, *args, **kwargs):
        from qsprpred.extra.data.utils.descriptorsets import PaDEL
        return PaDEL(*args, **kwargs)

    def get_RDkit(self, *args, **kwargs):
        return rdkit_descs(*args, **kwargs)

    def get_PredictorDesc(self, *args, **kwargs):
        return PredictorDesc(*args, **kwargs)

    def get_ProDec(self, *args, **kwargs):
        from qsprpred.extra.data.utils.descriptorsets import ProDec
        return ProDec(*args, **kwargs)

    def get_TanimotoDistances(self, *args, **kwargs):
        return TanimotoDistances(*args, **kwargs)


def get_descriptor(desc_type: str, *args, **kwargs):
    return _DescriptorSetRetriever().get_descriptor(desc_type, *args, **kwargs)
