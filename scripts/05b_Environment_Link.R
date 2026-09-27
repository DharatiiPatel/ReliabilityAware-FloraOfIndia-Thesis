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
# Combine GBIF occurrence tables, extract environment, and run PCA.
# Writes the primary analysis table under experiments/expansion/step05b_outputs/.

.libPaths(c("~/R/library", .libPaths()))
options(stringsAsFactors = FALSE)
options(bitmapType = "cairo")

library(terra)
library(geodata)
library(dplyr)

old_occ  <- file.path(base_dir, "Processed Data/experiments/gbif_outputs_clean/gbif_occurrences_all.csv")
new_occ  <- file.path(base_dir, "Processed Data/experiments/expansion/gbif_outputs/gbif_occurrences_new.csv")
env_dir  <- file.path(base_dir, "Processed Data/step05_env_data")
output_dir <- file.path(base_dir, "Processed Data/experiments/expansion/step05b_outputs")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

out_env_species  <- file.path(output_dir, "species_environment_trimmed.csv")
out_pca_scores   <- file.path(output_dir, "species_pca_scores.csv")
out_pca_loadings <- file.path(output_dir, "pca_loadings.csv")
out_final        <- file.path(output_dir, "species_color_environment_final_expanded.csv")
combined_occ_out <- file.path(base_dir, "Processed Data/experiments/expansion/gbif_outputs/gbif_occurrences_combined.csv")

message("Combining occurrence tables...")
occ_old <- read.csv(old_occ, encoding = "UTF-8")
occ_new <- if (file.exists(new_occ)) read.csv(new_occ, encoding = "UTF-8") else data.frame()
if (nrow(occ_new) > 0) {
  overlap <- intersect(unique(occ_old$query_name), unique(occ_new$query_name))
  if (length(overlap)) {
    message("Replacing ", length(overlap), " overlapping species with new colour labels")
    occ_old <- occ_old[!occ_old$query_name %in% overlap, ]
  }
  cols <- union(names(occ_old), names(occ_new))
  for (c in cols) {
    if (!c %in% names(occ_old)) occ_old[[c]] <- NA
    if (!c %in% names(occ_new)) occ_new[[c]] <- NA
  }
  occ <- bind_rows(occ_old[, cols], occ_new[, cols])
} else {
  occ <- occ_old
  message("No new occurrences; recomputing env/PCA on the earlier occurrence table")
}
dir.create(dirname(combined_occ_out), recursive = TRUE, showWarnings = FALSE)
write.csv(occ, combined_occ_out, row.names = FALSE)
message("Combined records: ", nrow(occ), " species: ", length(unique(occ$query_name)))

message("Loading rasters from cache...")
worldclim_bio <- worldclim_global(var = "bio", res = 10, path = env_dir)
worldclim_elev <- elevation_global(res = 10, path = env_dir)
soil_vars <- c("bdod", "cec", "nitrogen", "phh2o", "soc", "ocd", "ocs",
               "clay", "silt", "sand", "cfvo")
soil_rasters <- list()
for (var in soil_vars) {
  tryCatch({
    soil_rasters[[var]] <- soil_world(var = var, depth = 5, path = env_dir)
  }, error = function(e) message("  WARNING: ", var, " - ", conditionMessage(e)))
}

required_cols <- c("query_name", "decimalLatitude", "decimalLongitude",
                   "color_group", "color_category")
missing_cols <- setdiff(required_cols, names(occ))
if (length(missing_cols) > 0) stop("Missing columns: ", paste(missing_cols, collapse = ", "))

occ <- occ[!is.na(occ$decimalLatitude) & !is.na(occ$decimalLongitude), ]
coords <- vect(occ[, c("decimalLongitude", "decimalLatitude")],
               geom = c("decimalLongitude", "decimalLatitude"), crs = "EPSG:4326")

bio_vals <- extract(worldclim_bio, coords)[, -1]
names(bio_vals) <- paste0("bio", 1:19)
elev_vals <- extract(worldclim_elev, coords)[, -1, drop = FALSE]
names(elev_vals) <- "alt"
soil_vals_list <- list()
for (var in names(soil_rasters)) {
  tryCatch({
    sv <- extract(soil_rasters[[var]], coords)[, -1, drop = FALSE]
    names(sv) <- var
    soil_vals_list[[var]] <- sv
  }, error = function(e) message("  WARNING extract ", var))
}
env_vals <- cbind(bio_vals, elev_vals)
if (length(soil_vals_list) > 0) env_vals <- cbind(env_vals, do.call(cbind, soil_vals_list))

occ_env <- cbind(
  occ[, c("query_name", "color_group", "color_category",
          "decimalLatitude", "decimalLongitude")],
  env_vals
)

message("Removing duplicate grid cells...")
occ_env$lat_round <- round(occ_env$decimalLatitude,  1)
occ_env$lon_round <- round(occ_env$decimalLongitude, 1)
occ_env <- occ_env[!duplicated(
  paste(occ_env$query_name, occ_env$lat_round, occ_env$lon_round)
), ]
message("Records after deduplication: ", nrow(occ_env))

species_counts <- table(occ_env$query_name)
species_keep   <- names(species_counts[species_counts >= 6])
occ_env        <- occ_env[occ_env$query_name %in% species_keep, ]
message("Species with >= 6 records: ", length(species_keep))

env_cols <- c(paste0("bio", 1:19), "alt", soil_vars)
env_cols <- intersect(env_cols, names(occ_env))
trim_mean <- function(x) mean(x, trim = 0.2, na.rm = TRUE)

species_env <- occ_env %>%
  group_by(query_name, color_group, color_category) %>%
  summarise(
    n_records = n(),
    across(all_of(env_cols), trim_mean),
    .groups = "drop"
  )
write.csv(species_env, out_env_species, row.names = FALSE)

env_matrix <- species_env[, env_cols]
complete_rows <- complete.cases(env_matrix)
species_complete <- species_env[complete_rows, ]
env_matrix_clean <- env_matrix[complete_rows, ]
pca_result <- prcomp(env_matrix_clean, center = TRUE, scale. = TRUE)
pc_scores <- as.data.frame(pca_result$x[, 1:10])
names(pc_scores) <- paste0("PC", 1:10)
species_pca <- cbind(
  species_complete[, c("query_name", "color_group", "color_category", "n_records")],
  pc_scores
)
species_pca$is_white   <- as.integer(species_pca$color_group == "WHITE")
species_pca$is_yellow  <- as.integer(species_pca$color_group == "YELLOW")
species_pca$is_redtype <- as.integer(species_pca$color_group == "REDTYPE")

write.csv(species_pca, out_pca_scores, row.names = FALSE)
loadings_df <- as.data.frame(pca_result$rotation[, 1:10])
loadings_df$variable <- rownames(loadings_df)
write.csv(loadings_df, out_pca_loadings, row.names = FALSE)
write.csv(species_pca, out_final, row.names = FALSE)

message("Primary final: ", nrow(species_pca), " species -> ", out_final)
var_explained <- summary(pca_result)$importance[2, 1:10] * 100
for (i in 1:10) message(sprintf("  PC%d: %.1f%%", i, var_explained[i]))
