"""Close usable pockets that become sealed only after actual wall thickness is added."""
from shapely import set_precision
from shapely.geometry import Polygon
from shapely.ops import unary_union
def repair(ground):
    shapes={r['id']:set_precision(Polygon(r['polygon']),.001) for r in ground['rooms']};foot=unary_union(list(shapes.values()));physical=foot.buffer(.1,join_style='mitre');repairs=[]
    if physical.geom_type!='Polygon':return ground,repairs
    for ring in physical.interiors:
        clear=Polygon(ring)
        if clear.area<.01:continue
        pocket=set_precision(clear.buffer(.1,join_style='mitre'),.001).difference(foot)
        if pocket.area>ground['brief'].get('max_wall_pocket_repair_m2',4):raise ValueError('Wall-enclosed unassigned area exceeds bounded repair policy')
        options=[]
        for r in ground['rooms']:
            if r['kind'] in ['stair','hall','bedroom']:continue
            shared=shapes[r['id']].boundary.intersection(pocket.boundary).length
            expanded=shapes[r['id']].union(pocket)
            x0,y0,x1,y1=pocket.bounds
            required_contact=min(1,max(.2,min(x1-x0,y1-y0)))
            if shared<required_contact-1e-7 or expanded.geom_type!='Polygon' or expanded.interiors:continue
            priority=({'living':0,'kitchen':1,'dining':2,'storage':3,'bathroom':4,'majlis':5} if pocket.area>4 else {'storage':0,'bathroom':1,'living':2,'dining':3,'majlis':4,'kitchen':5}).get(r['kind'],9)
            options.append((priority,-shared,r,expanded))
        if not options:raise ValueError('Wall-enclosed pocket has no safe room assignment')
        _,_,r,expanded=min(options,key=lambda item:(item[0],item[1]));r['polygon']=list(expanded.exterior.coords)[:-1];shapes[r['id']]=expanded
        repairs.append({'room':r['id'],'added_centreline_area_m2':pocket.area,'sealed_clear_area_before_m2':clear.area,'polygon':list(pocket.exterior.coords)[:-1],'reason':'Wall thickness sealed a narrow exterior slot; assign the residual floor to an adjacent requested room, preserving its original core'})
        foot=unary_union(list(shapes.values()))
    return ground,repairs
