"""Headless static-dashboard checks, without fixtures, inference or GPU use."""
import argparse
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',help='Verify an already hosted docs root instead of a temporary local server')
    parser.add_argument('--preview',action='store_true')
    args=parser.parse_args()
    errors=[];requests=[];server=None
    if not args.url:
        server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'docs')))
        threading.Thread(target=server.serve_forever,daemon=True).start()
    base=args.url.rstrip('/') if args.url else f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='chrome',headless=True,args=['--disable-gpu'])
            try:
                for name,width,height in [('desktop',1440,1050),('mobile',430,900)]:
                    page=browser.new_page(viewport=dict(width=width,height=height),reduced_motion='reduce')
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.on('request',lambda request:requests.append(request.url))
                    page.goto(base+'/dashboard/index.html#performance',wait_until='networkidle')
                    assert page.locator('#connection').inner_text()=='Published snapshot'
                    assert page.evaluate('BENCH_DATA.runs.length')==445
                    assert page.evaluate('BENCH_DATA.captures.length')==351
                    ranking=page.evaluate('BenchPerformance.executionRankings(BENCH_DATA.runs)')
                    assert len(ranking)==5 and all(r['matched']==43 for r in ranking)
                    labels=page.locator('.backend-choices').inner_text()
                    assert 'Phoenix DLSS5' in labels and 'NVIDIA DLSS5' in labels
                    assert 'x86 Phoenix + native driver' not in page.locator('body').inner_text()
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+2')
                    if args.preview and name=='desktop':
                        page.screenshot(path=str(ROOT/'docs/dashboard-preview.png'))
                    page.locator('[data-view="gallery"]').click()
                    page.wait_for_function('Array.from(document.images).some(i=>i.complete&&i.naturalWidth>0)')
                    assert not page.locator('img').evaluate_all('(images)=>images.some(i=>i.complete&&i.naturalWidth===0)')
                    page.locator('[data-pick]').first.click()
                    page.locator('[data-pick]').nth(1).click()
                    page.locator('[data-view="compare"]').click()
                    assert page.locator('#view-compare img').count()>=2
                    page.close()
            finally:browser.close()
        assert not errors,errors
        assert not any('/api/data' in url for url in requests),'Published view attempted to reach a private indexer'
        print(json.dumps(dict(passed=True,gpu_used=False,fixtures_launched=False,records=445,captures=351,viewports=['desktop','mobile'])))
    finally:
        if server:server.shutdown();server.server_close()


if __name__=='__main__':main()
