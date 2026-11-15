"""Variable upper-floor rooms and a family hub with up to four variable circulation arms."""
import math,time
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from ortools.sat.python import cp_model

def solve_upper(ground,request,seconds=35,hint=None,first_solution=False,max_arms=4):
    shapes={r['id']:Polygon(r['polygon']) for r in ground['rooms']};foot=unary_union(list(shapes.values()))
    stair=next(r for r in ground['rooms'] if r['id']=='stair')
    if ground['stair_design']['entry_side']!='north':raise ValueError('Current upper solver supports a north landing; other stair entry directions are explicitly unsupported')
    ox,oy=ground['origin'];scale=10
    def integer(value,origin=0):return round((value-origin)*scale)
    bx0,by0,bx1,by1=foot.bounds;W=math.floor((bx1-ox)*10+1e-6);H=math.floor((by1-oy)*10+1e-6)
    xs=sorted({0,W}|{n for poly in shapes.values() for x,y in poly.exterior.coords for n in [math.floor((x-ox)*10+1e-7),math.ceil((x-ox)*10-1e-7)]})
    ys=sorted({0,H}|{n for poly in shapes.values() for x,y in poly.exterior.coords for n in [math.floor((y-oy)*10+1e-7),math.ceil((y-oy)*10-1e-7)]})
    outside=[]
    for y0,y1 in zip(ys,ys[1:]):
        intervals=[]
        for x0,x1 in zip(xs,xs[1:]):
            cell=box(ox+x0/10,oy+y0/10,ox+x1/10,oy+y1/10)
            if not foot.buffer(1e-7).covers(cell):
                if intervals and intervals[-1][1]==x0:intervals[-1][1]=x1
                else:intervals.append([x0,x1])
        outside += [(x0,y0,x1-x0,y1-y0) for x0,x1 in intervals]
    sx=integer(stair['x'],ox);sy=integer(stair['y'],oy);sw=integer(stair['width']);sh=integer(stair['depth'])
    model=cp_model.CpModel();rects={};areas={};intervals={}
    def add(rid,pairs,fixed=None):
        if fixed is not None:
            x,y,w,h=fixed
            r={k:model.NewConstant(v) for k,v in [('x',x),('y',y),('w',w),('h',h),('r',x+w),('t',y+h)]};area=model.NewConstant(w*h)
        else:
            if not pairs:raise ValueError('No dimension pairs for '+rid)
            r={'x':model.NewIntVar(0,W,rid+'_x'),'y':model.NewIntVar(0,H,rid+'_y'),'w':model.NewIntVar(min(p[0] for p in pairs),max(p[0] for p in pairs),rid+'_w'),'h':model.NewIntVar(min(p[1] for p in pairs),max(p[1] for p in pairs),rid+'_h'),'r':model.NewIntVar(0,W,rid+'_r'),'t':model.NewIntVar(0,H,rid+'_t')}
            area=model.NewIntVar(min(w*h for w,h in pairs),max(w*h for w,h in pairs),rid+'_area')
            model.AddAllowedAssignments([r['w'],r['h'],area],[(w,h,w*h) for w,h in pairs]);model.Add(r['r']==r['x']+r['w']);model.Add(r['t']==r['y']+r['h']);model.Add(r['r']<=W);model.Add(r['t']<=H)
        rects[rid]=r;areas[rid]=area
        intervals[rid]=(model.NewIntervalVar(r['x'],r['w'],r['r'],rid+'_ix'),model.NewIntervalVar(r['y'],r['h'],r['t'],rid+'_iy'))
    add('stair',[],(sx,sy,sw,sh))
    for i,rect in enumerate(outside):add('_out_'+str(i),[],rect)
    expected=request['floors'][1]['rooms'];specs={r['id']:r for r in expected if r['id'] not in ['family','stair']}
    if len(specs)!=len(expected)-2 or not {'family','stair'}<={r['id'] for r in expected}:raise ValueError('Upper programme requires one family distributor and the existing stair')
    if len({r['id'] for r in expected})!=len(expected):raise ValueError('Duplicate room IDs')
    def pairs(kind,rid,spec):
        default=16 if rid=='master' else 12 if kind=='bedroom' else 4.5
        minimum=spec.get('min_area',default);side=spec.get('min_side',3 if kind=='bedroom' else 1.8)
        minimum_side=math.ceil((side+.2)*10-1e-7)
        return [(w,h) for w in range(minimum_side,min(W,70)+1) for h in range(minimum_side,min(H,60)+1) if minimum+.20<=(w/10-.2)*(h/10-.2)<=(max(minimum*1.6,minimum+2) if kind=='bedroom' else max(minimum*2.8,13)) and max(w,h)<=min(w,h)*(2.2 if rid=='master' else 2 if kind=='bedroom' else 2.7)]
    for rid,s in specs.items():
        if s['kind'] not in ['bedroom','bath']:raise ValueError('Unsupported upper room kind '+s['kind'])
        add(rid,pairs(s['kind'],rid,s))
    add('terrace',[(w,h) for w in range(24,min(W,65)+1) for h in range(24,min(H,60)+1) if 5.5<=(w/10-.2)*(h/10-.2)<=24 and max(w,h)<=min(w,h)*2.5])
    add('family',[(w,h) for w in range(40,min(W,90)+1) for h in range(32,min(H,65)+1) if 16<=(w/10-.2)*(h/10-.2)<=38])
    model.Add(rects['family']['y']==sy+sh)
    model.Add(rects['family']['x']<=sx+sw-16);model.Add(rects['family']['r']>=sx+16)
    arms=['arm'+str(i) for i in range(max_arms)]
    for rid in arms:add(rid,[(18,n) for n in range(20,H+1)]+[(n,18) for n in range(20,W+1)])
    fixed=['stair']+['_out_'+str(i) for i in range(len(outside))]
    occupied=list(specs)+['terrace']
    # Only the family arms may overlap the hub or each other.
    model.AddNoOverlap2D([intervals[k][0] for k in occupied+fixed+['family']],[intervals[k][1] for k in occupied+fixed+['family']])
    for arm in arms:model.AddNoOverlap2D([intervals[k][0] for k in occupied+fixed+[arm]],[intervals[k][1] for k in occupied+fixed+[arm]])
    def contact(a,b,span=13):
        a,b=rects[a],rects[b];choices=[model.NewBoolVar('contact') for _ in range(4)]
        for v,p,q in [(choices[0],a,b),(choices[1],b,a)]:
            model.Add(p['r']==q['x']).OnlyEnforceIf(v);model.Add(p['y']<=q['t']-span).OnlyEnforceIf(v);model.Add(q['y']<=p['t']-span).OnlyEnforceIf(v)
        for v,p,q in [(choices[2],a,b),(choices[3],b,a)]:
            model.Add(p['t']==q['y']).OnlyEnforceIf(v);model.Add(p['x']<=q['r']-span).OnlyEnforceIf(v);model.Add(q['x']<=p['r']-span).OnlyEnforceIf(v)
        return choices
    def overlap(a,b):
        a,b=rects[a],rects[b];v=model.NewBoolVar('family_join')
        for p,q in [(a,b),(b,a)]:model.Add(p['x']<=q['r']-18).OnlyEnforceIf(v);model.Add(p['y']<=q['t']-18).OnlyEnforceIf(v)
        return v
    for i,arm in enumerate(arms):model.AddBoolOr([overlap(arm,k) for k in ['family']+arms[:i]])
    for rid in occupied:
        if rid=='master_bath':model.AddBoolOr(contact(rid,'master',12))
        else:model.AddBoolOr(sum([contact(rid,k,20 if rid=='terrace' else 12 if specs.get(rid,{}).get('kind')=='bath' else 13) for k in ['family']+arms],[]))
    model.AddBoolOr(contact('terrace','master',13))
    # Wet rooms may use a lower wet/storage/entry zone; exact risers are independently checked later.
    wet=[r for r in ground['rooms'] if r['kind'] in ['bathroom','storage','hall']]
    for rid,s in specs.items():
        if s['kind']!='bath':continue
        choices=[];r=rects[rid]
        for lower in wet:
            x=integer(lower['x'],ox);y=integer(lower['y'],oy);right=integer(lower['x']+lower['width'],ox);top=integer(lower['y']+lower['depth'],oy)
            v=model.NewBoolVar('wet_overlap');choices.append(v)
            for lhs,rhs in [(r['x'],right-6),(r['y'],top-6)]:model.Add(lhs<=rhs).OnlyEnforceIf(v)
            model.Add(r['r']>=x+6).OnlyEnforceIf(v);model.Add(r['t']>=y+6).OnlyEnforceIf(v)
        model.AddBoolOr(choices)
    # Stable IDs only break symmetry between interchangeable client rooms; their positions remain variables.
    children=sorted(rid for rid in specs if rid.startswith('child_'))
    for a,b in zip(children,children[1:]):model.Add(rects[a]['x']+rects[a]['y']*W<=rects[b]['x']+rects[b]['y']*W)
    minx=model.NewIntVar(0,W,'minx');miny=model.NewIntVar(0,H,'miny');maxx=model.NewIntVar(0,W,'maxx');maxy=model.NewIntVar(0,H,'maxy')
    allkeys=occupied+['family','stair']+arms;model.AddMinEquality(minx,[rects[k]['x'] for k in allkeys]);model.AddMinEquality(miny,[rects[k]['y'] for k in allkeys]);model.AddMaxEquality(maxx,[rects[k]['r'] for k in allkeys]);model.AddMaxEquality(maxy,[rects[k]['t'] for k in allkeys])
    bw=model.NewIntVar(0,W,'bw');bh=model.NewIntVar(0,H,'bh');bbox=model.NewIntVar(0,W*H,'bbox');model.Add(bw==maxx-minx);model.Add(bh==maxy-miny);model.AddMultiplicationEquality(bbox,[bw,bh])
    model.Minimize(3*bbox+sum(areas[k] for k in occupied)+8*sum(areas[k] for k in ['family']+arms)+10*(bw+bh))
    if hint:
        for rid,values in hint.items():
            if rid not in rects:continue
            x,y,w,h=values
            for k,v in [('x',integer(x,ox)),('y',integer(y,oy)),('w',integer(w)),('h',integer(h))]:model.AddHint(rects[rid][k],v)
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=seconds;solver.parameters.num_search_workers=4;solver.parameters.random_seed=19;solver.parameters.stop_after_first_solution=first_solution
    status=solver.Solve(model);result={'status':solver.StatusName(status),'seconds':solver.WallTime(),'grid_m':.1,'solver':'OR-Tools CP-SAT','variable_room_ids':list(specs),'plot':[request['site']['width'],request['site']['depth']],'hint_is_not_a_constraint':bool(hint),'max_family_arms':max_arms}
    if status not in [cp_model.FEASIBLE,cp_model.OPTIMAL]:return result
    result['rectangles']={}
    for k in allkeys:
        r=rects[k];result['rectangles'][k]={'x':round(ox+solver.Value(r['x'])/10,3),'y':round(oy+solver.Value(r['y'])/10,3),'width':solver.Value(r['w'])/10,'depth':solver.Value(r['h'])/10}
    result['objective']=solver.ObjectiveValue();result['best_bound']=solver.BestObjectiveBound()
    return result
