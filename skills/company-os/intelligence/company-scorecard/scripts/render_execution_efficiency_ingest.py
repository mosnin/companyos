#!/usr/bin/env python3
"""Render deterministic, provider-neutral Postgres ingestion SQL for one receipt."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import validate_execution_efficiency as validator


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sql_text(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def _jsonb_from_bytes(raw: bytes) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"convert_from(decode('{encoded}', 'base64'), 'UTF8')::jsonb"


def _text_from_bytes(raw: bytes) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"convert_from(decode('{encoded}', 'base64'), 'UTF8')"


def render_ingest_sql(
    receipt: dict[str, Any],
    *,
    source: str,
    workspace_id: str,
    workspace_name: str,
    project_id: str,
    project_name: str,
    run_id: str,
    framework_version_id: str,
    framework_source_commit: str | None,
    source_thread_id: str | None,
    supersedes_receipt_sha256: str | None,
) -> tuple[str, str, dict[str, Any]]:
    validation = validator.validate_receipt(receipt, source)
    if not validation["ok"]:
        raise validator.ReceiptError(
            "receipt failed validation: " + "; ".join(validation["errors"])
        )
    receipt_bytes = _canonical_bytes(receipt)
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    validation_bytes = _canonical_bytes(
        {
            **{
                key: value
                for key, value in validation.items()
                if key != "_aggregate"
            },
            "receipt_sha256": receipt_sha256,
        }
    )
    sql = "\n".join(
        [
            "BEGIN;",
            "SELECT company_os_observatory.ingest_execution_efficiency_receipt(",
            f"    {_sql_text(workspace_id)},",
            f"    {_sql_text(workspace_name)},",
            f"    {_sql_text(project_id)},",
            f"    {_sql_text(project_name)},",
            f"    {_sql_text(run_id)},",
            f"    {_sql_text(framework_version_id)},",
            f"    {_sql_text(framework_source_commit)},",
            f"    {_sql_text(source_thread_id)},",
            f"    {_sql_text(receipt_sha256)},",
            f"    {_sql_text(supersedes_receipt_sha256)},",
            f"    {_text_from_bytes(receipt_bytes)},",
            f"    {_jsonb_from_bytes(validation_bytes)}",
            ");",
            "COMMIT;",
            "",
        ]
    )
    return sql, receipt_sha256, validation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--framework-version-id", required=True)
    parser.add_argument("--framework-source-commit")
    parser.add_argument("--source-thread-id")
    parser.add_argument("--supersedes-receipt-sha256")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        receipt = validator._load_receipt(args.receipt)
        sql, _, _ = render_ingest_sql(
            receipt,
            source=str(args.receipt),
            workspace_id=args.workspace_id,
            workspace_name=args.workspace_name,
            project_id=args.project_id,
            project_name=args.project_name,
            run_id=args.run_id,
            framework_version_id=args.framework_version_id,
            framework_source_commit=args.framework_source_commit,
            source_thread_id=args.source_thread_id,
            supersedes_receipt_sha256=args.supersedes_receipt_sha256,
        )
    except (OSError, validator.ReceiptError) as error:
        sys.stderr.write(str(error) + "\n")
        return 1
    sys.stdout.write(sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
