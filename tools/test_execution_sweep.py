import configparser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_execution_sweep as sweep


class ExecutionSweepTests(unittest.TestCase):
    def test_all_native_x86_variants_disable_silent_fallback_and_keep_neural_work_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            for variant,(_,setting,_) in sweep.VARIANTS.items():
                sweep.configure(folder,'phoenix',variant)
                cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str
                cfg.read(folder/'ReShade.ini')
                self.assertEqual(cfg['Phoenix.Compatibility']['ExecutionMode'],setting)
                self.assertEqual(cfg['Phoenix.Compatibility']['NativeFallback'],'0')
                self.assertEqual(cfg['Phoenix']['RefinementPasses'],'1')
                self.assertEqual(cfg['Phoenix']['Experimental'],'0')
                self.assertEqual(cfg['Phoenix']['AutomaticBudget'],'0')
                self.assertEqual(cfg['Phoenix']['TransformerBlocks'],'8')
                for i in range(1,9):self.assertEqual(cfg['Phoenix'][f'Block{i}Repeats'],'1')
                self.assertEqual(cfg['Phoenix']['Backend'],'3')
            sweep.configure(folder,'nvidia','auto')
            cfg.read(folder/'ReShade.ini')
            self.assertEqual(cfg['Phoenix.Compatibility']['ExecutionMode'],'auto')
            self.assertEqual(cfg['Phoenix']['Backend'],'1')

    def test_variant_settings_and_observed_names_are_distinct(self):
        self.assertEqual(len(set(v[1] for v in sweep.VARIANTS.values())),3)
        self.assertEqual(len(set(v[2] for v in sweep.VARIANTS.values())),3)
        self.assertEqual(sweep.VARIANTS['x64-library'][2],'in_process_x64_library')
        self.assertEqual(sweep.VARIANTS['x86-driver'][2],'in_process_x86_driver')


if __name__=='__main__':unittest.main()
