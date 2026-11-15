import json
from pathlib import Path
from wall_pockets import repair
from audit import audit
from privacy import optimize
ROOT=Path(__file__).parent
for n in ['B6','E']:
 p=json.loads((ROOT/n/'GROUND_BEFORE_WALL_REPAIR.json').read_text());p,repairs=repair(p);a=audit(p)
 for d in a['doors']:
  if 'stair' in d['connects']:d['kind']='opening';d['width']=1.2
 a,pr=optimize(p,a)
 print(n,'privacy precision',pr['gate_pass'],pr['after']['visible_bedroom_rays'],pr['after']['visible_living_rays_from_public_entries'],flush=True)
