import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "src" / "tools"


class WorkerThreadTests(unittest.TestCase):
    def test_all_gui_worker_threads_are_daemons(self):
        missing_daemon: list[str] = []

        for path in sorted(TOOLS_DIR.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                if not (
                    isinstance(function, ast.Attribute)
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "threading"
                    and function.attr == "Thread"
                ):
                    continue
                daemon = next(
                    (keyword.value for keyword in node.keywords if keyword.arg == "daemon"),
                    None,
                )
                if not (
                    isinstance(daemon, ast.Constant) and daemon.value is True
                ):
                    relative = path.relative_to(ROOT)
                    missing_daemon.append(f"{relative}:{node.lineno}")

        self.assertEqual(missing_daemon, [])


if __name__ == "__main__":
    unittest.main()
