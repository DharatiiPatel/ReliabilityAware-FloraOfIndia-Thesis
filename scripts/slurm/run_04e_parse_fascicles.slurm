#!/bin/bash
#SBATCH --job-name=parse_fasc
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/parse_fasc_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/parse_fasc_%j.err

set -euo pipefail
module load Python/3.13.5-GCCcore-14.3.0
cd /scratch/dp23301/Thesis
mkdir -p logs
python scripts/04e_Parse_Fascicles.py
