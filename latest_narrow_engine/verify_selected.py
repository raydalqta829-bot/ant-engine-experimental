import json,subprocess,itertools
from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union
from audit import audit
from privacy import evaluate,scene
from contract import validate
ROOT=Path(__file__).parent
selected=json.loads((ROOT/'SELECTED.json').read_text());rows={};sigs={}
base=json.loads(Path('/workspace/ANT_SITE_SHAPE_TEST/narrow_deep/REQUEST.json').read_text())
for label,name in selected.items():
 p=ROOT/name;q=json.loads((p/'COORDINATION.json').read_text());req=json.loads((p/'REQUEST.json').read_text())
 assert req['site']==base['site']
 wanted=[r for r in req['floors'][0]['rooms'] if r['kind'] not in ['hall','stair']]
 old=[r for r in base['floors'][0]['rooms'] if r['kind'] not in ['hall','stair']]
 assert wanted==old and req['floors'][1]==base['floors'][1]
 assert audit(q['ground'])['accepted']
 # Fresh compiler validation, compilation and semantic facts.
 cli=ROOT/'node_modules/@chanmeng666/archlang/dist/cli.js'
 result=subprocess.run(['node',str(cli),'validate',str(p/'VILLA.arch'),'--strict','--json'],capture_output=True,text=True)
 val=json.loads(result.stdout);(p/'VALIDATION_STRICT.json').write_text(json.dumps(val,indent=2))
 assert not any(d['severity']=='error' for d in val['diagnostics'])
 allowed={'W_ROOM_NO_FIXTURE','W_ROOM_NOT_EQUATOR_FACING','W_ANNOTATION_OVERLAP','W_HABITABLE_NO_WINDOW'}
 assert all(d['code'] in allowed for d in val['diagnostics'])
 subprocess.run(['node',str(cli),'compile',str(p/'VILLA.arch'),'-f','json','-o',str(p/'VILLA_PLAN.json'),'--json'],capture_output=True,text=True,check=True)
 subprocess.run(['node',str(ROOT/'inspect.mjs'),str(p/'VILLA.arch')],capture_output=True,text=True,check=True)
 facts=json.loads((p/'COMPILER_FACTS.json').read_text());gate=validate(q,req,facts);assert gate['accepted'],gate
 levels={r['level']:r for r in facts['levels']};mapping={r['id']:'r_'+str(i) for i,r in enumerate(q['ground']['rooms'])}
 actual={r['id']:r for r in levels[0]['rooms']}
 for r in q['ground']['rooms']:assert actual[mapping[r['id']]]['floor_polygon']==[{'x':round(x*1000),'y':round(35000-y*1000)} for x,y in r['polygon']]
 edges={tuple(sorted(e['between'])) for e in levels[0]['access']['edges'] if 'exterior' not in e['between']}
 assert edges=={tuple(sorted([mapping[a],mapping[b]])) for a,b in req['floors'][0]['required_edges']}
 assert facts['vertical']['reachable_levels']==[0,1] and all(k['holds'] for k in facts['keeps'])
 lower={c['id']:c for c in json.loads((p/'VILLA_PLAN.L0.json').read_text())['columns']};upper=json.loads((p/'VILLA_PLAN.L1.json').read_text())['columns']
 assert all(c['id'] in lower and all(c[k]==lower[c['id']][k] for k in ['x','y','width','height']) for c in upper)
 fresh=evaluate(q['ground'],q['ground_audit']);assert fresh['visible_bedroom_rays']==0 and fresh['visible_living_rays_from_public_entries']==0
 assert {m['target_room'] for m in scene(q['ground'],q['ground_audit'])[2] if m['target']=='bedroom'}=={'elder','bedroom_2'}
 for rooms in [q['ground']['rooms'],q['upper_rooms']]:
  union=unary_union([Polygon(r['polygon']) for r in rooms]+([Polygon(q['terrace'])] if rooms is q['upper_rooms'] else []))
  assert union.geom_type=='Polygon' and not union.interiors
 assert all(c['pass'] for c in q['ground_net_checks'])
 rs={r['id']:r for r in q['ground']['rooms']};signature=[]
 for a,b in sorted(base['floors'][0]['required_edges']):
  if [a,b] not in req['floors'][0]['required_edges']:signature.append((a,b,None));continue
  u,v=rs[a],rs[b]
  if abs(u['x']+u['width']-v['x'])<1e-6:direction=(1,0)
  elif abs(v['x']+v['width']-u['x'])<1e-6:direction=(-1,0)
  elif abs(u['y']+u['depth']-v['y'])<1e-6:direction=(0,1)
  elif abs(v['y']+v['depth']-u['y'])<1e-6:direction=(0,-1)
  else:raise AssertionError('Requested connection has no core contact')
  signature.append((a,b,direction))
 sigs[label]=signature
 rows[label]={'case':name,'accepted':True,'ground_gross_m2':q['ground_audit']['gross_area_m2'],'bbox_coverage':q['ground_audit']['bbox_coverage'],'ground_dimensions':[q['ground']['width'],q['ground']['depth']],'sampled_rays':fresh['sampled_rays'],'upper_column_reservations':len(upper),'ground_column_reservations':len(lower),'warning_codes':sorted(set(d['code'] for d in val['diagnostics'])),'structural_approval':False}
 (p/'ACCEPTANCE.json').write_text(json.dumps({**gate,'scope':'Declared geometry and sampled privacy only; no structural or regulatory approval'},indent=2))
for a,b in itertools.combinations(sigs,2):
 for swap,sx,sy in itertools.product([False,True],[-1,1],[-1,1]):
  transformed=[(u,v,None if d is None else ((d[1]*sx,d[0]*sy) if swap else (d[0]*sx,d[1]*sy))) for u,v,d in sigs[a]]
  assert transformed!=sigs[b],f'{a}/{b} only differ by rotation/reflection'
prod=Path('/workspace/compare-ant/current')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=prod,text=True).strip()
assert subprocess.check_output(['git','rev-parse','archive/post-v49-development-paused'],cwd=prod,text=True).strip()=='1fcf20596eada738069deb67ae596a385a6b0621'
(ROOT/'VERIFIED.json').write_text(json.dumps({'cases':rows,'different_contact_topologies_up_to_rotation_and_reflection':True,'production_changed':False},indent=2))
print(json.dumps(rows,indent=2))
