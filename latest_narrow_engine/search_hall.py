import json
from pathlib import Path
from pipeline import generate
ROOT=Path(__file__).parent
req=json.loads(Path('/workspace/ANT_SITE_SHAPE_TEST/narrow_deep/REQUEST.json').read_text())
req['id']='H';req['search_seed']=73;req['ground_seconds']=50
req['search_policy']={'relax_bbox_exterior':True,'local_exterior':True,'relax_north_living':True,'relax_men_position':True}
req['floors'][0]['rooms'].append({'id':'bedroom-hall','kind':'hall','min_area':6,'min_side':1.5,'max_length':8.2,'name':'Bedroom Hall','floor':0,'count':1})
req['family_rooms'].append('bedroom-hall')
edges=req['floors'][0]['required_edges']
for e in edges:
 if e==['living','elder'] or e==['living','bedroom_2']:e[0]='bedroom-hall'
edges.append(['living','bedroom-hall'])
print('START H bedroom circulation alternative',flush=True)
g=generate(req,ROOT/'H',seconds=45,render=False,first_feasible=True)
print('RESULT H',json.dumps(g),flush=True)
