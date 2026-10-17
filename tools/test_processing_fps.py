import unittest
from processing_fps import completed_fps, processed_metrics


class ProcessingFpsTests(unittest.TestCase):
    def window(self):
        return dict(start_render_seconds=5, end_render_seconds=25, complete=True)

    def rows(self):
        return [dict(seconds=i/2, delivered=i*10, presented=i*300) for i in range(53)]

    def test_counts_unique_outputs_not_repeated_presentations(self):
        result = completed_fps(self.rows(), self.window())
        self.assertEqual(result['average_fps'],20)
        self.assertEqual(result['frames_rendered'],400)
        self.assertEqual(result['elapsed_seconds'],20)
        self.assertEqual(len(result['samples']),40)

    def test_interpolates_boundaries_without_extrapolation(self):
        result = completed_fps(self.rows(), dict(start_render_seconds=5.1,end_render_seconds=25.1))
        self.assertAlmostEqual(result['average_fps'],20)
        self.assertAlmostEqual(result['frames_rendered'],400)

    def test_duplicate_status_ticks_do_not_invent_frames_or_fail_a_valid_run(self):
        rows=self.rows()
        rows.insert(18,dict(rows[17]))
        rows.insert(31,dict(rows[30]))
        result=completed_fps(rows,self.window())
        self.assertEqual(result['average_fps'],20)
        self.assertEqual(result['frames_rendered'],400)

    def test_warmup_and_late_first_output_do_not_shorten_the_denominator(self):
        rows = [dict(seconds=i,delivered=max(0,i-10)*20) for i in range(26)]
        self.assertEqual(completed_fps(rows,self.window())['average_fps'],15)

    def test_missing_window_reset_or_no_progress_cannot_create_fps(self):
        bad = [self.rows()[12:], self.rows()[:40]]
        reset = self.rows(); reset[30]['delivered']=1; bad.append(reset)
        repeated = self.rows(); repeated[30]['seconds']=14; bad.append(repeated)
        bad.append([dict(seconds=i,delivered=0) for i in range(26)])
        for rows in bad:
            with self.assertRaises(ValueError):
                completed_fps(rows,self.window())

    def test_nested_measurement_never_keeps_game_fps_under_output_names(self):
        window = dict(self.window(), average_fps=600, frames_rendered=12000,
                      samples=[dict(fps=600)], maximum_frame_seconds=.01)
        output = completed_fps(self.rows(), window)
        self.assertEqual(output['measurement']['average_fps'], 20)
        self.assertEqual(output['measurement']['frames_rendered'], 400)
        self.assertEqual(output['measurement']['samples'], output['samples'])
        self.assertNotIn('maximum_frame_seconds', output['measurement'])

    def test_packaging_keeps_raw_metrics_separate_and_is_idempotent(self):
        original = dict(average_fps=600, samples=[dict(fps=600)], frames_rendered=12000,
                        measurement=dict(self.window(), average_fps=600), latest_fps=650,
                        full_run_average_fps=610, maximum_frame_seconds=.01)
        output = completed_fps(self.rows(), self.window())
        packaged = processed_metrics(original, output)
        self.assertEqual(packaged['average_fps'], 20)
        self.assertEqual(packaged['game_fps'], 600)
        self.assertEqual(packaged['game_latest_fps'], 650)
        self.assertNotIn('latest_fps', packaged)
        self.assertEqual(packaged['game_measurement'], original['measurement'])
        self.assertEqual(processed_metrics(packaged, output), packaged)
