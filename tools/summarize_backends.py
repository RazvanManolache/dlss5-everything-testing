"""Refresh a compact current sweep report without launching tests."""
import json
from pathlib import Path
from run_backends import ROOT, read, write, PROFILE, WARMUP_SECONDS, MEASURE_SECONDS, WIDTH, HEIGHT


def failure_detail(result):
    if result.get('passed') is not False:
        return None
    diagnostics = result.get('diagnostics') or {}
    messages = diagnostics.get('reshade_messages') or []
    if any('Skipping device because' in message and
           ('WARP' in message or 'Microsoft Basic Render Driver' in message)
           for message in messages):
        return 'Stock ReShade skips this software/reference device'
    error = result.get('error') or ''
    if 'executable/API combination is not supported' in error:
        return 'Installer has no supported route for this architecture/API'
    if diagnostics.get('execution_mode') == 'helper' and 'No enhanced presentation within' in error:
        return 'Helper started; no enhanced presentation within the readiness deadline'
    return None


def summarize():
    output = ROOT / 'runs/latest-x64-backends'
    games = list(read(ROOT / 'matrix.json')['games'])
    if (output / 'dos-vga').is_dir():
        games.append(dict(id='dos-vga', api='DOS VGA / DOSBox Enhanced direct renderer'))
    rows = []
    for game in games:
        folder = output / game['id']
        inventory = read(folder / 'inventory.json')
        candidate = (inventory.get('Games') or [{}])[0]
        plan = ((inventory.get('Plans') or [{}])[0].get('Plan') or {})
        row = dict(id=game['id'], application_api=game['api'],
                   detected_api=candidate.get('Api') or ('DOS VGA' if game['id']=='dos-vga' else None),
                   detection=candidate.get('Detection'), installation_plan=plan, modes={})
        for mode in ('native', 'nvidia', 'phoenix'):
            result = read(folder / mode / 'result.json')
            fps = read(folder / mode / 'fps.json')
            renderer = read(folder / mode / 'status.json').get('renderer_details', {})
            if result.get('passed') and fps:
                fps.update(backend=mode, source_suite=result.get('source_suite'),
                           executable_sha256=result.get('executable_sha256'),
                           captures=read(folder / mode / 'captures.json').get('captures') or [])
                write(folder / mode / 'fps.json', fps)
            elif result.get('passed') is False:
                fps = {}
            row['modes'][mode] = dict(
                outcome='passed' if result.get('passed') else 'failed' if result.get('error') else 'pending',
                fps=fps.get('average_fps'), game_fps=fps.get('game_fps', fps.get('average_fps')), neural_fps=result.get('neural_fps'),
                fps_scope=fps.get('fps_scope'),
                elapsed_seconds=fps.get('elapsed_seconds'), error=result.get('error'),
                failure_detail=failure_detail(result),
                execution=result.get('execution_mode') or result.get('processing', {}).get('execution_mode') or result.get('diagnostics', {}).get('execution_mode'),
                runtime_api=result.get('processing', {}).get('api'),
                renderer_backend=renderer.get('requested_backend'),
                reshade_profile_upgrade=renderer.get('reshade_profile_upgrade', False),
                captures=len(read(folder / mode / 'captures.json').get('captures') or []))
        rows.append(row)
    counts = {outcome:sum(m['outcome']==outcome for r in rows for m in r['modes'].values())
              for outcome in ('passed','failed','pending')}
    write(output / 'summary.json', dict(schema=1, requested_seconds=MEASURE_SECONDS,
                                       warmup_seconds=WARMUP_SECONDS, profile=PROFILE,
                                       width=WIDTH, height=HEIGHT, counts=counts, fixtures=rows))
    lines = ['# Current x86/x64 backend sweep', '',
             '5 seconds warmup, then 20 measured seconds per launched Windows mode; 1920x1080 except native Glide 856x480. DOS uses native VGA separately. VSync disabled, frozen showcase scene.',
             'One screenshot per successful mode, after measurement. Hidden-window timings are not visible gameplay benchmarks.', '',
             'Compatibility is the primary outcome: installer detection, loaded ReShade/addon, backend execution and changed presented pixels. FPS is supplementary.', '',
             '| Fixture | Detected API | Outcome | NVIDIA / Phoenix execution | Native FPS | NVIDIA fresh / game-loop FPS | Phoenix fresh / game-loop FPS |',
             '| --- | --- | --- | --- | ---: | ---: | ---: |']
    def number(value):
        return f'{value:.2f}' if isinstance(value, (int,float)) else '-'
    for row in rows:
        modes = row['modes']
        values = [number(modes['native']['game_fps'])]
        for name in ('nvidia', 'phoenix'):
            values.append(number(modes[name]['neural_fps']) + ' / ' + number(modes[name]['game_fps']))
        outcome = ', '.join(name + ': ' + data['outcome'] for name,data in modes.items())
        execution = ' / '.join(modes[name].get('execution') or '-' for name in ('nvidia', 'phoenix'))
        lines.append('| ' + ' | '.join([row['id'], row.get('detected_api') or '-', outcome, execution, *values]) + ' |')
    errors = [(r['id'], name, m['error']) for r in rows for name,m in r['modes'].items() if m.get('error')]
    if errors:
        lines += ['', '## Failures', '']
        lines += [f'- {fixture}, {mode}: {error}' for fixture,mode,error in errors]
    (output / 'summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    compatibility = ['# Current compatibility results', '',
        'Installer detection, deployed hook and runtime delivery are the primary checks. FPS is supplementary in summary.md.',
        'Each successful mode retains one screenshot. Failed modes retain no screenshots or FPS.',
        'These are synthetic API fixtures, not a claim that every real game using an API works.', '',
        '`in_process` means inside the game/DOSBox process; `helper` means the private background host.', '',
        '| Fixture | Detected API | Installed Hook | Captured API | NVIDIA | Phoenix | NVIDIA / Phoenix Execution | Notes |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in rows:
        modes = row['modes']
        plan = row['installation_plan']
        hook = plan.get('Proxy') or ('Vulkan layer' if plan else '-')
        if row['id']=='dos-vga':
            hook = 'DOSBox Enhanced built-in D3D12 (no ReShade)'
        execution = ' / '.join(modes[name].get('execution') or '-' for name in ('nvidia','phoenix'))
        notes = 'ReShade 4.3 compatibility context; requested 3.3 core' if any(m.get('reshade_profile_upgrade') for m in modes.values()) else ''
        captured_api = ' / '.join(sorted({m['runtime_api'] for m in modes.values() if m.get('runtime_api')})) or '-'
        if any(m.get('renderer_backend')=='Vulkan' and m.get('runtime_api')=='Direct3D 12' for m in modes.values()):
            notes = 'ANGLE Vulkan renderer; DirectX 12 presentation captured'
        if row['id']=='dos-vga': notes = '320x200 VGA; native FPS uses guest clock, enhanced FPS uses host wall time; not a Windows benchmark'
        if plan and row['id'].startswith('glide'):
            notes = 'Native Glide 856x480; legacy API mode, not 1080p'
        details = sorted({m['failure_detail'] for m in modes.values() if m.get('failure_detail')})
        notes = '; '.join(filter(None, [notes, *details]))
        compatibility.append('| ' + ' | '.join([row['id'], row.get('detected_api') or '-', hook, captured_api,
            modes['nvidia']['outcome'], modes['phoenix']['outcome'], execution, notes]) + ' |')
    if errors:
        compatibility += ['', '## Failures', '']
        compatibility += [f'- {fixture}, {mode}: {error}' for fixture,mode,error in errors]
    (output / 'compatibility.md').write_text('\n'.join(compatibility)+'\n', encoding='utf-8')
    print(json.dumps(counts))
    return counts


if __name__ == '__main__':
    summarize()
