"""Rebuild metric metadata from saved counters without launching or remeasuring."""
import csv
from processing_fps import completed_fps, processed_metrics
from run_backends import ROOT, read, write


def refresh():
    plan = read(ROOT / 'state/background-rerun.json')
    if plan.get('schema') != 'background-rerun/1' or not plan.get('targets'):
        raise ValueError('Missing background rerun plan')
    count = 0
    for fixture, modes in plan['targets'].items():
        for mode in modes:
            folder = ROOT / 'runs/latest-x64-backends' / fixture / mode
            result = read(folder / 'result.json')
            if result.get('passed') is not True:
                continue
            fps = read(folder / 'fps.json')
            measurement = fps.get('game_measurement') or result['measurement']
            output = completed_fps(read(folder / 'processing.json')['snapshots'], measurement)
            fps['game_measurement'] = measurement
            fps = processed_metrics(fps, output)
            write(folder / 'fps.json', fps)
            result.update(average_fps=output['average_fps'], neural_fps=output['average_fps'],
                          measurement=output['measurement'], fps_scope=output['fps_scope'])
            write(folder / 'result.json', result)
            with (folder / 'fps.csv').open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=['elapsed_seconds', 'frames', 'interval_seconds', 'fps', 'average_fps'])
                writer.writeheader()
                writer.writerows({key:sample.get(key) for key in writer.fieldnames} for sample in output['samples'])
            count += 1
    print(f'Rebuilt metric metadata for {count} selected successful runs; no tests launched')


if __name__ == '__main__':
    refresh()
