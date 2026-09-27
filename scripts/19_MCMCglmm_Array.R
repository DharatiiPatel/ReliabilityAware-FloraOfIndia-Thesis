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
# One MCMCglmm task (source x colour x chain) from the label-sensitivity manifest.
# MCMC settings match scripts/06_MCMCglmm.R.
# Saves Sol draws plus embedded provenance (no sidecar files).

.libPaths(c("~/R/library", .libPaths()))
options(stringsAsFactors = FALSE)

suppressMessages({
  library(MCMCglmm)
})

VARDIR <- Sys.getenv(
  "LABEL_SENSITIVITY_DIR",
  unset = file.path(BASE, "Processed Data/experiments/label_sensitivity")
)
MANIFEST <- file.path(VARDIR, "mcmc_manifest.csv")
OUTDIR <- file.path(VARDIR, "mcmc_chains")
dir.create(OUTDIR, recursive = TRUE, showWarnings = FALSE)

NITT_REQ   <- 1050000L
BURNIN_REQ <- 50000L
THIN_REQ   <- 100L
PRIOR <- list(
  R = list(V = 1, fix = 1),
  G = list(G1 = list(V = 1, nu = 0.002))
)
PC_COLS <- paste0("PC", 1:10)

tid <- Sys.getenv("SLURM_ARRAY_TASK_ID", unset = NA)
if (is.na(tid)) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) >= 1) tid <- args[1] else stop("No SLURM_ARRAY_TASK_ID / arg")
}
tid <- as.integer(tid)

man <- read.csv(MANIFEST, stringsAsFactors = FALSE)
row <- man[man$task_id == tid, , drop = FALSE]
if (nrow(row) != 1) stop("task_id ", tid, " not found in manifest")

if (!identical(as.character(row$cohort[[1]]), "llm_common")) {
  stop("main array only accepts llm_common; got cohort=", row$cohort[[1]])
}
if (identical(as.character(row$variant[[1]]), "baseline")) {
  stop("baseline is not part of the main label-sensitivity matrix")
}
if (grepl("wp4_label_variants", row$dataset_path[[1]], fixed = TRUE)) {
  stop("prohibited legacy path in manifest: wp4_label_variants")
}

variant  <- as.character(row$variant[[1]])
dataset  <- as.character(row$dataset_path[[1]])
response <- as.character(row$response_col[[1]])
color    <- as.character(row$color_label[[1]])
chain    <- as.integer(row$chain[[1]])
seed     <- as.integer(row$seed[[1]])
stem     <- as.character(row$chain_stem[[1]])
dataset_sha <- as.character(row$dataset_sha256[[1]])
cat_sha     <- as.character(row$categorizer_sha256[[1]])
n_man       <- as.integer(row$n[[1]])
pos_man     <- as.integer(row$positive_n[[1]])
nitt   <- if ("nitt" %in% names(row)) as.integer(row$nitt[[1]]) else NITT_REQ
burnin <- if ("burnin" %in% names(row)) as.integer(row$burnin[[1]]) else BURNIN_REQ
thin   <- if ("thin" %in% names(row)) as.integer(row$thin[[1]]) else THIN_REQ

if (!identical(nitt, NITT_REQ) || !identical(burnin, BURNIN_REQ) ||
    !identical(thin, THIN_REQ)) {
  stop("manifest MCMC settings must be nitt=1050000, burnin=50000, thin=100")
}

expected_output <- if ("expected_output" %in% names(row) &&
                       nzchar(as.character(row$expected_output[[1]]))) {
  as.character(row$expected_output[[1]])
} else {
  file.path(OUTDIR, paste0(stem, ".rds"))
}

message(sprintf(
  "TASK %d | variant=%s colour=%s chain=%d seed=%d stem=%s",
  tid, variant, color, chain, seed, stem))

# Verify on-disk dataset matches the manifest checksum (no silent mix of old inputs)
sha256_file <- function(path) {
  dig <- tryCatch(
    system2("sha256sum", args = shQuote(path), stdout = TRUE, stderr = TRUE),
    error = function(e) character(0)
  )
  if (!length(dig)) stop("failed to hash dataset: ", path)
  sub(" .*", "", dig[[1]])
}
actual_sha <- sha256_file(dataset)
if (!identical(actual_sha, dataset_sha)) {
  stop(sprintf(
    "dataset SHA-256 mismatch for %s\n  on-disk=%s\n  manifest=%s",
    dataset, actual_sha, dataset_sha))
}

df <- read.csv(dataset, encoding = "UTF-8")
df$genus <- sapply(strsplit(df$query_name, " "), function(x) x[[1]])
n <- nrow(df)
positive_n <- sum(df[[response]])
if (!identical(n, n_man) || !identical(as.integer(positive_n), pos_man)) {
  stop(sprintf(
    "n/positive_n mismatch vs manifest: data n=%d pos=%d; manifest n=%d pos=%d",
    n, positive_n, n_man, pos_man))
}

fixed_formula <- as.formula(paste(response, "~", paste(PC_COLS, collapse = " + ")))
message("N species: ", n, " | N positive: ", positive_n)

set.seed(seed)
model <- MCMCglmm(
  fixed  = fixed_formula,
  random = ~ genus,
  data   = df,
  family = "threshold",
  prior  = PRIOR,
  nitt   = nitt, burnin = burnin, thin = thin,
  verbose = FALSE
)

payload <- list(
  Sol = model$Sol,
  provenance = list(
    variant = variant,
    color_label = color,
    chain = chain,
    seed = seed,
    dataset_path = dataset,
    dataset_sha256 = dataset_sha,
    categorizer_sha256 = cat_sha,
    n = n,
    positive_n = as.integer(positive_n),
    nitt = nitt,
    burnin = burnin,
    thin = thin,
    response_col = response,
    chain_stem = stem,
    created_utc = format(as.POSIXct(Sys.time(), tz = "UTC"),
                         "%Y-%m-%dT%H:%M:%SZ")
  )
)

saveRDS(payload, expected_output)
message("Saved: ", expected_output)
