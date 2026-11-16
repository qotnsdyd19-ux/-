"""Software tests only: no approval of research data or published test model."""
import numpy as np
import pandas as pd
import pytest
from src.model import train,predict,eligible,REQUIRED
from tests.test_model import fixture

def sparse():
    df=fixture()
    df.loc[df.index%2==0,'top_nm']=np.nan
    for key in ['bottom_nm','anneal_s','wake_cycles']:df[key]=np.nan
    df.loc[:9,'atmosphere']=None
    return df

def test_optional_absence_is_not_source_approval_and_core_remains_required():
    df=sparse()
    assert len(eligible(df))==30
    df.loc[0,'review_status']='pending'
    assert len(eligible(df))==29
    for field in REQUIRED:
        bad=fixture().iloc[[0]].copy();bad[field]=None
        assert eligible(bad).empty,field

def test_optional_missingness_is_handled_without_changing_raw_data(tmp_path):
    df=sparse();before=df.copy(deep=True)
    bundle=train(df,tmp_path)
    pd.testing.assert_frame_equal(df,before)
    report=bundle['report']
    assert report['active']
    assert 'bottom_nm' in report['unused_features']
    assert 'bottom_nm' not in report['used_features']
    assert 'top_nm' in report['missing_allowed']
    names=bundle['model'].named_steps['features'].get_feature_names_out()
    assert any('missingindicator_top_nm' in n for n in names)
    query=df.iloc[0].to_dict()
    assert predict(bundle,query,df)[0] is not None
    assert predict(bundle,{**query,'bottom_nm':50.},df)[0] is None
    assert predict(bundle,{**query,'top_nm':500.},df)[0] is None
    assert predict(bundle,{**query,'voltage_v':None},df)[0] is None

def test_imputation_is_fitted_on_training_fold_only(tmp_path,monkeypatch):
    import src.model as model
    df=sparse();df['top_nm']=np.arange(1.,31.);df.loc[df.index%3==0,'top_nm']=np.nan
    original=model.pipeline;seen=[]
    def factory(numeric=None,categorical=None):
        pipe=original(numeric,categorical);fit=pipe.fit
        def capture(x,y):
            result=fit(x,y)
            median=pipe.named_steps['features'].named_transformers_['num'].named_steps['impute'].statistics_[numeric.index('top_nm')]
            seen.append((tuple(x.index),median,float(x.top_nm.median())))
            return result
        pipe.fit=capture;return pipe
    monkeypatch.setattr(model,'pipeline',factory)
    # Do not serialize a locally instrumented fit callback; it is not a model change.
    monkeypatch.setattr(model.joblib,'dump',lambda *args,**kwargs:None)
    model.train(df,tmp_path)
    assert len(seen)==6
    for indices,actual,expected in seen:
        assert actual==expected
    assert any(m!=df.top_nm.median() for _,m,_ in seen[:-1])

def test_source_verified_zero_is_valid_but_negative_target_is_not():
    df=fixture().iloc[[0]].copy();df['two_pr']=0.
    assert len(eligible(df))==1
    df['two_pr']=-1.
    assert eligible(df).empty
