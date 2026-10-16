"""Locate common assets using paths relative to a game or its ancestors."""
from pathlib import Path
import os

def find_assets(folder, dos=False):
    folder=Path(folder).resolve()
    name='GALLERY.DAT' if dos else 'museum.bin'
    for parent in (folder,*folder.parents):
        candidates=[parent/'assets']
        marker=parent/('DOSASSET.TXT' if dos else 'ASSETS.TXT')
        if marker.is_file():
            relative=Path(marker.read_text(encoding='utf-8').strip())
            if relative.is_absolute():raise RuntimeError('Asset paths must be relative: '+str(marker))
            candidates.append(parent/relative)
        candidates.append(parent/'dos/assets' if dos else parent/'shared-assets')
        for candidate in candidates:
            if (candidate/name).is_file():return candidate.resolve()
    raise FileNotFoundError('Cannot locate common '+name+' from '+str(folder))

def point_assets(suite, assets, dos=False):
    suite=Path(suite).resolve();assets=Path(assets).resolve()
    relative=os.path.relpath(assets,suite)
    suite.mkdir(parents=True,exist_ok=True)
    (suite/('DOSASSET.TXT' if dos else 'ASSETS.TXT')).write_text(relative+'\n',encoding='utf-8')
