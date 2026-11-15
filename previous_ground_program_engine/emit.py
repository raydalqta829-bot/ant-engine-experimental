"""Official ArchLang source emission from solved geometry; no hand-rendered plans."""
import json,sys
from pathlib import Path
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from to_arch import produce
def point(p):return f'({round(p[0]*1000)},{round(35000-p[1]*1000)})'
def column(c):
    x,y=c['center'];return f'column id={c["id"]} at {point((x-.15,y+.15))} size 300x300'
def shaft(s):
    x0,y0,x1,y1=Polygon(s['polygon']).bounds
    return f'void id={s["id"]} at {point((x0,y1))} size {round((x1-x0)*1000)}x{round((y1-y0)*1000)} rail none'
def emit(folder):
    q=json.loads((folder/'COORDINATION.json').read_text());ground=produce(q['ground'],q['ground_audit']);body=ground[ground.index('room id='):ground.rfind('}')]
    body+='\n'+'\n'.join(column(c) for c in q['columns'])+'\n'+'\n'.join(shaft(s) for s in q['shafts'])
    upper=[];shapes={r['id']:Polygon(r['polygon']) for r in q['upper_rooms']};shapes['TERRACE']=Polygon(q['terrace'])
    for r in q['upper_rooms']:
        poly=shapes[r['id']];anchor=''
        if r['id']=='stair':p=Polygon(q['ground']['stair_design']['upper_landing']).representative_point();anchor=' at '+point((p.x,p.y))
        upper.append(f'room id={r["id"]} polygon '+' '.join(point(p) for p in r['polygon'])+f' label "{r["label"]}"{anchor} uses {r["kind"]}')
    boundary=unary_union([p.boundary for p in shapes.values()]);segments=[]
    for line in boundary.geoms:
        coords=list(line.coords)
        for a,b in zip(coords,coords[1:]):
            mid=Point((a[0]+b[0])/2,(a[1]+b[1])/2);owners=frozenset(k for k,p in shapes.items() if p.boundary.distance(mid)<1e-7);segments.append((tuple(sorted((a,b))),owners))
    segments=list(dict.fromkeys(segments));change=True
    while change:
        change=False
        for i,(aa,oa) in enumerate(segments):
            for j,(bb,ob) in enumerate(segments[i+1:],i+1):
                shared=set(aa)&set(bb)
                if oa!=ob or not shared:continue
                c=next(iter(shared));ends=[p for p in aa+bb if p!=c]
                if len(ends)!=2:continue
                a,b=ends
                if abs((c[0]-a[0])*(b[1]-a[1])-(c[1]-a[1])*(b[0]-a[0]))>1e-7:continue
                segments.pop(j);segments.pop(i);segments.append((tuple(sorted(ends)),oa));change=True;break
            if change:break
    walls=[]
    for i,(ends,owners) in enumerate(segments):
        wid='uw_'+str(i);walls.append((wid,LineString(ends)));out=owners=={'TERRACE'}
        category='partition' if len(owners)==2 and 'TERRACE' not in owners else 'exterior'
        upper.append(f'wall id={wid} {category} thickness {150 if out else 200}'+(' height 1100' if out else '')+' { '+' '.join(point(p) for p in ends)+' }')
    def host(o):
        x,y=o['center'];h=o['width']/2
        line=LineString([(x-h,y),(x+h,y)]) if o['axis']=='x' else LineString([(x,y-h),(x,y+h)])
        for wid,wall in walls:
            if wall.buffer(1e-5).covers(line):return wid
        raise ValueError('Opening has no complete host '+o['id'])
    for o in q['upper_openings']:
        if o.get('kind')=='opening':text=f'opening id={o["id"]} at {point(o["center"])} width {round(o["width"]*1000)} wall {host(o)}'
        else:
            kind=o.get('kind','hinged');text=f'door id={o["id"]} {kind} at {point(o["center"])} width {round(o["width"]*1000)} wall {host(o)}'
            text+=' slide left' if kind=='glazed_sliding' else ' swing into '+o['receiving_room']
        upper.append(text)
    for o in q['upper_windows']:upper.append(f'window id={o["id"]} at {point(o["center"])} width {round(o["width"]*1000)} wall {host(o)}')
    upper.append('outdoor id=terrace deck polygon '+' '.join(point(p) for p in q['terrace'])+' label "Terrace"')
    upper.append(next(s for s in ground.splitlines() if s.startswith('stair id=core')).replace('dir up','dir down'))
    upper.append('void id=stair_void polygon '+' '.join(point(p) for p in q['ground']['stair_design']['upper_opening'])+' rail 0,1,2,3,4,5')
    upper.extend(shaft(s) for s in q['shafts']);upper.extend(column(c) for c in q['columns'] if c['continues_at_first_floor']);upper='\n'.join(upper)
    settings='units mm\ngrid 1\nnorth up\nsite { street south hemisphere north }\nscale 1:100 hidden\ntitle hidden\n'
    source='plan "Programme-driven villa study" {\n'+settings+'level 0 "Ground" height 3200 clear 3000 {\n'+body+'\n}\nlevel 1 "First" height 3200 slab 200 clear 3000 {\n'+upper+'\n}\nkeep stacked core on levels 0 1\n'+'\n'.join('keep stacked '+s['id']+' on levels 0 1' for s in q['shafts'])+'\n}'
    (folder/'VILLA.arch').write_text(source)
    for name,content in [('GROUND',body),('FIRST',upper)]: (folder/(name+'.arch')).write_text('plan "'+name+' - programme driven study" {\n'+settings+'height 3200\n'+content+'\n}')
if __name__=='__main__':emit(Path(sys.argv[1]))
