"""Apply explicit, source-backed decisions; importing a spreadsheet is not review."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
from src.data import SCHEMA, normalize_doi
from src.model import NUM, CAT, REQUIRED, apply_reviews

CONFIRMED = set(REQUIRED + ['two_pr','metric','structure','composition','scope_verified','measurement_definition','voltage_definition'])
CORRECTIONS = set(NUM+CAT+['anneal_type','structure','composition','doi','source_locator','top_interlayer_nm','bottom_interlayer_nm'])

def record_digest(row):
    values={}
    for k in SCHEMA:
        if k=='possible_overlap': continue  # Dataset-derived flag, recomputed separately.
        v=row.get(k)
        if v is None or pd.isna(v):v=None
        elif hasattr(v,'item'):v=v.item()
        values[k]=v
    return hashlib.sha256(json.dumps(values,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def verified_dataset(df,manifest_path,cache_dir):
    path=Path(manifest_path)
    if not path.exists():raise ValueError('검증 판정 파일이 없습니다.')
    manifest=json.loads(path.read_text())
    if manifest.get('schema_version')!=1:raise ValueError('지원하지 않는 검증 판정 버전')
    if not df.record_id.is_unique:raise ValueError('원본 record_id 중복')
    sources=manifest.get('sources',{})
    reviews={}; definitions={}; audits=[]
    indexed=df.set_index('record_id',drop=False)
    for decision in manifest.get('decisions',[]):
        rid=decision['record_id']
        if rid in reviews:raise ValueError('동일 기록의 판정 중복: '+rid)
        if rid not in indexed.index:raise ValueError('판정 대상 원본 없음: '+rid)
        row=indexed.loc[rid]
        if record_digest(row)!=decision.get('record_sha256'):raise ValueError('검토 후 원본 변경: '+rid)
        status=decision.get('review_status')
        if status not in {'approved','pending','rejected'}:raise ValueError('잘못된 검토 상태')
        if not decision.get('reviewer') or not decision.get('reviewed_at'):raise ValueError('검토자·검토일 필요')
        corrections=decision.get('corrections',{})
        if set(corrections)-CORRECTIONS:raise ValueError('검토 오버레이에서 레이블/임의 필드 변경 금지')
        citations=[]; confirmed=set()
        for evidence in decision.get('evidence',[]):
            source=sources.get(evidence.get('source_id'))
            if not source:raise ValueError('근거 문서 등록 없음')
            digest=source.get('sha256','')
            if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('원문 SHA256 필요')
            if urlparse(source.get('url','')).scheme!='https':raise ValueError('원문 HTTPS URL 필요')
            doi=normalize_doi(corrections.get('doi',row.doi))
            if not doi or normalize_doi(source.get('doi'))!=doi:raise ValueError('근거 DOI 불일치')
            doc=Path(cache_dir)/(digest+'.txt')
            if not doc.is_file() or hashlib.sha256(doc.read_bytes()).hexdigest()!=digest:raise ValueError('원문 캐시 없음/해시 불일치')
            excerpt=evidence.get('excerpt','')
            if len(excerpt.strip())<20 or not evidence.get('locator'):raise ValueError('구체적인 원문 인용·위치 필요')
            if ' '.join(excerpt.split()) not in ' '.join(doc.read_text().split()):raise ValueError('인용문이 원문에 없습니다.')
            confirmed.update(evidence.get('confirms',[]))
            citations.append({'url':source['url'],'sha256':digest,'locator':evidence['locator'],'excerpt':excerpt})
        if status=='approved':
            missing=CONFIRMED-set(confirmed)
            if missing:raise ValueError('원문 확인 항목 부족: '+', '.join(sorted(missing)))
            definition=decision.get('measurement_definition')
            method=corrections.get('measurement_method',row.get('measurement_method'))
            if definition!='2Pr_'+str(method) or method not in {'P-E','PUND'}:raise ValueError('2Pr 측정 정의를 방법별로 확인해야 합니다.')
            if decision.get('scope_verified') is not True:raise ValueError('기본 MFM 범위 검증 필요')
        review={k:decision.get(k) for k in ['review_status','reviewer','reviewed_at','scope_verified']}
        review.update(corrections=corrections,evidence=json.dumps(citations,ensure_ascii=False))
        reviews[rid]=review;definitions[rid]=decision.get('measurement_definition')
        audits.append({'record_id':rid,'status':status,'reviewer':decision['reviewer'],'source_count':len(citations)})
    # Input approval flags are not trusted; only this manifest can grant approval.
    base=df.copy();base['review_status']='pending'
    result=apply_reviews(base,reviews)
    result['measurement_definition']=result.measurement_definition.astype(object)
    for rid,definition in definitions.items():
        if definition:result.loc[result.record_id.eq(rid),'measurement_definition']=definition
    return result,audits
