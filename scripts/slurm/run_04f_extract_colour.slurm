#!/bin/bash
#SBATCH --job-name=qwen_expand
#SBATCH --partition=gpu_p
#SBATCH --gres=gpu:A100:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/qwen_expand_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/qwen_expand_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

set -euo pipefail
module load Python/3.13.5-GCCcore-14.3.0
export HF_HOME=/scratch/dp23301/.cache/huggingface
export HF_HUB_OFFLINE=1
cd /scratch/dp23301/Thesis
mkdir -p logs
nvidia-smi || true
python scripts/04f_Extract_Additional_Colour.py
