"""CPU-only timing arithmetic check. Does not link graphics APIs or launch fixtures."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from build import ROOT, VS, run_batch


class MeasurementWindowTests(unittest.TestCase):
    def test_compiled_clock_accounting(self):
        setup = VS / 'vcvars64.bat'
        if not setup.is_file():
            self.skipTest('MSVC x64 build tools unavailable')
        with tempfile.TemporaryDirectory(prefix='clock-check-', dir=ROOT / 'build') as temporary:
            folder = Path(temporary)
            exe = folder / 'clock-check.exe'
            command = (f'call "{setup}" >nul && cl /nologo /std:c++17 /O2 /EHsc /MT '
                       f'/I"{ROOT / "src"}" "{ROOT / "tests/measurement-window.cpp"}" '
                       f'/Fe:"{exe}" /Fo:"{folder / "clock-check.obj"}"')
            run_batch(command, folder / 'compile.cmd')
            subprocess.run([str(exe)], check=True, capture_output=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
