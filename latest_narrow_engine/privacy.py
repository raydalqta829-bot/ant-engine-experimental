"""2D open-door sightline sampling, explicitly limited to stated observers/targets."""
import copy
import json
from pathlib import Path
from itertools import product
import numpy as np
from shapely.geometry import Polygon,LineString,Point,box
from shapely.ops import unary_union
import shapely
from ortools.sat.python import cp_model

def interior_samples(poly,margin=.8,steps=3):
    core=poly.buffer(-margin,join_style='mitre')
    if core.is_empty:return [poly.representative_point()]
    x0,y0,x1,y1=core.bounds
    return [Point(x,y) for x,y in product(np.linspace(x0,x1,steps),np.linspace(y0,y1,steps)) if core.buffer(1e-8).covers(Point(x,y))]

def wall_model(plan):
    shapes={r['id']:Polygon(r['polygon']) for r in plan['rooms']}
    return unary_union([p.boundary for p in shapes.values()]).buffer(.1,cap_style='square',join_style='mitre'),shapes

def aperture(o):
    x,y=o['center'];w=o['width']+.1  # 50 mm conservative visibility allowance per jamb.
    return box(x-w/2,y-.13,x+w/2,y+.13) if o['axis']=='x' else box(x-.13,y-w/2,x+.13,y+w/2)

def scene(plan,audit):
    wall,shapes=wall_model(plan)
    bedroom_targets=[(r['id'],p) for r in plan['rooms'] if r['kind']=='bedroom' for p in interior_samples(shapes[r['id']],margin=.8,steps=6)]
    living_targets=interior_samples(shapes['living'],margin=1.2,steps=3)
    sources={rid:interior_samples(shapes[rid],margin=.6,steps=5) for rid in plan['brief']['privacy_guest_room_ids']}
    for entry in audit['doors']:
        if 'OUTSIDE' not in entry['connects']:continue
        x,y=entry['center'];offsets=np.linspace(-entry['width']/2+.1,entry['width']/2-.1,5)
        sources[entry['id']]=[Point(x+d,y-distance) for d,distance in product(offsets,[.8,1.6])] if entry['axis']=='x' else [Point(x+distance,y+d) for d,distance in product(offsets,[.8,1.6])]
    lines=[];meta=[]
    for name,observers in sources.items():
        for observer in observers:
            for target_id,target in bedroom_targets:
                lines.append(LineString([observer,target]));meta.append({'observer':name,'target':'bedroom','target_room':target_id,'from':[observer.x,observer.y],'to':[target.x,target.y]})
            if name in ['entry_main_foyer','entry_women_foyer']:
                for target in living_targets:
                    lines.append(LineString([observer,target]));meta.append({'observer':name,'target':'living','from':[observer.x,observer.y],'to':[target.x,target.y]})
    return wall,lines,meta

def evaluate(plan,audit,cached=None):
    walls,lines,meta=cached or scene(plan,audit)
    opaque=walls.difference(unary_union([aperture(d) for d in audit['doors']+audit['windows']]))
    visible=~shapely.intersects(np.array(lines,dtype=object),opaque)
    exposed=[m for m,ok in zip(meta,visible) if ok]
    return {'sampled_rays':len(lines),'visible_bedroom_rays':sum(m['target']=='bedroom' for m in exposed),'visible_living_rays_from_public_entries':sum(m['target']=='living' for m in exposed),'exposures':exposed,'visibility_jamb_allowance_m':.05,'assumptions':['Plan-level, eye height within open door/window height','All modelled door and window apertures treated as transparent','Openings enlarged 50 mm at each jamb for conservative sampling','Finite observer/target samples; not an exhaustive visibility proof','Bedroom targets are an interior zone, not a furnished bed','Curtains, glazing opacity, door leaves and upper-floor views unmodelled']}

def choices(plan,door):
    by={r['id']:r for r in plan['rooms']}
    if 'OUTSIDE' in door['connects']:return [door['center']]
    a,b=(by[rid] for rid in door['connects'])
    ca=box(a['x'],a['y'],round(a['x']+a['width'],3),round(a['y']+a['depth'],3));cb=box(b['x'],b['y'],round(b['x']+b['width'],3),round(b['y']+b['depth'],3))
    shared=ca.boundary.intersection(cb.boundary)
    if shared.geom_type!='LineString' or shared.length<door['width']+.6:return [door['center']]
    endpoints=list(shared.coords);vertical=door['axis']=='y';axis=1 if vertical else 0
    lo=min(p[axis] for p in endpoints)+door['width']/2+.3;hi=max(p[axis] for p in endpoints)-door['width']/2-.3
    result=[door['center']]
    for value in np.arange(lo,hi+.001,.1):
        q=list(door['center']);q[axis]=round(float(value),3);result.append(q)
    return result

def optimize(plan,audit):
    result=copy.deepcopy(audit);cached=scene(plan,audit);baseline=evaluate(plan,audit,cached);history=[]
    if baseline['visible_bedroom_rays']==0 and baseline['visible_living_rays_from_public_entries']==0:
        return result,{'before':baseline,'after':baseline,'changes':[],'changed_room_polygons':False,'gate_pass':True,'method':'Existing door positions pass the declared conservative sample'}
    walls,lines,meta=cached
    options=[];unions=[]
    for door in result['doors']:
        locations=[door['center']] if 'OUTSIDE' in door['connects'] or 'stair' in door['connects'] else choices(plan,door)
        locations=list({tuple(q):q for q in locations}.values());options.append(locations)
        unions.append(unary_union([aperture({**door,'center':q}) for q in locations]))
    fixed_windows=unary_union([aperture(w) for w in result['windows']])
    always_opaque=walls.difference(unary_union(unions+[fixed_windows]))
    possible=~shapely.intersects(np.array(lines,dtype=object),always_opaque)
    relevant=np.array([l for l,ok in zip(lines,possible) if ok],dtype=object)
    model=cp_model.CpModel();variables=[];blockers=[[] for _ in relevant];objective=[]
    for i,(door,locations) in enumerate(zip(result['doors'],options)):
        selected=[];others=unary_union([u for j,u in enumerate(unions) if j!=i]+[fixed_windows])
        for j,q in enumerate(locations):
            v=model.NewBoolVar(f'door_{i}_option_{j}');selected.append(v)
            opaque_subset=walls.difference(others.union(aperture({**door,'center':q})))
            blocked=shapely.intersects(relevant,opaque_subset)
            for k,yes in enumerate(blocked):
                if yes:blockers[k].append(v)
            displacement=round(Point(q).distance(Point(door['center']))*1000);objective.append(v*displacement)
        model.AddExactlyOne(selected);variables.append(selected)
    impossible=any(not b for b in blockers)
    for b in blockers:model.AddBoolOr(b)
    model.Minimize(sum(objective));solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=5;solver.parameters.num_search_workers=1;solver.parameters.random_seed=19
    status=solver.Solve(model)
    if status in [cp_model.OPTIMAL,cp_model.FEASIBLE]:
        for i,door in enumerate(result['doors']):
            chosen=next(q for q,v in zip(options[i],variables[i]) if solver.Value(v));old=list(door['center']);door['center']=list(chosen)
            if list(chosen)!=old:history.append({'door':door['id'],'from':old,'to':list(chosen),'fixed_shared_wall':True})
    after=evaluate(plan,result,cached)
    return result,{'before':baseline,'after':after,'changes':history,'changed_room_polygons':False,'gate_pass':after['visible_bedroom_rays']==0 and after['visible_living_rays_from_public_entries']==0,'method':'CP-SAT joint door-position selection with sufficient ray-blocking constraints','solver_status':solver.StatusName(status),'candidate_sensitive_rays':len(relevant),'no_blocker_for_some_ray':impossible}

if __name__=='__main__':
    root=Path(__file__).parent;plan=json.loads((root/'living_hub_completed.json').read_text());audit=json.loads((root/'living_hub_completed_audit.json').read_text())
    a,r=optimize(plan,audit);(root/'privacy_review.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));(root/'doors_refined.json').write_text(json.dumps(a,ensure_ascii=False,indent=2))
    print(json.dumps({'before':{k:v for k,v in r['before'].items() if k!='exposures'},'after':{k:v for k,v in r['after'].items() if k!='exposures'},'changes':r['changes'],'gate_pass':r['gate_pass']},ensure_ascii=False))
