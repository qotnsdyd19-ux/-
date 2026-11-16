"""Verify that requested original sources cover every candidate without inventing pages."""
from collections import Counter
import json
from pathlib import Path
import pandas as pd
from src.data import load_sources

ROOT=Path(__file__).resolve().parents[1]

def test_pdf_requests_cover_original_candidates_exactly_and_preserve_locators():
    data,_,_=load_sources(ROOT/'data/raw')
    candidates=data[data.structure.eq('MFM') & data.metric.eq('2Pr') & data.two_pr.notna()]
    requests=pd.read_csv(ROOT/'docs/required_pdfs.csv')
    ids=[rid for group in requests.record_ids for rid in group.split(' | ')]
    assert Counter(ids)==Counter(candidates.record_id)
    assert requests.candidate_source_rows.sum()==161
    assert requests.doi.nunique()==30
    assert requests.pdf_pages.eq('원문 PDF 미확보: 페이지 번호 확인 불가').all()
    for _,row in candidates[candidates.source_locator.notna()].iterrows():
        request=requests[requests.record_ids.str.contains(row.record_id,regex=False)].iloc[0]
        assert row.source_locator in request.reported_figure_table
    report=json.loads((ROOT/'docs/training_audit.json').read_text())
    assert report['rows_with_doi_and_reported_method']==0
    assert report['approved_rows']==0
    assert report['MAE'] is None and report['public_research_model_two_input_test']=='not_run_no_validated_model'
