#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, Mapping
SCHEMA="company-os.evaluator-calibration.v1"; OUT="company-os.evaluator-calibration-receipt.v1"
class CalibrationError(ValueError):
 def __init__(self,code,msg): self.code=code; super().__init__(f"{code}: {msg}")
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def digest(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()
def text(v,l):
 if not isinstance(v,str) or not v.strip(): raise CalibrationError("E_SCHEMA",f"{l} must be nonempty")
 return v
def calibrate(req:Mapping[str,Any])->dict[str,Any]:
 if req.get("$schema")!=SCHEMA: raise CalibrationError("E_SCHEMA","bad schema")
 eid=text(req.get("evaluator_id"),"evaluator_id"); dims=req.get("required_dimensions"); cands=req.get("candidates")
 if not isinstance(dims,list) or not dims or not all(isinstance(x,str) and x for x in dims): raise CalibrationError("E_SCHEMA","required_dimensions")
 if len(dims)!=len(set(dims)): raise CalibrationError("E_DUPLICATE","required_dimensions")
 if not isinstance(cands,list) or len(cands)<3: raise CalibrationError("E_SCHEMA","need at least three calibration candidates")
 seen=set(); ordered=[]
 for c in cands:
  if not isinstance(c,dict): raise CalibrationError("E_SCHEMA","candidate")
  cid=text(c.get("candidate_id"),"candidate_id")
  if cid in seen: raise CalibrationError("E_DUPLICATE",cid)
  seen.add(cid); expected=c.get("expected_rank"); scores=c.get("scores")
  if not isinstance(expected,int) or isinstance(expected,bool) or expected<1: raise CalibrationError("E_SCHEMA",f"{cid}.expected_rank")
  if not isinstance(scores,dict): raise CalibrationError("E_SCHEMA",f"{cid}.scores")
  clean={}
  for d in dims:
   v=scores.get(d)
   if not isinstance(v,(int,float)) or isinstance(v,bool): raise CalibrationError("E_SCHEMA",f"{cid}.scores.{d}")
   clean[d]=float(v)
  ordered.append({"candidate_id":cid,"expected_rank":expected,"scores":clean})
 ranks=[c["expected_rank"] for c in ordered]
 if len(ranks)!=len(set(ranks)) or sorted(ranks)!=list(range(1,len(ranks)+1)): raise CalibrationError("E_SCHEMA","expected ranks must be unique contiguous")
 by_rank=sorted(ordered,key=lambda x:x["expected_rank"]); failures=[]
 for d in dims:
  vals=[c["scores"][d] for c in by_rank]
  for i in range(len(vals)-1):
   if not vals[i] < vals[i+1]:
    failures.append({"dimension":d,"lower_candidate":by_rank[i]["candidate_id"],"higher_candidate":by_rank[i+1]["candidate_id"],"lower_score":vals[i],"higher_score":vals[i+1]})
 out={"$schema":OUT,"schema_version":1,"evaluator_id":eid,"candidate_count":len(ordered),"required_dimensions":sorted(dims),
      "pairwise_failures":failures,"passed":not failures}
 out["receipt_sha256"]=digest({**out,"receipt_sha256":None}); return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--request",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
 o=calibrate(json.loads(a.request.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n");print(f"calibration passed={o['passed']} failures={len(o['pairwise_failures'])}")
if __name__=="__main__":main()
