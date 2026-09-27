#!/bin/bash
#SBATCH --job-name=elevation
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/elevation_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/elevation_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

# Historical primary elevation MCMCglmm (n=1,438 V1 labels).
# Three independent chains per colour (seeds 42,123,456); strict MPSRF<1.01 gate.
# Does NOT run primary PC models, label-sensitivity, or reliability.

set -euo pipefail
cd /scratch/dp23301/Thesis
mkdir -p logs
module load R/4.5.1-gfbf-2025a
echo "Starting Step 08: Elevation Gradient Analysis (n=1,438; 3 chains/colour)"
unset SKIP_ELEV_MCMC || true
unset ECOLOGY_SET || true
export ECOLOGY_SET=primary
Rscript scripts/08_ElevationGradient_Analysis.R
