import json
import sys
from pathlib import Path
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union

def produce(plan,audit):
    if not audit['accepted'] or not audit.get('refinement_gate'):raise ValueError('Only plans passing the current independent refinement gates can be drawn')
    labels={'men':'Men Majlis','arabic':'Guest Dining','women':'Women Majlis','living':'Family Living','dining':'Family Dining','kitchen':'Kitchen','store':'Store','men-wc':'Men WC','women-wc':'Women WC','elder':'Bedroom','elder-bath':'Ensuite','main-foyer':'Main Entry','family-foyer':'Family Hall','women-foyer':'Women Entry','stair':'Stair Reserve'}
    ids={r['id']:'r_'+str(i) for i,r in enumerate(plan['rooms'])}
    transform=lambda q:(round(q[0]*1000),round(35000-q[1]*1000))
    point=lambda q:f'({q[0]},{q[1]})'
    shapes={r['id']:Polygon([transform(q) for q in r['polygon']]) for r in plan['rooms']}
    boundary=unary_union([p.boundary for p in shapes.values()]);segments=[]
    for line in boundary.geoms:
        coords=list(line.coords)
        for a,b in zip(coords,coords[1:]):
            ends=tuple(sorted((a,b)));mid=Point((a[0]+b[0])/2,(a[1]+b[1])/2);owners=frozenset(rid for rid,p in shapes.items() if p.boundary.distance(mid)<1e-6)
            segments.append((ends,owners))
    segments=list(dict.fromkeys(segments));changed=True
    while changed:
        changed=False
        for i,(a,oa) in enumerate(segments):
            for j,(b,ob) in enumerate(segments[i+1:],i+1):
                shared=set(a)&set(b)
                if oa!=ob or not shared:continue
                c=next(iter(shared));ends=[q for q in a+b if q!=c]
                if len(ends)!=2:continue
                u,v=ends
                if abs((c[0]-u[0])*(v[1]-u[1])-(c[1]-u[1])*(v[0]-u[0]))>1e-6:continue
                segments.pop(j);segments.pop(i);segments.append((tuple(sorted(ends)),oa));changed=True;break
            if changed:break
    source=['plan "ANT refined OR-Tools study" {','units mm','grid 1',f'height {round(plan["brief"]["floor_height"]*1000)}','north up','scale 1:100 hidden','title hidden']
    for r in plan['rooms']:
        kind={'majlis':'living','bathroom':'bath','stair':'circulation'}.get(r['kind'],r['kind'])
        label=r.get('name',labels.get(r['id'],r['id'].replace('-',' ').title()));anchor=''
        if r['id']=='stair' and plan.get('stair_design'):
            label='Stair';landing=Polygon(plan['stair_design']['ground_landing']);p=landing.representative_point();anchor=' at '+point(transform((p.x,p.y)))
        source.append(f'room id={ids[r["id"]]} polygon '+ ' '.join(point(transform(q)) for q in r['polygon'])+f' label "{label}"{anchor} uses {kind}')
    walls=[]
    for i,(ends,owners) in enumerate(segments):
        wid='w_'+str(i);walls.append((wid,ends));source.append(f'wall id={wid} {"exterior" if len(owners)==1 else "partition"} thickness 200 {{ '+ ' '.join(point(q) for q in ends)+' }')
    def host(center):
        for wid,ends in walls:
            from shapely.geometry import LineString
            if LineString(ends).distance(Point(center))<1e-6:return wid
        raise ValueError('Opening has no host wall')
    for d in audit['doors']:
        center=transform(d['center']);double=d.get('double',False)
        if d.get('kind')=='opening':source.append(f'opening id={d["id"]} at {point(center)} width {round(d["width"]*1000)} wall {host(center)}')
        else:source.append(f'door id={d["id"]} {"double " if double else ""}at {point(center)} width {round(d["width"]*1000)} wall {host(center)} swing into {ids[d["receiving_room"]]}')
    for w in audit['windows']:
        center=transform(w['center']);source.append(f'window id={w["id"]} at {point(center)} width {round(w["width"]*1000)} wall {host(center)}')
    for i,platform in enumerate(audit['platforms']):
        for j,poly in enumerate(platform['surfaces']):source.append(f'outdoor id=platform_{i}_{j} paving polygon '+' '.join(point(transform(q)) for q in poly))
    for i,bay in enumerate(audit.get('parking_reservations',[])):source.append(f'outdoor id=parking_{i} driveway polygon '+' '.join(point(transform(q)) for q in bay['polygon'])+' label "Parking Reserve"')
    if plan.get('stair_design'):
        stair=plan['stair_design'];pieces=[]
        for kind,poly in [('flight',stair['flights'][0]),('landing',stair['turn_landing']),('flight',stair['flights'][1])]:
            points=[transform(q) for q in poly];xs=[q[0] for q in points];ys=[q[1] for q in points]
            pieces.append(f'{kind} at ({min(xs)},{min(ys)}) size {max(xs)-min(xs)}x{max(ys)-min(ys)}')
        source.append(f'stair id=core dir up width {round(stair["rules"]["drawn_flight_width_m"]*1000)} {{ '+' '.join(pieces)+' }')
    source.append('}')
    return '\n'.join(source)

if __name__=='__main__':
    path=Path(sys.argv[1]);plan=json.loads(path.read_text());audit=json.loads(path.with_name(path.stem+'_audit.json').read_text());path.with_suffix('.arch').write_text(produce(plan,audit));print(path.with_suffix('.arch').name)
