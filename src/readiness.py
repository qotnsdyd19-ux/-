"""Reproducible target audit, without fitting unapproved literature candidates."""
import json
from collections import Counter
from pathlib import Path
from src.model import eligible, reasons, train

def write_report(df,out):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    review=df[['record_id','sample_id','structure','source_file','source_sheet','source_row','doi','source_locator','metric','possible_overlap']].copy()
    review['exclusion_reasons']=df.apply(lambda r:'; '.join(reasons(r)),axis=1)
    review.to_csv(out/'review_queue.csv',index=False)
    good=eligible(df)
    try:
        train(df,out/'models')
    except ValueError as exc:
        training={'status':'blocked_before_fit','reason':str(exc),'cross_validation':'not_run_on_unapproved_data'}
    else:
        raise RuntimeError('Public export must not train or publish a model')
    targets=[]
    for structure in ['MFM','MFIS']:
        part=df[df.structure.eq(structure)]
        for label,field in [('2Pr','two_pr'),('Memory Window','memory_window_v'),('Threshold shift','threshold_shift_v'),('Endurance','endurance_cycles')]:
            candidates=part[field].notna()
            if field=='two_pr': candidates &= part.metric.eq('2Pr')
            targets.append(dict(structure=structure,target=label,candidate_rows=int(candidates.sum()),
                                approved_rows=int(len(good)) if structure=='MFM' and field=='two_pr' else 0,
                                active=False,MAE=None,RMSE=None,R2=None,
                                reason='원문 승인·측정 정의·독립 DOI 부족' if field=='two_pr' else
                                '고장 정의·검열을 처리하는 별도 모델 미검증' if field=='endurance_cycles' else '확인된 수치 레이블 없음'))
    report=dict(version='2',sources=df.source_file.value_counts().to_dict(),structures=df.structure.fillna('unknown').value_counts().to_dict(),possible_cross_source_overlap_rows=int(df.possible_overlap.sum()),
                approved_rows=len(good),approved_dois=int(good.doi.nunique()),training=training,targets=targets,
                exclusion_counts=dict(Counter(reason for _,r in df.iterrows() for reason in reasons(r))),
                deployment={'static':'GitHub Pages','backend':'not_deployed','prediction_available':False},
                note='실험값 후보는 독립 관측치·원문 검증값과 다릅니다. 합성 곡선·자동 Pr 배증·자동 승인은 없습니다.')
    (out/'model_status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report
