#!/bin/bash
#SBATCH --job-name=rel_ecology
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/reliability_ecology_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/reliability_ecology_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

set -euo pipefail
cd /scratch/dp23301/Thesis
mkdir -p logs
module load R/4.5.1-gfbf-2025a
# Match scripts/06_MCMCglmm.R chain length. Runs 3 independent chains per model
# (~9 h total); inference pools them and Gelman-Rubin MPSRF is written to
# reliability_convergence.csv.
export RELIABILITY_FULL=1
unset MCMC_SMOKE || true
Rscript scripts/25_Reliability_Ecology.R
# export thinned chain draws so the convergence panel (fig18) can be built
Rscript scripts/28_Export_Reliability_Draws.R
# figures need matplotlib; base Python module lacks it, use the repo venv
.venv_figs/bin/python scripts/26_Build_Reliability_Figures.py
