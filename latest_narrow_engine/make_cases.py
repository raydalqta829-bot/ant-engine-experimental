"""Three declared architectural benchmark programmes; no placement coordinates."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).parent
def room(rid,kind,area,side,name,**extra):return {'id':rid,'kind':kind,'min_area':area,'min_side':side,'name':name,'count':1,'floor':0,**extra}
small=[room('men','majlis',25,4,'Men Majlis'),room('men-wc','bathroom',5,1.8,'Guest WC'),room('living','living',24,4.5,'Family Living'),room('dining','dining',16,3.5,'Family Dining'),room('kitchen','kitchen',16,3.5,'Kitchen'),room('store','storage',4,1.5,'Store'),room('elder','bedroom',16,3.5,'Ground Bedroom 1'),room('elder-bath','bathroom',5,1.8,'Ensuite 1',ensuite_of='elder')]
medium=copy.deepcopy(small)+[room('bedroom_2','bedroom',14,3.5,'Ground Bedroom 2'),room('family-bath','bathroom',5,1.8,'Family Bath')]
large=[room('men','majlis',45,5.5,'Men Majlis'),room('arabic','dining',18,3.5,'Guest Dining'),room('women','majlis',32,4.5,'Women Majlis'),room('living','living',25,5,'Family Living'),room('dining','dining',26.8,4,'Family Dining'),room('kitchen','kitchen',20,4,'Kitchen'),room('store','storage',5,1.5,'Store'),room('men-wc','bathroom',7,2,'Men WC'),room('women-wc','bathroom',7,2,'Women WC'),room('elder','bedroom',16,3.5,'Ground Bedroom 1'),room('elder-bath','bathroom',7,2,'Ensuite 1',ensuite_of='elder')]
upper_template=json.loads((ROOT/'UPPER_REFERENCE_PROGRAM.json').read_text())
for name,programme in [('compact_one_bedroom',small),('family_two_bedrooms',medium),('expanded_hospitality',large)]:
    ids={r['id'] for r in programme};circulation=[room('main-foyer','hall',7,2.8,'Main Entry'),room('family-foyer','hall',6.5,2.4,'Family Entry'),room('stair','stair',0,0,'Stair')]
    edges=[['main-foyer','men'],['main-foyer','men-wc'],['family-foyer','living'],['living','dining'],['living','stair'],['dining','kitchen'],['kitchen','store']]
    guests=[{'id':'men','entry':'main-foyer','rooms':['main-foyer','men','men-wc']}]
    entries=[{'room':'main-foyer','face':'south','width':2},{'room':'family-foyer','face':'south','width':1}];entry_rooms={'men':'main-foyer','family':'family-foyer'}
    if 'arabic' in ids:edges+=[['main-foyer','arabic'],['arabic','dining']];guests[0]['rooms'].append('arabic')
    else:edges.append(['main-foyer','dining'])
    if 'women' in ids:
        circulation.append(room('women-foyer','hall',8,3,'Women Entry'));edges+=[['women-foyer','women'],['women-foyer','women-wc'],['living','women']]
        guests.append({'id':'women','entry':'women-foyer','rooms':['women-foyer','women','women-wc']});entries.append({'room':'women-foyer','face':'east','width':1});entry_rooms['women']='women-foyer'
    for r in programme:
        if r['kind']=='bedroom':edges.append(['living',r['id']])
        if r.get('ensuite_of'):edges.append([r['ensuite_of'],r['id']])
    if 'family-bath' in ids:edges.append(['family-foyer','family-bath'])
    excluded={rid for g in guests for rid in g['rooms']};allrooms=programme+circulation
    req={'id':name,'site':{'width':30,'depth':35,'street':'south','setbacks':{'north':3,'south':3,'east':3,'west':3}},'floors':[{'level':0,'rooms':allrooms,'required_edges':edges},copy.deepcopy(upper_template)],'entries':entries,'entry_rooms':entry_rooms,'guest_groups':guests,'family_rooms':[r['id'] for r in allrooms if r['id'] not in excluded],'privacy_guest_room_ids':[r['id'] for r in programme if r['id'] in excluded and r['kind'] in ['majlis','dining']],'benchmark_note':'Engineering test assumptions; same plot and same upper programme in all three cases, not a new client commission'}
    folder=ROOT/'cases'/name;folder.mkdir(parents=True,exist_ok=True);(folder/'REQUEST.json').write_text(json.dumps(req,indent=2))
    print(name,len(programme),'requested functions',sum(r['kind']=='bedroom' for r in programme),'ground bedrooms',len(entries),'entries')
