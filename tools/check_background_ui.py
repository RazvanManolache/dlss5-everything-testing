"""Read-only browser checks for processing tags, filtering and FPS separation."""
from playwright.sync_api import sync_playwright, expect
import json


def main():
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True, channel='chrome', args=['--disable-gpu'])
        try:
            page=browser.new_page(viewport=dict(width=1440,height=1100))
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto('http://127.0.0.1:8765/dashboard/index.html#gallery',wait_until='networkidle')
            expect(page.locator('#connection')).to_have_class('connection live')
            page.locator('#execution').select_option('helper')
            cards=page.locator('.capture-card')
            helper_count=cards.count()
            assert helper_count>0
            expect(page.locator('.capture-card .execution-tag[data-execution="helper"]')).to_have_count(helper_count)
            expect(page.locator('.capture-card .fps-value').first).to_contain_text('processed FPS')
            page.locator('[data-view="results"]').click()
            expect(page.locator('#view-results tbody .execution-tag[data-execution="helper"]')).to_have_count(
                page.locator('#view-results tbody tr').count())
            expect(page.locator('#view-results thead')).to_contain_text('Output FPS')
            expect(page.locator('#view-results thead')).to_contain_text('Game-loop FPS')
            page.locator('[data-view="performance"]').click()
            expect(page.locator('.comparison-table .execution-tag[data-execution="in_process"]')).to_have_count(0)
            page.locator('#chartMetric').select_option('game_fps')
            expect(page.locator('.performance-summary')).to_contain_text('game-loop FPS')
            page.locator('#chartMetric').select_option('fps')
            expect(page.locator('.performance-summary')).to_contain_text('output FPS')
            page.locator('#execution').select_option('native')
            expect(page.locator('#perfRoute')).to_have_value('native')
            expect(page.locator('.performance-stat[data-backend="native"]')).to_be_visible()
            expect(page.locator('.performance-stat[data-backend="nvidia"]')).to_have_count(0)
            page.locator('#perfRoute').select_option('helper')
            expect(page.locator('#execution')).to_have_value('helper')
            page.locator('#resetFilters').click()
            expect(page.locator('#execution')).to_have_value('all')
            page.set_viewport_size(dict(width=390,height=1100))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.set_viewport_size(dict(width=320,height=844))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert not errors, errors
            print(json.dumps(dict(passed=True,helper_cards=helper_count,desktop=True,mobile=True,errors=errors)))
        finally:
            browser.close()


if __name__=='__main__':
    main()
