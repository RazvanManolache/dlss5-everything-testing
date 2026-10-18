"""Read-only, headless dashboard checks. Never launches fixtures or GPU tests."""
import argparse
import csv
import io
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def check(url, screenshots=False, channel='chrome'):
    root = Path(__file__).resolve().parents[1]
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel=channel, args=['--disable-gpu'])
        try:
            context = browser.new_context(viewport={'width': 1440, 'height': 1100},
                                          reduced_motion='reduce', accept_downloads=True)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url.rstrip('/') + '/dashboard/index.html#performance', wait_until='networkidle')
            expect(page.locator('#connection')).to_have_class('connection live')
            expected = page.evaluate('''() => {
                const a = BenchPerformance.analyse(BENCH_DATA.runs);
                return {fixtures:a.rows.length, matched:a.matched.length, failed:a.failed};
            }''')
            assert expected['fixtures'] > 0 and expected['matched'] > 0
            expect(page.locator('.backend-chart-row')).to_have_count(expected['fixtures'])
            expect(page.locator('.failed-value')).to_have_count(expected['failed'])
            expect(page.locator('.performance-context')).to_contain_text(f"{expected['matched']} matched cases")
            page.locator('#allBars').uncheck()
            expect(page.locator('.backend-chart-row')).to_have_count(min(20, expected['fixtures']))
            page.locator('#allBars').check()

            page.locator('[data-perf-backend="native"]').uncheck()
            expect(page.locator('.backend-series-name', has_text='Native')).to_have_count(0)
            page.locator('#chartMetric').select_option('drop')
            expect(page.locator('.backend-track.divergent').first).to_be_visible()
            expect(page.locator('.performance-context')).to_contain_text(f"{expected['matched']} matched cases")
            page.locator('[data-perf-backend="native"]').check()
            page.locator('#chartMetric').select_option('retention')
            expect(page.locator('.backend-value').first).to_have_text('100.0%')
            page.locator('#chartMetric').select_option('fps')

            page.locator('#perfRoute').select_option('in_process')
            direct = page.locator('.backend-chart-row').count()
            assert 0 < direct < expected['fixtures']
            expect(page.locator('.comparison-table')).to_contain_text('In process')
            with page.expect_download() as filtered_download:
                page.locator('#exportCsv').click()
            filtered_records = list(csv.DictReader(io.StringIO(
                Path(filtered_download.value.path()).read_text(encoding='utf-8-sig'))))
            assert len(filtered_records) == direct
            page.locator('#perfRoute').select_option('helper')
            expect(page.locator('.comparison-table')).to_contain_text('Background process')
            page.locator('#perfRoute').select_option('all')

            page.locator('#pairedOnly').check()
            expect(page.locator('.backend-chart-row')).to_have_count(expected['matched'])
            page.locator('#pairedOnly').uncheck()
            page.locator('#chartGroup').select_option('architecture')
            expect(page.locator('.backend-chart-row')).to_have_count(2)
            page.locator('#chartGroup').select_option('execution')
            expect(page.locator('.backend-chart')).to_contain_text('Background process')
            page.locator('#chartGroup').select_option('fixture')
            page.locator('#perfSort').select_option('ratio')
            page.locator('#logScale').check()
            expect(page.locator('.backend-legend')).to_contain_text('Log1p scale')
            page.locator('#logScale').uncheck()
            page.locator('#perfSort').select_option('name')

            page.locator('#chartMetric').select_option('neural_fps')
            expect(page.locator('[data-perf-backend="native"]')).to_be_disabled()
            expect(page.locator('.backend-series-name', has_text='Native')).to_have_count(0)
            expect(page.locator('.performance-stat[data-backend="nvidia"]')).to_contain_text('processed FPS')
            page.locator('#chartMetric').select_option('nvidia_neural')
            expect(page.locator('.backend-legend')).to_contain_text('NVIDIA = 100%')
            expect(page.locator('#logScale')).to_be_disabled()
            page.locator('#chartMetric').select_option('nvidia_game')
            expect(page.locator('[data-perf-backend="native"]')).to_be_disabled()
            page.locator('#chartMetric').select_option('fps')
            page.locator('#arch').select_option('x86')
            assert all(name.endswith('-x86') for name in page.locator('.backend-chart-row').evaluate_all(
                '(rows) => rows.map(row => row.dataset.fixture)'))
            page.locator('#arch').select_option('all')
            page.locator('#mode').select_option('phoenix')
            expect(page.locator('[data-perf-backend="nvidia"]')).to_be_disabled()
            expect(page.locator('.backend-series-name', has_text='NVIDIA')).to_have_count(0)
            page.locator('#mode').select_option('all')
            page.locator('#suite').select_option('working')
            enhanced_matched = page.evaluate("BenchPerformance.analyse(BENCH_DATA.runs, {backends:['nvidia','phoenix']}).matched.length")
            expect(page.locator('.performance-context')).to_contain_text(f"{enhanced_matched} matched cases")
            page.locator('#suite').select_option('all')
            page.locator('#outcome').select_option('failed')
            expect(page.locator('.backend-fill')).to_have_count(0)
            page.locator('#outcome').select_option('all')

            with page.expect_download() as download:
                page.locator('[data-export-performance]').click()
            records = list(csv.DictReader(io.StringIO(Path(download.value.path()).read_text(encoding='utf-8-sig'))))
            assert len(records) == expected['fixtures']
            for row in records:
                for mode in ('native', 'nvidia', 'phoenix'):
                    if row[mode + '_status'] == 'failed':
                        assert row[mode + '_value'] == ''

            expect(page.locator('#view-performance')).not_to_contain_text('NaN')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            expect(page.locator('#toast')).not_to_have_class(re.compile(r'\bvisible\b'))
            page.locator('#view-performance').evaluate("el => el.scrollIntoView({block:'start'})")
            if screenshots:
                page.screenshot(path=str(root / 'dashboard/preview-performance-desktop.png'))
            page.set_viewport_size({'width': 390, 'height': 1100})
            page.locator('#view-performance').evaluate("el => el.scrollIntoView({block:'start'})")
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if screenshots:
                page.screenshot(path=str(root / 'dashboard/preview-performance-mobile.png'))
            for metric in ('nvidia_neural', 'drop', 'retention'):
                page.locator('#chartMetric').select_option(metric)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.set_viewport_size({'width': 320, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert not errors, errors
            context.close()
            return dict(passed=True, desktop='1440x1100', mobile='390x1100',
                        fixtures=expected['fixtures'], matched=expected['matched'],
                        failed_tags=expected['failed'], errors=errors, screenshots=screenshots)
        finally:
            browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    parser.add_argument('--screenshots', action='store_true')
    parser.add_argument('--channel', default='chrome', help='Installed Chromium browser channel')
    args = parser.parse_args()
    print(json.dumps(check(args.url, args.screenshots, args.channel), indent=2))
