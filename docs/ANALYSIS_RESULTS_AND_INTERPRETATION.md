# Results notes (V2-related)

See [`V2_CATEGORISER.md`](V2_CATEGORISER.md) for the active V2 categoriser.

## Two label systems

- **Historical V1** defines the fixed **n = 1,438** primary ecology analysis
  (WHITE=613, YELLOW=494, REDTYPE=331).
- **V2** is the canonical categoriser for label-source sensitivity and
  reliability. Comparison across V1 primary versus V2 sensitivity tests whether
  ecological conclusions depend on label construction.
- V2 does not replace the historical primary analysis table.

Global GBIF occurrences (not India-only) are an intentional scope choice for
the environmental sample.

## Primary PC models (historical; not re-run in the 2026-09 closeout)

- Fitted by `scripts/06_MCMCglmm.R` on
  `Processed Data/experiments/expansion/step05b_outputs/species_color_environment_final_expanded.csv`.
- Three chains were fitted at runtime with seeds **42, 123, 456**.
- Gelman–Rubin diagnostics were calculated during that run; recorded max PSRF
  and MPSRF were below **1.01** (see `Results/tables/mcmc/gelman_rubin_*.csv`).
- **Only the seed-42 posterior object was retained** as
  `…/step06_outputs/models/model_{WHITE,YELLOW,REDTYPE}.rds`.
- Numerical convergence evidence from the original run is therefore available,
  but the original three-chain posterior objects cannot now be independently
  reconstructed from stored RDS files.
- The primary PC input dataset was not originally bound to the model objects
  with embedded SHA-256 hashes.
- All three historical primary PC chain objects are not currently retained on disk.

## Primary elevation models (hardened)

- Fitted by `scripts/08_ElevationGradient_Analysis.R` on the same fixed V1
  n=1,438 cohort with scaled elevation and a genus random intercept.
- Three independent chains per colour (seeds **42, 123, 456**);
  nitt=1,050,000, burnin=50,000, thin=100; HPD95; ESS; PSRF/MPSRF with a
  strict **&lt; 1.01** publication gate.
- All three chains’ Sol draws and provenance are retained as
  `chains_elev_{WHITE,YELLOW,REDTYPE}.rds` alongside compatibility
  `model_elev_*.rds` (chain 1).
- Dataset SHA-256 values and label source (`historical_primary_V1`) are
  recorded in `elevation_run_metadata.json` and `elevation_convergence.csv`.

## Final ecological interpretation (predefined robustness)

Across historical primary, V2 label-sensitivity (n=1,149), and V2 reliability
(common-known / high-confidence):

- **WHITE–PC2** (positive) and **YELLOW–PC2** (negative) are the only
  predefined **robust** ecological effects.
- **REDTYPE–PC3** appeared in the historical primary analysis but did not
  survive V2 label-source and reliability analyses → **not robust**.
- **Elevation** effects, even if supported under historical V1, did not
  survive the strict V2 reliability analysis → not final robust conclusions.
- Causal relationships are not claimed.

## Prediction (supporting, not central)

- Genus-grouped CV: random forest was the best environment model among
  logreg/RF, but macro_f1_3class gains over the majority baseline were modest.
- Model selection and performance estimation use the same grouped CV
  (not nested CV). Grouped-CV uncertainty uses genus-cluster bootstrap.
- The ungrouped genus-prior result is evidence of random-split genus
  leakage / within-genus information leakage, not proof that biological
  relatedness predicts colour.
- Permutation importance uses the **same** best model on held-out
  genus-grouped folds (macro_f1_3class drop, with fold SD). Drops are small;
  environment does not strongly determine flower colour, and PC2 is not
  necessarily the top predictive variable under that design.

## Canonical experiment folders

- `Processed Data/experiments/categorizer_evaluation/`
- `Processed Data/experiments/label_sensitivity/`
- `Processed Data/experiments/reliability/`
- `Processed Data/experiments/prediction/`
- Primary PC/elevation internals:
  `Processed Data/experiments/expansion/step06_outputs/`,
  `Processed Data/experiments/expansion/step08_outputs/`

## Reproducibility limitation: `unknown_diagnosis.csv`

`Processed Data/experiments/unknown_diagnosis.csv` (2,140 rows; causes such as
EMPTY / NO_COLOUR_STATED / …) is **read** by `scripts/04a_Verify_Recoverable.py`
and `scripts/04c_Recover_Lost_Treatments.py` but has **no in-repo producer**.
Git history does not track it (Processed Data is ignored). It cannot be
deterministically reconstructed from repository evidence, so it is retained as
a manual/intermediate diagnostic artifact. The fixed n=1,438 primary ecology
CSV and completed MCMC inputs are preserved independently of this file; the
gap does not invalidate those analytical datasets.
