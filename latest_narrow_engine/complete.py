"""Assign enclosed residual pockets to touching rooms, keeping all room cores."""
import json
from pathlib import Path
from ortools.sat.python import cp_model
from shapely.geometry import box,Polygon
from shapely.ops import unary_union

def complete(plan):
    if plan.get('status') not in ['OPTIMAL','FEASIBLE']:return plan
    shapes={r['id']:box(r['x'],r['y'],round(r['x']+r['width'],3),round(r['y']+r['depth'],3)) for r in plan['rooms']}
    union=unary_union(list(shapes.values()))
    if union.geom_type!='Polygon':raise ValueError('Disconnected floorplate cannot be completed automatically')
    holes=[Polygon(ring) for ring in union.interiors if Polygon(ring).area>1e-7]
    model=cp_model.CpModel();choices=[];objective=[]
    for i,hole in enumerate(holes):
        options=[]
        for room in plan['rooms']:
            rid=room['id'];shared=hole.boundary.intersection(shapes[rid].boundary).length
            if room['kind']=='stair':continue
            if shared<.2:continue
            merged=shapes[rid].union(hole)
            if merged.geom_type!='Polygon' or merged.buffer(-.1,join_style='mitre').geom_type!='Polygon':continue
            useful_width=1.5 if room['kind']=='hall' else .8
            opened=merged.buffer(-(.1+useful_width/2),join_style='mitre').buffer(.1+useful_width/2,join_style='mitre')
            x0,y0,x1,y1=hole.bounds
            wall_slit=hole.area<=.3 and min(x1-x0,y1-y0)<=plan['brief']['wall_thickness']+1e-7
            if hole.intersection(opened).area<hole.area*.9 and not wall_slit:continue
            choice=model.NewBoolVar(f'void_{i}_to_{rid}');options.append(choice);choices.append((i,rid,choice))
            preference={'storage':0,'kitchen':1,'hall':2,'bathroom':3,'living':4,'dining':5,'bedroom':6,'majlis':7,'stair':12}.get(room['kind'],9)
            extra_corners=max(0,len(merged.simplify(0).exterior.coords)-len(shapes[rid].simplify(0).exterior.coords))
            added_perimeter=max(0,merged.length-shapes[rid].length)
            objective.append(choice*(extra_corners*10000+round(added_perimeter*1000)+preference*100+round(100/shared)))
        if not options:raise ValueError('An enclosed void has no safe room assignment')
        model.AddExactlyOne(options)
    assignments=[]
    if holes:
        model.Minimize(sum(objective));solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=3;solver.parameters.num_search_workers=1
        status=solver.Solve(model)
        if status not in [cp_model.FEASIBLE,cp_model.OPTIMAL]:raise ValueError('Void assignment failed')
        for i,rid,choice in choices:
            if solver.Value(choice):shapes[rid]=shapes[rid].union(holes[i]);assignments.append({'room':rid,'added_area_m2':holes[i].area,'polygon':list(holes[i].exterior.coords)[:-1]})
    for room in plan['rooms']:
        poly=shapes[room['id']]
        if poly.geom_type!='Polygon' or poly.interiors:raise ValueError('Invalid completed room')
        room['polygon']=[[round(x,3),round(y,3)] for x,y in list(poly.exterior.coords)[:-1]]
        room['core']={key:room[key] for key in ['x','y','width','depth']}
    plan['completion']={'method':'Second CP-SAT assignment of residual enclosed voids to touching rooms; original clear rectangular cores remain','assigned_voids':assignments,'no_coordinate_changes_to_cores':True}
    return plan

if __name__=='__main__':
    import sys
    path=Path(sys.argv[1]);result=complete(json.loads(path.read_text()));output=path.with_name(path.stem+'_completed.json');output.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(output.name,'assigned',len(result.get('completion',{}).get('assigned_voids',[])),'voids')
