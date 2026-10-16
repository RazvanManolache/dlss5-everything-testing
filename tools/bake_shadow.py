"""Rasterize a 16-bit key-light depth map from the actual high-detail geometry."""
from pathlib import Path
import hashlib,json,struct,subprocess,tempfile,sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def main():
    with tempfile.TemporaryDirectory(prefix='shadow-',dir=ROOT/'build') as temporary:
        stage=Path(temporary)/'stage';out=Path(temporary)/'capture'
        subprocess.run([sys.executable,str(ROOT/'tools/build.py'),'--destination',str(stage),'--only','dx11-x64','--shared-assets'],check=True)
        exe=stage/'games/dx11-x64/Museum_dx11_x64.exe'
        subprocess.run([str(exe),'--bake-shadow','--windowed','--width','2048','--height','2048','--frames','1','--capture-frame','1','--fixed-time','--output',str(out)],check=True,timeout=60)
        im=Image.open(out/'capture.ppm').convert('RGBA')
    if im.size!=(2048,2048):raise RuntimeError('Shadow target must be exactly 2048 x 2048')
    target=ROOT/'build/scene/key-shadow.rgba';target.write_bytes(struct.pack('<II',*im.size)+im.tobytes())
    (ROOT/'build/scene/key-shadow.json').write_text(json.dumps({'source':'Native D3D11 rasterization of the full LOD0 museum with alpha-tested hair','width':2048,'height':2048,'encoding':'R is the high byte; G is the low byte of a 16-bit normalized depth','eye':[4.4,2.9,5.3],'target':[2.3,1.4,3.8],'fov_radians':1.91986218,'near':.05,'far':40,'scene_sha256':hashlib.sha256((ROOT/'build/scene/museum.bin').read_bytes()).hexdigest(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},indent=2))
    print('Baked native geometry shadow map:',target)
if __name__=='__main__':main()
