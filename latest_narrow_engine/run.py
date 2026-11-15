import json,copy,sys
from pathlib import Path
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from upper_solver import solve_upper
from audit import audit
from privacy import optimize
from stair import design
ROOT=Path(__file__).parent

def prepare_ground(request,trace_dir=None):
    site=request['site'];dims=(site['width'],site['depth'])
    library=[]
    for seed in reversed(json.loads((ROOT/'GROUND_HINTS.json').read_text())):
        candidate=seed['ground'];path=seed['name']
        distance=abs(candidate['brief']['plot_width']-site['width'])+abs(candidate['brief']['plot_depth']-site['depth'])
        target={r['id']:r for r in request['floors'][0]['rooms'] if r['kind'] not in ['hall','stair']};prior={r['id']:r for r in candidate['brief']['rooms']}
        distance+=10*len(set(target)^set(prior))+sum(abs(target[k]['min_area']-prior[k]['min_area'])/10 for k in set(target)&set(prior))
        library.append((distance,path,candidate))
    _,path,p=min(library,key=lambda v:v[0])
    if site['street']!='south':raise ValueError('South-street benchmark only')
    request_rooms=request['floors'][0]['rooms']
    ids=[r['id'] for r in request_rooms]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate ground room IDs')
    if not {'living','main-foyer','family-foyer','stair'}<=set(ids):raise ValueError('Missing required circulation roles')
    allowed={'majlis','living','dining','kitchen','storage','bedroom','bathroom','hall','stair'}
    if any(r['kind'] not in allowed for r in request_rooms):raise ValueError('Unsupported ground room kind')
    if any(r.get('ensuite_of') and r['ensuite_of'] not in ids for r in request_rooms):raise ValueError('Ensuite target is missing')
    if any(e['room'] not in {'main-foyer','family-foyer','women-foyer'} or e['face'] not in ['south','east'] for e in request['entries']):raise ValueError('Unsupported entry role or face')
    p=copy.deepcopy(p);p['brief']['floors']=2
    p['brief']['rooms']=[copy.deepcopy(r) for r in request_rooms if r['kind'] not in ['hall','stair']]
    p['brief']['circulation_rooms']=[copy.deepcopy(r) for r in request_rooms if r['kind'] in ['hall','stair']]
    p['brief']['connections']=request['floors'][0]['required_edges']
    for key in ['entries','entry_rooms','guest_groups','family_rooms','privacy_guest_room_ids']:p['brief'][key]=request[key]
    p['brief']['plot_width']=site['width'];p['brief']['plot_depth']=site['depth'];p['brief']['setbacks']=site['setbacks']
    p['brief'].update(request.get('search_policy',{}))
    from ground_solver import solve as solve_ground
    from complete import complete
    raw=solve_ground(p['brief'],'living_hub',request.get('ground_seconds',35),seed=request.get('search_seed',19),privacy_entry=p.get('larger_privacy_entries',False),warm_hint=request.get('ground_hint',p))
    if raw['status'] not in ['FEASIBLE','OPTIMAL']:raise ValueError('Ground CP-SAT returned '+raw['status']+'; no cached fallback drawing')
    ground_search={k:v for k,v in raw.items() if k not in ['rooms','brief','connections','entry_rooms']}
    folder=Path(trace_dir) if trace_dir is not None else ROOT/'cases'/request['id'];folder.mkdir(parents=True,exist_ok=True)
    (folder/'GROUND_RAW.json').write_text(json.dumps(raw,indent=2))
    p=complete(raw)
    (folder/'GROUND_COMPLETED_BEFORE_PATCHES.json').write_text(json.dumps(p,indent=2))

    # Create small usable-area margins for shaft reservation in existing wet/storage rooms.
    patches=[]
    minimum={r['id']:r['min_area'] for r in p['brief']['rooms']}
    for r in p['rooms']:
        if r['kind'] not in ['bathroom','storage']:continue
        for attempt in range(4):
            poly=Polygon(r['polygon'])
            if poly.buffer(-.1,join_style='mitre').area>=minimum[r['id']]+.3:break
            grown=box(r['x'],r['y'],round(r['x']+r['width'],3),round(r['y']+r['depth']+.1,3))
            extra=grown.difference(poly);others=unary_union([Polygon(s['polygon']) for s in p['rooms'] if s['id']!=r['id']])
            if extra.intersection(others).area>1e-7:break
            physical=unary_union([grown,others]).buffer(.1,join_style='mitre')
            if physical.geom_type=='Polygon' and any(Polygon(ring).area>.01 for ring in physical.interiors):break
            legal=box(site['setbacks']['west'],site['setbacks']['south'],site['width']-site['setbacks']['east'],site['depth']-site['setbacks']['north'])
            if not legal.buffer(1e-7).covers(grown.buffer(.1,join_style='mitre')):break
            r['depth']=round(r['depth']+.1,3);r['polygon']=list(grown.exterior.coords)[:-1];r['core']={k:r[k] for k in ['x','y','width','depth']};patches.append({'id':r['id'],'north_extension_m':.1})
    top=max(max(y for x,y in r['polygon']) for r in p['rooms']);p['depth']=round(top-p['origin'][1],3)
    (folder/'GROUND_BEFORE_WALL_REPAIR.json').write_text(json.dumps(p,indent=2))
    from wall_pockets import repair
    p,wall_repairs=repair(p)
    a=audit(p)
    (folder/'GROUND_GEOMETRY_REVIEW.json').write_text(json.dumps(a,indent=2))
    if not a['accepted']:raise ValueError(str(a['failures']))
    for d in a['doors']:
        if 'stair' in d['connects']:d['kind']='opening';d['width']=1.2
    a,privacy=optimize(p,a)
    if not privacy['gate_pass']:raise ValueError('Privacy gate failed: '+str(privacy['after']['exposures'][:3]))
    p['stair_design']=design(p,a);a['refinement_gate']=True
    from floorplate import stitch
    p,a,stitching=stitch(p,a,request)
    if stitching['applied']:privacy=stitching['privacy']
    return p,a,{'method':'CP-SAT ground generation on request dimensions, with library solutions as unlocked hints; no cached fallback','source':str(path),'ground_search':ground_search,'patches':patches,'wall_pocket_repairs':wall_repairs,'floorplate_stitching':stitching,'privacy':privacy}

def initial_hint(ground,request):
    # Translate a previous starting suggestion to the current landing; all coordinates remain unlocked.
    stair=next(r for r in ground['rooms'] if r['id']=='stair');living=next(r for r in ground['rooms'] if r['id']=='living')
    dx=stair['x']-16.9;dy=stair['y']+stair['depth']-9.2
    base={'arm0':[6.3,9.6,13.8,1.8],'arm1':[10.3,7.6,1.8,3.8],
          'child_1':[10.3,3.1,3.7,4.5],'child_2':[6.3,6.1,4,3.5],'child_3':[6.3,11.4,4,4.5],
          'master':[20.1,10.7,3.7,5.2],'master_bath':[23.8,10.7,2.2,3.9],'family_bath':[20.1,5.6,2.7,5.1],'terrace':[14.5,12.4,5.6,3.5]}
    hint={k:[round(x+dx,3),round(y+dy,3),w,h] for k,(x,y,w,h) in base.items()}
    w=min(6.2,living['width']);h=max(3.2,round(16/(w-.2)+.3,1))
    hint['family']=[living['x'],round(stair['y']+stair['depth'],3),w,min(h,living['depth'])]
    by={r['id']:r for r in ground['rooms']}
    if 'bedroom_2' in by and by['men']['depth']>=7.5 and by['kitchen']['x']<living['x']:
        men=by['men'];k=by['kitchen'];foyer=by['family-foyer'];main=by['main-foyer'];master=by['elder'];bath=by['elder-bath'];bed=by['bedroom_2']
        half=round(men['depth']/2,1);ty=max(foyer['y'],round(master['y']+1.4-2.8,1));top=round(ty+2.8,1)
        hint={'child_1':[men['x'],men['y'],men['width'],half],'child_2':[men['x'],round(men['y']+half,1),men['width'],round(men['depth']-half,1)],'child_3':[bed['x'],bed['y'],bed['width'],bed['depth']],
              'master':[master['x'],master['y'],master['width'],master['depth']],'master_bath':[bath['x'],bath['y'],bath['width'],bath['depth']],
              'family_bath':[k['x'],round(main['y']+main['depth']-2.7,1),2.2,2.7],'terrace':[foyer['x'],ty,foyer['width'],2.8],
              'family':[living['x'],living['y'],living['width'],3.2],
              'arm0':[k['x'],living['y'],round(living['x']+1.8-k['x'],1),1.8],
              'arm1':[k['x'],men['y'],1.8,round(k['y']+k['depth']-men['y'],1)],
              'arm2':[round(foyer['x']+foyer['width']-1.8,1),top,1.8,round(living['y']+1.8-top,1)],
              'arm3':[foyer['x'],top,foyer['width'],1.8]}
    return hint

def run(request,seconds=35):
    folder=Path(trace_dir) if trace_dir is not None else ROOT/'cases'/request['id'];folder.mkdir(parents=True,exist_ok=True)
    (folder/'REQUEST.json').write_text(json.dumps(request,indent=2))
    p,a,source=prepare_ground(request)
    (folder/'GROUND.json').write_text(json.dumps(p,indent=2));(folder/'GROUND_audit.json').write_text(json.dumps(a,indent=2));(folder/'GROUND_PROVENANCE.json').write_text(json.dumps(source,indent=2))
    hint=initial_hint(p,request);(folder/'SEARCH_HINT.json').write_text(json.dumps(hint,indent=2))
    result=solve_upper(p,request,seconds,hint)
    (folder/'SOLVER.json').write_text(json.dumps(result,indent=2));print(request['id'],result['status'],result['seconds'],flush=True)
    return folder,result

if __name__=='__main__':
    for folder in sorted((ROOT/'cases').iterdir()):
        if (folder/'REQUEST.json').exists():run(json.loads((folder/'REQUEST.json').read_text()))
