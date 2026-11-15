"""Bounded floorplate stitching for upper circulation, with a full lower-floor re-audit."""
import copy
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from audit import audit
from privacy import optimize
from stair import design

def stitch(ground,previous_audit,request):
    p=copy.deepcopy(ground);living=next(r for r in p['rooms'] if r['id']=='living');base=Polygon(living['polygon']);foot=unary_union([Polygon(r['polygon']) for r in p['rooms']]);candidates=[]
    for r in p['rooms']:
        if r['id'] in ['living','stair'] or r['kind'] not in ['kitchen','dining','storage']:continue
        other=Polygon(r['polygon']);a,b,c,d=base.bounds;x,y,z,t=other.bounds
        if .05<a-z<=2 and min(d,t)-max(b,y)>=1.8:
            bottom=max(b,y);candidates.append((r['id'],box(z,bottom,a,round(bottom+1.8,3))))
        if .05<x-c<=2 and min(d,t)-max(b,y)>=1.8:
            bottom=max(b,y);candidates.append((r['id'],box(c,bottom,x,round(bottom+1.8,3))))
        if .05<b-t<=2 and min(c,z)-max(a,x)>=1.8:
            left=max(a,x);candidates.append((r['id'],box(left,t,round(left+1.8,3),b)))
        if .05<y-d<=2 and min(c,z)-max(a,x)>=1.8:
            left=max(a,x);candidates.append((r['id'],box(left,d,round(left+1.8,3),y)))
    site=request['site'];s=site['setbacks'];legal=box(s['west'],s['south'],site['width']-s['east'],site['depth']-s['north']);path=p['family_approach'];approach=box(path['x'],path['y'],path['x']+path['width'],path['y']+path['depth'])
    for other,bridge in sorted(candidates,key=lambda item:item[1].area):
        if bridge.area>4 or bridge.intersection(foot).area>1e-7 or bridge.intersection(approach).area>1e-7:continue
        if not legal.buffer(1e-7).covers(bridge.buffer(.1,join_style='mitre')):continue
        expanded=base.union(bridge)
        if expanded.geom_type!='Polygon' or expanded.interiors:continue
        living['polygon']=list(expanded.exterior.coords)[:-1]
        a=audit(p)
        if not a['accepted']:living['polygon']=list(base.exterior.coords)[:-1];continue
        for door in a['doors']:
            if 'stair' in door['connects']:door['kind']='opening';door['width']=1.2
        a,privacy=optimize(p,a)
        if not privacy['gate_pass']:living['polygon']=list(base.exterior.coords)[:-1];continue
        p['stair_design']=design(p,a);a['refinement_gate']=True
        return p,a,{'applied':True,'added_gross_area_m2':bridge.area,'polygon':list(bridge.exterior.coords)[:-1],'near_room':other,'assignment':'living','reason':'Close an unbuilt gap to provide a 1.8 m wide upper-floor circulation bridge, without removing requested rooms or changing their original clear cores','privacy':privacy}
    return ground,previous_audit,{'applied':False,'added_gross_area_m2':0}
