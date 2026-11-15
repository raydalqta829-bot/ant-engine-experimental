"""Independent client brief and acceptance gate; contains no layout coordinates."""
from collections import defaultdict,deque,Counter
from shapely.geometry import Polygon,box
from shapely.ops import unary_union

def validate(candidate,brief,compiled=None):
    errors=[];site=brief['site'];s=site['setbacks']
    legal=box(s['west'],s['south'],site['width']-s['east'],site['depth']-s['north'])
    floors={0:candidate['ground']['rooms'],1:candidate['upper_rooms']}
    shapes={}
    for floor,rooms in floors.items():
        expected={r['id']:r for r in brief['floors'][floor]['rooms']};actual={r['id']:r for r in rooms}
        missing=sorted(set(expected)-set(actual));extra=sorted(set(actual)-set(expected))
        if missing:errors.append({'code':'MISSING_ROOMS','floor':floor,'ids':missing})
        if extra:errors.append({'code':'UNREQUESTED_ROOMS','floor':floor,'ids':extra})
        if len(actual)!=len(rooms):errors.append({'code':'DUPLICATE_IDS','floor':floor})
        for rid,r in actual.items():
            if rid in expected and r['kind']!=expected[rid]['kind']:errors.append({'code':'WRONG_ROOM_KIND','floor':floor,'id':rid})
            p=Polygon(r['polygon']);shapes[floor,rid]=p
            if not p.is_valid:errors.append({'code':'INVALID_POLYGON','floor':floor,'id':rid})
            if not legal.buffer(1e-6).covers(p.buffer(.1,join_style='mitre')):errors.append({'code':'SETBACK_EXCEEDED','floor':floor,'id':rid})
        for i,r in enumerate(rooms):
            for q in rooms[i+1:]:
                if shapes[floor,r['id']].intersection(shapes[floor,q['id']]).area>1e-7:errors.append({'code':'ROOM_OVERLAP','floor':floor,'ids':[r['id'],q['id']]})
    graph=defaultdict(set)
    for d in candidate['upper_openings']:
        a,b=d['connects'];graph[a].add(b);graph[b].add(a)
    for a,b in brief['floors'][1]['required_edges']:
        if b not in graph[a]:errors.append({'code':'MISSING_REQUIRED_CONNECTION','floor':1,'ids':[a,b]})
    seen={'stair'};queue=deque(seen)
    while queue:
        a=queue.popleft()
        for b in graph[a]:
            if b not in seen:seen.add(b);queue.append(b)
    for r in brief['floors'][1]['rooms']:
        if r['id'] not in seen:errors.append({'code':'UNREACHABLE_FROM_STAIR','floor':1,'id':r['id']})
    if graph['master_bath']!={'master'}:errors.append({'code':'ENSUITE_NOT_PRIVATE'})
    base=unary_union([shapes[0,r['id']] for r in floors[0]])
    for r in floors[1]:
        if not base.buffer(1e-6).covers(shapes[1,r['id']]):errors.append({'code':'UPPER_OUTSIDE_LOWER_FOOTPRINT','id':r['id']})
    if not legal.buffer(1e-6).covers(Polygon(candidate['terrace']).buffer(.1,join_style='mitre')):errors.append({'code':'TERRACE_SETBACK_EXCEEDED'})
    if not all(r['pass'] for r in candidate['ground_net_checks']):errors.append({'code':'GROUND_COLUMN_NET_AREA_FAILED'})
    if not candidate['ground']['stair_design']['checks']['pass']:errors.append({'code':'STAIR_GEOMETRY_FAILED'})
    if compiled is not None:
        levels={l['level']:l for l in compiled.get('levels',[])}
        for floor,rooms in floors.items():
            actual=len(levels.get(floor,{}).get('rooms',[]))
            if actual!=len(brief['floors'][floor]['rooms']):errors.append({'code':'COMPILED_ROOM_COUNT_MISMATCH','floor':floor,'actual':actual,'expected':len(brief['floors'][floor]['rooms'])})
        if compiled.get('vertical',{}).get('reachable_levels')!=[0,1]:errors.append({'code':'COMPILED_VERTICAL_ACCESS_FAILED'})
    return {'accepted':not errors,'errors':errors,'codes':dict(Counter(e['code'] for e in errors)),'scope':'Architectural contract gate; not a structural or code approval'}
