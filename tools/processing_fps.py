"""Fresh-output throughput from monotonic counters, never repeated presentations."""
import bisect
import math


def completed_fps(snapshots, measurement):
    start, end = measurement['start_render_seconds'], measurement['end_render_seconds']
    if not all(isinstance(v, (int,float)) and math.isfinite(v) for v in (start,end)) or end <= start:
        raise ValueError('Invalid processing measurement window')
    rows = []
    for sample in snapshots:
        if (not isinstance(sample.get('seconds'),(int,float)) or not math.isfinite(sample['seconds']) or
                not isinstance(sample.get('delivered'),int) or isinstance(sample['delivered'],bool) or sample['delivered']<0):
            continue
        if rows and sample['seconds']==rows[-1]['seconds']:
            if sample['delivered']<rows[-1]['delivered']:
                raise ValueError('Processing counter reset during a duplicate status tick')
            rows[-1]=sample  # Quantized or cached status timestamps can repeat.
        else:
            rows.append(sample)
    ticks = [s['seconds'] for s in rows]
    if len(rows) < 2 or any(b <= a for a,b in zip(ticks,ticks[1:])):
        raise ValueError('Missing or nonmonotonic processing samples')
    left = bisect.bisect_right(ticks, start) - 1
    right = bisect.bisect_left(ticks, end)
    if left < 0 or right >= len(rows):
        raise ValueError('Processing counters do not bracket the full measured window')
    selected = rows[left:right+1]
    if any(b['delivered'] < a['delivered'] for a,b in zip(selected,selected[1:])):
        raise ValueError('Processing counter reset during measurement')

    def counter(tick):
        i = bisect.bisect_left(ticks, tick)
        if ticks[i] == tick:
            return rows[i]['delivered']
        a,b = rows[i-1],rows[i]
        return a['delivered'] + (b['delivered']-a['delivered']) * (tick-a['seconds']) / (b['seconds']-a['seconds'])

    boundaries = [start, *[t for t in ticks if start < t < end], end]
    base = counter(start)
    samples = []
    for a,b in zip(boundaries,boundaries[1:]):
        frames = counter(b)-counter(a)
        samples.append(dict(elapsed_seconds=b-start, frames=frames, interval_seconds=b-a,
                            fps=frames/(b-a), average_fps=(counter(b)-base)/(b-start)))
    frames = counter(end)-base
    if frames <= 0:
        raise ValueError('No fresh processed frames completed during measurement')
    metrics = dict(average_fps=frames/(end-start), frames_rendered=frames, elapsed_seconds=end-start,
                minimum_sample_fps=min(s['fps'] for s in samples),
                maximum_sample_fps=max(s['fps'] for s in samples), samples=samples,
                fps_scope='Fresh completed enhanced outputs / host wall seconds',
                counter='delivered', counter_boundary_method='bounded linear interpolation; no extrapolation')
    window = {key:measurement[key] for key in ('start_render_seconds', 'end_render_seconds',
              'complete', 'enabled', 'requested_seconds', 'warmup_seconds') if key in measurement}
    return dict(metrics, measurement={**window, **metrics})


def processed_metrics(fps, output_rate):
    """Keep fixture timing available only under explicitly game-prefixed names."""
    result = dict(fps)
    already_processed = fps.get('counter') == 'delivered'
    for key in ('average_fps', 'samples', 'frames_rendered', 'measurement',
                'full_run_average_fps', 'latest_fps', 'maximum_frame_seconds',
                'minimum_frame_seconds', 'minimum_sample_fps', 'maximum_sample_fps'):
        if key in result:
            if not already_processed or key in ('full_run_average_fps', 'latest_fps',
                                                 'maximum_frame_seconds', 'minimum_frame_seconds'):
                result.setdefault('game_' + ('fps' if key == 'average_fps' else key), result[key])
            del result[key]
    return {**result, **output_rate}
