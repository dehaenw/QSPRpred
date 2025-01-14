# Change Log

From v2.0.1 to v2.1.0.a2

## Fixes

- fixed error with serialization of the `DataFrameDescriptorSet` (#63)
- Papyrus descriptors are not fetched by default anymore from the `Papyrus`  adapter, which caused fetching of unnecessary data.
- A [potential bug in new version of pandas](https://github.com/pandas-dev/pandas/issues/55009)  broke scaffold generation so a workaround was implemented.

## Changes
- `QSPRModel.evaluate` moved to a separate class `EvaluationMethod` in `qsprpred.models.interfaces`, with subclasses for cross-validation and making predictions on a test set in `qsprpred.models.evaluation_methods` (`CrossValidation` and `EvaluateTestSetPerformance` respectively).
- `QSPRModel` attribute `scoreFunc` is removed.
- 'qspr/models' is no longer added to the output path of `QSPRModel.save`, allowing for complete control over the output path.
- `SKlearnMetrics.supportsTask` now uses a dictionary like dict[ModelTasks, list[str]] to map tasks to supported metric names. (#53)
- `GBMTRandomSplit` and `ScaffoldSplit` now use the `GBMTDataSplit` to create balanced splits. `RandomSplit` still functions the same way as a completely random test split.
- `PCMSplit` replaces `StratifiedPerTarget` and is compatible with `RandomSplit`, `ScaffoldSplit` and `ClusterSplit`.
- `DuplicatesFilter` refactored to`RepeatsFilter`, as it also captures scenarios where triplicates/quadruplicates are found in the dataset. These scenarios are now also covered by the respective UnitTest.
- The versioning scheme of development snapshots has changed from `devX` to `alphaX`/`betaX`, where `X` is an integer that increments with each release.
- The following model class have been renamed and moved:
    - `models.models.QSPRsklearn` > `models.sklearn.SklearnModel`
    - `deep.models.QSPRDNN` > `extra.gpu.models.dnn.DNNModel`
    - `extra.models.pcm.ModelPCM` > `extra.models.pcm.PCMModel`
    - `extra.models.pcm.QSPRsklearnPCM` > `extra.models.pcm.SklearnPCMModel`
- The command line interface modules now use input and output file paths instead
  of automatically placing all files in a subfolder `qspr`, allowing for more
  control over the output and input paths.

## New Features
- `GBMTDataSplit` - parent class to create globally balanced splits with the [gbmt-split](https://github.com/sohviluukkonen/gbmt-splits) package.
- `ClusterSplit` - splits data based clustering of molecular fingerprints (uses `GBMTDataSplit`).
- Raise error if search space for optuna optimization is missing search space type annotation or if type not in list.
- When installing package with pip, the commit hash and date of the installation is saved into `qsprpred._version`
- `HyperParameterOptimization` classes now accept a `evaluation_method` argument, which is an instance of `EvaluationMethod` (see above). This allows for hyperparameter optimization to be performed on a test set, or on a cross-validation set. (#11)
- `HyperParameterOptimization` now accepts `score_aggregation` argument, which is a function that takes a list of scores and returns a single score. This allows for the use of different aggregation functions, such as `np.mean` or `np.median` to combine scores from different folds. (#45)
- A new tutorial `adding_new_components.ipynb` has been added to the `tutorials` folder, which demonstrates how to add new model to QSPRpred.
- A new function `Metrics.checkMetricCompatibility` has been added, which checks if a metric is compatible with a given task and a given prediction methods (i.e. `predict` or `predictProba`)
- In `EvaluationMethod` (see above), an attribute `use_proba` has been added, which determines whether the `predict` or `predictProba` method is used to make predictions (#56).
- Add new descriptorset `SmilesDesc` to use the smiles strings as a descriptor.
- New module `early_stopping` with classes `EarlyStopping` and `EarlyStoppingMode` has been added. This module allows for more control over early stopping in models that support it.
- Add new descriptorset `SmilesDesc` to use the smiles strings as a descriptor.
- Refactoring of the test suite under `qsprpred.data` and improvement of temporary file handling (!114).
- `PyBoostModel` - QSPRpred wrapper for py-boost models. Requires optional `pyboost` dependencies.
- `ChempropModel` - QSPRpred wrapper for Chemprop models. Requires optional `deep` dependencies.
- The `data_CLI` argument `--log_transform` (`-lt`) has been changed to `--transform_data` (`-t`), which now accepts a number of transformations to apply to the target data. Available transformations are `log`, `log10`, `log2`, `sqrt`, `cbrt`, `exp`, `exp2`, `exp10`, `square`, `cube`, `reciprocal`.
- New `data_CLI`, `model_CLI` and `predict_CLI` argument `--skip_backup` (`-sb`) to skip the backup of the output files. WARNING: This will overwrite existing files.

## Removed Features
- `StratifiedPerTarget` is replaced by `PCMSplit`.
