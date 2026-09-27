#!/usr/bin/env Rscript

# Portable repository/package root: THESIS_BASE, else --file location, else getwd().
.thesis_args <- commandArgs(trailingOnly = FALSE)
.thesis_file <- sub("^--file=", "", .thesis_args[grepl("^--file=", .thesis_args)])
.thesis_fallback <- if (length(.thesis_file) >= 1 && nzchar(.thesis_file[[1]])) {
  script_dir <- dirname(normalizePath(.thesis_file[[1]], mustWork = FALSE))
  if (identical(basename(script_dir), "lib")) {
    normalizePath(file.path(script_dir, "..", ".."), mustWork = FALSE)
  } else {
    normalizePath(file.path(script_dir, ".."), mustWork = FALSE)
  }
} else {
  normalizePath(getwd(), mustWork = FALSE)
}
.thesis_env <- Sys.getenv("THESIS_BASE", unset = "")
BASE <- if (nzchar(.thesis_env)) {
  normalizePath(path.expand(.thesis_env), mustWork = FALSE)
} else {
  .thesis_fallback
}
# Combine parallel MCMC chains into label-sensitivity tables.
# Hard-fails on missing/mismatched provenance or nonconvergence.
# Publishes atomically via tempfile; does not replace canonical tables on failure.

.libPaths(c("~/R/library", .libPaths()))
options(stringsAsFactors = FALSE)
suppressMessages({ library(coda) })

VARDIR <- Sys.getenv(
  "LABEL_SENSITIVITY_DIR",
  unset = file.path(BASE, "Processed Data/experiments/label_sensitivity")
)
MANIFEST <- file.path(VARDIR, "mcmc_manifest.csv")
CHAINDIR <- file.path(VARDIR, "mcmc_chains")
OUTDIR <- file.path(VARDIR, "results")

NITT_REQ   <- 1050000L
BURNIN_REQ <- 50000L
THIN_REQ   <- 100L
EXPECTED_TASKS <- 27L
MPSRF_MAX <- 1.01

fail <- function(...) {
  cat("ERROR: ", sprintf(...), "\n", sep = "")
  quit(status = 1)
}

load_sol <- function(path) {
  obj <- readRDS(path)
  if (is.list(obj) && !is.null(obj$Sol) && !is.null(obj$provenance)) {
    return(obj)
  }
  fail("chain lacks embedded provenance (refuse bare Sol): %s", path)
}

if (!file.exists(MANIFEST)) fail("missing manifest: %s", MANIFEST)
man <- read.csv(MANIFEST, stringsAsFactors = FALSE)

required_cols <- c(
  "task_id", "cohort", "variant", "color_label", "chain", "seed",
  "chain_stem", "dataset_path", "dataset_sha256", "categorizer_sha256",
  "n", "positive_n", "nitt", "burnin", "thin", "expected_output"
)
missing_cols <- setdiff(required_cols, names(man))
if (length(missing_cols)) {
  fail("manifest missing columns: %s", paste(missing_cols, collapse = ", "))
}

if (nrow(man) != EXPECTED_TASKS) {
  fail("manifest must have exactly %d tasks; got %d", EXPECTED_TASKS, nrow(man))
}
if (any(man$cohort != "llm_common")) fail("non-llm_common cohort in manifest")
if (any(man$variant == "baseline")) fail("baseline present in main manifest")
if (any(grepl("wp4_label_variants", man$dataset_path, fixed = TRUE))) {
  fail("prohibited legacy path in manifest: wp4_label_variants")
}
if (any(grepl("/secondary/", man$dataset_path, fixed = TRUE))) {
  fail("secondary path in main manifest")
}
if (length(unique(man$variant)) != 3L ||
    !all(sort(unique(man$variant)) == c("llama70b", "qwen72b", "qwen7b"))) {
  fail("manifest variants must be exactly qwen7b, qwen72b, llama70b")
}
if (any(man$nitt != NITT_REQ) || any(man$burnin != BURNIN_REQ) ||
    any(man$thin != THIN_REQ)) {
  fail("manifest MCMC settings must be nitt=1050000, burnin=50000, thin=100")
}

expected <- as.character(man$expected_output)
missing <- expected[!file.exists(expected)]
if (length(missing)) {
  cat("ERROR: missing ", length(missing), " / ", length(expected),
      " expected chain files:\n", sep = "")
  cat(paste0("  ", missing), sep = "\n")
  quit(status = 1)
}

# Validate each chain against its manifest row
for (i in seq_len(nrow(man))) {
  path <- expected[[i]]
  obj <- load_sol(path)
  p <- obj$provenance
  checks <- list(
    variant = identical(as.character(p$variant), as.character(man$variant[[i]])),
    color = identical(as.character(p$color_label), as.character(man$color_label[[i]])),
    chain = identical(as.integer(p$chain), as.integer(man$chain[[i]])),
    seed = identical(as.integer(p$seed), as.integer(man$seed[[i]])),
    dataset_sha = identical(as.character(p$dataset_sha256),
                            as.character(man$dataset_sha256[[i]])),
    cat_sha = identical(as.character(p$categorizer_sha256),
                        as.character(man$categorizer_sha256[[i]])),
    n = identical(as.integer(p$n), as.integer(man$n[[i]])),
    positive_n = identical(as.integer(p$positive_n), as.integer(man$positive_n[[i]])),
    nitt = identical(as.integer(p$nitt), NITT_REQ),
    burnin = identical(as.integer(p$burnin), BURNIN_REQ),
    thin = identical(as.integer(p$thin), THIN_REQ)
  )
  bad <- names(checks)[!unlist(checks)]
  if (length(bad)) {
    fail("provenance mismatch for %s: %s", path, paste(bad, collapse = ", "))
  }
}

message("All ", length(expected), " chains present with matching provenance.")

pmcmc <- function(x) {
  2 * min(mean(x > 0), mean(x < 0))
}

combos <- unique(man[, c("variant", "color_label")])
all_rows <- list()
converge_rows <- list()

for (i in seq_len(nrow(combos))) {
  variant <- combos$variant[i]
  color   <- combos$color_label[i]
  sub <- man[man$variant == variant & man$color_label == color, ]
  sub <- sub[order(sub$chain), ]
  if (nrow(sub) != 3L) {
    fail("expected 3 chains for %s/%s but found %d", variant, color, nrow(sub))
  }
  if (length(unique(sub$n)) != 1L || length(unique(sub$positive_n)) != 1L) {
    fail("n/positive_n inconsistent across chains for %s/%s", variant, color)
  }
  if (length(unique(sub$dataset_sha256)) != 1L ||
      length(unique(sub$categorizer_sha256)) != 1L) {
    fail("checksums inconsistent across chains for %s/%s", variant, color)
  }

  objs <- lapply(as.character(sub$expected_output), load_sol)
  sols <- lapply(objs, function(o) as.mcmc(as.matrix(o$Sol)))
  ml <- as.mcmc.list(sols)

  gr <- tryCatch(gelman.diag(ml, multivariate = TRUE, autoburnin = FALSE),
                 error = function(e) NULL)
  if (is.null(gr) || is.null(gr$mpsrf) || anyNA(gr$mpsrf) ||
      anyNA(gr$psrf[, 1])) {
    fail("non-finite convergence diagnostics for %s/%s", variant, color)
  }
  mpsrf <- as.numeric(gr$mpsrf)
  max_psrf <- max(gr$psrf[, 1], na.rm = TRUE)
  converged <- (mpsrf < MPSRF_MAX) && (max_psrf < MPSRF_MAX)

  ess_by_var <- sapply(colnames(sols[[1]]), function(v) {
    sum(vapply(sols, function(s) effectiveSize(s[, v]), numeric(1)))
  })

  converge_rows[[length(converge_rows) + 1]] <- data.frame(
    cohort = "llm_common",
    variant = variant,
    color = color,
    n = sub$n[[1]],
    positive_n = sub$positive_n[[1]],
    n_chains = 3L,
    nitt = NITT_REQ,
    burnin = BURNIN_REQ,
    thin = THIN_REQ,
    n_samples_pooled = sum(vapply(sols, nrow, integer(1))),
    mpsrf = mpsrf,
    max_psrf = max_psrf,
    min_ess = min(ess_by_var),
    converged = as.integer(converged),
    dataset_sha256 = sub$dataset_sha256[[1]],
    categorizer_sha256 = sub$categorizer_sha256[[1]],
    stringsAsFactors = FALSE
  )

  pooled <- do.call(rbind, lapply(objs, function(o) as.matrix(o$Sol)))
  for (v in colnames(pooled)) {
    x <- pooled[, v]
    hpd <- HPDinterval(as.mcmc(x), prob = 0.95)
    lo <- unname(hpd[1, 1])
    hi <- unname(hpd[1, 2])
    ess <- sum(vapply(sols, function(s) effectiveSize(s[, v]), numeric(1)))
    all_rows[[length(all_rows) + 1]] <- data.frame(
      cohort = "llm_common",
      variant = variant,
      color = color,
      variable = v,
      post_mean = mean(x),
      lower95 = lo,
      upper95 = hi,
      interval = "HPD95",
      pMCMC = pmcmc(x),
      significant = (lo > 0 | hi < 0),
      eff_samp = ess,
      n_chains = 3L,
      n_samples_pooled = length(x),
      n = sub$n[[1]],
      positive_n = sub$positive_n[[1]],
      dataset_sha256 = sub$dataset_sha256[[1]],
      categorizer_sha256 = sub$categorizer_sha256[[1]],
      stringsAsFactors = FALSE
    )
  }
}

fixed <- do.call(rbind, all_rows)
conv  <- do.call(rbind, converge_rows)

if (any(conv$converged == 0) || anyNA(conv$mpsrf) || anyNA(conv$max_psrf)) {
  cat("ERROR: convergence failure; canonical tables not replaced.\n")
  print(conv)
  quit(status = 1)
}

# Atomic publish into existing results location (create only if publishing)
tmpdir <- tempfile("label_sens_combine_")
dir.create(tmpdir)
on.exit(unlink(tmpdir, recursive = TRUE), add = TRUE)

fx_tmp <- file.path(tmpdir, "label_sensitivity_effects.csv")
cv_tmp <- file.path(tmpdir, "label_sensitivity_convergence.csv")
write.csv(fixed, fx_tmp, row.names = FALSE)
write.csv(conv, cv_tmp, row.names = FALSE)

if (!dir.exists(OUTDIR)) dir.create(OUTDIR, recursive = TRUE, showWarnings = FALSE)
fx_final <- file.path(OUTDIR, "label_sensitivity_effects.csv")
cv_final <- file.path(OUTDIR, "label_sensitivity_convergence.csv")

# Destination-local atomic publish (temp in dest dir → verify → rename).
# Do not treat a direct cross-filesystem file.copy(src, dest) as atomic.
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
atomic_publish(fx_tmp, fx_final)
atomic_publish(cv_tmp, cv_final)

message("All models converged (MPSRF/max PSRF < ", MPSRF_MAX, ").")
message("Saved: ", file.path(OUTDIR, "label_sensitivity_effects.csv"))
message("Saved: ", file.path(OUTDIR, "label_sensitivity_convergence.csv"))
message("Label sensitivity combine complete.")
