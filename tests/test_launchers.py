from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_windows_repairs_then_syncs_once_and_runs_without_resync(self):
        launcher = (ROOT / "run-windows.bat").read_text(encoding="utf-8")

        repair = 'scripts\\repair_project_venv.py --venv .venv'
        sync = 'uv sync --python "%PYTHON_EXE%"'
        run = 'uv run --no-sync --python "%PYTHON_EXE%" python src/app.py'

        self.assertIn("uv python find --no-project --managed-python", launcher)
        self.assertEqual(launcher.count(sync), 1)
        self.assertLess(launcher.index(repair), launcher.index(sync))
        self.assertLess(launcher.index(sync), launcher.index(run))

    def test_macos_repairs_then_syncs_once_and_runs_without_resync(self):
        launcher = (ROOT / "run-macos.command").read_text(encoding="utf-8")

        repair = "scripts/repair_project_venv.py --venv .venv"
        sync = 'uv sync --python "$PYTHON_BIN"'
        run = 'uv run --no-sync --python "$PYTHON_BIN" python src/app.py'

        self.assertEqual(launcher.count(sync), 1)
        self.assertLess(launcher.index(repair), launcher.index(sync))
        self.assertLess(launcher.index(sync), launcher.index(run))


if __name__ == "__main__":
    unittest.main()
