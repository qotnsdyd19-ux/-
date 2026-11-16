"""Regenerate public explorer exclusively from bundled, unapproved sources."""
from pathlib import Path
import sys
import shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data import export
root=Path(__file__).resolve().parents[1]
df,stats,_=export(root/'data/raw',root/'data')
cols=[c for c in df.columns if c!='raw_json']
(root/'docs/data.json').write_text(df[cols].to_json(orient='records',force_ascii=False,indent=2))
for name in ['normalized.csv','quality.json']: shutil.copyfile(root/'data'/name,root/'docs'/name)
from src.readiness import write_report
write_report(df,root/'docs')
print(f'Public explorer: {len(df)} rows; {stats["two_pr_candidates"]} 2Pr candidates; 0 approvals')
