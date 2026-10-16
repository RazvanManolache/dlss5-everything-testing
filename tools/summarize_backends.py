"""Refresh a compact current sweep report without launching tests."""
import json
from pathlib import Path
from run_backends import ROOT, read, write, PROFILE, WARMUP_SECONDS, MEASURE_SECONDS, WIDTH, HEIGHT


def summarize():
    output = ROOT / 'runs/latest-x64-backends'
    games = [g for g in read(ROOT / 'matrix.json')['games'] if g['architecture'] == 'x64']
    rows = []
    for game in games:
        folder = output / game['id']
        inventory = read(folder / 'inventory.json')
        candidate = (inventory.get('Games') or [{}])[0]
        row = dict(id=game['id'], application_api=game['api'],
                   detected_api=candidate.get('Api'), detection=candidate.get('Detection'), modes={})
        for mode in ('native', 'nvidia', 'phoenix'):
            result = read(folder / mode / 'result.json')
            fps = read(folder / mode / 'fps.json')
            if result.get('passed') and fps:
                fps.update(backend=mode, source_suite=result.get('source_suite'),
                           executable_sha256=result.get('executable_sha256'),
                           captures=read(folder / mode / 'captures.json').get('captures') or [])
                write(folder / mode / 'fps.json', fps)
            elif result.get('passed') is False:
                fps = {}
            row['modes'][mode] = dict(
                outcome='passed' if result.get('passed') else 'failed' if result.get('error') else 'pending',
                game_fps=fps.get('average_fps'), neural_fps=result.get('neural_fps'),
                elapsed_seconds=fps.get('elapsed_seconds'), error=result.get('error'),
                execution=result.get('processing', {}).get('execution_mode'),
                captures=len(read(folder / mode / 'captures.json').get('captures') or []))
        rows.append(row)
    counts = {outcome:sum(m['outcome']==outcome for r in rows for m in r['modes'].values())
              for outcome in ('passed','failed','pending')}
    write(output / 'summary.json', dict(schema=1, requested_seconds=MEASURE_SECONDS,
                                       warmup_seconds=WARMUP_SECONDS, profile=PROFILE,
                                       width=WIDTH, height=HEIGHT, counts=counts, fixtures=rows))
    lines = ['# Current x64 backend sweep', '',
             '5 seconds warmup, then 20 measured seconds per launched mode; 1920x1080, VSync disabled, frozen showcase scene.',
             'One screenshot per successful mode, after measurement. Hidden-window timings are not visible gameplay benchmarks.', '',
             '| Fixture | Detected API | Native FPS | NVIDIA game / neural FPS | Phoenix game / neural FPS | Outcome |',
             '| --- | --- | ---: | ---: | ---: | --- |']
    def number(value):
        return f'{value:.2f}' if isinstance(value, (int,float)) else '-'
    for row in rows:
        modes = row['modes']
        values = [number(modes['native']['game_fps'])]
        for name in ('nvidia', 'phoenix'):
            values.append(number(modes[name]['game_fps']) + ' / ' + number(modes[name]['neural_fps']))
        outcome = ', '.join(name + ': ' + data['outcome'] for name,data in modes.items())
        lines.append('| ' + ' | '.join([row['id'], row.get('detected_api') or '-', *values, outcome]) + ' |')
    errors = [(r['id'], name, m['error']) for r in rows for name,m in r['modes'].items() if m.get('error')]
    if errors:
        lines += ['', '## Failures', '']
        lines += [f'- {fixture}, {mode}: {error}' for fixture,mode,error in errors]
    (output / 'summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(counts))
    return counts


if __name__ == '__main__':
    summarize()
