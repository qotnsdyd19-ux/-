from pathlib import Path
import io
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from src.data import load_sources, ingest, NUMERIC, duplicate_candidates
from src.model import NUM, CAT, REQUIRED, MIN_ROWS, MIN_DOIS, apply_reviews, eligible, reasons, readiness, latest, train, predict
from src.store import Store

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='HZO · Ferroelectric Research',page_icon='◈',layout='wide')
st.markdown('''<style>
.block-container{max-width:1500px;padding-top:2.2rem}header[data-testid="stHeader"]{background:transparent}
h1{font-size:2.5rem!important;letter-spacing:-1.2px}h2{letter-spacing:-.6px}p{line-height:1.7}
[data-testid="stMetric"]{background:#121d2b;border:1px solid #243348;padding:20px;border-radius:12px}
[data-testid="stMetricLabel"]{color:#91a4bb}[data-testid="stMetricValue"]{color:#78e7c7}
.eyebrow{color:#6ee7c2;font:12px monospace;letter-spacing:3px}.lead{color:#93a4b9;max-width:780px}
.result{border:1px solid #29423e;border-radius:14px;padding:32px;background:linear-gradient(130deg,#142d2b,#111b29)}
.result .value{font-size:56px;color:#7debc9;font-weight:600}.muted{color:#93a4b9;font-size:14px}
.stTabs [data-baseweb="tab-list"]{gap:28px}footer{visibility:hidden}
</style>''',unsafe_allow_html=True)
base,counts,papers=load_sources(ROOT/'data/raw')
store=Store(ROOT/'artifacts/workspace.sqlite')
extra=store.records()
raw=pd.concat([base,extra],ignore_index=True).drop_duplicates('record_id')
df=apply_reviews(raw,store.reviews()); good=eligible(df)
model=latest(df,ROOT/'artifacts/models')
st.markdown('<div class="eyebrow">MATERIALS INTELLIGENCE / RESEARCH WORKSPACE</div>',unsafe_allow_html=True)
st.title('HZO Ferroelectric AI Predictor')
st.markdown('<p class="lead">MFM Structure · 2Pr Estimation<br>논문에서 공정으로, 검증된 데이터에서 예측으로. Hf₀.₅Zr₀.₅O₂ 강유전체 연구 워크스페이스.</p>',unsafe_allow_html=True)
a,b,c,d=st.columns(4)
a.metric('2Pr 후보 관측치',int((df.metric.eq('2Pr')&df.two_pr.notna()).sum()))
b.metric('출처 워크북',int(df.source_file.nunique()))
c.metric('학습 가능 · 승인 완료',len(good))
d.metric('모델 상태','활성' if model else '검증 대기')
st.caption(f'확인 시트 중복 {counts["duplicate_subset_rows"]}행은 추가하지 않았습니다. 두 파일의 논문ID는 서로 다른 이름공간이며, 논문 수로 합산하지 않습니다.')
if not model: st.info(f'원문·Methods 검토 전에는 예측하지 않습니다. 최소 {MIN_ROWS}개 승인 관측치 / {MIN_DOIS}개 DOI 및 DOI 분리 교차검증을 통과해야 활성화됩니다. 이 기준은 신뢰성을 보장하는 기준이 아닌 초기 운영 제한입니다.')
tabs=st.tabs(['◈  공정 시뮬레이터','▤  실험 데이터','◎  품질 리포트','↥  업로드 · 검토','⎇  모델 버전'])
with tabs[0]:
    left,right=st.columns([1.15,1],gap='large')
    with left:
        st.subheader('공정 조건')
        st.caption('Phase 1 · 단층 다결정 MFM · RTA · Hf:Zr = 0.5:0.5 고정')
        inputs={}
        with st.form('predict'):
            x,y=st.columns(2)
            with x:
                inputs['hzo_nm']=st.number_input('HZO 두께 (nm)',min_value=0.1,max_value=1000.,value=10.,step=0.1)
                inputs['top']=st.selectbox('Top electrode',['TiN','W','Mo','Ru','Pt','Au','NbN'])
                inputs['top_nm']=st.number_input('Top 두께 (nm)',min_value=0.1,max_value=2000.,value=50.,step=0.1)
                inputs['anneal_c']=st.number_input('RTA 온도 (°C)',min_value=20.,max_value=1200.,value=500.,step=1.)
                inputs['voltage_v']=st.number_input('측정 |전압| (V)',min_value=0.01,max_value=30.,value=3.,step=0.1)
                inputs['measurement_method']=st.selectbox('측정 방법',['P-E','PUND'])
            with y:
                st.text_input('Hf:Zr 비율','0.5 : 0.5',disabled=True)
                inputs['bottom']=st.selectbox('Bottom electrode',['TiN','W','Mo','Ru','Pt','Au','NbN'])
                inputs['bottom_nm']=st.number_input('Bottom 두께 (nm)',min_value=0.1,max_value=2000.,value=50.,step=0.1)
                inputs['anneal_s']=st.number_input('RTA 시간 (s)',min_value=0.1,max_value=36000.,value=30.,step=0.1)
                inputs['atmosphere']=st.selectbox('RTA 분위기',['N2','Ar','O2','N2/H2','Vacuum'])
                inputs['wake_cycles']=st.number_input('Wake-up / pre-cycling (cycles)',min_value=0,value=0,step=100)
            inputs['measurement_state']=st.selectbox('측정 상태',['pristine','wake-up','cycled'])
            with st.expander('고급 조건 · 삽입층 / 증착 / 측정'):
                inputs['multilayer']=st.checkbox('삽입층 또는 다층 전극 있음 (예측 제외)')
                st.number_input('Top 삽입층 (nm)',min_value=0.,value=0.,step=0.1,disabled=not inputs['multilayer'])
                st.number_input('Bottom 삽입층 (nm)',min_value=0.,value=0.,step=0.1,disabled=not inputs['multilayer'])
                inputs['ald_c']=st.number_input('ALD 온도 (°C) · 미기재 시 비워두기',min_value=0.,value=None)
                inputs['deposition']=st.selectbox('증착 유형',['thermal_ALD','PEALD','CPALD','ALD','sputtering'])
                inputs['pulse_s']=st.number_input('측정 펄스폭 (s) · 미기재 시 비워두기',min_value=0.,value=None,format='%.9f')
                inputs['frequency_hz']=st.number_input('측정 주파수 (Hz) · 미기재 시 비워두기',min_value=0.,value=None)
            submitted=st.form_submit_button('2Pr 예측 실행 →',type='primary',disabled=model is None,width='stretch')
    with right:
        st.subheader('예측 결과')
        value,issues=predict(model,inputs,df) if submitted else (None,[])
        if value is None:
            st.markdown('<div class="result"><div class="eyebrow">AWAITING VALIDATED MODEL</div><div class="value">— <span style="font-size:20px">μC/cm²</span></div><div class="muted">원문 검증 이후에만 2Pr 결과를 제공합니다.<br>실험값 후보와 모델 예측값은 구분됩니다.</div></div>',unsafe_allow_html=True)
        else:
            st.metric('Random Forest · 2Pr (μC/cm²)',f'{value:.2f}')
            st.caption('DOI 분리 검증을 통과한 연구용 추정입니다. 인과관계나 공정 보증을 의미하지 않습니다.')
        for issue in issues: st.warning(issue)
        st.markdown('#### 신뢰성 체크')
        st.write(f'승인된 관측치 **{len(good)} / {MIN_ROWS}** · 독립 DOI **{good.doi.nunique()} / {MIN_DOIS}**')
        st.progress(min(1.,len(good)/MIN_ROWS))
        st.caption('불확실성: N/A — 소수 논문에 대한 보정된 예측구간이 없습니다. 임의의 95% 신뢰구간을 표시하지 않습니다.')
        st.markdown('#### MFM stack')
        st.code(f'{inputs["top"]}  /  Hf₀.₅Zr₀.₅O₂  /  {inputs["bottom"]}\nTop metal        Ferroelectric        Bottom metal',language=None)
        st.caption('입력 기본값은 입력 예시이며 학습 데이터의 결측치를 채우지 않습니다.')

def table(data):
    cols=['sample_id','two_pr','hzo_nm','top','bottom','anneal_c','anneal_type','measurement_state','doi','source_url','verification','source_file','source_row','notes']
    st.dataframe(data[cols],hide_index=True,width='stretch',column_config={'source_url':st.column_config.LinkColumn('원문 링크'),'two_pr':st.column_config.NumberColumn('실험 2Pr (μC/cm²)',format='%.2f')})
with tabs[1]:
    st.subheader('문헌 실험값 탐색')
    st.caption('미승인 후보를 포함합니다. 그래프의 점은 보고된 실험값 후보이며 모델 예측이 아닙니다. 선으로 연결하지 않습니다.')
    a,b,c=st.columns([2,1,1])
    query=a.text_input('검색 · 논문 / DOI / 전극 / 샘플',placeholder='TiN, 10.3390, P09…')
    source=b.selectbox('출처',['전체']+sorted(df.source_file.dropna().unique().tolist()))
    anneal=c.selectbox('열처리',['전체','RTA','미확인']+sorted(set(df.anneal_type.dropna())-{'RTA'}))
    view=df.copy()
    if query: view=view[view.fillna('').astype(str).apply(lambda r:r.str.contains(query,case=False,regex=False).any(),axis=1)]
    if source!='전체': view=view[view.source_file.eq(source)]
    if anneal!='전체': view=view[view.anneal_type.isna() if anneal=='미확인' else view.anneal_type.eq(anneal)]
    xaxis=st.radio('비교 축',['hzo_nm','anneal_c'],format_func=lambda s:{'hzo_nm':'HZO 두께 (nm)','anneal_c':'열처리 온도 (°C)'}[s],horizontal=True)
    plot=view[view.metric.eq('2Pr')&view.two_pr.notna()&view[xaxis].notna()].copy()
    plot['treatment']=plot.anneal_type.fillna('미확인')
    if len(plot):
        fig=px.scatter(plot,x=xaxis,y='two_pr',color='treatment',symbol='source_file',hover_data=['sample_id','doi','top','bottom','verification'],labels={xaxis:'HZO 두께 (nm)' if xaxis=='hzo_nm' else '열처리 온도 (°C)','two_pr':'보고된 2Pr (μC/cm²)','treatment':'열처리'},color_discrete_sequence=['#74e6c4','#7eaeff','#e7ba70','#d89ce5','#ef8c8c'])
        fig.update_layout(template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='#101a28',height=410,legend=dict(orientation='h',y=-.25))
        st.plotly_chart(fig,width='stretch')
    else: st.info('선택한 조건에 숫자값과 비교 축이 모두 있는 기록이 없습니다.')
    st.caption(f'검색 결과 {len(view)}행 · 그래프 표시 {len(plot)}행 (결측 축 / 비2Pr 제외)')
    table(view)
    st.download_button('정규화 데이터 CSV 다운로드',df.to_csv(index=False).encode('utf-8-sig'),'hzo_normalized.csv','text/csv')
    with st.expander('논문 후보 목록 · 두 파일의 ID는 별개입니다'):
        st.dataframe(pd.DataFrame(papers),hide_index=True)
with tabs[2]:
    st.subheader('데이터 품질 · 학습 제외 사유')
    st.caption('결측은 원본에 그대로 보존합니다. 학습 파이프라인의 보간은 별도이며 측정 사실로 표시하지 않습니다.')
    quality=df[['record_id','sample_id','source_file','metric']].copy()
    quality['제외 사유']=df.apply(lambda r:'; '.join(reasons(r)) or '적격',axis=1)
    quality['중복 후보']=duplicate_candidates(df)
    st.dataframe(quality,hide_index=True,width='stretch')
    missing=df[NUMERIC].isna().sum().rename('결측 행 수').rename_axis('필드').reset_index()
    st.bar_chart(missing.set_index('필드'),color='#74e6c4')
    st.download_button('품질 리포트 다운로드',quality.to_csv(index=False).encode('utf-8-sig'),'quality_report.csv','text/csv')
    st.warning('데이터2의 열 이름 RTA는 각 행의 열처리 검증을 보장하지 않습니다. 열처리 방식은 원문 승인 전 미확인으로 유지합니다. 가능한 파일 간 중복은 학습에서 보수적으로 제외합니다.')
with tabs[3]:
    st.subheader('새 데이터 → 검토 → 승인 → 재학습')
    st.caption('개인 연구용 로컬 워크스페이스입니다. 인증 없는 공개 배포에서는 검토·업로드·학습 기능을 활성화하지 마세요.')
    import os
    editing=os.environ.get('HZO_READ_ONLY','1')=='0'
    if not editing: st.info('읽기 전용 모드입니다. 개인 환경에서 HZO_READ_ONLY=0 으로 실행하면 검토·학습을 사용할 수 있습니다.')
    upload=st.file_uploader('HZO Excel 또는 정규화 CSV (최대 20 MB)',type=['xlsx','csv'],disabled=not editing)
    if upload:
        try:
            incoming,stat,_=ingest(io.BytesIO(upload.getvalue()),upload.name)
            st.caption(f'{len(incoming)}행 파싱 · 확인 시트 중복 {stat["duplicate_subset_rows"]}행 제외. 업로드만으로 승인되지 않습니다.')
            table(incoming)
            if st.button('미승인 후보로 데이터셋에 추가',disabled=not editing):
                n=store.add(incoming); st.success(f'{n}행 추가됨. 원문 검토가 필요합니다.'); st.rerun()
        except Exception as exc: st.error('업로드 해석 실패: '+str(exc))
    selected=st.selectbox('검토할 관측치',df.record_id.tolist(),format_func=lambda rid:f'{df.loc[df.record_id.eq(rid),"sample_id"].iloc[0]} · {df.loc[df.record_id.eq(rid),"source_file"].iloc[0]} · {rid[:6]}')
    row=df[df.record_id.eq(selected)].iloc[0]
    st.json(json.loads(raw.loc[raw.record_id.eq(selected),'raw_json'].iloc[0]),expanded=False)
    st.caption('원본은 위에 보존됩니다. 아래 값은 원문을 확인한 뒤 기록하는 검토 오버레이입니다. 숫자 수정을 통한 레이블 변경은 지원하지 않습니다.')
    with st.form('review'):
        numcols=list(dict.fromkeys(NUM+['top_interlayer_nm','bottom_interlayer_nm']))
        corrections={}
        grid=st.columns(3)
        for i,col in enumerate(numcols):
            v=row.get(col)
            with grid[i%3]: corrections[col]=st.number_input(col,value=float(v) if pd.notna(v) else None,key='review_'+col)
        for i,col in enumerate(CAT+['anneal_type','structure','composition','doi','source_locator']):
            v=row.get(col)
            with grid[i%3]: corrections[col]=st.text_input(col,value=str(v) if pd.notna(v) else '',key='review_'+col)
        reviewer=st.text_input('검토자 이름')
        evidence=st.text_area('확인한 원문 위치 · Figure / Table / Methods · 측정 정의와 조건의 근거')
        scope=st.checkbox('원문에서 단층·다결정 HZO, 삽입층 없는 단일 금속 전극 MFM, Hf:Zr 1:1, RTA 및 측정 정의를 확인했습니다.')
        status=st.selectbox('검토 판정',['pending','rejected','approved'],format_func=lambda v:{'pending':'검토 중','rejected':'학습 제외','approved':'원문 검증 승인'}[v])
        if st.form_submit_button('검토 기록 저장',disabled=not editing):
            corrections={k:(v.strip() or None if isinstance(v,str) else v) for k,v in corrections.items()}
            candidate=row.to_dict(); candidate.update(corrections,review_status=status,scope_verified=scope,reviewer=reviewer,evidence=evidence)
            problems=reasons(candidate)
            if status=='approved' and problems: st.error('승인 불가: '+'; '.join(problems))
            else:
                try:
                    store.review(selected,dict(corrections=corrections,review_status=status,scope_verified=scope,reviewer=reviewer,evidence=evidence))
                    st.success('저장되었습니다. 모델은 데이터 버전이 바뀌면 재학습 전 비활성화됩니다.'); st.rerun()
                except ValueError as exc: st.error(str(exc))
with tabs[4]:
    st.subheader('재현 가능한 Python ML')
    st.write('ColumnTransformer → SimpleImputer → OneHotEncoder → RandomForestRegressor')
    st.caption('random_state=42 · 300 trees · DOI 기준 GroupKFold 5분할 · DummyRegressor(mean) 비교. 결측 선택 변수는 학습 fold 안에서만 처리합니다.')
    st.write(f'학습 허용: 승인 {MIN_ROWS}행 이상, DOI {MIN_DOIS}개 이상, 단층 다결정 RTA MFM, 검토 근거 및 필수 측정 조건 완비. 중복 의심 기록 제외.')
    if st.button('승인 데이터로 재학습',disabled=not (editing and readiness(df)),type='primary'):
        with st.spinner('DOI 분리 교차검증 및 모델 저장 중…'):
            result=train(df,ROOT/'artifacts/models')
            if result['report']['active']: st.success('기준 모델보다 MAE가 낮습니다. 모델 버전을 저장했습니다.')
            else: st.warning('기준 모델보다 MAE가 낮지 않아 예측 활성화를 보류했습니다. 버전과 결과는 보존했습니다.')
            st.json(result['report'])
    reports=[]
    for p in sorted((ROOT/'artifacts/models').glob('*/report.json'),reverse=True):
        r=json.loads(p.read_text()); reports.append(dict(version=r['version'],dataset=r['dataset_hash'][:12],rows=r['rows'],dois=r['dois'],RF_MAE=r['forest']['MAE'],RF_RMSE=r['forest']['RMSE'],RF_R2=r['forest']['R2'],Dummy_MAE=r['baseline']['MAE'],Dummy_RMSE=r['baseline']['RMSE'],Dummy_R2=r['baseline']['R2'],passed=r['active']))
    if reports: st.dataframe(pd.DataFrame(reports),hide_index=True)
    else: st.info('학습된 모델 없음 · MAE / RMSE / R²: N/A. 승인되지 않은 후보로 모델을 만들지 않았습니다.')
    st.caption('모델·데이터·리뷰 감사 기록은 artifacts/에 저장됩니다. 서버 재시작 시 보존되지만 임시 호스팅 디스크에서는 유실될 수 있습니다. 별도 영구 볼륨과 백업을 사용하세요. PDF 자동 추출과 Endurance/MFIS 예측은 Phase 1 범위 밖입니다.')
st.divider()
st.caption('HZO / MATERIALS INTELLIGENCE   ·   Phase 1 연구용   ·   수치 확인 ≠ 학습 승인   ·   No synthetic predictions')
