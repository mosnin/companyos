#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any, Mapping
SCHEMA="company-os.evaluator-runtime-request.v1"; OUT="company-os.evaluator-runtime-contract.v1"
LOC=re.compile(r"^(?:tool|runtime|module|workspace)://[a-zA-Z0-9._/-]+$")
class EvaluatorError(ValueError):
    def __init__(self,code:str,msg:str): self.code=code; super().__init__(f"{code}: {msg}")
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def digest(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()
def text(v:Any,l:str)->str:
    if not isinstance(v,str) or not v.strip(): raise EvaluatorError("E_SCHEMA",f"{l} must be nonempty")
    return v
def strings(v:Any,l:str)->list[str]:
    if not isinstance(v,list): raise EvaluatorError("E_SCHEMA",f"{l} must be array")
    out=[text(x,l) for x in v]
    if len(out)!=len(set(out)): raise EvaluatorError("E_DUPLICATE",l)
    return sorted(out)
def compile_contract(req:Mapping[str,Any])->dict[str,Any]:
    if req.get("$schema")!=SCHEMA: raise EvaluatorError("E_SCHEMA","bad schema")
    objective=text(req.get("objective_id"),"objective_id"); items=req.get("evaluators")
    if not isinstance(items,list) or not items: raise EvaluatorError("E_SCHEMA","evaluators must be nonempty")
    seen=set(); out=[]; blockers=[]
    for raw in items:
        if not isinstance(raw,dict): raise EvaluatorError("E_SCHEMA","evaluator must be object")
        eid=text(raw.get("evaluator_id"),"evaluator_id")
        if eid in seen: raise EvaluatorError("E_DUPLICATE",eid)
        seen.add(eid); label=text(raw.get("label"),f"{eid}.label")
        required=raw.get("required",True); independent=raw.get("independent_role",False); research=raw.get("research_only",False)
        if not isinstance(required,bool) or not isinstance(independent,bool) or not isinstance(research,bool): raise EvaluatorError("E_SCHEMA",eid)
        consumes=strings(raw.get("artifact_classes"),f"{eid}.artifact_classes")
        evidence=strings(raw.get("produces_evidence"),f"{eid}.produces_evidence")
        dims=strings(raw.get("score_dimensions",[]),f"{eid}.score_dimensions")
        adapter=raw.get("adapter_locator")
        if adapter is not None: adapter=text(adapter,f"{eid}.adapter_locator")
        if required and research: blockers.append({"evaluator_id":eid,"code":"RESEARCH_ONLY"})
        if required and not independent: blockers.append({"evaluator_id":eid,"code":"NOT_INDEPENDENT"})
        if required and (not isinstance(adapter,str) or LOC.fullmatch(adapter) is None):
            blockers.append({"evaluator_id":eid,"code":"NO_EXECUTABLE_ADAPTER"})
        if required and not consumes: blockers.append({"evaluator_id":eid,"code":"NO_ARTIFACT_COVERAGE"})
        if required and not evidence: blockers.append({"evaluator_id":eid,"code":"NO_EVIDENCE_OUTPUT"})
        out.append({"evaluator_id":eid,"label":label,"required":required,"independent_role":independent,
                    "research_only":research,"adapter_locator":adapter,"artifact_classes":consumes,
                    "produces_evidence":evidence,"score_dimensions":dims})
    blockers=sorted(blockers,key=lambda x:(x["evaluator_id"],x["code"]))
    result={"$schema":OUT,"schema_version":1,"objective_id":objective,
            "evaluators":sorted(out,key=lambda x:x["evaluator_id"]),"blockers":blockers,"ready":not blockers}
    result["contract_sha256"]=digest({**result,"contract_sha256":None}); return result
def main():
    p=argparse.ArgumentParser();p.add_argument("--request",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    out=compile_contract(json.loads(a.request.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(f"compiled evaluator runtime ready={out['ready']} blockers={len(out['blockers'])}")
if __name__=="__main__":main()
