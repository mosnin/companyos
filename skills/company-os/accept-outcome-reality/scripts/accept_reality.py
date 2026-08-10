#!/usr/bin/env python3
"""Execution bound reality acceptance for Company OS outcomes."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
REQUEST_SCHEMA='company-os.reality-acceptance-request.v2'; RECEIPT_SCHEMA='company-os.reality-acceptance-receipt.v1'
OUTCOME_SCHEMA='company-os.outcome-contract.v1'; ARTIFACT_SCHEMA='company-os.artifact-observation-contract.v1'; EVALUATOR_SCHEMA='company-os.evaluator-runtime-contract.v1'; BENCHMARK_SCHEMA='company-os.benchmark-contract.v1'; CALIBRATION_SCHEMA='company-os.evaluator-calibration-receipt.v1'
SCHEMA=REQUEST_SCHEMA; OUT=RECEIPT_SCHEMA
_EXECUTION_MODULE=None; _CALIBRATION_MODULE=None
class RealityError(ValueError):
 def __init__(self,code,msg): self.code=code; self.message=msg; super().__init__(f'{code}: {msg}')
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(v): return hashlib.sha256(canonical(v)).hexdigest()
def file_digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def text(v,l):
 if not isinstance(v,str) or not v.strip() or '\x00' in v: raise RealityError('E_SCHEMA',f'{l} must be nonempty')
 return v
def obj(v,l):
 if not isinstance(v,Mapping): raise RealityError('E_SCHEMA',f'{l} must be object')
 return v
def sha(v,l):
 v=text(v,l)
 if len(v)!=64 or any(c not in '0123456789abcdef' for c in v): raise RealityError('E_SCHEMA',f'{l} must be sha256')
 return v
def safe(project,v,l):
 raw=text(v,l); pure=PurePosixPath(raw)
 if '\\' in raw or pure.is_absolute() or not pure.parts or any(x in {'','.','..'} for x in pure.parts): raise RealityError('E_PATH',f'{l} unsafe')
 root=project.resolve(); cur=root
 for part in pure.parts:
  cur/=part
  if cur.is_symlink(): raise RealityError('E_PATH',f'{l} traverses symlink')
 try: p=(root/Path(*pure.parts)).resolve(strict=True)
 except OSError as e: raise RealityError('E_PATH',f'{l} missing') from e
 if root!=p and root not in p.parents or not p.is_file() or p.is_symlink(): raise RealityError('E_PATH',f'{l} invalid')
 return p,pure.as_posix()
def read(p,l):
 try: return json.loads(p.read_text())
 except Exception as e: raise RealityError('E_JSON',f'invalid {l}') from e
def verify_self(v,field,l):
 observed=sha(v.get(field),f'{l}.{field}')
 if observed!=digest({**v,field:None}): raise RealityError('E_DIGEST',f'{l} changed')
 return observed
def module(relative,name):
 path=Path(__file__).resolve().parents[2]/relative; spec=importlib.util.spec_from_file_location(name,path)
 if not spec or not spec.loader: raise RealityError('E_RUNTIME',f'cannot load {name}')
 m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def execution_module():
 global _EXECUTION_MODULE
 if _EXECUTION_MODULE is None: _EXECUTION_MODULE=module('execute-outcome-evaluator/scripts/execute_evaluator.py','company_os_reality_eval')
 return _EXECUTION_MODULE
def calibration_module():
 global _CALIBRATION_MODULE
 if _CALIBRATION_MODULE is None: _CALIBRATION_MODULE=module('calibrate-outcome-evaluator/scripts/calibrate_evaluator.py','company_os_reality_cal')
 return _CALIBRATION_MODULE

def load_contract(project,path_value,label,schema):
 p,rel=safe(project,path_value,label); v=dict(obj(read(p,label),label))
 if v.get('$schema')!=schema: raise RealityError('E_SCHEMA',f'{label} bad schema')
 verify_self(v,'contract_sha256',label)
 return v,{'path':rel,'file_sha256':file_digest(p),'contract_sha256':v['contract_sha256']}
def load_sources(project,paths,objective_id,original):
 required={'outcome_contract','artifact_contract','evaluator_contract','benchmark_contract','calibration_receipts'}
 if set(paths)!=required: raise RealityError('E_SCHEMA','source_paths incomplete')
 outcome,ob=load_contract(project,paths['outcome_contract'],'outcome contract',OUTCOME_SCHEMA)
 artifacts,ab=load_contract(project,paths['artifact_contract'],'artifact contract',ARTIFACT_SCHEMA)
 evaluators,eb=load_contract(project,paths['evaluator_contract'],'evaluator contract',EVALUATOR_SCHEMA)
 benchmarks,bb=load_contract(project,paths['benchmark_contract'],'benchmark contract',BENCHMARK_SCHEMA)
 for label,v in [('outcome',outcome),('artifacts',artifacts),('evaluators',evaluators),('benchmarks',benchmarks)]:
  if v.get('objective_id')!=objective_id: raise RealityError('E_BINDING',f'{label} objective mismatch')
 if outcome.get('original_objective')!=original: raise RealityError('E_BINDING','outcome does not bind original objective')
 cp,crel=safe(project,paths['calibration_receipts'],'calibration_receipts'); raw=read(cp,'calibration receipts')
 if not isinstance(raw,list) or not raw: raise RealityError('E_CALIBRATION','calibration receipts required')
 cal=[]
 for i,r in enumerate(raw):
  r=dict(obj(r,f'calibration[{i}]'))
  try: v=dict(calibration_module().verify_receipt(project,r))
  except Exception as e: raise RealityError(getattr(e,'code','E_CALIBRATION'),f'calibration invalid: {e}') from e
  if v.get('objective_id')!=objective_id or v.get('execution_bound') is not True or v.get('passed') is not True: raise RealityError('E_CALIBRATION','calibration not accepted for objective')
  cal.append({'evaluator_id':v['evaluator_id'],'receipt_sha256':sha(v['receipt_sha256'],'calibration receipt_sha256')})
 return {'outcome_contract':ob,'artifact_contract':ab,'evaluator_contract':eb,'benchmark_contract':bb,'calibration_receipts':{'path':crel,'file_sha256':file_digest(cp),'receipts_sha256':digest(sorted(cal,key=lambda x:x['evaluator_id']))}},outcome,artifacts

def required_observation_evidence(artifact_contract):
 result={}
 for item in artifact_contract.get('artifact_classes',[]):
  if not isinstance(item,Mapping) or item.get('required') is not True: continue
  aid=text(item.get('artifact_class_id'),'artifact_class_id'); evidence=item.get('required_evidence',[])
  if not isinstance(evidence,list) or not all(isinstance(x,str) and x for x in evidence): raise RealityError('E_SCHEMA',f'{aid}.required_evidence invalid')
  result[aid]=set(evidence)
 return result

def accept(project,req=None):
 if req is None:
  req=project; raise RealityError('E_SCHEMA','project root is required for execution bound reality acceptance')
 project=project.resolve()
 if req.get('$schema')!=REQUEST_SCHEMA: raise RealityError('E_SCHEMA','bad request schema')
 oid=text(req.get('objective_id'),'objective_id'); original=text(req.get('original_objective'),'original_objective'); candidate_id=text(req.get('candidate_id'),'candidate_id')
 if req.get('production_narrative_admissible') is not False: raise RealityError('E_AUTHORITY','production narrative is inadmissible')
 production=sorted(set(req.get('production_actor_ids',[])))
 if not production: raise RealityError('E_AUTHORITY','production actors required')
 sources,outcome,artifact_contract=load_sources(project,obj(req.get('source_paths'),'source_paths'),oid,original)
 claims=req.get('claims')
 if not isinstance(claims,list) or not claims: raise RealityError('E_SCHEMA','claims required')
 known_claims={x.get('claim_id'):x for x in outcome.get('outcome_claims',[]) if isinstance(x,Mapping)}
 required_evidence_by_artifact=required_observation_evidence(artifact_contract)
 seen=set(); decisions=[]; blockers=[]
 for i,c in enumerate(claims):
  c=obj(c,f'claims[{i}]'); cid=text(c.get('claim_id'),'claim_id')
  if cid in seen: raise RealityError('E_DUPLICATE',f'duplicate claim {cid}')
  seen.add(cid); statement=text(c.get('statement'),'statement'); required=c.get('required',True)
  if not isinstance(required,bool): raise RealityError('E_SCHEMA','required must be boolean')
  if cid not in known_claims or known_claims[cid].get('statement')!=statement: raise RealityError('E_BINDING',f'claim {cid} not in outcome contract')
  artifact_bindings=[]
  for j,a in enumerate(c.get('artifact_evidence',[])):
   a=obj(a,f'artifact_evidence[{j}]'); p,rel=safe(project,a.get('path'),f'artifact_evidence[{j}].path'); actual=file_digest(p)
   if actual!=sha(a.get('sha256'),'artifact sha256'): raise RealityError('E_DIGEST',f'artifact evidence changed: {cid}')
   artifact_bindings.append({'artifact_id':text(a.get('artifact_id'),'artifact_id'),'artifact_class_id':text(a.get('artifact_class_id'),'artifact_class_id'),'path':rel,'sha256':actual,'size':p.stat().st_size})
  artifact_classes={a['artifact_class_id'] for a in artifact_bindings}
  required_evidence=set().union(*(required_evidence_by_artifact.get(aid,set()) for aid in artifact_classes)) if artifact_classes else set()
  eval_bindings=[]; eval_accept=True; observed_evidence=set()
  for j,path_value in enumerate(c.get('evaluator_execution_receipt_paths',[])):
   p,rel=safe(project,path_value,f'evaluator_receipt[{j}]'); receipt=dict(obj(read(p,'evaluator receipt'),'evaluator receipt'))
   try: v=dict(execution_module().verify_receipt(project,receipt))
   except Exception as e: raise RealityError(getattr(e,'code','E_EVALUATOR'),f'evaluator receipt invalid: {e}') from e
   if v.get('objective_id')!=oid or sorted(receipt.get('production_actor_ids',[]))!=production or receipt.get('independent_role') is not True: raise RealityError('E_BINDING','evaluator receipt authority or objective mismatch')
   eval_accept=eval_accept and receipt.get('accepted') is True
   for evidence in receipt.get('evidence_bindings',[]):
    if isinstance(evidence,Mapping) and isinstance(evidence.get('evidence_type'),str) and evidence.get('evidence_type'):
     observed_evidence.add(evidence['evidence_type'])
   eval_bindings.append({'evaluator_id':v['evaluator_id'],'path':rel,'file_sha256':file_digest(p),'receipt_sha256':sha(v['receipt_sha256'],'execution receipt_sha256'),'accepted':receipt.get('accepted') is True})
  missing_observation=sorted(required_evidence-observed_evidence)
  evidence_ok=bool(artifact_bindings); independent_ok=bool(eval_bindings) and eval_accept; observation_ok=not missing_observation; passed=evidence_ok and independent_ok and observation_ok
  if required and not evidence_ok: blockers.append({'claim_id':cid,'code':'NO_ARTIFACT_EVIDENCE'})
  if required and not independent_ok: blockers.append({'claim_id':cid,'code':'INDEPENDENT_EVALUATION_FAILED'})
  if required and not observation_ok: blockers.append({'claim_id':cid,'code':'REQUIRED_OBSERVATION_EVIDENCE_MISSING','missing':missing_observation})
  decisions.append({'claim_id':cid,'statement':statement,'required':required,'passed':passed,'artifact_evidence':artifact_bindings,'evaluator_execution_receipts':eval_bindings,'required_observation_evidence':sorted(required_evidence),'observed_evidence_types':sorted(observed_evidence),'artifact_evidence_count':len(artifact_bindings),'evaluator_receipt_count':len(eval_bindings)})
 blockers.sort(key=lambda x:(x['claim_id'],x['code'])); accepted=not blockers and all((not d['required']) or d['passed'] for d in decisions)
 out={'$schema':RECEIPT_SCHEMA,'schema_version':2,'execution_bound':True,'objective_id':oid,'original_objective':original,'original_objective_sha256':hashlib.sha256(original.encode()).hexdigest(),'candidate_id':candidate_id,'production_actor_ids':production,'production_narrative_admissible':False,'source_bindings':sources,'claim_decisions':sorted(decisions,key=lambda x:x['claim_id']),'blockers':blockers,'accepted':accepted,'receipt_sha256':None}
 out['receipt_sha256']=digest(out); return out

def verify_receipt(project,receipt):
 if receipt.get('$schema')!=RECEIPT_SCHEMA or receipt.get('schema_version')!=2 or receipt.get('execution_bound') is not True: raise RealityError('E_SCHEMA','reality receipt is not execution bound')
 receipt_sha=verify_self(receipt,'receipt_sha256','reality receipt'); oid=text(receipt.get('objective_id'),'objective_id'); original=text(receipt.get('original_objective'),'original_objective')
 if receipt.get('production_narrative_admissible') is not False: raise RealityError('E_AUTHORITY','production narrative became admissible')
 bindings=obj(receipt.get('source_bindings'),'source_bindings'); paths={k:obj(v,f'source_bindings.{k}').get('path') for k,v in bindings.items()}
 sources,outcome,artifact_contract=load_sources(project,paths,oid,original)
 for k,v in sources.items():
  observed=obj(bindings.get(k),k)
  if observed.get('file_sha256')!=v.get('file_sha256'): raise RealityError('E_DIGEST',f'source drift: {k}')
 production=sorted(set(receipt.get('production_actor_ids',[]))); blockers=[]; count=0
 required_evidence_by_artifact=required_observation_evidence(artifact_contract)
 known={x.get('claim_id'):x for x in outcome.get('outcome_claims',[]) if isinstance(x,Mapping)}
 for d in receipt.get('claim_decisions',[]):
  d=obj(d,'claim decision'); cid=text(d.get('claim_id'),'claim_id')
  if cid not in known or known[cid].get('statement')!=d.get('statement'): raise RealityError('E_BINDING',f'claim drift: {cid}')
  artifacts=d.get('artifact_evidence',[]); evals=d.get('evaluator_execution_receipts',[])
  artifact_classes=set()
  for a in artifacts:
   a=obj(a,'artifact evidence'); p,_=safe(project,a.get('path'),'artifact path')
   if file_digest(p)!=sha(a.get('sha256'),'artifact sha256'): raise RealityError('E_DIGEST',f'artifact drift: {cid}')
   artifact_classes.add(text(a.get('artifact_class_id'),'artifact_class_id'))
  required_evidence=set().union(*(required_evidence_by_artifact.get(aid,set()) for aid in artifact_classes)) if artifact_classes else set()
  eval_accept=True; observed_evidence=set()
  for e in evals:
   e=obj(e,'evaluator execution'); p,_=safe(project,e.get('path'),'execution receipt path'); raw=dict(obj(read(p,'execution receipt'),'execution receipt'))
   try: v=dict(execution_module().verify_receipt(project,raw))
   except Exception as ex: raise RealityError(getattr(ex,'code','E_EVALUATOR'),f'evaluator receipt drift: {ex}') from ex
   if v.get('receipt_sha256')!=e.get('receipt_sha256') or sorted(raw.get('production_actor_ids',[]))!=production: raise RealityError('E_DIGEST',f'evaluator drift: {cid}')
   eval_accept=eval_accept and raw.get('accepted') is True
   for evidence in raw.get('evidence_bindings',[]):
    if isinstance(evidence,Mapping) and isinstance(evidence.get('evidence_type'),str) and evidence.get('evidence_type'):
     observed_evidence.add(evidence['evidence_type'])
  missing_observation=sorted(required_evidence-observed_evidence)
  passed=bool(artifacts) and bool(evals) and eval_accept and not missing_observation
  if d.get('required') is True and not artifacts: blockers.append({'claim_id':cid,'code':'NO_ARTIFACT_EVIDENCE'})
  if d.get('required') is True and (not evals or not eval_accept): blockers.append({'claim_id':cid,'code':'INDEPENDENT_EVALUATION_FAILED'})
  if d.get('required') is True and missing_observation: blockers.append({'claim_id':cid,'code':'REQUIRED_OBSERVATION_EVIDENCE_MISSING','missing':missing_observation})
  if d.get('passed') is not passed: raise RealityError('E_REALITY',f'stored claim decision drift: {cid}')
  if d.get('required_observation_evidence',[]) != sorted(required_evidence): raise RealityError('E_REALITY',f'stored observation requirement drift: {cid}')
  if d.get('observed_evidence_types',[]) != sorted(observed_evidence): raise RealityError('E_REALITY',f'stored observation evidence drift: {cid}')
  count+=1
 blockers=sorted(blockers,key=lambda x:(x['claim_id'],x['code']))
 accepted=not blockers and receipt.get('accepted') is True
 if receipt.get('blockers') != blockers: raise RealityError('E_REALITY','stored blocker state no longer matches reality')
 return {'objective_id':oid,'candidate_id':text(receipt.get('candidate_id'),'candidate_id'),'receipt_sha256':receipt_sha,'accepted':accepted,'execution_bound':True,'claim_count':count}
def main():
 p=argparse.ArgumentParser(); p.add_argument('--project-root',type=Path,required=True); p.add_argument('--request',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
 try: out=accept(a.project_root,obj(read(a.request,'request'),'request')); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps({'ok':True,'accepted':out['accepted'],'receipt_sha256':out['receipt_sha256']},sort_keys=True)); return 0
 except RealityError as e: print(json.dumps({'ok':False,'code':e.code,'error':e.message},sort_keys=True)); return 2
if __name__=='__main__': raise SystemExit(main())
