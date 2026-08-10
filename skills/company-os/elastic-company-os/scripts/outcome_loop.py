#!/usr/bin/env python3
"""Deterministic closed loop outcome runtime for Company OS."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Callable

REQUEST_SCHEMA='company-os.outcome-loop-request.v1'; STATE_SCHEMA='company-os.outcome-loop-state.v1'
CONTROL_SCHEMA='company-os.outcome-control-state.v1'; CANDIDATE_SCHEMA='company-os.outcome-candidate.v1'
OUTCOME_SCHEMA='company-os.outcome-contract.v1'; ARTIFACT_SCHEMA='company-os.artifact-observation-contract.v1'; EVALUATOR_SCHEMA='company-os.evaluator-runtime-contract.v1'; BENCHMARK_SCHEMA='company-os.benchmark-contract.v1'
BATCH_SCHEMA='company-os.outcome-evaluation-batch.v1'; EVALUATION_BATCH_SCHEMA=BATCH_SCHEMA; REALITY_SCHEMA='company-os.reality-acceptance-receipt.v1'
DEFAULT_POLICY={'default_min_score':8.5,'critical_min_score':9.0,'dimension_minimums':{},'critical_dimensions':[],
'blocking_finding_severities':['critical','error'],'max_iterations':12,'max_focus_dimensions':2,'min_improvement':0.25,'stagnation_window':2}
AUTO_CRITICAL={'security','safety','correctness','authority','durability','cancellation','evidence_integrity','data_integrity'}
_EXEC=None; _REALITY=None

class OutcomeLoopError(ValueError):
 def __init__(self,code,msg): self.code=code; self.message=msg; super().__init__(f'{code}: {msg}')
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(v): return hashlib.sha256(canonical(v)).hexdigest()
def file_digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def text(v,l):
 if not isinstance(v,str) or not v.strip() or '\x00' in v: raise OutcomeLoopError('E_SCHEMA',f'{l} must be nonempty')
 return v
def obj(v,l):
 if not isinstance(v,Mapping): raise OutcomeLoopError('E_SCHEMA',f'{l} must be an object')
 return v
def sha(v,l):
 v=text(v,l)
 if len(v)!=64 or any(c not in '0123456789abcdef' for c in v): raise OutcomeLoopError('E_SCHEMA',f'{l} must be sha256')
 return v
def safe(project,v,l):
 raw=text(v,l); pure=PurePosixPath(raw)
 if '\\' in raw or pure.is_absolute() or not pure.parts or any(x in {'','.','..'} for x in pure.parts): raise OutcomeLoopError('E_PATH',f'{l} is unsafe')
 root=project.resolve(); cur=root
 for part in pure.parts:
  cur/=part
  if cur.is_symlink(): raise OutcomeLoopError('E_PATH',f'{l} traverses symlink')
 try: p=(root/Path(*pure.parts)).resolve(strict=True)
 except OSError as e: raise OutcomeLoopError('E_PATH',f'{l} missing') from e
 if root!=p and root not in p.parents or not p.is_file() or p.is_symlink(): raise OutcomeLoopError('E_PATH',f'{l} invalid')
 return p,pure.as_posix()
def read(p,l):
 try: return json.loads(p.read_text())
 except Exception as e: raise OutcomeLoopError('E_JSON',f'invalid {l}') from e
def seal(v): v=dict(v); v['state_sha256']=digest({**v,'state_sha256':None}); return v
def verify_state(raw):
 v=dict(obj(raw,'state'))
 if v.get('$schema')!=STATE_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad state schema')
 observed=sha(v.get('state_sha256'),'state_sha256')
 if observed!=digest({**v,'state_sha256':None}): raise OutcomeLoopError('E_DIGEST','state changed')
 return v
def module(relative,name):
 path=Path(__file__).resolve().parents[2]/relative
 spec=importlib.util.spec_from_file_location(name,path)
 if not spec or not spec.loader: raise OutcomeLoopError('E_RUNTIME',f'cannot load {name}')
 m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def execution_module():
 global _EXEC
 if _EXEC is None: _EXEC=module('execute-outcome-evaluator/scripts/execute_evaluator.py','company_os_eval_exec')
 return _EXEC
def reality_module():
 global _REALITY
 if _REALITY is None: _REALITY=module('accept-outcome-reality/scripts/accept_reality.py','company_os_reality')
 return _REALITY

def policy(raw=None):
 raw=dict(obj(raw or {},'quality_policy')); out={**DEFAULT_POLICY,**raw}
 if set(raw)-set(DEFAULT_POLICY): raise OutcomeLoopError('E_SCHEMA','unknown quality policy field')
 for k in ('default_min_score','critical_min_score','min_improvement'):
  x=out[k]
  if not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(float(x)) or float(x)<0: raise OutcomeLoopError('E_SCHEMA',f'{k} invalid')
  out[k]=float(x)
 for k in ('max_iterations','max_focus_dimensions','stagnation_window'):
  if not isinstance(out[k],int) or isinstance(out[k],bool) or out[k]<1: raise OutcomeLoopError('E_SCHEMA',f'{k} invalid')
 out['dimension_minimums']={str(k):float(v) for k,v in obj(out['dimension_minimums'],'dimension_minimums').items()}
 out['critical_dimensions']=sorted(set(out['critical_dimensions'])); out['blocking_finding_severities']=sorted(set(out['blocking_finding_severities']))
 return out

def start(req):
 if req.get('$schema')!=REQUEST_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad request schema')
 oid=text(req.get('objective_id'),'objective_id'); original=text(req.get('original_objective'),'original_objective')
 return seal({'$schema':STATE_SCHEMA,'schema_version':1,'objective_id':oid,'original_objective':original,'quality_policy':policy(req.get('quality_policy')),
 'phase':'discovery','iteration':0,'control_state':None,'required_artifact_classes':[],'required_evaluators':[],'organization_plan':None,
 'candidates':[],'evaluations':[],'diagnoses':[],'interventions':[],'acceptance':None,'history':[],
 'next_action':{'action':'compile_outcome_contract','authority':'discovery','instruction':'Research unknowns until success, artifacts, evaluators, benchmarks, and reality acceptance are measurable.'},'state_sha256':None})

def load_contract(project,binding,label):
 p,rel=safe(project,binding.get('path'),label); v=dict(obj(read(p,label),label)); field=next((x for x in ('contract_sha256','authorization_sha256') if x in v),None)
 if field:
  observed=sha(v[field],f'{label}.{field}'); candidate={**v,field:None}
  if digest(candidate)!=observed: raise OutcomeLoopError('E_DIGEST',f'{label} self digest changed')
 if binding.get('file_sha256')!=file_digest(p): raise OutcomeLoopError('E_DIGEST',f'{label} file changed')
 return v,rel

def bind_control(project,raw_state,control):
 state=verify_state(raw_state)
 if state['phase']!='discovery': raise OutcomeLoopError('E_PHASE','control can only bind from discovery')
 if control.get('$schema')!=CONTROL_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad control schema')
 observed=sha(control.get('state_sha256'),'control.state_sha256')
 if observed!=digest({**control,'state_sha256':None}): raise OutcomeLoopError('E_DIGEST','control state changed')
 if control.get('objective_id')!=state['objective_id'] or control.get('original_objective')!=state['original_objective']: raise OutcomeLoopError('E_BINDING','control does not bind original objective')
 artifacts,_=load_contract(project,obj(control.get('artifacts'),'control.artifacts'),'artifact contract')
 evaluators,_=load_contract(project,obj(control.get('evaluators'),'control.evaluators'),'evaluator contract')
 outcome,_=load_contract(project,obj(control.get('outcome'),'control.outcome'),'outcome contract')
 required_artifacts=sorted({text(x.get('artifact_class_id'),'artifact_class_id') for x in artifacts.get('artifact_classes',[]) if isinstance(x,Mapping) and x.get('required') is True})
 required_evaluators=[]
 for x in evaluators.get('evaluators',[]):
  if isinstance(x,Mapping) and x.get('required') is True:
   required_evaluators.append({'evaluator_id':text(x.get('evaluator_id'),'evaluator_id'),'artifact_classes':sorted(x.get('artifact_classes',[])),'score_dimensions':sorted(x.get('score_dimensions',[]))})
 if not required_artifacts or not required_evaluators: raise OutcomeLoopError('E_CONTROL','real artifacts and evaluators are required')
 org={'mode':'initial_pilot','manager_lanes':[{'lane_id':'manager:outcome','role':'outcome_manager','mandate':'Own one real candidate through independent evaluation.'}],
 'production_lanes':[{'lane_id':f'artifact:{a}','role':'artifact_specialist','artifact_class_id':a,'artifact_classes':[a]} for a in required_artifacts],
 'evaluation_lanes':[{'lane_id':f'evaluator:{e["evaluator_id"]}','role':'independent_evaluator','evaluator_id':e['evaluator_id'],'artifact_classes':e['artifact_classes'],'score_dimensions':e['score_dimensions'],'mandate':f'Independently evaluate the current candidate with {e["evaluator_id"]} against the bound artifact evidence and benchmarks.'} for e in required_evaluators],
 'specialist_lanes':[{'lane_id':f'artifact:{a}','role':'artifact_specialist','artifact_classes':[a]} for a in required_artifacts],
 'independent_evaluators':[{'lane_id':f'evaluator:{e["evaluator_id"]}','role':'independent_evaluator','evaluator_id':e['evaluator_id'],'artifact_classes':e['artifact_classes'],'score_dimensions':e['score_dimensions']} for e in required_evaluators],
 'instruction':'Use the smallest team that can materialize a real candidate. Do not expand concurrency before evaluation.'}
 next_state={**state,'phase':'build_candidate','control_state':{'state_sha256':observed,'outcome':dict(control['outcome']),'artifacts':dict(control['artifacts']),'evaluators':dict(control['evaluators']),'benchmarks':dict(control['benchmarks']),'calibrations':dict(control['calibrations'])},'outcome_claims':[dict(x) for x in outcome.get('outcome_claims',[]) if isinstance(x,Mapping)],'required_artifact_classes':required_artifacts,'required_evaluators':required_evaluators,'organization_plan':org,
 'next_action':{'action':'materialize_candidate','authority':'bounded_pilot','required_artifact_classes':required_artifacts,'organization_plan':org}}
 return seal(next_state)

def record_candidate(project,raw_state,candidate):
 state=verify_state(raw_state)
 if state['phase'] not in {'build_candidate','rework'}: raise OutcomeLoopError('E_PHASE','candidate not expected')
 if state['iteration']>=state['quality_policy']['max_iterations']: raise OutcomeLoopError('E_ITERATIONS','autonomous iteration budget exhausted')
 if candidate.get('$schema')!=CANDIDATE_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad candidate schema')
 if candidate.get('objective_id') not in (None,state['objective_id']): raise OutcomeLoopError('E_BINDING','candidate objective mismatch')
 cid=text(candidate.get('candidate_id'),'candidate_id'); actors=sorted(set(candidate.get('production_actor_ids',[])))
 if not actors: raise OutcomeLoopError('E_AUTHORITY','production actors required')
 bindings=[]; covered=set()
 for i,a in enumerate(candidate.get('artifacts',[])):
  a=obj(a,f'artifacts[{i}]'); p,rel=safe(project,a.get('path'),f'artifacts[{i}].path'); actual=file_digest(p); expected=sha(a.get('sha256'),f'artifacts[{i}].sha256')
  if actual!=expected: raise OutcomeLoopError('E_DIGEST',f'artifact {i} changed')
  klass=text(a.get('artifact_class_id'),'artifact_class_id'); covered.add(klass); bindings.append({'artifact_id':text(a.get('artifact_id'),'artifact_id'),'artifact_class_id':klass,'path':rel,'sha256':actual,'size':p.stat().st_size})
 missing=set(state['required_artifact_classes'])-covered
 if missing: raise OutcomeLoopError('E_ARTIFACT',f'missing required artifact classes: {sorted(missing)}')
 iteration=state['iteration']+1; sorted_bindings=sorted(bindings,key=lambda x:x['artifact_id']); c={'candidate_id':cid,'iteration':iteration,'production_actor_ids':actors,'artifact_bindings':sorted_bindings,'artifacts':sorted_bindings}; c['candidate_sha256']=digest(c)
 return seal({**state,'phase':'evaluate','iteration':iteration,'candidates':[*state['candidates'],c],
 'next_action':{'action':'execute_required_evaluators','authority':'independent_evaluation','candidate_id':cid,'evaluator_ids':[e['evaluator_id'] for e in state['required_evaluators']]}})

def threshold(state,dim):
 p=state['quality_policy']; critical=dim in p['critical_dimensions'] or dim.lower().replace(' ','_') in AUTO_CRITICAL
 return float(p['dimension_minimums'].get(dim,p['critical_min_score'] if critical else p['default_min_score']))
def diagnosis(state,scores,findings,accepted):
 gaps=[{'kind':'score','dimension':d,'score':s,'threshold':threshold(state,d),'deficit':threshold(state,d)-s} for d,s in scores.items() if s<threshold(state,d)]
 for f in findings:
  if f['severity'] in state['quality_policy']['blocking_finding_severities']: gaps.append({'kind':'finding','dimension':f['code'],'score':None,'threshold':None,'deficit':10.0,'statement':f['statement']})
 if not accepted and not gaps: gaps.append({'kind':'evaluator_rejection','dimension':'independent_acceptance','score':None,'threshold':None,'deficit':10.0})
 gaps.sort(key=lambda x:(-x['deficit'],x['dimension'])); return gaps

def record_evaluations(project,raw_state,batch,verifier:Callable|None=None):
 state=verify_state(raw_state)
 if state['phase']!='evaluate': raise OutcomeLoopError('E_PHASE','evaluation not expected')
 if batch.get('$schema')!=BATCH_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad evaluation batch schema')
 candidate=state['candidates'][-1]
 if batch.get('candidate_id')!=candidate['candidate_id']: raise OutcomeLoopError('E_BINDING','evaluation targets wrong candidate')
 verify=verifier or execution_module().verify_receipt; by_id={}; receipts=[]
 receipt_paths=batch.get('execution_receipt_paths',batch.get('receipt_paths',[]))
 for path_value in receipt_paths:
  p,rel=safe(project,path_value,'execution_receipt_path'); receipt=dict(obj(read(p,'evaluation receipt'),'evaluation receipt'))
  try: verified=dict(verify(project,receipt))
  except Exception as e: raise OutcomeLoopError(getattr(e,'code','E_EVALUATOR'),f'evaluator receipt invalid: {e}') from e
  eid=text(verified.get('evaluator_id',receipt.get('evaluator_id')),'evaluator_id')
  if verified.get('objective_id',receipt.get('objective_id'))!=state['objective_id'] or eid in by_id: raise OutcomeLoopError('E_BINDING','evaluator receipt identity invalid')
  if sorted(receipt.get('production_actor_ids',[]))!=candidate['production_actor_ids']: raise OutcomeLoopError('E_BINDING','evaluator observed different production actors')
  expected={(a['artifact_class_id'],a['path'],a['sha256']) for a in candidate['artifact_bindings']}; observed={(a.get('artifact_class_id'),a.get('path'),a.get('sha256')) for a in receipt.get('artifact_bindings',[])}
  if not expected.issubset(observed): raise OutcomeLoopError('E_BINDING','evaluator did not observe current candidate')
  by_id[eid]=receipt; receipts.append({'evaluator_id':eid,'path':rel,'file_sha256':file_digest(p),'receipt_sha256':verified.get('receipt_sha256',receipt.get('receipt_sha256')),'accepted':receipt.get('accepted') is True})
 required={e['evaluator_id'] for e in state['required_evaluators']}
 if set(by_id)!=required: raise OutcomeLoopError('E_EVALUATOR',f'exact required evaluator set needed: {sorted(required)}')
 dims={}; findings=[]; accepted=True
 for eid,r in by_id.items():
  accepted=accepted and r.get('accepted') is True
  for d,s in obj(r.get('scores',{}),'scores').items():
   if not isinstance(s,(int,float)) or isinstance(s,bool) or not math.isfinite(float(s)): raise OutcomeLoopError('E_SCORE',f'{d} invalid')
   dims.setdefault(d,[]).append(float(s))
  for f in r.get('findings',[]):
   if isinstance(f,Mapping): findings.append({'evaluator_id':eid,'code':text(f.get('code'),'finding code'),'severity':text(f.get('severity'),'finding severity'),'statement':text(f.get('statement'),'finding statement')})
 scores={d:min(v) for d,v in dims.items()}; gaps=diagnosis(state,scores,findings,accepted); passing=sorted(d for d,s in scores.items() if s>=threshold(state,d))
 rejected=sorted(eid for eid,r in by_id.items() if r.get('accepted') is not True)
 summary={'scores':scores,'passing_dimensions':passing,'gaps':gaps,'all_evaluators_accepted':accepted}; evaluation={'candidate_id':candidate['candidate_id'],'iteration':state['iteration'],'receipts':sorted(receipts,key=lambda x:x['evaluator_id']),'summary':summary}; evaluation['evaluation_sha256']=digest(evaluation)
 diagnosis_record={'candidate_id':candidate['candidate_id'],'gaps':gaps,'rejected_evaluators':rejected,'passing_dimensions':passing}; diagnosis_record['diagnosis_sha256']=digest(diagnosis_record)
 history=[*state['history'],{'event':'candidate_evaluated','candidate_id':candidate['candidate_id'],'evaluation_sha256':evaluation['evaluation_sha256'],'gap_count':len(gaps)}]
 if not gaps:
  cstate=state['control_state']; source_paths={'outcome_contract':cstate['outcome']['path'],'artifact_contract':cstate['artifacts']['path'],'evaluator_contract':cstate['evaluators']['path'],'benchmark_contract':cstate['benchmarks']['path'],'calibration_receipts':cstate['calibrations']['path']}
  receipt_paths_by_eval={r['evaluator_id']:r['path'] for r in receipts}; claims=[]
  for claim in state.get('outcome_claims',[]):
   claims.append({'claim_id':claim['claim_id'],'statement':claim['statement'],'required':True,'artifact_evidence':[dict(a) for a in candidate['artifact_bindings']],'evaluator_execution_receipt_paths':[receipt_paths_by_eval[e['evaluator_id']] for e in state['required_evaluators'] if e['evaluator_id'] in receipt_paths_by_eval]})
  request={'$schema':'company-os.reality-acceptance-request.v2','objective_id':state['objective_id'],'original_objective':state['original_objective'],'candidate_id':candidate['candidate_id'],'production_actor_ids':candidate['production_actor_ids'],'production_narrative_admissible':False,'source_paths':source_paths,'claims':claims}
  return seal({**state,'phase':'reality','evaluations':[*state['evaluations'],evaluation],'diagnoses':[*state.get('diagnoses',[]),diagnosis_record],'history':history,
  'next_action':{'action':'run_reality_acceptance','authority':'quality_ready','candidate_id':candidate['candidate_id'],'request_template':request}})
 focus=[g['dimension'] for g in gaps[:state['quality_policy']['max_focus_dimensions']]]; stagnant={}
 prior=state['evaluations'][-state['quality_policy']['stagnation_window']:] if state['evaluations'] else []
 for d in focus:
  old=[x['summary']['scores'].get(d) for x in prior if d in x['summary']['scores']]
  if old and d in scores: stagnant[d]=sum(1 for x in old if scores[d]-x<state['quality_policy']['min_improvement'])
 reorg=any(v>=state['quality_policy']['stagnation_window'] for v in stagnant.values()); mode='reorganize' if reorg else 'retask'; artifact_map={}
 for e in state['required_evaluators']:
  for d in e['score_dimensions']: artifact_map.setdefault(d,set()).update(e['artifact_classes'])
 lanes=[{'lane_id':f'improve:{d}','role':'bottleneck_specialist','target_dimension':d,'artifact_classes':sorted(artifact_map.get(d,set(state['required_artifact_classes']))),'mandate':'Move this quality bottleneck without regressing passing dimensions.'} for d in focus]
 instructions=['Preserve independently passing dimensions.','Change only the dominant constraint and directly coupled artifacts.','Materialize a new real candidate before reevaluation.']
 if reorg: instructions+=['Replace the strategy owner for stagnant dimensions.','Acquire missing capability or stronger benchmarks.','Challenge the current artifact approach instead of polishing the same failed abstraction.','Reduce unrelated production concurrency until the bottleneck moves.']
 intervention={'intervention_id':f'iteration:{state["iteration"]}:bottleneck','mode':mode,'dominant_gap':gaps[0],'target_dimensions':focus,'preserve_dimensions':passing,'stagnation_count':stagnant,'organization_mutation':{'specialist_lanes':lanes,'keep_independent_evaluators':[e['evaluator_id'] for e in state['required_evaluators']],'instructions':instructions}}; intervention['intervention_sha256']=digest(intervention)
 return seal({**state,'phase':'rework','evaluations':[*state['evaluations'],evaluation],'diagnoses':[*state.get('diagnoses',[]),diagnosis_record],'interventions':[*state['interventions'],intervention],'history':history,'organization_plan':intervention['organization_mutation'],
 'next_action':{'action':'execute_intervention','authority':'targeted_rework','candidate_id':candidate['candidate_id'],'intervention':intervention}})

def record_reality(project,raw_state,path_value,verifier:Callable|None=None):
 state=verify_state(raw_state)
 if state['phase']!='reality': raise OutcomeLoopError('E_PHASE','reality not expected')
 p,rel=safe(project,path_value,'reality_receipt_path'); receipt=dict(obj(read(p,'reality receipt'),'reality receipt'))
 if receipt.get('$schema')!=REALITY_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad reality receipt schema')
 verify=verifier or reality_module().verify_receipt
 try: v=dict(verify(project,receipt))
 except Exception as e: raise OutcomeLoopError(getattr(e,'code','E_REALITY'),f'reality receipt invalid: {e}') from e
 candidate=state['candidates'][-1]
 if v.get('objective_id')!=state['objective_id'] or receipt.get('candidate_id')!=candidate['candidate_id']: raise OutcomeLoopError('E_BINDING','reality receipt targets wrong objective or candidate')
 acceptance={'candidate_id':candidate['candidate_id'],'path':rel,'file_sha256':file_digest(p),'receipt_sha256':sha(v.get('receipt_sha256',receipt.get('receipt_sha256')),'receipt_sha256'),'accepted':v.get('accepted') is True,'claim_count':v.get('claim_count',0)}
 history=[*state['history'],{'event':'reality_judged','candidate_id':candidate['candidate_id'],'accepted':acceptance['accepted']}]
 if acceptance['accepted']: return seal({**state,'phase':'accepted','acceptance':acceptance,'history':history,'next_action':{'action':'complete','authority':'reality_accepted','candidate_id':candidate['candidate_id'],'receipt_sha256':acceptance['receipt_sha256']}})
 intervention={'intervention_id':f'iteration:{state["iteration"]}:reality','mode':'reorganize','dominant_gap':{'kind':'reality_rejection','dimension':'original_objective','deficit':10.0},'target_dimensions':['original_objective'],'preserve_dimensions':state['evaluations'][-1]['summary']['passing_dimensions'],'organization_mutation':{'specialist_lanes':[{'lane_id':'improve:original_objective','role':'outcome_strategy_specialist','target_dimension':'original_objective','artifact_classes':state['required_artifact_classes']}],'keep_independent_evaluators':[e['evaluator_id'] for e in state['required_evaluators']],'instructions':['Reopen assumptions implicated by the failed real world claim.','Preserve verified strengths.','Materialize a new candidate before acceptance.']}}; intervention['intervention_sha256']=digest(intervention)
 return seal({**state,'phase':'rework','acceptance':acceptance,'history':history,'interventions':[*state['interventions'],intervention],'organization_plan':intervention['organization_mutation'],'next_action':{'action':'execute_intervention','authority':'reality_rework','intervention':intervention}})

def status(raw):
 s=verify_state(raw); return {'objective_id':s['objective_id'],'phase':s['phase'],'iteration':s['iteration'],'candidate_count':len(s['candidates']),'evaluation_count':len(s['evaluations']),'accepted':s['phase']=='accepted','next_action':s['next_action'],'state_sha256':s['state_sha256']}
def write(path,v): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def main():
 p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
 for name in ('start','bind-control','record-candidate','record-evaluations','record-reality','verify'):
  x=sub.add_parser(name); x.add_argument('--state',type=Path); x.add_argument('--output',type=Path); x.add_argument('--project-root',type=Path)
  if name=='start': x.add_argument('--request',type=Path,required=True)
  if name=='bind-control': x.add_argument('--control-state',type=Path,required=True)
  if name=='record-candidate': x.add_argument('--candidate',type=Path,required=True)
  if name=='record-evaluations': x.add_argument('--batch',type=Path,required=True)
  if name=='record-reality': x.add_argument('--receipt-path',required=True)
 a=p.parse_args()
 try:
  if a.cmd=='start': r=start(obj(read(a.request,'request'),'request'))
  elif a.cmd=='bind-control': r=bind_control(a.project_root,obj(read(a.state,'state'),'state'),obj(read(a.control_state,'control'),'control'))
  elif a.cmd=='record-candidate': r=record_candidate(a.project_root,obj(read(a.state,'state'),'state'),obj(read(a.candidate,'candidate'),'candidate'))
  elif a.cmd=='record-evaluations': r=record_evaluations(a.project_root,obj(read(a.state,'state'),'state'),obj(read(a.batch,'batch'),'batch'))
  elif a.cmd=='record-reality': r=record_reality(a.project_root,obj(read(a.state,'state'),'state'),a.receipt_path)
  else: print(json.dumps(status(obj(read(a.state,'state'),'state')),sort_keys=True)); return 0
  write(a.output,r); print(json.dumps({'ok':True,**status(r)},sort_keys=True)); return 0
 except OutcomeLoopError as e: print(json.dumps({'ok':False,'code':e.code,'error':e.message},sort_keys=True)); return 2
if __name__=='__main__': raise SystemExit(main())
