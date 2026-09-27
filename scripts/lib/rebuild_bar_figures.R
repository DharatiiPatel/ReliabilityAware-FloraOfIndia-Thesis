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
# Rebuild only the bar-chart figures, in publication style, from cached CSVs.
#
# No MCMC is re-run. Outputs are written to the canonical figure directories,
# so the symlinks under Results/figures/ pick them up automatically.
#
#   module load R/4.5.1-gfbf-2025a
#   Rscript scripts/lib/rebuild_bar_figures.R

source(file.path(base_dir, "scripts/lib/figure_style.R"))

suppressPackageStartupMessages(library(tidyr))

step04_dir <- file.path(base_dir, "Processed Data/step04_outputs")
step05_dir <- file.path(base_dir, "Processed Data/step05_outputs")
step06_dir <- file.path(base_dir, "Processed Data/step06_outputs")
step08_dir <- file.path(base_dir, "Processed Data/step08_outputs")
fig_dir    <- file.path(base_dir, "Processed Data/figures")
elev_figs  <- file.path(step08_dir, "figures")

save_fig <- function(path, plot, w, h) {
  ggsave(path, plot, width = w, height = h, dpi = 300, bg = "white")
  message("  ", basename(path))
}

message("Rebuilding bar charts in publication style...")

# --- fig1: colour counts ----------------------------------------------------
df_species <- read.csv(file.path(step04_dir,
                                 "flora_india_color_clean_species_only.csv"))
colour_counts <- df_species %>%
  filter(!color_category %in% c("UNKNOWN", "OTHER", "GREENISH")) %>%
  count(color_category, name = "n")
save_fig(file.path(fig_dir, "fig1_colour_counts.png"),
         plot_colour_counts(colour_counts), 8.0, 4.4)

# --- fig4: convergence ------------------------------------------------------
gr_dir <- file.path(step06_dir, "tables/convergence")
if (!dir.exists(gr_dir)) gr_dir <- step06_dir
gr_all <- bind_rows(
  read.csv(file.path(gr_dir, "gelman_rubin_WHITE.csv"))   %>% mutate(color = "WHITE"),
  read.csv(file.path(gr_dir, "gelman_rubin_YELLOW.csv"))  %>% mutate(color = "YELLOW"),
  read.csv(file.path(gr_dir, "gelman_rubin_REDTYPE.csv")) %>% mutate(color = "REDTYPE")
)
save_fig(file.path(fig_dir, "fig4_convergence.png"),
         plot_convergence(gr_all), 10.5, 4.0)

# --- fig5: pipeline retention ----------------------------------------------
n_parsed <- nrow(read.csv(file.path(
  base_dir, "Processed Data/flora_of_india_species_descriptions.csv")))
n_species <- nrow(df_species)
n_known   <- sum(!df_species$color_category %in% c("UNKNOWN", "OTHER", "GREENISH"))
n_gbif    <- length(list.files(file.path(base_dir, "Processed Data/step05_gbif_cache"),
                               pattern = "\\.csv$"))
n_final   <- nrow(read.csv(file.path(step05_dir,
                                     "species_color_environment_final.csv")))

pipe_df <- tibble(
  stage = c("Parsed text blocks", "Species-level records", "Known flower colour",
            "GBIF matched", "Final analysis set"),
  n     = c(n_parsed, n_species, n_known, n_gbif, n_final)
)
save_fig(file.path(fig_dir, "fig5_pipeline_summary.png"),
         plot_pipeline(pipe_df), 8.6, 4.4)

# --- fig6: elevation bar charts --------------------------------------------
band_summary <- read.csv(file.path(step08_dir, "elevation_band_summary.csv"),
                         check.names = FALSE)

prop_df <- band_summary %>%
  select(elev_band, pct_white, pct_yellow, pct_redtype) %>%
  pivot_longer(-elev_band, names_to = "colour", values_to = "pct") %>%
  mutate(colour = recode(colour, pct_white = "WHITE",
                         pct_yellow = "YELLOW", pct_redtype = "REDTYPE"))

count_df <- band_summary %>%
  select(elev_band, n_white, n_yellow, n_redtype) %>%
  pivot_longer(-elev_band, names_to = "colour", values_to = "n") %>%
  mutate(colour = recode(colour, n_white = "WHITE",
                         n_yellow = "YELLOW", n_redtype = "REDTYPE"))

p_prop  <- plot_elev_proportions(prop_df, band_summary)
p_count <- plot_elev_counts(count_df, band_summary)

for (d in c(elev_figs, fig_dir)) {
  dir.create(d, recursive = TRUE, showWarnings = FALSE)
}
save_fig(file.path(elev_figs, "fig6_elevation_colour_proportions.png"), p_prop, 8.6, 4.8)
save_fig(file.path(elev_figs, "fig6_elevation_species_counts.png"),    p_count, 9.2, 4.8)

message("Done. Results/figures/ symlinks now point at the new versions.")
