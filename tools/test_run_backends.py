"""CPU-only benchmark evidence checks; never launches a fixture."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import run_backends
from run_backends import compact, ready, failure_record


class BackendEvidenceTests(unittest.TestCase):
    def snapshot(self):
        return dict(enabled=True, delivered=15, presented=15, selection_revision=4,
                    presented_revision=4, applied_settings={'Backend': 1},
                    in_process={'nvidia': {'ready': True, 'evaluates': 14}})

    def test_full_and_compact_nvidia_status_both_validate(self):
        snapshot = self.snapshot()
        self.assertTrue(ready(snapshot, 1))
        self.assertTrue(ready(compact(snapshot), 1))

    def test_stale_revision_is_not_presentation_proof(self):
        snapshot = self.snapshot()
        snapshot['presented_revision'] = 3
        self.assertFalse(ready(snapshot, 1))

    def test_nvidia_needs_evaluation_not_just_delivered_counter(self):
        snapshot = self.snapshot()
        snapshot['in_process']['nvidia']['evaluates'] = 0
        self.assertFalse(ready(snapshot, 1))

    def test_different_backend_is_not_success(self):
        self.assertFalse(ready(self.snapshot(), 3))

    def test_failed_mode_never_keeps_fps_images_or_gpu_timing(self):
        result = failure_record(dict(id='dx12-x64', backend='nvidia', error='failed',
                                     average_fps=70, neural_fps=45, captures=['photo.png'],
                                     processing=dict(phase=5, status='failed', gpu_timing={'fps': 100})))
        self.assertFalse(result['passed'])
        self.assertEqual(result['state'], 'error')
        self.assertNotIn('average_fps', result)
        self.assertNotIn('neural_fps', result)
        self.assertNotIn('captures', result)
        self.assertNotIn('gpu_timing', result['diagnostics'])

    def test_failed_case_publishes_only_failure_record_and_removes_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'runs/latest-x64-backends/test-x64/nvidia'
            def fail(game, backend, folder, staged, seconds, environment, reference):
                (staged / 'capture.png').write_bytes(b'image')
                run_backends.write(staged / 'fps.json', {'average_fps': 100})
                return dict(id='test-x64', backend='nvidia', passed=False, error='unavailable', average_fps=100)
            with patch.object(run_backends, 'ROOT', root), patch.object(run_backends, '_run_case', fail):
                result = run_backends.run_case({'id':'test-x64'}, 'nvidia', root, target, 30, {})
            self.assertEqual([p.name for p in target.iterdir()], ['result.json'])
            self.assertNotIn('average_fps', result)
            self.assertEqual(list((root / 'build').iterdir()), [])

    def test_clear_history_preserves_baseline_programs_and_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('games/test-x64', 'clean/games/test-x64', 'runs/latest', 'state'):
                (root / name).mkdir(parents=True)
            baseline = root / 'clean/games/test-x64'
            (baseline / 'game.exe').write_bytes(b'program')
            (baseline / 'texture.png').write_bytes(b'asset')
            reference = root / 'state/matched-reference.png'
            reference.write_bytes(b'reference')
            (root / 'runs/latest/capture.png').write_bytes(b'history')
            run_backends.write(root / 'runs/latest/fps.json', {'average_fps':70})
            with patch.object(run_backends, 'ROOT', root):
                run_backends.clear_history()
            self.assertEqual((baseline / 'game.exe').read_bytes(), b'program')
            self.assertTrue((baseline / 'texture.png').is_file())
            self.assertTrue(reference.is_file())
            self.assertEqual(list((root / 'runs/latest').iterdir()), [])

    def test_native_command_is_1080p_with_one_post_measurement_capture(self):
        command = run_backends.fixture_command(Path('game.exe'), 'native', Path('out'))
        self.assertEqual(command[command.index('--width')+1], '1920')
        self.assertEqual(command[command.index('--height')+1], '1080')
        self.assertEqual(command[command.index('--warmup-seconds')+1], '5')
        self.assertEqual(command[command.index('--measure-seconds')+1], '20')
        self.assertEqual(command.count('--capture-at'), 1)
        self.assertEqual(command[command.index('--capture-at')+1], '25')
        self.assertIn('--capture-after-measure', command)

    def test_enhanced_command_never_captures_unprocessed_fixture_images(self):
        for mode in ('nvidia', 'phoenix'):
            command = run_backends.fixture_command(Path('game.exe'), mode, Path('out'))
            self.assertIn('--no-capture', command)
            self.assertNotIn('--capture-at', command)

    def test_old_capped_results_cannot_resume_as_new_benchmarks(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'result.json'
            game = {'sha256':'same-build'}
            run_backends.write(path, dict(passed=True, executable_sha256='same-build'))
            self.assertFalse(run_backends.current_pass(path, game))
            run_backends.write(path, dict(passed=True, executable_sha256='same-build', profile=run_backends.PROFILE))
            self.assertTrue(run_backends.current_pass(path, game))


if __name__ == '__main__':
    unittest.main()
