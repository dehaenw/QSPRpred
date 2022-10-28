set -e

export PYTHONPATH=".."

# input data and base directory
export TEST_BASE="."
export TEST_DATA_PRETRAINING='ZINC_raw_small.tsv'
export TEST_DATA_FINETUNING='A2AR_raw_small.tsv'
export TEST_DATA_ENVIRONMENT='A2AR_raw_small_env.tsv'

# prefixes for output files
export VOC_PREFIX='vocabulary'
export PRETRAINING_PREFIX='pre'
export FINETUNING_PREFIX='ft'

function cleanup() {
  rm -rf ${TEST_BASE}/data/backup_*;
  rm -rf ${TEST_BASE}/data/${FINETUNING_PREFIX}_*.tsv;
  rm -rf ${TEST_BASE}/data/${FINETUNING_PREFIX}_*.txt;
  rm -rf ${TEST_BASE}/data/${FINETUNING_PREFIX}_*.vocab;
  rm -rf ${TEST_BASE}/data/${PRETRAINING_PREFIX}_*.tsv;
  rm -rf ${TEST_BASE}/data/${PRETRAINING_PREFIX}_*.txt;
  rm -rf ${TEST_BASE}/data/${PRETRAINING_PREFIX}_*.vocab;
  rm -rf ${TEST_BASE}/data/${VOC_PREFIX}_*.txt;
  rm -rf ${TEST_BASE}/data/*.log;
  rm -rf ${TEST_BASE}/data/*.json;
  rm -rf ${TEST_BASE}/envs;
  rm -rf ${TEST_BASE}/generators;
  rm -rf ${TEST_BASE}/logs;
}

cleanup

# default values of some common parameters
export MOL_COL='CANONICAL_SMILES'
export N_FRAGS=4
export N_COMBINATIONS=4
export FRAG_METHOD='brics'
export TRAIN_EPOCHS=2
export TRAIN_BATCH=32
export TRAIN_GPUS=0
export N_CPUS=2
export OPTIMIZATION='bayes'
export SEARCH_SPACE='data/search_space/search_space_test'
export N_TRIALS=2

###########
# DATASET #
###########

export DATASET_COMMON_ARGS="-b ${TEST_BASE} -d -mc ${MOL_COL} -sv -sif"
export DATASET_FRAGMENT_ARGS="-fm ${FRAG_METHOD} -nf ${N_COMBINATIONS} -nf ${N_FRAGS}"

###############
# ENVIRONMENT #
###############
export ENVIRON_COMMON_ARGS="-b ${TEST_BASE} -d"
python -m drugex.environ \
${ENVIRON_COMMON_ARGS} \
-i ${TEST_DATA_ENVIRONMENT} \
-l \
-s \
-m RF \
-r CLS \
-ncpu ${N_CPUS} \
-o ${OPTIMIZATION} \
-ss ${SEARCH_SPACE} \
-nt ${N_TRIALS}

cleanup