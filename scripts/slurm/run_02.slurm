#!/bin/bash
#SBATCH --job-name=qwen_clean_extract
#SBATCH --partition=gpu_p
#SBATCH --gres=gpu:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/qwen_clean_%A.out

# Start from a clean module/env state (avoid inherited PYTHONPATH pollution)
module purge
unset PYTHONPATH
module load Python/3.13.5-GCCcore-14.3.0

# Store HF cache on scratch
export HF_HOME=/scratch/dp23301/.cache/huggingface

cd /scratch/dp23301/Thesis

python "scripts/02_Extract_Flower_Colour.py"
