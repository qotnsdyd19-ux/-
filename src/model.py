"""Conservative review gate, DOI-grouped validation, immutable model versions."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from src.data import duplicate_candidates,normalize_doi

NUM=['hzo_nm','top_nm','bottom_nm','anneal_c','anneal_s','voltage_v','wake_cycles','ald_c','pulse_s','frequency_hz']
CAT=['top','bottom','atmosphere','measurement_method','measurement_state','deposition']
REQUIRED=['hzo_nm','anneal_c','voltage_v','top','bottom','measurement_method','measurement_state','source_locator','doi']
OPTIONAL_NUM=[k for k in NUM if k not in REQUIRED]
OPTIONAL_CAT=[k for k in CAT if k not in REQUIRED]
MIN_ROWS=20
MIN_DOIS=5

def fingerprint(df):
    return hashlib.sha256(df.sort_values('record_id').fillna('').to_csv(index=False).encode()).hexdigest()

def reasons(row):
    issues=[]
    if row.get('review_status')!='approved': issues.append('원문 승인 대기')
    if row.get('possible_overlap') is True or isinstance(row.get('possible_overlap'),np.bool_) and row.get('possible_overlap'): issues.append('출처 간 중복 후보 · 독립 관측 확인 필요')
    if row.get('metric')!='2Pr' or pd.isna(row.get('two_pr')): issues.append('2Pr 레이블 없음 / Pr 분리')
    elif row['two_pr']<0: issues.append('이 모델의 2Pr 정의는 비음수 차이값 필요')
    if pd.notna(row.get('pr')) or pd.notna(row.get('two_pr_lower_bound')) or 'CONFLICT' in str(row.get('measurement_state') or ''): issues.append('Pr·하한·충돌은 2Pr 점값 학습에서 제외')
    if row.get('anneal_type')!='RTA': issues.append('RTA 미확인 / 비RTA')
    if row.get('structure')!='MFM': issues.append('기본 MFM 미확인')
    if row.get('composition')!='Hf:Zr=1:1': issues.append('Hf:Zr 1:1 미확인')
    if row.get('scope_verified') is not True: issues.append('단층·다결정·삽입층 없음 미확인')
    if pd.notna(row.get('il_material')) or (pd.notna(row.get('il_nm')) and row.get('il_nm')>0): issues.append('IL 포함 · 기본 MFM 모델 제외')
    for col in ['top_interlayer_nm','bottom_interlayer_nm']:
        if pd.notna(row.get(col)) and row[col]>0: issues.append('삽입층 / 다층 전극 제외')
    for col in NUM+['two_pr']:
        value=row.get(col)
        if pd.notna(value) and (not isinstance(value,(int,float,np.number)) or not np.isfinite(value)):
            issues.append('유한한 수치 필요: '+col)
    for col in REQUIRED:
        v=row.get(col)
        if v is None or pd.isna(v) or (isinstance(v,str) and not v.strip()): issues.append('결측: '+col)
    for col in ['hzo_nm','top_nm','bottom_nm','anneal_c','anneal_s','voltage_v']:
        if pd.notna(row.get(col)) and row[col]<=0: issues.append('양수 필요: '+col)
    if pd.notna(row.get('wake_cycles')) and row['wake_cycles']<0: issues.append('wake_cycles 음수')
    if row.get('measurement_method') not in ['P-E','PUND']: issues.append('P-E/PUND 정의 미확인')
    if not row.get('reviewer') or not row.get('evidence'): issues.append('검토자·원문 근거 없음')
    return issues

def apply_reviews(df,reviews):
    df=df.copy()
    for i,row in df.iterrows():
        rev=reviews.get(row.record_id)
        if not rev: continue
        for k,v in rev.get('corrections',{}).items():
            if k in NUM+CAT+['anneal_type','structure','composition','doi','source_locator','top_interlayer_nm','bottom_interlayer_nm','voltage_definition']: df.loc[i,k]=normalize_doi(v) if k=='doi' else v
        for k in ['review_status','scope_verified','reviewer','evidence','reviewed_at']: df.loc[i,k]=rev.get(k)
    return df

def eligible(df):
    flags=df.apply(lambda row:len(reasons(row))==0,axis=1)
    return df.loc[flags & ~duplicate_candidates(df)].copy()

def readiness(df,method=None):
    good=eligible(df)
    if method:good=good[good.measurement_method.eq(method)]
    return len(good)>=MIN_ROWS and good.doi.nunique()>=MIN_DOIS

def pipeline(numeric=None,categorical=None):
    numeric=NUM if numeric is None else numeric
    categorical=CAT if categorical is None else categorical
    prep=ColumnTransformer([
        ('num',Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True))]),numeric),
        ('cat',Pipeline([('impute',SimpleImputer(strategy='constant',fill_value='unknown')),('encode',OneHotEncoder(handle_unknown='ignore'))]),categorical)
    ])
    return Pipeline([('features',prep),('forest',RandomForestRegressor(n_estimators=300,min_samples_leaf=2,random_state=42,n_jobs=2))])

def scores(y,p):
    return dict(MAE=float(mean_absolute_error(y,p)),RMSE=float(np.sqrt(mean_squared_error(y,p))),R2=float(r2_score(y,p)) if len(y)>=3 and np.var(y)>0 else None)

def group_splits(df):
    return list(GroupKFold(n_splits=min(MIN_DOIS,df.doi.nunique())).split(df,df.two_pr,groups=df.doi))

def train(df,folder='artifacts/models',method=None):
    if not readiness(df,method): raise ValueError(f'동일 측정 방법으로 승인된 {MIN_ROWS}개 관측치 및 {MIN_DOIS}개 DOI가 필요합니다.')
    good=eligible(df).reset_index(drop=True)
    if method:good=good[good.measurement_method.eq(method)].reset_index(drop=True)
    if good.measurement_method.nunique()!=1:raise ValueError('P-E와 PUND는 별도 모델로 학습해야 합니다.')
    numeric=[k for k in NUM if good[k].notna().any()]
    categorical=[k for k in CAT if good[k].notna().any()]
    unused=[k for k in NUM+CAT if k not in numeric+categorical]
    missing_allowed=[k for k in OPTIONAL_NUM+OPTIONAL_CAT if good[k].isna().any()]
    x=good[NUM+CAT].copy(); x=x.where(x.notna(),np.nan); y=good.two_pr.to_numpy()
    pred=np.empty(len(good)); base=np.empty(len(good)); folds=[]
    for train_i,test_i in group_splits(good):
        p=pipeline(numeric,categorical); p.fit(x.iloc[train_i],y[train_i]); pred[test_i]=p.predict(x.iloc[test_i])
        d=DummyRegressor(strategy='mean'); d.fit(x.iloc[train_i],y[train_i]); base[test_i]=d.predict(x.iloc[test_i])
        folds.append(dict(train_dois=sorted(good.iloc[train_i].doi.unique()),test_dois=sorted(good.iloc[test_i].doi.unique()),test_records=len(test_i)))
    report=dict(forest=scores(y,pred),baseline=scores(y,base),folds=folds,rows=len(good),dois=int(good.doi.nunique()))
    improvement=1-report['forest']['MAE']/report['baseline']['MAE'] if report['baseline']['MAE']>0 else 0
    report['relative_mae_improvement']=improvement
    report['active']=improvement>=0.05 and (report['forest']['R2'] or 0)>0
    report.update(structure='MFM',target='2Pr',unit='μC/cm²',measurement_method=good.measurement_method.iloc[0],
                  validation='DOI-grouped out-of-fold',limitations='소수 논문 검증의 연구용 추정. 인과·공정 보증 및 보정된 예측구간 없음.')
    report.update(required_fields=REQUIRED,optional_numeric=OPTIONAL_NUM,optional_categorical=OPTIONAL_CAT,
                  used_features=numeric+categorical,unused_features=unused,missing_allowed=missing_allowed,
                  missing_policy='원본 결측 보존. 보간은 각 학습 fold 내부에서만 수행; 전체 결측 열 제외; 수치 결측 표시자 사용.')
    report['dataset_hash']=fingerprint(df)
    report['version']=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+report['dataset_hash'][:8]
    fitted=pipeline(numeric,categorical); fitted.fit(x,y)
    limits={k:[float(good[k].min()),float(good[k].max())] for k in NUM if good[k].notna().any()}
    categories={k:sorted(good[k].dropna().unique().tolist()) for k in CAT}
    bundle=dict(model=fitted,report=report,limits=limits,categories=categories,pairs=good[['top','bottom']].drop_duplicates().values.tolist())
    out=Path(folder)/report['version']; out.mkdir(parents=True,exist_ok=False)
    joblib.dump(bundle,out/'model.joblib'); good.to_csv(out/'dataset.csv',index=False)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return bundle

def latest(df,folder='artifacts/models'):
    paths=sorted(Path(folder).glob('*/report.json'),reverse=True)
    for path in paths:
        report=json.loads(path.read_text())
        if report['dataset_hash']==fingerprint(df) and report['active']:
            return joblib.load(path.parent/'model.joblib')
    return None

def predict(bundle,inputs,df=None):
    if bundle is None: return None,['검증된 활성 모델이 없습니다.']
    if not bundle['report']['active']: return None,['기준 모델보다 성능이 낮아 예측이 비활성화되었습니다.']
    if df is not None and bundle['report']['dataset_hash']!=fingerprint(df): return None,['데이터 또는 승인이 변경되었습니다. 재학습하세요.']
    issues=[]
    missing_allowed=bundle['report'].get('missing_allowed',[])
    unused=bundle['report'].get('unused_features',[])
    missing=lambda value:value is None or value is pd.NA or isinstance(value,(float,np.floating)) and np.isnan(value)
    for col in unused:
        if not missing(inputs.get(col)):issues.append(col+': 학습 자료가 없어 사용하지 않는 변수입니다. 미기재로 남기세요.')
    for col, (lo,hi) in bundle['limits'].items():
        value=inputs.get(col)
        if missing(value) and col in missing_allowed:continue
        if value is None or not isinstance(value,(int,float,np.number)) or not np.isfinite(value) or not lo<=value<=hi: issues.append(f'{col}: 학습 범위 {lo:g}–{hi:g} 밖 / 결측')
    for col,values in bundle['categories'].items():
        if missing(inputs.get(col)) and col in missing_allowed:continue
        if inputs.get(col) not in values: issues.append(col+': 학습에 없는 범주')
    if [inputs.get('top'),inputs.get('bottom')] not in bundle['pairs']: issues.append('학습에 없는 전극 조합')
    if inputs.get('multilayer'): issues.append('삽입층·다층은 Phase 1 예측 범위 밖')
    if issues: return None,issues
    query=pd.DataFrame([inputs]).reindex(columns=NUM+CAT)
    query=query.where(query.notna(),np.nan)
    return float(bundle['model'].predict(query)[0]),[]
