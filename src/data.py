"""Lossless workbook ingestion. Workbook recommendations are never approvals."""
from __future__ import annotations
import hashlib
import io
import json
import math
import re
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

NUMERIC = ['two_pr','hzo_nm','top_nm','bottom_nm','top_interlayer_nm','bottom_interlayer_nm','anneal_c','anneal_s','voltage_v','field_mv_cm','wake_cycles','ald_c','pulse_s','frequency_hz']
SCHEMA = ['record_id','source_file','source_sheet','source_row','sample_id','paper','doi','source_url','source_locator','metric','structure','composition','crystallinity','top','bottom','anneal_type','atmosphere','measurement_method','measurement_state','deposition','verification','recommendation','notes','raw_json'] + NUMERIC
MAP = {'2Pr (μC/cm²)':'two_pr','HZO (nm)':'hzo_nm','Top 전극':'top','Top 두께 (nm)':'top_nm','Bottom 전극':'bottom','Bottom 두께 (nm)':'bottom_nm','Top W 삽입층 (nm)':'top_interlayer_nm','Bottom W 삽입층 (nm)':'bottom_interlayer_nm','열처리 온도 (°C)':'anneal_c','열처리 시간 (s)':'anneal_s','열처리 방식':'anneal_type','분위기':'atmosphere','Wake-up 횟수':'wake_cycles','측정 |V| (V)':'voltage_v','증착법':'deposition','ALD 온도 (°C)':'ald_c','Sample ID':'sample_id','출처 DOI':'doi','출처 URL':'source_url','Fig / Table':'source_locator','원문 수치 검증':'verification','기존 데이터 상태':'recommendation','비고 / 확인사항':'notes'}
MAP2 = {'논문ID':'sample_id','논문':'paper','소자구조':'structure','결정성':'crystallinity','HZO 조성':'composition','HZO 두께 nm':'hzo_nm','하부전극':'bottom','하부전극 두께 nm':'bottom_nm','상부전극':'top','상부전극 두께 nm':'top_nm','RTA 온도 °C':'anneal_c','RTA 시간 s':'anneal_s','RTA 분위기':'atmosphere','인가전압 V':'voltage_v','인가전계 MV/cm':'field_mv_cm','펄스폭 s':'pulse_s','주파수 Hz':'frequency_hz','측정상태':'measurement_state','2Pr µC/cm²':'two_pr','학습사용':'recommendation','비고':'notes','원문':'source_url'}

def clean(value):
    if value is None or (isinstance(value, float) and math.isnan(value)): return None
    if isinstance(value, str): return value.strip() or None
    return value

def number(value):
    # No midpoint, range, units, or string-to-label guesses.
    if isinstance(value, bool): return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError): return None

def normalize_doi(value):
    if not value: return None
    match = re.search(r'10\.\d{4,9}/[^\s?#]+',str(value),re.I)
    return match.group(0).rstrip('/.,').lower() if match else None

def frame(rows):
    df = pd.DataFrame(rows).reindex(columns=SCHEMA)
    for col in NUMERIC: df[col] = pd.to_numeric(df[col],errors='coerce')
    return df

def ingest(source, name=None):
    name = name or Path(source).name
    if name.lower().endswith('.csv'):
        df = pd.read_csv(source)
        needed = {'sample_id','metric','two_pr','doi','source_locator'}
        if not needed.issubset(df.columns): raise ValueError('CSV 필수 열: '+', '.join(sorted(needed)))
        rows=[]
        for i,r in enumerate(df.to_dict('records'),2):
            r={k:clean(v) for k,v in r.items() if k in SCHEMA}
            r['raw_json']=json.dumps(r,ensure_ascii=False,default=str)
            r.update(source_file=name,source_sheet='CSV',source_row=i)
            r['record_id']=hashlib.sha256(r['raw_json'].encode()).hexdigest()[:20]
            r['doi']=normalize_doi(r.get('doi'))
            rows.append(r)
        return frame(rows),{'duplicate_subset_rows':0,'non_2pr_rows':0},[]
    wb = load_workbook(source,data_only=True)
    rows=[]; papers=[]; stats={'duplicate_subset_rows':0,'non_2pr_rows':0}
    if '01_2Pr_40행' in wb.sheetnames:
        s=wb['01_2Pr_40행']; headers=[c.value for c in s[1]]
        primary={}
        for cells in list(s)[1:]:
            raw={h:clean(c.value) for h,c in zip(headers,cells)}
            r={v:raw.get(k) for k,v in MAP.items()}
            r.update(metric='2Pr',composition='Hf:Zr=1:1',structure='MFM')
            primary[(r['sample_id'],normalize_doi(r.get('doi')))]=r
            rows.append((r,raw,s.title,cells[0].row))
        if '02_수치원문확인_10행' in wb.sheetnames:
            for cells in list(wb['02_수치원문확인_10행'])[1:]:
                raw={h:clean(c.value) for h,c in zip(headers,cells)}
                key=(raw.get('Sample ID'),normalize_doi(raw.get('출처 DOI')))
                if key in primary:
                    stats['duplicate_subset_rows']+=1
                    primary[key]['verification']=str(primary[key].get('verification') or '')+' · 중복 확인 시트 포함 (학습 승인 아님)'
                else: raise ValueError('확인 시트에 본 시트에 없는 기록: '+str(key))
        for r in wb['03_논문_20편'].iter_rows(min_row=2,values_only=True):
            papers.append(dict(zip([c.value for c in wb['03_논문_20편'][1]],r)))
        s=wb['04_2Pr아닌자료_9행']; headers=[c.value for c in s[1]]
        for cells in list(s)[1:]:
            raw={h:clean(c.value) for h,c in zip(headers,cells)}
            r=dict(sample_id=raw.get('sample_id'),metric=raw.get('reported_metric'),two_pr=None,top=raw.get('top_electrode'),bottom=raw.get('bottom_electrode'),hzo_nm=raw.get('hzo_thickness_nm'),source_url=raw.get('source_url'),source_locator=raw.get('source_locator'),verification=raw.get('review_status'),notes=raw.get('notes'))
            rows.append((r,raw,s.title,cells[0].row)); stats['non_2pr_rows']+=1
    elif '데이터' in wb.sheetnames:
        s=wb['데이터']; headers=[' '.join(str(c.value or '').split()) for c in s[4]]
        # First measurement block belongs to 2Pr. Later repeated headers belong to Endurance.
        for cells in list(s)[4:]:
            if not cells[0].value: continue
            raw={f'{i+1}:{h}':clean(c.value) for i,(h,c) in enumerate(zip(headers,cells))}
            r={}
            for i,(h,c) in enumerate(zip(headers,cells)):
                if 19<=i<=24: continue
                if h in MAP2: r[MAP2[h]]=clean(c.value)
            link=cells[27].hyperlink
            r['source_url']=link.target if link else None
            r['doi']=normalize_doi(r['source_url'])
            r['anneal_type']=None # Header mentions RTA, but does not certify each row's treatment.
            r['metric']='2Pr' if number(r.get('two_pr')) is not None else 'no_2Pr_label'
            r['verification']='원문·Methods 검토 대기 (권장은 승인 아님)'
            rows.append((r,raw,s.title,cells[0].row))
        if '논문목록' in wb.sheetnames:
            for cells in list(wb['논문목록'])[1:]:
                if not cells[0].value: continue
                papers.append(dict(paper_id=cells[0].value,title=cells[1].value,source_url=cells[5].hyperlink.target if cells[5].hyperlink else None,cohort='데이터2'))
    else: raise ValueError('지원하는 HZO 시트가 없습니다. 정규화 CSV 또는 원본 HZO Excel을 사용하세요.')
    result=[]
    for r,raw,sheet,row in rows:
        r['raw_json']=json.dumps(raw,ensure_ascii=False,default=str)
        r.update(source_file=name,source_sheet=sheet,source_row=row)
        r['record_id']=hashlib.sha256((name+'|'+sheet+'|'+str(row)+'|'+r['raw_json']).encode()).hexdigest()[:20]
        r['doi']=normalize_doi(r.get('doi'))
        for k in NUMERIC: r[k]=number(r.get(k))
        result.append(r)
    return frame(result),stats,papers

def load_sources(folder):
    datasets=[]; stats={'duplicate_subset_rows':0,'non_2pr_rows':0}; papers=[]
    for path in sorted(Path(folder).glob('*.xlsx')):
        df,counts,p=ingest(path); datasets.append(df); papers.extend(p)
        for k,v in counts.items(): stats[k]+=v
    return pd.concat(datasets,ignore_index=True) if datasets else frame([]),stats,papers

def duplicate_candidates(df):
    cols=['doi','two_pr','hzo_nm','top','bottom','anneal_c','voltage_v']
    # Flag possible cross-source duplicates, never silently collapse independent measurements.
    return df['doi'].notna() & df['two_pr'].notna() & df.duplicated(cols,keep=False)

def export(folder='data/raw',output='data'):
    df,stats,papers=load_sources(folder)
    out=Path(output); out.mkdir(parents=True,exist_ok=True)
    df.to_csv(out/'normalized.csv',index=False)
    (out/'papers.json').write_text(json.dumps(papers,ensure_ascii=False,indent=2,default=str))
    stats.update(total_records=len(df),two_pr_candidates=int((df.metric.eq('2Pr')&df.two_pr.notna()).sum()),approved_records=0,possible_duplicate_rows=int(duplicate_candidates(df).sum()),missing={k:int(df[k].isna().sum()) for k in NUMERIC},note='원문 미검증. 모든 기록은 조회 전용으로 시작합니다.')
    (out/'quality.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    return df,stats,papers

if __name__=='__main__':
    print(json.dumps(export()[1],ensure_ascii=False,indent=2))
