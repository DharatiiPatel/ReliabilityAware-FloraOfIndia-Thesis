#!/bin/bash
#SBATCH --job-name=label_sens_mcmc
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=08:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/label_sens_mcmc_%A_%a.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/label_sens_mcmc_%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

# Label-sensitivity MCMCglmm array (equal cohort n=1149; 27 tasks).
# Build manifest first:
#   python scripts/18_Make_MCMC_Manifest.py
# Submit with the array range printed by script 18, e.g.:
#   sbatch --array=0-26 scripts/slurm/run_19_array.slurm
# Each task runs ONE (variant x colour x chain) MCMCglmm.
# Do not include baseline / four_source / secondary / prohibited legacy wp4 paths
# in the main label-sensitivity array.

module purge
unset PYTHONPATH
module load R/4.5.1-gfbf-2025a

cd /scratch/dp23301/Thesis
Rscript scripts/19_MCMCglmm_Array.R
