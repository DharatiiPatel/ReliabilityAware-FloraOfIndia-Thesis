#!/usr/bin/env python3
"""Path-isolation tests for portable package / repository roots.

Fails if non-Slurm analysis scripts hard-code the Sapelo checkout, or if
script 14 / the numerical audit can silently load categorisers from another tree.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH_LITERAL = "/scratch/dp23301/Thesis"
SCRIPTS = ROOT / "scripts"


def _non_slurm_script_files() -> list[Path]:
    files: list[Path] = []
    for path in SCRIPTS.rglob("*"):
        if not path.is_file():
            continue
        if "slurm" in path.parts:
            continue
        if path.suffix.lower() in {".py", ".r"}:
            files.append(path)
    return sorted(files)


class ProjectRootIsolationTests(unittest.TestCase):
    def test_no_hardcoded_scratch_in_non_slurm_scripts(self):
        offenders = []
        for path in _non_slurm_script_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            if SCRATCH_LITERAL in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(
            offenders,
            [],
            "non-Slurm scripts must not hard-code " + SCRATCH_LITERAL,
        )

    def test_script14_base_and_v1_inside_package_when_thesis_root_unset(self):
        env = os.environ.copy()
        env.pop("THESIS_ROOT", None)
        env.pop("THESIS_BASE", None)
        # Import a fresh module object from the local scripts/14 file.
        path = SCRIPTS / "14_Categorize_v2.py"
        spec = importlib.util.spec_from_file_location("cat_v2_isolation", path)
        mod = importlib.util.module_from_spec(spec)
        # Ensure import uses this process env without THESIS_ROOT.
        old = os.environ.pop("THESIS_ROOT", None)
        try:
            sys.modules.pop("cat_v2_isolation", None)
            spec.loader.exec_module(mod)
        finally:
            if old is not None:
                os.environ["THESIS_ROOT"] = old
        self.assertEqual(Path(mod.BASE).resolve(), ROOT.resolve())
        self.assertEqual(
            Path(mod.V1_SOURCE).resolve(),
            (ROOT / "scripts" / "03_04_Categorize_and_Prepare.py").resolve(),
        )
        self.assertTrue(str(Path(mod.V1_SOURCE).resolve()).startswith(str(ROOT.resolve())))
        self.assertEqual(mod.categorize_v1("flowers white"), "WHITE")

    def test_thesis_root_override_changes_script14_base(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td).resolve()
            (fake / "scripts").mkdir()
            # Script 14 inserts BASE/scripts on sys.path and imports lib.*.
            os.symlink(SCRIPTS / "lib", fake / "scripts" / "lib")
            env = os.environ.copy()
            env["THESIS_ROOT"] = str(fake)
            code = (
                "import importlib.util\n"
                f"spec = importlib.util.spec_from_file_location('c14', {str(SCRIPTS / '14_Categorize_v2.py')!r})\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                "print(mod.BASE)\n"
                "print(mod.V1_SOURCE)\n"
            )
            proc = subprocess.run(
                [sys.executable, "-c", code],
                env=env,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
            self.assertGreaterEqual(len(lines), 2, msg=proc.stderr)
            self.assertEqual(Path(lines[0]).resolve(), fake)
            self.assertEqual(
                Path(lines[1]).resolve(),
                (fake / "scripts" / "03_04_Categorize_and_Prepare.py").resolve(),
            )

    def test_audit_imports_v1_v2_only_from_current_root(self):
        """Script 27 loads V2 from ROOT/scripts/14; V1 via that module's V1_SOURCE."""
        env = os.environ.copy()
        env.pop("THESIS_ROOT", None)
        env.pop("THESIS_BASE", None)
        code = (
            "import importlib.util\n"
            "from pathlib import Path\n"
            f"root = Path({str(ROOT)!r}).resolve()\n"
            "audit = root / 'scripts' / '27_Audit_All_Numbers.py'\n"
            "text = audit.read_text()\n"
            "assert '/scratch/dp23301/Thesis' not in text\n"
            "spec = importlib.util.spec_from_file_location(\n"
            "    'c2', root / 'scripts' / '14_Categorize_v2.py')\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "assert Path(mod.BASE).resolve() == root\n"
            "assert Path(mod.V1_SOURCE).resolve().is_relative_to(root)\n"
            "assert '03_04_Categorize_and_Prepare.py' in str(mod.V1_SOURCE)\n"
            "print('OK', mod.BASE, mod.V1_SOURCE)\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("OK", proc.stdout)
        # When the current checkout lives at the Sapelo path, that string will
        # appear in BASE; the invariant is that BASE equals THIS package root.
        base_line = proc.stdout.strip().splitlines()[-1]
        parts = base_line.split()
        self.assertGreaterEqual(len(parts), 3)
        self.assertEqual(Path(parts[1]).resolve(), ROOT.resolve())
        self.assertTrue(str(Path(parts[2]).resolve()).startswith(str(ROOT.resolve()) + "/"))
        self.assertTrue(Path(parts[2]).name == "03_04_Categorize_and_Prepare.py")


if __name__ == "__main__":
    unittest.main()
