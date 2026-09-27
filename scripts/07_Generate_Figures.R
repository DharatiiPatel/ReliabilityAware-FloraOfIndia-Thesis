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
# Full ecology figure set for the primary analysis set (n=1,438).
# Writes under Processed Data/experiments/expansion/figures/ (internal path;
# that directory is the primary analysis output) and copies files into
# Results/figures/.

options(stringsAsFactors = FALSE)
options(bitmapType = "cairo")

for (pkg in c("ggplot2", "patchwork", "dplyr", "tidyr", "scales")) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop("Missing package: ", pkg)
  }
}
library(ggplot2)
library(patchwork)
library(dplyr)
library(tidyr)
library(scales)

source(file.path(base_dir, "scripts/lib/figure_style.R"))

exp_root     <- file.path(base_dir, "Processed Data/experiments/expansion")
primary_exp  <- file.path(base_dir, "Processed Data/experiments")
step05_dir   <- file.path(exp_root, "step05b_outputs")
env_final_f  <- file.path(step05_dir, "species_color_environment_final_expanded.csv")
step06_dir   <- file.path(exp_root, "step06_outputs")
step06_tables <- file.path(step06_dir, "tables")
step06_models <- file.path(step06_dir, "models")
step06_fig   <- file.path(step06_dir, "figures")
fig_dir      <- file.path(exp_root, "figures")
step08_dir   <- file.path(exp_root, "step08_outputs")

s06_combined <- file.path(step06_tables, "combined/all_fixed_effects_combined.csv")
s06_sv       <- file.path(step06_tables, "combined/single_variable_models.csv")

dir.create(fig_dir,    recursive = TRUE, showWarnings = FALSE)
dir.create(step06_fig, recursive = TRUE, showWarnings = FALSE)

COL_POS_BAR <- "#B35D45"
COL_NEG_BAR <- "#78B0C5"
COL_SIG     <- "#A3262A"
COL_NONSIG  <- "#999999"

var_label <- function(v) {
  if (v == "alt") return("Others")
  if (v %in% c("bdod", "cec", "nitrogen", "phh2o", "soc", "ocd", "ocs",
               "clay", "silt", "sand", "cfvo")) return("Soil environment")
  if (grepl("^bio", v, ignore.case = TRUE)) {
    num <- suppressWarnings(as.integer(sub("bio", "", v, ignore.case = TRUE)))
    if (num %in% c(2, 3, 4, 5))  return("Temperature variability")
    if (num == 15)                 return("Precipitation variability")
    if (num %in% 1:11)             return("Temperature level")
    if (num %in% 12:19)            return("Precipitation level")
  }
  "Others"
}

var_colors <- c(
  "Temperature level" = "#A3262A",
  "Temperature variability" = "#B8860B",
  "Precipitation level" = "#1F4E79",
  "Precipitation variability" = "#5B9BD5",
  "Soil environment" = "#E07A5F",
  "Others" = "#666666"
)

message("Loading primary analysis data (n=1,438 set)...")

df_analysis <- read.csv(env_final_f, check.names = FALSE)
n_analysis  <- nrow(df_analysis)
n_subtitle  <- sprintf("n = %s", format(n_analysis, big.mark = ","))
message("Analysis N = ", n_analysis)

effects <- read.csv(s06_combined, check.names = FALSE)
# Normalise column names (MCMCglmm CSV may use "l-95% CI" or R-mangled forms)
nm <- names(effects)
rename_map <- c(
  "post.mean" = "mean", "Estimate" = "mean",
  "l-95% CI" = "lower", "l.95..CI" = "lower", "X2.5." = "lower",
  "u-95% CI" = "upper", "u.95..CI" = "upper", "X97.5." = "upper",
  "eff.samp" = "eff_samp", "eff_samp" = "eff_samp"
)
for (old in names(rename_map)) {
  if (old %in% nm) names(effects)[names(effects) == old] <- rename_map[[old]]
}
stopifnot(all(c("mean", "lower", "upper", "variable", "color") %in% names(effects)))

loadings <- read.csv(file.path(step05_dir, "pca_loadings.csv"), check.names = FALSE)

gr_dir <- file.path(step06_tables, "convergence")
gr_all <- bind_rows(
  read.csv(file.path(gr_dir, "gelman_rubin_WHITE.csv"))   %>% mutate(color = "WHITE"),
  read.csv(file.path(gr_dir, "gelman_rubin_YELLOW.csv"))  %>% mutate(color = "YELLOW"),
  read.csv(file.path(gr_dir, "gelman_rubin_REDTYPE.csv")) %>% mutate(color = "REDTYPE")
)

has_sv <- file.exists(s06_sv)
if (has_sv) {
  sv_effects <- read.csv(s06_sv, check.names = FALSE)
  if ("post.mean" %in% names(sv_effects)) {
    sv_effects <- sv_effects %>%
      rename(mean = `post.mean`, lower = `l-95% CI`, upper = `u-95% CI`)
  }
}

save_fig <- function(path, plot, w, h, dpi = 300) {
  ggsave(path, plot, width = w, height = h, dpi = dpi, bg = "white")
  message("  Saved: ", basename(path))
}

make_forest_plot <- function(eff_df, pc_levels, title, subtitle = NULL) {
  sub <- eff_df %>%
    filter(variable %in% pc_levels, variable != "(Intercept)") %>%
    mutate(
      variable    = factor(variable, levels = rev(pc_levels)),
      significant = lower > 0 | upper < 0,
      color       = factor(color, levels = c("WHITE", "YELLOW", "REDTYPE"))
    )

  ggplot(sub, aes(x = mean, y = variable, colour = significant)) +
    geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50", linewidth = 0.6) +
    geom_errorbar(aes(xmin = lower, xmax = upper), width = 0.15, linewidth = 0.7) +
    geom_point(size = 2.8, shape = 21, aes(fill = significant)) +
    scale_colour_manual(values = c("TRUE" = COL_SIG, "FALSE" = COL_NONSIG), guide = "none") +
    scale_fill_manual(values = c("TRUE" = COL_SIG, "FALSE" = "white"), guide = "none") +
    facet_grid(~ color) +
    labs(title = title, subtitle = subtitle,
         x = "Posterior mean (95% CI)", y = NULL) +
    theme_pub_forest()
}

# ── Figure 1: colour counts (analysis-set composition) ───────────────────────
message("Figure 1: Colour counts...")

color_counts <- df_analysis %>%
  filter(!color_category %in% c("UNKNOWN", "OTHER", "GREENISH")) %>%
  count(color_category, name = "n")

p1 <- plot_colour_counts(color_counts)
save_fig(file.path(fig_dir, "fig1_colour_counts.png"), p1, 8.0, 4.4)

# ── Figure 3: PCA loadings ───────────────────────────────────────────────────
message("Figure 3: PCA loadings...")

loading_long <- bind_rows(lapply(paste0("PC", 1:5), function(pc) {
  ord <- order(abs(loadings[[pc]]), decreasing = TRUE)[1:10]
  loadings[ord, ] %>%
    select(variable, loading = all_of(pc)) %>%
    mutate(pc = pc, var_type = vapply(variable, var_label, character(1)))
})) %>%
  mutate(
    pc = factor(pc, levels = paste0("PC", 1:5)),
    variable = factor(variable, levels = unique(variable))
  )

loading_long <- loading_long %>%
  group_by(pc) %>%
  arrange(loading) %>%
  mutate(
    variable = factor(variable, levels = unique(variable)),
    var_type = factor(var_type, levels = names(var_colors))
  ) %>%
  ungroup()

p3 <- ggplot(loading_long, aes(x = loading, y = variable, fill = loading > 0)) +
  geom_col(width = 0.7) +
  geom_vline(xintercept = 0, linewidth = 0.5, colour = "grey40") +
  facet_wrap(~ pc, nrow = 1, scales = "free_x") +
  scale_fill_manual(values = c("TRUE" = COL_POS_BAR, "FALSE" = COL_NEG_BAR), guide = "none") +
  labs(title = "PCA loadings of environmental variables",
       subtitle = n_subtitle,
       x = "Loading", y = NULL) +
  theme_pub() +
  theme(axis.text.y = element_text(size = 8), legend.position = "none")

save_fig(file.path(fig_dir, "fig3_pca_loadings.png"), p3, 14, 7)

# ── Figure 2: MCMC coefficients ──────────────────────────────────────────────
message("Figure 2: MCMC coefficients...")

eff_pc <- effects %>%
  filter(variable != "(Intercept)") %>%
  mutate(significant = lower > 0 | upper < 0)

p2 <- make_forest_plot(
  eff_pc, paste0("PC", 1:5),
  "Environmental PCs and flower colour",
  subtitle = n_subtitle
)
save_fig(file.path(fig_dir, "fig2_mcmc_coefficients.png"), p2, 12, 5)

message("Figure 2 supplementary: PC6-PC10...")
p2s <- make_forest_plot(
  eff_pc, paste0("PC", 6:10),
  "Environmental PCs 6-10 and flower colour",
  subtitle = n_subtitle
)
save_fig(file.path(fig_dir, "fig2_supp_PC6_10.png"), p2s, 12, 5)

if (has_sv) {
  message("Figure 2b: Single-variable MCMC results...")
  sv <- sv_effects %>%
    filter(variable != "(Intercept)") %>%
    mutate(
      significant = lower > 0 | upper < 0,
      var_type    = vapply(env_var, var_label, character(1)),
      env_var     = factor(env_var, levels = loadings$variable)
    )

  p2b <- ggplot(sv, aes(x = mean, y = env_var, colour = significant)) +
    geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50") +
    geom_errorbar(aes(xmin = lower, xmax = upper), width = 0.15, linewidth = 0.5) +
    geom_point(size = 2, shape = 21, aes(fill = significant)) +
    scale_colour_manual(values = c("TRUE" = COL_SIG, "FALSE" = COL_NONSIG), guide = "none") +
    scale_fill_manual(values = c("TRUE" = COL_SIG, "FALSE" = "white"), guide = "none") +
    facet_grid(color ~ ., scales = "free_y", space = "free_y") +
    labs(title = "Single environmental variables and flower colour",
         subtitle = n_subtitle,
         x = "Posterior mean (95% CI)", y = NULL) +
    theme_pub_forest() +
    theme(axis.text.y = element_text(size = 7))

  save_fig(file.path(fig_dir, "fig2b_mcmc_env_variables.png"), p2b, 10, 14)
} else {
  message("  fig2b skipped — single_variable_models.csv not found for primary set.")
}

# ── Figure 4: convergence ────────────────────────────────────────────────────
message("Figure 4: Convergence diagnostics...")
p4 <- plot_convergence(gr_all)
save_fig(file.path(fig_dir, "fig4_convergence.png"), p4, 10.5, 4.0)

# ── Figure 5: pipeline summary ───────────────────────────────────────────────
message("Figure 5: Pipeline summary...")

# Construction funnel ending at the final primary analysis set (n = 1,438).
treatments_f <- file.path(primary_exp, "species_descriptions_treatments.csv")
clean_sp_f   <- file.path(primary_exp, "clean_species_only.csv")

df_tr <- read.csv(treatments_f, encoding = "UTF-8")
n_treatments <- nrow(df_tr)
n_described  <- if ("has_description" %in% names(df_tr)) {
  sum(toupper(as.character(df_tr$has_description)) %in% c("TRUE", "1", "YES"))
} else {
  sum(nzchar(as.character(df_tr$raw_text)))
}

df_clean_sp <- read.csv(clean_sp_f, encoding = "UTF-8")
if (!"binomial" %in% names(df_clean_sp) || all(!nzchar(as.character(df_clean_sp$binomial)))) {
  df_clean_sp$binomial <- trimws(paste(df_clean_sp$genus, df_clean_sp$epithet))
}
known_cats <- c("WHITE", "YELLOW", "RED", "PINK", "PURPLE/BLUE")
n_known <- length(unique(df_clean_sp$binomial[df_clean_sp$color_category %in% known_cats &
                                              nzchar(df_clean_sp$binomial)]))

pipe_df <- tibble(
  stage = c("Unique treatments",
            "With morphological description",
            "Known flower colour (corpus extracts)",
            "Environment-linked primary analysis set"),
  n     = c(n_treatments, n_described, n_known, n_analysis)
)
stopifnot(identical(as.integer(pipe_df$n), c(3857L, 3230L, 1674L, 1438L)))

# Anti-clip layout: short bar-end labels, wrapped subtitle, extra right room.
# Stages/counts unchanged; retention is vs the immediately preceding stage.
.pipe5_prev <- c(NA_real_, pipe_df$n[-nrow(pipe_df)])
.pipe5_d <- pipe_df %>%
  mutate(
    kept  = 100 * n / .pipe5_prev,
    label = ifelse(
      is.na(.pipe5_prev),
      scales::comma(n),
      sprintf("%s (%.0f%% retained)", scales::comma(n), kept)
    ),
    stage = factor(stage, levels = rev(stage))
  )
stopifnot(identical(
  sort(as.character(.pipe5_d$label)),
  sort(c("3,857", "3,230 (84% retained)",
         "1,674 (52% retained)", "1,438 (86% retained)"))
))

p5 <- ggplot(.pipe5_d, aes(x = n, y = stage, fill = stage)) +
  geom_col(width = 0.64) +
  geom_text(aes(label = label), hjust = -0.05, size = 3.1, colour = PUB_INK) +
  scale_fill_manual(values = rev(PUB_STAGE_RAMP(nrow(.pipe5_d))), guide = "none") +
  scale_x_continuous(
    labels = scales::comma,
    expand = expansion(mult = c(0, 0.34))
  ) +
  labs(
    title = "Species retention through the analysis pipeline",
    subtitle = paste0(
      "3,857 unique treatments → 3,230 with morphological descriptions →\n",
      "1,674 with known flower colour → 1,438 environment-linked species"
    ),
    x = "Number of records", y = NULL
  ) +
  theme_pub_hbar() +
  theme(
    plot.subtitle = element_text(lineheight = 1.2),
    plot.margin   = margin(12, 56, 12, 12)
  )
save_fig(file.path(fig_dir, "fig5_pipeline_summary.png"), p5, 10.2, 4.8)

# Compact coefficient plot (artefact name kept for path stability)
p_exp <- make_forest_plot(
  eff_pc, paste0("PC", 1:10),
  "MCMCglmm fixed effects (PC1-PC10)",
  subtitle = n_subtitle
)
save_fig(file.path(fig_dir, "coefficient_plot_expanded.png"), p_exp, 10, 8)

writeLines(c(
  paste("expanded_n_species", n_analysis),
  paste("WHITE", sum(df_analysis$is_white)),
  paste("YELLOW", sum(df_analysis$is_yellow)),
  paste("REDTYPE", sum(df_analysis$is_redtype)),
  paste("generated", as.character(Sys.time()))
), file.path(fig_dir, "expanded_n_summary.txt"))

# ── Supplementary traces ─────────────────────────────────────────────────────
message("Supplementary: Trace plots...")

if (requireNamespace("coda", quietly = TRUE) && dir.exists(step06_models)) {
  models <- list(
    WHITE   = readRDS(file.path(step06_models, "model_WHITE.rds")),
    YELLOW  = readRDS(file.path(step06_models, "model_YELLOW.rds")),
    REDTYPE = readRDS(file.path(step06_models, "model_REDTYPE.rds"))
  )

  trace_plots <- lapply(names(models), function(nm) {
    m <- models[[nm]]
    n_cols <- min(6, ncol(m$Sol))
    trace_df <- as.data.frame(m$Sol[, seq_len(n_cols), drop = FALSE]) %>%
      mutate(iter = row_number()) %>%
      pivot_longer(-iter, names_to = "parameter", values_to = "value")

    ggplot(trace_df, aes(x = iter, y = value, colour = parameter)) +
      geom_line(linewidth = 0.3, alpha = 0.85) +
      facet_wrap(~ parameter, scales = "free_y", ncol = 3) +
      labs(title = paste("MCMC trace,", nm),
           subtitle = n_subtitle,
           x = "Sample (post burn-in/thin)", y = NULL) +
      theme_pub() +
      theme(legend.position = "none", strip.text = element_text(size = 9))
  })

  p_traces <- wrap_plots(trace_plots, ncol = 1)
  save_fig(file.path(fig_dir, "figS_traceplots.png"), p_traces, 12, 16)

  for (i in seq_along(trace_plots)) {
    nm <- names(models)[i]
    save_fig(file.path(step06_fig, paste0("trace_", nm, ".png")), trace_plots[[i]], 10, 7)
  }

  p_pc13 <- make_forest_plot(eff_pc, paste0("PC", 1:3),
                             "MCMCglmm coefficients, PC1 to PC3",
                             subtitle = n_subtitle)
  save_fig(file.path(step06_fig, "coefficient_plot_PC1_PC3.png"), p_pc13, 10, 4)
  save_fig(file.path(fig_dir, "coefficient_plot_PC1_PC3.png"), p_pc13, 10, 4)
} else {
  message("  Trace plots skipped (coda / models missing).")
}

message("\n── Significant Results ─────────────────────────────────────────")
sig <- eff_pc %>% filter(significant) %>% select(color, variable, mean, lower, upper, pMCMC)
if (nrow(sig) > 0) print(sig) else message("No significant fixed effects.")

message("\n── Convergence ─────────────────────────────────────────────────")
conv_rows <- distinct(gr_all, color, mpsrf)
for (i in seq_len(nrow(conv_rows))) {
  row <- conv_rows[i, ]
  st  <- if (row$mpsrf < 1.1) "CONVERGED" else "NOT CONVERGED"
  message(sprintf("  %s MPSRF: %.6f %s", row$color, row$mpsrf, st))
}

# ── Publish to Results/ ──────────────────────────────────────────────────────
message("Publishing Results/ from primary analysis outputs...")
res  <- file.path(base_dir, "Results")
proc <- file.path(base_dir, "Processed Data")

for (d in c("figures/ecology", "figures/methods", "figures/supplementary",
            "tables/mcmc", "tables/elevation", "tables/descriptive")) {
  dir.create(file.path(res, d), recursive = TRUE, showWarnings = FALSE)
}

publish_copy <- function(src, dst) {
  if (!file.exists(src)) return(invisible(FALSE))
  if (file.exists(dst) || (!is.na(Sys.readlink(dst)) && nzchar(Sys.readlink(dst)))) {
    unlink(dst)
  }
  dir.create(dirname(dst), recursive = TRUE, showWarnings = FALSE)
  file.copy(src, dst, overwrite = TRUE)
  invisible(TRUE)
}

ecology_figs <- c(
  "fig1_colour_counts.png", "fig2_mcmc_coefficients.png",
  "fig3_pca_loadings.png", "fig4_convergence.png", "fig5_pipeline_summary.png"
)
for (f in ecology_figs) {
  publish_copy(file.path(fig_dir, f), file.path(res, "figures/ecology", f))
}
publish_copy(file.path(fig_dir, "fig2_supp_PC6_10.png"),
        file.path(res, "figures/supplementary", "fig2_supp_PC6_10.png"))
publish_copy(file.path(fig_dir, "figS_traceplots.png"),
        file.path(res, "figures/supplementary", "figS_traceplots.png"))
publish_copy(file.path(fig_dir, "coefficient_plot_PC1_PC3.png"),
        file.path(res, "figures/supplementary", "coefficient_plot_PC1_PC3.png"))

elev_fig <- file.path(step08_dir, "figures")
if (dir.exists(elev_fig)) {
  for (f in list.files(elev_fig, pattern = "\\.png$")) {
    publish_copy(file.path(elev_fig, f), file.path(res, "figures/ecology", f))
  }
}

mcmc_tables <- c(
  "combined/all_fixed_effects_combined.csv",
  "fixed_effects/fixed_effects_WHITE.csv", "fixed_effects/fixed_effects_YELLOW.csv",
  "fixed_effects/fixed_effects_REDTYPE.csv",
  "convergence/gelman_rubin_WHITE.csv", "convergence/gelman_rubin_YELLOW.csv",
  "convergence/gelman_rubin_REDTYPE.csv",
  "random_effects/random_effects_WHITE.csv", "random_effects/random_effects_YELLOW.csv",
  "random_effects/random_effects_REDTYPE.csv"
)
for (t in mcmc_tables) {
  publish_copy(file.path(step06_tables, t), file.path(res, "tables/mcmc", basename(t)))
}

sig_out <- effects %>%
  filter(variable != "(Intercept)", lower > 0 | upper < 0)
write.csv(sig_out, file.path(res, "tables/mcmc/significant_results.csv"), row.names = FALSE)

gr_files <- list.files(gr_dir, full.names = TRUE, pattern = "gelman")
if (length(gr_files) > 0) {
  gr <- do.call(rbind, lapply(gr_files, function(f) {
    x <- read.csv(f)
    x$color <- sub("gelman_rubin_(.*)\\.csv", "\\1", basename(f))
    x
  }))
  conv <- aggregate(point_est ~ color, gr, function(x) max(x, na.rm = TRUE))
  names(conv)[2] <- "max_psrf"
  conv$mpsrf <- sapply(conv$color, function(c) unique(gr$mpsrf[gr$color == c]))
  conv$converged <- conv$mpsrf < 1.1
  write.csv(conv, file.path(res, "tables/mcmc/convergence_summary.csv"), row.names = FALSE)
}

color_summary_dst <- file.path(res, "tables/descriptive/color_category_summary.csv")
if (file.exists(color_summary_dst) && !identical(Sys.readlink(color_summary_dst), "")) {
  unlink(color_summary_dst)
}
write.csv(color_counts, color_summary_dst, row.names = FALSE)

publish_copy(file.path(step05_dir, "pca_loadings.csv"),
        file.path(res, "tables/descriptive/pca_loadings.csv"))

if (dir.exists(step08_dir)) {
  for (t in c("elevation_band_summary.csv", "elevation_mcmc_results.csv",
              "pc2_by_elevation_band.csv", "elevation_analysis_summary.txt")) {
    publish_copy(file.path(step08_dir, t), file.path(res, "tables/elevation", t))
  }
}

writeLines(c(
  "# Thesis Results", "",
  "```",
  "Results/",
  "├── figures/",
  "│   ├── ecology/         fig1-fig6  colour, climate models, elevation",
  "│   ├── methods/         fig7-fig14 gold set, errors, RAG, prediction",
  "│   ├── reliability/     fig15-fig18 overlap, forest, convergence",
  "│   └── supplementary/   extra coefficient and trace plots",
  "├── tables/",
  "│   ├── mcmc/            colour-environment model output",
  "│   ├── elevation/       elevation-band tables",
  "│   ├── descriptive/     colour counts, PCA loadings",
  "│   └── reliability/     agreement and MCMC diagnostics",
  "```", "",
  paste("Last synced:", Sys.time()),
  paste("Analysis N:", n_analysis)
), file.path(res, "README.md"))

message("Results published to: ", res)
message("Primary figure publish complete (N=", n_analysis, ").")
