"""Verify a running real supplied-data model service, without fake predictions."""
import argparse,json,sys,os
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.experimental import load,predict
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--retrain',action='store_true');args=p.parse_args()
if args.retrain:
 token=os.environ.get('HZO_TRAIN_TOKEN');assert token
 trained=requests.post(args.url+'/v1/train',headers={'Authorization':'Bearer '+token},timeout=60);trained.raise_for_status();assert trained.json()['report']['source_review_verified'] is False
 print('Actual authenticated training HTTP 200')
root=Path(__file__).resolve().parents[1];b=load(root);cases=json.loads((root/'docs/experimental-cases.json').read_text());values=[]
for c in cases:
 body={'structure':'MFM','target':'2Pr','measurement_method':'unconfirmed','expected_model_version':b['report']['version'],'acknowledge_unvalidated':True,'inputs':c['inputs']}
 res=requests.post(args.url+'/v1/predict',json=body,timeout=30);res.raise_for_status();r=res.json()
 assert abs(r['value']-predict(b,c['inputs'],True)['value'])<1e-9
 assert r['source_review_verified'] is False and r['validation_passed']==b['report']['validation_passed']
 values.append(r['value'])
assert values[0]!=values[1]
assert requests.post(args.url+'/v1/train',timeout=10).status_code==403
print(json.dumps({'mode':'actual_supplied_data_experiment','actual_http_values':values,'source_review_verified':False,'validation_passed':b['report']['validation_passed']}))
