#!/usr/bin/env python3
"""Compile rich artifact observation contracts."""

from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, Mapping

SCHEMA="company-os.artifact-observation-request.v1"
OUT="company-os.artifact-observation-contract.v1"
RICH_MODALITIES={"interactive","visual","audio","executable","service","database","model","physical","composite"}
WEAK_METHODS={"file_exists","nonempty","normalized_nonempty","hash_matches","build_succeeds","text_review"}

class ArtifactError(ValueError):
    def __init__(self, code:str, message:str)->None:
        self.code=code
        super().__init__(f"{code}: {message}")

def canonical(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def digest(v:Any)->str:
    return hashlib.sha256(canonical(v)).hexdigest()

def text(v:Any,label:str)->str:
    if not isinstance(v,str) or not v.strip(): raise ArtifactError("E_SCHEMA",f"{label} must be non-empty")
    return v

def strings(v:Any,label:str)->list[str]:
    if not isinstance(v,list): raise ArtifactError("E_SCHEMA",f"{label} must be an array")
    out=[text(x,f"{label}[]") for x in v]
    if len(out)!=len(set(out)): raise ArtifactError("E_DUPLICATE",f"{label} contains duplicates")
    return sorted(out)

def compile_contract(req:Mapping[str,Any])->dict[str,Any]:
    if req.get("$schema")!=SCHEMA: raise ArtifactError("E_SCHEMA",f"$schema must be {SCHEMA}")
    objective_id=text(req.get("objective_id"),"objective_id")
    items=req.get("artifact_classes")
    if not isinstance(items,list) or not items: raise ArtifactError("E_SCHEMA","artifact_classes must be nonempty")
    seen=set(); normalized=[]; blockers=[]
    for raw in items:
        if not isinstance(raw,dict): raise ArtifactError("E_SCHEMA","artifact class must be object")
        aid=text(raw.get("artifact_class_id"),"artifact_class_id")
        if aid in seen: raise ArtifactError("E_DUPLICATE",aid)
        seen.add(aid)
        label=text(raw.get("label"),f"{aid}.label")
        modalities=strings(raw.get("modalities"),f"{aid}.modalities")
        if not modalities: raise ArtifactError("E_SCHEMA",f"{aid} needs modalities")
        methods=strings(raw.get("observation_methods"),f"{aid}.observation_methods")
        evidence=strings(raw.get("required_evidence"),f"{aid}.required_evidence")
        required=raw.get("required",True)
        if not isinstance(required,bool): raise ArtifactError("E_SCHEMA",f"{aid}.required must be boolean")
        rich=bool(set(modalities)&RICH_MODALITIES)
        strong=[m for m in methods if m not in WEAK_METHODS]
        if required and not methods:
            blockers.append({"artifact_class_id":aid,"code":"NO_OBSERVATION_METHOD"})
        if required and rich and not strong:
            blockers.append({"artifact_class_id":aid,"code":"RICH_ARTIFACT_TEXT_ONLY"})
        # Executed evidence only: a REQUIRED class observed solely through weak
        # methods (text_review, file_exists, hashes, ...) can be satisfied by a
        # prose document, which is exactly the currency that lets planning
        # substitute for acting. Every required class must carry at least one
        # executed observation method; a document-shaped deliverable either
        # gains an executable check or is declared required:false (advisory).
        if required and methods and not strong:
            blockers.append({"artifact_class_id":aid,"code":"TEXT_ONLY_OBSERVATION"})
        if required and not evidence:
            blockers.append({"artifact_class_id":aid,"code":"NO_CAPTURED_EVIDENCE"})
        normalized.append({
            "artifact_class_id":aid,"label":label,"required":required,
            "modalities":modalities,"observation_methods":methods,
            "required_evidence":evidence,"rich":rich,
        })
    blockers=sorted(blockers,key=lambda x:(x["artifact_class_id"],x["code"]))
    result={"$schema":OUT,"schema_version":1,"objective_id":objective_id,
            "artifact_classes":sorted(normalized,key=lambda x:x["artifact_class_id"]),
            "blockers":blockers,"ready":not blockers}
    result["contract_sha256"]=digest({**result,"contract_sha256":None})
    return result

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("--request",type=Path,required=True); p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(); req=json.loads(a.request.read_text()); out=compile_contract(req)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(f"compiled artifact contract ready={out['ready']} blockers={len(out['blockers'])}")
if __name__=="__main__": main()
