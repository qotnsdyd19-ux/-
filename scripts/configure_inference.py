"""Set an actual deployed API URL only after checking its model readiness."""
import argparse,json
from pathlib import Path
from urllib.parse import urlparse
import requests

def main():
    parser=argparse.ArgumentParser();parser.add_argument('url');args=parser.parse_args()
    url=args.url.rstrip('/');parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:raise ValueError('루트 HTTPS URL만 사용할 수 있습니다.')
    response=requests.get(url+'/readyz',timeout=45);response.raise_for_status()
    if response.json().get('ready') is not True:raise ValueError('추론 서버가 준비되지 않았습니다.')
    models=requests.get(url+'/v1/models',timeout=45);models.raise_for_status()
    if not models.json().get('models'):raise ValueError('검증된 활성 모델 없음')
    path=Path(__file__).resolve().parents[1]/'docs/inference-config.json'
    path.write_text(json.dumps({'api_base_url':url},ensure_ascii=False,indent=2)+'\n')
    print('검증한 실제 서버 주소를 저장했습니다. 사이트 재배포가 필요합니다.')

if __name__=='__main__':main()
