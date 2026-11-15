import sys,json,copy,time
from pathlib import Path
ROOT=Path('/workspace/ANT_GROUND_PROGRAM_SOLVER')
sys.path.insert(0,str(ROOT))
from pipeline import generate
OUT=Path(__file__).parent
base=json.loads((ROOT/'cases/family_two_bedrooms/REQUEST.json').read_text())
results={}
for name,w,d in [('narrow_deep',22,40),('wide_shallow',40,22),('near_square',30,30)]:
 req=copy.deepcopy(base);req['id']=name;req['site']['width']=w;req['site']['depth']=d
 req['benchmark_note']='Same family programme; site shape experiment; provisional engineering coordination only'
 print('START',name,w,d,flush=True)
 result=generate(req,OUT/name,seconds=40,render=False,first_feasible=True)
 results[name]=result
 print('RESULT',name,json.dumps(result),flush=True)
 (OUT/'RESULTS.json').write_text(json.dumps(results,indent=2))
