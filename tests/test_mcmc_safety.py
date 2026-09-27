#!/usr/bin/env python3
"""Concise MCMC safety tests (no real MCMCglmm fits).

Run:
  python tests/test_mcmc_safety.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ["THESIS_ROOT"]).resolve() if os.environ.get("THESIS_ROOT") else Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
VARDIR = ROOT / "Processed Data" / "experiments" / "label_sensitivity"
MANIFEST = VARDIR / "mcmc_manifest.csv"
CATEGORISER = SCRIPTS / "lib" / "colour_categoriser.py"

EXPECTED_VARIANTS = {"qwen7b", "qwen72b", "llama70b"}
EXPECTED_TASKS = 27
CAT_SHA = (
    "0fe312ceb5ac3917ebcc7a1b6b6dbe7b40ac82e6509f71967933af0714b2d9df"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


class ManifestSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Regenerate canonical main manifest (no MCMC)
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "18_Make_MCMC_Manifest.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode != 0:
            raise RuntimeError(f"script 18 failed:\n{r.stdout}\n{r.stderr}")
        cls.rows = read_manifest(MANIFEST)

    def test_exactly_27_tasks(self) -> None:
        self.assertEqual(len(self.rows), EXPECTED_TASKS)

    def test_variants_only_three_llms(self) -> None:
        variants = {r["variant"] for r in self.rows}
        self.assertEqual(variants, EXPECTED_VARIANTS)

    def test_no_baseline_or_four_source(self) -> None:
        joined = "\n".join(
            f"{r['variant']}|{r['dataset_path']}|{r.get('cohort','')}"
            for r in self.rows
        )
        self.assertNotIn("baseline", joined)
        self.assertNotIn("four_source", joined)

    def test_no_obsolete_wp4_paths(self) -> None:
        for r in self.rows:
            self.assertNotIn("wp4_label_variants", r["dataset_path"])
            self.assertIn(
                "Processed Data/experiments/label_sensitivity/",
                r["dataset_path"],
            )
            self.assertNotIn("/secondary/", r["dataset_path"])

    def test_provenance_columns_present(self) -> None:
        required = {
            "dataset_sha256",
            "categorizer_sha256",
            "n",
            "positive_n",
            "seed",
            "nitt",
            "burnin",
            "thin",
            "expected_output",
        }
        self.assertTrue(required.issubset(self.rows[0].keys()))

    def test_n_and_hashes(self) -> None:
        for r in self.rows:
            self.assertEqual(int(r["n"]), 1149)
            self.assertEqual(r["categorizer_sha256"], CAT_SHA)
            self.assertEqual(r["nitt"], "1050000")
            self.assertEqual(r["burnin"], "50000")
            self.assertEqual(r["thin"], "100")
        # on-disk categoriser matches stamped hash
        self.assertEqual(sha256_file(CATEGORISER), CAT_SHA)


def _find_rscript() -> str | None:
    env = os.environ.get("RSCRIPT")
    if env and Path(env).exists():
        return env
    which = shutil.which("Rscript")
    if which:
        return which
    for cand in (
        "/apps/eb/R/4.5.1-gfbf-2025a/bin/Rscript",
        "/apps/eb/software/R/4.5.1-gfbf-2025a/bin/Rscript",
    ):
        if Path(cand).exists():
            return cand
    return None


RSCRIPT = _find_rscript()


def _write_mock_chain(
    path: Path,
    *,
    variant: str,
    color: str,
    chain: int,
    seed: int,
    dataset_sha: str,
    cat_sha: str,
    n: int = 1149,
    positive_n: int = 400,
    nitt: int = 1050000,
    burnin: int = 50000,
    thin: int = 100,
    shift: float = 0.0,
) -> None:
    """Write a tiny Sol+provenance RDS via R (no MCMCglmm)."""
    if RSCRIPT is None:
        raise RuntimeError("Rscript not available")
    path.parent.mkdir(parents=True, exist_ok=True)
    r_code = f"""
    suppressMessages(library(coda))
    set.seed({seed + int(shift * 1000)})
    sol <- coda::mcmc(cbind(
      `(Intercept)` = rnorm(40, {shift}, 0.05),
      PC1 = rnorm(40, 0, 0.05),
      PC2 = rnorm(40, 0, 0.05)
    ))
    payload <- list(
      Sol = sol,
      provenance = list(
        variant = "{variant}",
        color_label = "{color}",
        chain = {chain}L,
        seed = {seed}L,
        dataset_path = "mock.csv",
        dataset_sha256 = "{dataset_sha}",
        categorizer_sha256 = "{cat_sha}",
        n = {n}L,
        positive_n = {positive_n}L,
        nitt = {nitt}L,
        burnin = {burnin}L,
        thin = {thin}L,
        created_utc = "2026-01-01T00:00:00Z"
      )
    )
    saveRDS(payload, "{path.as_posix()}")
    """
    r = subprocess.run(
        [RSCRIPT, "-e", r_code],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(f"mock chain write failed: {r.stderr}")


def _build_mock_workspace(
    tmp: Path,
    *,
    dataset_sha: str = "a" * 64,
    cat_sha: str = CAT_SHA,
    n_tasks: int = 27,
    drop_one: bool = False,
    bad_dataset_sha_for: str | None = None,
    bad_cat_sha_for: str | None = None,
    force_nonconverged: bool = False,
) -> Path:
    """Build a temp LABEL_SENSITIVITY_DIR with manifest + mock chains."""
    chaindir = tmp / "mcmc_chains"
    resdir = tmp / "results"
    chaindir.mkdir(parents=True)
    resdir.mkdir(parents=True)

    sentinel_fx = resdir / "label_sensitivity_effects.csv"
    sentinel_cv = resdir / "label_sensitivity_convergence.csv"
    sentinel_fx.write_text("SENTINEL_EFFECTS\n", encoding="utf-8")
    sentinel_cv.write_text("SENTINEL_CONV\n", encoding="utf-8")

    variants = ["qwen7b", "qwen72b", "llama70b"]
    colors = ["WHITE", "YELLOW", "REDTYPE"]
    seeds = {1: 42, 2: 123, 3: 456}
    rows = []
    tid = 0
    for variant in variants:
        for color in colors:
            for chain, seed in seeds.items():
                stem = f"{variant}_{color}_chain{chain}"
                out = chaindir / f"{stem}.rds"
                key = f"{variant}|{color}|{chain}"
                shift = 10.0 if force_nonconverged and chain == 3 else 0.0
                if not (drop_one and tid == 0):
                    chain_ds = ("b" * 64) if bad_dataset_sha_for == key else dataset_sha
                    chain_cat = ("c" * 64) if bad_cat_sha_for == key else cat_sha
                    _write_mock_chain(
                        out,
                        variant=variant,
                        color=color,
                        chain=chain,
                        seed=seed,
                        dataset_sha=chain_ds,
                        cat_sha=chain_cat,
                        shift=shift,
                    )
                rows.append(
                    dict(
                        task_id=tid,
                        cohort="llm_common",
                        variant=variant,
                        dataset_path=str(
                            tmp / f"species_color_environment_{variant}.csv"
                        ),
                        dataset_sha256=dataset_sha,
                        categorizer_sha256=cat_sha,
                        n=1149,
                        n_species=1149,
                        positive_n=400,
                        color_label=color,
                        response_col=f"is_{color.lower()}",
                        chain=chain,
                        seed=seed,
                        nitt=1050000,
                        burnin=50000,
                        thin=100,
                        chain_stem=stem,
                        expected_output=str(out),
                    )
                )
                tid += 1
                if tid >= n_tasks:
                    break
            if tid >= n_tasks:
                break
        if tid >= n_tasks:
            break

    man = tmp / "mcmc_manifest.csv"
    with man.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return tmp


def _run_combine(tmpdir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["LABEL_SENSITIVITY_DIR"] = str(tmpdir)
    env["THESIS_BASE"] = str(ROOT)
    # Ensure user R library (coda) is visible
    env.setdefault("R_LIBS_USER", str(Path.home() / "R" / "library"))
    return subprocess.run(
        [RSCRIPT or "Rscript", str(SCRIPTS / "20_Combine_Label_Results.R")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@unittest.skipUnless(RSCRIPT is not None, "Rscript not available")
class CombineRejectionTests(unittest.TestCase):
    def test_missing_chain_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mcmc_miss_") as td:
            tmp = _build_mock_workspace(Path(td), drop_one=True)
            r = _run_combine(tmp)
            self.assertNotEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertTrue(
                (tmp / "results" / "label_sensitivity_effects.csv")
                .read_text(encoding="utf-8")
                .startswith("SENTINEL")
            )

    def test_dataset_checksum_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mcmc_dsha_") as td:
            tmp = _build_mock_workspace(
                Path(td),
                bad_dataset_sha_for="qwen7b|WHITE|1",
            )
            r = _run_combine(tmp)
            self.assertNotEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("provenance mismatch", (r.stdout + r.stderr).lower())
            self.assertTrue(
                (tmp / "results" / "label_sensitivity_effects.csv")
                .read_text(encoding="utf-8")
                .startswith("SENTINEL")
            )

    def test_categorizer_checksum_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mcmc_csha_") as td:
            tmp = _build_mock_workspace(
                Path(td),
                bad_cat_sha_for="qwen7b|WHITE|1",
            )
            r = _run_combine(tmp)
            self.assertNotEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("provenance mismatch", (r.stdout + r.stderr).lower())
            self.assertTrue(
                (tmp / "results" / "label_sensitivity_effects.csv")
                .read_text(encoding="utf-8")
                .startswith("SENTINEL")
            )

    def test_nonconvergence_preserves_canonical_tables(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mcmc_conv_") as td:
            tmp = _build_mock_workspace(Path(td), force_nonconverged=True)
            r = _run_combine(tmp)
            # Either gelman fails finite/threshold → nonzero, and sentinel remains
            self.assertNotEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            fx = (tmp / "results" / "label_sensitivity_effects.csv").read_text(
                encoding="utf-8"
            )
            self.assertTrue(
                fx.startswith("SENTINEL"),
                msg="canonical effects must not be replaced on convergence failure",
            )


class AtomicPublishTests(unittest.TestCase):
    """Publication helpers must be destination-local temp+rename, not bare copy."""

    def _assert_atomic_helper(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        self.assertIn("atomic_publish", text)
        self.assertIn("tmpdir = dest_dir", text)
        self.assertIn("file.rename(tmp, dest)", text)
        # Must not treat a lone cross-filesystem copy as the publish step.
        self.assertNotRegex(
            text,
            r"atomic_publish\s*<-\s*function\(src,\s*dest\)\s*\{\s*"
            r"(?:ok\s*<-\s*file\.rename\(src,\s*dest\).*?)?"
            r"if\s*\(!file\.copy\(src,\s*dest",
            msg=f"{path.name}: direct file.copy(src, dest) publish is not atomic",
        )

    def test_elevation_atomic_publish(self) -> None:
        self._assert_atomic_helper(SCRIPTS / "08_ElevationGradient_Analysis.R")

    def test_label_combine_atomic_publish(self) -> None:
        self._assert_atomic_helper(SCRIPTS / "20_Combine_Label_Results.R")

    def test_reliability_atomic_publish_and_staging(self) -> None:
        text = (SCRIPTS / "25_Reliability_Ecology.R").read_text(encoding="utf-8")
        self._assert_atomic_helper(SCRIPTS / "25_Reliability_Ecology.R")
        self.assertIn("stage_dir", text)
        self.assertIn("make_chain_payload", text)
        self.assertIn("provenance", text)
        # Models/chains must not write straight to out_dir before the gate.
        self.assertNotIn(
            'saveRDS(ms[[1]], file.path(out_dir, sprintf("model_%s.rds", tag)))',
            text,
        )

    def test_future_payload_fields_documented(self) -> None:
        text = (SCRIPTS / "25_Reliability_Ecology.R").read_text(encoding="utf-8")
        for key in (
            "subset", "outcome", "dataset_sha256", "categorizer_sha256",
            "n", "positive_n", "nitt", "burnin", "thin", "created_utc",
            "analysis_script_sha256",
        ):
            self.assertIn(key, text)


class ReliabilityGateTests(unittest.TestCase):
    def test_script_requires_full_flag_text(self) -> None:
        text = (SCRIPTS / "25_Reliability_Ecology.R").read_text(encoding="utf-8")
        self.assertIn('RELIABILITY_FULL', text)
        self.assertIn("required for publishable", text)
        self.assertIn("canonical tables not replaced", text)
        self.assertIn("mcmc_run", text)
        self.assertIn("HPDinterval", text)
        self.assertIn("chain_storage_note", text)


class HPDImplementationTests(unittest.TestCase):
    def test_combine_uses_hpd_not_quantiles(self) -> None:
        text = (SCRIPTS / "20_Combine_Label_Results.R").read_text(encoding="utf-8")
        self.assertIn("HPDinterval", text)
        self.assertIn('interval = "HPD95"', text)
        self.assertIn("effectiveSize", text)
        self.assertNotIn("quantile(x, 0.025)", text)
        self.assertIn("MPSRF_MAX <- 1.01", text)
        self.assertIn("quit(status = 1)", text)


class ElevationSafetyTests(unittest.TestCase):
    """Static / structural gates for hardened primary elevation (script 08)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (SCRIPTS / "08_ElevationGradient_Analysis.R").read_text(
            encoding="utf-8"
        )

    def test_three_seeds_and_settings(self) -> None:
        self.assertIn("CHAIN_SEEDS <- c(42L, 123L, 456L)", self.text)
        self.assertIn("NITT   <- 1050000L", self.text)
        self.assertIn("BURNIN <- 50000L", self.text)
        self.assertIn("THIN   <- 100L", self.text)
        self.assertIn("MPSRF_MAX <- 1.01", self.text)

    def test_hash_and_provenance_required(self) -> None:
        self.assertIn("sha256_file", self.text)
        self.assertIn("expected_pca_sha", self.text)
        self.assertIn("9d1e0f03fe774a7fcb19815a91341b8b55bdc79d133a2a9359a3d32967938280", self.text)
        self.assertIn("historical_primary_V1", self.text)
        self.assertIn("chains_elev_", self.text)
        self.assertIn("elevation_convergence.csv", self.text)
        self.assertIn("HPDinterval", self.text)

    def test_hard_fail_paths(self) -> None:
        self.assertIn("failed convergence gate", self.text)
        self.assertIn("canonical outputs not replaced", self.text)
        self.assertIn("quit(status = 1)", self.text)
        self.assertIn("PCA dataset SHA mismatch", self.text)
        self.assertIn("non-finite convergence diagnostics", self.text)

    def test_no_skip_when_csv_exists_for_full_run(self) -> None:
        # Full runs must not short-circuit on existing CSV (old behaviour).
        self.assertNotIn(
            'else if (file.exists(elev_csv)) {\n  message("Skipping MCMC',
            self.text,
        )
        self.assertIn("SKIP_ELEV_MCMC", self.text)

    def test_canonical_input_paths(self) -> None:
        self.assertIn(
            "species_color_environment_final_expanded.csv", self.text
        )
        self.assertIn("species_environment_trimmed.csv", self.text)
        self.assertNotIn("wp4", self.text.lower())
        self.assertNotIn("corrected_v2", self.text)
        self.assertNotIn("v2_fixed_cohort", self.text)

    def test_gate_rejects_bad_diagnostics_logic(self) -> None:
        # Mirror the script's gate in pure Python.
        def gate(mpsrf: float, max_psrf: float, threshold: float = 1.01) -> bool:
            import math
            if not (math.isfinite(mpsrf) and math.isfinite(max_psrf)):
                return False
            return mpsrf < threshold and max_psrf < threshold

        self.assertTrue(gate(1.0003, 1.0002))
        self.assertFalse(gate(1.01, 1.0001))
        self.assertFalse(gate(1.0001, 1.02))
        self.assertFalse(gate(float("nan"), 1.0))
        self.assertFalse(gate(1.0, float("inf")))

    def test_expected_hash_constant_matches_disk(self) -> None:
        pca = (
            ROOT
            / "Processed Data/experiments/expansion/step05b_outputs"
            / "species_color_environment_final_expanded.csv"
        )
        self.assertTrue(pca.exists())
        self.assertEqual(sha256_file(pca), (
            "9d1e0f03fe774a7fcb19815a91341b8b55bdc79d133a2a9359a3d32967938280"
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
