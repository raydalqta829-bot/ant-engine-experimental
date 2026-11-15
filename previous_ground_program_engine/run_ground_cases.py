import json,traceback
from pathlib import Path
from run import prepare_ground
ROOT=Path(__file__).parent
for f in sorted((ROOT/'cases').iterdir()):
    if (f/'GROUND.json').exists():continue
    try:
        request=json.loads((f/'REQUEST.json').read_text());p,a,provenance=prepare_ground(request)
        for n,data in [('GROUND.json',p),('GROUND_audit.json',a),('GROUND_PROVENANCE.json',provenance)]: (f/n).write_text(json.dumps(data,indent=2))
        (f/'GROUND_REJECTED.json').unlink(missing_ok=True)
        print(f.name,'GROUND_PASS',len(p['rooms']),a['gross_area_m2'],flush=True)
    except Exception as e:
        (f/'GROUND_REJECTED.json').write_text(json.dumps({'accepted':False,'reason':str(e)},indent=2));print(f.name,'REJECTED',str(e)[:350],flush=True)
