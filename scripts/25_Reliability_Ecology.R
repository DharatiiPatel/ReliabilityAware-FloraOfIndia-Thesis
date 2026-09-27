#!/usr/bin/env Rscript
# Confidence-stratified ecology: same models on common-known support vs
# high-confidence (three-LLM agreement). Primary colour = Qwen-7B v2.
#
# UNKNOWN/OTHER rows are not in these CSVs (never coded as is_white=0).
#
# Three independent chains per model; inference uses the pooled posterior and
# Gelman-Rubin MPSRF (reliability_convergence.csv), matching scripts/06 and 19/20.
#
# Publishable execution requires RELIABILITY_FULL=1 (nitt=1.05e6, burnin=5e4,
# thin=100). MCMC_SMOKE=1 allows a non-publishable I/O path test only.
# Genus random intercept only: genus-adjusted, not phylogenetically corrected.

args_all <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", args_all[grepl("^--file=", args_all)])
.thesis_env <- Sys.getenv("THESIS_BASE", unset = "")
if (nzchar(.thesis_env)) {
  root <- normalizePath(path.expand(.thesis_env), mustWork = FALSE)
} else if (length(file_arg) != 1 || !nzchar(file_arg[[1]])) {
  root <- normalizePath(getwd(), mustWork = FALSE)
} else {
  root <- dirname(dirname(normalizePath(file_arg[[1]], mustWork = FALSE)))
}

.libPaths(c(file.path(Sys.getenv("HOME"), "R/library"),
            file.path(root, "R_library"), .libPaths()))
options(stringsAsFactors = FALSE)
options(bitmapType = "cairo")

suppressPackageStartupMessages({
  library(MCMCglmm)
  library(coda)
  library(dplyr)
})

fail <- function(...) {
  cat("ERROR: ", sprintf(...), "\n", sep = "")
  quit(status = 1)
}

sha256_file <- function(path) {
  dig <- tryCatch(
    system2("sha256sum", args = shQuote(path), stdout = TRUE, stderr = TRUE),
    error = function(e) character(0)
  )
  if (!length(dig) || !nzchar(dig[[1]])) fail("failed to hash %s", path)
  sub(" .*", "", dig[[1]])
}

out_dir <- file.path(root, "Processed Data/experiments/reliability")
res_dir <- file.path(root, "Results/tables/reliability")
fig_dir <- file.path(out_dir, "figures")
# Existing dirs only — do not invent new permanent trees
if (!dir.exists(out_dir)) fail("missing reliability dir: %s", out_dir)
if (!dir.exists(res_dir)) fail("missing results dir: %s", res_dir)
if (!dir.exists(fig_dir)) dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)

full  <- identical(Sys.getenv("RELIABILITY_FULL", ""), "1")
smoke <- identical(Sys.getenv("MCMC_SMOKE", ""), "1")
if (!full && !smoke) {
  fail("RELIABILITY_FULL=1 required for publishable execution (or MCMC_SMOKE=1 for non-publishable I/O test)")
}

if (full) {
  NITT <- 1050000L; BURNIN <- 50000L; THIN <- 100L
} else {
  NITT <- 55000L; BURNIN <- 5000L; THIN <- 50L
}
if (smoke && !full) {
  NITT <- 3000L; BURNIN <- 500L; THIN <- 5L
  message("*** MCMC_SMOKE=1: short chains; will NOT replace canonical tables ***")
}
PRIOR <- list(R = list(V = 1, fix = 1), G = list(G1 = list(V = 1, nu = 0.002)))
pc_cols <- paste0("PC", 1:10)
CHAIN_SEEDS <- c(42L, 123L, 456L)
MPSRF_MAX <- 1.01
CATEGORISER <- file.path(root, "scripts/lib/colour_categoriser.py")

common <- file.path(out_dir, "ecology_common_known.csv")
high   <- file.path(out_dir, "ecology_high_confidence.csv")
if (!file.exists(common) || !file.exists(high)) {
  fail("Run python scripts/24_Build_Reliability_Set.py first")
}
if (!file.exists(CATEGORISER)) fail("missing categoriser: %s", CATEGORISER)

common_sha <- sha256_file(common)
high_sha   <- sha256_file(high)
cat_sha    <- sha256_file(CATEGORISER)

message("Reliability ecology MCMC  nitt=", NITT, " burnin=", BURNIN, " thin=", THIN)
message("RELIABILITY_FULL=", full, "  smoke=", smoke, "  chains=", length(CHAIN_SEEDS))
message("common_known_sha256=", common_sha)
message("high_confidence_sha256=", high_sha)
message("categorizer_sha256=", cat_sha)

fit_chains <- function(data, formula_str, label) {
  lapply(seq_along(CHAIN_SEEDS), function(i) {
    message("    chain ", i, "/", length(CHAIN_SEEDS), " (seed ", CHAIN_SEEDS[i], ")")
    set.seed(CHAIN_SEEDS[i])
    MCMCglmm(
      fixed   = as.formula(formula_str),
      random  = ~ genus,
      data    = data,
      family  = "threshold",
      prior   = PRIOR,
      nitt    = NITT,
      burnin  = BURNIN,
      thin    = THIN,
      verbose = FALSE
    )
  })
}

fit_pc <- function(df, response, label) {
  message("  ", label, " ~ PC1+...+PC10  n=", nrow(df),
          " positives=", sum(df[[response]]))
  fit_chains(df, paste(response, "~", paste(pc_cols, collapse = " + ")), label)
}

fit_elev <- function(df, response, label) {
  d <- df[!is.na(df$alt) & df$alt >= 0, ]
  d$alt_scaled <- as.numeric(scale(d$alt))
  message("  ", label, " ~ alt_scaled  n=", nrow(d),
          " positives=", sum(d[[response]]))
  list(models = fit_chains(d, paste(response, "~ alt_scaled"), label), n = nrow(d))
}

extract_row <- function(models, subset_name, n, effect, color, response) {
  sols <- lapply(models, function(m) as.mcmc(as.matrix(m$Sol)))
  if (!effect %in% colnames(sols[[1]])) return(NULL)

  gr <- tryCatch(gelman.diag(as.mcmc.list(sols), multivariate = TRUE,
                             autoburnin = FALSE),
                 error = function(e) NULL)
  mpsrf    <- if (is.null(gr)) NA_real_ else as.numeric(gr$mpsrf)
  max_psrf <- if (is.null(gr)) NA_real_ else max(gr$psrf[, 1], na.rm = TRUE)

  x <- unlist(lapply(sols, function(s) s[, effect]), use.names = FALSE)
  hpd <- HPDinterval(as.mcmc(x), prob = 0.95)
  ess <- sum(vapply(sols, function(s) effectiveSize(s[, effect]), numeric(1)))
  pmcmc <- 2 * max(0.5 / length(x),
                   min(sum(x > 0) / length(x), sum(x < 0) / length(x)))

  data.frame(
    subset = subset_name,
    n = n,
    color = color,
    response = response,
    effect = effect,
    mean = mean(x),
    lower = unname(hpd[1, 1]),
    upper = unname(hpd[1, 2]),
    interval = "HPD95",
    pMCMC = pmcmc,
    excludes_zero = as.integer(hpd[1, 1] > 0 | hpd[1, 2] < 0),
    direction = ifelse(mean(x) > 0, "+", "-"),
    nitt = NITT,
    burnin = BURNIN,
    thin = THIN,
    n_chains = length(models),
    n_samples_pooled = length(x),
    eff_samp = ess,
    mpsrf = mpsrf,
    max_psrf = max_psrf,
    converged = as.integer(!is.na(mpsrf) & mpsrf < MPSRF_MAX &
                             !is.na(max_psrf) & max_psrf < MPSRF_MAX),
    common_known_sha256 = common_sha,
    high_confidence_sha256 = high_sha,
    categorizer_sha256 = cat_sha,
    stringsAsFactors = FALSE
  )
}

save_trace <- function(models, effect, tag) {
  tryCatch({
    png(file.path(fig_dir, paste0("trace_", tag, ".png")),
        width = 900, height = 420)
    on.exit(dev.off(), add = TRUE)
    mat <- vapply(models, function(m) as.matrix(m$Sol)[, effect],
                  numeric(nrow(models[[1]]$Sol)))
    matplot(mat, type = "l", lty = 1, col = c("#1B6C6F", "#B4642A", "#5A6FA8"),
            xlab = "stored iteration", ylab = effect,
            main = paste0(tag, "  (", ncol(mat), " chains)"))
    abline(h = mean(mat), lty = 2, col = "grey40")
  }, error = function(e) {
    message("    (trace plot skipped: ", conditionMessage(e), ")")
  })
}

# Stage directory for future full runs: models/chains/tables land here until the
# complete convergence gate passes. Canonical out_dir is untouched on failure.
# Completed historical reliability chains remain plain Sol lists tied to
# contemporaneous table/summary hashes; future runs embed provenance payloads.
stage_dir <- NULL
if (full && !smoke) {
  stage_dir <- tempfile("reliability_mcmc_stage_")
  dir.create(stage_dir)
  on.exit(unlink(stage_dir, recursive = TRUE), add = TRUE)
}

make_chain_payload <- function(models, subset_name, color, response, effect,
                               input_path, n, positive_n) {
  script_path <- if (length(file_arg) == 1) normalizePath(file_arg) else NA_character_
  script_sha <- if (!is.na(script_path) && file.exists(script_path)) {
    sha256_file(script_path)
  } else {
    "unavailable"
  }
  list(
    Sol = lapply(models, function(m) m$Sol),
    provenance = list(
      subset = subset_name,
      outcome = color,
      response = response,
      effect = effect,
      chain_seeds = CHAIN_SEEDS,
      n_chains = length(CHAIN_SEEDS),
      seed = CHAIN_SEEDS,
      input_path = input_path,
      dataset_sha256 = if (identical(subset_name, "common_known")) common_sha else high_sha,
      categorizer_sha256 = cat_sha,
      n = as.integer(n),
      positive_n = as.integer(positive_n),
      nitt = NITT,
      burnin = BURNIN,
      thin = THIN,
      created_utc = format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ"),
      analysis_script_sha256 = script_sha,
      note = paste(
        "Future reliability chain format: list(Sol=<list of chain Sol>,",
        "provenance=<named list>). Historical completed chains in this repo",
        "are stored as plain Sol lists only."
      )
    )
  )
}

run_subset <- function(path, subset_name) {
  df <- read.csv(path, encoding = "UTF-8")
  stopifnot(all(c("is_white", "is_yellow", "is_redtype", "genus") %in% names(df)))
  if (any(is.na(df$is_white))) stop("NA in is_white: UNKNOWN leaked into ecology file")
  rows <- list()
  specs <- list(
    list(col = "is_white",   lab = "WHITE",   effect = "PC2"),
    list(col = "is_yellow",  lab = "YELLOW",  effect = "PC2"),
    list(col = "is_redtype", lab = "REDTYPE", effect = "PC3")
  )
  for (sp in specs) {
    ms <- fit_pc(df, sp$col, sp$lab)
    rows[[length(rows) + 1]] <- extract_row(ms, subset_name, nrow(df), sp$effect, sp$lab, sp$col)
    tag <- sprintf("%s_%s_pc", subset_name, sp$lab)
    save_trace(ms, sp$effect, tag)
    if (!is.null(stage_dir)) {
      saveRDS(ms[[1]], file.path(stage_dir, sprintf("model_%s.rds", tag)))
      saveRDS(
        make_chain_payload(ms, subset_name, sp$lab, sp$col, sp$effect, path,
                           nrow(df), sum(df[[sp$col]])),
        file.path(stage_dir, sprintf("chains_%s.rds", tag))
      )
    }
  }
  for (sp in specs) {
    ev <- fit_elev(df, sp$col, sp$lab)
    rows[[length(rows) + 1]] <- extract_row(
      ev$models, subset_name, ev$n, "alt_scaled", sp$lab, sp$col
    )
    tag <- sprintf("%s_%s_elev", subset_name, sp$lab)
    save_trace(ev$models, "alt_scaled", tag)
    if (!is.null(stage_dir)) {
      saveRDS(ev$models[[1]], file.path(stage_dir, sprintf("model_%s.rds", tag)))
      d_elev <- df[!is.na(df$alt) & df$alt >= 0, ]
      saveRDS(
        make_chain_payload(ev$models, subset_name, sp$lab, sp$col, "alt_scaled",
                           path, ev$n, sum(d_elev[[sp$col]])),
        file.path(stage_dir, sprintf("chains_%s.rds", tag))
      )
    }
  }
  bind_rows(rows)
}

effects <- bind_rows(
  run_subset(common, "common_known"),
  run_subset(high, "high_confidence")
)

expected_models <- 12L  # 2 subsets × 3 colours × 2 model types
if (nrow(effects) != expected_models) {
  fail("expected %d model rows, got %d; canonical tables not replaced",
       expected_models, nrow(effects))
}
if (anyNA(effects$mpsrf) || anyNA(effects$max_psrf)) {
  fail("non-finite convergence diagnostics; canonical tables not replaced")
}
if (any(effects$n_chains != length(CHAIN_SEEDS))) {
  fail("chain count mismatch; canonical tables not replaced")
}
if (any(effects$converged == 0)) {
  cat("ERROR: convergence failure (MPSRF/max PSRF >= ", MPSRF_MAX,
      "); canonical tables not replaced.\n", sep = "")
  print(effects[, c("subset", "color", "effect", "mpsrf", "max_psrf", "converged")])
  quit(status = 1)
}

wide <- effects %>%
  mutate(key = paste(color, effect, sep = "~")) %>%
  select(key, subset, n, mean, lower, upper, pMCMC, excludes_zero, direction)

keys <- unique(wide$key)
robust_rows <- lapply(keys, function(k) {
  a <- wide %>% filter(key == k, subset == "common_known")
  b <- wide %>% filter(key == k, subset == "high_confidence")
  if (nrow(a) != 1 || nrow(b) != 1) return(NULL)
  same_dir <- a$direction == b$direction
  both_ex  <- a$excludes_zero == 1 & b$excludes_zero == 1
  designation <- if (same_dir && both_ex) {
    "robust"
  } else if (same_dir) {
    "same_direction_interval_changes"
  } else {
    "label-sensitive"
  }
  data.frame(
    effect = k,
    n_common_known = a$n,
    n_high_confidence = b$n,
    mean_common = a$mean, lower_common = a$lower, upper_common = a$upper,
    p_common = a$pMCMC, dir_common = a$direction, excl0_common = a$excludes_zero,
    mean_high = b$mean, lower_high = b$lower, upper_high = b$upper,
    p_high = b$pMCMC, dir_high = b$direction, excl0_high = b$excludes_zero,
    designation = designation,
    stringsAsFactors = FALSE
  )
})
robust <- bind_rows(robust_rows)

convergence <- effects %>%
  transmute(
    subset, color, effect, n,
    n_chains, nitt, burnin, thin, n_samples_pooled,
    eff_samp = round(eff_samp, 1),
    mpsrf = round(mpsrf, 6),
    max_psrf = round(max_psrf, 6),
    converged,
    common_known_sha256, high_confidence_sha256, categorizer_sha256
  )

completed_utc <- format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ")
mcmc_provenance <- list(
  common_known_sha256 = common_sha,
  high_confidence_sha256 = high_sha,
  categorizer_sha256 = cat_sha,
  nitt = NITT,
  burnin = BURNIN,
  thin = THIN,
  seeds = CHAIN_SEEDS,
  model_count = nrow(effects),
  chain_count = length(CHAIN_SEEDS),
  completion_status = "complete",
  convergence_status = "passed",
  mpsrf_max_threshold = MPSRF_MAX,
  max_mpsrf = max(effects$mpsrf),
  max_psrf = max(effects$max_psrf),
  reliability_full = as.integer(full),
  completed_utc = completed_utc
)

# Smoke / non-full: preserve existing canonical tables
if (!full || smoke) {
  message("Non-publishable run finished successfully; canonical tables preserved.")
  print(mcmc_provenance)
  quit(status = 0)
}

# Atomic publish: stage tables then destination-local temp+rename.
# Models/chains are published from stage_dir only after the full gate above.
tmpdir <- tempfile("reliability_publish_")
dir.create(tmpdir)
on.exit(unlink(tmpdir, recursive = TRUE), add = TRUE)

write.csv(effects, file.path(tmpdir, "reliability_mcmc_effects.csv"), row.names = FALSE)
write.csv(robust, file.path(tmpdir, "reliability_robustness_table.csv"), row.names = FALSE)
write.csv(convergence, file.path(tmpdir, "reliability_convergence.csv"), row.names = FALSE)

# Destination-local atomic publish (temp in dest dir → verify → rename).
atomic_publish <- function(src, dest) {
  dest_dir <- dirname(dest)
  if (!dir.exists(dest_dir)) {
    dir.create(dest_dir, recursive = TRUE, showWarnings = FALSE)
  }
  tmp <- tempfile(pattern = paste0(".", basename(dest), "."), tmpdir = dest_dir)
  tryCatch({
    if (!file.copy(src, tmp, overwrite = TRUE)) {
      fail("failed to stage publish copy for %s", dest)
    }
    si <- file.info(src)$size
    ti <- file.info(tmp)$size
    if (is.na(si) || is.na(ti) || si != ti || ti < 1) {
      fail("publish size/readability check failed for %s", dest)
    }
    if (!isTRUE(file.rename(tmp, dest))) {
      fail("failed to rename publish temp over %s", dest)
    }
  }, error = function(e) {
    if (file.exists(tmp)) unlink(tmp)
    stop(e)
  })
  if (file.exists(tmp)) unlink(tmp)
}

for (nm in c("reliability_mcmc_effects.csv",
             "reliability_robustness_table.csv",
             "reliability_convergence.csv")) {
  atomic_publish(file.path(tmpdir, nm), file.path(out_dir, nm))
  atomic_publish(file.path(tmpdir, nm), file.path(res_dir, nm))
}

# Publish staged model/chain RDS only after full gate
if (!is.null(stage_dir)) {
  staged <- list.files(stage_dir, pattern = "\\.(rds)$", full.names = TRUE)
  for (src in staged) {
    atomic_publish(src, file.path(out_dir, basename(src)))
  }
}

# Merge provenance into existing summary.json (no new directory)
summary_path <- file.path(out_dir, "summary.json")
summary <- list()
if (file.exists(summary_path)) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    fail("jsonlite required to update summary.json with MCMC provenance")
  }
  summary <- jsonlite::fromJSON(summary_path, simplifyVector = TRUE)
}
if (!requireNamespace("jsonlite", quietly = TRUE)) {
  fail("jsonlite required to write reliability MCMC provenance")
}
summary$mcmc_run <- mcmc_provenance
summary$chain_storage_note <- paste(
  "Completed reliability chains currently on disk are posterior Sol lists",
  "tied to contemporaneous table/summary hashes.",
  "Future RELIABILITY_FULL runs write list(Sol=, provenance=) payloads."
)
tmp_sum <- file.path(tmpdir, "summary.json")
jsonlite::write_json(summary, tmp_sum, auto_unbox = TRUE, pretty = TRUE)
atomic_publish(tmp_sum, summary_path)
atomic_publish(summary_path, file.path(res_dir, "reliability_summary.json"))

message("Wrote reliability MCMC tables (atomic publish)")
print(robust)
message("\nConvergence (Gelman-Rubin across ", length(CHAIN_SEEDS), " chains):")
print(convergence)
message("max MPSRF = ", round(max(convergence$mpsrf, na.rm = TRUE), 6),
        "   min pooled ESS = ", round(min(convergence$eff_samp, na.rm = TRUE), 1))
message("All models converged (MPSRF < ", MPSRF_MAX, " and max PSRF < ", MPSRF_MAX, ").")
