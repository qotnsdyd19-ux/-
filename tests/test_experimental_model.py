"""Real supplied data, explicitly unverified; these tests do not validate physics."""
import json,subprocess
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from src.data import load_sources
from src.experimental import load,predict,prepare

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def actual():return load(ROOT)

def test_real_data_lineage_and_no_automatic_approval(actual):
    data,excluded,total=prepare(ROOT);source,_,_=load_sources(ROOT/'data/raw')
    assert total==161 and len(data)>=20 and data.doi.nunique()>=5
    original=source.set_index('record_id')
    for _,row in data.iterrows():
        assert original.loc[row.record_id,'two_pr']==row.two_pr
        assert row.structure=='MFM' and row.metric=='2Pr'
        assert row.review_status!='approved'
    assert json.loads((ROOT/'data/reviews/decisions.json').read_text())['decisions']==[]
    report=actual['report']
    assert report['source_review_verified'] is False and report['active'] is False
    assert report['rows']==len(data)
    for fold in report['folds']:assert set(fold['train_dois']).isdisjoint(fold['test_dois'])

def test_recorded_oof_metrics_are_actual_predictions(actual):
    from src.model import scores
    r=actual['report'];df=pd.read_csv(ROOT/'models-experimental'/r['version']/'oof.csv')
    assert scores(df.two_pr,df.prediction)==pytest.approx(r['forest'])
    assert scores(df.two_pr,df.baseline_prediction)==pytest.approx(r['baseline'])
    expected=r['forest']['MAE']<=.95*r['baseline']['MAE'] and (r['forest']['R2'] or 0)>0
    assert r['validation_passed']==expected

def test_two_actual_inputs_and_browser_forest_equal_python(actual):
    cases=json.loads((ROOT/'docs/experimental-cases.json').read_text())
    novel={**cases[0]['inputs'],'hzo_nm':11.3,'anneal_c':547.5}
    expected=[predict(actual,c['inputs'],True)['value'] for c in cases]
    assert len(set(expected))>1
    assert np.isfinite(predict(actual,novel,True)['value'])
    code='''import fs from 'node:fs';import {predictForest} from './docs/forest-runtime.js';
const model=JSON.parse(fs.readFileSync('docs/experimental-model.json','utf8'));
const cases=JSON.parse(fs.readFileSync('docs/experimental-cases.json','utf8'));
process.stdout.write(JSON.stringify(cases.map(c=>predictForest(model,c.inputs))));'''
    result=subprocess.run(['node','--input-type=module','-e',code],cwd=ROOT,check=True,capture_output=True,text=True)
    assert json.loads(result.stdout)==pytest.approx(expected,abs=1e-9)
    with pytest.raises(ValueError):predict(actual,cases[0]['inputs'],False)
    with pytest.raises(ValueError):predict(actual,{**cases[0]['inputs'],'hzo_nm':1000.},True)

def test_actual_python_api_requires_ack_and_exposes_failed_validation(actual):
    from src.experiment_api import create_app
    client=TestClient(create_app(ROOT));cases=json.loads((ROOT/'docs/experimental-cases.json').read_text())
    report=actual['report'];assert client.get('/readyz').json()['source_review_verified'] is False
    body={'structure':'MFM','target':'2Pr','measurement_method':'unconfirmed','expected_model_version':report['version'],'acknowledge_unvalidated':False,'inputs':cases[0]['inputs']}
    assert client.post('/v1/predict',json=body).status_code==422
    body['acknowledge_unvalidated']=True
    responses=[]
    for case in cases:
        body['inputs']=case['inputs'];res=client.post('/v1/predict',json=body)
        assert res.status_code==200
        assert res.json()['kind']=='experimental_model_prediction'
        assert res.json()['validation_passed']==report['validation_passed']
        responses.append(res.json()['value'])
    assert responses[0]!=responses[1]
    assert client.post('/v1/train').status_code==403
    body['structure']='MFIS';assert client.post('/v1/predict',json=body).status_code==422
