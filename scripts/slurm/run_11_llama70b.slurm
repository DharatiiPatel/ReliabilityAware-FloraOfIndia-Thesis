#!/bin/bash
#SBATCH --job-name=llama70b_extract
#SBATCH --partition=gpu_p
#SBATCH --gres=gpu:A100:2
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=256G
#SBATCH --time=48:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/llama70b_extract_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/llama70b_extract_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

# Clean environment
module purge
unset PYTHONPATH
module load Python/3.13.5-GCCcore-14.3.0

export HF_HOME=/scratch/dp23301/.cache/huggingface

# Llama is gated — token required. Prefer a local file outside the git repo:
#   echo 'hf_...' > ~/.hf_token && chmod 600 ~/.hf_token
if [ -z "$HF_TOKEN" ] && [ -f "$HOME/.hf_token" ]; then
  export HF_TOKEN="$(tr -d '[:space:]' < "$HOME/.hf_token")"
fi
if [ -z "$HF_TOKEN" ]; then
  echo "ERROR: HF_TOKEN not set and ~/.hf_token not found."
  echo "Create a Read token at https://huggingface.co/settings/tokens"
  echo "then:  echo 'hf_...' > ~/.hf_token && chmod 600 ~/.hf_token"
  exit 1
fi

cd /scratch/dp23301/Thesis

MODEL="meta-llama/Llama-3.3-70B-Instruct"
OUTDIR="Processed Data/experiments/benchmark"

# Same tasks as Qwen-72B: gold-set scoring + full treatments (label-source inputs)
python scripts/11_Extract_Multimodel.py \
  --model "$MODEL" \
  --task "Processed Data/experiments/gold_set_labeled.csv::raw_text_snippet::species_id::${OUTDIR}/gold_pred_llama70b.csv" \
  --task "Processed Data/experiments/species_descriptions_treatments.csv::raw_text::species_id::${OUTDIR}/treatments_pred_llama70b.csv"
