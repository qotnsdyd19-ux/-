"""Read-only serving of explicitly exported, integrity-checked local bundles."""
import hashlib
import json
from pathlib import Path
import joblib

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_release_digest(root):
    root=Path(root)
    files=sorted(p for p in (root/'data/raw').glob('*') if p.suffix.lower() in {'.xlsx','.csv'})
    manifest=root/'data/reviews/decisions.json'
    if not files or not manifest.is_file():raise ValueError('배포 원본·검토 판정 파일 없음')
    digest=hashlib.sha256()
    for file in files+[manifest]:
        digest.update(str(file.relative_to(root)).encode());digest.update(bytes.fromhex(sha256(file)))
    return digest.hexdigest()

class Registry:
    def __init__(self,folder,source_root=None,allow_test_fixtures=False):
        self.folder=Path(folder);self.bundles={};self.problems=[]
        index=self.folder/'index.json'
        if not index.is_file():
            self.problems.append('원문 승인·검증을 통과해 내보낸 모델이 없습니다.');return
        manifest=json.loads(index.read_text())
        if manifest.get('schema_version')!=1:raise ValueError('지원하지 않는 모델 레지스트리 버전')
        for entry in manifest.get('models',[]):
            try:
                version=entry['version']
                if not isinstance(version,str) or '/' in version or '\\' in version or version in {'.','..',''}:raise ValueError('모델 경로 오류')
                root=(self.folder/version).resolve()
                if not root.is_relative_to(self.folder.resolve()):raise ValueError('모델 경로 범위 오류')
                for filename in ['model.joblib','report.json','dataset.csv','review_manifest.json']:
                    if sha256(root/filename)!=entry['sha256'][filename]:raise ValueError('모델/데이터/승인 기록 해시 불일치')
                report=json.loads((root/'report.json').read_text())
                audit=json.loads((root/'review_manifest.json').read_text())
                if audit.get('fixture_only') and not allow_test_fixtures:raise ValueError('합성 테스트 모델은 공개 추론 서버에서 제공할 수 없습니다.')
                if not audit.get('source_review_verified') or audit.get('dataset_hash')!=report.get('dataset_hash'):raise ValueError('검증된 원문 승인 기록 없음')
                if audit.get('source_release_sha256')!=source_release_digest(source_root or self.folder.parent):raise ValueError('원본 또는 검토 판정 변경 · 재학습 필요')
                if not report.get('active') or report.get('rows',0)<20 or report.get('dois',0)<5:raise ValueError('검증을 통과한 모델이 아닙니다.')
                if report.get('version')!=version:raise ValueError('모델 버전 불일치')
                if report.get('structure')!='MFM' or report.get('target')!='2Pr':raise ValueError('지원하지 않는 모델 범위')
                # Never load remote/uploaded joblib. Only files built with the server image.
                bundle=joblib.load(root/'model.joblib')
                if bundle['report']!=report:raise ValueError('모델과 검증 보고서 불일치')
                key=(report['structure'],report['target'],report['measurement_method'])
                if key in self.bundles:raise ValueError('동일 범위의 활성 모델 중복')
                self.bundles[key]=bundle
            except (KeyError,ValueError,OSError) as exc:self.problems.append(str(exc))

    def metadata(self):
        return [dict(**b['report'],limits=b['limits'],categories=b['categories'],electrode_pairs=b['pairs']) for b in self.bundles.values()]
