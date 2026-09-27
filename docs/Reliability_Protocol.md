# Reliability protocol (chapter add-on)

Question: which open-LLM flower-colour labels are reliable enough for downstream
inference?

- Primary ecology table remains n=1,438 with Qwen-7B pipeline labels (V1).
- Three-LLM coverage is smaller: 72B and Llama were run on the 3,857 parsed
  treatments, not the fascicle/recovery increment (~125 ecology species).
- Common known-label support: all three LLMs give WHITE/YELLOW/REDTYPE.
  Ecology models on that set still use **Qwen-7B v2** as the predeclared label.
- **High confidence** = exact agreement among Qwen-7B, Qwen-72B and Llama-70B on
  a known WHITE/YELLOW/REDTYPE class. The source-text validator is a **separate
  lexical diagnostic**; validator flags do **not** determine high-confidence
  membership and do **not** automatically exclude species from MCMC.
- Disagreement subset is descriptive only.
- Keyword baseline is not part of consensus.
- UNKNOWN is dropped, never coded as is_white=0.
- Existing n=98 gold set is exploratory (v2 was developed there). No independent
  second-annotator study was performed; label quality is assessed through
  three-model agreement + lexical source grounding, not human inter-annotator
  agreement.
- Mixed models are **genus-adjusted, not phylogenetically corrected.**
- Reliability ecology is run at full chain length (`nitt=1,050,000`, matching
  `scripts/06_MCMCglmm.R`) via
  `sbatch scripts/slurm/run_25_reliability_ecology.slurm` (`RELIABILITY_FULL=1`).
- **3 independent chains** per model (seeds 42/123/456); inference uses the pooled
  30,000 samples and convergence is reported as Gelman-Rubin MPSRF in
  `reliability_convergence.csv`, plotted as **fig18_reliability_convergence**.
- Completed reliability chain RDS objects currently on disk are posterior Sol
  lists tied to contemporaneous table/summary hashes. Future full runs will
  embed a `list(Sol=, provenance=)` payload; existing objects were not rewritten
  merely to simulate embedded provenance.

Observed (v2 labels, three-LLM overlap; not the published n=1,438 pipeline table):

| Set | n |
|---|---:|
| Primary ecology | 1,438 |
| Three-LLM coverage | 1,313 |
| Common known support | 1,149 |
| High confidence (exact three-LLM agreement) | 1,129 |
| Disagreement | 20 |

Full-chain result (`nitt=1,050,000`, 3 chains pooled; values from
`Results/tables/reliability/reliability_mcmc_effects.csv`):

WHITE~PC2 and YELLOW~PC2 keep sign and exclude zero on both subsets (**robust**):
WHITE~PC2 **+0.069348** (common) / **+0.072894** (high-conf);
YELLOW~PC2 **−0.069222** / **−0.070313**.
REDTYPE~PC3 and all three elevation slopes keep direction but include zero on
both subsets (**not robust** under this restriction).

Convergence: all 12 models pass, worst MPSRF **1.000453** (threshold 1.01), lowest
pooled effective sample size **29,175.4** of 30,000. Going from one chain to three moved
the posterior means by at most 0.0006 and changed no designation.

Lexical validator summary (diagnostic only; from `summary.json` after vocabulary repair):
unsupported known-colour **7**; wrong-context **3**; high-confidence-and-supported **1,123**;
malformed/key-stub **277**; multi-colour phrase **561**.
