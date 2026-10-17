"""Counter-derived DOS rates; no emulator, graphics, or process operations."""
import csv
import math


def measure(rows, counter, warmup=5, seconds=20):
    """Use real counter deltas after warmup, never reciprocal inference time."""
    selected = []
    for row in rows:
        tick, count = row.get('seconds'), row.get(counter)
        if (isinstance(tick, bool) or not isinstance(tick, (int, float)) or
                not math.isfinite(tick) or tick < 0 or isinstance(count, bool) or
                not isinstance(count, int) or count < 0):
            raise ValueError('Invalid DOS timestamp or frame counter')
        if selected and (tick <= selected[-1]['seconds'] or count < selected[-1][counter]):
            raise ValueError('DOS timestamps/counters reset during measurement')
        if tick >= warmup:
            selected.append(row)
        if selected and tick >= warmup + seconds:
            break
    if (len(selected) < 2 or selected[0]['seconds'] > warmup + 1 or
            selected[-1]['seconds'] < warmup + seconds):
        raise ValueError('DOS measurement does not cover the requested window')
    start, end = selected[0], selected[-1]
    elapsed, frames = end['seconds'] - start['seconds'], end[counter] - start[counter]
    if elapsed <= 0 or frames <= 0:
        raise ValueError('No DOS frames completed in the measured window')
    samples = []
    for previous, current in zip(selected, selected[1:]):
        interval = current['seconds'] - previous['seconds']
        count = current[counter] - previous[counter]
        samples.append(dict(elapsed_seconds=current['seconds'] - start['seconds'],
                            frames=count, interval_seconds=interval, fps=count / interval,
                            average_fps=(current[counter] - start[counter]) /
                                        (current['seconds'] - start['seconds'])))
    measurement = dict(complete=True, warmup_seconds=warmup, requested_seconds=seconds,
                       start_render_seconds=start['seconds'], end_render_seconds=end['seconds'],
                       elapsed_seconds=elapsed, frames_rendered=frames)
    return dict(average_fps=frames / elapsed, frames_rendered=frames, elapsed_seconds=elapsed,
                minimum_sample_fps=min(s['fps'] for s in samples),
                maximum_sample_fps=max(s['fps'] for s in samples),
                measurement=measurement, samples=samples)


def guest_fps(path, warmup=5, seconds=20):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = [dict(seconds=float(row['elapsed_seconds']), frames=int(row['frame']))
                for row in csv.DictReader(stream)]
    result = measure(rows, 'frames', warmup, seconds)
    return result | dict(fps_scope='DOS guest render frames / emulated seconds',
                         clock='DOS guest uclock', counter='FPS.CSV frame')


def graphics_fps(snapshots, backend, warmup=5, seconds=20):
    if backend not in ('nvidia', 'phoenix'):
        raise ValueError('Unknown DOS enhancement backend')
    rows = []
    evaluation_counter = 'nr_frames' if backend == 'nvidia' else 'phoenix_frames'
    for snapshot in snapshots:
        graphics = snapshot.get('graphics') or {}
        if snapshot.get('seconds', 0) >= warmup:
            if (graphics.get('renderer') != backend or graphics.get('source_width') != 320 or
                    graphics.get('source_height') != 200 or graphics.get(evaluation_counter, 0) <= 0 or
                    graphics.get('fg_active') or graphics.get('generated', 0) != 0):
                raise ValueError('DOS measured output has the wrong renderer/extent or generated frames')
        rows.append(dict(seconds=snapshot.get('seconds'), frames=graphics.get('frames'),
                         presented=graphics.get('presented')))
    fresh = measure(rows, 'frames', warmup, seconds)
    present = measure(rows, 'presented', warmup, seconds)
    return present | dict(neural_fps=fresh['average_fps'], processed_frames=fresh['frames_rendered'],
                          fps_scope='DOSBox enhanced presentations / host wall seconds',
                          neural_fps_scope='Completed enhanced images / host wall seconds',
                          clock='host monotonic', counter='graphics.presented',
                          neural_counter='graphics.frames')
