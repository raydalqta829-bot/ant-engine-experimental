import json,copy
from pathlib import Path
from pipeline import generate
ROOT=Path(__file__).parent
base=json.loads(Path('/workspace/ANT_SITE_SHAPE_TEST/narrow_deep/REQUEST.json').read_text())
for name,profile,seed,hint,strict in [('F','east_bedroom',26,'trial_b/GROUND_RAW.json',True),('G','rear_kitchen',111,'C2/GROUND_RAW.json',True)]:
 req=copy.deepcopy(base);req['id']=name;req['search_seed']=seed;req['ground_seconds']=35
 req['search_policy']={'relax_bbox_exterior':True,'local_exterior':strict,'relax_north_living':True,'relax_men_position':True,'topology_profile':profile}
 if hint:req['ground_hint']=json.loads((ROOT/hint).read_text())
 if name=='G':req['search_policy']['ensuite_east']=True
 print('START',name,profile,flush=True)
 g=generate(req,ROOT/name,seconds=45,render=False,first_feasible=True)
 print('RESULT',name,json.dumps(g),flush=True)
