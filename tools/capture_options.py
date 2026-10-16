"""Shared capture scheduling rules for Windows, DOS and suite launchers."""
import math
from pathlib import Path
import json
import numpy as np
from PIL import Image


def add_arguments(parser):
    parser.add_argument('--capture-at',action='append',help='Seconds, comma-separated times, or repeat this option')
    parser.add_argument('--capture-every',type=float,help='Capture at each multiple of this positive interval')


def schedule(seconds, explicit=None, every=None, default=True):
    if not math.isfinite(seconds) or seconds<0:raise ValueError('--seconds must be finite and nonnegative')
    times=[]
    for group in explicit or []:
        for item in str(group).split(','):
            if not item.strip():raise ValueError('Empty screenshot time')
            times.append(float(item))
    if every is not None:
        if not math.isfinite(every) or every<=0 or seconds<=0:raise ValueError('--capture-every requires a positive interval and duration')
        ratio=seconds/every
        if not math.isfinite(ratio) or ratio>10000:raise ValueError('At most 10000 screenshots per run')
        count=math.floor(ratio+1e-10)
        times.extend(min(seconds,i*every) for i in range(1,count+1) if i*every<=seconds+1e-9)
        if not times:raise ValueError('Capture interval exceeds run time')
    if not explicit and every is None and default:times=[seconds/2 if seconds else 15]
    if len(times)>10000:raise ValueError('At most 10000 screenshots per run')
    result=[]
    for value in sorted(times):
        if not math.isfinite(value) or value<0 or seconds and value>seconds:raise ValueError('Screenshot times must be finite, nonnegative and no later than --seconds')
        if not result or abs(value-result[-1])>=1e-9:result.append(value)
    return result


def native_arguments(times):
    # Repetition is useful at the shell; a CSV keeps the DOS command tail short.
    return ['--capture-at',','.join(format(t,'.12g') for t in times)] if times else []


def check_captures(folder,expected,records,tolerance,png_key='png'):
    checks={};actual=[r for r in records if r.get('requested_seconds') is not None]
    checks['capture_schedule_complete']=len(actual)==len(expected) and all(abs(r['requested_seconds']-t)<1e-7 for r,t in zip(actual,expected))
    checks['capture_times_honored']=all(r['requested_seconds']<=r['elapsed_seconds']<r['requested_seconds']+tolerance for r in actual)
    paths=[r.get(png_key,'') for r in actual]
    checks['unique_screenshot_files']=len(paths)==len(set(paths)) and all(paths)
    images_ok=bool(actual);readbacks_ok=True
    for record in actual:
        path=Path(folder)/record[png_key]
        if not path.is_file():images_ok=False;continue
        image=np.asarray(Image.open(path).convert('RGB'))
        images_ok=images_ok and float(image.std())>15
        readback_name=record.get('ppm') or record.get('bmp')
        if readback_name:
            readback=Path(folder)/readback_name
            readbacks_ok=readbacks_ok and readback.is_file() and np.array_equal(image,np.asarray(Image.open(readback).convert('RGB')))
    checks['all_screenshots_nonblank']=images_ok
    checks['all_pngs_match_readbacks']=readbacks_ok
    return checks
