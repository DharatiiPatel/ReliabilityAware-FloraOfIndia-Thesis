#!/bin/bash
#SBATCH --job-name=qwen7b_gold
#SBATCH --partition=gpu_p
#SBATCH --gres=gpu:A100:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/qwen7b_gold_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/qwen7b_gold_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

module purge
unset PYTHONPATH
module load Python/3.13.5-GCCcore-14.3.0
export HF_HOME=/scratch/dp23301/.cache/huggingface

cd /scratch/dp23301/Thesis

# Re-run the 7B model on ALL 98 gold descriptions (not just the 70 that survived
# the clean parser) so every model is scored on the same rows.
python scripts/11_Extract_Multimodel.py \
  --model "Qwen/Qwen2.5-7B-Instruct" \
  --task "Processed Data/experiments/gold_set_labeled.csv::raw_text_snippet::species_id::Processed Data/experiments/benchmark/gold_pred_qwen7b_full.csv"
