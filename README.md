# Reliability-Aware Flower-Colour Extraction from the Flora of India

MS Computer Science thesis (Dharati Patel, University of Georgia).

**Contribution:** which open-LLM flower-colour labels are reliable enough for
downstream ecological inference — not “we used LLMs to extract colour.”

Protocol: three open extractors (Qwen-7B, Qwen-72B, Llama-3.3-70B) on a **fixed**
environment-linked species list; **high confidence = exact agreement** among the
three LLMs on a known class; a cheap **lexical** source-text check is a parallel
diagnostic (it does not create the high-confidence cohort and does not
automatically exclude species from MCMC). Ecology models are re-run on the
common known-label support vs the high-confidence subset. The keyword baseline
is a benchmark only. UNKNOWN is never coded as “not white / not yellow / not
redtype.” Models are genus-adjusted, not phylogenetically corrected.

Scripts are numbered `01a`–`28`. See `scripts/README.md`.
Reliability chapter: `24`–`26`, `28`. Regression audit of every cited number: `27`.

## Layout

```
Thesis/
├── Results/                 figures and tables for the thesis
│   ├── figures/ecology/     fig1–fig6
│   ├── figures/methods/     fig7–fig14
│   ├── figures/reliability/ fig15–fig18
│   ├── figures/supplementary/
│   └── tables/              mcmc/, elevation/, descriptive/
├── docs/
│   ├── VERIFIED_Numbers_for_Thesis.md
│   ├── Reliability_Protocol.md
│   ├── FINAL_SAMPLE_FLOW.md
│   ├── ANALYSIS_RESULTS_AND_INTERPRETATION.md
│   ├── PIPELINE_AUDIT.md
│   ├── V2_CATEGORISER.md
│   └── RUN_MANIFEST.tsv
├── scripts/                 01a–28, then lib/ and slurm/
├── Processed Data/          pipeline outputs (gitignored)
└── raw_data/                Flora of India PDFs (gitignored)
```

## Key numbers

| Quantity | Value |
|---|---:|
| Unique treatments | 3,857 |
| With morphological description | 3,230 |
| Ecology *n* (primary) | 1,438 |
| WHITE / YELLOW / REDTYPE | 613 / 494 / 331 |
| Gold set labelled | 98 |
| Best gold-set accuracy | 0.949 (Qwen-7B, RAG + categoriser v2) |

Always cite the categoriser with an accuracy: 0.878 is zero-shot + v1,
0.929 is the same predictions + v2, 0.949 is RAG + v2.
Provenance: `docs/VERIFIED_Numbers_for_Thesis.md`.

## Execution scope and path resolution

Portable tests, scoring, the numerical audit (`scripts/27`), and figure scripts
resolve the repository or technical-package root from the script location (or
from an explicit override). They do **not** hard-code a cluster checkout path.

- Python: set `THESIS_ROOT` to override; otherwise the root is the parent of
  `scripts/` derived from `__file__`.
- R: set `THESIS_BASE` to override; otherwise the root is derived from the
  script’s `--file` path (falling back to `getwd()` only when `--file` is
  absent).
- `scripts/slurm/` wrappers remain configured for Dharati’s Sapelo checkout and
  are intentionally cluster-specific.

Raw Flora PDFs, complete GBIF occurrence downloads, and the cluster software
stack are **not** bundled in the technical package. That omission prevents a
complete from-scratch reconstruction outside the cluster, but packaged
derived-data audits, unit tests and figure inspection remain portable.

```bash
module load R/4.5.1-gfbf-2025a
Rscript scripts/07_Generate_Figures.R

python -m venv .venv_figs && .venv_figs/bin/pip install matplotlib numpy pandas scikit-learn
# 22 now publishes straight into Results/figures/methods/ (no manual copy step)
.venv_figs/bin/python scripts/22_Build_Method_Figures.py
.venv_figs/bin/python scripts/21_Predict_Colour_from_Env.py
# 23 publishes fig14 into Results/figures/methods/ (same as 22)
.venv_figs/bin/python scripts/23_Build_Prediction_Figure.py

python scripts/24_Build_Reliability_Set.py
.venv_figs/bin/python scripts/26_Build_Reliability_Figures.py
# Ecology robustness (cluster; RELIABILITY_FULL=1 matches step 06 chain length;
# runs 25 then rebuilds the figures):
#   sbatch scripts/slurm/run_25_reliability_ecology.slurm
```
