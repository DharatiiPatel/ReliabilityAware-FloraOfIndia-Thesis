#!/bin/bash
#SBATCH --job-name=mcmcglmm
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/mcmcglmm_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/mcmcglmm_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

cd /scratch/dp23301/Thesis
module load R/4.5.1-gfbf-2025a
Rscript scripts/06_MCMCglmm.R