import json,copy
from pathlib import Path
from run import prepare_ground
from upper_solver import solve_upper
from run import initial_hint
from coordinate import coordinate
from emit import emit
ROOT=Path(__file__).parent
base=json.loads(Path('/workspace/ANT_SITE_SHAPE_TEST/narrow_deep/REQUEST.json').read_text())
raw=json.loads((ROOT/'local_1.json').read_text())
base.update({'id':'witness','search_policy':{'relax_bbox_exterior':True,'local_exterior':True,'relax_north_living':True,'relax_men_position':False},'ground_hint':raw,'ground_seconds':35,'search_seed':26})
folder=ROOT/'trial_b';folder.mkdir(exist_ok=True);(folder/'REQUEST.json').write_text(json.dumps(base,indent=2))
try:
 p,a,pr=prepare_ground(base,trace_dir=folder)
 for n,v in [('GROUND.json',p),('GROUND_audit.json',a),('GROUND_PROVENANCE.json',pr)]: (folder/n).write_text(json.dumps(v,indent=2))
 print('GROUND OK',p['width'],p['depth'],flush=True)
 result=solve_upper(p,base,50,initial_hint(p,base),first_solution=True)
 (folder/'SOLVER.json').write_text(json.dumps(result,indent=2));print('UPPER',result['status'],flush=True)
 if result['status'] in ['FEASIBLE','OPTIMAL']:
  q=coordinate(folder);emit(folder);print('COORDINATION OK',flush=True)
except Exception as e:print('FAILED',str(e),flush=True)
