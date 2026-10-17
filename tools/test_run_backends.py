"""CPU-only benchmark evidence checks; never launches a fixture."""
import unittest
import ctypes
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import run_backends
from run_backends import compact, ready, failure_record


class BackendEvidenceTests(unittest.TestCase):
    def test_background_cleanup_preserves_baselines_and_inprocess_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'state').mkdir()
            run_backends.write(root/'matrix.json', {'games':[{'id':'case','sha256':'same'}]})
            for mode,route in [('native','native'),('nvidia','helper'),('phoenix','in_process')]:
                folder=root/'runs/latest-x64-backends/case'/mode
                folder.mkdir(parents=True)
                run_backends.write(folder/'result.json',dict(backend=mode,passed=True,execution_mode=route))
                (folder/'capture.png').write_bytes(b'capture')
            with patch.object(run_backends,'ROOT',root):
                plan=run_backends.prepare_background_rerun()
                with self.assertRaises(RuntimeError):
                    run_backends.clear_enhanced_case(root/'runs/latest-x64-backends/case/native')
            self.assertEqual(plan['targets'],{'case':['nvidia']})
            case=root/'runs/latest-x64-backends/case'
            self.assertTrue((case/'native/capture.png').exists())
            self.assertTrue((case/'phoenix/capture.png').exists())
            self.assertEqual([p.name for p in (case/'nvidia').iterdir()],['result.json'])
            self.assertEqual(run_backends.read(case/'nvidia/result.json')['state'],'queued')

    def test_background_selection_includes_failed_observed_helpers(self):
        self.assertEqual(run_backends.execution_mode({'diagnostics':{'execution_mode':'helper'}}),'helper')
    def test_glide_uses_declared_native_mode_and_separate_resume_profile(self):
        game = {'glide_version':1, 'background_test':{'width':856,'height':480}}
        self.assertEqual(run_backends.desired_extent(game), (856,480))
        self.assertNotEqual(run_backends.profile_for(game), run_backends.PROFILE)
        command = run_backends.fixture_command(Path('game.exe'), 'native', Path('out'), run_backends.desired_extent(game))
        self.assertEqual(command[command.index('--width')+1], '856')
        self.assertEqual(command[command.index('--height')+1], '480')

    def test_control_request_expiry_covers_slow_frame_response_deadline(self):
        with tempfile.TemporaryDirectory() as temporary:
            mail = run_backends.Mailbox.__new__(run_backends.Mailbox)
            mail.mail = Path(temporary)
            mail.endpoint = {'session':'session'}
            mail.process = Mock(pid=777)
            mail.process.poll.return_value = None
            mail.kernel = Mock()
            mail.kernel.GetTickCount64.return_value = 5000
            mail.helpers = {}
            run_backends.write(mail.mail / 'response.json', {'id':'request','snapshot':{}})
            with patch.object(run_backends.uuid, 'uuid4', return_value=Mock(hex='request')):
                mail.command('screenshot', timeout=10)
            request = run_backends.read(mail.mail / 'request.json')
            self.assertGreater(request['expires_tick_ms'], 15000)

    def test_shutdown_closes_owned_private_desktop_windows_without_activating_it(self):
        user, process = Mock(), Mock(pid=777)
        process.poll.return_value = None
        user.OpenDesktopW.return_value = 1234
        def window_pid(hwnd, pointer):
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_ulong)).contents.value = 777
        user.GetWindowThreadProcessId.side_effect = window_pid
        user.EnumDesktopWindows.side_effect = lambda desktop, callback, parameter: callback(55, None)
        with patch.object(ctypes, 'WinDLL', return_value=user):
            run_backends.close_fixture(process)
        self.assertEqual(user.OpenDesktopW.call_args.args[0], 'MuseumFixture_777')
        user.CloseDesktop.assert_called_once_with(1234)
        self.assertEqual(user.PostMessageW.call_args.args[1], 0x10)
        user.SwitchDesktop.assert_not_called()
        process.kill.assert_not_called()

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

    def test_addon_change_invalidates_enhanced_result_but_not_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'result.json'
            game = {'sha256':'fixture', 'addon_sha256':'new-addon'}
            record = dict(passed=True, executable_sha256='fixture', profile=run_backends.PROFILE,
                          backend='phoenix', addon_sha256='old-addon')
            run_backends.write(path, record)
            self.assertFalse(run_backends.current_pass(path, game))
            record['backend'] = 'native'
            run_backends.write(path, record)
            self.assertTrue(run_backends.current_pass(path, game))


if __name__ == '__main__':
    unittest.main()
