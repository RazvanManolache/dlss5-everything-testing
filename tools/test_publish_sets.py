"""Regression checks for preserving installs and isolating the two build sets."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
import publish_sets as publisher


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='museum-dual-')
        self.root = Path(self.temporary.name)
        self.stage = self.root/'stage'
        self.clean = self.root/'clean'
        self.working = self.root/'working'
        self.shared = self.root/'shared-assets'
        self.relative = 'games/test-x64'
        self.folder = self.stage/self.relative
        files = {'Museum_test_x64.exe': b'native fixture', 'RUN.cmd': b'run',
                 'test-game.json': b'{}', 'd3d9.dll': b'factory wrapper',
                 'wrapper.conf': b'factory settings', 'assets/museum.bin': b'scene',
                 'assets/texture.bin': b'texture'}
        records = {}
        pins = {}
        for name, data in files.items():
            path = self.folder/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            pin = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            member = 'common/'+name if name.startswith('assets/') else self.relative+'/'+name
            records[member] = pin
            if name in ('d3d9.dll', 'wrapper.conf'): pins[name] = pin
        self.game = {'id': 'test-x64', 'install_directory': self.relative,
                     'executable': self.relative+'/Museum_test_x64.exe',
                     'sha256': records[self.relative+'/Museum_test_x64.exe']['sha256'],
                     'runtime_files': pins}
        matrix = {'games': [self.game]}
        (self.stage/'matrix.json').write_text(json.dumps(matrix))
        (self.root/'baseline.json').write_text(json.dumps({'matrix': matrix, 'files': records}))
        self.validation = self.root/'validation.json'
        self.validation.write_text(json.dumps({'passed': True, 'results': [
            {'id': 'test-x64', 'mode': mode, 'passed': True, 'sha256': self.game['sha256']}
            for mode in ('matched', 'showcase')]}))
        self.config = self.root/'config.json'
        self.config.write_text(json.dumps({'clean_suite': str(self.clean),
            'reshade_suite': str(self.working), 'shared_assets': str(self.shared),
            'validation': str(self.validation)}))
        self.root_patch = patch.object(publisher, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temporary.cleanup()

    def publish(self):
        return publisher.publish(self.stage, self.validation, self.config, self.root/'publication.json')

    def test_installed_proxy_settings_and_renamed_seed_survive(self):
        working = self.working/self.relative
        working.mkdir(parents=True)
        (working/'d3d9.dll').write_bytes(b'ReShade proxy')
        (working/'ReShade.ini').write_bytes(b'user settings')
        (working/'original-wrapper.dll').write_bytes(b'factory wrapper')
        result = self.publish()
        self.assertTrue(result['passed'])
        self.assertEqual((working/'d3d9.dll').read_bytes(), b'ReShade proxy')
        self.assertEqual((working/'ReShade.ini').read_bytes(), b'user settings')
        self.assertEqual((working/'original-wrapper.dll').read_bytes(), b'factory wrapper')
        self.assertFalse((working/'wrapper.conf').exists(), 'Do not recreate a deliberately absent seed')
        self.assertEqual((self.clean/self.relative/'d3d9.dll').read_bytes(), b'factory wrapper')
        self.assertFalse((working/'assets').exists())
        self.assertEqual(publisher.find_assets(working), self.shared)
        self.assertFalse((self.clean/self.relative/'assets').exists())
        self.assertEqual(publisher.find_assets(self.clean/self.relative), self.shared)
        self.assertNotEqual((working/'d3d9.dll').stat().st_ino,
                            (self.clean/self.relative/'d3d9.dll').stat().st_ino)
        self.publish()  # Repeated updates must preserve the installation too.
        self.assertEqual((working/'d3d9.dll').read_bytes(), b'ReShade proxy')

    def test_modified_clean_runtime_stops_before_working_update(self):
        self.publish()
        clean_proxy = self.clean/self.relative/'d3d9.dll'
        clean_proxy.write_bytes(b'accidental installation')
        with self.assertRaisesRegex(RuntimeError, 'Modified runtime in clean set'):
            self.publish()
        self.assertEqual(clean_proxy.read_bytes(), b'accidental installation')

    def test_unexpected_clean_addon_is_preserved_and_rejected(self):
        self.publish()
        addon = self.clean/self.relative/'test.addon64'
        addon.write_bytes(b'addon')
        with self.assertRaisesRegex(RuntimeError, 'Unexpected file in clean set'):
            self.publish()
        self.assertEqual(addon.read_bytes(), b'addon')

    def test_unknown_asset_edits_are_never_deleted(self):
        assets = self.working/self.relative/'assets'
        assets.mkdir(parents=True)
        edited = assets/'museum.bin'
        edited.write_bytes(b'edited scene')
        with self.assertRaisesRegex(RuntimeError, 'Assets differ'):
            self.publish()
        self.assertEqual(edited.read_bytes(), b'edited scene')


if __name__ == '__main__':
    unittest.main()
