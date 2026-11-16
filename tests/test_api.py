import json
from fastapi.testclient import TestClient
import pytest
from src.api import create_app
from tests.helpers import exported_fixture

@pytest.fixture(scope='module')
def service(tmp_path_factory):
    path=tmp_path_factory.mktemp('SYNTHETIC_TEST_MODELS')
    data,bundle=exported_fixture(path)
    app=create_app(path,data_root=path/'source_fixture',allow_test_fixtures=True)
    return TestClient(app),data,bundle,path

def request(data,bundle,index=1):
    fields=['hzo_nm','top_nm','bottom_nm','anneal_c','anneal_s','voltage_v','wake_cycles','top','bottom','atmosphere','measurement_method','measurement_state','deposition','ald_c','pulse_s','frequency_hz']
    row=data.iloc[index].to_dict()
    return {'structure':'MFM','target':'2Pr','expected_model_version':bundle['report']['version'],'inputs':{k:row[k] for k in fields}}

def test_no_model_does_not_return_prediction(tmp_path):
    client=TestClient(create_app(tmp_path))
    assert client.get('/healthz').json()['ready'] is False
    assert client.get('/readyz').status_code==503
    assert client.get('/v1/models').json()['models']==[]

def test_real_model_inference_recomputes_for_input(service):
    client,data,bundle,_=service
    assert client.get('/readyz').json()=={'ready':True}
    first=client.post('/v1/predict',json=request(data,bundle,0))
    second=client.post('/v1/predict',json=request(data,bundle,5))
    assert first.status_code==second.status_code==200
    a,b=first.json(),second.json()
    assert a['value']!=b['value']
    assert a['kind']=='model_prediction' and a['dataset_hash']==bundle['report']['dataset_hash']
    assert a['model_version']==bundle['report']['version']
    assert client.get('/v1/models').json()['models'][0]['dois']==5

@pytest.mark.parametrize('field,value',[('hzo_nm',1000.),('top','Au'),('measurement_method','P-E'),('multilayer',True),('top_interlayer_nm',2.)])
def test_scope_and_unknown_conditions_blocked(service,field,value):
    client,data,bundle,_=service;body=request(data,bundle);body['inputs'][field]=value
    response=client.post('/v1/predict',json=body)
    assert response.status_code in {422,503}
    assert 'value' not in response.json()

def test_mfis_endurance_and_stale_version_blocked(service):
    client,data,bundle,_=service
    body=request(data,bundle);body['structure']='MFIS'
    assert client.post('/v1/predict',json=body).status_code==503
    body=request(data,bundle);body['target']='Endurance'
    assert client.post('/v1/predict',json=body).status_code==503
    body=request(data,bundle);body['expected_model_version']='old'
    assert client.post('/v1/predict',json=body).status_code==409

def test_public_api_has_no_edit_or_model_upload_routes(service):
    client,_,_,_=service
    for url in ['/train','/approve','/upload','/load-model']:
        assert client.post(url,json={}).status_code==404
    allowed=client.options('/v1/predict',headers={'Origin':'https://qotnsdyd19-ux.github.io','Access-Control-Request-Method':'POST'})
    denied=client.options('/v1/predict',headers={'Origin':'https://other.example','Access-Control-Request-Method':'POST'})
    assert allowed.headers['access-control-allow-origin']=='https://qotnsdyd19-ux.github.io'
    assert 'access-control-allow-origin' not in denied.headers

def test_changed_model_artifact_fails_closed(service,tmp_path):
    import shutil
    _,_,bundle,path=service
    root=tmp_path/'models';shutil.copytree(path,root)
    (root/bundle['report']['version']/'model.joblib').write_bytes(b'changed')
    client=TestClient(create_app(root,data_root=root/'source_fixture',allow_test_fixtures=True))
    assert client.get('/readyz').status_code==503
    assert client.get('/v1/models').json()['models']==[]

def test_changed_source_release_blocks_old_model(service,tmp_path):
    import shutil
    _,_,_,path=service
    root=tmp_path/'models';shutil.copytree(path,root)
    (root/'source_fixture/data/raw/synthetic.csv').write_text('changed source')
    client=TestClient(create_app(root,data_root=root/'source_fixture',allow_test_fixtures=True))
    assert client.get('/readyz').status_code==503

def test_production_cannot_serve_synthetic_test_registry(service):
    _,_,_,path=service
    client=TestClient(create_app(path,data_root=path/'source_fixture'))
    assert client.get('/readyz').status_code==503
    assert client.get('/v1/models').json()['models']==[]

def test_inputs_reject_strings_booleans_and_unknown_fields(service):
    client,data,bundle,_=service
    for change in [{'hzo_nm':'10'},{'hzo_nm':True},{'review_status':'approved'},{'model_url':'https://example.com/model'}]:
        body=request(data,bundle);body['inputs'].update(change)
        assert client.post('/v1/predict',json=body).status_code==422
