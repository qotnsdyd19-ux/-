from pathlib import Path
import argparse,json,requests
from urllib.parse import urlparse
parser=argparse.ArgumentParser();parser.add_argument('url');args=parser.parse_args()
u=args.url.rstrip('/');p=urlparse(u)
if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment:raise ValueError('루트 HTTPS 서버 주소만 허용')
r=requests.get(u+'/readyz',timeout=45);r.raise_for_status()
if r.json().get('mode')!='provided_data_experimental':raise ValueError('실험용 학습 서버 아님')
root=Path(__file__).resolve().parents[1];config=json.loads((root/'docs/inference-config.json').read_text())
models=requests.get(u+'/v1/models',timeout=45);models.raise_for_status()
if not any(m['version']==config['model_version'] and m['source_review_verified'] is False for m in models.json()['models']):raise ValueError('사이트와 서버 모델 버전 불일치')
config.update(mode='experimental_api',api_base_url=u)
(root/'docs/inference-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
print('실제 실험용 서버 준비 상태와 버전을 확인하고 연결 설정 저장. Pages 재배포 필요.')
