from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_workflows_pin_resolvable_action_release_tags(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        release = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        combined = ci + release

        self.assertIn("actions/checkout@v7.0.0", combined)
        self.assertIn("astral-sh/setup-uv@v8.3.2", combined)
        self.assertIn("actions/upload-artifact@v7.0.1", combined)
        self.assertIn("softprops/action-gh-release@v3.0.2", release)

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

    def test_packaged_app_smoke_requires_startup_and_graceful_shutdown(self):
        smoke_script = (ROOT / "scripts" / "smoke_packaged_app.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("Start-Process", smoke_script)
        self.assertIn("CloseMainWindow", smoke_script)
        self.assertIn("WaitForExit", smoke_script)
        self.assertIn("Stop-Process", smoke_script)

    def test_pyinstaller_build_cleans_readonly_output_and_detects_running_app(self):
        script = (ROOT / "scripts" / "run_pyinstaller.ps1").read_text(encoding="utf-8")

        self.assertIn("Remove-PreviousBuildTree", script)
        self.assertIn("FileAttributes]::ReadOnly", script)
        self.assertIn("Refusing to clean build path outside", script)
        self.assertIn("The previous packaged app is still running", script)


if __name__ == "__main__":
    unittest.main()
