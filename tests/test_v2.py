import json
import re
import subprocess
from pathlib import Path
import pandas as pd
import pytest
from src.data import ingest,load_sources,duplicate_candidates
from src.model import eligible,train,reasons

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def release():
    return ingest(ROOT/'data/raw/HZO_MFM_MFIS_확장통합_2026-11-16.xlsx')

def test_all_sheets_audited_and_subsets_not_double_counted(release):
    df,stats,papers=release
    assert len(df)==152 and df.record_id.nunique()==152
    assert len(stats['workbook_sheets'])==10
    assert stats['v2_subset_rows_not_added']==sum(s['rows']-1 for s in stats['workbook_sheets'] if s['role']=='subset')
    assert len(papers)==37
    assert df.structure.eq('MFIS').sum()==35
    assert df.review_status.eq('pending').all()
    assert df.source_row.min()==2
    assert df.sheet_membership.map(json.loads).map(len).max()>1

def test_conflicts_pr_bounds_and_survival_remain_distinct(release):
    df,_,_=release
    assert df.metric.eq('Pr/2Pr conflict').any()
    assert df.metric.eq('2Pr lower bound').sum()==2
    assert df.loc[df.metric.ne('2Pr'),'two_pr'].isna().all()
    assert df.pr.notna().any()
    row=df[df.endurance_relation.eq('FATIGUE_ONSET_NOT_FAILURE')].iloc[0]
    assert row.endurance_cycles==63_000_000
    assert 'NOT breakdown' in row.endurance_definition
    assert df.endurance_relation.eq('TESTED_TO').any()
    assert df[df.sample_group.eq('WANG23_400')].field_mv_cm.nunique()==3
    assert df.memory_window_v.isna().all() and df.threshold_shift_v.isna().all()

def test_attached_csv_is_lossless_and_does_not_invent_evidence():
    df,_,_=ingest(ROOT/'data/raw/hzo_new_mfm.csv')
    assert len(df)==37 and df.review_status.eq('pending').all()
    assert df.doi.isna().all() and df.source_locator.isna().all()
    row=df[df.sample_id.eq('N003')].iloc[0]
    assert row.endurance_cycles==50000 and row.endurance_relation=='시험종료'
    assert json.loads(row.raw_json)['end_type']=='시험종료'
    assert row.structure=='MFM'
    assert df.structure.eq('MFM(저자 표기 MFIM)').sum()==8
    assert df.pulse_s.isna().sum()>0  # Never fill from cycling pulse width.

def test_combined_review_gate_and_public_report(tmp_path):
    df,_,_=load_sources(ROOT/'data/raw')
    assert len(df)==301 and df.record_id.nunique()==301
    assert eligible(df).empty
    with pytest.raises(ValueError,match='20개'):train(df,tmp_path)
    assert not list(tmp_path.iterdir())
    report=json.loads((ROOT/'docs/model_status.json').read_text())
    assert report['approved_rows']==0 and report['approved_dois']==0
    assert report['training']['status']=='blocked_before_fit'
    assert all(t['active'] is False and t['MAE'] is None for t in report['targets'])

def test_different_measurement_cycles_preserved(release):
    df,_,_=release
    part=df[df.sample_group.eq('ASAPU22_RTA600')]
    assert set(part.wake_cycles)=={100,1_000_000,100_000_000}
    assert not duplicate_candidates(part).any()

def test_mfis_cannot_enter_legacy_mfm_model(release):
    df,_,_=release
    row=df[df.structure.eq('MFIS')].iloc[0].to_dict()
    row.update(review_status='approved',scope_verified=True,reviewer='test',evidence='test only')
    assert '기본 MFM 미확인' in reasons(row)
    assert eligible(pd.DataFrame([row])).empty

def test_javascript_syntax_and_external_module():
    html=(ROOT/'docs/index.html').read_text()
    assert '<script type="module" src="site.js"></script>' in html
    assert not re.search(r'<script>\s*\S',html)
    subprocess.run(['node','--check',str(ROOT/'docs/site.js')],check=True,capture_output=True)
    subprocess.run(['node','--check',str(ROOT/'docs/inference.js')],check=True,capture_output=True)
