#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, Mapping
SCHEMA="company-os.reality-acceptance-request.v1"; OUT="company-os.reality-acceptance-receipt.v1"
class RealityError(ValueError):
 def __init__(self,code,msg): self.code=code; super().__init__(f"{code}: {msg}")
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def digest(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()
def text(v,l):
 if not isinstance(v,str) or not v.strip(): raise RealityError("E_SCHEMA",f"{l} must be nonempty")
 return v
def accept(req:Mapping[str,Any])->dict[str,Any]:
 if req.get("$schema")!=SCHEMA: raise RealityError("E_SCHEMA","bad schema")
 oid=text(req.get("objective_id"),"objective_id"); objective=text(req.get("original_objective"),"original_objective")
 if req.get("production_narrative_admissible") is not False: raise RealityError("E_AUTHORITY","production narrative must be inadmissible")
 calibrations=req.get("calibration_receipts")
 if not isinstance(calibrations,list) or not calibrations: raise RealityError("E_EVIDENCE","calibration receipts required")
 if any(not isinstance(x,dict) or x.get("passed") is not True for x in calibrations): raise RealityError("E_CALIBRATION","all evaluator calibrations must pass")
 claims=req.get("claims")
 if not isinstance(claims,list) or not claims: raise RealityError("E_SCHEMA","claims must be nonempty")
 seen=set(); decisions=[]; blockers=[]
 for c in claims:
  if not isinstance(c,dict): raise RealityError("E_SCHEMA","claim")
  cid=text(c.get("claim_id"),"claim_id")
  if cid in seen: raise RealityError("E_DUPLICATE",cid)
  seen.add(cid); statement=text(c.get("statement"),f"{cid}.statement"); required=c.get("required",True)
  if not isinstance(required,bool): raise RealityError("E_SCHEMA",cid)
  artifact=c.get("artifact_evidence"); evals=c.get("evaluator_receipts")
  if not isinstance(artifact,list): raise RealityError("E_SCHEMA",f"{cid}.artifact_evidence")
  if not isinstance(evals,list): raise RealityError("E_SCHEMA",f"{cid}.evaluator_receipts")
  evidence_ok=bool(artifact)
  independent_ok=bool(evals) and all(isinstance(e,dict) and e.get("independent_role") is True and e.get("accepted") is True for e in evals)
  passed=evidence_ok and independent_ok
  if required and not evidence_ok: blockers.append({"claim_id":cid,"code":"NO_ARTIFACT_EVIDENCE"})
  if required and not independent_ok: blockers.append({"claim_id":cid,"code":"INDEPENDENT_EVALUATION_FAILED"})
  decisions.append({"claim_id":cid,"statement":statement,"required":required,"passed":passed,
                    "artifact_evidence_count":len(artifact),"evaluator_receipt_count":len(evals)})
 blockers=sorted(blockers,key=lambda x:(x["claim_id"],x["code"]))
 accepted=not blockers and all((not d["required"]) or d["passed"] for d in decisions)
 out={"$schema":OUT,"schema_version":1,"objective_id":oid,"original_objective":objective,
      "original_objective_sha256":hashlib.sha256(objective.encode()).hexdigest(),
      "claim_decisions":sorted(decisions,key=lambda x:x["claim_id"]),"blockers":blockers,"accepted":accepted}
 out["receipt_sha256"]=digest({**out,"receipt_sha256":None});return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--request",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
 o=accept(json.loads(a.request.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n");print(f"reality accepted={o['accepted']} blockers={len(o['blockers'])}")
if __name__=="__main__":main()
