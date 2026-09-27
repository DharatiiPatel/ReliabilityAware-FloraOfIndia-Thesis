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
base_dir <- if (nzchar(.thesis_env)) {
  normalizePath(path.expand(.thesis_env), mustWork = FALSE)
} else {
  .thesis_fallback
}
.libPaths(c(file.path(base_dir, "R_library"), path.expand("~/R/library"), .libPaths()))
# Elevation-gradient analysis on the primary analysis set (n=1,438).
# Writes under Processed Data/experiments/expansion/step08_outputs/
# (internal path; treat as primary analysis output).
# Does not touch prior n=1,174 paths under step08_outputs_clean/.
#
# Three independently seeded chains (42, 123, 456) per colour; strict
# convergence gate (MPSRF/max PSRF < 1.01) before atomic publication.
#
# Set SKIP_ELEV_MCMC=1 to rebuild descriptive fig6 panels from existing
# elevation_mcmc_results.csv only (no MCMCglmm).

options(stringsAsFactors = FALSE)
options(bitmapType = "cairo")

for (pkg in c("MCMCglmm", "coda", "ggplot2", "patchwork", "dplyr", "tidyr", "scales",
              "jsonlite")) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop("Missing package: ", pkg)
}
suppressPackageStartupMessages({
  library(MCMCglmm)
  library(coda)
  library(ggplot2)
  library(patchwork)
  library(dplyr)
  library(tidyr)
  library(scales)
})

source(file.path(base_dir, "scripts/lib/figure_style.R"))

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

# ECOLOGY_SET=clean reruns the historical n=1,174 set for the §1b comparison
# table. It must NOT publish into Results/, which holds the primary n=1,438
# figures. Default (unset / "primary") is the published analysis.
eco_set <- Sys.getenv("ECOLOGY_SET", "primary")
publish_results <- !identical(eco_set, "clean")
message("ECOLOGY_SET = ", eco_set, "  (publish to Results: ", publish_results, ")")

if (identical(eco_set, "clean")) {
  clean_root <- file.path(base_dir, "Processed Data/experiments")
  input_pca  <- file.path(clean_root, "step05b_outputs_clean/species_color_environment_final_clean.csv")
  input_env  <- file.path(clean_root, "step05b_outputs_clean/species_environment_trimmed.csv")
  output_dir <- file.path(clean_root, "step08_outputs_clean")
  expected_n <- NA_integer_
} else {
  exp_root    <- file.path(base_dir, "Processed Data/experiments/expansion")
  input_pca   <- file.path(exp_root, "step05b_outputs/species_color_environment_final_expanded.csv")
  input_env   <- file.path(exp_root, "step05b_outputs/species_environment_trimmed.csv")
  output_dir  <- file.path(exp_root, "step08_outputs")
  expected_n  <- 1438L
  expected_pca_sha <- "9d1e0f03fe774a7fcb19815a91341b8b55bdc79d133a2a9359a3d32967938280"
}
fig_dir <- file.path(output_dir, "figures")

if (!dir.exists(output_dir)) dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
if (!dir.exists(fig_dir)) dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)

skip_mcmc <- identical(Sys.getenv("SKIP_ELEV_MCMC", ""), "1")

ELEV_BREAKS <- c(-Inf, 500, 1500, 3000, 4500, Inf)
ELEV_LABELS <- c(
  "Lowland\n(0-500 m)",
  "Submontane\n(500-1500 m)",
  "Montane\n(1500-3000 m)",
  "Subalpine\n(3000-4500 m)",
  "Alpine\n(>4500 m)"
)

assign_elev_band <- function(alt_m) {
  cut(alt_m, breaks = ELEV_BREAKS, labels = ELEV_LABELS, right = TRUE)
}

NITT   <- 1050000L
BURNIN <- 50000L
THIN   <- 100L
CHAIN_SEEDS <- c(42L, 123L, 456L)
MPSRF_MAX <- 1.01
PRIOR  <- list(R = list(V = 1, fix = 1), G = list(G1 = list(V = 1, nu = 0.002)))
PRIOR_DESC <- "R: V=1 fixed; G: V=1, nu=0.002"

COL_SIG    <- "#A3262A"
COL_NONSIG <- "#999999"

V1_SCRIPT <- file.path(base_dir, "scripts/03_04_Categorize_and_Prepare.py")

message("Loading elevation data (", eco_set, " set)...")
if (!file.exists(input_pca)) fail("missing PCA input: %s", input_pca)
if (!file.exists(input_env)) fail("missing env input: %s", input_env)

pca_sha <- sha256_file(input_pca)
env_sha <- sha256_file(input_env)
if (identical(eco_set, "primary") && !identical(pca_sha, expected_pca_sha)) {
  fail("primary PCA dataset SHA mismatch\n  got=%s\n  expected=%s", pca_sha, expected_pca_sha)
}

v1_sha <- if (file.exists(V1_SCRIPT)) sha256_file(V1_SCRIPT) else NA_character_

df <- read.csv(input_pca, encoding = "UTF-8")
env <- read.csv(input_env, encoding = "UTF-8") %>%
  select(query_name, alt)

df <- df %>%
  left_join(env, by = "query_name") %>%
  filter(!is.na(alt), alt >= 0) %>%
  mutate(
    genus      = sapply(strsplit(query_name, " "), function(x) x[1]),
    elev_band  = assign_elev_band(alt),
    alt_scaled = scale(alt)[, 1]
  )

if (!is.na(expected_n) && nrow(df) != expected_n) {
  fail("expected n=%d after elevation join; got %d", expected_n, nrow(df))
}

n_elev <- nrow(df)
n_subtitle <- sprintf("n = %s", format(n_elev, big.mark = ","))
message("Species with elevation: ", n_elev)
message("Elevation range (m): ", round(min(df$alt)), " – ", round(max(df$alt)))
message("pca_sha256=", pca_sha)
message("env_sha256=", env_sha)
message("v1_script_sha256=", if (is.na(v1_sha)) "unavailable" else v1_sha)

# Descriptive tables write to a staging area first when MCMC will publish atomically;
# for SKIP path, write directly as before.
write.csv(df, file.path(output_dir, "species_with_elevation.csv"), row.names = FALSE)

message("\nColour proportions by elevation band...")

band_summary <- df %>%
  group_by(elev_band) %>%
  summarise(
    n_species   = n(),
    n_white     = sum(is_white),
    n_yellow    = sum(is_yellow),
    n_redtype   = sum(is_redtype),
    pct_white   = 100 * mean(is_white),
    pct_yellow  = 100 * mean(is_yellow),
    pct_redtype = 100 * mean(is_redtype),
    median_alt  = median(alt),
    .groups = "drop"
  )

write.csv(band_summary, file.path(output_dir, "elevation_band_summary.csv"), row.names = FALSE)
print(band_summary)

colour_long <- df %>%
  mutate(colour_label = case_when(
    is_white  == 1 ~ "WHITE",
    is_yellow == 1 ~ "YELLOW",
    is_redtype == 1 ~ "REDTYPE",
    TRUE ~ NA_character_
  )) %>%
  filter(!is.na(colour_label))

chi_tab  <- table(colour_long$elev_band, colour_long$colour_label)
chi_test <- chisq.test(chi_tab)
message("\nChi-square test (colour × elevation band):")
message("  X² = ", round(chi_test$statistic, 3), ", df = ", chi_test$parameter,
        ", p = ", format.pval(chi_test$p.value, digits = 3))
writeLines(capture.output(print(chi_test)), file.path(output_dir, "elevation_chisq_test.txt"))

message("\nMCMCglmm models — colour ~ scaled elevation (3 chains)...")

colors_to_run <- list(
  list(col = "is_white",   label = "WHITE"),
  list(col = "is_yellow",  label = "YELLOW"),
  list(col = "is_redtype", label = "REDTYPE")
)

elev_csv     <- file.path(output_dir, "elevation_mcmc_results.csv")
elev_conv    <- file.path(output_dir, "elevation_convergence.csv")
elev_meta    <- file.path(output_dir, "elevation_run_metadata.json")
elev_effects <- NULL

pmcmc <- function(x) {
  2 * min(mean(x > 0), mean(x < 0))
}

fit_three_chains <- function(response_col, label) {
  positive_n <- as.integer(sum(df[[response_col]]))
  formula_str <- paste(response_col, "~ alt_scaled")
  models <- vector("list", length(CHAIN_SEEDS))
  for (i in seq_along(CHAIN_SEEDS)) {
    message("  ", label, " chain ", i, "/", length(CHAIN_SEEDS),
            " (seed ", CHAIN_SEEDS[i], ")")
    set.seed(CHAIN_SEEDS[i])
    models[[i]] <- MCMCglmm(
      fixed   = as.formula(formula_str),
      random  = ~ genus,
      data    = df,
      family  = "threshold",
      prior   = PRIOR,
      nitt    = NITT,
      burnin  = BURNIN,
      thin    = THIN,
      verbose = FALSE
    )
  }
  sols <- lapply(models, function(m) as.mcmc(as.matrix(m$Sol)))
  ml <- as.mcmc.list(sols)
  gr <- tryCatch(
    gelman.diag(ml, multivariate = TRUE, autoburnin = FALSE),
    error = function(e) NULL
  )
  if (is.null(gr) || is.null(gr$mpsrf) || anyNA(gr$mpsrf) || anyNA(gr$psrf[, 1])) {
    fail("non-finite convergence diagnostics for %s", label)
  }
  mpsrf <- as.numeric(gr$mpsrf)
  max_psrf <- max(gr$psrf[, 1], na.rm = TRUE)
  if (!(is.finite(mpsrf) && is.finite(max_psrf) &&
        mpsrf < MPSRF_MAX && max_psrf < MPSRF_MAX)) {
    fail("%s failed convergence gate: mpsrf=%.6f max_psrf=%.6f (require < %.2f)",
         label, mpsrf, max_psrf, MPSRF_MAX)
  }

  pooled <- do.call(rbind, lapply(models, function(m) as.matrix(m$Sol)))
  vars <- colnames(pooled)
  if (!all(c("(Intercept)", "alt_scaled") %in% vars)) {
    fail("%s missing expected coefficients", label)
  }

  effect_rows <- list()
  for (v in vars) {
    x <- pooled[, v]
    hpd <- HPDinterval(as.mcmc(x), prob = 0.95)
    ess_by_chain <- vapply(sols, function(s) effectiveSize(s[, v]), numeric(1))
    if (any(!is.finite(ess_by_chain)) || any(ess_by_chain <= 0)) {
      fail("%s non-finite/non-positive ESS for %s", label, v)
    }
    effect_rows[[length(effect_rows) + 1]] <- data.frame(
      color = label,
      variable = v,
      mean = mean(x),
      lower = unname(hpd[1, 1]),
      upper = unname(hpd[1, 2]),
      interval = "HPD95",
      pMCMC = pmcmc(x),
      excludes_zero = as.integer(hpd[1, 1] > 0 | hpd[1, 2] < 0),
      eff_samp = sum(ess_by_chain),
      min_chain_ess = min(ess_by_chain),
      n_chains = length(CHAIN_SEEDS),
      n_samples_pooled = length(x),
      n_samples_per_chain = nrow(sols[[1]]),
      n = n_elev,
      positive_n = positive_n,
      mpsrf = mpsrf,
      max_psrf = max_psrf,
      seeds = paste(CHAIN_SEEDS, collapse = ","),
      nitt = NITT,
      burnin = BURNIN,
      thin = THIN,
      pca_sha256 = pca_sha,
      env_sha256 = env_sha,
      label_source = "historical_primary_V1",
      v1_script_sha256 = if (is.na(v1_sha)) "unavailable" else v1_sha,
      stringsAsFactors = FALSE
    )
  }
  effects <- do.call(rbind, effect_rows)

  conv_row <- data.frame(
    color = label,
    n = n_elev,
    positive_n = positive_n,
    n_chains = length(CHAIN_SEEDS),
    nitt = NITT,
    burnin = BURNIN,
    thin = THIN,
    n_samples_per_chain = nrow(sols[[1]]),
    n_samples_pooled = sum(vapply(sols, nrow, integer(1))),
    mpsrf = mpsrf,
    max_psrf = max_psrf,
    min_ess = min(vapply(vars, function(v) {
      sum(vapply(sols, function(s) effectiveSize(s[, v]), numeric(1)))
    }, numeric(1))),
    converged = 1L,
    seeds = paste(CHAIN_SEEDS, collapse = ","),
    pca_sha256 = pca_sha,
    env_sha256 = env_sha,
    label_source = "historical_primary_V1",
    stringsAsFactors = FALSE
  )

  created_utc <- format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ")
  chain_payload <- list(
    Sol = lapply(models, function(m) m$Sol),
    provenance = list(
      analysis_name = "primary_elevation",
      eco_set = eco_set,
      color_label = label,
      response_col = response_col,
      chain_seeds = CHAIN_SEEDS,
      n_chains = length(CHAIN_SEEDS),
      input_pca_path = input_pca,
      input_env_path = input_env,
      pca_sha256 = pca_sha,
      env_sha256 = env_sha,
      label_source = "historical_primary_V1",
      v1_script_path = V1_SCRIPT,
      v1_script_sha256 = if (is.na(v1_sha)) "unavailable" else v1_sha,
      n = n_elev,
      positive_n = positive_n,
      model_formula = formula_str,
      random_formula = "~ genus",
      prior_description = PRIOR_DESC,
      nitt = NITT,
      burnin = BURNIN,
      thin = THIN,
      retained_samples_per_chain = nrow(sols[[1]]),
      R_version = paste(R.version$major, R.version$minor, sep = "."),
      MCMCglmm_version = as.character(packageVersion("MCMCglmm")),
      created_utc = created_utc,
      mpsrf = mpsrf,
      max_psrf = max_psrf
    )
  )

  list(
    effects = effects,
    conv = conv_row,
    chain1_model = models[[1]],
    chain_payload = chain_payload
  )
}

if (skip_mcmc) {
  if (!file.exists(elev_csv)) {
    fail("SKIP_ELEV_MCMC=1 but missing %s", elev_csv)
  }
  message("SKIP_ELEV_MCMC=1 — loading ", elev_csv)
  elev_effects <- read.csv(elev_csv, stringsAsFactors = FALSE)
} else {
  # Stage all MCMC artefacts; replace canonical only after ALL colours pass
  stage <- tempfile("elev_mcmc_stage_")
  dir.create(stage)
  on.exit(unlink(stage, recursive = TRUE), add = TRUE)

  all_effects <- list()
  all_conv <- list()
  staged_models <- list()
  staged_chains <- list()

  for (color_info in colors_to_run) {
    message("\n", strrep("-", 50))
    message("MCMCglmm: ", color_info$label, " ~ alt_scaled + genus (3 chains)")
    message(strrep("-", 50))
    res <- fit_three_chains(color_info$col, color_info$label)
    all_effects[[color_info$label]] <- res$effects
    all_conv[[color_info$label]] <- res$conv
    staged_models[[color_info$label]] <- res$chain1_model
    staged_chains[[color_info$label]] <- res$chain_payload
    saveRDS(res$chain1_model,
            file.path(stage, paste0("model_elev_", color_info$label, ".rds")))
    saveRDS(res$chain_payload,
            file.path(stage, paste0("chains_elev_", color_info$label, ".rds")))
  }

  elev_effects <- bind_rows(all_effects)
  elev_convergence <- bind_rows(all_conv)

  if (nrow(elev_convergence) != 3L || any(elev_convergence$converged != 1)) {
    fail("convergence gate incomplete; canonical outputs not replaced")
  }
  if (anyNA(elev_effects$mean) || anyNA(elev_effects$lower) || anyNA(elev_effects$upper)) {
    fail("missing coefficients; canonical outputs not replaced")
  }

  write.csv(elev_effects, file.path(stage, "elevation_mcmc_results.csv"),
            row.names = FALSE)
  write.csv(elev_convergence, file.path(stage, "elevation_convergence.csv"),
            row.names = FALSE)

  meta <- list(
    analysis_name = "primary_elevation",
    eco_set = eco_set,
    n = n_elev,
    colour_counts = as.list(table(df$color_group)),
    input_pca_path = input_pca,
    input_env_path = input_env,
    pca_sha256 = pca_sha,
    env_sha256 = env_sha,
    label_source = "historical_primary_V1",
    v1_script_sha256 = if (is.na(v1_sha)) "unavailable" else v1_sha,
    nitt = NITT,
    burnin = BURNIN,
    thin = THIN,
    seeds = CHAIN_SEEDS,
    n_chains_per_model = length(CHAIN_SEEDS),
    n_models = 3L,
    mpsrf_max_threshold = MPSRF_MAX,
    max_mpsrf = max(elev_convergence$mpsrf),
    max_psrf = max(elev_convergence$max_psrf),
    completion_status = "complete",
    convergence_status = "passed",
    interval = "HPD95",
    completed_utc = format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ")
  )
  jsonlite::write_json(meta, file.path(stage, "elevation_run_metadata.json"),
                       auto_unbox = TRUE, pretty = TRUE)

  # Destination-local atomic publish: write/copy into a temp file in the
  # destination directory, verify size, then rename over the destination.
  # Cross-filesystem file.copy(src, dest) is intentionally NOT called "atomic".
  atomic_publish <- function(src, dest) {
    dest_dir <- dirname(dest)
    if (!dir.exists(dest_dir)) {
      dir.create(dest_dir, recursive = TRUE, showWarnings = FALSE)
    }
    tmp <- tempfile(pattern = paste0(".", basename(dest), "."), tmpdir = dest_dir)
    ok_copy <- FALSE
    tryCatch({
      if (!file.copy(src, tmp, overwrite = TRUE)) {
        fail("failed to stage publish copy for %s", dest)
      }
      ok_copy <- TRUE
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

  # Publish models/chains/tables only after full gate pass
  for (lab in c("WHITE", "YELLOW", "REDTYPE")) {
    atomic_publish(file.path(stage, paste0("model_elev_", lab, ".rds")),
                   file.path(output_dir, paste0("model_elev_", lab, ".rds")))
    atomic_publish(file.path(stage, paste0("chains_elev_", lab, ".rds")),
                   file.path(output_dir, paste0("chains_elev_", lab, ".rds")))
  }
  atomic_publish(file.path(stage, "elevation_mcmc_results.csv"), elev_csv)
  atomic_publish(file.path(stage, "elevation_convergence.csv"), elev_conv)
  atomic_publish(file.path(stage, "elevation_run_metadata.json"), elev_meta)

  message("All elevation models passed convergence gate; canonical tables replaced.")
  print(elev_convergence)
}

message("\nPC2 by elevation band...")

pc2_by_band <- df %>%
  group_by(elev_band) %>%
  summarise(
    n        = n(),
    mean_PC2 = mean(PC2, na.rm = TRUE),
    sd_PC2   = sd(PC2, na.rm = TRUE),
    mean_alt = mean(alt),
    .groups = "drop"
  )

write.csv(pc2_by_band, file.path(output_dir, "pc2_by_elevation_band.csv"), row.names = FALSE)

message("\nGenerating elevation figures...")

save_fig <- function(out_path, plot, w, h) {
  ggsave(out_path, plot, width = w, height = h, dpi = 300, bg = "white")
  message("  Saved: ", basename(out_path))
}

prop_df <- band_summary %>%
  select(elev_band, pct_white, pct_yellow, pct_redtype) %>%
  pivot_longer(-elev_band, names_to = "colour", values_to = "pct") %>%
  mutate(colour = recode(colour,
    pct_white = "WHITE", pct_yellow = "YELLOW", pct_redtype = "REDTYPE"
  ))

p_prop <- plot_elev_proportions(prop_df, band_summary)
save_fig(file.path(fig_dir, "fig6_elevation_colour_proportions.png"), p_prop, 8.6, 4.8)

count_df <- band_summary %>%
  select(elev_band, n_white, n_yellow, n_redtype) %>%
  pivot_longer(-elev_band, names_to = "colour", values_to = "n") %>%
  mutate(colour = recode(colour,
    n_white = "WHITE", n_yellow = "YELLOW", n_redtype = "REDTYPE"
  ))

p_count <- plot_elev_counts(count_df, band_summary)
save_fig(file.path(fig_dir, "fig6_elevation_species_counts.png"), p_count, 9.2, 4.8)

p_density <- ggplot(df, aes(x = alt, fill = color_group)) +
  geom_density(alpha = 0.45, colour = NA) +
  scale_fill_manual(values = PUB_CLASS_COLORS, name = NULL) +
  scale_x_continuous(labels = comma) +
  labs(
    title = "Elevation by flower colour",
    subtitle = n_subtitle,
    x = "Elevation (m)", y = "Density"
  ) +
  theme_pub()

save_fig(file.path(fig_dir, "fig6_elevation_density.png"), p_density, 10, 5)

if (!is.null(elev_effects) && nrow(elev_effects) > 0) {
  nm <- names(elev_effects)
  if ("post.mean" %in% nm) names(elev_effects)[nm == "post.mean"] <- "mean"
  if ("l.95..CI" %in% names(elev_effects)) names(elev_effects)[names(elev_effects) == "l.95..CI"] <- "lower"
  if ("u.95..CI" %in% names(elev_effects)) names(elev_effects)[names(elev_effects) == "u.95..CI"] <- "upper"
  if ("l-95% CI" %in% names(elev_effects)) names(elev_effects)[names(elev_effects) == "l-95% CI"] <- "lower"
  if ("u-95% CI" %in% names(elev_effects)) names(elev_effects)[names(elev_effects) == "u-95% CI"] <- "upper"
  if (!"excludes_zero" %in% names(elev_effects)) {
    elev_effects$excludes_zero <- as.integer(elev_effects$lower > 0 | elev_effects$upper < 0)
  }

  eff_plot <- elev_effects %>%
    filter(variable != "(Intercept)") %>%
    mutate(
      significant = as.logical(excludes_zero),
      color = factor(color, levels = c("WHITE", "YELLOW", "REDTYPE"))
    )

  p_mcmc <- ggplot(eff_plot, aes(x = mean, y = color, colour = significant)) +
    geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50") +
    geom_errorbar(aes(xmin = lower, xmax = upper), width = 0.15, linewidth = 0.8) +
    geom_point(size = 3.5, shape = 21, aes(fill = significant)) +
    scale_colour_manual(values = c("TRUE" = COL_SIG, "FALSE" = COL_NONSIG), guide = "none") +
    scale_fill_manual(values = c("TRUE" = COL_SIG, "FALSE" = "white"), guide = "none") +
    labs(
      title = "Elevation effect on flower colour",
      subtitle = paste0(n_subtitle, "  (3-chain HPD95)"),
      x = "Coefficient (scaled elevation)", y = NULL
    ) +
    theme_pub_forest()

  save_fig(file.path(fig_dir, "fig6_elevation_mcmc_coefficients.png"), p_mcmc, 8, 4)
} else {
  message("  fig6_elevation_mcmc_coefficients skipped (no elevation MCMC results yet).")
}

p_pc2 <- ggplot(df, aes(x = elev_band, y = PC2, fill = elev_band)) +
  geom_boxplot(outlier.size = 0.8, alpha = 0.85, show.legend = FALSE,
               colour = PUB_INK, linewidth = 0.35) +
  geom_hline(yintercept = 0, linetype = "dashed", colour = "grey50") +
  scale_fill_manual(values = PUB_STAGE_RAMP(nlevels(df$elev_band))) +
  labs(
    title = "Environmental PC2 across elevation bands",
    subtitle = n_subtitle,
    x = NULL, y = "PC2 score"
  ) +
  theme_pub() +
  theme(axis.text.x = element_text(size = 9), legend.position = "none")

save_fig(file.path(fig_dir, "fig6_elevation_pc2_boxplot.png"), p_pc2, 10, 5)

summary_lines <- c(
  paste0("Elevation Gradient Analysis — ", eco_set, " set summary"),
  strrep("=", 50),
  paste("Date:", Sys.time()),
  paste("ECOLOGY_SET:", eco_set),
  paste("Input PCA:", input_pca),
  paste("Input env:", input_env),
  paste("pca_sha256:", pca_sha),
  paste("env_sha256:", env_sha),
  paste("label_source: historical_primary_V1"),
  paste("v1_script_sha256:", if (is.na(v1_sha)) "unavailable" else v1_sha),
  paste("Species analysed:", nrow(df)),
  paste("Elevation range (m):", round(min(df$alt)), "-", round(max(df$alt))),
  paste("SKIP_ELEV_MCMC:", skip_mcmc),
  paste("Chains per colour:", if (skip_mcmc) "cached" else length(CHAIN_SEEDS)),
  paste("Seeds:", paste(CHAIN_SEEDS, collapse = ",")),
  paste("nitt/burnin/thin:", NITT, BURNIN, THIN),
  "",
  "Chi-square (colour x band):",
  capture.output(print(chi_test)),
  "",
  paste("Outputs under:", output_dir)
)
writeLines(summary_lines, file.path(output_dir, "elevation_analysis_summary.txt"))

if (publish_results) {
  res_elev <- file.path(base_dir, "Results/figures/ecology")
  dir.create(res_elev, recursive = TRUE, showWarnings = FALSE)
  for (f in list.files(fig_dir, pattern = "\\.png$")) {
    dst <- file.path(res_elev, f)
    if (file.exists(dst) || !is.na(Sys.readlink(dst))) try(unlink(dst), silent = TRUE)
    file.copy(file.path(fig_dir, f), dst, overwrite = TRUE)
  }
  for (t in c("elevation_band_summary.csv", "elevation_mcmc_results.csv",
              "elevation_convergence.csv", "elevation_run_metadata.json",
              "pc2_by_elevation_band.csv", "elevation_analysis_summary.txt")) {
    src <- file.path(output_dir, t)
    if (!file.exists(src)) next
    dst <- file.path(base_dir, "Results/tables/elevation", t)
    dir.create(dirname(dst), recursive = TRUE, showWarnings = FALSE)
    if (file.exists(dst) || !is.na(Sys.readlink(dst))) try(unlink(dst), silent = TRUE)
    file.copy(src, dst, overwrite = TRUE)
  }
} else {
  message("Skipping Results/ publication (ECOLOGY_SET=clean).")
}

message("\nPrimary elevation Step 08 complete")
message("Results: ", output_dir)
message("Figures: ", fig_dir)
