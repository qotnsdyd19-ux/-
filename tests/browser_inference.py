"""Browser → HTTP API → trained SYNTHETIC test model, never a research deployment."""
from pathlib import Path
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from urllib.parse import urlparse
import requests
import uvicorn
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.helpers import exported_fixture
from src.api import create_app

with tempfile.TemporaryDirectory(prefix='hzo-SYNTHETIC-browser-test-') as directory:
    folder=Path(directory)
    data,bundle=exported_fixture(folder)
    app=create_app(folder,data_root=folder/'source_fixture',allow_test_fixtures=True)
    listener=socket.socket();listener.bind(('127.0.0.1',0))
    api='http://127.0.0.1:'+str(listener.getsockname()[1])
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(0.05)
    assert server.started
    calls=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/inference-config.json',lambda r:r.fulfill(json={'api_base_url':'https://hzo-synthetic-test.invalid'}))
            def proxy(route):
                # Test reverse proxy only; responses are computed by the real local API.
                req=route.request;path=urlparse(req.url).path
                if path=='/v1/predict':calls.append(json.loads(req.post_data))
                response=requests.request(req.method,api+path,data=req.post_data,headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:8000'},timeout=15)
                route.fulfill(status=response.status_code,content_type='application/json',body=response.content,headers={'Access-Control-Allow-Origin':'http://127.0.0.1:8000'})
            page.route('https://hzo-synthetic-test.invalid/**',proxy)
            page.goto('http://127.0.0.1:8000/',wait_until='networkidle')
            expect(page.locator('#engineStatus')).to_contain_text('활성 모델 1개')
            page.locator('#methodInput').select_option('PUND')
            page.get_by_text('고급 옵션 · 증착 / 삽입층',exact=True).click()
            page.locator('#depositionInput').select_option('ALD')
            page.locator('#hzoInput').fill('5')
            page.locator('#predictButton').click()
            expect(page.locator('#resultNumber')).not_to_have_text('—')
            first=page.locator('#resultNumber').inner_text()
            assert calls[-1]['inputs']['hzo_nm']==5
            assert page.locator('#resultVersion').inner_text()==bundle['report']['version']
            with page.expect_download() as download:page.locator('#downloadPrediction').click()
            csv=Path(download.value.path()).read_text(encoding='utf-8-sig')
            assert 'model_prediction' in csv and bundle['report']['version'] in csv
            page.locator('#hzoInput').fill('15')
            assert page.locator('#resultNumber').inner_text()=='—'
            page.locator('#predictButton').click()
            expect(page.locator('#resultNumber')).not_to_have_text('—')
            assert page.locator('#resultNumber').inner_text()!=first
            assert len(calls)==2 and calls[-1]['inputs']['hzo_nm']==15
            page.locator('#hzoInput').fill('100')
            page.locator('#predictButton').click()
            expect(page.locator('#predictionStatus')).to_contain_text('학습 범위')
            assert page.locator('#resultNumber').inner_text()=='—'
            assert page.locator('#downloadPrediction').is_disabled()
            page.locator('#deviceStructure').select_option('MFIS')
            assert page.locator('#predictButton').is_disabled()
            assert len(calls)==3
            assert not errors,errors
            browser.close()
            print(json.dumps({'test_data':'SYNTHETIC ONLY / temporary files removed','actual_model_http_inference':'passed','input_changes_recompute':'passed','stale_result_cleared':'passed','out_of_range':'blocked','MFIS':'blocked','prediction_CSV':'passed','browser_errors':errors},ensure_ascii=False))
    finally:
        server.should_exit=True;thread.join(timeout=5)
