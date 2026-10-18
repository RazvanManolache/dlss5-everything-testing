import os
import unittest
from pathlib import Path
from unittest.mock import patch
import build_dependencies


class ToolchainTests(unittest.TestCase):
    def test_explicit_toolchain_override(self):
        with patch.dict(os.environ,{'VS_BUILD_TOOLS':'relative/toolchain'}):
            self.assertEqual(build_dependencies.visual_studio_build(),Path('relative/toolchain'))

    def test_missing_toolchain_has_actionable_error(self):
        with patch.dict(os.environ,{},clear=True),patch.object(Path,'is_file',return_value=False):
            with self.assertRaisesRegex(FileNotFoundError,'VS_BUILD_TOOLS'):
                build_dependencies.visual_studio_build()


if __name__=='__main__':unittest.main()
