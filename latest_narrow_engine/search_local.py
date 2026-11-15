import json,copy
from pathlib import Path
from ground_solver import solve
from complete import complete
from audit import audit
ROOT=Path(__file__).parent
b=json.loads(Path('/workspace/ANT_GROUND_PROGRAM_SOLVER/cases/family_two_bedrooms/GROUND.json').read_text())['brief']
b.update({'plot_width':22,'plot_depth':40,'relax_bbox_exterior':True,'local_exterior':True})
for i,flags in enumerate([{}, {'relax_north_living':True}, {'relax_north_living':True,'relax_men_position':True}]):
 bb=copy.deepcopy(b);bb.update(flags)
 r=solve(bb,'living_hub',30,seed=19+i*7,warm_hint=None)
 (ROOT/('local_'+str(i)+'.json')).write_text(json.dumps(r,indent=2))
 print(i,r['status'],r['seconds'],flush=True)
 if r['status'] in ['FEASIBLE','OPTIMAL']:
  try:
   p=complete(r);a=audit(p);print('AUDIT',a['accepted'],a['failures'],flush=True)
  except Exception as e: print('COMPLETE',str(e),flush=True)
