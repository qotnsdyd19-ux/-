"""TEMPORARY SYNTHETIC TEST MODEL. Never publish as a research model."""
import json
from src.model import train
from src.serving import sha256,source_release_digest
from tests.test_model import fixture

def exported_fixture(folder):
    data=fixture();bundle=train(data,folder)
    source=folder/'source_fixture'
    (source/'data/raw').mkdir(parents=True)
    (source/'data/reviews').mkdir(parents=True)
    (source/'data/raw/synthetic.csv').write_text('SYNTHETIC TEST SOURCE ONLY')
    (source/'data/reviews/decisions.json').write_text('{"synthetic_test_only":true}')
    report=bundle['report'];root=folder/report['version']
    audit={'source_review_verified':True,'dataset_hash':report['dataset_hash'],'source_release_sha256':source_release_digest(source),'fixture_only':True,'note':'Synthetic unit test; never publish'}
    (root/'review_manifest.json').write_text(json.dumps(audit))
    files=['model.joblib','report.json','dataset.csv','review_manifest.json']
    entry={'version':report['version'],'sha256':{name:sha256(root/name) for name in files}}
    (folder/'index.json').write_text(json.dumps({'schema_version':1,'models':[entry]}))
    return data,bundle
