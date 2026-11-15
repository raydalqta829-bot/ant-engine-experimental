"""Independent architecture/clearance checks and provisional vertical reservations."""
import json,math,itertools
from pathlib import Path
from shapely.geometry import Polygon,box,Point,LineString
from shapely.ops import unary_union,linemerge
from contract import validate

def lines(geometry):
    if geometry.geom_type=='LineString':return [geometry]
    return [p for part in getattr(geometry,'geoms',[]) for p in lines(part)]
def rect(r):return box(r['x'],r['y'],round(r['x']+r['width'],3),round(r['y']+r['depth'],3))
def portal(a,b,rid,receiver,width=.9,kind=None,served_core=None):
    shared=a.boundary.intersection(b.boundary)
    if shared.geom_type=='MultiLineString':shared=linemerge(shared)
    candidates=[]
    for piece in lines(shared):
        coords=list(piece.simplify(.000001).coords)
        candidates.extend(LineString([a,b]) for a,b in zip(coords,coords[1:]))
    candidates=[l for l in candidates if l.length>=width+.3999]
    if not candidates:raise ValueError('No legal door contact: '+rid)
    candidates=sorted(candidates,key=lambda l:l.length,reverse=True);chosen=None
    for line in candidates:
        for t in [.5,.4,.6,.3,.7]:
            p=line.interpolate(t,normalized=True)
            if min(p.distance(Point(line.coords[0])),p.distance(Point(line.coords[-1])))<width/2+.1999:continue
            if served_core is not None and served_core.distance(p)>.951:continue
            chosen=(line,p);break
        if chosen:break
    if chosen is None:raise ValueError('No doorway reaches clear family circulation: '+rid)
    line,p=chosen;start,end=line.coords[0],line.coords[-1]
    return {'id':rid,'center':[round(p.x,4),round(p.y,4)],'width':width,'axis':'x' if abs(start[1]-end[1])<1e-6 else 'y','receiving_room':receiver,'kind':kind or 'hinged'}
def guard(o,extra=.2):
    x,y=o['center'];half=o['width']/2+extra
    return box(x-half,y-.3,x+half,y+.3) if o['axis']=='x' else box(x-.3,y-half,x+.3,y+half)

def coordinate(folder):
    request=json.loads((folder/'REQUEST.json').read_text());solution=json.loads((folder/'SOLVER.json').read_text());ground=json.loads((folder/'GROUND.json').read_text());a=json.loads((folder/'GROUND_audit.json').read_text())
    if solution['status'] not in ['FEASIBLE','OPTIMAL']:raise ValueError('Solver did not find a feasible layout')
    rs=solution['rectangles'];family=unary_union([rect(rs[k]) for k in rs if k=='family' or k.startswith('arm')])
    footprint=unary_union([family]+[rect(rs[k]) for k in rs if k!='family' and not k.startswith('arm')]);completion=[]
    if footprint.geom_type=='Polygon':
        for ring in footprint.interiors:
            hole=Polygon(ring)
            if hole.area>3 or family.boundary.intersection(hole.boundary).length<.3:raise ValueError('Unassigned enclosed roof void')
            family=family.union(hole);completion.append({'area_m2':hole.area,'assigned_to':'family','reason':'Close small residual enclosed pocket without moving solved room cores'})
    if family.geom_type!='Polygon' or family.interiors:raise ValueError('Family distributor disconnected or enclosing an unintended void')
    specs=request['floors'][1]['rooms'];shapes={r['id']:family if r['id']=='family' else rect(rs[r['id']]) for r in specs}
    terrace=rect(rs['terrace']);upper=[]
    for s in specs:
        rid=s['id'];label='Child '+rid.split('_')[-1] if rid.startswith('child_') else {'family':'Family Lounge','stair':'Stair','master':'Master Bedroom','master_bath':'Master Bath','family_bath':'Family Bath'}.get(rid,rid.replace('_',' ').title())
        upper.append({'id':rid,'kind':s['kind'],'label':label,'polygon':list(shapes[rid].exterior.coords)[:-1]})
    openings=[];family_core=family.buffer(-.849,join_style='mitre')
    for i,(u,v) in enumerate(request['floors'][1]['required_edges']):
        if v=='OUTSIDE':
            d=portal(shapes[u],terrace,'u_'+u+'_terrace',u,1.6 if u=='family' else .9,'glazed_sliding' if u=='family' else None,family_core if u=='family' else None);d['connects']=[u,'OUTSIDE']
        else:
            width=1.2 if v=='stair' else .8 if v.endswith('bath') else .9
            d=portal(shapes[u],shapes[v],'u_'+str(i),v,width,'opening' if v=='stair' else None,family_core if u=='family' else None);d['connects']=[u,v]
        openings.append(d)
    footprint=unary_union(list(shapes.values()));windows=[]
    for r in upper:
        if r['kind'] in ['circulation']:continue
        edge=shapes[r['id']].boundary.intersection(footprint.exterior);width=.7 if r['kind']=='bath' else 1.4
        options=[]
        for line in lines(edge):
            coords=list(line.coords)
            for start,end in zip(coords,coords[1:]):
                segment=LineString([start,end])
                if segment.length<width+.4:continue
                distances=[segment.length/2]+[i/20 for i in range(1,int(segment.length*20))]
                for distance in sorted(set(distances),key=lambda v:abs(v-segment.length/2)):
                    center=segment.interpolate(distance)
                    if min(center.distance(Point(start)),center.distance(Point(end)))<width/2+.2:continue
                    aperture_line=LineString([(center.x-width/2,center.y),(center.x+width/2,center.y)]) if abs(start[1]-end[1])<1e-6 else LineString([(center.x,center.y-width/2),(center.x,center.y+width/2)])
                    junctions=[Point(v) for poly in list(shapes.values())+[terrace] for v in poly.exterior.coords if segment.distance(Point(v))<1e-6]
                    if any(aperture_line.distance(v)<.19999 for v in junctions):continue
                    d={'id':'n_'+r['id'],'room_id':r['id'],'center':[center.x,center.y],'width':width,'axis':'x' if abs(start[1]-end[1])<1e-6 else 'y'}
                    if any(guard(d,0).intersects(guard(o,.05)) for o in openings):continue
                    options.append((segment.length,d))
        if not options:
            if r['id']=='family' and any(d['kind']=='glazed_sliding' and d['connects']==['family','OUTSIDE'] for d in openings):continue
            raise ValueError('Room lacks a clear exterior window: '+r['id'])
        windows.append(max(options,key=lambda p:p[0])[1])
    lower={r['id']:Polygon(r['polygon']) for r in ground['rooms']};site=request['site'];s=site['setbacks'];legal=box(s['west'],s['south'],site['width']-s['east'],site['depth']-s['north']);lower_foot=unary_union(list(lower.values()))
    shafts=[];ground_min={r['id']:r for r in ground['brief']['rooms']}
    def ground_pass(obstacles):
        for rid,req in ground_min.items():
            free=lower[rid].buffer(-.1,join_style='mitre').difference(obstacles)
            if free.area<req['min_area']-1e-7 or free.buffer(-req['min_side']/2+.001,join_style='mitre').is_empty:return False
        for r in ground['rooms']:
            if r['kind']!='hall':continue
            free=lower[r['id']].buffer(-.1,join_style='mitre').difference(obstacles);core=free.buffer(-.75+.001,join_style='mitre')
            if core.is_empty or core.geom_type!='Polygon':return False
            if any(core.distance(Point(d['center']))>.951 for d in a['doors'] if r['id'] in d['connects']):return False
        return True
    service_options=[]
    for r in upper:
        if r['kind']!='bath':continue
        options=[]
        eligible=sorted([g for g in ground['rooms'] if g['kind'] in ['bathroom','storage','hall']],key=lambda g:['bathroom','storage','hall'].index(g['kind']))
        for g in eligible:
            overlap=shapes[r['id']].buffer(-.1,join_style='mitre').intersection(lower[g['id']].buffer(-.1,join_style='mitre'))
            if overlap.is_empty:continue
            x0,y0,x1,y1=overlap.bounds
            for ix in range(math.ceil((x0+.15)*10),math.floor((x1-.15)*10)+1):
                for iy in range(math.ceil((y0+.15)*10),math.floor((y1-.15)*10)+1):
                    shaft=box(ix/10-.15,iy/10-.15,ix/10+.15,iy/10+.15)
                    if not overlap.buffer(1e-7).covers(shaft) or any(shaft.intersects(guard(d)) for d in a['doors']+a['windows']+openings+windows):continue
                    if ground_pass(shaft):options.append((g,shaft))
            if options:break
        if not options:
            (folder/'SERVICE_PLACEMENT_DEBUG.json').write_text(json.dumps({'room':r,'doors':a['doors']+openings,'windows':a['windows']+windows,'already_placed_shafts':shafts,'ground_pass_without_new_shaft':ground_pass(unary_union([Polygon(s['polygon']) for s in shafts]))},indent=2))
            raise ValueError('No coordinated service riser for '+r['id'])
        service_options.append((r,options))
    service_options.sort(key=lambda group:len(group[1]))
    visits=[0]
    def select_services(index,chosen):
        if index==len(service_options):return chosen
        r,options=service_options[index]
        for g,shaft in options:
            visits[0]+=1
            if visits[0]>10000:return None
            if any(shaft.intersection(item[2]).area>1e-7 for item in chosen):continue
            union=unary_union([shaft]+[item[2] for item in chosen])
            if not ground_pass(union):continue
            answer=select_services(index+1,chosen+[(r,g,shaft)])
            if answer is not None:return answer
        return None
    selected=select_services(0,[])
    if selected is None:raise ValueError('No jointly coordinated service risers within bounded search')
    for r,g,shaft in selected:shafts.append({'id':'wet_'+r['id'],'above':r['id'],'below':g['id'],'polygon':list(shaft.exterior.coords)[:-1],'connection_note':'Joint spatial reservation; horizontal connections and engineering details unverified'})
    shaft_union=unary_union([Polygon(s['polygon']) for s in shafts]);columns=[];upper_columns=[]
    stair=ground['stair_design'];occupied=unary_union([Polygon(p) for p in stair['flights']+[stair['ground_landing'],stair['upper_landing'],stair['turn_landing']]])
    boundary=unary_union([p.boundary for p in lower.values()]);candidates=set()
    for r in ground['rooms']:
        points=list(Polygon(r['polygon']).exterior.coords)
        for u,v in zip(points,points[1:]):
            line=LineString([u,v]);n=max(1,math.ceil(line.length/4.5))
            for i in range(n+1):
                p=line.interpolate(i/n,normalized=True);candidates.add((round(p.x,3),round(p.y,3)))
    all_guards=unary_union([guard(d) for d in a['doors']+a['windows']+openings+windows])
    for cx,cy in sorted(candidates,key=lambda p:(p[1],p[0])):
        if any(Point(cx,cy).distance(Point(c['center']))<1.6 for c in columns):continue
        for dx,dy in itertools.product([0,.05,-.05],[0,.05,-.05]):
            x,y=round(cx+dx,3),round(cy+dy,3);c=box(x-.15,y-.15,x+.15,y+.15)
            if not legal.buffer(1e-7).covers(c) or not lower_foot.buffer(.1,join_style='mitre').buffer(1e-7).covers(c):continue
            if c.intersects(all_guards) or c.intersection(occupied).area>1e-7 or c.intersects(shaft_union):continue
            obs=unary_union([shaft_union,c]+[Polygon(k['polygon']) for k in columns])
            if not ground_pass(obs):continue
            item={'id':'C'+str(len(columns)+1).zfill(2),'center':[x,y],'polygon':list(c.exterior.coords)[:-1],'reserved_size_m':[.3,.3],'continues_at_first_floor':False}
            # Roof supports are a preliminary subset; every continuing column must stack.
            if min(p.boundary.distance(Point(x,y)) for p in shapes.values())<=.2 and c.intersection(footprint).area>1e-7:
                upper_obs=unary_union([shaft_union,c]+[Polygon(k['polygon']) for k in upper_columns]);okay=True
                for u in upper:
                    rid=u['id'];free=shapes[rid].buffer(-.1,join_style='mitre').difference(upper_obs)
                    spec=next(r for r in specs if r['id']==rid)
                    target=spec.get('min_area',16 if rid=='master' else 12 if u['kind']=='bedroom' else 4.5 if u['kind']=='bath' else 0)
                    side=spec.get('min_side',3 if u['kind']=='bedroom' else 1.8 if u['kind']=='bath' else 0)
                    if side and free.buffer(-side/2+.001,join_style='mitre').is_empty:okay=False
                    if free.area<target-1e-7:okay=False
                test_core=family.buffer(-.1,join_style='mitre').difference(upper_obs).buffer(-.749,join_style='mitre')
                if test_core.is_empty or test_core.geom_type!='Polygon' or any(test_core.distance(Point(d['center']))>.951 for d in openings if 'family' in d['connects']):okay=False
                if okay:item['continues_at_first_floor']=True;upper_columns.append(item)
            columns.append(item);break
    upper_obs=unary_union([shaft_union]+[Polygon(c['polygon']) for c in upper_columns]);ground_obs=unary_union([shaft_union]+[Polygon(c['polygon']) for c in columns])
    family_free=family.buffer(-.1,join_style='mitre').difference(upper_obs);core=family_free.buffer(-.75+.001,join_style='mitre')
    if core.is_empty or core.geom_type!='Polygon':raise ValueError('Family circulation is narrower than 1.5 m or disconnected')
    if any(core.distance(Point(d['center']))>.951 for d in openings if 'family' in d['connects']):raise ValueError('Door not served by the clear distributor')
    checks=[]
    for rid,r in ground_min.items():
        free=lower[rid].buffer(-.1,join_style='mitre').difference(ground_obs);checks.append({'room':rid,'net_after_columns_shafts_m2':free.area,'minimum_area_m2':r['min_area'],'pass':free.area>=r['min_area']-1e-7})
    net={rid:p.buffer(-.1,join_style='mitre').difference(upper_obs).area for rid,p in shapes.items()}
    for spec in specs:
        rid=spec['id'];minimum=spec.get('min_area',16 if rid=='master' else 12 if spec['kind']=='bedroom' else 4.5 if spec['kind']=='bath' else 0)
        if net[rid]<minimum-1e-7:raise ValueError('Upper net area below programme after reservations: '+rid)
    q={'ground':ground,'ground_audit':a,'ground_privacy':json.loads((folder/'GROUND_PROVENANCE.json').read_text())['privacy'],'upper_rooms':upper,'terrace':list(terrace.exterior.coords)[:-1],'upper_openings':openings,'upper_windows':windows,'shafts':shafts,'columns':columns,'ground_net_checks':checks,'upper_net_areas_after_columns_shafts_m2':net,'family_daylight':'Exterior window where available; otherwise modelled glazed sliding terrace door, not an invented window','family_clear_width_target_m':1.5,'column_size_is_reservation_not_structural_design':True,'scope':'Generic upper room variables in a north-landing topology; matched cached ground witnesses; no frame capacity analysis'}
    acceptance=validate(q,request)
    if not acceptance['accepted']:raise ValueError(str(acceptance))
    (folder/'REJECTED.json').unlink(missing_ok=True)
    q['completion']=completion;q['acceptance']=acceptance;(folder/'COORDINATION.json').write_text(json.dumps(q,indent=2));return q

if __name__=='__main__':
    import sys
    folder=Path(sys.argv[1])
    try:q=coordinate(folder);print(folder.name,'COORDINATION_PASS',len(q['columns']),'ground reservations',flush=True)
    except Exception as e:
        (folder/'COORDINATION.json').unlink(missing_ok=True)
        for old in folder.iterdir():
            if old.suffix in ['.arch','.svg','.png','.pdf','.dxf']:old.unlink()
        (folder/'REJECTED.json').write_text(json.dumps({'accepted':False,'stage':'coordination','reason':str(e)},indent=2));raise
