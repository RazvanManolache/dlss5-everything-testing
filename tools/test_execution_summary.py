import tempfile
import csv
from pathlib import Path
import unittest
from unittest.mock import patch

import summarize_execution_sweep as summary
from run_backends import write


class ExecutionSummaryTests(unittest.TestCase):
    def test_dos_has_separate_totals_and_explicit_clock_in_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);output=root/'runs/latest-x64-backends'
            write(root/'matrix.json',dict(games=[]))
            for backend in ('native','nvidia','phoenix'):
                folder=output/'dos-vga'/backend;folder.mkdir(parents=True)
                write(folder/'result.json',dict(id='dos-vga',backend=backend,passed=True,
                    average_fps=7 if backend=='native' else 35,
                    fps_scope='guest clock' if backend=='native' else 'host wall clock'))
            with patch.object(summary,'ROOT',root),patch.object(summary,'OUTPUT',output):
                report=summary.summarize()
            self.assertEqual(report['counts'],{})
            self.assertEqual(len(report['dos_results']),3)
            self.assertTrue(all(r['matched_fixtures']==0 for r in report['matched_x86_rankings']))
            with (output/'execution-scores.csv').open(newline='') as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),3)
            self.assertEqual({r['architecture'] for r in rows},{'dos'})
            self.assertEqual({r['fps_scope'] for r in rows},{'guest clock','host wall clock'})

    def test_pending_is_not_failure_and_legacy_native_alias_is_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);output=root/'runs/latest-x64-backends'
            (root/'state').mkdir(parents=True)
            write(root/'matrix.json',dict(games=[dict(id='case',architecture='x86')]))
            (output/'case/native').mkdir(parents=True)
            write(output/'case/native/result.json',dict(id='case',backend='native',passed=True,
                executable_sha256='fixture',profile='same',width=1920,height=1080,game_fps=110))
            (output/'case/phoenix-helper').mkdir()
            write(output/'case/phoenix-helper/result.json',dict(id='case',backend='phoenix',passed=None,
                execution_variant='helper',state='running'))
            write(root/'state/previous-execution-scores.json',dict(scores=[dict(id='case',backend='native',passed=True,
                executable_sha256='fixture',profile='same',width=1920,height=1080,average_fps=100)]))
            with patch.object(summary,'ROOT',root),patch.object(summary,'OUTPUT',output):
                report=summary.summarize()
            self.assertEqual(report['counts'],dict(passed=1,pending=1))
            self.assertAlmostEqual(report['previous_native_x64_comparison'][0]['change_percent'],10)
            self.assertEqual(report['failures'],[])

    def test_positive_rejects_invalid_or_boolean_scores(self):
        for value in (None,True,0,-1,float('nan'),float('inf')):
            self.assertFalse(summary.positive(value))
        self.assertTrue(summary.positive(.1))

    def test_late_readiness_is_exported_without_erasing_the_score(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);output=root/'runs/latest-x64-backends'
            write(root/'matrix.json',dict(games=[dict(id='case',architecture='x86')]))
            (output/'case/phoenix-helper').mkdir(parents=True)
            write(output/'case/phoenix-helper/result.json',dict(id='case',backend='phoenix',passed=True,
                execution_variant='helper',execution_mode='helper',neural_fps=2,
                first_ready_render_seconds=8,warmup_seconds=5))
            with patch.object(summary,'ROOT',root),patch.object(summary,'OUTPUT',output):
                report=summary.summarize()
            self.assertEqual(report['counts'],dict(passed=1))
            self.assertIn('True',(output/'execution-scores.csv').read_text())
            self.assertIn('2',(output/'execution-scores.csv').read_text())


if __name__=='__main__':unittest.main()
