#!/bin/bash
#SBATCH --job-name=rag_qwen7b_gold
#SBATCH --partition=gpu_p
#SBATCH --gres=gpu:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/rag_qwen7b_gold_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/rag_qwen7b_gold_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

module purge
unset PYTHONPATH
module load Python/3.13.5-GCCcore-14.3.0
export HF_HOME=/scratch/dp23301/.cache/huggingface

cd /scratch/dp23301/Thesis

python scripts/15_RAG_Extract_Gold.py \
  --model "Qwen/Qwen2.5-7B-Instruct" \
  --top-k 3 \
  --out "Processed Data/experiments/categorizer_evaluation/gold_pred_qwen7b_rag.csv"
