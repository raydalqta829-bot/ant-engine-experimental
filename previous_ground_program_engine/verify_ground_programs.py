import copy,json,subprocess
from pathlib import Path
from collections import Counter
from shapely.geometry import Polygon
from shapely.ops import unary_union
from audit import audit
from privacy import evaluate,scene
from contract import validate
from pipeline import generate
ROOT=Path(__file__).parent;cases={};checks=[]
for folder in sorted((ROOT/'cases').iterdir()):
    request=json.loads((folder/'REQUEST.json').read_text());q=json.loads((folder/'COORDINATION.json').read_text());f=json.loads((folder/'VILLA_FACTS.json').read_text());gate=validate(q,request,f)
    assert gate['accepted'],gate
    assert q['ground']==json.loads((folder/'GROUND.json').read_text())
    assert audit(q['ground'])['accepted']
    assert not (folder/'REJECTED.json').exists() and not (folder/'GROUND_REJECTED.json').exists()
    fresh_privacy=evaluate(q['ground'],q['ground_audit']);assert fresh_privacy['visible_bedroom_rays']==0 and fresh_privacy['visible_living_rays_from_public_entries']==0
    target_ids={m['target_room'] for m in scene(q['ground'],q['ground_audit'])[2] if m['target']=='bedroom'}
    bedrooms={r['id'] for r in request['floors'][0]['rooms'] if r['kind']=='bedroom'};assert target_ids==bedrooms
    levels={l['level']:l for l in f['levels']};mapping={r['id']:'r_'+str(i) for i,r in enumerate(q['ground']['rooms'])}
    actual_rooms={r['id']:r for r in levels[0]['rooms']}
    for r in q['ground']['rooms']:assert actual_rooms[mapping[r['id']]]['floor_polygon']==[{'x':round(x*1000),'y':round(35000-y*1000)} for x,y in r['polygon']]
    actual_edges={tuple(sorted(e['between'])) for e in levels[0]['access']['edges'] if 'exterior' not in e['between']}
    expected_edges={tuple(sorted([mapping[a],mapping[b]])) for a,b in request['floors'][0]['required_edges']};assert actual_edges==expected_edges
    actual_entries=[e for e in levels[0]['access']['edges'] if 'exterior' in e['between']];assert len(actual_entries)==len(request['entries'])
    assert len(levels[0]['rooms'])==len(request['floors'][0]['rooms']);assert len(levels[1]['rooms'])==8
    assert f['vertical']['reachable_levels']==[0,1] and all(k['holds'] for k in f['keeps'])
    lower={c['id']:c for c in json.loads((folder/'VILLA_PLAN.L0.json').read_text())['columns']};upper=json.loads((folder/'VILLA_PLAN.L1.json').read_text())['columns']
    assert all(c['id'] in lower and all(c[k]==lower[c['id']][k] for k in ['x','y','width','height']) for c in upper)
    for floor in [q['ground']['rooms'],q['upper_rooms']]:
        union=unary_union([Polygon(r['polygon']) for r in floor]+([Polygon(q['terrace'])] if floor is q['upper_rooms'] else []));assert union.geom_type=='Polygon' and not union.interiors
    for check in q['ground_net_checks']:assert check['pass']
    original={r['id']:r for r in request['floors'][0]['rooms']}
    for minimum in q['ground']['brief']['rooms']:assert minimum['min_area']==original[minimum['id']]['min_area'] and minimum['min_side']==original[minimum['id']]['min_side']
    assert not json.loads((folder/'RENDER_DIAGNOSTICS.json').read_text());lint=json.loads((folder/'VILLA_LINT.json').read_text());assert not any(d['severity']=='error' for d in lint)
    allowed={'W_ROOM_NO_FIXTURE','W_ROOM_NOT_EQUATOR_FACING','W_ANNOTATION_OVERLAP','W_HABITABLE_NO_WINDOW'}
    assert all(d['code'] in allowed for d in lint),[(d['code'],d['message']) for d in lint if d['code'] not in allowed]
    for n in ['COORD_GROUND','COORD_FIRST']:assert (folder/(n+'.pdf')).read_bytes().startswith(b'%PDF-')
    provenance=json.loads((folder/'GROUND_PROVENANCE.json').read_text());upper_search=json.loads((folder/'SOLVER.json').read_text());assert provenance['ground_search']['status'] in ['FEASIBLE','OPTIMAL'] and upper_search['status'] in ['FEASIBLE','OPTIMAL']
    row={'accepted_for_declared_gates':True,'requested_ground_functions':len(q['ground']['brief']['rooms']),'ground_spaces_including_circulation':len(q['ground']['rooms']),'ground_bedrooms':len(bedrooms),'ground_entrances':len(actual_entries),'ground_gross_room_polygons_m2':q['ground_audit']['gross_area_m2'],'upper_gross_room_polygons_m2':sum(Polygon(r['polygon']).area for r in q['upper_rooms']),'ground_column_reservations':len(lower),'upper_column_reservations':len(upper),'privacy_target_room_ids':sorted(target_ids),'sampled_sightlines':fresh_privacy['sampled_rays'],'family_approach_depth_m':q['ground']['family_approach']['depth'],'bbox_coverage':q['ground_audit']['bbox_coverage'],'wall_pocket_repairs':provenance.get('wall_pocket_repairs',[]),'floorplate_stitching':provenance.get('floorplate_stitching',{'applied':False}),'max_upper_arms':len([k for k in upper_search['rectangles'] if k.startswith('arm')]),'lint_counts':dict(Counter(d['code'] for d in lint)),'structural_design_approved':False}
    (folder/'ACCEPTANCE.json').write_text(json.dumps({**gate,'structural_design_approved':False,'warning_codes':row['lint_counts']},indent=2));cases[folder.name]=row;checks.append(folder.name+': exact brief, compiled polygons/edges/entries, two-floor access, columns, services and all bedroom privacy samples')
middle=ROOT/'cases/family_two_bedrooms';q=json.loads((middle/'COORDINATION.json').read_text());bad=copy.deepcopy(q['ground']);bad['rooms']=[r for r in bad['rooms'] if r['id']!='bedroom_2'];assert not audit(bad)['accepted']
bad=copy.deepcopy(q['ground']);bad['connections'].append(['men','bedroom_2']);review=audit(bad);assert not review['accepted'] and any('Direct guest/private bedroom door' in s for s in review['failures']);checks.append('Missing second bedroom and a direct guest-to-bedroom connection are rejected')
req=json.loads((middle/'REQUEST.json').read_text());req['site']['street']='north';out=ROOT/'rejection_smoke';out.mkdir(exist_ok=True);(out/'stale.pdf').write_bytes(b'%PDF-test-only');rejection=generate(req,out,1,False);assert not rejection['accepted'] and not list(out.glob('*.pdf'));checks.append('Unsupported orientation rejected without stale drawings')
prod=Path('/workspace/compare-ant/current');assert not subprocess.check_output(['git','status','--porcelain'],cwd=prod,text=True).strip();assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=prod,text=True).strip()=='d0d1f2b0fee8c67ed45d6dfdcf1a7b0820db205a';assert subprocess.check_output(['git','rev-parse','archive/post-v49-development-paused'],cwd=prod,text=True).strip()=='1fcf20596eada738069deb67ae596a385a6b0621';checks.append('Production, A2 reference and paused branch untouched')
assert [cases[n]['ground_bedrooms'] for n in ['compact_one_bedroom','family_two_bedrooms','expanded_hospitality']]==[1,2,1]
assert [cases[n]['ground_entrances'] for n in ['compact_one_bedroom','family_two_bedrooms','expanded_hospitality']]==[2,2,3]
smoke_path=ROOT/'PIPELINE_SMOKE.json'
if smoke_path.exists():
    smoke=json.loads(smoke_path.read_text());assert smoke['accepted'],smoke;checks.append('Full generic two-bedroom ground pipeline, including upper generation and compiler gates, passes without rendering')
result={'cases':cases,'checks_passed':checks,'same_plot_m':[30,35],'same_upper_programme':True,'structural_approval':False,'production_changed':False,'scope':'Three measured ground programmes with explicit room graphs, rectangular south-street sites and north stair arrival; not all villa programmes or local codes'}
(ROOT/'VERIFICATION.json').write_text(json.dumps(result,indent=2));print(json.dumps({'cases':{k:{x:v[x] for x in ['requested_ground_functions','ground_bedrooms','ground_entrances','ground_gross_room_polygons_m2']} for k,v in cases.items()},'checks':len(checks)},indent=2))
