#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, Mapping
SCHEMA="company-os.benchmark-request.v1"; OUT="company-os.benchmark-contract.v1"
class BenchmarkError(ValueError):
 def __init__(self,code,msg): self.code=code; super().__init__(f"{code}: {msg}")
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def digest(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()
def text(v,l):
 if not isinstance(v,str) or not v.strip(): raise BenchmarkError("E_SCHEMA",f"{l} must be nonempty")
 return v
def compile_contract(req:Mapping[str,Any])->dict[str,Any]:
 if req.get("$schema")!=SCHEMA: raise BenchmarkError("E_SCHEMA","bad schema")
 oid=text(req.get("objective_id"),"objective_id"); dims=req.get("dimensions")
 if not isinstance(dims,list) or not dims: raise BenchmarkError("E_SCHEMA","dimensions must be nonempty")
 seen=set(); norm=[]; blockers=[]
 for d in dims:
  if not isinstance(d,dict): raise BenchmarkError("E_SCHEMA","dimension must be object")
  did=text(d.get("dimension_id"),"dimension_id")
  if did in seen: raise BenchmarkError("E_DUPLICATE",did)
  seen.add(did); label=text(d.get("label"),f"{did}.label"); required=d.get("required",True)
  if not isinstance(required,bool): raise BenchmarkError("E_SCHEMA",did)
  refs=d.get("references")
  if not isinstance(refs,list): raise BenchmarkError("E_SCHEMA",f"{did}.references")
  rseen=set(); nrefs=[]; tiers=set()
  for r in refs:
   if not isinstance(r,dict): raise BenchmarkError("E_SCHEMA","reference must be object")
   rid=text(r.get("reference_id"),"reference_id")
   if rid in rseen: raise BenchmarkError("E_DUPLICATE",rid)
   rseen.add(rid); locator=text(r.get("locator"),f"{rid}.locator"); provenance=text(r.get("provenance"),f"{rid}.provenance")
   tier=r.get("quality_tier")
   if tier not in {"negative","baseline","strong","exemplar"}: raise BenchmarkError("E_SCHEMA",f"{rid}.quality_tier")
   tiers.add(tier); nrefs.append({"reference_id":rid,"locator":locator,"provenance":provenance,"quality_tier":tier})
  if required and not nrefs: blockers.append({"dimension_id":did,"code":"NO_REFERENCES"})
  if required and not tiers.intersection({"strong","exemplar"}): blockers.append({"dimension_id":did,"code":"NO_POSITIVE_ANCHOR"})
  if required and len(tiers)<2: blockers.append({"dimension_id":did,"code":"NO_DISCRIMINATION_TIERS"})
  norm.append({"dimension_id":did,"label":label,"required":required,"references":sorted(nrefs,key=lambda x:x["reference_id"])})
 blockers=sorted(blockers,key=lambda x:(x["dimension_id"],x["code"]))
 out={"$schema":OUT,"schema_version":1,"objective_id":oid,"dimensions":sorted(norm,key=lambda x:x["dimension_id"]),"blockers":blockers,"ready":not blockers}
 out["contract_sha256"]=digest({**out,"contract_sha256":None});return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--request",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
 o=compile_contract(json.loads(a.request.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n");print(f"compiled benchmarks ready={o['ready']}")
if __name__=="__main__":main()
