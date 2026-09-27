#!/bin/bash
# Regression audit of every number cited in docs/VERIFIED_Numbers_for_Thesis.md.
# Cheap and read-only, so it is safe to run any time. Submit with a dependency to
# have it fire automatically once reruns land, e.g.:
#   sbatch --dependency=afterany:<job1>:<job2> scripts/slurm/run_27_audit.slurm
#SBATCH --job-name=audit_numbers
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=/scratch/dp23301/Thesis/logs/audit_numbers_%j.out
#SBATCH --error=/scratch/dp23301/Thesis/logs/audit_numbers_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=dp23301@uga.edu

cd /scratch/dp23301/Thesis
mkdir -p logs

# Report file is easier to read than the SLURM log.
REPORT="logs/audit_report_$(date +%Y%m%d_%H%M%S).txt"
python3 scripts/27_Audit_All_Numbers.py 2>&1 | tee "$REPORT"
STATUS=${PIPESTATUS[0]}

echo "" | tee -a "$REPORT"
echo "audit exit status: $STATUS" | tee -a "$REPORT"
if [ "$STATUS" -ne 0 ]; then
  echo "FAILURES PRESENT — see report above before citing any affected number." | tee -a "$REPORT"
fi
echo "report written to: $REPORT"
exit "$STATUS"
