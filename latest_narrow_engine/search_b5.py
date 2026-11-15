import json,copy
from pathlib import Path
from pipeline import generate
ROOT=Path(__file__).parent
base=json.loads(Path('/workspace/ANT_SITE_SHAPE_TEST/narrow_deep/REQUEST.json').read_text())
for name,profile,seed,hint,strict in [('B5','west_stair_east_service',33,None,True)]:
 req=copy.deepcopy(base);req['id']=name;req['search_seed']=seed;req['ground_seconds']=45
 req['search_policy']={'relax_bbox_exterior':True,'local_exterior':strict,'relax_north_living':True,'relax_men_position':True,'topology_profile':profile,'max_wall_pocket_repair_m2':6,'side_family_entry':True}
 if hint:req['ground_hint']=json.loads((ROOT/hint).read_text())
 print('START',name,profile,flush=True)
 g=generate(req,ROOT/name,seconds=45,render=False,first_feasible=True)
 print('RESULT',name,json.dumps(g),flush=True)
