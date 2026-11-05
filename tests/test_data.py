from pathlib import Path
import io
import pandas as pd
from src.data import load_sources, ingest, normalize_doi
from src.model import eligible, reasons, apply_reviews
ROOT=Path(__file__).resolve().parents[1]

def test_actual_workbooks_and_duplicate_subset():
    df,counts,_=load_sources(ROOT/'data/raw')
    assert len(df)==112
    assert counts['duplicate_subset_rows']==10
    assert df.source_sheet.eq('01_2Pr_40행').sum()==40
    assert not df.source_sheet.eq('02_수치원문확인_10행').any()
    assert df.record_id.nunique()==112
    assert (df.metric.eq('2Pr') & df.two_pr.notna()).sum()==78

def test_pr_is_never_doubled():
    df,_,_=load_sources(ROOT/'data/raw')
    other=df[df.source_sheet.eq('04_2Pr아닌자료_9행')]
    assert len(other)==9
    assert other.two_pr.isna().all()
    assert other.raw_json.str.contains('reported_value').all()

def test_annealing_types_and_missing_values_remain_distinct():
    df,_,_=load_sources(ROOT/'data/raw')
    assert df.loc[df.sample_id.eq('P09-RTA'),'anneal_type'].iloc[0]=='RTA'
    assert df.loc[df.sample_id.eq('P09-MWA'),'anneal_type'].iloc[0]=='MICROWAVE_ANNEAL'
    assert df.loc[df.source_file.eq('HZO_데이터2.xlsx'),'anneal_type'].isna().all()
    assert df.loc[df.sample_id.eq('P03-W_TE'),'hzo_nm'].isna().all()
    assert len(eligible(df))==0

def test_import_cannot_self_approve():
    raw=b'sample_id,metric,two_pr,doi,source_locator,review_status,scope_verified\na,2Pr,40,10.1234/TEST,Fig1,approved,True\n'
    df,_,_=ingest(io.BytesIO(raw),'new.csv')
    assert 'review_status' not in df
    assert df.doi.iloc[0]=='10.1234/test'
    assert eligible(df).empty

def test_unknown_csv_schema_rejected():
    import pytest
    with pytest.raises(ValueError): ingest(io.BytesIO(b'x,y\n1,2'),'other.csv')

def test_doi_canonicalization():
    assert normalize_doi('https://doi.org/10.3390/NANO12173001')=='10.3390/nano12173001'
