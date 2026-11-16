"""Audit original metadata and missing evidence; never infer approval from metadata."""
import json
from pathlib import Path
import sys
from collections import Counter
import pandas as pd
from openpyxl import load_workbook
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data import load_sources
from src.model import REQUIRED,OPTIONAL_NUM,OPTIONAL_CAT,MIN_ROWS,MIN_DOIS,eligible

LEGACY_REQUIRED=['hzo_nm','top_nm','bottom_nm','anneal_c','anneal_s','voltage_v','wake_cycles','top','bottom','atmosphere','measurement_method','measurement_state','source_locator','doi']
PRIORITY=['10.3390/ma18153547','10.3390/nano12030548','10.1021/acsami.4c17978','10.3390/nano13101608','10.3390/nano12173001']

def audit(root):
    root=Path(root);df,_,_=load_sources(root/'data/raw')
    m=df[df.structure.eq('MFM') & df.metric.eq('2Pr') & df.two_pr.notna()].copy()
    mfis=df[df.structure.eq('MFIS')]
    missing={k:int(m[k].isna().sum()) for k in dict.fromkeys(LEGACY_REQUIRED+OPTIONAL_NUM+OPTIONAL_CAT)}
    complete=lambda fields:int(m[fields].notna().all(axis=1).sum())
    inventory=[]
    for path in sorted((root/'data/raw').glob('*.xlsx')):
        wb=load_workbook(path,data_only=True)
        inventory.append({'file':path.name,'sheets':[{'name':s.title,'rows':s.max_row,'columns':s.max_column} for s in wb]})
    secondary=m[['source_locator','evidence_level']].fillna('').astype(str).agg(' '.join,axis=1).str.contains(r'review|secondary|\bref\b|benchmark',case=False,regex=True)
    m['secondary_hint']=secondary
    requests=[]
    m['request_key']=m.apply(lambda r:'doi:'+r.doi if pd.notna(r.doi) else 'unresolved:'+r.source_file+':'+str(r.paper if pd.notna(r.paper) else r.sample_id),axis=1)
    for key,g in m.groupby('request_key',sort=True):
        doi=g.doi.dropna().iloc[0] if g.doi.notna().any() else ''
        locators=sorted(set(g.source_locator.dropna().astype(str)))
        requests.append({'doi':doi,'paper_keys':' | '.join(sorted(set(g.paper.dropna().astype(str)))),'candidate_source_rows':len(g),
                         'reported_rta_rows':int(g.anneal_type.eq('RTA').sum()),
                         'source_urls':' | '.join(sorted(set(g.source_url.dropna().astype(str)))),
                         'record_ids':' | '.join(g.record_id),
                         'original_locations':' | '.join(f'{r.source_file} / {r.source_sheet} / row {int(r.source_row)} / {r.sample_id}' for _,r in g.iterrows()),
                         'reported_figure_table':' | '.join(locators) or '미기재',
                         'pdf_pages':'원문 PDF 미확보: 페이지 번호 확인 불가',
                         'needed_sections':'Methods/Experimental 전체; '+(' | '.join(locators) if locators else '2Pr 수치·정의를 보고한 Figure/Table와 캡션; 해당 위치 식별 필요'),
                         'needed_confirmation':'DOI; 2Pr/Pr/PUND 정의·단위; 수치; 소자/조성/삽입층; 측정 전압 정의·방법·상태; 공정 조건',
                         'missing_core_fields':json.dumps({k:int(g[k].isna().sum()) for k in REQUIRED if g[k].isna().any()},ensure_ascii=False),
                         'priority':PRIORITY.index(doi)+1 if doi in PRIORITY else 100,
                         'primary_pdf_needed':'요약/리뷰의 해당 표가 인용한 원논문 PDF도 필요; 원논문 DOI 확인 필요' if g.secondary_hint.any() else '해당 DOI의 원논문 PDF와 보충자료 필요',
                         'review_status':'pending_original_source'})
    queue=pd.DataFrame(requests).sort_values(['priority','doi','paper_keys'])
    out=root/'docs';queue.to_csv(out/'required_pdfs.csv',index=False)
    mfis_requests=[]
    for doi,group in mfis.groupby('doi',dropna=False):
        mfis_requests.append({'doi':doi,'source_records':len(group),'record_ids':' | '.join(group.record_id),
                              'source_urls':' | '.join(sorted(set(group.source_url.dropna().astype(str)))),
                              'reported_locations':' | '.join(sorted(set(group.source_locator.dropna().astype(str)))),
                              'pdf_pages':'원문 PDF 미확보: 페이지 번호 확인 불가',
                              'needed_measurements':'실제 MW(V) 또는 ΔVth(V); FeFET Vth와 capacitor Vfb/C-V 폭의 정의 구분; 기준 상태와 program/erase/read 조건',
                              'needed_protocol':'동일 소자·조건의 두 전압 원값; 추출 기준; C-V 주파수/스윕 또는 FET drain/current 기준; 반복 횟수; 실패/검열 정의'})
    pd.DataFrame(mfis_requests).to_csv(out/'mfis_measurement_requests.csv',index=False)
    raw_review=df[['record_id','sample_id','structure','metric','source_file','source_sheet','source_row','doi']].copy()
    raw_review['missing_core_fields']=df.apply(lambda r:'; '.join(k for k in REQUIRED if pd.isna(r.get(k))),axis=1)
    raw_review['missing_optional_fields']=df.apply(lambda r:'; '.join(k for k in OPTIONAL_NUM+OPTIONAL_CAT if pd.isna(r.get(k))),axis=1)
    raw_review['approval']='pending'  # This audit grants no source review decisions.
    raw_review.to_csv(out/'training_blockers.csv',index=False)
    approved=eligible(df)
    report={'status':'데이터 검증 부족으로 학습 불가','total_source_records':len(df),'mfm_2pr_candidate_rows':len(m),
            'mfm_candidate_known_dois':int(m.doi.nunique()),'approved_rows':len(approved),'approved_dois':int(approved.doi.nunique()),
            'legacy_required_fields':LEGACY_REQUIRED,'core_required_fields':REQUIRED,
            'optional_numeric_fields':OPTIONAL_NUM,'optional_categorical_fields':OPTIONAL_CAT,
            'reported_missing_counts':missing,'legacy_complete_rows':complete(LEGACY_REQUIRED),'core_complete_rows':complete(REQUIRED),
            'rows_with_doi_and_reported_method':int((m.doi.notna() & m.measurement_method.notna()).sum()),
            'rows_with_supported_method':int(m.measurement_method.isin(['P-E','PUND']).sum()),
            'source_overlap_candidate_rows':int(m.possible_overlap.sum()),'secondary_evidence_hint_rows':int(secondary.sum()),
            'training_requirement':{'min_rows_per_method':MIN_ROWS,'min_independent_dois':MIN_DOIS,'missing_approved_rows':max(0,MIN_ROWS-len(approved)),'missing_approved_dois':max(0,MIN_DOIS-approved.doi.nunique())},
            'training':'not_fitted','cross_validation':'not_run','MAE':None,'RMSE':None,'R2':None,
            'public_research_model_two_input_test':'not_run_no_validated_model','public_inference_deployment':'not_deployed',
            'mfis':{'source_rows':len(mfis),'two_pr_candidates':int((mfis.metric.eq('2Pr') & mfis.two_pr.notna()).sum()),'memory_window_labels':int(mfis.memory_window_v.notna().sum()),'threshold_shift_labels':int(mfis.threshold_shift_v.notna().sum()),'endurance_candidates':int(mfis.endurance_cycles.notna().sum())},
            'workbooks':inventory,'pdf_request_groups':len(queue),
            'interpretation':'Counts describe supplied metadata, not verified measurements or independent devices. No missing value was invented and no row was approved.'}
    (out/'training_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# 실제 예측 활성화 점검 결과','', '**현재 상태: 데이터 검증 부족으로 학습 불가 / 추가 원문 자료 또는 사용자 설정 필요. 실제 모델 추론 미완료.**','',
           f'원본 Excel의 {sum(len(w["sheets"]) for w in inventory)}개 시트와 통합 {len(df)}행을 다시 검사했습니다. MFM 2Pr 후보 {len(m)}행, DOI가 있는 후보 {int(m.doi.notna().sum())}행 / {int(m.doi.nunique())} DOI입니다. 후보 수는 원문 승인 수나 독립 소자 수가 아닙니다.','',
           f'| 필드 | 후보 {len(m)}행 중 결측 | 수정한 정책 |','|---|---:|---|']
    for field in LEGACY_REQUIRED:lines.append(f'| {field} | {missing[field]} | '+('필수: 측정 대상·조건·출처 식별' if field in REQUIRED else '선택: 실제 보고·검증된 값만 사용, 원본 결측 유지')+' |')
    lines += ['',f'기존 필수 항목이 모두 기록된 행: {report["legacy_complete_rows"]}. 선택 변수 5개를 필수에서 제외한 뒤 핵심 항목이 모두 기록된 행도 {report["core_complete_rows"]}입니다. **DOI와 측정 방법이 동시에 기록된 행이 {report["rows_with_doi_and_reported_method"]}행**이므로 선택 변수 완화만으로 원문 검증 문제를 해결할 수 없습니다.', '',
              '전극 두께·열처리 시간·분위기·정확한 wake-up 횟수는 연구 결과에 영향을 줄 수 있지만, 제한된 관측 자료에서 모두 필수로 두는 것은 과도했습니다. 해당 필드는 선택으로 바꿨습니다. 원본/공개 CSV에 값을 채우지 않습니다. 실제 검증된 선택 값만 사용하고, 보간은 학습 fold 안에서만 수행하며 수치 결측 표시자를 추가합니다. 전체 결측 열은 모델에서 제외합니다. 모델이 학습하지 않은 변수의 값을 입력해 효과를 예측했다고 표시하지 않습니다.', '',
              'hzo_nm·anneal_c·voltage_v와 전극·측정 방법·측정 상태·DOI·원문 위치는 이 공정/측정 조건 기반 2Pr 모델의 필수 항목으로 유지합니다. 구조 MFM, 조성, 삽입층/다층 여부와 2Pr/Pr/PUND 및 전압 정의는 별도의 원문 확인 대상입니다. 확인되지 않은 상태를 pristine, wake-up 0회, RTA 또는 단일 전극으로 추측하지 않습니다. 명시적으로 측정한 2Pr=0은 허용하되, “강유전성 없음”이라는 문장만으로 0을 만들어 승인하지 않습니다.', '',
              '## 원문 확인과 필요한 PDF','',
              f'[필요한 원문·Figure/Table·원본 행 전체 목록](docs/required_pdfs.csv)을 생성했습니다. DOI 없는 {int(m.doi.isna().sum())}행은 파일/논문 키별로 별도 요청합니다. PDF를 확보하지 못했으므로 **PDF 페이지 번호는 확인 불가**로 기록했습니다. 아래 Figure/Table 위치도 첨부 자료에 기재된 단서이며 실제 대조 결과가 아닙니다. 초록·리뷰 표만 있는 경우 원 논문의 Methods와 해당 수치 위치가 추가로 필요합니다.','',
              '| 우선 확인 DOI | 해당 논문의 후보 행 | 첨부 자료의 위치 단서 |','|---|---:|---|']
    for _,r in queue[queue.priority.lt(100)].iterrows():lines.append(f'| {r.doi} | {r.candidate_source_rows} | {str(r.reported_figure_table).replace(chr(124), " / ")} |')
    lines += ['', '환경 프록시가 원문 요청을 403으로 거절했습니다. 원문 접근 53 DOI의 마지막 결과는 [접근 상태](docs/source_access_status.json)에 기록했습니다. 새 승인 기록을 만들지 않았습니다. 환경 설정의 저장된 도메인 허용 변경을 적용하거나, 위 목록에 해당하는 원문 PDF(Methods·Figure/Table·캡션·보충자료 포함)가 필요합니다.', '',
              '## 학습 기준과 정확한 부족량','',
              f'승인 관측치 {len(approved)}행 / 독립 DOI {int(approved.doi.nunique())}개. P-E와 PUND 각각 최소 {MIN_ROWS}행 / {MIN_DOIS} DOI 기준에 대해 **승인 {MIN_ROWS}행과 독립 DOI {MIN_DOIS}개가 부족**합니다. P-E/PUND를 합쳐 조건을 맞추지 않습니다.', '',
              '20행·5 DOI는 통계적 신뢰성이 보장되는 수가 아니라 기존 공개 모델 활성화의 운영 기준입니다. GroupKFold 자체는 2개 그룹부터 가능하지만, 동일 논문의 여러 조건을 독립 표본처럼 합산하면 성능이 과대평가될 수 있습니다. 현재 승인 0행이므로 이 숫자를 낮춰도 검증된 데이터가 생기지 않습니다. 기준은 유지합니다. 실제 학습은 차단됐으며 DOI 분리 MAE/RMSE/R²는 N/A입니다. 단순 평균 기준과의 비교나 교차검증을 실행했다고 주장하지 않습니다.', '',
              '## MFIS','',
              f'MFIS {len(mfis)}행 중 Memory Window 수치 {report["mfis"]["memory_window_labels"]}행, Threshold Voltage Shift 수치 {report["mfis"]["threshold_shift_labels"]}행입니다. 2Pr 후보 {report["mfis"]["two_pr_candidates"]}행을 Memory Window나 MFM 모델로 바꾸어 사용하지 않습니다. 별도 MFIS 학습 모델은 아직 학습할 수 없습니다.', '',
              '[MFIS 원문·실측값 요청 목록](docs/mfis_measurement_requests.csv)도 별도로 작성했습니다. 첨부 원본의 모든 열·비고를 확인했으며, 논문 제목의 memory 및 Pr/파괴 임계값을 Vth 측정값으로 오인하지 않았습니다. 이는 첨부 자료의 레이블 부재를 뜻하며, 접근하지 못한 논문 전체에 해당 측정값이 없다는 주장과는 다릅니다.', '',
              '추가로 필요한 실측 열: sample/device ID, DOI/원문 위치, 게이트 재료/두께, HZO 조성/두께, IL 재료/두께/위치, 반도체/도핑, 열처리, program/erase 각각의 전압·펄스폭, read 지연/바이어스, 온도, 반복 횟수와 상태. Memory Window는 측정 정의별로 구분해야 합니다. FeFET의 Vth_program−Vth_erase (V)는 두 Vth와 전류/드레인 바이어스·추출 기준을, MFIS capacitor의 Vfb 차이 또는 C-V 히스테리시스 폭은 두 전압과 flat-band/C 기준·주파수·스윕 방향을 함께 보고해야 합니다. 이 정의들을 하나의 MW 레이블로 합치지 않습니다. Threshold shift는 실제 FET의 Vth(N)−Vth(reference) (V)와 기준 상태를 명시해야 하며, capacitor의 ΔVfb를 ΔVth로 바꾸지 않습니다. Endurance는 고장 기준과 시험 종료/검열 구분 및 Ncycles에서의 실제 MW/ΔVth를 별도로 제공해야 합니다. 단위·측정 정의가 없는 숫자를 임의로 결합하지 않습니다.', '',
              '## 학습·배포·실제 작동 여부','',
              '기존 Python API·모델 버전·범위 검사·사이트 연결 코드는 유지했습니다. 실제 승인 모델이 없으므로 공개 Python 추론 서버를 활성화하거나 Pages 버튼을 임의로 켜지 않았습니다. 공개 연구 모델로 두 입력을 계산하는 검증은 미실행입니다. 합성 fixture의 소프트웨어 테스트는 이 완료 기준을 충족하지 않습니다. 배포 계정 연결과 실제 검증 모델 내보내기 후에만 [배포 절차](DEPLOYMENT.md)를 진행할 수 있습니다. 새 디자인이나 기능 추가를 완료로 대체하지 않습니다.','']
    (root/'TRAINING_AUDIT.md').write_text('\n'.join(lines))
    return report

if __name__=='__main__':
    result=audit(Path(__file__).resolve().parents[1])
    print(json.dumps({k:result[k] for k in ['status','mfm_2pr_candidate_rows','core_complete_rows','rows_with_doi_and_reported_method','approved_rows','approved_dois','mfis']},ensure_ascii=False,indent=2))
