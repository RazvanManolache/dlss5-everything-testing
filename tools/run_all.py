"""Run Windows and DOS fixtures with one shared duration and screenshot schedule."""
from pathlib import Path
import argparse,datetime,json,subprocess,sys
from capture_options import add_arguments,schedule,native_arguments
from publish_sets import ROOT,write_json
from storage_policy import latest_output
from control_options import add_control_arguments,control_arguments


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',type=Path,default=ROOT)
    p.add_argument('--only',nargs='+')
    p.add_argument('--list',action='store_true')
    p.add_argument('--seconds',type=float,default=30)
    add_arguments(p)
    p.add_argument('--mode',choices=['matched','showcase'],default='showcase')
    p.add_argument('--fixed-time',action='store_true')
    p.add_argument('--allow-installed',action='store_true')
    p.add_argument('--output',type=Path,default=None)
    add_control_arguments(p)
    a=p.parse_args();suite=a.suite.resolve()
    games=json.loads((suite/'matrix.json').read_text())['games']
    ids=[g['id'] for g in games]+(['dos-vga'] if (suite/'games/dos-vga/MUSEUM.EXE').is_file() else [])
    if a.only and not set(a.only)<=set(ids):p.error('Unknown fixture ID')
    chosen=[key for key in ids if not a.only or key in a.only]
    if a.list:
        print('\n'.join(chosen));return
    try:
        if a.seconds<=0:raise ValueError('Timed runs require positive --seconds')
        times=schedule(a.seconds,a.capture_at,a.capture_every)
    except ValueError as error:p.error(str(error))
    a.output=latest_output(a.output,'latest')
    if a.output.exists() and any(a.output.iterdir()):p.error('Choose a new empty result folder')
    a.output.mkdir(parents=True,exist_ok=True);results=[];errors=[]
    common=['--suite',str(suite),'--seconds',str(a.seconds),*native_arguments(times),'--mode',a.mode]
    common+=control_arguments(a)
    if a.fixed_time:common+=['--fixed-time']
    windows=[key for key in chosen if key!='dos-vga']
    if windows:
        folder=(a.output/'windows').resolve()
        command=[sys.executable,str(ROOT/'tools/run_background.py'),*common,'--only',*windows,'--output',str(folder)]
        if a.allow_installed:command+=['--allow-installed']
        code=subprocess.run(command).returncode
        if (folder/'verification.json').exists():
            for record in json.loads((folder/'verification.json').read_text())['results']:
                record['result_directory']=str(folder/record['id']);results.append(record)
        if code:errors.append('Windows runner failed')
    if 'dos-vga' in chosen:
        folder=(a.output/'dos-vga').resolve()
        code=subprocess.run([sys.executable,str(ROOT/'tools/run_dos.py'),*common,'--background','--output',str(folder)]).returncode
        if (folder/'verification.json').exists():
            record=json.loads((folder/'verification.json').read_text());record.update(id='dos-vga',result_directory=str(folder));results.append(record)
        if code:errors.append('DOS runner failed')
    report={'passed':not errors and len(results)==len(chosen) and all(r['passed'] for r in results),
            'requested_games':chosen,'seconds_per_game':a.seconds,'capture_times_seconds':times,
            'scope':'Sequential hidden runs; Windows and DOS FPS describe different execution environments',
            'errors':errors,'results':results}
    write_json(a.output/'verification.json',report)
    print('All-platform run','PASS' if report['passed'] else 'FAIL',len(results),'games:',a.output.resolve(),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
