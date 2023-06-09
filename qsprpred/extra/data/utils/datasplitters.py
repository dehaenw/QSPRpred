"""Different splitters to create train and tests for evalutating QSPR model performance.

To add a new data splitter:
* Add a datasplit subclass for your new splitter
"""
import numpy as np

from qsprpred.data.data import QSPRDataset
from qsprpred.data.interfaces import datasplit, DataSetDependant
from qsprpred.data.utils.datasplitters import temporalsplit
from qsprpred.extra.data.data import PCMDataset


class LeaveTargetsOut(datasplit, DataSetDependant):

    def __init__(self, targets: list[str], dataset: PCMDataset = None):
        """Creates a leave target out splitter.

        Args:
            targets (list): the identifiers of the targets to leave out as test set
            dataset (PCMDataset): a `PCMDataset` instance to split
        """

        super().__init__(dataset)
        self.targets = list(set(targets))

    def split(self, X, y):
        ds = self.getDataSet()
        ds_targets = ds.getProteinKeys()
        for target in self.targets:
            assert target in ds_targets, f"Target key '{target}' not in dataset!"
            ds_targets.remove(target)
        mask = ds.getProperty(ds.proteincol).isin(ds_targets).values
        indices = np.array([x for x in range(len(ds))])
        train = indices[mask]
        test = indices[~mask]
        return iter([(train, test)])


class StratifiedPerTarget(datasplit, DataSetDependant):
    """Splits dataset in train and test subsets based on the specified splitter."""

    def __init__(self, splitter: datasplit = None, splitters: dict[str, datasplit] = None, dataset: PCMDataset = None):
        """Creates a split that is consistent across targets.

        Args:
            splitter: a `datasplit` instance to split the target subsets of the dataset
            splitters (dict[str, datasplit]): a dictionary with target keys as keys and splitters to use on each protein target as values
            dataset (PCMDataset): a `PCMDataset` instance to split
        """
        super().__init__(dataset)
        self.splitter = splitter
        self.splitters = splitters
        assert self.splitter is not None or self.splitters is not None, \
            "Either a splitter or multiple splitters must be specified!"
        assert (splitter is None) != (splitters is None), \
            "Either one splitter or multiple splitters must be specified, but not both!"

    def split(self, X, y):
        ds = self.getDataSet()
        df = ds.getDF()
        train = []
        test = []
        indices = np.array([x for x in range(len(ds))])
        for target in ds.getProteinKeys():
            splitter = self.splitter if self.splitter is not None else self.splitters[target]
            df_target = df[df[ds.proteincol] == target]
            ds_target = QSPRDataset(
                name=f"{target}_scaff_split_{hash(self)}",
                df=df_target,
                smilescol=ds.smilescol,
                target_props=ds.targetProperties,
                index_cols=ds.indexCols,
            )
            ds_target.split(splitter)
            train.extend(indices[df.index.isin(ds_target.X.index)])
            test.extend(indices[df.index.isin(ds_target.X_ind.index)])

        assert len(set(train)) + len(set(test)) == len(ds), "Train and test set do not cover the whole dataset!"
        return iter([(train, test)])


class TemporalPerTarget(datasplit, DataSetDependant):

    def __init__(self, year_col: str, split_years: dict[str, int], dataset: PCMDataset = None):
        """Creates a temporal split that is consistent across targets.

        Args:
            year_col (str): the name of the column in the dataframe that contains the year information
            split_years (dict[str,int]): a dictionary with target keys as keys and split years as values
            dataset (PCMDataset): a `PCMDataset` instance to split
        """
        super().__init__(dataset)
        self.splitYears = split_years
        self.yearCol = year_col

    def split(self, X, y):
        splitters = {
            target: temporalsplit(
                timeprop=self.yearCol,
                timesplit=self.splitYears[target]
            )
            for target, year in self.splitYears.items()
        }
        return StratifiedPerTarget(dataset=self.getDataSet(), splitters=splitters).split(X, y)