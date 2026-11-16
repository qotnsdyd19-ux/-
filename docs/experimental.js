import {predictForest} from './forest-runtime.js';
const $=id=>document.getElementById(id);
const fields={hzo_nm:'hzoInput',anneal_c:'temperatureInput',voltage_v:'voltageInput',anneal_s:'timeInput',top:'topInput',bottom:'bottomInput',anneal_type:'experimentalAnneal',measurement_state:'measurementStateInput'};
export async function startExperimental(config) {
  const response=await fetch(config.model_url,{cache:'no-store'});
  if(!response.ok)throw new Error('실험 모델 파일 HTTP '+response.status);
  const text=await response.text();
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))).map(v=>v.toString(16).padStart(2,'0')).join('');
  if(hash!==config.model_sha256)throw new Error('실험 모델 해시 불일치');
  const model=JSON.parse(text),r=model.report;
  if(r.source_review_verified!==false || r.version!==config.model_version || !r.available_for_experiments)throw new Error('실험 모델 표시 불일치');
  const intro=$('processForm').parentElement.querySelector('.caption');if(intro)intro.textContent='입력값은 제공 자료로 학습한 실험 모델의 계산 조건입니다. 조건 예시를 적용하거나 입력을 바꾼 뒤 실험 계산을 실행하세요.';
  const examples=await fetch('experimental-cases.json',{cache:'no-store'}).then(v=>v.json());
  let result=null,generation=0,pending=null;
  const serverMode=config.mode==='experimental_api';
  const apiBase=serverMode?new URL(config.api_base_url):null;
  if(apiBase&&(apiBase.protocol!=='https:'||apiBase.username||apiBase.password||apiBase.search||apiBase.hash))throw new Error('HTTPS 서버 주소 오류');
  const notice=document.createElement('div');notice.className='notice warning';notice.id='experimentalNotice';
  const title=document.createElement('strong');title.textContent='실험용 모델 · 원문 미검증 · '+(r.validation_passed?'제공 자료 교차검증 기준 통과':'논문별 교차검증 기준 미통과');
  const metrics=document.createElement('p');metrics.textContent=`실제 학습 ${r.rows}행 / ${r.dois} DOI · MAE ${r.forest.MAE.toFixed(2)}, RMSE ${r.forest.RMSE.toFixed(2)} μC/cm², R² ${r.forest.R2?.toFixed(3)??'N/A'} · 평균값 기준 MAE ${r.baseline.MAE.toFixed(2)}. 검증된 물성값이나 공정 보증이 아닙니다.`;
  const label=document.createElement('label');label.className='check';const ack=document.createElement('input');ack.type='checkbox';ack.id='experimentalAcknowledgement';
  label.append(ack,document.createTextNode('원문 미검증·성능 평가 결과를 확인했고, 실험용으로 계산합니다.'));
  const link=document.createElement('a');link.href='experimental-training.csv';link.download='hzo_experimental_training.csv';link.textContent='실제 학습에 사용한 제공 자료 '+r.rows+'행 다운로드';
  notice.append(title,metrics,label,link);$('predictButton').before(notice);
  const annealLabel=document.createElement('label');annealLabel.textContent='자료의 열처리 방식';const anneal=document.createElement('select');anneal.id='experimentalAnneal';annealLabel.append(anneal);$('processForm').querySelector('.fields').append(annealLabel);
  const method=$('methodInput');method.add(new Option('미확인 자료군 (실험용)','unconfirmed'));method.value='unconfirmed';
  for(const [key,values] of Object.entries(model.categories)) {
    const input=$(fields[key]);input.replaceChildren(new Option('미기재 / 미확인',''));
    for(const value of values)input.add(new Option(value,value));
    input.required=r.required_fields.includes(key) || !model.missing_allowed.includes(key);
  }
  for(const key of model.preprocessing.numeric) $(fields[key]).required=r.required_fields.includes(key) || !model.missing_allowed.includes(key);
  for(const id of ['topThicknessInput','bottomThicknessInput','wakeInput','aldInput','depositionInput','pulseInput','frequencyInput','atmosphereInput','topInterlayerInput','bottomInterlayerInput']) {$(id).required=false;$(id).disabled=true;if($(id).tagName==='INPUT')$(id).value='';}
  const buttons=document.createElement('div');buttons.className='button-row';buttons.id='experimentalExamples';
  examples.forEach((example,i)=>{const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent=`제공 자료 조건 ${i+1} 적용`;button.id='experimentalExample'+i;button.addEventListener('click',()=>apply(example));buttons.append(button);});
  $('processForm').after(buttons);
  function inputValues() {
    return Object.fromEntries(Object.entries(fields).map(([key,id])=>[key,$(id).value===''?null:model.preprocessing.numeric.includes(key)?Number($(id).value):$(id).value]));
  }
  function clear() {generation++;if(pending)pending.abort();pending=null;result=null;$('resultNumber').textContent='—';$('downloadPrediction').disabled=true;}
  function refresh() {
    clear();
    const supported=$('deviceStructure').value==='MFM' && $('predictionTarget').value==='2Pr' && method.value==='unconfirmed';
    $('predictButton').disabled=!supported || !ack.checked;
    $('predictButton').textContent=supported?'2Pr 실험 계산 실행':$('predictionTarget').value+' · 이 구조·측정 방법의 실험 모델 없음';
    $('resultTarget').textContent=supported?'2Pr (실험용)':$('predictionTarget').value;
    $('resultUnit').textContent=supported?'μC/cm²':'—';
    $('resultHeading').textContent='제공 자료 기반 실험 추정';$('resultVersion').textContent=r.version;
    $('predictionStatus').textContent=supported?'입력 조건을 바꿔 실제 학습 모델을 계산할 수 있습니다. 실행 전 위 실험용 확인란을 선택하세요.':'MFIS·P-E·PUND 모델은 이 미확인 자료군과 분리하며, 해당 모델은 아직 없습니다.';
    $('resultExplanation').textContent=r.limitations;
    $('resultFooter').textContent='실험용 / '+(r.validation_passed?'자료 교차검증 기준 통과':'DOI 교차검증 기준 미통과');
    $('approvedModelRows').textContent=`원문 승인 0행 / 실험 학습 ${r.rows}행`;
    $('validationStatus').textContent=r.validation_passed?'실험용 기준 통과 (원문 미검증)':'미통과 — 실험 계산만 허용';
  }
  function apply(example) {for(const [key,id] of Object.entries(fields)) $(id).value=example.inputs[key]??'';refresh();}
  $('predictButton').addEventListener('click',async()=>{
    clear();if(!ack.checked || $('deviceStructure').value!=='MFM' || $('predictionTarget').value!=='2Pr' || method.value!=='unconfirmed')return;
    const revision=generation;
    try {
      if(!$('processForm').reportValidity())return;
      const inputs=inputValues(),current=generation;let value;
      if(serverMode){
        const controller=new AbortController();pending=controller;const timer=setTimeout(()=>controller.abort(),45000);
        try{
          const res=await fetch(apiBase.origin+'/v1/predict',{method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},signal:controller.signal,
            body:JSON.stringify({structure:'MFM',target:'2Pr',measurement_method:'unconfirmed',expected_model_version:r.version,acknowledge_unvalidated:true,inputs})});
          const data=await res.json();if(current!==generation)return;
          if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
          if(data.kind!=='experimental_model_prediction'||data.model_version!==r.version||data.dataset_hash!==r.dataset_hash||data.source_review_verified!==false||!Number.isFinite(data.value))throw new Error('서버 응답과 모델 정보 불일치');
          value=data.value;
        }finally{clearTimeout(timer);if(current===generation)pending=null;}
      }else value=predictForest(model,inputs);
      result={kind:'experimental_model_prediction',value,unit:r.unit,model_version:r.version,dataset_hash:r.dataset_hash,source_review_verified:false,validation_passed:r.validation_passed,inputs};
      $('resultNumber').textContent=value.toFixed(2);$('downloadPrediction').disabled=false;
      $('predictionStatus').textContent=(serverMode?'실제 Python 서버 계산값':'실제 Python 학습 모델의 브라우저 계산값')+' · 실험용 · 원문 미검증 · '+(r.validation_passed?'자료 CV 기준 통과':'CV 기준 미통과');
      window.dispatchEvent(new CustomEvent('hzo-experimental-prediction',{detail:result}));
    }catch(error){if(revision===generation)$('predictionStatus').textContent='계산 차단: '+error.message;}
  });
  $('processForm').addEventListener('input',refresh);$('processForm').addEventListener('change',refresh);ack.addEventListener('change',refresh);
  $('deviceStructure').addEventListener('change',()=>{
    const options=$('deviceStructure').value==='MFM'?['2Pr','Endurance']:['Memory Window','Threshold shift','Endurance'];
    $('predictionTarget').replaceChildren(...options.map(t=>new Option(t,t)));refresh();
  });
  $('predictionTarget').addEventListener('change',refresh);
  $('downloadPrediction').addEventListener('click',()=>{
    if(!result)return;
    const flat={...result,inputs:JSON.stringify(result.inputs)},quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
    const csv=[Object.keys(flat),Object.values(flat)].map(row=>row.map(quote).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob(['\ufeff',csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='hzo_experimental_prediction.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  $('engineStatus').textContent=serverMode?'실험 모델 준비됨 · 실제 Python 추론 서버 연결 설정됨':`실험 모델 준비됨 · Python Random Forest ${model.trees.length}개 트리를 브라우저에서 계산 · 공개 Python 서버는 별도 배포 전`;
  $('activeModelCount').textContent='1 (실험용)';
  const trainingRow=document.querySelector('.readiness li');if(trainingRow){trainingRow.querySelector('span').textContent='실제 모델 학습';trainingRow.querySelector('b').textContent='Python · 제공 자료 '+r.rows+'행 학습 완료';}
  $('selectedMetrics').textContent=[r.forest.MAE,r.forest.RMSE,r.forest.R2].map(v=>v==null?'N/A':v.toFixed(3)).join(' / ');
  $('modelDetails').textContent=JSON.stringify({...r,limits:model.limits,categories:model.categories,missing_allowed:model.missing_allowed},null,2);
  const deploymentNotice=$('inferenceDeploymentNotice');if(deploymentNotice)deploymentNotice.textContent='현재 제공 자료로 Python에서 학습한 실험 모델을 이 브라우저에서 계산합니다. 공개 Python 서버는 별도 배포 전이며, 동일한 모델로 학습·추론하는 서버 코드와 Docker 이미지를 제공합니다.';
  const exampleNote=document.createElement('p');exampleNote.className='caption';exampleNote.textContent='조건 예시는 학습에 사용한 제공 자료에서 가져왔습니다. 이 조건의 계산 결과는 논문 분리 검증 성능을 뜻하지 않습니다.';buttons.after(exampleNote);
  if(deploymentNotice){const note=document.createTextNode(' 제공된 저장소 원본으로 학습한 모델입니다. 브라우저 임시 자료 추가는 모델을 재학습하지 않으며, 새 자료 학습은 Python 서버의 인증된 학습 경로에서 수행합니다.');deploymentNotice.parentElement.replaceChildren(deploymentNotice,document.createElement('br'),note);if(serverMode)deploymentNotice.textContent='현재 실제 Python 실험용 추론 서버에 연결해 계산합니다. 원문 독립 검증 모델은 아닙니다.';}
  apply(examples[0]);
}
