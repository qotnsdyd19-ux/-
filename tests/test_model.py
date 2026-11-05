"""Synthetic records are test fixtures only, never research data."""
import json
import numpy as np
import pandas as pd
import pytest
from src.model import train,predict,readiness,group_splits,reasons,latest,apply_reviews,eligible
from src.data import frame
from src.store import Store

def fixture():
    rows=[]
    for i in range(30):
        x=5+(i%6)*2
        rows.append(dict(record_id=f'test-{i}',doi=f'10.1234/synthetic-{i//6}',sample_id=f'synthetic-{i}',metric='2Pr',two_pr=2*x+1,hzo_nm=x,top_nm=50.,bottom_nm=50.,anneal_c=500.,anneal_s=30.,voltage_v=3.,wake_cycles=0.,ald_c=None,pulse_s=None,frequency_hz=None,top='TiN',bottom='TiN',anneal_type='RTA',atmosphere='N2',measurement_method='PUND',measurement_state='pristine',deposition='ALD',structure='MFM',composition='Hf:Zr=1:1',scope_verified=True,review_status='approved',reviewer='test fixture',evidence='synthetic fixture only',source_locator='Fig1'))
    return pd.DataFrame(rows)

def test_group_folds_prevent_doi_leakage():
    df=fixture()
    for a,b in group_splits(df): assert set(df.iloc[a].doi).isdisjoint(df.iloc[b].doi)

def test_no_model_no_number():
    value,issues=predict(None,{})
    assert value is None and issues

def test_insufficient_groups_cannot_train(tmp_path):
    df=fixture(); df['doi']='10.1234/one'
    with pytest.raises(ValueError): train(df,tmp_path)
    assert not list(tmp_path.iterdir())

def test_approval_is_not_enough_to_include_bad_scope():
    df=fixture()
    for column,value in [('anneal_type','MICROWAVE_ANNEAL'),('metric','Pr'),('composition','Zr x=0.55'),('structure','MFIM'),('scope_verified',False),('measurement_method','unknown'),('hzo_nm',None),('top_interlayer_nm',5)]:
        candidate=df.iloc[0].to_dict(); candidate[column]=value
        assert reasons(candidate), column

def test_versioned_train_predict_ood_and_stale_data(tmp_path):
    df=fixture(); bundle=train(df,tmp_path)
    assert bundle['report']['active']
    assert bundle['report']['forest']['MAE']<bundle['report']['baseline']['MAE']
    query=df.iloc[2].to_dict()
    value,issues=predict(bundle,query,df)
    assert value is not None and not issues
    assert latest(df,tmp_path) is not None
    assert predict(bundle,{**query,'hzo_nm':100},df)[0] is None
    assert predict(bundle,{**query,'top':'Au'},df)[0] is None
    assert predict(bundle,{**query,'multilayer':True},df)[0] is None
    assert predict(bundle,{**query,'measurement_method':'P-E'},df)[0] is None
    df.loc[0,'two_pr']+=1
    assert latest(df,tmp_path) is None
    assert predict(bundle,query,df)[0] is None
    assert len(list(tmp_path.glob('*/model.joblib')))==1

def test_store_review_preserves_original_and_requires_evidence(tmp_path):
    db=Store(tmp_path/'state.sqlite'); df=frame([fixture().iloc[0].to_dict()])
    assert db.add(df)==1
    assert db.add(df)==0
    with pytest.raises(ValueError): db.review(df.record_id.iloc[0],{})
    review=dict(corrections={'hzo_nm':12},review_status='pending',scope_verified=True,reviewer='Tester',evidence='Fig 1, checked')
    db.review(df.record_id.iloc[0],review)
    original=db.records(); changed=apply_reviews(original,db.reviews())
    assert original.hzo_nm.iloc[0]==5
    assert changed.hzo_nm.iloc[0]==12
    assert eligible(changed).empty
