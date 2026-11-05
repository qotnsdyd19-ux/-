"""Regenerate public explorer exclusively from bundled, unapproved sources."""
from pathlib import Path
import sys
import shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data import export
root=Path(__file__).resolve().parents[1]
df,stats,_=export(root/'data/raw',root/'data')
cols=['record_id','source_file','source_row','sample_id','paper','doi','source_url','metric','hzo_nm','two_pr','top','bottom','anneal_c','anneal_type','measurement_state','notes']
(root/'docs/data.json').write_text(df[cols].to_json(orient='records',force_ascii=False,indent=2))
for name in ['normalized.csv','quality.json']: shutil.copyfile(root/'data'/name,root/'docs'/name)
print(f'Public explorer: {len(df)} rows; {stats["two_pr_candidates"]} 2Pr candidates; 0 approvals')
