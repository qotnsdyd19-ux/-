"""Optional local browser validation; requires Playwright + Chromium installed."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000/',wait_until='networkidle')
    page.wait_for_function("document.querySelector('#candidate-count').textContent === '78'")
    assert page.locator('#rows tr').count()==20
    assert page.locator('#chart circle').count()>0
    page.locator('#search').fill('P09-MWA')
    assert page.locator('#rows tr').count()==1
    assert '63' in page.locator('#rows').inner_text()
    page.locator('#anneal').select_option('RTA')
    assert page.locator('#rows tr').count()==0
    page.locator('#search').fill('')
    page.locator('#anneal').select_option('')
    page.locator('#axis-temp').click()
    assert page.locator('#axis-temp').get_attribute('aria-pressed')=='true'
    page.locator('#show-more').click()
    assert page.locator('#rows tr').count()==50
    page.screenshot(path='/tmp/hzo-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.reload(wait_until='networkidle')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='/tmp/hzo-mobile.png',full_page=True)
    assert not errors,errors
    page.set_viewport_size({'width':1440,'height':1000})
    page.goto('http://127.0.0.1:8501/',wait_until='networkidle')
    page.get_by_role('heading',name='HZO Ferroelectric AI Predictor',exact=True).wait_for(timeout=40000)
    assert page.get_by_role('button',name='2Pr 예측 실행 →',exact=True).is_disabled()
    page.get_by_role('tab',name='▤  실험 데이터',exact=True).click()
    page.get_by_placeholder('TiN, 10.3390, P09…').fill('P09-MWA')
    page.get_by_placeholder('TiN, 10.3390, P09…').press('Enter')
    page.wait_for_timeout(1000)
    assert not page.locator('[data-testid="stException"]').count()
    page.screenshot(path='/tmp/hzo-streamlit.png',full_page=True)
    assert not errors,errors
    print(json.dumps({'pages':'search, treatment filter, chart switch, pagination passed','mobile':'390px, no horizontal overflow','streamlit':'render, disabled prediction, search passed','browser_errors':errors},ensure_ascii=False))
    browser.close()
