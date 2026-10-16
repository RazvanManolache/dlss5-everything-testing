"""Build a genuine DOS VGA fixture and publish it to both configured sets."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile
from publish_sets import ROOT,load_config,write_json
from asset_paths import point_assets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'build-sets.json')
    args=parser.parse_args()
    subprocess.run([sys.executable,str(ROOT/'tools/export_dos.py')],check=True)
    gcc=ROOT/'vendor/dos/djgpp/djgpp/bin/i586-pc-msdosdjgpp-gcc.exe'
    subprocess.run([str(gcc),'-O2','-march=i386','-fomit-frame-pointer','-Wall','-Werror',
                    '-Wno-misleading-indentation',str(ROOT/'dos/museum.c'),'-o',
                    str(ROOT/'dos/MUSEUM.EXE'),'-lm'],check=True)
    config=load_config(args.config)
    publish_artifacts(config)


def publish_artifacts(config):
    for kind in ('clean','reshade'):
        folder=config[kind+'_suite']/'games/dos-vga';folder.mkdir(parents=True,exist_ok=True)
        for src,name in [(ROOT/'dos/MUSEUM.EXE','MUSEUM.EXE'),
                         (ROOT/'vendor/dos/cwsdpmi/bin/CWSDPMI.EXE','CWSDPMI.EXE'),
                         (ROOT/'vendor/dos/cwsdpmi/bin/cwsdpmi.doc','CWSDPMI.TXT'),
                         (ROOT/'dos/README.TXT','README.TXT'),
                         (ROOT/'dos/DJGPP.TXT','DJGPP.TXT'),
                         (ROOT/'dos/LIBCOPY.TXT','LIBCOPY.TXT'),
                         (ROOT/'dos/GPLCOPY.TXT','GPLCOPY.TXT')]:
            shutil.copy2(src,folder/name)
        suite=config[kind+'_suite']
        point_assets(suite,ROOT/'dos/assets',dos=True)
        script=os.path.relpath(ROOT/'tools/run_dos.py',folder)
        launcher='@echo off\r\npython "%~dp0'+script+'" --suite "%~dp0..\\.." %*\r\n'
        (folder/'RUN.cmd').write_text(launcher)
        write_json(folder/'test-game.json',{'id':'dos-vga','platform':'DOS','architecture':'i386',
                   'fixture_version':6,'configurable_duration':True,'multiple_screenshots':True,
                   'capture_options':['--capture-at','--capture-every'],
                   'controls':{'freeze':'F / Space','movement':'WASD / arrows; Q down, E up','look':'IJKL','orbit':'O; W/S zoom','animations':'T lighting, B camera motion','command_line':['--freeze','--orbit','--camera free|orbit','--animations on|off','--camera-motion on|off']},
                   'api':'VGA BIOS / CPU software renderer','executable':'MUSEUM.EXE',
                   'resolution':[320,200],'palette_colors':256,
                   'sha256':hashlib.sha256((folder/'MUSEUM.EXE').read_bytes()).hexdigest(),
                   'asset_source':os.path.relpath(ROOT/'dos/assets',folder),'windows_api_matrix':False})
        print('Published DOS VGA:',folder,flush=True)
    archive=ROOT/'dos/MUSEUM-DOS.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in ('MUSEUM.EXE','CWSDPMI.EXE','CWSDPMI.TXT','README.TXT','DJGPP.TXT','LIBCOPY.TXT','GPLCOPY.TXT'):z.write(folder/name,name)
        for asset in sorted((ROOT/'dos/assets').rglob('*')):
            if asset.is_file():z.write(asset,'ASSETS/'+asset.relative_to(ROOT/'dos/assets').as_posix())
        z.write(ROOT/'dos/museum.c','SOURCE/MUSEUM.C')
    (ROOT/'dos/MUSEUM-DOS.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  MUSEUM-DOS.zip\n')
    print('Portable DOS package:',archive,archive.stat().st_size,'bytes',flush=True)


if __name__=='__main__':main()
