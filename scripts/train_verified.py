"""Export only a source-reviewed, grouped-validation-passing MFM model."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data import load_sources
from src.model import eligible,train,fingerprint,MIN_ROWS,MIN_DOIS
from src.reviews import verified_dataset
from src.serving import sha256,source_release_digest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',default='data/reviews/decisions.json')
    parser.add_argument('--cache',default='artifacts/source_cache')
    parser.add_argument('--output',default='models')
    parser.add_argument('--method',choices=['P-E','PUND'],default='P-E')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    source,_,_=load_sources(root/'data/raw')
    reviewed,audit=verified_dataset(source,args.manifest,args.cache)
    good=eligible(reviewed);good=good[good.measurement_method.eq(args.method)]
    attempt={'status':'blocked_before_fit','approved_rows':len(good),'approved_dois':int(good.doi.nunique()),
             'measurement_method':args.method,'required_rows':MIN_ROWS,'required_dois':MIN_DOIS,
             'dataset_hash':fingerprint(reviewed),'decisions':audit,'cross_validation':'not_run'}
    out=root/'artifacts';out.mkdir(exist_ok=True)
    def save_attempt():
        content=json.dumps(attempt,ensure_ascii=False,indent=2)
        (out/'training_attempt.json').write_text(content)
        (out/('training_attempt_'+args.method+'.json')).write_text(content)
    if len(good)<MIN_ROWS or good.doi.nunique()<MIN_DOIS:
        attempt['reason']='원문 근거를 확인한 동일 측정 방법의 승인 관측치와 독립 DOI 부족'
        save_attempt()
        print(json.dumps(attempt,ensure_ascii=False,indent=2));return 2
    bundle=train(reviewed,args.output,method=args.method);report=bundle['report']
    attempt.update(status='passed' if report['active'] else 'failed_validation',cross_validation='completed',metrics=report['forest'],baseline=report['baseline'])
    save_attempt()
    if report['active']:
        folder=Path(args.output)/report['version']
        review={'source_review_verified':True,'dataset_hash':report['dataset_hash'],'decisions':audit,'source_release_sha256':source_release_digest(root),
                'manifest_sha256':sha256(args.manifest)}
        (folder/'review_manifest.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
        files=['model.joblib','report.json','dataset.csv','review_manifest.json']
        entry={'version':report['version'],'sha256':{name:sha256(folder/name) for name in files}}
        # Each method has its own registry key; preserve the other validated method.
        index=Path(args.output)/'index.json'
        existing=json.loads(index.read_text()).get('models',[]) if index.exists() else []
        retained=[]
        for item in existing:
            prior=json.loads((Path(args.output)/item['version']/'report.json').read_text())
            if prior['measurement_method']!=args.method:retained.append(item)
        index.write_text(json.dumps({'schema_version':1,'models':retained+[entry]},ensure_ascii=False,indent=2))
    print(json.dumps(attempt,ensure_ascii=False,indent=2))
    return 0 if report['active'] else 3

if __name__=='__main__':sys.exit(main())
