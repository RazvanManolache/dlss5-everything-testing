"""Counter arithmetic regressions; never launches DOSBox or inference."""
import tempfile
import unittest
from pathlib import Path
from dos_fps import guest_fps, graphics_fps, measure


class DosFpsTests(unittest.TestCase):
    def snapshots(self, backend='phoenix'):
        return [dict(seconds=i / 2, graphics=dict(renderer=backend, source_width=320,
                    source_height=200, frames=i * 10 + 1, presented=i * 100 + 1,
                    phoenix_frames=i * 30 + 1, nr_frames=i * 30 + 1,
                    generated=0, fg_active=False)) for i in range(51)]

    def test_separates_fresh_frames_from_presentation_and_refinement_passes(self):
        for backend in ('nvidia', 'phoenix'):
            fps = graphics_fps(self.snapshots(backend), backend)
            self.assertEqual(fps['average_fps'], 200)
            self.assertEqual(fps['neural_fps'], 20)
            self.assertEqual(fps['processed_frames'], 400)
            self.assertEqual(fps['elapsed_seconds'], 20)
            self.assertEqual(fps['measurement']['start_render_seconds'], 5)

    def test_rejects_missing_samples_or_truncated_window(self):
        for rows in ([], self.snapshots()[:30]):
            with self.assertRaises(ValueError):
                graphics_fps(rows, 'phoenix')

    def test_rejects_counter_reset_and_time_reset(self):
        for key, value in [('frames', 0), ('presented', 0)]:
            rows = self.snapshots()
            rows[30]['graphics'][key] = value
            with self.assertRaises(ValueError):
                graphics_fps(rows, 'phoenix')
        rows = self.snapshots()
        rows[30]['seconds'] = 10
        with self.assertRaises(ValueError):
            graphics_fps(rows, 'phoenix')

    def test_rejects_wrong_backend_extent_or_frame_generation(self):
        for key, value in [('renderer','nvidia'), ('source_width',640), ('generated',1),
                           ('fg_active',True), ('phoenix_frames',0)]:
            rows = self.snapshots()
            rows[30]['graphics'][key] = value
            with self.assertRaises(ValueError):
                graphics_fps(rows, 'phoenix')

    def test_guest_clock_has_explicit_scope_and_excludes_warmup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'FPS.CSV'
            path.write_text('frame,elapsed_seconds\n' +
                            '\n'.join(f'{i * 10},{i}' for i in range(26)))
            fps = guest_fps(path)
            self.assertEqual(fps['average_fps'], 10)
            self.assertEqual(fps['frames_rendered'], 200)
            self.assertIn('emulated seconds', fps['fps_scope'])
            self.assertNotIn('neural_fps', fps)

    def test_rejects_no_progress_and_nonfinite_values(self):
        for rows in ([dict(seconds=i, frames=1) for i in range(26)],
                     [dict(seconds=float('nan'), frames=1)]):
            with self.assertRaises(ValueError):
                measure(rows, 'frames')


if __name__ == '__main__':
    unittest.main()
