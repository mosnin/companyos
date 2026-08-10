#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_reality() -> None:
    path = Path("skills/company-os/accept-outcome-reality/scripts/accept_reality.py")
    text = path.read_text(encoding="utf-8")
    old_return = " return {'outcome_contract':ob,'artifact_contract':ab,'evaluator_contract':eb,'benchmark_contract':bb,'calibration_receipts':{'path':crel,'file_sha256':file_digest(cp),'receipts_sha256':digest(sorted(cal,key=lambda x:x['evaluator_id']))}},outcome\n\ndef accept(project,req=None):"
    new_return = " return {'outcome_contract':ob,'artifact_contract':ab,'evaluator_contract':eb,'benchmark_contract':bb,'calibration_receipts':{'path':crel,'file_sha256':file_digest(cp),'receipts_sha256':digest(sorted(cal,key=lambda x:x['evaluator_id']))}},outcome,artifacts\n\ndef required_observation_evidence(artifact_contract):\n result={}\n for item in artifact_contract.get('artifact_classes',[]):\n  if not isinstance(item,Mapping) or item.get('required') is not True: continue\n  aid=text(item.get('artifact_class_id'),'artifact_class_id'); evidence=item.get('required_evidence',[])\n  if not isinstance(evidence,list) or not all(isinstance(x,str) and x for x in evidence): raise RealityError('E_SCHEMA',f'{aid}.required_evidence invalid')\n  result[aid]=set(evidence)\n return result\n\ndef accept(project,req=None):"
    if text.count(old_return) != 1:
        raise SystemExit("load_sources return marker missing")
    text = text.replace(old_return, new_return, 1)
    text = text.replace(" sources,outcome=load_sources(project,obj(req.get('source_paths'),'source_paths'),oid,original)", " sources,outcome,artifact_contract=load_sources(project,obj(req.get('source_paths'),'source_paths'),oid,original)", 1)
    old_known = " known_claims={x.get('claim_id'):x for x in outcome.get('outcome_claims',[]) if isinstance(x,Mapping)}\n seen=set(); decisions=[]; blockers=[]"
    new_known = " known_claims={x.get('claim_id'):x for x in outcome.get('outcome_claims',[]) if isinstance(x,Mapping)}\n required_evidence_by_artifact=required_observation_evidence(artifact_contract)\n seen=set(); decisions=[]; blockers=[]"
    if text.count(old_known) != 1:
        raise SystemExit("accept claim setup marker missing")
    text = text.replace(old_known, new_known, 1)
    old_eval = "  eval_bindings=[]; eval_accept=True\n  for j,path_value in enumerate(c.get('evaluator_execution_receipt_paths',[])):"
    new_eval = "  artifact_classes={a['artifact_class_id'] for a in artifact_bindings}\n  required_evidence=set().union(*(required_evidence_by_artifact.get(aid,set()) for aid in artifact_classes)) if artifact_classes else set()\n  eval_bindings=[]; eval_accept=True; observed_evidence=set()\n  for j,path_value in enumerate(c.get('evaluator_execution_receipt_paths',[])):"
    if text.count(old_eval) != 1:
        raise SystemExit("accept evaluator setup marker missing")
    text = text.replace(old_eval, new_eval, 1)
    old_binding = "   eval_accept=eval_accept and receipt.get('accepted') is True\n   eval_bindings.append({'evaluator_id':v['evaluator_id'],'path':rel,'file_sha256':file_digest(p),'receipt_sha256':sha(v['receipt_sha256'],'execution receipt_sha256'),'accepted':receipt.get('accepted') is True})\n  evidence_ok=bool(artifact_bindings); independent_ok=bool(eval_bindings) and eval_accept; passed=evidence_ok and independent_ok\n  if required and not evidence_ok: blockers.append({'claim_id':cid,'code':'NO_ARTIFACT_EVIDENCE'})\n  if required and not independent_ok: blockers.append({'claim_id':cid,'code':'INDEPENDENT_EVALUATION_FAILED'})\n  decisions.append({'claim_id':cid,'statement':statement,'required':required,'passed':passed,'artifact_evidence':artifact_bindings,'evaluator_execution_receipts':eval_bindings,'artifact_evidence_count':len(artifact_bindings),'evaluator_receipt_count':len(eval_bindings)})"
    new_binding = "   eval_accept=eval_accept and receipt.get('accepted') is True\n   for evidence in receipt.get('evidence_bindings',[]):\n    if isinstance(evidence,Mapping) and isinstance(evidence.get('evidence_type'),str) and evidence.get('evidence_type'):\n     observed_evidence.add(evidence['evidence_type'])\n   eval_bindings.append({'evaluator_id':v['evaluator_id'],'path':rel,'file_sha256':file_digest(p),'receipt_sha256':sha(v['receipt_sha256'],'execution receipt_sha256'),'accepted':receipt.get('accepted') is True})\n  missing_observation=sorted(required_evidence-observed_evidence)\n  evidence_ok=bool(artifact_bindings); independent_ok=bool(eval_bindings) and eval_accept; observation_ok=not missing_observation; passed=evidence_ok and independent_ok and observation_ok\n  if required and not evidence_ok: blockers.append({'claim_id':cid,'code':'NO_ARTIFACT_EVIDENCE'})\n  if required and not independent_ok: blockers.append({'claim_id':cid,'code':'INDEPENDENT_EVALUATION_FAILED'})\n  if required and not observation_ok: blockers.append({'claim_id':cid,'code':'REQUIRED_OBSERVATION_EVIDENCE_MISSING','missing':missing_observation})\n  decisions.append({'claim_id':cid,'statement':statement,'required':required,'passed':passed,'artifact_evidence':artifact_bindings,'evaluator_execution_receipts':eval_bindings,'required_observation_evidence':sorted(required_evidence),'observed_evidence_types':sorted(observed_evidence),'artifact_evidence_count':len(artifact_bindings),'evaluator_receipt_count':len(eval_bindings)})"
    if text.count(old_binding) != 1:
        raise SystemExit("accept evidence decision marker missing")
    text = text.replace(old_binding, new_binding, 1)
    old_verify_sources = " sources,outcome=load_sources(project,paths,oid,original)"
    new_verify_sources = " sources,outcome,artifact_contract=load_sources(project,paths,oid,original)"
    if text.count(old_verify_sources) != 1:
        raise SystemExit("verify source marker missing")
    text = text.replace(old_verify_sources, new_verify_sources, 1)
    old_verify_setup = " production=sorted(set(receipt.get('production_actor_ids',[]))); blockers=[]; count=0\n known={x.get('claim_id'):x for x in outcome.get('outcome_claims',[]) if isinstance(x,Mapping)}"
    new_verify_setup = " production=sorted(set(receipt.get('production_actor_ids',[]))); blockers=[]; count=0\n required_evidence_by_artifact=required_observation_evidence(artifact_contract)\n known={x.get('claim_id'):x for x in outcome.get('outcome_claims',[]) if isinstance(x,Mapping)}"
    if text.count(old_verify_setup) != 1:
        raise SystemExit("verify setup marker missing")
    text = text.replace(old_verify_setup, new_verify_setup, 1)
    old_verify_loop = "  artifacts=d.get('artifact_evidence',[]); evals=d.get('evaluator_execution_receipts',[])\n  for a in artifacts:\n   a=obj(a,'artifact evidence'); p,_=safe(project,a.get('path'),'artifact path')\n   if file_digest(p)!=sha(a.get('sha256'),'artifact sha256'): raise RealityError('E_DIGEST',f'artifact drift: {cid}')\n  eval_accept=True\n  for e in evals:\n   e=obj(e,'evaluator execution'); p,_=safe(project,e.get('path'),'execution receipt path'); raw=dict(obj(read(p,'execution receipt'),'execution receipt'))\n   try: v=dict(execution_module().verify_receipt(project,raw))\n   except Exception as ex: raise RealityError(getattr(ex,'code','E_EVALUATOR'),f'evaluator receipt drift: {ex}') from ex\n   if v.get('receipt_sha256')!=e.get('receipt_sha256') or sorted(raw.get('production_actor_ids',[]))!=production: raise RealityError('E_DIGEST',f'evaluator drift: {cid}')\n   eval_accept=eval_accept and raw.get('accepted') is True\n  passed=bool(artifacts) and bool(evals) and eval_accept\n  if d.get('required') is True and not passed: blockers.append(cid)\n  count+=1\n accepted=not blockers and receipt.get('accepted') is True\n if bool(receipt.get('blockers')) != bool(blockers): raise RealityError('E_REALITY','stored blocker state no longer matches reality')"
    new_verify_loop = "  artifacts=d.get('artifact_evidence',[]); evals=d.get('evaluator_execution_receipts',[])\n  artifact_classes=set()\n  for a in artifacts:\n   a=obj(a,'artifact evidence'); p,_=safe(project,a.get('path'),'artifact path')\n   if file_digest(p)!=sha(a.get('sha256'),'artifact sha256'): raise RealityError('E_DIGEST',f'artifact drift: {cid}')\n   artifact_classes.add(text(a.get('artifact_class_id'),'artifact_class_id'))\n  required_evidence=set().union(*(required_evidence_by_artifact.get(aid,set()) for aid in artifact_classes)) if artifact_classes else set()\n  eval_accept=True; observed_evidence=set()\n  for e in evals:\n   e=obj(e,'evaluator execution'); p,_=safe(project,e.get('path'),'execution receipt path'); raw=dict(obj(read(p,'execution receipt'),'execution receipt'))\n   try: v=dict(execution_module().verify_receipt(project,raw))\n   except Exception as ex: raise RealityError(getattr(ex,'code','E_EVALUATOR'),f'evaluator receipt drift: {ex}') from ex\n   if v.get('receipt_sha256')!=e.get('receipt_sha256') or sorted(raw.get('production_actor_ids',[]))!=production: raise RealityError('E_DIGEST',f'evaluator drift: {cid}')\n   eval_accept=eval_accept and raw.get('accepted') is True\n   for evidence in raw.get('evidence_bindings',[]):\n    if isinstance(evidence,Mapping) and isinstance(evidence.get('evidence_type'),str) and evidence.get('evidence_type'):\n     observed_evidence.add(evidence['evidence_type'])\n  missing_observation=sorted(required_evidence-observed_evidence)\n  passed=bool(artifacts) and bool(evals) and eval_accept and not missing_observation\n  if d.get('required') is True and not artifacts: blockers.append({'claim_id':cid,'code':'NO_ARTIFACT_EVIDENCE'})\n  if d.get('required') is True and (not evals or not eval_accept): blockers.append({'claim_id':cid,'code':'INDEPENDENT_EVALUATION_FAILED'})\n  if d.get('required') is True and missing_observation: blockers.append({'claim_id':cid,'code':'REQUIRED_OBSERVATION_EVIDENCE_MISSING','missing':missing_observation})\n  if d.get('passed') is not passed: raise RealityError('E_REALITY',f'stored claim decision drift: {cid}')\n  if d.get('required_observation_evidence',[]) != sorted(required_evidence): raise RealityError('E_REALITY',f'stored observation requirement drift: {cid}')\n  if d.get('observed_evidence_types',[]) != sorted(observed_evidence): raise RealityError('E_REALITY',f'stored observation evidence drift: {cid}')\n  count+=1\n blockers=sorted(blockers,key=lambda x:(x['claim_id'],x['code']))\n accepted=not blockers and receipt.get('accepted') is True\n if receipt.get('blockers') != blockers: raise RealityError('E_REALITY','stored blocker state no longer matches reality')"
    if text.count(old_verify_loop) != 1:
        raise SystemExit("verify evidence loop marker missing")
    text = text.replace(old_verify_loop, new_verify_loop, 1)
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = Path("tests/test_reality_acceptance.py")
    text = path.read_text(encoding="utf-8")
    old_artifacts = '  self._write_json("artifacts.json",self._contract(M.ARTIFACT_SCHEMA,{"ready":True,"artifact_classes":[]})); self._write_json("evaluators.json",self._contract(M.EVALUATOR_SCHEMA,{"ready":True,"evaluators":[]})); self._write_json("benchmarks.json",self._contract(M.BENCHMARK_SCHEMA,{"ready":True,"benchmarks":[]}))'
    new_artifacts = '  self._write_json("artifacts.json",self._contract(M.ARTIFACT_SCHEMA,{"ready":True,"artifact_classes":[{"artifact_class_id":"playable_game","required":True,"required_evidence":["interaction_trace"]}]})); self._write_json("evaluators.json",self._contract(M.EVALUATOR_SCHEMA,{"ready":True,"evaluators":[]})); self._write_json("benchmarks.json",self._contract(M.BENCHMARK_SCHEMA,{"ready":True,"benchmarks":[]}))'
    if text.count(old_artifacts) != 1:
        raise SystemExit("artifact fixture marker missing")
    text = text.replace(old_artifacts, new_artifacts, 1)
    old_eval = '  artifact=self.project/"game.bin"; artifact.write_bytes(b"playable"); self.artifact_sha=M.file_digest(artifact)\n  self._write_json("eval.json",{"$schema":"company-os.evaluator-execution-receipt.v1","schema_version":1,"objective_id":self.objective_id,"evaluator_id":"gameplay","production_actor_ids":["worker"],"independent_role":True,"accepted":True,"receipt_sha256":"d"*64})'
    new_eval = '  artifact=self.project/"game.bin"; artifact.write_bytes(b"playable"); self.artifact_sha=M.file_digest(artifact)\n  trace=self.project/"interaction.json"; trace.write_text("{}\\n"); trace_sha=M.file_digest(trace)\n  self._write_json("eval.json",{"$schema":"company-os.evaluator-execution-receipt.v1","schema_version":1,"objective_id":self.objective_id,"evaluator_id":"gameplay","production_actor_ids":["worker"],"independent_role":True,"accepted":True,"evidence_bindings":[{"evidence_id":"interaction","evidence_type":"interaction_trace","path":"interaction.json","sha256":trace_sha,"size":trace.stat().st_size}],"receipt_sha256":"d"*64})'
    if text.count(old_eval) != 1:
        raise SystemExit("evaluation fixture marker missing")
    text = text.replace(old_eval, new_eval, 1)
    marker = ''' def test_artifact_drift_invalidates_existing_reality_receipt(self):
  receipt=M.accept(self.project,self.request()); (self.project/"game.bin").write_bytes(b"changed")
  with self.assertRaises(M.RealityError) as ctx: M.verify_receipt(self.project,receipt)
  self.assertEqual(ctx.exception.code,"E_DIGEST")
'''
    replacement = ''' def test_required_observation_evidence_is_not_optional(self):
  evaluation=json.loads((self.project/"eval.json").read_text()); evaluation["evidence_bindings"]=[]; self._write_json("eval.json",evaluation)
  receipt=M.accept(self.project,self.request()); self.assertFalse(receipt["accepted"])
  self.assertEqual({item["code"] for item in receipt["blockers"]},{"REQUIRED_OBSERVATION_EVIDENCE_MISSING"})
 def test_artifact_drift_invalidates_existing_reality_receipt(self):
  receipt=M.accept(self.project,self.request()); (self.project/"game.bin").write_bytes(b"changed")
  with self.assertRaises(M.RealityError) as ctx: M.verify_receipt(self.project,receipt)
  self.assertEqual(ctx.exception.code,"E_DIGEST")
'''
    if text.count(marker) != 1:
        raise SystemExit("test insertion marker missing")
    text = text.replace(marker, replacement, 1)
    path.write_text(text, encoding="utf-8")


patch_reality()
patch_tests()
print("observation evidence acceptance applied")
