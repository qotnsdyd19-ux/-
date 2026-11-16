"""Functional browser checks; start docs:8000 and read-only Streamlit:8501 first."""
import json
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000/',wait_until='networkidle')
    page.wait_for_function("document.querySelector('#recordCount').textContent === '301'")
    assert page.locator('#candidateCount').inner_text()=='204'
    assert page.locator('#dataRows > tr').count()==25
    assert page.locator('#predictButton').is_disabled()
    assert page.locator('#chart circle').count()==0  # Never mix structures by default.
    page.locator('#structureFilter').select_option('MFM')
    assert page.locator('#chart circle').count()>0
    page.locator('#searchInput').fill('P09-MWA')
    assert page.locator('#dataRows > tr').count()==1
    page.locator('#annealFilter').select_option('RTA')
    assert '조건에 맞는 기록이 없습니다' in page.locator('#dataRows').inner_text()
    page.locator('#resetFilters').click()
    page.locator('#deviceStructure').select_option('MFIS')
    assert page.locator('#mfisFields').is_visible()
    assert 'Semiconductor' in page.locator('#deviceStack').inner_text()
    assert 'Memory Window' in page.locator('#predictButton').inner_text()
    assert '35행' in page.locator('#rowCount').inner_text()
    page.locator('#showMore').click()
    assert page.locator('#dataRows > tr').count()==35
    assert all('MFIS' in t.inner_text() for t in page.locator('#dataRows > tr').all())
    page.locator('#metricFilter').select_option('Pr')
    assert page.locator('#chart circle').count()==0
    page.locator('#resetFilters').click()
    page.locator('#searchInput').fill('EXT002')
    page.locator('#dataRows details').evaluate('(el)=>el.open=true')
    assert 'FATIGUE_ONSET_NOT_FAILURE' in page.locator('#dataRows').inner_text()
    assert '63000000' in page.locator('#dataRows').inner_text()
    with page.expect_download() as download:
        page.locator('#downloadResults').click()
    text=Path(download.value.path()).read_text(encoding='utf-8-sig')
    assert 'EXT002' in text and 'FATIGUE_ONSET_NOT_FAILURE' in text
    page.locator('#resetFilters').click()
    page.locator('#dataFile').set_input_files(ROOT/'data/raw/hzo_new_mfm.csv')
    page.locator('#importFile').click()
    expect(page.locator('#importStatus')).to_contain_text('37행')
    assert page.locator('#recordCount').inner_text()=='338'
    page.locator('#importFile').click()
    expect(page.locator('#importStatus')).to_contain_text('0행')
    assert page.locator('#recordCount').inner_text()=='338'
    page.locator('#researchNotes').fill('원문 확인 대기 메모')
    page.locator('#saveNotes').click()
    page.reload(wait_until='networkidle')
    assert page.locator('#researchNotes').input_value()=='원문 확인 대기 메모'
    assert page.locator('#recordCount').inner_text()=='338'
    page.screenshot(path='/tmp/hzo-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.reload(wait_until='networkidle')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='/tmp/hzo-mobile.png',full_page=True)
    page.goto('http://127.0.0.1:8501/',wait_until='networkidle')
    page.get_by_role('heading',name='HZO Ferroelectric AI Predictor',exact=True).wait_for(timeout=40000)
    assert page.get_by_role('button',name='2Pr 예측 실행 →',exact=True).is_disabled()
    page.get_by_text('MFIS',exact=True).first.click()
    page.get_by_role('heading',name='MFIS · 독립 모델 검증 대기').wait_for()
    assert page.get_by_role('button',name='MFIS 예측 실행 · 검증 모델 없음').is_disabled()
    assert not page.locator('[data-testid="stException"]').count()
    page.screenshot(path='/tmp/hzo-streamlit.png',full_page=True)
    assert not errors,errors
    print(json.dumps({'static':'structure isolation, search, definition filter, fatigue endpoint, CSV export, upload dedup, notes passed','mobile':'390px, no horizontal overflow','streamlit':'MFM/MFIS render and blocked predictions passed','browser_errors':errors},ensure_ascii=False))
    browser.close()
