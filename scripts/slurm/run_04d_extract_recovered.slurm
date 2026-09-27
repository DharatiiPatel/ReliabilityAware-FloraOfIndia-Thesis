#!/bin/bash
#SBATCH --job-name=qwen_recovered
#SBATCH --partition=gpu_p
#SBATCH --gres=gpu:A100:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/qwen_recovered_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/qwen_recovered_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

# Colour extraction for recovered lost-species treatments.
# Submit with: sbatch --dependency=afterok:<recover_jobid> scripts/slurm/run_04d_extract_recovered.slurm
# Expects recovered_descriptions_for_extract.csv from job 31.

set -euo pipefail

# Avoid module purge (breaks module system on this cluster).
module load Python/3.13.5-GCCcore-14.3.0
export HF_HOME=/scratch/dp23301/.cache/huggingface
export HF_HUB_OFFLINE=1

cd /scratch/dp23301/Thesis
mkdir -p logs

echo "host=$(hostname)  date=$(date)"
nvidia-smi || true

IN="Processed Data/experiments/recovered_descriptions_for_extract.csv"
if [[ ! -f "$IN" ]]; then
  echo "Missing $IN - recovery job did not produce extract input"; exit 1
fi
echo "input rows: $(($(wc -l < "$IN") - 1))"

python scripts/04d_Extract_Recovered_Colour.py
echo "DONE $(date)"
ls -la "Processed Data/experiments/flower_color_recovered.csv"
