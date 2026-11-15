import json,copy
from pathlib import Path
from upper_solver import solve_upper
from coordinate import coordinate
from emit import emit
ROOT=Path(__file__).parent;folder=ROOT/'C2';p=json.loads((folder/'GROUND.json').read_text());req=json.loads((folder/'REQUEST.json').read_text());prev=json.loads((folder/'SOLVER.json').read_text());hint={k:[v['x'],v['y'],v['width'],v['depth']] for k,v in prev['rectangles'].items()}
result=solve_upper(p,req,45,hint,first_solution=True)
(folder/'SOLVER.json').write_text(json.dumps(result,indent=2));print('C UPPER',result['status'],flush=True)
if result['status'] in ['FEASIBLE','OPTIMAL']:
 try:
  q=coordinate(folder);emit(folder);print('C COORDINATION PASS',flush=True)
 except Exception as e:print('C COORDINATION FAIL',str(e),flush=True)
