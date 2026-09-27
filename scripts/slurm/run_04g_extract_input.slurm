#!/bin/bash
#SBATCH --job-name=build_extract_in
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/build_extract_in_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/build_extract_in_%j.err

set -euo pipefail
module load Python/3.13.5-GCCcore-14.3.0
cd /scratch/dp23301/Thesis
python scripts/04g_Build_Analysis_Set.py --stage extract-input
