import json,copy
from pathlib import Path
from ground_solver import solve
from complete import complete
from audit import audit
ROOT=Path(__file__).parent
b=json.loads(Path('/workspace/ANT_GROUND_PROGRAM_SOLVER/cases/family_two_bedrooms/GROUND.json').read_text())['brief']
b['plot_width']=22;b['plot_depth']=40
for tag,flags in [('exterior',{'relax_bbox_exterior':True}),('living',{'relax_north_living':True}),('men',{'relax_men_position':True}),('aspect',{'relax_aspect':True})]:
 bb=copy.deepcopy(b);bb.update(flags)
 r=solve(bb,'living_hub',15,warm_hint=None)
 (ROOT/('diagnose_'+tag+'.json')).write_text(json.dumps(r,indent=2))
 print(tag,r['status'],r['seconds'],flush=True)
 if r['status'] in ['FEASIBLE','OPTIMAL']:
  try:
   p=complete(r);a=audit(p);print('AUDIT',a['accepted'],a['failures'],flush=True)
  except Exception as e: print('COMPLETE',str(e),flush=True)
