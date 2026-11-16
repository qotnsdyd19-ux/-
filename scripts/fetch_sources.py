"""Acquire primary HTML for local review; never treat a successful fetch as approval."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data import load_sources,normalize_doi

class Text(HTMLParser):
    def __init__(self):super().__init__();self.ignored=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript','svg'}:self.ignored+=1
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript','svg'} and self.ignored:self.ignored-=1
    def handle_data(self,text):
        if not self.ignored:self.parts.append(text)

def fetch(doi,url,cache):
    item={'doi':doi,'url':url,'checked_at':datetime.now(timezone.utc).isoformat(),'review_status':'pending'}
    try:
        r=requests.get(url,timeout=30,headers={'User-Agent':'HZO-Research-Source-Review/2.1'},stream=True)
        item['http_status']=r.status_code
        if r.status_code!=200:item['access']='http_error';return item
        body=bytearray()
        for chunk in r.iter_content(65536):
            body.extend(chunk)
            if len(body)>15_000_000:raise ValueError('원문 크기 제한 초과')
        if 'text/html' not in r.headers.get('Content-Type',''):item['access']='unsupported_content_type';return item
        parser=Text();parser.feed(bytes(body).decode(r.encoding or 'utf-8',errors='replace'))
        text='\n'.join(part.strip() for part in parser.parts if part.strip())
        # Landing pages and anti-bot pages are not primary evidence.
        if len(text)<3000 or doi.lower() not in text.lower():item['access']='needs_full_text_or_doi_confirmation';return item
        data=text.encode();digest=hashlib.sha256(data).hexdigest()
        cache.mkdir(parents=True,exist_ok=True);(cache/(digest+'.txt')).write_bytes(data)
        item.update(access='downloaded_not_reviewed',sha256=digest,bytes=len(data))
    except requests.exceptions.ProxyError as exc:
        item['access']='network_policy_blocked' if '403' in str(exc) else 'proxy_connection_failed'
    except requests.RequestException as exc:item.update(access='request_failed',error_type=type(exc).__name__)
    except ValueError as exc:item.update(access='invalid_document',reason=str(exc))
    return item

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='artifacts/source_access.json');parser.add_argument('--cache',default='artifacts/source_cache');parser.add_argument('--public-summary',default='docs/source_access_status.json');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];df,_,_=load_sources(root/'data/raw')
    items=[]
    for doi,part in df[df.doi.notna()].groupby('doi'):
        urls=part.source_url.dropna().tolist();url=next((u for u in urls if str(u).startswith('https://')),'https://doi.org/'+doi)
        items.append((normalize_doi(doi),url))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda pair:fetch(*pair,Path(args.cache)),items))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps({'sources':results,'note':'접속 성공은 원문 검증·학습 승인이 아닙니다.'},ensure_ascii=False,indent=2))
    from collections import Counter
    summary={'doi_sources':len(results),'last_attempt_at':max((r['checked_at'] for r in results),default=None),
             'access':dict(Counter(r['access'] for r in results)),
             'note':'접속 성공은 원문 검증·학습 승인이 아닙니다. 마지막 접속 시도의 관측 결과입니다.'}
    Path(args.public_summary).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'sources':len(results),'access':dict(Counter(r['access'] for r in results))},ensure_ascii=False))
    return 0 if any(r['access']=='downloaded_not_reviewed' for r in results) else 2

if __name__=='__main__':sys.exit(main())
