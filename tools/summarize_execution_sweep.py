"""Summarize execution-labelled scores without launching games or inference."""
import collections
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

from run_backends import ROOT, read, write

OUTPUT=ROOT/'runs/latest-x64-backends'
ROUTES={'helper':'External x64 helper','x64-library':'x64 library inside x86',
        'x86-driver':'x86 Phoenix + native driver'}
EXPECTED={'helper':'helper','x64-library':'in_process_x64_library','x86-driver':'in_process_x86_driver'}


def positive(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0


def compare_images(rows):
    import numpy as np
    from PIL import Image
    comparisons=[]
    for backend in ('phoenix','nvidia'):
        fixtures=collections.defaultdict(dict)
        for row in rows:
            if row['architecture']=='x86' and row['backend']==backend and row.get('passed'):
                captures=read(ROOT/row['result_directory']/'captures.json').get('captures') or []
                if len(captures)==1:
                    fixtures[row['id']][row['variant']]=ROOT/row['result_directory']/captures[0]['png']
        for fixture,images in fixtures.items():
            if 'x64-library' not in images:continue
            with Image.open(images['x64-library']) as image:reference=np.asarray(image.convert('RGB')).astype(np.int16)
            h,w=reference.shape[:2]
            for variant,path in images.items():
                if variant=='x64-library':continue
                with Image.open(path) as image:tested=np.asarray(image.convert('RGB')).astype(np.int16)
                if tested.shape!=reference.shape:continue
                delta=np.abs(tested[h//4:3*h//4,w//4:3*w//4]-reference[h//4:3*h//4,w//4:3*w//4])
                comparisons.append(dict(id=fixture,backend=backend,variant=variant,reference_variant='x64-library',
                    central_mae=float(delta.mean()),central_p99=float(np.percentile(delta,99)),
                    central_changed_fraction_gt2=float((delta.max(axis=2)>2).mean()),
                    identical_file=path.read_bytes()==images['x64-library'].read_bytes()))
    geometry=[]
    for row in rows:
        if not row.get('passed') or row['backend']=='native':continue
        folder=ROOT/row['result_directory']
        tested=read(folder/'captures.json').get('captures') or []
        native_folder=folder.parent/'native'
        original=read(native_folder/'captures.json').get('captures') or []
        if len(tested)!=1 or len(original)!=1:continue
        with Image.open(folder/tested[0]['png']) as image:
            frame=np.asarray(image.convert('RGB').resize((160,90),Image.Resampling.BILINEAR)).astype(float)
        with Image.open(native_folder/original[0]['png']) as image:
            reference=np.asarray(image.convert('RGB').resize((160,90),Image.Resampling.BILINEAR)).astype(float)
        transforms={'original':frame,'vertical_flip':frame[::-1], 'horizontal_flip':frame[:,::-1],
                    'both_flips':frame[::-1,::-1],'red_blue_swap':frame[:,:,::-1]}
        errors={name:float(np.abs(value-reference).mean()) for name,value in transforms.items()}
        best=min(errors,key=errors.get)
        flagged=best!='original' and errors[best]<.7*errors['original'] and errors['original']-errors[best]>3
        geometry.append(dict(id=row['id'],backend=row['backend'],variant=row['variant'],
            low_resolution_mae=errors,closest_transform=best,possible_orientation_or_channel_error=flagged))
    write(OUTPUT/'route-image-comparison.json',dict(comparisons=comparisons,geometry_checks=geometry,
        note='Frozen-scene pixel comparison, not a perceptual quality or gameplay temporal metric.'))
    return comparisons


def summarize(images=False):
    from benchmark_errors import failure_reason
    games={g['id']:g for g in read(ROOT/'matrix.json')['games']}
    rows=[]
    for path in sorted(OUTPUT.glob('*/*/result.json')):
        row=read(path)
        row['error']=failure_reason(row)
        if row.get('id') not in games: continue
        row['architecture']=games[row['id']]['architecture']
        row['result_directory']=path.parent.relative_to(ROOT).as_posix()
        row['variant']=row.get('execution_variant') or ('baseline' if row.get('backend')=='native' else 'auto')
        row['outcome']='not_applicable' if row.get('applicable') is False else 'passed' if row.get('passed') is True else 'failed' if row.get('passed') is False else 'pending'
        row['startup_in_measurement']=(row.get('backend')!='native' and
            positive(row.get('first_ready_render_seconds')) and
            row['first_ready_render_seconds'] > row.get('warmup_seconds',5))
        row['output_interval_ms']=1000/row['neural_fps'] if row.get('passed') and positive(row.get('neural_fps')) else None
        rows.append(row)
    groups=collections.defaultdict(list)
    for row in rows: groups[(row['architecture'],row['backend'],row['variant'])].append(row)
    totals=[]
    for (arch,backend,variant),members in groups.items():
        good=[r for r in members if r['outcome']=='passed']
        rates=[r['neural_fps'] for r in good if positive(r.get('neural_fps'))]
        totals.append(dict(architecture=arch,backend=backend,variant=variant,
            passed=len(good),failed=sum(r['outcome']=='failed' for r in members),
            not_applicable=sum(r['outcome']=='not_applicable' for r in members),
            mean_processed_fps=statistics.mean(rates) if rates else None,
            mean_output_interval_ms=statistics.mean(1000/v for v in rates) if rates else None))
    ranking=[]
    for backend,variants in [('phoenix',list(ROUTES)),('nvidia',['helper','x64-library'])]:
        indexed={(r['id'],r['variant']):r for r in rows if r['architecture']=='x86' and r['backend']==backend}
        matched=[]
        for key in [g for g,v in games.items() if v['architecture']=='x86']:
            candidates=[indexed.get((key,variant),{}) for variant in variants]
            if not all(r.get('passed') and positive(r.get('neural_fps')) and r.get('execution_mode')==EXPECTED[v]
                       for r,v in zip(candidates,variants)): continue
            contexts=[(r.get('executable_sha256'),r.get('profile'),r.get('width'),r.get('height'),
                       r.get('warmup_seconds'),r.get('requested_seconds'),r.get('vsync'),r.get('addon_sha256')) for r in candidates]
            if len(set(contexts))!=1: continue
            matched.append((key,dict(zip(variants,candidates))))
        for variant in variants:
            rates=[cases[variant]['neural_fps'] for _,cases in matched]
            ratios=[cases[variant]['neural_fps']/cases['helper']['neural_fps'] for _,cases in matched]
            ranking.append(dict(backend=backend,variant=variant,label=ROUTES[variant],matched_fixtures=len(matched),
                mean_processed_fps=statistics.mean(rates) if rates else None,
                geometric_speedup_vs_helper=math.exp(statistics.mean(math.log(r) for r in ratios)) if ratios else None,
                startup_affected=sum(bool(cases[variant].get('startup_in_measurement')) for _,cases in matched),
                wins=sum(cases[variant]['neural_fps']>=max(r['neural_fps'] for r in cases.values())*.99 for _,cases in matched)))
    previous=read(ROOT/'state/previous-execution-scores.json').get('scores',[])
    previous={(r.get('id'),r.get('backend')):r for r in previous}
    comparisons=[]
    for row in rows:
        if row['backend']!='native' and row['architecture']!='x64':continue
        if row['variant'] not in ('auto','baseline'):continue
        old=previous.get((row['id'],row['backend']))
        if not old:continue
        comparable=all(row.get(k)==old.get(k) for k in ('executable_sha256','profile','width','height'))
        field='game_fps' if row['backend']=='native' else 'neural_fps'
        # Older clean records used average_fps before game_fps was named
        # explicitly. This alias is safe only for unmodified native baselines.
        a=old.get(field,old.get('average_fps') if row['backend']=='native' else None)
        b=row.get(field)
        delta=100*(b/a-1) if comparable and old.get('passed') and row.get('passed') and positive(a) and positive(b) else None
        comparisons.append(dict(id=row['id'],backend=row['backend'],old_passed=old.get('passed'),
            passed=row.get('passed'),comparable_profile=comparable,metric=field,
            old_fps=a if old.get('passed') else None,new_fps=b if row.get('passed') else None,change_percent=delta,
            old_execution=old.get('execution_mode'),execution=row.get('execution_mode')))
    counts=dict(collections.Counter(r['outcome'] for r in rows))
    dos=[]
    for path in sorted((OUTPUT/'dos-vga').glob('*/result.json')):
        row=read(path)
        if row.get('id')!='dos-vga':continue
        row.update(architecture='dos',variant='baseline' if row.get('backend')=='native' else 'dos-integrated',
            execution_label='DOS guest baseline' if row.get('backend')=='native' else 'DOSBox integrated renderer',
            outcome='passed' if row.get('passed') is True else 'failed' if row.get('passed') is False else 'pending')
        dos.append(row)
    failures=[{k:r.get(k) for k in ('id','backend','variant','outcome','error','execution_mode','requested_execution_mode')}
              for r in rows if r['outcome'] in ('failed','not_applicable')]
    report=dict(schema='execution-comparison/1',hardware=read(ROOT/'state/execution-hardware.json'),counts=counts,totals=totals,matched_x86_rankings=ranking,dos_results=dos,
        previous_native_x64_comparison=comparisons,failures=failures,
        timing_note='Processed FPS counts fresh completed outputs. Output interval is 1000/FPS, not isolated GPU inference latency. Rankings use the same successful fixture set across each backend\'s required routes. The window starts after 5 fixture seconds, not 5 seconds after renderer readiness; startup_in_measurement flags initialization extending into that window.',
        regression_note='Single serial 20s measurement per case; changes versus previous scores are observations, not statistical regressions or proof of equal visual quality.')
    if images:report['route_output_comparison']=compare_images(rows)
    write(OUTPUT/'execution-comparison.json',report)
    fields=['id','architecture','backend','variant','execution_label','outcome','execution_mode','first_ready_render_seconds','startup_in_measurement','game_fps','neural_fps','output_interval_ms','average_fps','fps_scope','width','height','vsync','error']
    with (OUTPUT/'execution-scores.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows+dos)
    lines=['# Current Execution Sweep','',report['timing_note'],'',report['regression_note'],'',
        '| Architecture | Renderer | Requested execution | Passed | Failed | Not applicable | Mean processed FPS (successful only) |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    def n(value):return f'{value:.2f}' if positive(value) else '-'
    for row in totals:
        lines.append(f"| {row['architecture']} | {row['backend']} | {ROUTES.get(row['variant'],row['variant'])} | {row['passed']} | {row['failed']} | {row['not_applicable']} | {n(row['mean_processed_fps'])} |")
    lines+=['','## Matched x86 Route Comparison','',
        'Failures are excluded, not zero-valued. These rows use the same passing fixtures for every route within each renderer.',
        '', '| Renderer | Route | Matched fixtures | Mean processed FPS | Geometric speed vs helper | Fastest or within 1% | Startup affected |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for row in ranking:
        lines.append(f"| {row['backend']} | {row['label']} | {row['matched_fixtures']} | {n(row['mean_processed_fps'])} | {n(row['geometric_speedup_vs_helper'])} | {row['wins']} | {row['startup_affected']} |")
    if dos:
        lines+=['','## DOS Compatibility Check','',
            'Separate 320x200 emulation test, excluded from all Windows totals and route rankings. The native rate uses the DOS guest clock; enhanced rates use host wall time with VSync. Do not interpret these as a speedup over native DOS.',
            '', '| Renderer | Outcome | Rate | Measurement scope |', '| --- | --- | ---: | --- |']
        for row in dos:
            lines.append(f"| {row['backend']} | {row['outcome']} | {n(row.get('average_fps'))} | {row.get('fps_scope') or row.get('error') or '-'} |")
    lines+=['','## Changes From Previous Native/x64 Scores','',
        '| Fixture | Renderer | Previous FPS | Current FPS | Change |', '| --- | --- | ---: | ---: | ---: |']
    for row in comparisons:
        delta=f"{row['change_percent']:+.1f}%" if row['change_percent'] is not None else 'Not comparable / failed'
        lines.append(f"| {row['id']} | {row['backend']} | {n(row['old_fps'])} | {n(row['new_fps'])} | {delta} |")
    lines+=['','## Failures and Unavailable Combinations','']
    lines += [f"- {r['id']}, {r['backend']}, {r['variant']} ({r['outcome']}): {str(r['error']).replace(chr(10),' ')}" for r in failures]
    (OUTPUT/'execution-comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # The older three-mode summary cannot represent separate x86 transports.
    write(OUTPUT/'summary.json',dict(schema='execution-summary-index/1',
        report='execution-comparison.json',scores='execution-scores.csv',counts=counts,
        dos_counts=dict(collections.Counter(r['outcome'] for r in dos))))
    index='# Execution Sweep Results\n\nSee [the complete execution comparison](execution-comparison.md) and [all scores](execution-scores.csv).\n\nThe complete report separates x86 transports, failed cases, and DOS clocks.\n'
    for name in ('summary.md','compatibility.md'):
        (OUTPUT/name).write_text(index,encoding='utf-8')
    print(json.dumps(dict(counts=counts,ranking=ranking)))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images',action='store_true',help='Also compare frozen outputs between execution routes')
    summarize(parser.parse_args().images)
