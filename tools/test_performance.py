"""CPU-only tests of the exact JavaScript statistics module used by the dashboard."""
from pathlib import Path
import shutil
import subprocess
import unittest


class PerformanceTests(unittest.TestCase):
    def test_browser_statistics_contract(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node.js is required to validate dashboard calculations')
        root = Path(__file__).resolve().parents[1]
        run = subprocess.run([node, '--test', 'tests/dashboard-performance.cjs'], cwd=root,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main()
