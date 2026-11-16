"""Explicit user authorization: supplied-data experiments, never source approval."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.experimental import train
if __name__=='__main__':
 bundle,cases=train(Path(__file__).resolve().parents[1])
 print(json.dumps({'report':bundle['report'],'actual_input_results':cases},ensure_ascii=False,indent=2))
