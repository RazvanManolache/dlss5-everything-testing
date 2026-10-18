"""Run one opt-in fixture under the native debugger; never score a debug run."""
import argparse
import os
from pathlib import Path
import subprocess
import shutil

import psutil
from run_execution_sweep import ROOT, configure, read, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',required=True)
    parser.add_argument('--backend',choices=['phoenix','nvidia'],default='phoenix')
    parser.add_argument('--variant',choices=['x64-library','x86-driver'],required=True)
    parser.add_argument('--refresh-runtime',type=Path,help='Verified optional package beside its local build receipt')
    args=parser.parse_args()
    game=next(g for g in read(ROOT/'matrix.json')['games'] if g['id']==args.fixture)
    exe=ROOT/game['executable']
    if args.refresh_runtime:
        source=args.refresh_runtime.resolve()
        receipt=read(source.parents[2]/'wow64-runtime-build.json')
        if not receipt.get('passed'):raise ValueError('Native build receipt is missing')
        for name,expected in receipt['files'].items():
            path=source/name
            if digest(path)!=expected:raise ValueError('Native package hash mismatch')
            destination=exe.parent/'PhoenixRuntime/wow64'/name
            if destination.is_symlink() or destination.is_junction():raise ValueError('Linked native output')
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,destination)
    configure(exe.parent,args.backend,args.variant)
    debugger=Path(os.environ['ProgramFiles(x86)'])/'Windows Kits/10/Debuggers/x64/cdb.exe'
    log=ROOT/'state/native-fixture-debug.log'
    command='sxd -c2 ".ecxr; r; kv; dt ntdll!_TEB @$teb ThreadLocalStoragePointer; dt ntdll!_PEB @$peb KernelCallbackTable; dps poi(@$peb+0x58) L6; u poi(poi(@$peb+0x58)) L18; q" av;g'
    with log.open('w',encoding='utf-8') as stream:
        process=subprocess.Popen([str(debugger),'-g','-G','-c',command,str(exe),
            '--background','--windowed','--width','1920','--height','1080','--mode','showcase',
            '--fixed-time','--seconds','10','--output',str(ROOT/'state/native-debug-fixture')],
            cwd=exe.parent,stdout=stream,stderr=subprocess.STDOUT)
        try:
            process.wait(90)
        except subprocess.TimeoutExpired:
            for child in psutil.Process(process.pid).children(recursive=True):
                try:child.kill()
                except psutil.Error:pass
            process.kill();process.wait(5)
            raise RuntimeError('Debugger timed out; owned processes stopped')
    print(log.read_text(encoding='utf-8',errors='replace')[-26000:])


if __name__=='__main__':main()
