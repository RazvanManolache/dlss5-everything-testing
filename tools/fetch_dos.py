"""Restore the pinned DOS compiler, emulator and CWSDPMI without global installs."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    vendor=ROOT/'vendor/dos'
    for dependency in json.loads((vendor/'dependencies.json').read_text()):
        archive=vendor/dependency['url'].rsplit('/',1)[-1]
        if not archive.exists():urllib.request.urlretrieve(dependency['url'],archive)
        with archive.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if archive.stat().st_size!=dependency['bytes'] or actual!=dependency['sha256']:
            raise RuntimeError('Pinned dependency checksum mismatch: '+str(archive))
        destination=vendor/dependency['name']
        with zipfile.ZipFile(archive) as z:
            for member in z.namelist():
                if not (destination/member).resolve().is_relative_to(destination.resolve()):
                    raise RuntimeError('Unsafe dependency archive member')
            z.extractall(destination)
        print('Verified and extracted',dependency['name'],flush=True)


if __name__=='__main__':main()
