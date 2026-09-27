# Sample flow

## Primary environmental cohort

Corpus processing, recovery, fascicle parsing, colour extraction and
environmental matching produced the final primary environmental dataset of
**n = 1,438** species in
`Processed Data/experiments/expansion/step05b_outputs/species_color_environment_final_expanded.csv`.

Pipeline retention (Figure 5):

| Stage | n |
|---|---:|
| Unique species treatments | 3,857 |
| Treatments with a morphological description | 3,230 |
| Known flower colour (corpus extracts) | 1,674 |
| Environment-linked primary analysis set | **1,438** |

Primary ecology labels on this table are historical **V1**. Not every parsed
treatment enters the environmental analysis; attrition reflects missing
descriptions, absent colour statements, and environment-matching filters.

## V2 within the primary cohort

Error analysis of V1 motivated V2. V2 was applied within the fixed n = 1,438
environmental species anchor for categoriser evaluation, label-source
sensitivity and reliability, without changing the species sample or re-running
GBIF, environmental extraction or PCA. V2-known versus V2-UNKNOWN/OTHER
attrition is reported with the label-sensitivity outputs.

## Related canonical folders

- `categorizer_evaluation/` — V1 vs V2 scores, RAG evaluation, error taxonomy
- `label_sensitivity/` — equal-cohort LLM label variants (n = 1,149)
- `reliability/` — common-known (n = 1,149) / high-confidence (n = 1,129)
- `prediction/` — environmental prediction
