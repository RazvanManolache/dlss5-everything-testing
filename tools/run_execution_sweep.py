"""Update fixtures with the real installer, then compare x64 and three x86 routes."""
import argparse
import configparser
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import run_backends as runner
from run_backends import ROOT, read, write, digest, emit, desired_extent

OUTPUT = ROOT/'runs/latest-x64-backends'
VARIANTS = {
    'helper': ('External x64 helper', 'helper', 'helper'),
    'x64-library': ('x64 library inside x86', 'wow64_library', 'in_process_x64_library'),
    'x86-driver': ('x86 Phoenix + native driver', 'wow64_driver', 'in_process_x86_driver'),
}


def prepare_payload(payload, candidate):
    hashes = read(candidate/'FILES_SHA256.json')
    for name in ('Phoenix.addon32', 'Phoenix.addon64'):
        if digest(candidate/name) != hashes.get(name):
            raise ValueError('Candidate hash mismatch: '+name)
        shutil.copy2(candidate/name, payload/name)
    companion = digest(candidate/'Phoenix.addon32')
    relative = f'phoenix-companions/{companion}/Phoenix.addon32'
    destination = payload/relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate/'Phoenix.addon32', destination)
    release = read(payload/'phoenix-release.json')
    release.update(Source=(candidate/'Phoenix.addon64').as_uri(), Version='0.81',
        Size=(candidate/'Phoenix.addon64').stat().st_size,
        Sha256=digest(candidate/'Phoenix.addon64').upper(), IsDevelopment=True,
        Companion32Path=relative, Companion32Sha256=companion.upper(),
        Companion32Size=destination.stat().st_size)
    write(payload/'phoenix-release.json', release)
    return hashes


def configure(folder, backend, variant):
    runner.ini_backend(folder, 1 if backend == 'nvidia' else 3)
    for name in ('ReShade.ini', 'ReShadeVR.ini'):
        path = folder/name
        cfg = configparser.ConfigParser(interpolation=None, strict=False)
        cfg.optionxform = str
        cfg.read(path, encoding='utf-8-sig')
        cfg['Phoenix'].update(ExecutionDevice='native', Experimental='0',
            AutomaticBudget='0', TransformerBlocks='8', RefinementPasses='1',
            **{f'Block{i}Repeats':'1' for i in range(1,9)})
        if not cfg.has_section('Phoenix.Compatibility'):
            cfg.add_section('Phoenix.Compatibility')
        cfg['Phoenix.Compatibility'].update(Enabled='1', CoherentFrames='1',
            ExecutionMode=VARIANTS[variant][1] if variant in VARIANTS else 'auto',
            NativeRuntime='PhoenixRuntime\\wow64', NativeFallback='0' if variant in VARIANTS else '1')
        with path.open('w', encoding='utf-8') as stream:
            cfg.write(stream)


def previous_scores():
    return [dict(relative=p.parent.relative_to(OUTPUT).as_posix(), **{
        k:v for k,v in read(p).items() if k in ('id','backend','passed','average_fps','game_fps',
        'neural_fps','profile','execution_mode','executable_sha256','addon_sha256','width','height','error')})
        for p in OUTPUT.glob('**/result.json')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--only', nargs='+')
    parser.add_argument('--stage', choices=('all','baseline','x64','x86'), default='all')
    args = parser.parse_args()
    installer, payload, candidate = [p.resolve() for p in (args.installer,args.payload,args.candidate)]
    if not installer.is_file() or not payload.is_dir() or not candidate.is_dir():
        raise ValueError('Installer/payload/candidate are missing')
    hashes = prepare_payload(payload,candidate)
    if not args.resume:
        write(ROOT/'state/previous-execution-scores.json',dict(scores=previous_scores()))
        runner.latest_output(None,'latest-x64-backends')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if (OUTPUT/'STOP').exists():
        (OUTPUT/'STOP').unlink()
    games = [g for g in read(ROOT/'matrix.json')['games'] if not args.only or g['id'] in args.only]
    games.sort(key=lambda g: (g['id'] not in ('dx12-x64','dx12-x86'), g['id']))
    report = read(OUTPUT/'execution-sweep.json') if args.resume else {}
    report.update(schema='phoenix-execution-sweep/1', addon_release='0.81',
        started=report.get('started',time.strftime('%Y-%m-%dT%H:%M:%S%z')),
        installer_sha256=digest(installer), candidate_sha256=hashes,
        warmup_seconds=5, measured_seconds=20, pending=True)
    report.setdefault('installations',{})
    def save(stage):
        report['stage']=stage
        report['updated']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
        rows=[read(p) for p in OUTPUT.glob('*/*/result.json')]
        report['counts']={name:sum(r.get('passed') is value and r.get('applicable',True) for r in rows)
                          for name,value in [('passed',True),('failed',False)]}
        report['counts']['not_applicable']=sum(r.get('applicable') is False for r in rows)
        write(OUTPUT/'execution-sweep.json',report)
        from dashboard import export_snapshot
        export_snapshot()
    def cli(game, operation):
        folder=OUTPUT/game['id'];folder.mkdir(exist_ok=True)
        exe=ROOT/game['executable']
        command=[str(installer),operation,str(exe)]
        if operation=='--inspect': command+=['--output',str(folder/'inventory.json'),'--payload',str(payload)]
        else: command+=['--payload',str(payload),'--offline']
        result=subprocess.run(command,cwd=installer.parent,capture_output=True,text=True,timeout=180)
        (folder/('inspect.log' if operation=='--inspect' else 'install.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        return result
    for game in games:
        folder=ROOT/game['install_directory'];clean=ROOT/'clean'/game['executable']
        if not folder.resolve().is_relative_to(ROOT/'games') or digest(ROOT/game['executable'])!=game['sha256'] or digest(clean)!=game['sha256']:
            raise ValueError('Working/clean fixture identity mismatch: '+game['id'])
        if any(clean.parent.glob('*.addon*')) or (clean.parent/'Phoenix.json').exists():
            raise ValueError('Baseline is not clean: '+game['id'])
        prior=report['installations'].get(game['id'],{})
        addon_name='Phoenix.addon32' if game['architecture']=='x86' else 'Phoenix.addon64'
        if args.resume and prior.get('inspection_passed'):
            native_files={n:v for n,v in hashes.items() if n.startswith('PhoenixRuntime/wow64/')}
            native_current=game['architecture']!='x86' or all((folder/n).is_file() and digest(folder/n)==v for n,v in native_files.items())
            if not prior.get('passed') or native_current and (folder/addon_name).is_file() and digest(folder/addon_name)==hashes[addon_name]:
                continue
        inspected=cli(game,'--inspect')
        installed=cli(game,'--install') if inspected.returncode==0 else inspected
        item=dict(attempted=True,inspection_passed=inspected.returncode==0,
            passed=installed.returncode==0,error=((installed.stderr or installed.stdout)[-2000:] or
            f'Installer exited with code {installed.returncode}') if installed.returncode else None)
        if item['passed']:
            addon='Phoenix.addon32' if game['architecture']=='x86' else 'Phoenix.addon64'
            if digest(folder/addon)!=hashes[addon]:
                raise ValueError('Installer did not install current add-on: '+game['id'])
            item['addon_sha256']=hashes[addon]
            if game['architecture']=='x86':
                for name,expected in hashes.items():
                    if name.startswith('PhoenixRuntime/wow64/'):
                        source=candidate/name
                        if digest(source)!=expected: raise ValueError('Optional runtime hash mismatch')
                        destination=folder/name
                        if destination.is_symlink() or destination.is_junction(): raise ValueError('Linked runtime target')
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(source,destination)
                item['optional_runtime_deployment']='Test runner copied hash-verified native x86 package after normal CLI installation; not an installer feature claim.'
        report['installations'][game['id']]=item
        emit(dict(stage='install',id=game['id'],passed=item['passed']))
        save('install')
    stages=['baseline','x64','x86'] if args.stage=='all' else [args.stage]
    for stage in stages:
        save(stage)
        selected=games if stage=='baseline' else [g for g in games if g['architecture']==stage]
        for game in selected:
            if (OUTPUT/'STOP').exists():
                save('stopped');return
            folder=ROOT/game['install_directory'];case=OUTPUT/game['id'];case.mkdir(exist_ok=True)
            game=dict(game,addon_sha256=hashes['Phoenix.addon32' if game['architecture']=='x86' else 'Phoenix.addon64'])
            game['execution_runtime_sha256']=hashes.get('PhoenixRuntime/wow64/bootstrap.json') if game['architecture']=='x86' else None
            cases=[('native','baseline')] if stage=='baseline' else ([('nvidia','auto'),('phoenix','auto')] if stage=='x64' else
                [(backend,variant) for variant in VARIANTS for backend in ('nvidia','phoenix')])
            for backend,variant in cases:
                if (OUTPUT/'STOP').exists():save('stopped');return
                label=VARIANTS[variant][0] if variant in VARIANTS else ('Native baseline' if backend=='native' else 'Automatic x64')
                expected=VARIANTS[variant][2] if variant in VARIANTS else None
                current=dict(game,execution_variant=variant,execution_label=label,expected_execution_mode=expected)
                target=case/(backend if variant in ('baseline','auto') else backend+'-'+variant)
                previous=read(target/'result.json')
                runtime_current=backend=='native' or previous.get('execution_runtime_sha256')==game['execution_runtime_sha256']
                if args.resume and ((runner.current_pass(target/'result.json',game) and previous.get('execution_variant')==variant and runtime_current) or previous.get('applicable') is False):
                    continue
                if backend=='nvidia' and variant=='x86-driver':
                    target.mkdir(exist_ok=True)
                    write(target/'result.json',dict(id=game['id'],backend=backend,execution_variant=variant,
                        execution_label=label,requested_execution_mode=expected,passed=False,applicable=False,
                        state='not_applicable',executable_sha256=game['sha256'],source_suite='working',
                        profile=runner.profile_for(game),width=desired_extent(game)[0],height=desired_extent(game)[1],
                        requested_seconds=20,warmup_seconds=5,vsync=False,
                        error='NVIDIA has no x86 graph host. This route is Phoenix-only; no helper fallback is scored.'))
                    save(stage);continue
                installation=report['installations'][game['id']]
                if backend!='native' and not installation['passed']:
                    target.mkdir(exist_ok=True)
                    failure=runner.failure_record(dict(id=game['id'],backend=backend,execution_variant=variant,
                        execution_label=label,error=installation['error'],source_suite='working',
                        executable_sha256=game['sha256'],profile=runner.profile_for(game),
                        requested_execution_mode=expected,addon_sha256=game['addon_sha256'],
                        width=desired_extent(game)[0],height=desired_extent(game)[1],
                        requested_seconds=20,warmup_seconds=5,vsync=False))
                    write(target/'result.json',failure);save(stage);continue
                environment=os.environ.copy()
                if backend!='native':
                    configure(folder,backend,variant)
                    manifest=read(folder/'_DLSS5_Compat_Backup/manifest.json')
                    environment.update(manifest.get('VulkanLaunchEnvironment') or manifest.get('vulkanLaunchEnvironment') or {})
                runner.run_case(current,backend,(ROOT/'clean'/game['executable']).parent if backend=='native' else folder,
                                target,20,environment)
                save(stage)
    report['pending']=False
    save('complete')
    emit(dict(stage='complete',counts=report['counts']))


if __name__=='__main__':
    main()
