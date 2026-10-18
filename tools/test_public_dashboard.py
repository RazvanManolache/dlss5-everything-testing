import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, PngImagePlugin
import export_public_dashboard as public


class PublicSnapshotTests(unittest.TestCase):
    def data(self):
        return dict(schema=1, generated_at='2026-10-18T00:00:00Z', groups=['Modern DirectX'],
            notes=[], fixtures=[dict(id='case', api='dx12', executable='C:/private/game.exe')],
            runs=[dict(id='run-a', mode='phoenix', execution_variant='helper',
                processing=dict(api='Direct3D 12', inference_pid=123, ModelFolder='C:/private/model', token='secret')),
                dict(id='run-b', mode='phoenix', execution_variant='x86-driver')],
            captures=[dict(id='runs/a.png',run_id='run-a'),dict(id='runs/b.png',run_id='run-b')])

    def test_allowlist_drops_paths_pids_tokens_and_unknown_fields(self):
        result=public.public_data(self.data())
        encoded=json.dumps(result)
        for word in ('private', 'inference_pid', 'secret', 'ModelFolder'):
            self.assertNotIn(word,encoded)
        self.assertTrue(result['public_snapshot'])
        self.assertEqual(result['runs'][0]['processing'],dict(api='Direct3D 12'))

    def test_paths_in_allowed_strings_fail_closed(self):
        data=self.data();data['runs'][0]['error']='Failed to open C:/private/model'
        with self.assertRaises(ValueError):public.public_data(data)

    def test_pixel_dedup_keeps_both_run_identities_and_lossless_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'runs').mkdir();(root/'dashboard').mkdir()
            for name in public.ASSETS:(root/'dashboard'/name).write_text('fixture')
            frame=Image.new('RGB',(20,12),(12,60,180))
            frame.save(root/'runs/a.png')
            meta=PngImagePlugin.PngInfo();meta.add_text('private','discard me')
            frame.save(root/'runs/b.png',pnginfo=meta)
            with patch.object(public,'ROOT',root):
                manifest=public.export(root/'docs/dashboard',self.data())
                self.assertEqual(manifest['unique_images'],1)
                self.assertEqual(manifest['capture_records'],2)
                source=(root/'docs/dashboard/data.js').read_text()
                result=json.loads(source.removeprefix('window.BENCH_DATA = ').rstrip(';\n'))
                self.assertEqual(result['captures'][0]['src'],result['captures'][1]['src'])
                self.assertNotEqual(result['captures'][0]['run_id'],result['captures'][1]['run_id'])
                with Image.open(root/'docs/dashboard'/result['captures'][0]['src']) as encoded:
                    self.assertEqual(public.pixel_identity(encoded)[0],public.pixel_identity(frame)[0])
                public.export(root/'docs/dashboard',self.data(),replace=True)
                (root/'docs/dashboard/private.txt').write_text('not exporter owned')
                with self.assertRaises(ValueError):public.export(root/'docs/dashboard',self.data(),replace=True)


if __name__=='__main__':unittest.main()
