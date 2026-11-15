"""One brief -> solve -> coordinate -> compile -> contract gate -> render, or reject."""
import argparse,json,subprocess,shutil
from pathlib import Path
from run import prepare_ground,initial_hint
from upper_solver import solve_upper
from coordinate import coordinate
from emit import emit
from contract import validate
ROOT=Path(__file__).parent

def generate(request,out,seconds=35,render=True,first_feasible=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    # No stale drawing may survive a changed or rejected request.
    for p in out.iterdir():
        if p.is_file() and (p.suffix in ['.arch','.svg','.png','.pdf','.dxf'] or p.name in ['COORDINATION.json','ACCEPTANCE.json','REJECTED.json','VILLA_FACTS.json']):p.unlink()
    (out/'REQUEST.json').write_text(json.dumps(request,indent=2))
    try:
        ground,a,provenance=prepare_ground(request,trace_dir=out)
        for name,data in [('GROUND.json',ground),('GROUND_audit.json',a),('GROUND_PROVENANCE.json',provenance)]: (out/name).write_text(json.dumps(data,indent=2))
        hint=initial_hint(ground,request);(out/'SEARCH_HINT.json').write_text(json.dumps(hint,indent=2))
        result=solve_upper(ground,request,seconds,hint,first_solution=first_feasible);(out/'SOLVER.json').write_text(json.dumps(result,indent=2))
        if result['status'] not in ['FEASIBLE','OPTIMAL']:raise ValueError('Upper search returned '+result['status']+'; no fallback drawing')
        q=coordinate(out);emit(out)
        cli=ROOT/'node_modules/@chanmeng666/archlang/dist/cli.js'
        validation=subprocess.run(['node',str(cli),'validate',str(out/'VILLA.arch'),'--strict','--json'],capture_output=True,text=True,check=False)
        diagnosis=json.loads(validation.stdout);(out/'VALIDATION_STRICT.json').write_text(json.dumps(diagnosis,indent=2))
        if any(d['severity']=='error' for d in diagnosis.get('diagnostics',[])):raise ValueError('Compiler error; see VALIDATION_STRICT.json')
        allowed={'W_ROOM_NO_FIXTURE','W_ROOM_NOT_EQUATOR_FACING','W_ANNOTATION_OVERLAP','W_HABITABLE_NO_WINDOW'}
        if any(d['code'] not in allowed for d in diagnosis.get('diagnostics',[]) if d['severity']=='warning'):raise ValueError('Unreviewed compiler warning; no export')
        if any(d['code']=='W_HABITABLE_NO_WINDOW' for d in diagnosis.get('diagnostics',[])) and not any(d.get('kind')=='glazed_sliding' and d['connects']==['family','OUTSIDE'] for d in q['upper_openings']):raise ValueError('No modelled external light opening for family lounge')
        subprocess.run(['node',str(cli),'compile',str(out/'VILLA.arch'),'-f','json','-o',str(out/'VILLA_PLAN.json'),'--json'],capture_output=True,text=True,check=True)
        gc={c['id']:c for c in json.loads((out/'VILLA_PLAN.L0.json').read_text())['columns']}
        uc=json.loads((out/'VILLA_PLAN.L1.json').read_text())['columns']
        if any(c['id'] not in gc or any(c[k]!=gc[c['id']][k] for k in ['x','y','width','height']) for c in uc):raise ValueError('An upper column does not match its lower support')
        if render:subprocess.run(['node',str(ROOT/'render_multi.mjs')],cwd=out,check=True,capture_output=True,text=True)
        else:subprocess.run(['node',str(ROOT/'inspect.mjs'),str(out/'VILLA.arch')],cwd=ROOT,check=True,capture_output=True,text=True)
        facts_path=out/('VILLA_FACTS.json' if render else 'COMPILER_FACTS.json');gate=validate(q,request,json.loads(facts_path.read_text()))
        if not gate['accepted']:raise ValueError(str(gate))
        gate.update({'accepted_warning_codes':sorted({d['code'] for d in diagnosis.get('diagnostics',[]) if d['severity']=='warning'}),'strict_without_exceptions':diagnosis['ok'],'structural_design_approved':False})
        (out/'ACCEPTANCE.json').write_text(json.dumps(gate,indent=2));return gate
    except Exception as e:
        for p in out.iterdir():
            if p.is_file() and p.suffix in ['.arch','.svg','.png','.pdf','.dxf']:p.unlink()
        rejection={'accepted':False,'reason':str(e),'impossibility_proven':False,'no_fallback_drawing':True}
        (out/'REJECTED.json').write_text(json.dumps(rejection,indent=2));return rejection

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--out',required=True);p.add_argument('--seconds',type=float,default=35);p.add_argument('--no-render',action='store_true');args=p.parse_args()
    request=json.loads(Path(args.request).read_text());print(json.dumps(generate(request,Path(args.out).resolve(),args.seconds,not args.no_render),indent=2))
