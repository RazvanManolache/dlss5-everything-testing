"""Audit the completed background-only sweep without launching any program."""
import math
from pathlib import Path
from run_backends import ROOT, read, write, digest, execution_mode


def audit():
    plan=read(ROOT/'state/background-rerun.json')
    if plan.get('schema')!='background-rerun/1' or not plan.get('targets'):
        raise ValueError('Missing background rerun plan')
    preserved_changed=[name for name,value in plan.get('preserved_sha256',{}).items()
                       if not (ROOT/name).is_file() or digest(ROOT/name)!=value]
    issues, rows=[],[]
    for fixture,modes in plan['targets'].items():
        for mode in modes:
            folder=ROOT/'runs/latest-x64-backends'/fixture/mode
            result=read(folder/'result.json')
            row=dict(id=fixture,backend=mode,passed=result.get('passed'),execution_mode=execution_mode(result))
            rows.append(row)
            if result.get('passed') is None:
                issues.append(f'{fixture}/{mode}: not finished')
            elif result['passed']:
                fps=read(folder/'fps.json')
                captures=read(folder/'captures.json').get('captures',[])
                output=result.get('average_fps')
                if (not isinstance(output,(int,float)) or not math.isfinite(output) or output<=0 or
                        output!=result.get('neural_fps') or output!=fps.get('average_fps') or fps.get('counter')!='delivered'):
                    issues.append(f'{fixture}/{mode}: output FPS is not backed by unique completion counters')
                if len(captures)!=1 or not (folder/captures[0]['png']).is_file():
                    issues.append(f'{fixture}/{mode}: expected exactly one presented screenshot')
                if row['execution_mode'] not in ('helper','in_process'):
                    issues.append(f'{fixture}/{mode}: no observed processing location')
                if result.get('game_fps')!=fps.get('game_fps'):
                    issues.append(f'{fixture}/{mode}: game-loop rate was not kept separately')
                if any(item.get('average_fps') != output for item in
                       (result.get('measurement', {}), fps.get('measurement', {}))):
                    issues.append(f'{fixture}/{mode}: nested measurement mixes game and processed rates')
                if result.get('installation_verification',{}).get('verified') is not True:
                    issues.append(f'{fixture}/{mode}: installed component identity not verified')
                row.update(output_fps=output,game_fps=result.get('game_fps'))
            elif sorted(p.name for p in folder.iterdir())!=['result.json']:
                issues.append(f'{fixture}/{mode}: failed mode retains extra output files')
    report=dict(schema='background-rerun-audit/1',passed=not issues and not preserved_changed,
                counts={str(state):sum(r['passed'] is state for r in rows) for state in (True,False,None)},
                cases=len(rows),preserved_files=len(plan.get('preserved_sha256',{})),
                preserved_changed=preserved_changed,issues=issues,rows=rows)
    write(ROOT/'runs/latest-x64-backends/background-rerun-audit.json',report)
    print({key:value for key,value in report.items() if key!='rows'})
    return report


if __name__=='__main__':
    raise SystemExit(0 if audit()['passed'] else 1)
