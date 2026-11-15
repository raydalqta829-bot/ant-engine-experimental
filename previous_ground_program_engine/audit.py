"""Independent geometric and access audit; does not trust CP-SAT's status."""
import json
import math
from pathlib import Path
from collections import deque
from shapely.geometry import box,LineString,Point,Polygon
from shapely.ops import unary_union,linemerge

ROOT=Path(__file__).parent
EPS=1e-7

def reachable(graph,start,allowed=None):
    seen={start};queue=deque([start])
    while queue:
        for nxt in graph.get(queue.popleft(),[]):
            if nxt not in seen and (allowed is None or nxt in allowed):seen.add(nxt);queue.append(nxt)
    return seen

def audit(plan):
    if plan['status'] not in ['OPTIMAL','FEASIBLE']:return {'accepted':False,'solver_status':plan['status'],'failures':['No feasible solution supplied'],'scope':'Not a production-engine validation'}
    b=plan['brief'];rooms=plan['rooms'];by_id={r['id']:r for r in rooms};polys={r['id']:Polygon(r['polygon']) if r.get('polygon') else box(r['x'],r['y'],round(r['x']+r['width'],3),round(r['y']+r['depth'],3)) for r in rooms};failures=[];net={}
    required={r['id'] for r in b['rooms']}|{r['id'] for r in b['circulation_rooms']}
    if set(by_id)!=required or len(by_id)!=len(rooms):return {'accepted':False,'failures':['Missing, duplicate or unexpected spaces'],'scope':'Independent trial checks only'}
    for requested in b['rooms']:
        rid=requested['id'];r=by_id.get(rid)
        if r is None:failures.append('Missing room '+rid);continue
        if r['kind']!=requested['kind']:failures.append('Wrong kind '+rid)
        clear=polys[rid].buffer(-.1,join_style='mitre');net[rid]=clear.area
        if clear.geom_type!='Polygon' or not clear.is_valid:failures.append('Disconnected clear floor '+rid)
        core=box(r['x']+.1,r['y']+.1,round(r['x']+r['width']-.1,3),round(r['y']+r['depth']-.1,3))
        if not clear.buffer(EPS).covers(core):failures.append('Original usable rectangle lost '+rid)
        if net[rid]+EPS<requested['min_area']:failures.append('Net area too small '+rid)
        if min(r['width']-.2,r['depth']-.2)+EPS<requested['min_side']:failures.append('Clear width too small '+rid)
    if len(rooms)!=len(b['rooms'])+len(b['circulation_rooms']):failures.append('Unexpected room count')
    if sum(r['kind']=='bedroom' for r in rooms)!=sum(r['kind']=='bedroom' for r in b['rooms']):failures.append('Bedroom count changed')
    overlap=0
    for i,a in enumerate(rooms):
        for other in rooms[i+1:]:
            area=polys[a['id']].intersection(polys[other['id']]).area;overlap+=area
            if area>EPS:failures.append('Room overlap '+a['id']+'/'+other['id'])
    footprint=unary_union(list(polys.values()))
    components=1 if footprint.geom_type=='Polygon' else len(footprint.geoms)
    holes=sum(Polygon(q).area>EPS for q in footprint.interiors) if footprint.geom_type=='Polygon' else sum(sum(Polygon(r).area>EPS for r in q.interiors) for q in footprint.geoms)
    if components!=1:failures.append('Building disconnected')
    if holes:failures.append('Unrequested enclosed void')
    s=b['setbacks'];envelope=box(s['west'],s['south'],b['plot_width']-s['east'],b['plot_depth']-s['north'])
    if not envelope.buffer(EPS).covers(footprint.buffer(.1,join_style='mitre')):failures.append('Exterior walls cross setbacks')
    graph={r['id']:set() for r in rooms};doors=[]
    for i,(a,c) in enumerate(plan['connections']):
        graph[a].add(c);graph[c].add(a)
        ca,cc=by_id[a],by_id[c]
        original_a=box(ca['x'],ca['y'],round(ca['x']+ca['width'],3),round(ca['y']+ca['depth'],3))
        original_c=box(cc['x'],cc['y'],round(cc['x']+cc['width'],3),round(cc['y']+cc['depth'],3))
        # Keep all functional doors on the solver's original room-core contact,
        # never on a newly absorbed narrow alcove merely because it is longer.
        shared=original_a.boundary.intersection(original_c.boundary).intersection(polys[a].boundary).intersection(polys[c].boundary)
        if shared.geom_type=='MultiLineString':shared=linemerge(shared)
        lines=[shared] if shared.geom_type=='LineString' else list(getattr(shared,'geoms',[]));lines=[l for l in lines if l.geom_type=='LineString']
        if not lines or max(l.length for l in lines)<1.5-EPS:failures.append('Door has no sufficient shared wall '+a+'/'+c);continue
        wall=max(lines,key=lambda l:l.length);center=wall.interpolate(.5,normalized=True);p0,p1=wall.coords[0],wall.coords[-1];axis='x' if abs(p0[1]-p1[1])<EPS else 'y'
        doors.append({'id':'d_'+str(i),'center':[center.x,center.y],'width':.9,'axis':axis,'connects':[a,c],'receiving_room':c})
    if reachable(graph,'family-foyer')!=set(by_id):failures.append('Disconnected access graph')
    for group in b['guest_groups']:
        allowed=set(group['rooms']);entry=group['entry']
        if reachable(graph,entry,allowed)!=allowed:failures.append('Guest circulation crosses family zone '+group['id'])
    guest_network={rid for group in b['guest_groups'] for rid in group['rooms']}
    family_allowed=set(by_id)-guest_network
    declared_sources=set(b['privacy_guest_room_ids']);expected_sources={rid for rid in guest_network if by_id[rid]['kind'] in ['majlis','dining','living']}
    if declared_sources!=expected_sources:failures.append('Guest sightline sources incomplete')
    if reachable(graph,'family-foyer',family_allowed)!=family_allowed:failures.append('Family route depends on guest rooms')
    for r in b['rooms']:
        if r.get('ensuite_of') and graph[r['id']]!={r['ensuite_of']}:failures.append('Ensuite not private '+r['id'])
    guest=set(b['privacy_guest_room_ids']);private={r['id'] for r in b['rooms'] if r['kind']=='bedroom' or r.get('ensuite_of')}
    if any((a in guest and c in private) or (c in guest and a in private) for a,c in plan['connections']):failures.append('Direct guest/private bedroom door')
    ox,oy=plan['origin'];right=ox+plan['width'];top=oy+plan['depth'];entries=[]
    for rid,side,width in [(e['room'],e['face'],e['width']) for e in b['entries']]:
        r=by_id[rid];center=[r['x']+r['width']/2,r['y']] if side=='south' else [r['x']+r['width'],r['y']+r['depth']/2]
        entries.append({'id':'entry_'+rid.replace('-','_'),'center':center,'width':width,'axis':'x' if side=='south' else 'y','connects':['OUTSIDE',rid],'receiving_room':rid,'double':rid=='main-foyer'})
    hall_access=[]
    for room in rooms:
        if room['kind']!='hall':continue
        walk_core=polys[room['id']].buffer(-(.1+b['corridor_width']/2),join_style='mitre')
        door_distances=[walk_core.distance(Point(d['center'])) for d in doors+entries if room['id'] in d['connects']]
        if walk_core.is_empty or walk_core.geom_type!='Polygon' or any(d>.1+b['corridor_width']/2+.1+EPS for d in door_distances):failures.append('Hall door is served through a narrow or disconnected passage '+room['id'])
        hall_access.append({'room':room['id'],'tested_clear_width_m':b['corridor_width'],'max_door_to_walk_core_m':max(door_distances,default=0)})
    path=plan['family_approach']
    if path['depth']>EPS:
        approach=box(path['x'],path['y'],path['x']+path['width'],path['y']+path['depth'])
        if any(approach.intersection(poly).area>EPS for poly in polys.values()):failures.append('Family entrance approach obstructed')
    windows=[]
    for req in b['rooms']:
        if req['kind']=='storage':continue
        r=by_id[req['id']];faces=[]
        if abs(r['y']+r['depth']-top)<EPS:faces.append(('x',[r['x']+r['width']/2,top]))
        if abs(r['x']-ox)<EPS:faces.append(('y',[ox,r['y']+r['depth']/2]))
        if abs(r['x']+r['width']-right)<EPS:faces.append(('y',[right,r['y']+r['depth']/2]))
        if abs(r['y']-oy)<EPS:faces.append(('x',[r['x']+r['width']/2,oy]))
        width=.8 if req['kind']=='bathroom' else 1.5 if req['id']=='arabic' else 2.4
        exterior=polys[req['id']].boundary.intersection(footprint.exterior)
        lines=[exterior] if exterior.geom_type=='LineString' else [q for q in getattr(exterior,'geoms',[]) if q.geom_type=='LineString']
        segments=[]
        for line in lines:
            coords=list(line.coords)
            for a,c in zip(coords,coords[1:]):
                if Point(a).distance(Point(c))>=width+.4-EPS:segments.append(LineString([a,c]))
        if not segments:failures.append('Room has no usable exterior window wall '+req['id']);continue
        line=max(segments,key=lambda l:l.length);mid=line.interpolate(.5,normalized=True);a,c=line.coords[0],line.coords[-1]
        axis='x' if abs(a[1]-c[1])<EPS else 'y';center=[mid.x,mid.y]
        windows.append({'id':'n_'+req['id'].replace('-','_'),'room_id':req['id'],'center':center,'width':width,'axis':axis})
    platforms=[]
    risers=math.ceil(b['entry_plinth_height_m']/.17) if b['entry_plinth_height_m'] else 0
    for entry in entries:
        if not risers:continue
        x,y=entry['center'];width=entry['width']+.4;out=[]
        if entry['axis']=='x':
            face=y-.1;out.append(box(x-width/2,face-1.2,x+width/2,face))
            for i in range(risers-1):out.append(box(x-width/2,face-1.2-(i+1)*.3,x+width/2,face-1.2-i*.3))
        else:
            face=x+.1;out.append(box(face,y-width/2,face+1.2,y+width/2))
            for i in range(risers-1):out.append(box(face+1.2+i*.3,y-width/2,face+1.2+(i+1)*.3,y+width/2))
        for surface in out:
            if not box(0,0,b['plot_width'],b['plot_depth']).buffer(EPS).covers(surface):failures.append('Entry platform outside parcel')
            if surface.intersection(footprint).area>EPS:failures.append('Entry platform hits building')
        platforms.append({'entry':entry['id'],'risers':risers,'riser_height':b['entry_plinth_height_m']/risers,'surfaces':[list(poly.exterior.coords)[:-1] for poly in out]})
    all_platforms=[__import__('shapely').geometry.Polygon(poly) for platform in platforms for poly in platform['surfaces']]
    for i,a in enumerate(all_platforms):
        for c in all_platforms[i+1:]:
            if a.intersection(c).area>EPS:failures.append('Entry platforms overlap')
    parking=[]
    if b.get('design_parking_count',0)==1:
        # Geometric reservation only. No claim about local parking regulations.
        bay=box(.2,.3,2.8,5.8);access=box(.2,0,2.8,5.8)
        if not box(0,0,b['plot_width'],b['plot_depth']).covers(bay):failures.append('Parking outside parcel')
        if access.intersection(footprint.buffer(.1,join_style='mitre')).area>EPS or any(access.intersection(q).area>EPS for q in all_platforms):failures.append('Parking approach obstructed')
        parking=[{'width_m':2.6,'length_m':5.5,'polygon':list(bay.exterior.coords)[:-1],'access_polygon':list(access.exterior.coords)[:-1],'assumption':'Straight access from south street; maneuvering and regulations unverified'}]
    gross=sum(poly.area for poly in polys.values());bbox=plan['width']*plan['depth'];coverage=gross/bbox
    if coverage<.8-EPS:failures.append('Footprint too scattered for this experiment')
    return {'accepted':not failures,'failures':failures,'scope':'Independent trial checks only; not 009/010 or regulatory approval','requested_count':len(b['rooms']),'rooms_with_circulation_and_stair':len(rooms),'bedroom_count':sum(r['kind']=='bedroom' for r in rooms),'net_areas_m2':net,'gross_area_m2':gross,'bbox_area_m2':bbox,'bbox_coverage':coverage,'envelope_perimeter_m':footprint.length,'holes':holes,'components':components,'overlap_area_m2':overlap,'dedicated_hall_area_m2':sum(polys[r['id']].area for r in rooms if r['kind']=='hall'),'hall_access':hall_access,'guest_paths_separate':not any('Guest circulation' in f for f in failures),'family_path_without_guest_transit':not any('Family route' in f for f in failures),'ensuite_private':all(graph[r['id']]=={r['ensuite_of']} for r in b['rooms'] if r.get('ensuite_of')),'windows':windows,'doors':doors+entries,'platforms':platforms,'parking_reservations':parking,'unverified':['Sightline privacy','Local building codes','Stair treads and upper-storey connection','Furniture and fixture clearances','Structural and MEP coordination','Solar/daylight performance beyond exterior-window existence','Parking maneuvering and local requirements']}

if __name__=='__main__':
    import sys
    path=Path(sys.argv[1]);result=audit(json.loads(path.read_text()));out=path.with_name(path.stem+'_audit.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['doors','windows','platforms','net_areas_m2']},ensure_ascii=False))
