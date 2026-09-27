#!/bin/bash
# Submit fascicle OCR + treatment recovery as one dependent chain.
#
# Usage:  bash scripts/slurm/submit_full_dataset.sh
# Then:   squeue -u $USER

set -euo pipefail
cd /scratch/dp23301/Thesis
mkdir -p logs "Processed Data/experiments/expansion"

echo "=== 0. Download missing fascicle PDFs (lightweight) ==="
module load Python/3.13.5-GCCcore-14.3.0
python scripts/04b_Download_Fascicles.py

# Drop ballooned pilot OCR PDF if present (sidecar txt is enough)
rm -f raw_data/fascicles/F11_Cucurbitaceae_ocr.pdf

echo ""
echo "=== 1. Submit jobs ==="

OCR=$(sbatch --parsable scripts/slurm/run_04b_ocr_fascicles_array.slurm)
echo "OCR_ARRAY          $OCR  (array 1-24%6)"

REC=$(sbatch --parsable scripts/slurm/run_04c_recover_lost.slurm)
echo "RECOVER_LOST       $REC"

PARSE=$(sbatch --parsable --dependency=afterok:${OCR} scripts/slurm/run_04e_parse_fascicles.slurm)
echo "PARSE_FASCICLES    $PARSE  afterok:$OCR"

BUILD_EX=$(sbatch --parsable --dependency=afterok:${PARSE}:${REC} scripts/slurm/run_04g_extract_input.slurm)
echo "BUILD_EXTRACT_IN   $BUILD_EX  afterok:$PARSE:$REC"

QWEN=$(sbatch --parsable --dependency=afterok:${BUILD_EX} scripts/slurm/run_04f_extract_colour.slurm)
echo "QWEN_EXPAND        $QWEN  afterok:$BUILD_EX  (GPU)"

BUILD_GB=$(sbatch --parsable --dependency=afterok:${QWEN} scripts/slurm/run_04g_gbif_input.slurm)
echo "BUILD_GBIF_IN      $BUILD_GB  afterok:$QWEN"

GBIF=$(sbatch --parsable --dependency=afterok:${BUILD_GB} scripts/slurm/run_05a.sh)
echo "GBIF               $GBIF  afterok:$BUILD_GB"

ENV=$(sbatch --parsable --dependency=afterok:${GBIF} scripts/slurm/run_05b.sh)
echo "ENV                $ENV  afterok:$GBIF"

MCMC=$(sbatch --parsable --dependency=afterok:${ENV} scripts/slurm/run_06.sh)
echo "MCMC               $MCMC  afterok:$ENV"

ELEV=$(sbatch --parsable --dependency=afterok:${ENV} scripts/slurm/run_08.slurm)
echo "ELEVATION          $ELEV  afterok:$ENV"

FIG=$(sbatch --parsable --dependency=afterok:${MCMC}:${ELEV} scripts/slurm/run_07.sh)
echo "FIG                $FIG  afterok:$MCMC:$ELEV"

JOBS_FILE=Processed\ Data/experiments/expansion/JOB_CHAIN.txt
cat > "$JOBS_FILE" <<EOF
Primary (n=1,438) job chain submitted $(date -Is)

OCR_ARRAY=$OCR
RECOVER_LOST=$REC
PARSE_FASCICLES=$PARSE
BUILD_EXTRACT_IN=$BUILD_EX
QWEN_COLOUR=$QWEN
BUILD_GBIF_IN=$BUILD_GB
GBIF=$GBIF
ENV=$ENV
MCMC=$MCMC
ELEVATION=$ELEV
FIG=$FIG

Dependency graph:
  OCR_ARRAY ──────────────────────────> PARSE_FASCICLES ──┐
  RECOVER_LOST ───────────────────────────────────────────┴> BUILD_EXTRACT_IN
        -> QWEN_COLOUR -> BUILD_GBIF_IN -> GBIF -> ENV
        -> MCMC (after ENV)
        -> ELEVATION (after ENV)
        -> FIG (after MCMC and ELEVATION)

Monitor:
  squeue -u \$USER
  tail -f logs/ocr_fasc_${OCR}_*.out
  tail -f logs/recover_lost_${REC}.out
  tail -f logs/qwen_expand_${QWEN}.out
  tail -f logs/gbif_${GBIF}.out
  tail -f logs/mcmcglmm_${MCMC}.out

Outputs (Processed Data/experiments/expansion/ unless noted):
  fascicle OCR txt:     raw_data/fascicles/F{N}_{slug}.txt
  recovered texts:      ../recovered_treatments.csv (parent experiments/)
  new descriptions:     new_descriptions_for_extract.csv
  new colours:          flower_color_new.csv
  GBIF new:             gbif_outputs/gbif_occurrences_new.csv
  combined occ:         gbif_outputs/gbif_occurrences_combined.csv
  env+PCA final:        step05b_outputs/species_color_environment_final_expanded.csv
  MCMCglmm:             step06_outputs/
  elevation:            step08_outputs/
  figures:              figures/ and Results/figures/
EOF

echo ""
echo "Wrote $JOBS_FILE"
echo ""
squeue -u "$USER"
