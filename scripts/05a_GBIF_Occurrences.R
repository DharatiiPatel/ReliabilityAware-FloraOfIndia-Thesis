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
# GBIF fetch for species added by fascicles/recovery (04g).
# Reuses the existing GBIF cache. Writes under experiments/expansion/.

.libPaths(c("~/R/library", .libPaths()))
options(stringsAsFactors = FALSE)

for (pkg in c("rgbif", "dplyr")) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg, repos = "https://cloud.r-project.org")
  }
  library(pkg, character.only = TRUE)
}

input_file  <- file.path(base_dir, "Processed Data/experiments/expansion/species_for_gbif_new.csv")
cache_dir   <- file.path(base_dir, "Processed Data/experiments/gbif_cache_clean")  # SHARED cache
output_dir  <- file.path(base_dir, "Processed Data/experiments/expansion/gbif_outputs")
dir.create(cache_dir,  recursive = TRUE, showWarnings = FALSE)
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

final_output <- file.path(output_dir, "gbif_occurrences_new.csv")
failed_log   <- file.path(output_dir, "gbif_failed_species_new.txt")

MAX_RECORDS   <- 10000
MIN_RECORDS   <- 6
SLEEP_BETWEEN <- 0.5

message("Reading: ", input_file)
df <- read.csv(input_file, encoding = "UTF-8")
df <- df[nzchar(as.character(df$binomial)) & !is.na(df$binomial), ]
known_colors <- c("WHITE", "YELLOW", "RED", "PINK", "PURPLE/BLUE")
df <- df[df$color_category %in% known_colors, ]
if (nrow(df) == 0) {
  message("No new colour-bearing species to fetch. Writing empty occurrence file.")
  write.csv(data.frame(query_name=character(), color_group=character(),
                       color_category=character(), decimalLatitude=numeric(),
                       decimalLongitude=numeric()), final_output, row.names = FALSE)
  quit(save = "no", status = 0)
}

df$color_group <- df$color_category
df$color_group[df$color_category %in% c("RED", "PINK", "PURPLE/BLUE")] <- "REDTYPE"
df$binomial <- trimws(df$binomial)
df_unique <- df[!duplicated(df$binomial), ]
message("NEW species for GBIF: ", nrow(df_unique))

fetch_occurrences <- function(species_name) {
  tryCatch({
    name_result <- name_backbone(name = species_name, rank = "species", verbose = FALSE)
    if (is.null(name_result) || is.na(name_result$usageKey)) {
      return(list(status = "no_match", data = NULL))
    }
    occ <- occ_search(
      taxonKey = name_result$usageKey, hasCoordinate = TRUE, limit = MAX_RECORDS,
      fields = c("species", "decimalLatitude", "decimalLongitude",
                 "year", "countryCode", "gbifID", "hasGeospatialIssues")
    )
    if (is.null(occ$data) || nrow(occ$data) == 0) {
      return(list(status = "no_records", data = NULL))
    }
    occ_clean <- occ$data[!is.na(occ$data$decimalLatitude) &
                          !is.na(occ$data$decimalLongitude), ]
    if ("hasGeospatialIssues" %in% names(occ_clean)) {
      occ_clean <- occ_clean[is.na(occ_clean$hasGeospatialIssues) |
                             occ_clean$hasGeospatialIssues == FALSE, ]
    }
    if (nrow(occ_clean) == 0) return(list(status = "no_clean_records", data = NULL))
    list(status = "success", data = occ_clean)
  }, error = function(e) list(status = paste("error:", conditionMessage(e)), data = NULL))
}

failed <- character()
for (i in seq_len(nrow(df_unique))) {
  sp <- df_unique$binomial[i]
  safe_name <- gsub("[^A-Za-z0-9]+", "_", sp)
  cache_file <- file.path(cache_dir, paste0(safe_name, ".csv"))
  message(sprintf("[%d/%d] %s", i, nrow(df_unique), sp))
  if (file.exists(cache_file) && file.info(cache_file)$size > 10) {
    message("  cache hit")
  } else {
    res <- fetch_occurrences(sp)
    if (identical(res$status, "success")) {
      write.csv(res$data, cache_file, row.names = FALSE)
    } else {
      write.csv(data.frame(), cache_file, row.names = FALSE)
      failed <- c(failed, paste(sp, res$status))
      message("  ", res$status)
    }
    Sys.sleep(SLEEP_BETWEEN)
  }
}
if (length(failed)) writeLines(failed, failed_log)

parts <- list()
for (i in seq_len(nrow(df_unique))) {
  sp <- df_unique$binomial[i]
  safe_name <- gsub("[^A-Za-z0-9]+", "_", sp)
  cache_file <- file.path(cache_dir, paste0(safe_name, ".csv"))
  if (!file.exists(cache_file) || file.info(cache_file)$size <= 10) next
  d <- tryCatch(read.csv(cache_file), error = function(e) NULL)
  if (is.null(d) || nrow(d) < MIN_RECORDS) next
  d$query_name <- sp
  d$color_category <- df_unique$color_category[i]
  d$color_group <- df_unique$color_group[i]
  parts[[length(parts) + 1]] <- d
}
if (length(parts) == 0) {
  write.csv(data.frame(query_name=character(), color_group=character(),
                       color_category=character(), decimalLatitude=numeric(),
                       decimalLongitude=numeric()), final_output, row.names = FALSE)
  message("No species met MIN_RECORDS=", MIN_RECORDS)
} else {
  combined <- dplyr::bind_rows(parts)
  write.csv(combined, final_output, row.names = FALSE)
  message("Wrote ", nrow(combined), " records for ",
          length(unique(combined$query_name)), " species -> ", final_output)
}
