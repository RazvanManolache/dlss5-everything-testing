"""Rebuild both sets with temporary staging and no retained build history."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys,tempfile
from publish_sets import ROOT,load_config,publish,write_json
from capture_options import schedule,native_arguments


def run(*arguments):
    subprocess.run([sys.executable,*map(str,arguments)],check=True,cwd=ROOT)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--validate',action='store_true',help='Explicitly run game checks; temporary screenshots are removed afterwards')
    p.add_argument('--only',nargs='+',help='Rebuild selected IDs and update both sets')
    p.add_argument('--assets',action='store_true',help='Regenerate assets and rebuild every fixture')
    p.add_argument('--config',type=Path,default=ROOT/'build-sets.json')
    p.add_argument('--test-seconds',type=float,default=30)
    p.add_argument('--test-capture-at',action='append')
    p.add_argument('--jobs',type=int,choices=range(1,5),default=3)
    a=p.parse_args()
    if a.assets and a.only:p.error('--assets requires a full build')
    try:
        if a.test_seconds<=0:raise ValueError('Test duration must be positive')
        times=schedule(a.test_seconds,a.test_capture_at or [','.join(format(a.test_seconds*f,'.12g') for f in (1/6,1/2,5/6))])
    except ValueError as error:p.error(str(error))
    config=load_config(a.config);state=ROOT/'state';state.mkdir(exist_ok=True)
    clean=config['clean_suite'];dos_requested=not a.only or 'dos-vga' in a.only
    only=[key for key in a.only if key!='dos-vga'] if a.only else None
    build=ROOT/'build';build.mkdir(exist_ok=True)
    # Staging, objects, wrapper copies and validation images disappear on success or failure.
    with tempfile.TemporaryDirectory(prefix='work-',dir=build) as temporary:
        work=Path(temporary)
        if a.only and not only:
            run(ROOT/'tools/build_dos.py','--config',a.config)
            if a.validate:
                output=work/'dos'
                run(ROOT/'tools/run_dos.py','--suite',clean,'--background','--seconds',a.test_seconds,*native_arguments(times),'--output',output)
                report=json.loads((output/'verification.json').read_text());report['captures_retained']=False
                write_json(state/'dos-validation.json',report)
            print('Both DOS sets updated; temporary outputs removed.',flush=True)
            return
        matrix=json.loads((clean/'matrix.json').read_text());ids={g['id'] for g in matrix['games']}
        if only and not set(only)<=ids:p.error('Unknown fixture ID')
        previous=json.loads(config['validation'].read_text()) if config['validation'].is_file() else {'results':[]}
        stage=work/'stage';release=work/'release'
        run(ROOT/'tools/clean_stage.py',clean,stage,'--assets-source',build/'scene')
        command=[ROOT/'tools/build.py','--expand','--destination',stage,'--shared-assets']
        if only:command+=['--only',*only]
        if a.assets:command+=['--assets']
        run(*command)
        report={'passed':True,'scope':'build files only','runtime_tests_run':False,'results':[]}
        matched=work/'matched'
        if a.validate:
            selected=['--only',*only] if only else []
            command=[ROOT/'tools/verify.py','--suite',stage,'--background','--frames','30','--mode','matched','--output',matched,*selected]
            if only and 'dx11-x64' not in only:command+=['--reference',config['matched_reference']]
            run(*command)
            showcase=work/'showcase'
            if a.jobs>1:
                run(ROOT/'tools/validate_background.py','--suite',stage,'--only',*(only or sorted(ids)),'--matched-results',matched,'--output',showcase,'--jobs',a.jobs,'--seconds',a.test_seconds,*native_arguments(times))
            else:
                run(ROOT/'tools/run_background.py','--suite',stage,'--mode','showcase','--fixed-time','--matched-results',matched,'--output',showcase,'--seconds',a.test_seconds,*native_arguments(times),*selected)
            results={(r['id'],r['mode']):r for r in previous.get('results',[])}
            for mode,directory in (('matched',matched),('showcase',showcase)):
                checked=json.loads((directory/'verification.json').read_text())
                if not checked['passed']:raise RuntimeError('Validation failed: '+mode)
                for record in checked['results']:
                    required='matching_scene_view' if mode=='matched' else 'showcase_changes_rendered_pixels'
                    if not record['checks'].get(required):raise RuntimeError('Missing visual comparison: '+record['id'])
                    record.update(mode=mode,captures_retained=False);record.pop('source_evidence',None)
                    results[(record['id'],mode)]=record
            ordered=[]
            current=json.loads((stage/'matrix.json').read_text())
            for game in current['games']:
                for mode in ('matched','showcase'):
                    record=results.get((game['id'],mode),{})
                    if not record.get('passed') or record.get('sha256')!=game['sha256']:
                        raise RuntimeError('Missing current validation: '+game['id']+' '+mode+'; a full --validate build is required')
                    ordered.append(record)
            report={'passed':True,'runtime_tests_run':True,'captures_retained':False,'tested_games':len(current['games']),'native_runs':len(ordered),'results':ordered}
        run(ROOT/'tools/clean_stage.py',stage,release)
        run(ROOT/'tools/seal_baseline.py','--replace-from',release)
        validation=state/'validation.json';write_json(validation,report)
        publish(release,validation,a.config,state/'publication.json',build_only=not a.validate)
        if dos_requested:
            run(ROOT/'tools/build_dos.py','--config',a.config)
            if a.validate:
                output=work/'dos'
                run(ROOT/'tools/run_dos.py','--suite',clean,'--background','--seconds',a.test_seconds,*native_arguments(times),'--output',output)
                checked=json.loads((output/'verification.json').read_text());checked['captures_retained']=False
                write_json(state/'dos-validation.json',checked)
        reference=matched/'dx11-x64/capture.png'
        if reference.is_file():shutil.copy2(reference,state/'matched-reference.png')
        updated=json.loads(a.config.read_text())
        updated['matched_reference']='state/matched-reference.png'
        write_json(a.config,updated)
    print('Both sets updated; staging removed. '+('Runtime checks completed.' if a.validate else 'No games launched.'),flush=True)


if __name__=='__main__':main()
