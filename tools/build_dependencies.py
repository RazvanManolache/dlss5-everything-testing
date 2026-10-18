from pathlib import Path
import json
import os
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def dependency(name):
    value=Path(json.loads((ROOT/'build-dependencies.json').read_text())[name])
    return value if value.is_absolute() else ROOT/value

def visual_studio_build():
    override=os.environ.get('VS_BUILD_TOOLS')
    if override:return Path(override)
    locator=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    if locator.is_file():
        installation=subprocess.check_output([str(locator),'-latest','-products','*',
            '-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],
            text=True,timeout=15).strip()
        if installation:return Path(installation)/'VC/Auxiliary/Build'
    raise FileNotFoundError('Install Visual Studio C++ build tools or set VS_BUILD_TOOLS to its VC/Auxiliary/Build folder')
