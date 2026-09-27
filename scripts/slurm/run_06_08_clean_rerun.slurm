#!/bin/bash
# Regenerate the historical n=1,174 "clean" ecology outputs that back the
# comparison column in docs/VERIFIED_Numbers_for_Thesis.md §1b and §7d.
# The original step06_outputs_clean/ and step08_outputs_clean/ were deleted in a
# repo cleanup, leaving those numbers unverifiable; this rebuilds them.
#
# ECOLOGY_SET=clean redirects input/output and (in step 08) suppresses copying
# into Results/, so the published n=1,438 figures are never touched.
#SBATCH --job-name=clean_rerun
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=48:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/clean_rerun_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/clean_rerun_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

set -euo pipefail
cd /scratch/dp23301/Thesis
mkdir -p logs
module load R/4.5.1-gfbf-2025a

export ECOLOGY_SET=clean
unset SKIP_ELEV_MCMC || true

echo "=== Step 06 on clean set (n=1,174) ==="
Rscript scripts/06_MCMCglmm.R

echo "=== Step 08 on clean set (n=1,174) ==="
Rscript scripts/08_ElevationGradient_Analysis.R

echo "=== Done. Outputs: ==="
ls -1 "Processed Data/experiments/step06_outputs_clean/tables/combined/" || true
ls -1 "Processed Data/experiments/step08_outputs_clean/" || true
