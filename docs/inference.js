// The public page requests actual inference; it contains no prediction table.
const byId = id => document.getElementById(id);
let experimentalMode=false;
let apiBase = null, models = [], selected = null, prediction = null, generation = 0, pending = null;
const finite = value => typeof value === 'number' && Number.isFinite(value);
const number = id => byId(id).value === '' ? null : Number(byId(id).value);
const columns = {top:'topInput',bottom:'bottomInput',atmosphere:'atmosphereInput',measurement_state:'measurementStateInput',deposition:'depositionInput'};

function clearResult(message) {
  generation++;
  if (pending) pending.abort();
  pending = null; prediction = null;
  byId('resultNumber').textContent = '—';
  byId('downloadPrediction').disabled = true;
  if (message) byId('predictionStatus').textContent = message;
}

function updateModel() {
  if(experimentalMode)return;
  clearResult();
  const structure = byId('deviceStructure').value, target = byId('predictionTarget').value, method = byId('methodInput').value;
  selected = models.find(m => m.structure === structure && m.target === target && m.measurement_method === method && m.active === true) || null;
  byId('predictButton').disabled = !selected;
  byId('predictButton').textContent = selected ? target + ' 실제 모델 예측 실행' : target + ' 예측 · 검증 모델 없음';
  byId('resultTarget').textContent = target;
  byId('resultUnit').textContent = selected?.unit || (target === '2Pr' ? 'μC/cm²' : target === 'Endurance' ? 'cycles' : 'V');
  byId('resultVersion').textContent = selected ? selected.version : '모델 없음';
  byId('resultHeading').textContent = structure + ' / ' + target;
  byId('resultFooter').textContent = selected ? 'VERIFIED RESEARCH MODEL / '+selected.version : 'AWAITING VALIDATED MODEL';
  byId('resultExplanation').textContent = selected ? '모델 계산값은 실험 측정값이 아닙니다. 입력 조건을 바꾸면 다시 실행해야 합니다.' : '검증된 학습 모델이 없어 예측값을 표시하지 않습니다.';
  byId('approvedModelRows').textContent = selected ? selected.rows+'행 / '+selected.dois+' DOI' : '선택한 모델 없음';
  byId('validationStatus').textContent = selected ? 'DOI 그룹 교차검증 통과' : '미검증';
  byId('selectedMetrics').textContent = selected ? [selected.forest.MAE,selected.forest.RMSE,selected.forest.R2].map(v=>finite(v)?v.toFixed(3):'N/A').join(' / ') : 'N/A';
  byId('modelDetails').textContent = selected ? JSON.stringify({version:selected.version,dataset_hash:selected.dataset_hash,approved_rows:selected.rows,independent_dois:selected.dois,measurement_method:selected.measurement_method,validation:selected.forest,baseline:selected.baseline,limits:selected.limits,categories:selected.categories,used_features:selected.used_features,unused_features:selected.unused_features,missing_allowed:selected.missing_allowed,missing_policy:selected.missing_policy,limitations:selected.limitations},null,2) : '이 구조·출력·측정 방법의 검증 모델 없음';
  byId('predictionStatus').textContent = selected ? '검증 결과와 입력 범위를 확인한 뒤 실행하세요. 입력 예시는 검증된 조건이나 예측 결과가 아닙니다.' : '이 구조·출력·측정 방법은 원문 승인·모델 검증 전이므로 예측을 제공하지 않습니다.';
  if (selected) {
    for (const [key,id] of Object.entries(columns)) {
      const input=byId(id), prior=input.value;
      input.replaceChildren(new Option('선택 필요',''));
      for (const v of selected.categories[key] || []) input.add(new Option(v,v));
      input.value=(selected.categories[key] || []).includes(prior) ? prior : '';
      input.required=!(selected.missing_allowed || []).includes(key) && !(selected.unused_features || []).includes(key);
      input.disabled=(selected.unused_features || []).includes(key);
    }
    const numeric={hzo_nm:'hzoInput',top_nm:'topThicknessInput',bottom_nm:'bottomThicknessInput',anneal_c:'temperatureInput',anneal_s:'timeInput',voltage_v:'voltageInput',wake_cycles:'wakeInput',ald_c:'aldInput',pulse_s:'pulseInput',frequency_hz:'frequencyInput'};
    for (const [key,id] of Object.entries(numeric)) {
      const input=byId(id), unused=(selected.unused_features || []).includes(key);
      input.disabled=unused;
      input.required=!unused && !(selected.missing_allowed || []).includes(key);
      if (unused) input.value='';
    }
  }
}

function updateStructure() {
  if(experimentalMode)return;
  const prior=byId('predictionTarget').value, mfis=byId('deviceStructure').value==='MFIS';
  const choices=mfis ? ['Memory Window','Threshold shift','Endurance'] : ['2Pr','Endurance'];
  byId('predictionTarget').replaceChildren(...choices.map(t=>new Option(t,t)));
  if (choices.includes(prior)) byId('predictionTarget').value=prior;
  updateModel();
}

async function connect() {
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),45000);
  try {
    const configResponse=await fetch('inference-config.json',{cache:'no-store',signal:controller.signal});
    if (!configResponse.ok) throw new Error('서버 연결 설정을 읽지 못했습니다.');
    const config=await configResponse.json();
    if(config.mode==='experimental_browser'||config.mode==='experimental_api'){experimentalMode=true;const {startExperimental}=await import('./experimental.js');await startExperimental(config);return;}
    if (!config.api_base_url) {
      byId('engineStatus').textContent='추론 서버 미배포 · 원문 검증 및 호스팅 계정 연결 대기';
      updateModel();return;
    }
    const url=new URL(config.api_base_url);
    if (url.protocol!=='https:' || url.username || url.password || url.search || url.hash || url.pathname!=='/') throw new Error('유효한 HTTPS 추론 서버 주소가 필요합니다.');
    apiBase=url.origin;
    byId('engineStatus').textContent='추론 서버 연결 중… 무료 서버는 시작에 시간이 걸릴 수 있습니다.';
    const response=await fetch(apiBase+'/v1/models',{cache:'no-store',credentials:'omit',signal:controller.signal});
    if (!response.ok) throw new Error('서버 응답 HTTP '+response.status);
    const payload=await response.json();
    if (!Array.isArray(payload.models)) throw new Error('서버 모델 정보 형식이 올바르지 않습니다.');
    models=payload.models.filter(m=>m.active===true && typeof m.version==='string' && typeof m.dataset_hash==='string' && m.categories && m.limits && m.forest && m.rows>=20 && m.dois>=5);
    byId('activeModelCount').textContent=models.length || '없음';
    byId('engineStatus').textContent='서버 연결됨 · 검증된 활성 모델 '+models.length+'개';
    updateModel();
  } catch(error) {
    models=[];selected=null;apiBase=null;updateModel();
    byId('engineStatus').textContent='추론 서버 연결 실패: '+error.message+' · 예측 차단';
  } finally {clearTimeout(timer);}
}

function inputs() {
  return {hzo_nm:number('hzoInput'),top_nm:number('topThicknessInput'),bottom_nm:number('bottomThicknessInput'),anneal_c:number('temperatureInput'),anneal_s:number('timeInput'),voltage_v:number('voltageInput'),wake_cycles:number('wakeInput'),
    top:byId('topInput').value,bottom:byId('bottomInput').value,atmosphere:byId('atmosphereInput').value||null,measurement_method:byId('methodInput').value,measurement_state:byId('measurementStateInput').value,deposition:byId('depositionInput').value||null,
    ald_c:number('aldInput'),pulse_s:number('pulseInput'),frequency_hz:number('frequencyInput'),top_interlayer_nm:number('topInterlayerInput')??0,bottom_interlayer_nm:number('bottomInterlayerInput')??0,multilayer:(number('topInterlayerInput')??0)>0 || (number('bottomInterlayerInput')??0)>0};
}

async function runPrediction() {
  if(experimentalMode)return;
  clearResult();
  if (!selected || !apiBase) return;
  if (!byId('processForm').reportValidity()) return;
  const model=selected, body={structure:byId('deviceStructure').value,target:byId('predictionTarget').value,expected_model_version:model.version,inputs:inputs()};
  const current=generation, controller=new AbortController();pending=controller;
  const timer=setTimeout(()=>controller.abort(),45000);
  byId('predictButton').disabled=true;
  byId('predictionStatus').textContent='선택한 입력을 Python 모델에서 계산 중…';
  try {
    const response=await fetch(apiBase+'/v1/predict',{method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
    const result=await response.json();
    if (current!==generation) return;
    if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail.map(v=>typeof v==='string'?v:JSON.stringify(v)).join('; ') : result.detail || 'HTTP '+response.status);
    if (!finite(result.value) || result.kind!=='model_prediction' || result.model_version!==model.version || result.dataset_hash!==model.dataset_hash || result.structure!==body.structure || result.target!==body.target || result.unit!==model.unit) throw new Error('예측 결과와 모델 정보가 일치하지 않습니다.');
    prediction=result;
    byId('resultNumber').textContent=result.value.toFixed(2);
    byId('predictionStatus').textContent='실제 Python 모델 계산값 · '+result.limitations;
    byId('downloadPrediction').disabled=false;
  } catch(error) {
    if (current===generation) {
      byId('resultNumber').textContent='—';prediction=null;
      byId('predictionStatus').textContent='예측을 제공할 수 없습니다: '+error.message;
    }
  } finally {
    clearTimeout(timer);
    if (current===generation) {pending=null;byId('predictButton').disabled=!selected;}
  }
}

byId('predictButton').addEventListener('click',runPrediction);
for (const event of ['input','change']) byId('processForm').addEventListener(event,()=>{
  if(experimentalMode)return;
  clearResult('입력이 변경되었습니다. 다시 예측을 실행하세요.');
  byId('predictButton').disabled=!selected;
});
byId('deviceStructure').addEventListener('change',updateStructure);
byId('predictionTarget').addEventListener('change',updateModel);
byId('methodInput').addEventListener('change',updateModel);
byId('downloadPrediction').addEventListener('click',()=>{
  if(experimentalMode)return;
  if (!prediction) return;
  const result={kind:prediction.kind,structure:prediction.structure,target:prediction.target,value:prediction.value,unit:prediction.unit,model_version:prediction.model_version,dataset_hash:prediction.dataset_hash,...prediction.inputs};
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  const csv=[Object.keys(result),Object.values(result)].map(r=>r.map(quote).join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob(['\ufeff',csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='hzo_model_prediction.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
connect();
