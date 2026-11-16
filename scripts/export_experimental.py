"""Refresh portable weights/config from the already trained real model, without refitting."""
from pathlib import Path
import json,hashlib,sys,re
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.experimental import load,portable,NUMERIC,CATEGORICAL,predict
import pandas as pd
root=Path(__file__).resolve().parents[1];b=load(root);r=b['report'];folder=root/'models-experimental'/r['version']
encoded=json.dumps(portable(b),ensure_ascii=False,separators=(',',':'),allow_nan=False)
(root/'docs/experimental-model.json').write_text(encoded)
(root/'docs/experimental-report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False))
(root/'docs/experimental-training.csv').write_bytes((folder/'dataset.csv').read_bytes())
(root/'docs/experimental-exclusions.csv').write_bytes((folder/'excluded.csv').read_bytes())
config={'mode':'experimental_browser','api_base_url':None,'model_url':'experimental-model.json','model_version':r['version'],'model_sha256':hashlib.sha256(encoded.encode()).hexdigest()}
(root/'docs/inference-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
print('Exported real experimental model',r['version'])

html=root/'docs/index.html'
html.write_text(re.sub(r'src=\"inference\.js(?:\?[^\"]*)?\"', 'src=\"inference.js?v='+r['version']+'\"', html.read_text()))
