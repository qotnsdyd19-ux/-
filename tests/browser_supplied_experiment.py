"""Direct page test with the real supplied-data model. No mocked inference responses."""
import argparse,json,shutil,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.experimental import load,predict
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8000/');args=parser.parse_args()
model=load(ROOT);cases=json.loads((ROOT/'docs/experimental-cases.json').read_text());expected=[predict(model,c['inputs'],True)['value'] for c in cases]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(args.url+('&' if '?' in args.url else '?')+'release='+model['report']['version'],wait_until='networkidle')
    expect(page.locator('#experimentalNotice')).to_be_visible(timeout=45000)
    assert model['report']['version'] in page.locator('#resultVersion').inner_text()
    assert page.locator('#predictButton').is_disabled()
    expect(page.locator('#experimentalNotice')).to_contain_text('미통과' if not model['report']['validation_passed'] else '통과')
    page.locator('#experimentalAcknowledgement').check()
    output=[]
    for index,case in enumerate(cases):
        page.locator('#experimentalExample'+str(index)).click()
        page.locator('#predictButton').click()
        expect(page.locator('#resultNumber')).to_have_text(f'{expected[index]:.2f}')
        assert '실제 Python 학습 모델' in page.locator('#predictionStatus').inner_text()
        output.append(page.locator('#resultNumber').inner_text())
    assert output[0]!=output[1]
    with page.expect_download() as download:page.locator('#downloadPrediction').click()
    text=Path(download.value.path()).read_text(encoding='utf-8-sig');assert 'experimental_model_prediction' in text and 'false' in text.lower()
    page.screenshot(path='/tmp/hzo-real-experimental-prediction.png',full_page=True)
    novel={**cases[0]['inputs'],'hzo_nm':11.3,'anneal_c':547.5}
    novel_expected=predict(model,novel,True)['value']
    page.locator('#experimentalExample0').click();page.locator('#hzoInput').fill('11.3');page.locator('#temperatureInput').fill('547.5');page.locator('#predictButton').click()
    expect(page.locator('#resultNumber')).to_have_text(f'{novel_expected:.2f}')
    page.locator('#hzoInput').fill('1000');assert page.locator('#resultNumber').inner_text()=='—'
    page.locator('#hzoInput').evaluate('(el)=>el.max="10000"');page.locator('#predictButton').click()
    expect(page.locator('#predictionStatus')).to_contain_text('학습 범위')
    page.locator('#deviceStructure').select_option('MFIS');assert page.locator('#predictButton').is_disabled()
    page.screenshot(path='/tmp/hzo-real-experimental-page.png',full_page=True)
    assert not errors,errors
    print(json.dumps({'page_url':args.url,'model':model['report']['version'],'actual_supplied_data_training_rows':model['report']['rows'],
                      'actual_python_predictions':expected,'browser_predictions':output,'novel_input_prediction':novel_expected,'source_review_verified':False,
                      'validation_passed':model['report']['validation_passed'],'ack_required':True,'out_of_range':'blocked','MFIS':'blocked','page_errors':errors},ensure_ascii=False))
    browser.close()
