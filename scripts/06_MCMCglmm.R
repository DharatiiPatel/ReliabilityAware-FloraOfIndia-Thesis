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
# MCMCglmm on the primary analysis set (n=1,438).

.libPaths(c("~/R/library", .libPaths()))
options(stringsAsFactors = FALSE)
options(bitmapType = "cairo")

required_packages <- c("MCMCglmm", "ape", "coda")
for (pkg in required_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg, lib = "~/R/library", repos = "https://cloud.r-project.org")
  }
  library(pkg, character.only = TRUE)
}

# ECOLOGY_SET=clean reruns the historical n=1,174 set for the §1b comparison
# table. Default (unset / "primary") is the published n=1,438 analysis.
eco_set <- Sys.getenv("ECOLOGY_SET", "primary")
if (identical(eco_set, "clean")) {
  input_file <- file.path(base_dir, "Processed Data/experiments/step05b_outputs_clean/species_color_environment_final_clean.csv")
  output_dir <- file.path(base_dir, "Processed Data/experiments/step06_outputs_clean")
} else {
  input_file <- file.path(base_dir, "Processed Data/experiments/expansion/step05b_outputs/species_color_environment_final_expanded.csv")
  output_dir <- file.path(base_dir, "Processed Data/experiments/expansion/step06_outputs")
}
message("ECOLOGY_SET = ", eco_set)
fig_dir     <- file.path(output_dir, "figures")
dir_tables  <- file.path(output_dir, "tables")
dir_models  <- file.path(output_dir, "models")
dir_combined  <- file.path(dir_tables, "combined")
dir_fixed     <- file.path(dir_tables, "fixed_effects")
dir_converge  <- file.path(dir_tables, "convergence")
dir_random    <- file.path(dir_tables, "random_effects")

dir.create(fig_dir,       recursive = TRUE, showWarnings = FALSE)
dir.create(dir_combined,   recursive = TRUE, showWarnings = FALSE)
dir.create(dir_fixed,     recursive = TRUE, showWarnings = FALSE)
dir.create(dir_converge,  recursive = TRUE, showWarnings = FALSE)
dir.create(dir_random,    recursive = TRUE, showWarnings = FALSE)
dir.create(dir_models,    recursive = TRUE, showWarnings = FALSE)

NITT    <- 1050000   # total iterations
BURNIN  <- 50000     # burn-in
THIN    <- 100       # thinning interval
# Effective samples = (1050000 - 50000) / 100 = 10000

# MCMC_SMOKE=1 runs short chains to test I/O only. Do not use for reported results.
if (identical(Sys.getenv("MCMC_SMOKE", ""), "1")) {
  NITT <- 1300; BURNIN <- 300; THIN <- 10
  message("*** MCMC_SMOKE=1: short chains, results are NOT publishable ***")
}

PRIOR <- list(
  R = list(V = 1, fix = 1), #prior for the residual variance. in binary threshold models rv is not identifiable from data so we fixed it to 1.
  G = list(G1 = list(V = 1, nu = 0.002)) #prior for the random effect variance.
)

message("Loading data: ", input_file)
df <- read.csv(input_file, encoding = "UTF-8")

message("Total species: ", nrow(df)) #number of rows in df.
message("Colour breakdown:") #print the number of species in each color group.
print(table(df$color_group))

# Check required columns
pc_cols <- paste0("PC", 1:10) #create a vector of the first 10 pcs.
missing <- setdiff(c(pc_cols, "is_white", "is_yellow", "is_redtype", "query_name"), names(df))
if (length(missing) > 0) {
  stop("Missing columns: ", paste(missing, collapse = ", "))
}

# Extract genus from query_name for random effects
df$genus  <- sapply(strsplit(df$query_name, " "), function(x) x[1]) #sapply splits the query_name column by spaces and then takes the first element of the split.

#run MCMCglmm for one colour
run_mcmc_model <- function(data, response_col, label, random_formula = "~ genus") {

  message("\n", strrep("─", 60))
  message("Running MCMCglmm for: ", label)
  message(strrep("─", 60))

  # Build formula
  fixed_formula  <- as.formula(paste(response_col, "~", paste(pc_cols, collapse = " + "))) #.formula converts the string to a formula object because the MCMCglmm function expects a formula object and not string
  random_formula <- as.formula(random_formula)

  message("Fixed formula: ", deparse(fixed_formula)) #deparse converts the formula object to a string.
  message("N species: ", nrow(data))
  message("N positive: ", sum(data[[response_col]]))

  set.seed(42) #set the seed to 42 so that the results are reproducible.

  model <- tryCatch({
    MCMCglmm(
      fixed   = fixed_formula,
      random  = random_formula, #This tells the model that observations from the same genus are correlated. The model will estimate a variance component for genus how much of the variation in flower colour is explained by genus membership alone.
      data    = data,
      family  = "threshold", 
      prior   = PRIOR,
      nitt    = NITT,
      burnin  = BURNIN,
      thin    = THIN,
      verbose = TRUE #print progress to the console.
    )
  }, error = function(e) {
    message("ERROR in MCMCglmm: ", conditionMessage(e))
    return(NULL)
  })

  return(model)
}

#extract and save results 
save_model_results <- function(model, label, output_dir) {

  if (is.null(model)) {
    message("Skipping results for ", label, " - model failed")
    return(NULL)
  }

  # Fixed effects summary
  fixed_summary <- summary(model)$solutions
  fixed_df <- as.data.frame(fixed_summary)
  fixed_df$variable <- rownames(fixed_df)
  fixed_df$color    <- label

  out_fixed <- file.path(dir_fixed, paste0("fixed_effects_", label, ".csv"))
  write.csv(fixed_df, out_fixed, row.names = FALSE)
  message("Saved fixed effects: ", out_fixed)

  # Random effect variance
  rand_summary <- summary(model)$Gcovariances
  rand_df <- as.data.frame(rand_summary)
  rand_df$color <- label

  out_rand <- file.path(dir_random, paste0("random_effects_", label, ".csv"))
  write.csv(rand_df, out_rand, row.names = FALSE)

  # Gelman-Rubin convergence (need multiple chains - run 3 chains)
  message("Checking convergence for ", label, "...")

  # Run 2 more chains for Gelman-Rubin
  set.seed(123)
  model2 <- tryCatch({
    MCMCglmm(
      fixed   = model$Fixed$formula,
      random  = model$Random$formula,
      data    = df,
      family  = "threshold",
      prior   = PRIOR,
      nitt    = NITT,
      burnin  = BURNIN,
      thin    = THIN,
      verbose = FALSE
    )
  }, error = function(e) NULL)

  set.seed(456)
  model3 <- tryCatch({
    MCMCglmm(
      fixed   = model$Fixed$formula,
      random  = model$Random$formula,
      data    = df,
      family  = "threshold",
      prior   = PRIOR,
      nitt    = NITT,
      burnin  = BURNIN,
      thin    = THIN,
      verbose = FALSE
    )
  }, error = function(e) NULL)

  if (!is.null(model2) && !is.null(model3)) { #Sol extracts the MCMC samples of the fixed effects (the posterior chains). mcmc.list wraps them into a coda object for convergence analysis.
    chains <- mcmc.list(model$Sol, model2$Sol, model3$Sol)
    gr     <- gelman.diag(chains, multivariate = TRUE)

    gr_df <- data.frame(
      variable = rownames(gr$psrf),
      point_est = gr$psrf[, 1],
      upper_CI  = gr$psrf[, 2],
      mpsrf     = gr$mpsrf,
      color     = label
    )

    out_gr <- file.path(dir_converge, paste0("gelman_rubin_", label, ".csv"))
    write.csv(gr_df, out_gr, row.names = FALSE)
    message("MPSRF for ", label, ": ", round(gr$mpsrf, 6))
  }

  # Save trace plots
  png(file.path(fig_dir, paste0("trace_", label, ".png")),
      width = 1200, height = 800)
  plot(model$Sol[, 1:min(6, ncol(model$Sol))])
  dev.off()

  return(fixed_df)
}

colors_to_run <- list(
  list(col = "is_white",   label = "WHITE"),
  list(col = "is_yellow",  label = "YELLOW"),
  list(col = "is_redtype", label = "REDTYPE")
)

all_fixed_effects <- list()

for (color_info in colors_to_run) {

  model <- run_mcmc_model(
    data           = df,
    response_col   = color_info$col,
    label          = color_info$label,
    random_formula = "~ genus"
  )

  results <- save_model_results(model, color_info$label, output_dir)
  if (!is.null(results)) {
    all_fixed_effects[[color_info$label]] <- results
  }

  # Save model object
  model_file <- file.path(dir_models, paste0("model_", color_info$label, ".rds"))
  saveRDS(model, model_file)
  message("Saved model: ", model_file)
}

#Combine all fixed effects 
if (length(all_fixed_effects) > 0) {
  combined_effects <- do.call(rbind, all_fixed_effects)
  combined_path <- file.path(dir_combined, "all_fixed_effects_combined.csv")
  write.csv(combined_effects, combined_path, row.names = FALSE)
  message("\nSaved combined fixed effects table")
}

# Single-variable models: run scripts/06b_SingleVariable_MCMCglmm.R (not here)

#generate coefficient plot 
message("\nGenerating coefficient plots...")

if (length(all_fixed_effects) > 0) {

  combined <- do.call(rbind, all_fixed_effects)
  combined <- combined[combined$variable != "(Intercept)", ]

  # Rename columns if needed
  names(combined)[names(combined) == "post.mean"] <- "mean"
  names(combined)[names(combined) == "l-95% CI"]  <- "lower"
  names(combined)[names(combined) == "u-95% CI"]  <- "upper"

  # Mark significant (CI doesn't overlap zero)
  combined$significant <- (combined$lower > 0 | combined$upper < 0)

  png(file.path(fig_dir, "coefficient_plot_PC1_PC3.png"),
      width = 1200, height = 600)

  par(mfrow = c(1, 3), mar = c(5, 4, 3, 1)) #mfrow sets the layout of the plot. mar sets the margins.

  for (col_label in c("WHITE", "YELLOW", "REDTYPE")) {

    sub <- combined[combined$color == col_label &
                    combined$variable %in% c("PC1", "PC2", "PC3"), ]

    if (nrow(sub) == 0) next

    ylim <- range(c(sub$lower, sub$upper), na.rm = TRUE) #range finds the minimum and maximum values of the lower and upper confidence intervals. na.rm = TRUE removes any NA values.

    plot(1:nrow(sub), sub$mean,
         ylim   = ylim,
         xaxt   = "n",
         xlab   = "",
         ylab   = "Coefficient",
         main   = col_label,
         pch    = 19, #pch sets the shape of the points.
         col    = ifelse(sub$significant, "black", "grey60"),
         cex    = 1.5)

    axis(1, at = 1:nrow(sub), labels = sub$variable, las = 2)
    abline(h = 0, lty = 2, col = "red")

    arrows(1:nrow(sub), sub$lower,
           1:nrow(sub), sub$upper,
           angle  = 90,
           code   = 3,
           length = 0.05,
           col    = ifelse(sub$significant, "black", "grey60"))
  }

  dev.off()
  message("Saved coefficient plot")
}

message("\n Step 06 Complete ")
message("Results saved to: ", output_dir)
message("Figures saved to: ", fig_dir)
