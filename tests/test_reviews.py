import hashlib
import json
import pandas as pd
import pytest
from src.data import frame,normalize_doi
from src.model import eligible
from src.reviews import verified_dataset,record_digest,CONFIRMED,required_confirmations
from tests.test_model import fixture

def manifest(tmp_path):
    # Entirely synthetic evidence for validating the review machinery only.
    df=frame([fixture().iloc[0].to_dict()]);df['review_status']='pending'
    text='SYNTHETIC TEST DOCUMENT. Not a scientific source. 2Pr and process are test fixture values only.'
    digest=hashlib.sha256(text.encode()).hexdigest();(tmp_path/(digest+'.txt')).write_text(text)
    decision={'record_id':df.record_id.iloc[0],'record_sha256':record_digest(df.iloc[0]),'review_status':'approved','reviewer':'unit test only','reviewed_at':'2026-11-16T00:00:00Z','scope_verified':True,'measurement_definition':'2Pr_PUND','corrections':{},
              'evidence':[{'source_id':'synthetic','excerpt':text,'locator':'Synthetic test paragraph','confirms':sorted(required_confirmations(df.iloc[0],{}))}]}
    obj={'schema_version':1,'sources':{'synthetic':{'url':'https://example.com/test-only','doi':df.doi.iloc[0],'sha256':digest}},'decisions':[decision]}
    path=tmp_path/'manifest.json';path.write_text(json.dumps(obj));return df,obj,path

def test_verified_overlay_retains_original_and_checks_cached_evidence(tmp_path):
    df,obj,path=manifest(tmp_path);before=df.copy(deep=True)
    reviewed,audit=verified_dataset(df,path,tmp_path)
    assert len(eligible(reviewed))==1 and audit[0]['status']=='approved'
    pd.testing.assert_frame_equal(df,before)
    assert reviewed.measurement_definition.iloc[0]=='2Pr_PUND'

@pytest.mark.parametrize('mutation',['wrong_quote','source_changed','raw_changed','missing_confirmation','label_correction','wrong_doi'])
def test_unsupported_approval_fails(tmp_path,mutation):
    df,obj,path=manifest(tmp_path);d=obj['decisions'][0]
    if mutation=='wrong_quote':d['evidence'][0]['excerpt']='Invented paragraph that was never present.'
    elif mutation=='source_changed':next(tmp_path.glob('*.txt')).write_text('changed')
    elif mutation=='raw_changed':df.loc[0,'two_pr']=999.
    elif mutation=='missing_confirmation':d['evidence'][0]['confirms'].remove('two_pr')
    elif mutation=='label_correction':d['corrections']['two_pr']=100.
    elif mutation=='wrong_doi':obj['sources']['synthetic']['doi']='10.1234/different'
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError):verified_dataset(df,path,tmp_path)

def test_frontiers_full_and_pdf_routes_share_one_doi_group():
    assert normalize_doi('https://www.frontiersin.org/articles/10.3389/fmats.2022.969188/full')=='10.3389/fmats.2022.969188'
    assert normalize_doi('10.3389/fmats.2022.969188/pdf')=='10.3389/fmats.2022.969188'

def test_present_optional_value_also_needs_source_confirmation(tmp_path):
    df,obj,path=manifest(tmp_path)
    decision=obj['decisions'][0]
    decision['evidence'][0]['confirms'].remove('top_nm')
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='top_nm'):verified_dataset(df,path,tmp_path)
    # A reviewer may omit an unconfirmed optional value from the training overlay.
    decision['corrections']['top_nm']=None
    path.write_text(json.dumps(obj))
    reviewed,_=verified_dataset(df,path,tmp_path)
    assert pd.isna(reviewed.top_nm.iloc[0])
    assert df.top_nm.iloc[0]==50.

def test_review_corrections_keep_doi_group_identity_canonical(tmp_path):
    df,obj,path=manifest(tmp_path)
    obj['decisions'][0]['corrections']['doi']=df.doi.iloc[0].upper()
    path.write_text(json.dumps(obj))
    reviewed,_=verified_dataset(df,path,tmp_path)
    assert reviewed.doi.iloc[0]==df.doi.iloc[0]
