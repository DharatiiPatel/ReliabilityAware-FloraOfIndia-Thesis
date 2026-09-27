#!/bin/bash
#SBATCH --job-name=mcmc_sv
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=72:00:00
#SBATCH --array=0-2
#SBATCH --output=/scratch/dp23301/Thesis/logs/mcmc_sv_%A_%a.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/mcmc_sv_%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

# Array task 0=WHITE, 1=YELLOW, 2=REDTYPE (single-variable MCMC only)
COLORS=(WHITE YELLOW REDTYPE)
COLOR=${COLORS[$SLURM_ARRAY_TASK_ID]}

cd /scratch/dp23301/Thesis
module load R/4.5.1-gfbf-2025a
echo "Running single-variable MCMC for: ${COLOR}"
Rscript scripts/06b_SingleVariable_MCMCglmm.R "${COLOR}"
