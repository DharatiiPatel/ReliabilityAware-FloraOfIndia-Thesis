#!/bin/bash
#SBATCH --job-name=qwen72b_extract
#SBATCH --partition=gpu_p
#SBATCH --gres=gpu:A100:2
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=256G
#SBATCH --time=48:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/qwen72b_extract_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/qwen72b_extract_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

# Clean environment (avoid inherited PYTHONPATH pollution)
module purge
unset PYTHONPATH
module load Python/3.13.5-GCCcore-14.3.0

# HF cache on scratch — 72B weights already downloaded (~137G) from the timed-out run
export HF_HOME=/scratch/dp23301/.cache/huggingface
# Do NOT set HF_HUB_OFFLINE: transformers still calls the HF API for a light
# metadata check even when weights are cached. Cache hits skip re-download.

cd /scratch/dp23301/Thesis

MODEL="Qwen/Qwen2.5-72B-Instruct"
OUTDIR="Processed Data/experiments/benchmark"

# Task 1: gold-set (100 human-labelled descriptions) -> for scoring
# Task 2: full treatments (3,857 species) -> the dataset for this model
python scripts/11_Extract_Multimodel.py \
  --model "$MODEL" \
  --task "Processed Data/experiments/gold_set_labeled.csv::raw_text_snippet::species_id::${OUTDIR}/gold_pred_qwen72b.csv" \
  --task "Processed Data/experiments/species_descriptions_treatments.csv::raw_text::species_id::${OUTDIR}/treatments_pred_qwen72b.csv"
