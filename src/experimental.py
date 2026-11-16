"""User-authorized supplied-data experiments. Never grants source approval."""
from pathlib import Path
import hashlib,json,re
import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import GroupKFold
from src.data import load_sources
from src.model import pipeline,scores
from src.serving import sha256,source_release_digest

NUMERIC=['hzo_nm','anneal_c','voltage_v','anneal_s']
CATEGORICAL=['top','bottom','anneal_type','measurement_state']
CORE=['hzo_nm','anneal_c','top','bottom']
METALS={'TiN','W','Mo','Pt','Ru','Au','Ni','Pd','TaN','NbN','β-W'}
WARNING='제공 자료 기반 실험용 모델입니다. 원문 독립 검증 전이며 교차검증 성능이 미달할 수 있습니다. 공정 결정·검증된 물성값으로 사용하지 마세요.'

def prepare(root):
    df,_,_=load_sources(Path(root)/'data/raw')
    candidates=df[df.structure.eq('MFM') & df.metric.eq('2Pr') & df.two_pr.notna()].copy()
    known_protocol_dois=set()
    for _,row in candidates[candidates.doi.notna()].iterrows():
        text=' '.join(str(v) for v in json.loads(row.raw_json).values() if isinstance(v,str))
        if pd.notna(row.measurement_method) or re.search(r'\bPUND\b|P\s*[-–−]\s*[EV]\b',text,re.I):known_protocol_dois.add(row.doi)
    kept=[];excluded=[]
    for _,r in candidates.iterrows():
        reasons=[]
        if not pd.notna(r.doi):reasons.append('DOI 없음: 논문별 분리 평가 불가')
        if any(pd.isna(r[k]) for k in CORE):reasons.append('핵심 공정/전극 정보 없음')
        if r.top not in METALS or r.bottom not in METALS:reasons.append('복합/미지원 전극: 문자열을 단일 전극으로 바꾸지 않음')
        if r.composition!='Hf:Zr=1:1':reasons.append('첨부 자료에서 Hf:Zr=1:1 미확인')
        if pd.notna(r.il_material) or any(pd.notna(r[k]) and r[k]>0 for k in ['il_nm','top_interlayer_nm','bottom_interlayer_nm']):reasons.append('보고된 삽입층 있음: 단일 전극 실험 범위 제외')
        if r.two_pr<0:reasons.append('비음수 2Pr 차이값 범위 제외')
        # Keep known protocols separate. An unknown method is explicitly NOT P-E/PUND.
        method=str(r.measurement_method) if pd.notna(r.measurement_method) else ''
        state=str(r.measurement_state) if pd.notna(r.measurement_state) else ''
        if r.doi in known_protocol_dois or method or re.search(r'\bPUND\b',state,re.I):reasons.append('측정 방법이 기재된 별도 자료군: 미확인 자료군과 합치지 않음')
        item={'record_id':r.record_id,'sample_id':r.sample_id,'doi':r.doi,'reason':'; '.join(reasons)}
        if reasons:excluded.append(item)
        else:kept.append(r.to_dict())
    data=pd.DataFrame(kept).reindex(columns=df.columns)
    # Conservative exact reported-condition duplicate consolidation; raw sources remain intact.
    key=['doi','two_pr','hzo_nm','anneal_c','voltage_v','measurement_state','top','bottom','wake_cycles','frequency_hz']
    duplicate=data.duplicated(key,keep='first')
    for _,r in data[duplicate].iterrows():excluded.append({'record_id':r.record_id,'sample_id':r.sample_id,'doi':r.doi,'reason':'동일 DOI·레이블·보고 조건 중복 후보: 원본 보존, 학습 합산 제외'})
    data=data[~duplicate].reset_index(drop=True)
    return data,pd.DataFrame(excluded),len(candidates)

def portable(bundle):
    model=bundle['model'];prep=model.named_steps['features']
    num=prep.named_transformers_['num'].named_steps['impute']
    cat=prep.named_transformers_['cat']
    return {'format':'sklearn-random-forest-v1','report':bundle['report'],'limits':bundle['limits'],'categories':bundle['categories'],
            'pairs':bundle['pairs'],'missing_allowed':bundle['missing_allowed'],
            'preprocessing':{'numeric':NUMERIC,'numeric_fill':num.statistics_.tolist(),'numeric_indicators':num.indicator_.features_.tolist(),
                             'categorical':CATEGORICAL,'categorical_fill':cat.named_steps['impute'].statistics_.tolist(),
                             'onehot_categories':[a.tolist() for a in cat.named_steps['encode'].categories_]},
            'trees':[{'feature':t.tree_.feature.tolist(),'threshold':t.tree_.threshold.tolist(),'left':t.tree_.children_left.tolist(),
                      'right':t.tree_.children_right.tolist(),'value':t.tree_.value[:,0,0].tolist()} for t in model.named_steps['forest'].estimators_]}

def predict(bundle,inputs,acknowledged=False):
    if not acknowledged:raise ValueError('원문 미검증·교차검증 결과를 확인하고 실험용 계산에 동의해야 합니다.')
    report=bundle['report']
    for k in CORE:
        if inputs.get(k) is None or inputs.get(k)=='':raise ValueError('필수 입력: '+k)
    for k,(lo,hi) in bundle['limits'].items():
        value=inputs.get(k)
        if value is None and k in bundle['missing_allowed']:continue
        if isinstance(value,bool) or not isinstance(value,(int,float,np.number)) or not np.isfinite(value) or not lo<=value<=hi:raise ValueError(f'{k}: 학습 범위 {lo:g}–{hi:g} 밖 / 미기재')
    for k,values in bundle['categories'].items():
        value=inputs.get(k)
        if value is None and k in bundle['missing_allowed']:continue
        if value not in values:raise ValueError(k+': 제공 자료에 없는 범주')
    if [inputs.get('top'),inputs.get('bottom')] not in bundle['pairs']:raise ValueError('제공 자료에 없는 전극 조합')
    x=pd.DataFrame([inputs]).reindex(columns=NUMERIC+CATEGORICAL);x=x.where(x.notna(),np.nan)
    value=float(bundle['model'].predict(x)[0])
    return {'kind':'experimental_model_prediction','value':value,'unit':'μC/cm²','structure':'MFM','target':'2Pr','model_version':report['version'],
            'dataset_hash':report['dataset_hash'],'source_review_verified':False,'validation_passed':report['validation_passed'],
            'validation':report['forest'],'baseline':report['baseline'],'inputs':inputs,'limitations':WARNING}

def train(root,output=None):
    root=Path(root);out=Path(output or root/'models-experimental');data,excluded,candidates=prepare(root)
    if len(data)<20 or data.doi.nunique()<5:raise ValueError('실험용 논문 분리 평가에 필요한 20행·5 DOI 부족')
    x=data[NUMERIC+CATEGORICAL].copy();x=x.where(x.notna(),np.nan);y=data.two_pr.to_numpy()
    predictions=np.zeros(len(data));baseline=np.zeros(len(data));folds=[]
    for a,b in GroupKFold(5).split(x,y,groups=data.doi):
        model=pipeline(NUMERIC,CATEGORICAL);model.fit(x.iloc[a],y[a]);predictions[b]=model.predict(x.iloc[b])
        dummy=DummyRegressor(strategy='mean');dummy.fit(x.iloc[a],y[a]);baseline[b]=dummy.predict(x.iloc[b])
        folds.append({'train_dois':sorted(data.iloc[a].doi.unique()),'test_dois':sorted(data.iloc[b].doi.unique()),'rows':len(b),
                      'forest':scores(y[b],predictions[b]),'baseline':scores(y[b],baseline[b])})
    rf=scores(y,predictions);base=scores(y,baseline);passed=rf['MAE']<=.95*base['MAE'] and (rf['R2'] or 0)>0
    csv=data.to_csv(index=False);digest=hashlib.sha256((csv+'experimental-process-v1').encode()).hexdigest();version='provided-2pr-'+digest[:12]
    report={'version':version,'validation_level':'provided_data_experimental','source_review_verified':False,'source_approved_rows':0,
            'available_for_experiments':True,'active':False,'validation_passed':bool(passed),'requires_acknowledgement':True,
            'structure':'MFM','target':'2Pr','measurement_method':'unconfirmed','measurement_definition':'자료 표기 2Pr; 원문 독립 검증 전·측정 정의 미확인',
            'unit':'μC/cm²','rows':len(data),'dois':int(data.doi.nunique()),'candidate_rows':candidates,'excluded_rows':len(excluded),
            'dataset_hash':digest,'source_release_sha256':source_release_digest(root),'forest':rf,'baseline':base,'folds':folds,
            'parameters':{'n_estimators':300,'min_samples_leaf':2,'random_state':42,'validation':'GroupKFold(5), DOI'},
            'used_features':NUMERIC+CATEGORICAL,'required_fields':CORE,'optional_fields':[k for k in NUMERIC+CATEGORICAL if k not in CORE],
            'limitations':WARNING,'scope':'첨부 자료의 MFM·Hf:Zr=1:1·단일 전극·측정법 미기재 자료군. P-E/PUND 언급 논문과 Pr/하한/충돌 자료는 혼합하지 않음.'}
    model=pipeline(NUMERIC,CATEGORICAL);model.fit(x,y)
    bundle={'model':model,'report':report,'limits':{k:[float(data[k].min()),float(data[k].max())] for k in NUMERIC},
            'categories':{k:sorted(data[k].dropna().unique().tolist()) for k in CATEGORICAL},
            'missing_allowed':[k for k in NUMERIC+CATEGORICAL if data[k].isna().any()],
            'pairs':data[['top','bottom']].drop_duplicates().values.tolist()}
    folder=out/version;folder.mkdir(parents=True,exist_ok=True)
    joblib.dump(bundle,folder/'model.joblib');(folder/'dataset.csv').write_text(csv);excluded.to_csv(folder/'excluded.csv',index=False)
    data[['record_id','sample_id','doi','two_pr']].assign(prediction=predictions,baseline_prediction=baseline).to_csv(folder/'oof.csv',index=False)
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    (out/'index.json').write_text(json.dumps({'version':version,'model_sha256':sha256(folder/'model.joblib'),'report_sha256':sha256(folder/'report.json')},indent=2))
    document=portable(bundle);encoded=json.dumps(document,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    (root/'docs/experimental-model.json').write_text(encoded)
    (root/'docs/experimental-training.csv').write_text(csv)
    excluded.to_csv(root/'docs/experimental-exclusions.csv',index=False)
    (root/'docs/experimental-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    # Real supplied-data functional cases; not a runtime prediction lookup table.
    examples=[]
    for _,r in data.iterrows():
        inp={k:None if pd.isna(r[k]) else r[k] for k in NUMERIC+CATEGORICAL}
        examples.append({'inputs':inp,'result':predict(bundle,inp,True),'record_id':r.record_id})
    examples=sorted(examples,key=lambda e:e['result']['value']);examples=[examples[0],examples[-1]]
    (root/'docs/experimental-cases.json').write_text(json.dumps([{'inputs':e['inputs'],'record_id':e['record_id']} for e in examples],ensure_ascii=False,indent=2,allow_nan=False))
    config={'mode':'experimental_browser','api_base_url':None,'model_url':'experimental-model.json','model_version':version,
            'model_sha256':hashlib.sha256(encoded.encode()).hexdigest()}
    (root/'docs/inference-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    return bundle,examples

def load(root):
    root=Path(root);folder=root/'models-experimental';index=json.loads((folder/'index.json').read_text());version=index['version']
    if not re.fullmatch(r'provided-2pr-[0-9a-f]{12}',version):raise ValueError('실험용 모델 경로 오류')
    path=folder/version
    if sha256(path/'model.joblib')!=index['model_sha256'] or sha256(path/'report.json')!=index['report_sha256']:raise ValueError('실험용 모델 해시 불일치')
    report=json.loads((path/'report.json').read_text())
    if report.get('source_review_verified') is not False or report.get('validation_level')!='provided_data_experimental':raise ValueError('실험용 표시 불일치')
    if report['source_release_sha256']!=source_release_digest(root):raise ValueError('원본 변경: 실험용 모델 재학습 필요')
    bundle=joblib.load(path/'model.joblib')
    if bundle['report']!=report:raise ValueError('실험용 모델과 보고서 불일치')
    return bundle
