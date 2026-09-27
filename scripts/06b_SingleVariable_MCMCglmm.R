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

options(stringsAsFactors = FALSE)

required_packages <- c("MCMCglmm")
for (pkg in required_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg, lib = "~/R/library", repos = "https://cloud.r-project.org")
  }
  library(pkg, character.only = TRUE)
}

# Optional: restrict to one colour via command-line arg (for SLURM array)
args <- commandArgs(trailingOnly = TRUE)
color_filter <- if (length(args) >= 1 && nzchar(args[1])) toupper(args[1]) else NULL

input_file <- file.path(base_dir, "Processed Data/experiments/expansion/step05b_outputs/species_color_environment_final_expanded.csv")
output_dir <- file.path(base_dir, "Processed Data/experiments/expansion/step06_outputs")
dir_combined <- file.path(output_dir, "tables/combined")
dir.create(dir_combined, recursive = TRUE, showWarnings = FALSE)
out_csv    <- file.path(dir_combined, "single_variable_models.csv")

NITT   <- 1050000
BURNIN <- 50000
THIN   <- 100
PRIOR  <- list(R = list(V = 1, fix = 1), G = list(G1 = list(V = 1, nu = 0.002)))

colors_to_run <- list(
  list(col = "is_white",   label = "WHITE"),
  list(col = "is_yellow",  label = "YELLOW"),
  list(col = "is_redtype", label = "REDTYPE")
)
if (!is.null(color_filter)) {
  colors_to_run <- Filter(function(x) x$label == color_filter, colors_to_run) #Filter keeps only the elements of the list that satisfy the condition.
  if (length(colors_to_run) == 0) stop("Unknown colour filter: ", color_filter) #stop stops the script and prints the error message.
} 

message("Loading data: ", input_file)
df <- read.csv(input_file, encoding = "UTF-8")
df$genus <- sapply(strsplit(df$query_name, " "), function(x) x[1])

env_file <- file.path(base_dir, "Processed Data/experiments/expansion/step05b_outputs/species_environment_trimmed.csv")
loadings <- read.csv(file.path(base_dir, "Processed Data/experiments/expansion/step05b_outputs/pca_loadings.csv"))
env_vars <- loadings$variable

if (file.exists(env_file)) {
  env_df <- read.csv(env_file)
  env_cols <- setdiff(names(env_df), names(df))
  df <- merge(df, env_df[, c("query_name", env_cols)], by = "query_name", all.x = TRUE)
  message("Merged ", length(env_cols), " environmental variables")
}

# Load existing results for resume
done_keys <- character(0)
if (file.exists(out_csv)) {
  existing <- read.csv(out_csv)
  if (nrow(existing) > 0 && "color" %in% names(existing) && "env_var" %in% names(existing)) {
    done_keys <- paste(existing$color, existing$env_var, sep = "___")
    message("Resuming: ", length(done_keys), " models already completed")
  }
}

normalize_summary <- function(sv_summary, env_var, color_label) {
  sv_summary$variable <- rownames(sv_summary)
  rownames(sv_summary) <- NULL
  if ("post.mean" %in% names(sv_summary)) {
    names(sv_summary)[names(sv_summary) == "post.mean"] <- "mean"
    names(sv_summary)[names(sv_summary) == "l-95% CI"] <- "lower"
    names(sv_summary)[names(sv_summary) == "u-95% CI"] <- "upper"
  }
  sv_summary$env_var <- env_var
  sv_summary$color   <- color_label
  sv_summary
}

append_result <- function(row_df) {
  if (file.exists(out_csv) && file.info(out_csv)$size > 0) {
    write.table(row_df, out_csv, append = TRUE, sep = ",",
                row.names = FALSE, col.names = FALSE)
  } else {
    write.csv(row_df, out_csv, row.names = FALSE)
  }
}

for (color_info in colors_to_run) {
  for (env_var in env_vars) {
    key <- paste(color_info$label, env_var, sep = "___")
    if (key %in% done_keys) {
      message("  SKIP (done): ", key)
      next
    }
    if (!env_var %in% names(df)) {
      message("  SKIP (missing col): ", env_var)
      next
    }

    message("\n", strrep("─", 50))
    message("Single-var model: ", color_info$label, " ~ ", env_var)
    message(strrep("─", 50))

    formula_sv <- as.formula(paste(color_info$col, "~", env_var))
    set.seed(42)

    sv_model <- tryCatch({
      MCMCglmm(
        fixed   = formula_sv,
        random  = ~ genus,
        data    = df,
        family  = "threshold",
        prior   = PRIOR,
        nitt    = NITT,
        burnin  = BURNIN,
        thin    = THIN,
        verbose = TRUE
      )
    }, error = function(e) {
      message("ERROR: ", conditionMessage(e))
      NULL
    })

    if (!is.null(sv_model)) {
      sv_summary <- normalize_summary(
        as.data.frame(summary(sv_model)$solutions),
        env_var, color_info$label
      )
      append_result(sv_summary)
      done_keys <- c(done_keys, key)
      message("  Saved: ", key)
    }
  }
}

message("\nStep 06b complete. Output: ", out_csv)
