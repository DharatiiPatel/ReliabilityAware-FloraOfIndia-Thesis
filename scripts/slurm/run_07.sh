#!/bin/bash
#SBATCH --job-name=figures
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/figures_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/figures_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

cd /scratch/dp23301/Thesis
module load R/4.5.1-gfbf-2025a
# Primary ecology figures (n=1,438).
Rscript scripts/07_Generate_Figures.R