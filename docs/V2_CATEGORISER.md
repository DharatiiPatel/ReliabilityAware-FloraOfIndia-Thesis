# V2 categoriser

**Entry:** `scripts/14_Categorize_v2.py`  
**Implementation:** `scripts/lib/colour_categoriser.py`  
**Tests:** `tests/test_colour_categoriser.py`

## Metadata

| Field | Value |
|-------|-------|
| `categorizer_name` | `V2` |
| `categorizer_version` | `2` |
| `categorizer_sha256` | computed from `colour_categoriser.py` |
| `primary_anchor_n` | `1438` |

## Role

The 1,438-species primary cohort was constructed before the categorisation
refinement. Error analysis of V1 motivated V2. V2 was subsequently applied
within the primary cohort to evaluate label sensitivity and downstream
reliability without changing the environmental species sample, and without
re-running GBIF, environmental extraction or PCA.

Historical primary ecology uses **V1** labels. Label sensitivity and
reliability use **V2** labels. That duality is intentional.

See [`ANALYSIS_RESULTS_AND_INTERPRETATION.md`](ANALYSIS_RESULTS_AND_INTERPRETATION.md)
for primary PC retention limits, hardened elevation provenance, and the final
robust-effect summary.

## Terminology

| Name | Meaning |
|------|---------|
| **V1** | Original categoriser (`scripts/03_04_Categorize_and_Prepare.py`). Unchanged. |
| **V2** | This categoriser. Used for label sensitivity and reliability. |

Allowed phrasing: V2 categoriser, V2 labels, V2 reclassification, V2 sensitivity analysis.

## Disclosure

V2 is not externally validated. Gold-set scores that use the same gold set are
method-development evaluation, not independent external validation.

## Canonical related paths

| Analysis | Path |
|----------|------|
| Categoriser evaluation | `Processed Data/experiments/categorizer_evaluation/` |
| Label sensitivity | `Processed Data/experiments/label_sensitivity/` |
| Reliability | `Processed Data/experiments/reliability/` |
| Prediction | `Processed Data/experiments/prediction/` |
| Method figures | `Results/figures/methods/` |
