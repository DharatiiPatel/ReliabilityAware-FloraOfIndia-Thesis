#!/bin/bash
#SBATCH --job-name=ocr_fasc
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --array=1-24%6
#SBATCH --output=/scratch/dp23301/Thesis/logs/ocr_fasc_%A_%a.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/ocr_fasc_%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

# OCR all 24 Fascicles of Flora of India (array task = fascicle number).
# Writes sidecar .txt only permanently; OCR PDF is deleted after sidecar exists
# to avoid ~200 MB/fascicle storage blow-up (F11 OCR PDF was 229 MB).
#
# Do NOT module purge on this cluster - it breaks the module system.
# Skip if sidecar .txt already exists and looks complete (>50 KB).

set -euo pipefail

module load Ghostscript/10.03.1-GCCcore-13.3.0
module load tesseract/5.5.0-GCCcore-13.3.0
module load ocrmypdf/16.12.0-GCCcore-13.3.0-gbpip

cd /scratch/dp23301/Thesis
mkdir -p logs raw_data/fascicles

N="${SLURM_ARRAY_TASK_ID}"
MANIFEST=scripts/lib/fascicle_manifest.csv
# manifest columns: n,slug,pdf_name
line=$(awk -F, -v n="$N" '$1==n {print; exit}' "$MANIFEST")
if [[ -z "$line" ]]; then
  echo "No manifest row for fascicle $N"; exit 1
fi
slug=$(echo "$line" | cut -d, -f2)
PDF="raw_data/fascicles/F${N}_${slug}.pdf"
TXT="raw_data/fascicles/F${N}_${slug}.txt"
TMP_PDF="raw_data/fascicles/F${N}_${slug}_ocr_tmp.pdf"

# Legacy F11 naming from the pilot
if [[ "$N" == "11" && ! -f "$PDF" && -f raw_data/fascicles/F11_Cucurbitaceae.pdf ]]; then
  PDF=raw_data/fascicles/F11_Cucurbitaceae.pdf
fi
if [[ "$N" == "11" && ! -f "$TXT" && -f raw_data/fascicles/F11_Cucurbitaceae.txt ]]; then
  # Reuse completed pilot sidecar under the canonical name
  cp -f raw_data/fascicles/F11_Cucurbitaceae.txt "$TXT"
  echo "F${N}: reused pilot sidecar -> $TXT"
  wc -l -c "$TXT"
  exit 0
fi

echo "host=$(hostname)  date=$(date)  fascicle=$N slug=$slug"
echo "PDF=$PDF"

if [[ ! -f "$PDF" ]]; then
  echo "Missing PDF: $PDF  (run 04b_Download_Fascicles.py first)"; exit 1
fi

if [[ -f "$TXT" ]] && [[ $(wc -c < "$TXT") -gt 50000 ]]; then
  echo "F${N}: sidecar already complete ($(wc -c < "$TXT") bytes) - skipping OCR"
  exit 0
fi

which gs tesseract ocrmypdf
ocrmypdf \
  --force-ocr \
  --jobs "${SLURM_CPUS_PER_TASK}" \
  --sidecar "$TXT" \
  --output-type pdf \
  "$PDF" \
  "$TMP_PDF"

# Sidecar is the durable product; drop the ballooned OCR PDF.
rm -f "$TMP_PDF"
# Also drop any leftover pilot OCR PDF for F11
rm -f raw_data/fascicles/F11_Cucurbitaceae_ocr.pdf

echo "DONE $(date)"
ls -la "$TXT"
wc -l -c "$TXT"
head -20 "$TXT"
