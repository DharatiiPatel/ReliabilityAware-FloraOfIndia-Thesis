#!/bin/bash
#SBATCH --job-name=recover_lost
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/recover_lost_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/recover_lost_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

# Re-locate treatment text for parse-failed UNKNOWN species in existing
# volume OCR (no new OCR). Writes recovered_treatments.csv and the slim
# extract-input CSV for the follow-on GPU colour job.

set -euo pipefail

# Do not module purge - keep module system intact. Python module is enough.
module load Python/3.13.5-GCCcore-14.3.0

cd /scratch/dp23301/Thesis
mkdir -p logs

echo "host=$(hostname)  date=$(date)"
python scripts/04c_Recover_Lost_Treatments.py
echo "DONE $(date)"
ls -la "Processed Data/experiments/recovered_treatments.csv" \
       "Processed Data/experiments/recovered_descriptions_for_extract.csv" \
       "Processed Data/experiments/recovered_treatments_summary.json"
