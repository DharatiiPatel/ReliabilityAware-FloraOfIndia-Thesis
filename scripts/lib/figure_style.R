#!/usr/bin/env Rscript
# Shared publication style for thesis bar charts.
#
# Sourced by 07_Generate_Figures.R, 08_ElevationGradient_Analysis.R and
# rebuild_bar_figures.R so that regenerating figures by any route gives the
# same output.
#
# Design rules:
#   * bars always start at a true zero - no truncated baselines
#   * category labels read horizontally (bars are flipped where labels are long)
#   * values are printed on the plot, so the reader never measures against a gridline
#   * one muted palette shared with the method-depth figures (fig7-fig14)
#   * no chartjunk: no vertical gridlines behind horizontal bars, no legend when
#     the fill is already named on the axis

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
})

# ---------------------------------------------------------------- palettes ---

PUB_INK   <- "#1b1b1b"
PUB_MUTED <- "#6e6e6e"
PUB_GRID  <- "#e3e3e3"

# Colour-class palette, matched to the CS/method figures.
PUB_CLASS_COLORS <- c(
  WHITE         = "#b9b3a4",
  YELLOW        = "#d8a634",
  REDTYPE       = "#a63f34",
  RED           = "#a63f34",
  PINK          = "#c98da8",
  "PURPLE/BLUE" = "#6b7fa8"
)

# Sequential ramp for pipeline-stage figures (attrition reads left to right).
PUB_STAGE_RAMP <- colorRampPalette(c("#2e6f78", "#7aa7ac", "#c3a98a", "#b4622d"))

# DejaVu Sans is the same family matplotlib uses for the method figures.
PUB_FONT <- "DejaVu Sans"

theme_pub <- function(base_size = 11) {
  theme_minimal(base_size = base_size, base_family = PUB_FONT) +
    theme(
      plot.title       = element_text(face = "bold", size = 12,
                                      hjust = 0, colour = PUB_INK,
                                      margin = margin(b = 4)),
      plot.subtitle    = element_text(size = 9.5, hjust = 0,
                                      colour = PUB_MUTED,
                                      margin = margin(b = 8)),
      plot.caption     = element_text(size = base_size - 2.5, hjust = 0,
                                      colour = PUB_MUTED,
                                      margin = margin(t = 10)),
      plot.title.position   = "plot",
      plot.caption.position = "plot",
      axis.title       = element_text(size = base_size - 0.5, colour = PUB_INK),
      axis.text        = element_text(size = base_size - 1.5, colour = PUB_INK),
      panel.grid.minor = element_blank(),
      strip.text       = element_text(face = "bold", size = base_size - 0.5,
                                      hjust = 0, colour = PUB_INK),
      legend.position  = "bottom",
      legend.title     = element_text(size = base_size - 1.5),
      legend.text      = element_text(size = base_size - 1.5),
      legend.key.height = unit(0.8, "lines"),
      plot.margin      = margin(12, 16, 10, 12)
    )
}

# Horizontal bars: gridlines run along x only.
theme_pub_hbar <- function(base_size = 11) {
  theme_pub(base_size) +
    theme(
      panel.grid.major.y = element_blank(),
      panel.grid.major.x = element_line(colour = PUB_GRID, linewidth = 0.4),
      axis.ticks         = element_blank()
    )
}

# Vertical bars: gridlines run along y only.
theme_pub_vbar <- function(base_size = 11) {
  theme_pub(base_size) +
    theme(
      panel.grid.major.x = element_blank(),
      panel.grid.major.y = element_line(colour = PUB_GRID, linewidth = 0.4),
      axis.ticks         = element_blank()
    )
}

# Forest / coefficient plots: no y-grid, left-aligned facet strips.
theme_pub_forest <- function(base_size = 11) {
  theme_pub(base_size) +
    theme(
      panel.grid.major.y = element_blank(),
      panel.grid.major.x = element_line(colour = PUB_GRID, linewidth = 0.4),
      strip.background   = element_rect(fill = "grey90", colour = NA),
      panel.spacing      = unit(1.2, "lines"),
      axis.ticks         = element_blank(),
      legend.position    = "none"
    )
}

# ------------------------------------------------------------- fig 1 ---------

#' Flower colour distribution.
#' @param counts data frame with columns color_category, n
plot_colour_counts <- function(counts) {
  total <- sum(counts$n)
  d <- counts %>%
    mutate(
      pct   = 100 * n / total,
      label = sprintf("%s   %.1f%%", comma(n), pct),
      color_category = factor(color_category,
                              levels = color_category[order(n)])
    )

  ggplot(d, aes(x = n, y = color_category, fill = color_category)) +
    geom_col(width = 0.66) +
    geom_text(aes(label = label), hjust = -0.06, size = 3.2, colour = PUB_INK) +
    scale_fill_manual(values = PUB_CLASS_COLORS, guide = "none") +
    scale_x_continuous(labels = comma,
                       expand = expansion(mult = c(0, 0.20))) +
    labs(
      title    = "Flower colour in the analysis set",
      subtitle = sprintf("n = %s", comma(total)),
      x = "Number of species", y = NULL
    ) +
    theme_pub_hbar()
}

# ------------------------------------------------------------- fig 4 ---------

#' Gelman-Rubin convergence.
#' Plots |PSRF - 1| from a true zero baseline. The old version drew bars from a
#' faked 0.998 baseline, which visually exaggerated differences that are noise.
#' Magnitude is used because a PSRF marginally below 1 is Monte Carlo noise, not
#' a qualitatively different outcome; the criterion is |PSRF - 1| < 0.1.
#' @param gr data frame with columns variable, point_est, color
plot_convergence <- function(gr) {
  d <- gr %>%
    filter(variable != "(Intercept)", grepl("^PC", variable)) %>%
    mutate(
      color    = factor(color, levels = c("WHITE", "YELLOW", "REDTYPE")),
      variable = factor(variable, levels = paste0("PC", 1:10)),
      dev      = abs(point_est - 1)
    )
  worst <- max(d$dev)

  ggplot(d, aes(x = variable, y = dev)) +
    geom_col(width = 0.62, fill = "#2e6f78") +
    facet_wrap(~ color, nrow = 1) +
    scale_y_continuous(
      labels = function(x) format(x, scientific = FALSE, drop0trailing = TRUE),
      expand = expansion(mult = c(0, 0.14))
    ) +
    labs(
      title    = "MCMC convergence",
      subtitle = sprintf("Largest |PSRF - 1| = %.5f", worst),
      x = NULL, y = "|PSRF - 1|"
    ) +
    theme_pub_vbar() +
    theme(axis.text.x = element_text(size = 7))
}

# ------------------------------------------------------------- fig 5 ---------

#' Pipeline retention funnel.
#' @param pipe data frame with columns stage (ordered factor) and n
plot_pipeline <- function(pipe) {
  start <- pipe$n[1]
  prev <- c(NA_real_, pipe$n[-length(pipe$n)])
  d <- pipe %>%
    mutate(
      pct_of_start = 100 * n / start,
      kept         = 100 * n / prev,
      label        = ifelse(
        is.na(prev),
        sprintf("%s", comma(n)),
        sprintf("%s   %.0f%% retained from preceding stage", comma(n), kept)
      ),
      stage = factor(stage, levels = rev(levels(factor(stage, levels = stage))))
    )

  ggplot(d, aes(x = n, y = stage, fill = stage)) +
    geom_col(width = 0.64) +
    geom_text(aes(label = label), hjust = -0.05, size = 3.1, colour = PUB_INK) +
    scale_fill_manual(values = rev(PUB_STAGE_RAMP(nrow(d))), guide = "none") +
    scale_x_continuous(labels = comma,
                       expand = expansion(mult = c(0, 0.28))) +
    labs(
      title = "Species retention through the analysis pipeline",
      subtitle = paste(
        "3,857 unique treatments → 3,230 with morphological description →",
        "1,674 with known flower colour in corpus extracts →",
        "1,438 environment-linked primary analysis species.",
        "Percentages are retention relative to the immediately preceding stage."
      ),
      x = "Number of records", y = NULL
    ) +
    theme_pub_hbar()
}

# ------------------------------------------------------- fig 6 (elevation) ---

#' Colour composition across elevation bands (100% stacked - correct encoding
#' for parts of a whole).
#' @param prop long data: elev_band, colour, pct
#' @param bands data with elev_band, n_species
plot_elev_proportions <- function(prop, bands) {
  lev <- unique(as.character(bands$elev_band))
  prop <- prop %>%
    mutate(
      elev_band = factor(as.character(elev_band), levels = lev),
      colour    = factor(colour, levels = c("REDTYPE", "WHITE", "YELLOW"))
    ) %>%
    group_by(elev_band) %>%
    arrange(desc(colour), .by_group = TRUE) %>%
    mutate(pos = cumsum(pct) - pct / 2) %>%
    ungroup()

  bands <- bands %>%
    mutate(elev_band = factor(as.character(elev_band), levels = lev))

  ggplot(prop, aes(x = elev_band, y = pct, fill = colour)) +
    geom_col(width = 0.7) +
    geom_text(aes(y = pos, label = sprintf("%.0f%%", pct),
                  colour = colour == "WHITE"),
              size = 3.1, show.legend = FALSE) +
    geom_text(data = bands, inherit.aes = FALSE,
              aes(x = elev_band, y = 103, label = paste0("n = ", comma(n_species))),
              size = 3.0, colour = PUB_MUTED) +
    scale_fill_manual(values = PUB_CLASS_COLORS, name = NULL,
                      breaks = c("WHITE", "YELLOW", "REDTYPE")) +
    scale_colour_manual(values = c("TRUE" = PUB_INK, "FALSE" = "white"),
                        guide = "none") +
    scale_y_continuous(breaks = seq(0, 100, 25),
                       expand = expansion(mult = c(0, 0.07))) +
    coord_cartesian(ylim = c(0, 107), clip = "off") +
    labs(
      title    = "Flower colour across elevation bands",
      x = NULL, y = "Share of species (%)"
    ) +
    theme_pub_vbar() +
    theme(axis.text.x = element_text(size = 8.5))
}

#' Species counts by band and colour.
#' Grouped rather than stacked: only the bottom segment of a stacked bar shares
#' a baseline, so stacking makes YELLOW and REDTYPE impossible to compare.
#' @param counts long data: elev_band, colour, n
#' @param bands data with elev_band, n_species
plot_elev_counts <- function(counts, bands) {
  lev <- unique(as.character(bands$elev_band))
  counts <- counts %>%
    mutate(
      elev_band = factor(as.character(elev_band), levels = lev),
      colour    = factor(colour, levels = c("WHITE", "YELLOW", "REDTYPE"))
    )
  bands <- bands %>%
    mutate(elev_band = factor(as.character(elev_band), levels = lev))

  ggplot(counts, aes(x = elev_band, y = n, fill = colour)) +
    geom_col(position = position_dodge(width = 0.78), width = 0.72) +
    geom_text(aes(label = n), position = position_dodge(width = 0.78),
              vjust = -0.45, size = 2.9, colour = PUB_INK) +
    geom_text(data = bands, inherit.aes = FALSE,
              aes(x = elev_band, y = -18,
                  label = paste0("band total ", comma(n_species))),
              size = 2.9, colour = PUB_MUTED) +
    scale_fill_manual(values = PUB_CLASS_COLORS, name = NULL) +
    scale_y_continuous(labels = comma,
                       expand = expansion(mult = c(0, 0.12))) +
    coord_cartesian(ylim = c(-24, NA), clip = "off") +
    labs(
      title = "Species counts by elevation band",
      x = NULL, y = "Number of species"
    ) +
    theme_pub_vbar() +
    theme(axis.text.x = element_text(size = 8.5))
}
