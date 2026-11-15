"""Parametric two-flight U stair, explicitly conditional on structural assumptions."""
import math
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union

def requirements(brief):
    height=float(brief['floor_height']);n=math.ceil(height/.17);n+=n%2
    per_flight=n//2;going=.28;run=(per_flight-1)*going
    rules={'floor_height_m':height,'risers':n,'risers_per_flight':per_flight,'riser_m':height/n,'going_m':going,'goings_per_flight':per_flight-1,'flight_run_m':run,'clear_flight_width_m':1.2,'rail_intrusion_each_side_m':.05,'drawn_flight_width_m':1.3,'gap_m':.2,'turn_landing_depth_m':1.3,'ground_landing_depth_m':1.6,'opening_cutback_m':.3,'slab_assumed_m':.2,'upper_cover_underside_assumed_m':2*height-.2,'required_headroom_m':float(brief.get('stair_headroom',2.1)),'outer_wall_m':float(brief['wall_thickness'])}
    rules['comfort_2r_plus_g_m']=2*rules['riser_m']+going
    rules['pitch_deg']=math.degrees(math.atan(rules['riser_m']/going))
    rules['minimum_reserved_long_m']=math.ceil((1.6+run+1.3+rules['outer_wall_m']+.06)*10)/10
    rules['minimum_reserved_cross_m']=math.ceil((2*1.3+.2+rules['outer_wall_m']+.12)*10)/10
    return rules

def design(plan,audit):
    rules=requirements(plan['brief']);room=next(r for r in plan['rooms'] if r['id']=='stair');joining=next(d for d in audit['doors'] if 'stair' in d['connects'])
    x,y,w,h=(room[k] for k in ['x','y','width','depth']);cx,cy=joining['center'];t=rules['outer_wall_m'];long_axis='x' if w>h else 'y'
    if long_axis=='x':
        if abs(cx-x)<1e-6:entry='west';origin=(x+t/2,y+t/2);forward=(1,0)
        elif abs(cx-(x+w))<1e-6:entry='east';origin=(x+w-t/2,y+t/2);forward=(-1,0)
        else:raise ValueError('Stair entry must be on the short end, not halfway along a flight')
        across=(0,1);length=w-t;cross=h-t
    else:
        if abs(cy-y)<1e-6:entry='south';origin=(x+t/2,y+t/2);forward=(0,1)
        elif abs(cy-(y+h))<1e-6:entry='north';origin=(x+t/2,y+h-t/2);forward=(0,-1)
        else:raise ValueError('Stair entry must be on the short end')
        across=(1,0);length=h-t;cross=w-t
    total_cross=2*rules['drawn_flight_width_m']+rules['gap_m'];required_length=rules['ground_landing_depth_m']+rules['flight_run_m']+rules['turn_landing_depth_m']
    if length+1e-8<required_length or cross+1e-8<total_cross:raise ValueError('Stair flights and both landings do not fit the enclosure')
    margin=(cross-total_cross)/2;origin=(origin[0]+across[0]*margin,origin[1]+across[1]*margin)
    def world(u,v):return [round(origin[0]+forward[0]*u+across[0]*v,6),round(origin[1]+forward[1]*u+across[1]*v,6)]
    def rect(u0,v0,u1,v1):return [world(u0,v0),world(u1,v0),world(u1,v1),world(u0,v1)]
    start=rules['ground_landing_depth_m'];end=start+rules['flight_run_m'];fw=rules['drawn_flight_width_m'];second=fw+rules['gap_m']
    flights=[rect(start,0,end,fw),rect(start,second,end,second+fw)];turn=rect(end,0,end+rules['turn_landing_depth_m'],total_cross);bottom=rect(0,0,start,total_cross)
    # First-flight cutback avoids the slab edge sitting directly over its first riser.
    void=unary_union([Polygon(rect(start,0,end+rules['turn_landing_depth_m'],total_cross)),Polygon(rect(start-rules['opening_cutback_m'],0,start,second))])
    if void.geom_type!='Polygon':raise ValueError('Stair opening disconnected')
    tread_lines=[];riser_lines=[];walk=[]
    for i in range(rules['risers_per_flight']):
        u=start+i*rules['going_m'];z=(i+1)*rules['riser_m'];riser_lines.append({'flight':1,'riser':i+1,'z_m':z,'points':[world(u,0),world(u,fw)]})
    for i in range(rules['risers_per_flight']):
        u=end-i*rules['going_m'];z=(rules['risers_per_flight']+i+1)*rules['riser_m'];riser_lines.append({'flight':2,'riser':rules['risers_per_flight']+i+1,'z_m':z,'points':[world(u,second),world(u,second+fw)]})
    samples=[]
    # Evaluate step surfaces and the interpolated nosing line; cover/slab planes are assumptions.
    for u in [i*.02 for i in range(math.ceil(required_length/.02)+1)]:
        u=min(u,required_length)
        if u<start:samples.append({'point':world(u,fw/2),'z_m':0,'part':'ground_landing'})
        if start<=u<=end:
            q=(u-start)/rules['going_m'];z=min(rules['risers_per_flight']*rules['riser_m'],(q+1)*rules['riser_m']);samples.append({'point':world(u,fw/2),'z_m':z,'part':'flight_1_nosing'})
            q2=(end-u)/rules['going_m'];z2=min(rules['floor_height_m'],(rules['risers_per_flight']+q2+1)*rules['riser_m']);samples.append({'point':world(u,second+fw/2),'z_m':z2,'part':'flight_2_nosing'})
        if u>=end:samples.append({'point':world(u,total_cross/2),'z_m':rules['floor_height_m']/2,'part':'turn_landing'})
    # Upper arrival landing occupies the opposite flight's half plus the full front strip.
    upper_landing=unary_union([Polygon(rect(0,0,start-rules['opening_cutback_m'],total_cross)),Polygon(rect(start-rules['opening_cutback_m'],second,start,total_cross))])
    for p in [upper_landing.representative_point()]:samples.append({'point':[p.x,p.y],'z_m':rules['floor_height_m'],'part':'upper_landing'})
    result={'rules':rules,'entry_side':entry,'flights':flights,'turn_landing':turn,'ground_landing':bottom,'upper_landing':list(upper_landing.exterior.coords)[:-1],'upper_opening':list(void.exterior.coords)[:-1],'riser_lines':riser_lines,'headroom_samples':samples,'drawing_tread_intervals_per_flight':round(rules['flight_run_m']*1000/280),'enclosure_id':'stair','scope':'Geometric proposal; slab/upper-cover elevations assumed; upper-storey plan and structure not coordinated'}
    result['checks']=check(result,room,joining)
    if not result['checks']['pass']:raise ValueError('Stair geometric checks failed: '+str(result['checks']))
    return result

def check(stair,room,joining):
    r=stair['rules'];clear=box(room['x']+r['outer_wall_m']/2,room['y']+r['outer_wall_m']/2,room['x']+room['width']-r['outer_wall_m']/2,room['y']+room['depth']-r['outer_wall_m']/2)
    fit=all(clear.buffer(1e-7).covers(Polygon(p)) for p in stair['flights']+[stair['turn_landing'],stair['ground_landing']])
    opening=Polygon(stair['upper_opening']);values=[]
    for sample in stair['headroom_samples']:
        point=Point(sample['point']);z=sample['z_m']
        if sample['part']=='upper_landing':overhead=r['upper_cover_underside_assumed_m']
        else:overhead=r['upper_cover_underside_assumed_m'] if opening.buffer(1e-7).covers(point) else r['floor_height_m']-r['slab_assumed_m']
        values.append(overhead-z)
    minimum=min(values)
    ground=Polygon(stair['ground_landing']);landing_reached=ground.distance(Point(joining['center']))<=r['outer_wall_m']/2+1e-7
    checks={'fits':fit,'riser_sum_m':r['risers']*r['riser_m'],'rise_matches_floor':abs(r['risers']*r['riser_m']-r['floor_height_m'])<1e-9,'clear_flight_width_m':r['drawn_flight_width_m']-2*r['rail_intrusion_each_side_m'],'lower_landing_reached_from_opening':landing_reached,'minimum_modelled_headroom_m':minimum,'required_headroom_m':r['required_headroom_m'],'headroom_pass_under_assumptions':minimum>=r['required_headroom_m']-1e-8,'samples':len(values),'pass':False}
    checks['pass']=fit and checks['rise_matches_floor'] and landing_reached and checks['headroom_pass_under_assumptions'] and checks['clear_flight_width_m']>=1.2-1e-8
    return checks
