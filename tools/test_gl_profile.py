"""CPU-only contract for ReShade's documented-in-source GL profile upgrade."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from build import ROOT, VS, run_batch


class GLProfileTests(unittest.TestCase):
    def test_upgrade_is_allowed_only_for_reshade_and_pre43_requests(self):
        with tempfile.TemporaryDirectory(prefix='gl-policy-', dir=ROOT / 'build') as temporary:
            folder = Path(temporary)
            exe = folder / 'profile.exe'
            run_batch(f'call "{VS / "vcvars64.bat"}" >nul && cl /nologo /std:c++17 /EHsc /MT '
                      f'/I"{ROOT / "src"}" "{ROOT / "tests/gl-profile.cpp"}" '
                      f'/Fo:"{folder / "profile.obj"}" /Fe:"{exe}"', folder / 'compile.cmd')
            subprocess.run([str(exe)], check=True, timeout=10)
