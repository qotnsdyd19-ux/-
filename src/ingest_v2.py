"""Attached literature releases: preserve definitions, never grant approval."""
import hashlib
import json
from collections import Counter
from src.data import clean, number, normalize_doi, frame, NUMERIC

WORKBOOK_MAP = {
    'Record ID':'sample_id','구조':'structure','Sample Group (독립소자)':'sample_group',
    'HZO 두께 (nm)':'hzo_nm','Hf mol fraction':'hf_fraction',
    'Top electrode':'top','Top 두께 (nm)':'top_nm','Bottom electrode':'bottom','Bottom 두께 (nm)':'bottom_nm',
    '삽입층 / IL':'il_material','IL 두께 (nm)':'il_nm','IL 위치':'il_position',
    '증착법':'deposition','ALD 온도 (°C)':'ald_c','Anneal 종류':'anneal_type',
    '열처리 온도 (°C)':'anneal_c','열처리 시간 (s)':'anneal_s','열처리 분위기':'atmosphere',
    '2Pr (μC/cm²)':'two_pr','2Pr > bound':'two_pr_lower_bound','Pr (μC/cm²) ONLY':'pr',
    '2Pr/Pr 상태':'measurement_state','Wake-up/cycle count':'wake_cycles',
    'P-E 전압 (V)':'voltage_v','P-E 전계 (MV/cm)':'field_mv_cm',
    'Endurance cycles':'endurance_cycles','Endurance relation':'endurance_relation','Endurance 정의':'endurance_definition',
    'Cycling 전압 (V)':'cycling_voltage_v','Cycling 전계 (MV/cm)':'cycling_field_mv_cm',
    'Cycling 주파수 (Hz)':'cycling_frequency_hz','Cycling 온도 (°C)':'cycling_temperature_c',
    '숫자 신뢰도':'numeric_confidence','근거 수준':'evidence_level','원문 위치':'source_locator',
    '논문 제목':'paper','DOI':'doi','논문 URL':'source_url','2Pr ML 후보':'recommendation','특이사항 / 확인 필요':'notes',
}

CSV_MAP = {
    'id':'sample_id','paper':'paper','structure':'structure','crystal':'crystallinity',
    'bottom_electrode':'bottom','top_electrode':'top','thickness_nm':'hzo_nm',
    'deposition':'deposition','dep_temp_C':'ald_c','anneal_temp_C':'anneal_c','anneal_time_s':'anneal_s',
    'ambient':'atmosphere','meas_V':'voltage_v','meas_E':'field_mv_cm','meas_wave':'measurement_method',
    'meas_freq_Hz':'frequency_hz','meas_pw_s':'pulse_s','meas_T_K':'measurement_temperature_k',
    'state':'measurement_state','twoPr':'two_pr','cyc_V':'cycling_voltage_v','cyc_E':'cycling_field_mv_cm',
    'cyc_freq_Hz':'cycling_frequency_hz','cyc_pw_s':'cycling_pulse_s','endurance':'endurance_cycles',
    'end_type':'endurance_relation','end_twoPr':'end_two_pr','retain_pct':'retention_pct','use':'recommendation','note':'notes',
}

def finish(r,raw,name,sheet,row):
    r.update(source_file=name,source_sheet=sheet,source_row=row,review_status='pending',
             verification='미승인 · 원문·측정 정의·조건 검토 필요')
    r['original_structure']=r.get('structure')
    r['doi']=normalize_doi(r.get('doi'))
    r['raw_json']=json.dumps(raw,ensure_ascii=False,default=str,allow_nan=False)
    r['record_id']=hashlib.sha256((name+'|'+sheet+'|'+str(row)+'|'+r['raw_json']).encode()).hexdigest()[:20]
    for k in NUMERIC: r[k]=number(r.get(k))
    # Explicit bounds and conflicting definitions are not point labels.
    state=str(r.get('measurement_state') or '')
    if 'CONFLICT' in state:
        r['metric']='Pr/2Pr conflict'; r['two_pr']=None
    elif r.get('two_pr_lower_bound') is not None:
        r['metric']='2Pr lower bound'; r['two_pr']=None
    elif r.get('pr') is not None:
        r['metric']='Pr'; r['two_pr']=None
    else:
        r['metric']='2Pr' if r.get('two_pr') is not None else 'no_2Pr_label'
    r.setdefault('measurement_definition',state or '未確認 / 원문 검토 필요')
    r.setdefault('voltage_definition','원본 표기 보존 · ±V/Vpp/|V| 미확인')
    r.setdefault('cycling_voltage_definition','원본 표기 보존 · ±V/Vpp/|V| 미확인')
    r.setdefault('cycle_definition','원본 상태 필드 확인 · wake-up/측정/수명 횟수 구분 필요')
    if r.get('hf_fraction')==0.5:r['composition']='Hf:Zr=1:1'
    return r

def ingest_workbook(wb,name):
    sheet=wb['01_ALL_MERGED']; values=list(sheet.values); headers=values[0]
    primary={r[0]:r for r in values[1:] if r[0]}
    if len(primary)!=len(values)-1:raise ValueError('통합 시트 Record ID 중복')
    membership={k:[sheet.title] for k in primary}; inventory=[]; repeated=0
    for s in wb:
        entries=list(s.values)
        inventory.append({'sheet':s.title,'rows':s.max_row,'columns':s.max_column,
                          'role':'canonical' if s==sheet else 'index' if s.max_column!=44 else 'subset'})
        if s!=sheet and s.max_column==44:
            if entries[0]!=headers:raise ValueError('부분 시트 헤더 불일치: '+s.title)
            for row in entries[1:]:
                if primary.get(row[0])!=row:raise ValueError('부분 시트 기록 불일치: '+s.title+' '+str(row[0]))
                membership[row[0]].append(s.title); repeated+=1
    rows=[]
    for i,values in enumerate(values[1:],2):
        raw={k:clean(v) for k,v in zip(headers,values)}
        r={v:raw.get(k) for k,v in WORKBOOK_MAP.items()}
        r['sheet_membership']=json.dumps(membership[r['sample_id']],ensure_ascii=False)
        rows.append(finish(r,raw,name,sheet.title,i))
    papers=[{'source_file':name,**dict(zip(list(wb['08_PAPER_INDEX'].values)[0],v))}
            for v in list(wb['08_PAPER_INDEX'].values)[1:]]
    return frame(rows),{'duplicate_subset_rows':0,'non_2pr_rows':sum(r['metric']!='2Pr' for r in rows),
                        'v2_subset_rows_not_added':repeated,'workbook_sheets':inventory},papers

def ingest_csv(df,name):
    rows=[]
    for i,values in enumerate(df.to_dict('records'),2):
        raw={k:clean(v) for k,v in values.items()}
        r={v:raw.get(k) for k,v in CSV_MAP.items()}
        zr=number(raw.get('zr_x')); r['hf_fraction']=1-zr if zr is not None else None
        # Short citation keys are not DOI evidence or independent device IDs.
        r['sample_group']=None
        r['source_locator']=None
        r['endurance_definition']=raw.get('end_type')
        r['cycling_voltage_definition']='파형: '+str(raw.get('cyc_wave') or '미확인')+' · 전압 정의 미확인'
        r['measurement_definition']='원본 twoPr 열 후보 · Pr 변환 여부 원문 확인 필요'
        rows.append(finish(r,raw,name,'CSV',i))
    return frame(rows),{'duplicate_subset_rows':0,'non_2pr_rows':sum(r['metric']!='2Pr' for r in rows)},[]
