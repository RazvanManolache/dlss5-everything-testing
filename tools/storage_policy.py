"""Bound default run storage; explicitly named output folders are never erased."""
from pathlib import Path
import shutil,stat
ROOT=Path(__file__).resolve().parents[1]

def latest_output(requested,name):
    if requested is not None:return Path(requested).resolve()
    if name not in ('latest','latest-windows','latest-dos','latest-verify','latest-x64-backends'):
        raise ValueError('Unknown default run directory')
    runs=ROOT/'runs';path=runs/name
    if runs.exists() and runs.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise RuntimeError('Refusing to clear results under a linked runs folder')
    if not path.resolve().is_relative_to(ROOT/'runs'):raise RuntimeError('Unsafe run directory')
    if path.exists():
        stack=[path]
        while stack:
            current=stack.pop()
            if current.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise RuntimeError('Refusing to clear a linked run directory: '+str(current))
            if current.is_dir():stack.extend(current.iterdir())
        shutil.rmtree(path)
    return path
