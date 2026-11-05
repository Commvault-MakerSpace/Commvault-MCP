# --------------------------------------------------------------------------
# Copyright Commvault Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# --------------------------------------------------------------------------
# Modified from Commvault/commvault-mcp-server for cv-mcp.
"""CommCell-level dashboards: report datasets, SLA counts and the security posture."""

from __future__ import annotations

from typing import Any

from cv_mcp.shaping.jobs import clean_text

# Report-engine bookkeeping columns that carry nothing for the reader.
_NOISE_COLUMNS = frozenset({"sys_rowid", "Data Source"})

# Security/Dashboard parameter status codes as used by the Command Center UI.
SECURITY_STATUS = {0: "good", 1: "warning", 2: "not following recommendation"}


def format_report_dataset_response(api_response: dict[str, Any]) -> dict[str, Any]:
    """Turn a report dataset (columns + row arrays) into a list of dicts keyed by column name."""
    column_names = [col.get("name") for col in api_response.get("columns", [])]
    records = []
    for record in api_response.get("records", []):
        row = {name: value for name, value in zip(column_names, record, strict=False)}
        records.append({k: v for k, v in row.items() if k not in _NOISE_COLUMNS})
    return {"totalRecordCount": api_response.get("totalRecordCount", len(records)), "records": records}


def _column_index(columns: list[dict[str, Any]], wanted: str, default: int) -> int:
    key = wanted.replace(" ", "").lower()
    for i, col in enumerate(columns):
        if str(col.get("name", "")).replace(" ", "").lower() == key:
            return i
    return default


def transform_sla_data(api_response: dict[str, Any]) -> dict[str, Any]:
    """SLA dashboard counts per status plus 'SLA Percentage' = met / (met + missed) * 100."""
    columns = api_response.get("columns", [])
    status_idx = _column_index(columns, "SLAStatus", 2)
    count_idx = _column_index(columns, "CurrentCount", 3)
    result: dict[str, Any] = {}
    for record in api_response.get("records", []):
        if len(record) <= max(status_idx, count_idx):
            continue
        status, count = record[status_idx], record[count_idx]
        if isinstance(status, str):
            result[status] = count
    met = result.get("Met SLA", 0) or 0
    missed = result.get("Missed SLA", 0) or 0
    total = met + missed
    result["SLA Percentage"] = round(met / total * 100, 2) if total else 0
    return result


def _parameters(api_response: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for cat in api_response.get("securityCategories", []):
        for p in cat.get("parameter", []):
            out.append(
                {
                    "category": cat.get("category"),
                    "parameter": p.get("paramName"),
                    "status": p.get("status"),
                    "statusText": SECURITY_STATUS.get(p.get("status"), str(p.get("status"))),
                    "currentSetting": clean_text(p.get("currentSetting")),
                    "recommendation": clean_text(p.get("recommendation")),
                }
            )
    return out


def compute_security_score(api_response: dict[str, Any]) -> dict[str, Any]:
    """Score = parameters not in status 2 / all parameters * 100, plus the list of failing parameters."""
    params = _parameters(api_response)
    if not params:
        raise ValueError("Security dashboard returned no parameters")
    failures = [p for p in params if p["status"] == 2]
    return {
        "security_score": round((len(params) - len(failures)) / len(params) * 100),
        "checked": len(params),
        "failed": len(failures),
        "failures": failures,
    }


def security_posture(api_response: dict[str, Any]) -> dict[str, Any]:
    """All security parameters with status text, current setting, recommendation and plain-text remarks."""
    params = _parameters(api_response)
    for p, raw in zip(
        params,
        (p for cat in api_response.get("securityCategories", []) for p in cat.get("parameter", [])),
        strict=False,
    ):
        remarks = clean_text(raw.get("remarks"))
        if remarks:
            p["remarks"] = remarks
    counts = {text: sum(1 for p in params if p["statusText"] == text) for text in SECURITY_STATUS.values()}
    return {"summary": counts, "parameters": params}
