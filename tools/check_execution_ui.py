"""Headless checks of live execution labels; never launches a benchmark fixture."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8765')
    parser.add_argument('--screenshots',action='store_true')
    parser.add_argument('--expected-summary',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    errors=[]
    results=[]
    expected=json.loads(args.expected_summary.read_text(encoding='utf-8')) if args.expected_summary else None
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel='chrome',headless=True,args=['--disable-gpu'])
        try:
            for name,size in [('desktop',{'width':1440,'height':1000}),('mobile',{'width':430,'height':900})]:
                page=browser.new_page(viewport=size,reduced_motion='reduce')
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(args.url+'/dashboard/index.html#performance',wait_until='networkidle')
                page.wait_for_selector('#connection.live',state='attached')
                for field in ('#execution','#perfRoute'):
                    values=page.locator(field+' option').evaluate_all('(nodes)=>nodes.map(n=>n.value)')
                    for value in ('helper','in_process_x64_library','in_process_x86_driver'):
                        assert value in values,(field,value)
                for value in ('in_process_x64_library','in_process_x86_driver','helper','all'):
                    page.locator('#perfRoute').select_option(value)
                    assert page.locator('#execution').input_value()==value
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+2')
                data=page.evaluate('({runs:BENCH_DATA.runs.length,captures:BENCH_DATA.captures.length,variants:[...new Set(BENCH_DATA.runs.map(r=>r.execution_variant))]})')
                if expected:
                    ranking=page.evaluate('BenchPerformance.executionRankings(BENCH_DATA.runs)')
                    indexed={(r['backend'],r['variant']):r for r in ranking}
                    for row in expected['matched_x86_rankings']:
                        shown=indexed[(row['backend'],row['variant'])]
                        assert shown['matched']==row['matched_fixtures'],(row,shown)
                        assert abs(shown['meanFps']-row['mean_processed_fps'])<1e-8,(row,shown)
                        assert shown['wins']==row['wins'] and shown['startupAffected']==row['startup_affected']
                    assert page.locator('#executionRanking tbody tr').count()==len(indexed)
                if args.screenshots:
                    page.screenshot(path=str(root/f'dashboard/preview-execution-{name}.png'))
                results.append(dict(viewport=name,**data))
                page.close()
        finally:browser.close()
    assert not errors,errors
    print(json.dumps(dict(passed=True,gpu_used=False,checks=results)))


if __name__=='__main__':main()
