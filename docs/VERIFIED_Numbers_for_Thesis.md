# Verified numbers

Locked values from the published outputs. Every quantity below is recomputed by
`scripts/27_Audit_All_Numbers.py`. Use the cited CSV when a table rounds.

---

## 1. Primary analysis set

Source: `Processed Data/experiments/expansion/step05b_outputs/species_color_environment_final_expanded.csv`.
The folder name `expansion/` is a leftover path; this is the published analysis.
Figures under `Results/figures/` are written by `scripts/07_Generate_Figures.R`.

| Quantity | Value |
|---|---:|
| Unique species treatments | 3,857 |
| Treatments with a morphological description | 3,230 |
| Analysis *n* | **1,438** |
| WHITE / YELLOW / REDTYPE | **613 / 494 / 331** |

---

## 2. Dataset construction and primary elevation

Corpus processing, recovery, fascicle parsing, colour extraction and
environmental matching produced the final primary environmental dataset of
**n = 1,438**. Pipeline retention is summarised in Figure 5
(3,857 → 3,230 → 1,674 → 1,438). Primary ecology labels are historical V1.

Primary elevation (n = 1,438) was re-hardened (2026-09-26) to three
independent chains (seeds 42, 123, 456) with HPD95, ESS, and MPSRF/max PSRF
&lt; 1.01 (`elevation_convergence.csv`, `elevation_run_metadata.json`,
`chains_elev_*.rds`).

| Test | Primary n = 1,438 (3-chain) |
|---|---|
| χ² colour × elevation band | X² = 31.25, p = 0.00013 |
| WHITE ~ elevation | −0.123, HPD [−0.229, −0.019], pMCMC = 0.021 |
| YELLOW ~ elevation | +0.011, HPD includes 0, pMCMC = 0.862 |
| REDTYPE ~ elevation | +0.174, HPD [+0.052, +0.294], pMCMC = 0.0054 |
| Max MPSRF | ≤ 1.0002 |

On the primary set, colour composition differs across elevation bands; after
genus control, WHITE declines and REDTYPE increases with elevation. YELLOW has
no elevation association. These V1 elevation associations are not final
robust conclusions: they did not survive the V2 reliability framework
(common-known / high-confidence). Elevation is therefore not reported as a
robust novel ecological contribution.


---

## 3. Multiple testing

Each colour × environment analysis is a grid of tests. Benjamini-Hochberg
q-values are recomputed from the published CSVs by `27_Audit_All_Numbers.py`.

| Analysis | Tests | Expected FP at 0.05 | Raw significant | Survives BH q < 0.05 |
|---|---:|---:|---:|---|
| Primary ecology, colour × PC1-PC10 | 30 | 1.5 | 3 | WHITE ~ PC2 (q = 0.006), YELLOW ~ PC2 (q = 0.015) |
| Primary elevation, colour × `alt_scaled` | 3 | 0.15 | 2 | REDTYPE (q = 0.019), WHITE (q = 0.034) |
| Label-source grid (3 LLMs, equal cohort n=1,149) | 90 | 4.5 | 9 | No single effect retains BH q < 0.05 over the full 90-test grid; WHITE ~ PC2 and YELLOW ~ PC2 are significant under all three LLM sources |
| Reliability chapter (pre-specified) | 12 | 0.6 | 4 | all 4 (WHITE / YELLOW × PC2, q ≤ 0.013) |

WHITE ~ PC2 (positive) and YELLOW ~ PC2 (negative) survive BH in the primary
PC and reliability families, hold under the three-LLM equal cohort (all three
sources; HPD excludes 0), and are the only predefined **robust** ecological
effects.

REDTYPE ~ PC3 on the primary set (p = 0.0162) has q = 0.162 and does not survive
correction over the 30-test grid; it also fails under V2 label-sensitivity and
reliability. Elevation slopes can survive BH within the primary V1 elevation
family but are **not robust** under the complete V2 reliability framework.

---

## 4. Gold set

| Quantity | Value |
|---|---:|
| Template rows | 100 |
| Human-labelled | **98** |
| Unlabelled (excluded from scoring) | **2** (row 49 genus header `Ginalloa Korth.`; row 100 incomplete `Erigeron uniflorus` stub) |

---

## 5. Benchmark (categoriser v1)

Scored only on rows that have a gold label and a prediction.
Source predictions: `benchmark/gold_pred_*.csv`.
Summary: `benchmark/benchmark_summary.csv`.

| Model | n | Accuracy | Cohen's κ | macro_f1_target4 | macro_f1_all5 | Wrong |
|---|---:|---:|---:|---:|---:|---:|
| Rule baseline | 97 | 0.7629 | 0.6956 | 0.8035 | 0.6428 | 23 |
| Qwen2.5-7B | 98 | 0.8776 | 0.8352 | 0.8745 | 0.6996 | 12 |
| Qwen2.5-72B | 98 | 0.8776 | 0.8348 | 0.8735 | 0.6988 | 12 |
| Llama-3.3-70B | 98 | 0.8571 | 0.8077 | 0.8606 | 0.6884 | 14 |

Primary gold-set Macro-F1 is **macro_f1_target4**: unweighted mean F1 over the fixed
human target classes WHITE, YELLOW, REDTYPE, UNKNOWN (OTHER predictions still count
as errors for the true class). **macro_f1_all5** additionally averages OTHER with
`zero_division=0` and is reported as a transparent supplementary metric.
Accuracy and κ above match the locked evaluation values.

To 3 d.p.: baseline 0.763; Qwen-7B and Qwen-72B 0.878; Llama 0.857.
Under v1 the 72B model does not beat the 7B model.

---

## 6. Error taxonomy (Qwen-7B, categoriser v1)

Twelve disagreements with gold.

| Error class | Count |
|---|---:|
| CATEGORY_PRIORITY | 4 |
| JUNK_NON_SPECIES | 3 |
| MULTI_COLOUR | 2 |
| CONTAMINATION | 1 |
| FALSE_POSITIVE | 1 |
| FALSE_NEGATIVE | 1 |
| **Total** | **12** |

---

## 7. Categoriser v2 and RAG

Same free-text, new class mapping (v2). RAG is Qwen-7B with 3 TF-IDF exemplars,
leave-one-out. Predictions: `gold_pred_qwen7b_rag.csv`.
RAG `uncertain` outputs are scored as UNKNOWN, as in `15_RAG_Extract_Gold.py`.

| Model | Accuracy v1 | Accuracy v2 | Change |
|---|---:|---:|---:|
| Keyword baseline | 0.7629 | 0.7835 | +0.0206 |
| Qwen-7B | 0.8776 | **0.9286** | **+0.0510** |
| Qwen-72B | 0.8776 | 0.9184 | +0.0408 |
| Llama-70B | 0.8571 | 0.9184 | +0.0612 |

| Setup | n | Accuracy | `uncertain` |
|---|---:|---:|---:|
| Zero-shot + v1 | 98 | 0.8776 | 0 |
| Zero-shot + v2 | 98 | 0.9286 | 0 |
| RAG + v1 | 98 | 0.8980 | 5 |
| RAG + v2 | 98 | **0.9490** | 5 |

Best gold-set accuracy is **0.949** (RAG + categoriser v2), with 5 abstentions
out of 100 rows. RAG was run on the gold set only.

---

## 8. Gold-set robustness (junk rows excluded)

Excluding the 9 rows flagged `JUNK_NON_SPECIES` leaves n = 89.

| System | n = 98 v1 | n = 98 v2 | n = 89 v1 | n = 89 v2 |
|---|---:|---:|---:|---:|
| Keyword baseline | 0.7629 | 0.7835 | 0.7727 | 0.7955 |
| Qwen-7B | 0.8776 | 0.9286 | 0.8989 | 0.9326 |
| Qwen-72B | 0.8776 | 0.9184 | 0.8989 | 0.9326 |
| Llama-70B | 0.8571 | 0.9184 | 0.8989 | 0.9438 |
| Qwen-7B RAG | 0.8980 | 0.9490 | 0.8989 | 0.9438 |

On species-only rows under v2, RAG scores 84 / 89 = 0.9438 and zero-shot
Qwen-7B scores 83 / 89 = 0.9326.
Under v1, all three LLMs score 0.8989 once junk is removed.

Of RAG's 5 abstentions, 4 are genuine species rows and 1 is a junk row. All 4
genuine abstentions have gold = UNKNOWN. Zero-shot and RAG differ on 4 of the
89 rows (2 RAG fixes, 1 RAG break), so McNemar is uninformative.
RAG remains the best gold-set setup under V2 (0.9490 on n=98) and abstains on
rows that carry no colour information.

---

## 9. Label-source sensitivity

Equal three-LLM common cohort (`llm_common`): Qwen-7B ∩ Qwen-72B ∩ Llama-70B
known colour under V2; **n = 1,149**. No baseline / four-source cohort in the
primary label-sensitivity MCMC.

MCMC: **27 / 27** chain files present (3 variants × 3 colours × 3 chains).
Maximum MPSRF < 1.01 (all ≈ 1.000).
WHITE ~ PC2 (+) and YELLOW ~ PC2 (-) are significant for all three LLM sources.

### Analysis n by label source

| Variant | n |
|---|---:|
| Qwen-7B | 1,149 |
| Qwen-72B | 1,149 |
| Llama-70B | 1,149 |

Species set and environmental PC rows are identical across the three variants;
only the colour labels differ.

### PC2 coefficients

From `Processed Data/experiments/label_sensitivity/results/label_sensitivity_effects.csv`
(4 d.p.; use the CSV for full precision).

| Variant | WHITE ~ PC2 mean | pMCMC | YELLOW ~ PC2 mean | pMCMC |
|---|---:|---:|---:|---:|
| Qwen-7B | +0.0693 | 0.0039 | -0.0692 | 0.0046 |
| Qwen-72B | +0.0688 | 0.0037 | -0.0666 | 0.0063 |
| Llama-70B | +0.0709 | 0.0023 | -0.0655 | 0.0083 |

### Other effects that reach raw pMCMC < 0.05

Thirty colour × PC effects per variant (90 tests). Nine combinations are
significant under at least one label source; six of those are WHITE/YELLOW × PC2.
YELLOW ~ PC4 is also raw-significant under all three sources (p ≈ 0.028–0.047)
but is not a predefined robust claim. REDTYPE ~ PC3 is not significant under any
source (p ≈ 0.81–0.88).

Label source does not flip either PC2 association. The equal-cohort grid is
3 colours × 10 PCs × 3 sources = 90 tests (~4.5 expected hits at pMCMC < 0.05;
9 observed). Under BH over that full grid, no individual effect retains q < 0.05;
robustness of WHITE ~ PC2 and YELLOW ~ PC2 is therefore judged by the predefined
cross-source / reliability criterion, not by BH on the 90-test label grid alone.

---

## 10. Prediction (colour from environment)

Source: `Processed Data/experiments/prediction/prediction_cv_summary.csv`.
Run on the primary n = 1,438 set (417 genera; 613 / 494 / 331).
Figure: `Results/figures/methods/fig14_prediction.{png,pdf}`.
Five-fold CV. Genus-grouped CV is the headline split: a genus never spans a fold,
so the genus prior collapses to the majority class. Model selection and performance
estimation use the **same** grouped CV (not nested CV). Uncertainty intervals under
grouped CV use **genus-cluster bootstrap** (resampling whole genera); a species-level
bootstrap is retained only as a supplementary comparison.

| Model | Accuracy | Balanced acc. | macro_f1_3class [genus-cluster 95% CI] |
|---|---:|---:|---|
| Majority class | 0.4263 | 0.3333 | 0.1993 [0.185, 0.213] |
| Logistic regression | 0.4325 | 0.3595 | 0.3135 [0.284, 0.344] |
| Random forest (best environment model) | 0.4131 | 0.3628 | 0.3500 [0.325, 0.375] |
| Genus prior (grouped CV) | 0.4263 | 0.3333 | 0.1993 [0.185, 0.213] |
| Genus prior, ungrouped CV | 0.6161 | 0.6015 | 0.6077 [0.580, 0.633] (species bootstrap; leaky) |

Genus-cluster versus species-level bootstrap under grouped CV (same point estimates):
majority/genus-prior species [0.191, 0.208] → genus [0.185, 0.213];
logreg species [0.292, 0.335] → genus [0.284, 0.344];
random forest species [0.325, 0.375] → genus [0.325, 0.375] (essentially unchanged).

Environment is associated with colour but weakly predictive: balanced accuracy
0.363 against a 0.333 chance floor. The large ungrouped genus-prior lift is evidence of
random-split genus leakage / within-genus information leakage, rather than proof that
biological relatedness predicts colour outside that leakage. Held-out genus-grouped
permutation importance (random forest) yields several weak positive axes with fold-to-fold
uncertainty; PC3 is largest on mean drop (+0.011), with PC2 also positive (+0.008).
Environment does not strongly determine colour, and PC2 is not the sole predictive axis.

---

## 11. Full-treatment prediction files

| File | Rows |
|---|---:|
| `treatments_pred_baseline.csv` | 3,857 |
| `treatments_pred_qwen72b.csv` | 3,857 |
| `treatments_pred_llama70b.csv` | 3,857 |

Full-corpus Qwen-7B colours are in `flower_color_qwen_clean.csv` from the clean
pipeline.

---

## 12. Reliability chapter

Sources: `Processed Data/experiments/reliability/summary.json`,
`reliability_robustness_table.csv`, `reliability_mcmc_effects.csv`,
`reliability_convergence.csv` (also under `Results/tables/reliability/`).
Built by `scripts/24_Build_Reliability_Set.py` and `scripts/25_Reliability_Ecology.R`
at `nitt = 1,050,000`, 3 independent chains (seeds 42 / 123 / 456), inference on
the pooled 30,000 samples. Appendix figure: fig18.

These are categoriser-v2 labels on the three-model overlap. They are not the
published n = 1,438 pipeline table in §1.

The ecology label is Qwen-7B v2. Qwen-72B and Llama contribute only to coverage
and agreement. The keyword baseline is excluded from consensus. UNKNOWN and
OTHER are dropped and never coded as `is_white = 0`.

| Set | n |
|---|---:|
| Primary ecology | 1,438 |
| Three-LLM coverage (72B + Llama present) | 1,313 |
| Common known support (all 3 give WHITE/YELLOW/REDTYPE) | **1,149** |
| High confidence (all 3 agree on class) | **1,129** |
| Disagreement (descriptive only) | **20** |

Agreement rate on common-known support: 0.9826; on coverage where 7B is known:
0.9733. Validator flags (lexical diagnostic only): unsupported known colour **7**;
wrong-context **3**; high-confidence and supported **1,123**; malformed/key-stub **277**;
multi-colour phrase **561**. High confidence is defined by three-LLM exact agreement;
validator flags do not automatically exclude species from MCMC.
Colour counts — common: YELLOW 432 / WHITE 394 / REDTYPE 323;
high-confidence: 425 / 389 / 315.

### Robustness (both subsets, genus RE, threshold MCMCglmm)

Pooled posterior over 3 chains.

| Effect | Common-known (n = 1,149) | High-confidence (n = 1,129) |
|---|---|---|
| WHITE ~ PC2 | +0.069348, p = 0.0039, CI excludes 0 | +0.072894, p = 0.0021, CI excludes 0 |
| YELLOW ~ PC2 | −0.069222, p = 0.0046, CI excludes 0 | −0.070313, p = 0.0052, CI excludes 0 |
| REDTYPE ~ PC3 | -0.0061, p = 0.86 | -0.0134, p = 0.71 |
| WHITE ~ elevation | -0.0296, p = 0.65 | -0.0324, p = 0.62 |
| YELLOW ~ elevation | +0.0415, p = 0.57 | +0.0460, p = 0.54 |
| REDTYPE ~ elevation | +0.0029, p = 0.97 | +0.0055, p = 0.94 |

WHITE ~ PC2 (+) and YELLOW ~ PC2 (-) keep sign and exclude zero on both subsets.
REDTYPE ~ PC3 and the three elevation slopes keep direction but include zero.
That is robustness to disagreement among these three models, not to all
extraction error: shared OCR or prompt bias can still agree.

### Convergence

| Diagnostic | Value |
|---|---|
| Chains per model (seeds 42 / 123 / 456) | 3 |
| Pooled posterior samples per model | 30,000 |
| Worst Gelman-Rubin MPSRF (12 models) | **1.000453** |
| Worst per-parameter PSRF | 1.000284 |
| Lowest pooled effective sample size | **29,175.4** of 30,000 |
| Models with MPSRF < 1.01 | **12 / 12** |

All 12 models converged. Worst MPSRF 1.0004 against a 1.01 threshold; effective
sample sizes are within 2% of the nominal 30,000. Moving from one chain to three
shifted posterior means by at most 0.0006 and left every robustness designation
unchanged. Step 06 and the label-source models report the same class of
diagnostic (worst MPSRF 1.00053).

No second-annotator or human inter-annotator study was performed. Reliability
is model agreement plus lexical source grounding (not human validation). The
n = 98 gold set is exploratory / development-set evidence for V2 (error patterns
observed there informed V2), not independent external validation.

