"""Bounded data-index and read-only HTTP checks; no benchmark executable is launched."""
from pathlib import Path
import base64, hashlib, json, tempfile, threading, unittest, urllib.request, urllib.error
from unittest.mock import patch
import dashboard

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jPz8AAAAASUVORK5CYII=')


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='museum-dashboard-')
        self.root = Path(self.temp.name)
        self.patcher = patch.object(dashboard, 'ROOT', self.root)
        self.patcher.start()
        self.write('matrix.json', {'games': [{'id': 'dx11-x64', 'api': 'dx11', 'architecture': 'x64', 'sha256': 'current'}]})

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return path

    def image(self, rel):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG)
        return path

    def test_incomplete_capture_does_not_invent_fps_or_freshness(self):
        self.image('runs/latest/windows/dx11-x64/capture.png')
        data = dashboard.make_data()
        self.assertEqual(len(data['captures']), 1)
        result = data['runs'][0]
        self.assertEqual(result['status'], 'incomplete')
        self.assertIsNone(result['fps'])
        self.assertEqual(result['freshness'], 'unverified')

    def test_current_result_and_capture_schedule(self):
        base = 'clean/games/dx11-x64/run/'
        self.image(base + 'capture-00001.png')
        self.image(base + 'capture.png')
        self.write(base + 'status.json', {'state': 'complete', 'mode': 'matched', 'width': 1280, 'height': 720})
        self.write(base + 'fps.json', {'average_fps': 124.5, 'samples': [{'elapsed_seconds': 1, 'fps': 123}],
                                     'captures': [{'png': 'capture-00001.png', 'requested_seconds': 15, 'elapsed_seconds': 15.1}]})
        self.write(base + 'verification.json', {'sha256': 'current', 'passed': True})
        data = dashboard.make_data()
        self.assertEqual(data['runs'][0]['freshness'], 'current')
        self.assertEqual(data['runs'][0]['suite'], 'clean')
        self.assertEqual(data['runs'][0]['fps'], 124.5)
        self.assertEqual(len(data['captures']), 1)
        self.assertEqual(data['captures'][0]['seconds'], 15.1)

    def test_identical_images_group_only_within_the_same_run(self):
        base = 'runs/latest/dx11-x64/'
        self.image(base + 'capture-00001.png')
        self.image(base + 'capture-00002.png')
        distinct = self.image(base + 'capture-00003.png')
        distinct.write_bytes(PNG + b'distinct-file-content')
        self.write(base + 'captures.json', {'captures': [
            {'png': 'capture-00001.png', 'elapsed_seconds': 15, 'frame': 100},
            {'png': 'capture-00002.png', 'elapsed_seconds': 25, 'frame': 200},
            {'png': 'capture-00003.png', 'elapsed_seconds': 30, 'frame': 300},
            {'png': 'capture-00001.png', 'elapsed_seconds': 15, 'frame': 100}]})
        self.image('runs/other/dx11-x64/capture-00001.png')
        data = dashboard.make_data()
        grouped = next(c for c in data['captures'] if c['id'] == base + 'capture-00001.png')
        self.assertEqual(len(data['captures']), 3)
        self.assertEqual([c['seconds'] for c in grouped['occurrences']], [15, 25])
        self.assertEqual([c['frame'] for c in grouped['occurrences']], [100, 200])
        self.assertEqual(len(next(r for r in data['runs'] if r['id'] == base.rstrip('/'))['captures']), 2)

    def test_old_result_is_stale_even_when_passed(self):
        self.write('runs/latest/dx11-x64/status.json', {'state': 'complete'})
        self.write('runs/latest/dx11-x64/verification.json', {'sha256': 'older', 'passed': True})
        self.assertEqual(dashboard.make_data()['runs'][0]['freshness'], 'stale')

    def test_backend_not_scene_labels_the_run_and_exposes_neural_throughput(self):
        base = 'runs/latest-x64-backends/dx11-x64/phoenix/'
        self.write(base + 'status.json', {'state': 'complete', 'mode': 'showcase'})
        self.write(base + 'result.json', {'backend': 'phoenix', 'neural_fps': 23.5, 'passed': True})
        result = dashboard.make_data()['runs'][0]
        self.assertEqual(result['mode'], 'phoenix')
        self.assertEqual(result['scene_mode'], 'showcase')
        self.assertEqual(result['neural_fps'], 23.5)
        self.assertEqual(result['fps'], 23.5)

    def test_helper_output_never_uses_game_loop_or_stale_game_samples(self):
        base='runs/latest-x64-backends/dx11-x64/phoenix/'
        self.write(base+'result.json', {'backend':'phoenix','passed':True,'execution_mode':'helper','neural_fps':20})
        self.write(base+'fps.json', {'average_fps':600,'samples':[{'elapsed_seconds':1,'fps':600}]})
        run=dashboard.make_data()['runs'][0]
        self.assertEqual(run['fps'],20)
        self.assertEqual(run['game_fps'],600)
        self.assertEqual(run['samples'],[])
        self.assertEqual(run['game_samples'],[{'seconds':1,'fps':600}])
        self.assertEqual(run['execution_mode'],'helper')

    def test_missing_helper_completion_counter_never_falls_back_to_game_fps(self):
        base='runs/latest-x64-backends/dx11-x64/phoenix/'
        self.write(base+'result.json', {'backend':'phoenix','passed':True,'execution_mode':'helper'})
        self.write(base+'fps.json', {'average_fps':600})
        run=dashboard.make_data()['runs'][0]
        self.assertIsNone(run['fps'])
        self.assertEqual(run['game_fps'],600)

    def test_new_counter_samples_preserve_separate_game_loop_rate(self):
        base='runs/latest-x64-backends/dx11-x64/phoenix/'
        self.write(base+'result.json', {'backend':'phoenix','passed':True,'neural_fps':20})
        self.write(base+'fps.json', {'counter':'delivered','average_fps':20,'game_fps':600,
                   'samples':[{'elapsed_seconds':1,'fps':20}], 'game_samples':[{'elapsed_seconds':1,'fps':600}]})
        run=dashboard.make_data()['runs'][0]
        self.assertEqual(run['fps'],20)
        self.assertEqual(run['game_fps'],600)
        self.assertEqual(run['samples'],[{'seconds':1,'fps':20}])

    def test_pairing_metadata_comes_from_saved_benchmark_evidence(self):
        base = 'runs/latest-x64-backends/dx11-x64/phoenix/'
        self.write(base + 'result.json', {'backend': 'phoenix', 'passed': True,
            'profile': 'uncapped-1080p', 'addon_sha256': 'tested-addon', 'requested_seconds': 20, 'warmup_seconds': 5,
            'vsync': False, 'width': 1920, 'height': 1080, 'measurement': {'complete': True}})
        run = dashboard.make_data()['runs'][0]
        self.assertEqual(run['benchmark_profile'], 'uncapped-1080p')
        self.assertEqual(run['addon_sha256'], 'tested-addon')
        self.assertEqual(run['comparison_batch'], 'runs/latest-x64-backends')
        self.assertEqual((run['width'], run['height']), (1920, 1080))
        self.assertEqual(run['requested_seconds'], 20)
        self.assertEqual(run['warmup_seconds'], 5)
        self.assertIs(run['vsync'], False)
        self.assertIs(run['measurement_complete'], True)

    def test_dos_rates_keep_their_clock_and_resolution_scope(self):
        base = 'runs/latest-x64-backends/dos-vga/phoenix/'
        self.write('games/dos-vga/test-game.json', {'id':'dos-vga', 'sha256':'dos-hash'})
        self.write(base + 'result.json', {'id':'dos-vga', 'backend':'phoenix', 'passed':True,
                                         'neural_fps':19.5, 'width':320, 'height':200})
        self.write(base + 'status.json', {'state':'complete', 'mode':'showcase'})
        self.write(base + 'fps.json', {'average_fps':60, 'fps_scope':'DOS host presentations',
                                      'neural_fps_scope':'Completed images / host seconds'})
        run = dashboard.make_data()['runs'][0]
        self.assertEqual(run['fps'], 60)
        self.assertEqual(run['neural_fps'], 19.5)
        self.assertEqual((run['width'], run['height']), (320,200))
        self.assertEqual(run['fps_scope'], 'DOS host presentations')
        self.assertEqual(run['neural_fps_scope'], 'Completed images / host seconds')

    def test_missing_presented_capture_never_substitutes_original_readback(self):
        base = 'runs/latest-x64-backends/dx11-x64/nvidia/'
        self.write(base + 'result.json', {'backend': 'nvidia', 'passed': False,
                                         'capture_source': 'phoenix_presented_output'})
        self.write(base + 'captures.json', {'captures': []})
        self.write(base + 'fps.json', {'captures': [{'png': 'capture-00001.png'}]})
        self.image(base + 'capture-00001.png')
        self.assertEqual(dashboard.make_data()['captures'], [])

    def test_failed_backend_hides_even_stale_images_and_rates(self):
        base = 'runs/latest-x64-backends/dx11-x64/nvidia/'
        self.write(base + 'result.json', {'backend': 'nvidia', 'passed': False, 'neural_fps': 35})
        self.write(base + 'fps.json', {'average_fps': 70, 'samples': [{'elapsed_seconds': 1, 'fps': 70}]})
        self.image(base + 'capture-00001.png')
        data = dashboard.make_data()
        self.assertEqual(data['captures'], [])
        self.assertIsNone(data['runs'][0]['fps'])
        self.assertIsNone(data['runs'][0]['neural_fps'])
        self.assertEqual(data['runs'][0]['samples'], [])

    def test_running_status_exposes_recorded_benchmark_fps(self):
        self.write('games/dx11-x64/run/status.json', {'state': 'running', 'benchmark': {'average_fps': 110}})
        result = dashboard.make_data()['runs'][0]
        self.assertEqual(result['fps'], 110)
        self.assertEqual(result['status'], 'incomplete')

    def test_manifest_cannot_reference_an_external_file(self):
        self.write('runs/latest/dx11-x64/captures.json', {'captures': [{'png': '../../private.png'}]})
        self.image('runs/private.png')
        self.assertEqual(dashboard.make_data()['captures'], [])

    def test_dos_binary_hash_and_alias_image(self):
        self.write('games/dos-vga/test-game.json', {'id': 'dos-vga', 'sha256': hashlib.sha256(b'new').hexdigest()})
        file = self.root / 'runs/latest-dos/MUSEUM.EXE'
        file.parent.mkdir(parents=True)
        file.write_bytes(b'old')
        self.image('runs/latest-dos/CAP00001.BMP')
        self.image('runs/latest-dos/CAPTURE.BMP')
        data = dashboard.make_data()
        self.assertEqual(len(data['captures']), 1)
        self.assertEqual(data['runs'][0]['freshness'], 'stale')
        self.assertEqual(data['runs'][0]['fixture_id'], 'dos-vga')

    def test_http_allows_only_dashboard_images_and_index(self):
        self.image('runs/latest/dx11-x64/capture.png')
        secret = self.root / '.git/config'
        secret.parent.mkdir()
        secret.write_text('private remote')
        self.write('dashboard/index.html', {})
        server = dashboard.ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with urllib.request.urlopen(base + '/api/data') as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(len(json.load(response)['fixtures']), 1)
            with urllib.request.urlopen(base + '/runs/latest/dx11-x64/capture.png') as response:
                self.assertEqual(response.read(), PNG)
            for path in ('/.git/config', '/%2e%2e/private.png', '/matrix.json'):
                with self.assertRaises(urllib.error.HTTPError) as denied: urllib.request.urlopen(base + path)
                denied.exception.close()
            request = urllib.request.Request(base + '/api/data', headers={'Host': 'unrelated.example'})
            with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_dashboard_listener_does_not_allow_a_second_instance_on_the_same_port(self):
        server = dashboard.DashboardServer(('127.0.0.1', 0), dashboard.Handler)
        try:
            with self.assertRaises(OSError):
                other = dashboard.DashboardServer(server.server_address, dashboard.Handler)
                other.server_close()
        finally:
            server.server_close()


if __name__ == '__main__': unittest.main()
