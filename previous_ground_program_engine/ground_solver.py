"""Independent CP-SAT research spike. Never imported by the production engine."""
import argparse
import json
import math
from pathlib import Path
from ortools.sat.python import cp_model
from stair import requirements

ROOT=Path(__file__).parent
FAMILIES={'living_hub':None}

def dimensions(room):
    minimum=math.ceil((room['min_side']+.2)*10-1e-8)
    maximum=math.ceil((max(room['min_side']*1.8,math.sqrt(room['min_area'])*1.55)+.2)*10)
    pairs=[]
    for w in range(minimum,maximum+1):
        for h in range(minimum,maximum+1):
            net=(w-2)*(h-2)
            if math.ceil(room['min_area']*100-1e-8)<=net<=math.floor((room['min_area']*1.6+1)*100) and max(w,h)<=min(w,h)*1.9:
                pairs.append((w,h,w*h))
    if not pairs:raise ValueError('No permitted room dimension pairs: '+room['id'])
    return pairs

def solve(brief,family,seconds=20,seed=19,privacy_entry=False,warm_hint=None):
    requested=brief['rooms']
    if len({r['id'] for r in requested})!=len(requested) or any(r.get('count',1)!=1 or r.get('floor',0)!=0 for r in requested):
        raise ValueError('Use unique, expanded ground-room instances; no counts silently ignored')
    if brief['entrance_face']!='south':raise ValueError('This spike assumes a south street; no automatic rotation.')
    model=cp_model.CpModel()
    max_w=math.floor((brief['plot_width']-brief['setbacks']['east']-brief['setbacks']['west']-.2)*10+1e-8)
    max_h=math.floor((brief['plot_depth']-brief['setbacks']['north']-brief['setbacks']['south']-.2)*10+1e-8)
    if min(max_w,max_h)<40:return {'status':'INFEASIBLE','family':family,'reason':'Insufficient buildable envelope'}
    bw=model.NewIntVar(40,max_w,'building_width');bh=model.NewIntVar(40,max_h,'building_depth')
    specs={r['id']:{'kind':r['kind'],'name':r['name'],'pairs':dimensions(r)} for r in requested}
    for r in brief['circulation_rooms']:
        if r['kind']=='stair':continue
        lo=math.ceil((r.get('min_side',2.4)+.2)*10)
        specs[r['id']]={'kind':'hall','name':r['name'],'pairs':[(w,h,w*h) for w in range(lo,43) for h in range(lo,43) if (w-2)*(h-2)>=r.get('min_area',6)*100]}
    specs['stair']={'kind':'stair','name':'Stair','pairs':[]}
    stair_rules=requirements(brief);long=round(stair_rules['minimum_reserved_long_m']*10);cross=round(stair_rules['minimum_reserved_cross_m']*10)
    specs['stair']['pairs']=[(c,l,c*l) for c,l in [(cross,long),(cross+2,long),(long,cross),(long,cross+2)]]
    rooms={};xi=[];yi=[]
    for rid,spec in specs.items():
        pairs=spec['pairs'];w=model.NewIntVar(min(p[0] for p in pairs),max(p[0] for p in pairs),rid+'_w');h=model.NewIntVar(min(p[1] for p in pairs),max(p[1] for p in pairs),rid+'_h');area=model.NewIntVar(min(p[2] for p in pairs),max(p[2] for p in pairs),rid+'_area')
        model.AddAllowedAssignments([w,h,area],pairs)
        x=model.NewIntVar(0,max_w,rid+'_x');y=model.NewIntVar(0,max_h,rid+'_y');right=model.NewIntVar(0,max_w,rid+'_right');top=model.NewIntVar(0,max_h,rid+'_top')
        model.Add(right==x+w);model.Add(top==y+h);model.Add(right<=bw);model.Add(top<=bh)
        xi.append(model.NewIntervalVar(x,w,right,rid+'_ix'));yi.append(model.NewIntervalVar(y,h,top,rid+'_iy'))
        rooms[rid]={'x':x,'y':y,'w':w,'h':h,'right':right,'top':top,'area':area}
    model.AddMinEquality(0,[r['x'] for r in rooms.values()]);model.AddMinEquality(0,[r['y'] for r in rooms.values()]);model.AddMaxEquality(bw,[r['right'] for r in rooms.values()]);model.AddMaxEquality(bh,[r['top'] for r in rooms.values()])
    edges=[tuple(e) for e in brief['connections']]
    if any(a not in rooms or b not in rooms for a,b in edges):raise ValueError('Requested connection references a missing room')
    for index,(a,b) in enumerate(edges):
        ra,rb=rooms[a],rooms[b];choices=[model.NewBoolVar(f'contact_{index}_{i}') for i in range(4)]
        model.AddExactlyOne(choices)
        if b=='stair':model.Add(choices[3]==1)
        elif a=='stair':model.Add(choices[2]==1)
        contact=18 if 'stair' in (a,b) else 15
        for choice,first,second in [(choices[0],ra,rb),(choices[1],rb,ra)]:
            model.Add(first['right']==second['x']).OnlyEnforceIf(choice)
            model.Add(first['y']<=second['top']-contact).OnlyEnforceIf(choice);model.Add(second['y']<=first['top']-contact).OnlyEnforceIf(choice)
            if 'stair' in (a,b):model.Add(rooms['stair']['w']>rooms['stair']['h']).OnlyEnforceIf(choice)
        for choice,first,second in [(choices[2],ra,rb),(choices[3],rb,ra)]:
            model.Add(first['top']==second['y']).OnlyEnforceIf(choice)
            model.Add(first['x']<=second['right']-contact).OnlyEnforceIf(choice);model.Add(second['x']<=first['right']-contact).OnlyEnforceIf(choice)
            if 'stair' in (a,b):model.Add(rooms['stair']['h']>rooms['stair']['w']).OnlyEnforceIf(choice)
    # Dedicated entrances, fixed street orientation. Coordinates remain solver variables.
    model.Add(rooms['main-foyer']['y']==0)
    if 'women-foyer' in rooms:model.Add(rooms['women-foyer']['right']==bw)
    # Family entry may be recessed. Reserve a genuinely unobstructed 1.8 m
    # outdoor approach from its south face to the front of the building.
    family_path_x=model.NewIntVar(0,max_w,'family_approach_x');family_path_end=model.NewIntVar(0,max_w,'family_approach_right')
    model.Add(2*family_path_x==2*rooms['family-foyer']['x']+rooms['family-foyer']['w']-18)
    model.Add(family_path_end==family_path_x+18)
    path_x=model.NewIntervalVar(family_path_x,18,family_path_end,'family_approach_ix')
    path_y=model.NewIntervalVar(0,rooms['family-foyer']['y'],rooms['family-foyer']['y'],'family_approach_iy')
    model.AddNoOverlap2D(xi+[path_x],yi+[path_y])
    if 'men' in rooms:
        model.Add(2*rooms['men']['y']<=bh);model.Add(2*rooms['men']['x']+rooms['men']['w']<=bw)
    if 'women' in rooms:
        model.Add(2*rooms['women']['y']<=bh);model.Add(2*rooms['women']['x']+rooms['women']['w']>=bw)
    # Every requested habitable/wet room gets an actual exterior wall; no invented lightwell.
    for rid in [r['id'] for r in requested if r['kind']!='storage']:
        r=rooms[rid];faces=[model.NewBoolVar(rid+'_exterior_'+str(i)) for i in range(6)]
        for c,lhs,rhs in [(faces[0],r['x'],0),(faces[1],r['y'],0),(faces[2],r['right'],bw),(faces[3],r['top'],bh)]:model.Add(lhs==rhs).OnlyEnforceIf(c)
        window_span=12 if specs[rid]['kind']=='bathroom' else 19 if rid=='arabic' else 28
        # The declared front-open approach is also exterior, not an enclosed shaft.
        for choice,lhs,rhs in [(faces[4],r['right'],family_path_x),(faces[5],r['x'],family_path_end)]:
            model.Add(lhs==rhs).OnlyEnforceIf(choice)
            model.Add(r['y']<=rooms['family-foyer']['y']-window_span).OnlyEnforceIf(choice)
            model.Add(r['top']>=window_span).OnlyEnforceIf(choice)
            model.Add(rooms['family-foyer']['y']>=window_span).OnlyEnforceIf(choice)
        model.AddBoolOr(faces)
    # These are explicit experimental architectural preferences, not customer mandates.
    if family=='living_hub':model.Add(rooms['living']['top']==bh)
    model.Add(10*bw<=18*bh);model.Add(10*bh<=18*bw)
    box_area=model.NewIntVar(0,max_w*max_h,'bbox_area');model.AddMultiplicationEquality(box_area,[bw,bh])
    gross=sum(r['area'] for r in rooms.values());model.Add(100*gross>=82*box_area)
    preference=rooms['living']['x'] if family=='family_hall' else bw-rooms['living']['right'] if family=='dining_hub' else 0
    model.Minimize(4*box_area+gross+20*(bw+bh)+5*preference)
    warm_start=False
    hint_path=ROOT/'living_hub_before_void_gate.json'
    if warm_hint is not None or hint_path.exists():
        hint=warm_hint if warm_hint is not None else json.loads(hint_path.read_text())
        if hint.get('rooms') and hint['width']*10<=max_w and hint['depth']*10<=max_h:
            warm_start=True
            for r in hint['rooms']:
                if r['id'] not in rooms:continue
                for k,value in [('x',(r['x']-hint['origin'][0])*10),('y',(r['y']-hint['origin'][1])*10),('w',r['width']*10),('h',r['depth']*10)]:model.AddHint(rooms[r['id']][k],round(value))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=seconds;solver.parameters.num_search_workers=4;solver.parameters.random_seed=seed;solver.parameters.log_search_progress=False;solver.parameters.stop_after_first_solution=True
    status=solver.Solve(model);name=solver.StatusName(status)
    result={'status':name,'family':family,'seconds':solver.WallTime(),'branches':solver.NumBranches(),'conflicts':solver.NumConflicts(),'best_bound':solver.BestObjectiveBound(),'solver_version':'9.14.6206','grid_m':.1,'street':'south','requested_room_count':len(requested),'variable_room_ids':list(specs),'warm_start':warm_start,'larger_privacy_entries':privacy_entry,'model_scope':'Request-defined ground room graph; south street and north stair entry; limited architectural topology.'}
    if status not in [cp_model.OPTIMAL,cp_model.FEASIBLE]:return result
    ox=brief['setbacks']['west']+.1;oy=brief['setbacks']['south']+.1
    result.update({'width':solver.Value(bw)/10,'depth':solver.Value(bh)/10,'origin':[ox,oy],'objective':solver.ObjectiveValue(),'rooms':[],'connections':[list(e) for e in edges],'stair_rules':stair_rules,'entry_rooms':brief['entry_rooms'],'family_approach':{'x':ox+solver.Value(family_path_x)/10,'y':oy,'width':1.8,'depth':solver.Value(rooms['family-foyer']['y'])/10},'brief':brief})
    for rid,r in rooms.items():
        result['rooms'].append({'id':rid,'kind':specs[rid]['kind'],'name':specs[rid]['name'],'x':round(ox+solver.Value(r['x'])/10,3),'y':round(oy+solver.Value(r['y'])/10,3),'width':solver.Value(r['w'])/10,'depth':solver.Value(r['h'])/10})
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--family',choices=list(FAMILIES),required=True);parser.add_argument('--seconds',type=float,default=20);parser.add_argument('--brief',default=str(ROOT/'BRIEF.json'));parser.add_argument('--out');parser.add_argument('--privacy-entry',action='store_true');args=parser.parse_args()
    result=solve(json.loads(Path(args.brief).read_text()),args.family,args.seconds,privacy_entry=args.privacy_entry)
    out=Path(args.out) if args.out else ROOT/(args.family+'.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ['brief','rooms','connections','entry_rooms']},ensure_ascii=False),flush=True)
