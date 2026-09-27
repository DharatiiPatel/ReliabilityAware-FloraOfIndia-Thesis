# Cluster jobs

Submit from the thesis root:

```bash
cd /scratch/dp23301/Thesis
sbatch scripts/slurm/<name>.slurm
```

| Jobs | Scripts they run |
|------|------------------|
| `run_02` | colour extraction |
| `run_04*` | fascicles and recovery |
| `run_05a` `run_05b` `run_06` `run_06b` `run_07` `run_08` | GBIF, environment, models, figures |
| `run_11_*` `run_15_rag` `run_19_array` | gold-set models, RAG, label-sensitivity MCMC |
| `run_25_reliability_ecology` | confidence-stratified ecology (full MCMC) + figures |
| `submit_full_dataset.sh` | fascicles + recovery, then GBIF / models / figures |
