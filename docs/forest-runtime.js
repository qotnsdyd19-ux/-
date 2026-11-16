// Evaluate exported sklearn preprocessing and real RandomForest decision trees.
export function validateInputs(model,input) {
  for (const key of model.report.required_fields) if(input[key]===null || input[key]===undefined || input[key]==='') throw new Error('필수 입력: '+key);
  for (const [key,[lo,hi]] of Object.entries(model.limits)) {
    const value=input[key];
    if ((value===null || value===undefined) && model.missing_allowed.includes(key)) continue;
    if(typeof value!=='number' || !Number.isFinite(value) || value<lo || value>hi) throw new Error(`${key}: 학습 범위 ${lo}–${hi} 밖 / 미기재`);
  }
  for (const [key,values] of Object.entries(model.categories)) {
    const value=input[key];
    if ((value===null || value===undefined) && model.missing_allowed.includes(key)) continue;
    if(!values.includes(value)) throw new Error(key+': 제공 자료에 없는 범주');
  }
  if(!model.pairs.some(([a,b])=>a===input.top && b===input.bottom)) throw new Error('제공 자료에 없는 전극 조합');
}
export function predictForest(model,input) {
  validateInputs(model,input);
  const p=model.preprocessing, features=[];
  for(let i=0;i<p.numeric.length;i++) features.push(input[p.numeric[i]]==null?p.numeric_fill[i]:input[p.numeric[i]]);
  for(const index of p.numeric_indicators) features.push(input[p.numeric[index]]==null?1:0);
  for(let i=0;i<p.categorical.length;i++) {
    const value=input[p.categorical[i]]==null?p.categorical_fill[i]:input[p.categorical[i]];
    for(const category of p.onehot_categories[i]) features.push(value===category?1:0);
  }
  // sklearn's tree prediction casts transformed inputs to float32.
  const values=features.map(Math.fround);let total=0;
  for(const tree of model.trees) {
    let node=0;
    while(tree.left[node]!==-1) node=values[tree.feature[node]]<=tree.threshold[node]?tree.left[node]:tree.right[node];
    total+=tree.value[node];
  }
  return total/model.trees.length;
}
