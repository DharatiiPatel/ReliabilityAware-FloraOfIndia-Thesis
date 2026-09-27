# Pipeline audit notes

Obsolete parallel output trees (`corrected_v2/`, `v2_fixed_cohort/`) were
removed when the repository was returned to a single canonical pipeline. Those
directory names are retained here only as prohibited legacy paths rejected by
safety guards.

**Active design**

- Primary environmental cohort: **n = 1,438** (historical V1 labels; fixed
  species sample for V2 sensitivity and reliability work).
- V2 categoriser: `scripts/14_Categorize_v2.py` + `scripts/lib/colour_categoriser.py`
- Docs: `docs/V2_CATEGORISER.md`
- Checkpoint of pre-cleanup obsolete parallel outputs: git branch
  `checkpoint/pre-v2-cleanup-2026-09-25`

**Historical development provenance**

An earlier environment-linked development table (n = 1,174) remains under
`Processed Data/experiments/expansion/step05b_outputs_clean/` and related
`*_clean` MCMC paths. It documents a development checkpoint in the
environment-matching workflow. The published primary analysis cohort is
n = 1,438. Scripts such as `scripts/slurm/run_06_08_clean_rerun.slurm` can
regenerate that historical set for continuity checks; they are not the thesis
primary result.

**Canonical experiment paths**

| Analysis | Path |
|----------|------|
| Categoriser evaluation | `Processed Data/experiments/categorizer_evaluation/` |
| Label sensitivity | `Processed Data/experiments/label_sensitivity/` |
| Reliability | `Processed Data/experiments/reliability/` |
| Prediction | `Processed Data/experiments/prediction/` |
| Method figures | `Results/figures/methods/` |

Historical primary MCMC/PCA remain under `expansion/step06_outputs/` and related
paths.
