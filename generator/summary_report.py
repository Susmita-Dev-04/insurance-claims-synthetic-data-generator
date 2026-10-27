
"""
Insurance Claims Synthetic Data Generator
=========================================
Professional, consolidated reporting for clean and edge-case datasets.

Outputs:
    summary_report.html  - Styled executive dashboard
    summary_report.json  - Structured machine-readable report
    summary_report.csv   - KPI/metric export
    summary_report.md    - Human-readable Markdown report

Example:
    python -m generator.summary_report \
        --data data \
        --edge-data data_edge_cases \
        --out reports

Optional explicit audit inputs:
    --audit-report data/clean_audit.csv
    --edge-audit-report data_edge_cases/audit_mismatches.csv
    --validation-report data/validation_report.csv
    --edge-validation-report data_edge_cases/validation_report.csv

Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_TITLE = "Insurance Claims Synthetic Data Generator"
REPORT_VERSION = "1.0"

# The project has 15 expected transactional tables.
EXPECTED_TABLES = [
    "customer",
    "coverage",
    "policy",
    "policy_coverage",
    "adjuster",
    "incident",
    "claim",
    "claim_item",
    "document",
    "claim_assignment",
    "assessment",
    "assessment_check",
    "reserve",
    "settlement",
    "claim_status_event",
]

# Candidate column names allow the report to work across minor schema
# naming differences without silently assuming that every field exists.
ALIASES = {
    "claim_id": ["claim_id", "claimid"],
    "policy_id": ["policy_id", "policyid"],
    "customer_id": ["customer_id", "customerid"],
    "incident_id": ["incident_id", "incidentid"],
    "incident_type": ["incident_type", "claim_type", "incident_category"],
    "incident_date": ["incident_date", "date_of_incident", "loss_date"],
    "claim_date": ["claim_date", "reported_date", "report_date"],
    "claim_amount": [
        "claimed_amount", "claim_amount", "requested_amount",
        "amount_claimed", "total_claimed_amount",
    ],
    "approved_amount": [
        "approved_amount", "assessed_amount", "assessment_amount",
        "payable_amount",
    ],
    "assessment_outcome": [
        "eligibility_status", "assessment_outcome", "outcome",
        "decision", "claim_decision",
    ],
    "reason_code": ["reason_code", "decision_reason", "reason"],
    "fraud_score": ["fraud_score", "risk_score"],
    "claim_status": ["claim_status", "status", "current_status"],
    "assessment_id": ["assessment_id", "assessmentid"],
    "reserve_amount": [
        "reserve_amount", "reserve", "reserved_amount",
        "outstanding_reserve", "amount",
    ],
    "settlement_amount": [
        "settlement_amount", "paid_amount", "payment_amount",
        "settled_amount", "amount_paid", "amount",
    ],
    "check_code": ["check_code", "check_id", "rule_code"],
    "check_result": ["check_result", "passed", "is_passed", "result"],
    "is_mandatory": ["is_mandatory", "mandatory"],
    "received_date": ["received_date", "document_received_date"],
    "assessed_date": ["assessed_date", "assessment_date"],
    "status_event": ["status", "claim_status", "event_status", "to_status"],
    "event_date": ["event_date", "status_date", "created_at", "timestamp"],
    "exclusions": ["exclusions", "excluded_perils", "exclusion"],
}


def normalise_name(value: str) -> str:
    """Normalise a column/table name for case-insensitive matching."""
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV as dictionaries; return an empty list if it does not exist."""
    if not path.is_file():
        return []

    # utf-8-sig handles CSV files exported with a BOM.
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_column(
    rows: list[dict[str, Any]],
    logical_name: str,
    extra_aliases: Iterable[str] | None = None,
) -> str | None:
    """Find the actual column name matching a logical field."""
    if not rows:
        return None

    existing = list(rows[0].keys())
    lookup = {normalise_name(name): name for name in existing}

    candidates = list(ALIASES.get(logical_name, []))
    if extra_aliases:
        candidates.extend(extra_aliases)

    for candidate in candidates:
        found = lookup.get(normalise_name(candidate))
        if found is not None:
            return found

    return None


def value_of(
    row: dict[str, Any],
    column: str | None,
    default: Any = None,
) -> Any:
    if column is None:
        return default
    value = row.get(column)
    if value is None or str(value).strip() == "":
        return default
    return value


def parse_number(value: Any) -> float | None:
    """Convert common numeric/currency representations into a number."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.replace(",", "").replace("₹", "").replace("$", "")
    raw = raw.replace("INR", "").replace("Rs.", "").replace("Rs", "")
    raw = raw.strip().replace("%", "")

    if negative:
        raw = raw[1:-1].strip()

    try:
        number = float(raw)
        if not math.isfinite(number):
            return None
        return -abs(number) if negative else number
    except (TypeError, ValueError):
        return None


def money(value: float | int | None) -> float | None:
    """Round monetary totals to two decimal places."""
    if value is None:
        return None
    return round(float(value), 2)


def sum_column(
    rows: list[dict[str, Any]],
    logical_name: str,
    extra_aliases: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Summarise a numeric column without treating missing values as zero."""
    column = find_column(rows, logical_name, extra_aliases)
    if column is None:
        return {
            "available": False,
            "column": None,
            "count": 0,
            "total": None,
            "average": None,
            "minimum": None,
            "maximum": None,
        }

    values = [
        number
        for row in rows
        if (number := parse_number(row.get(column))) is not None
    ]

    if not values:
        return {
            "available": True,
            "column": column,
            "count": 0,
            "total": None,
            "average": None,
            "minimum": None,
            "maximum": None,
        }

    return {
        "available": True,
        "column": column,
        "count": len(values),
        "total": money(sum(values)),
        "average": money(sum(values) / len(values)),
        "minimum": money(min(values)),
        "maximum": money(max(values)),
    }


def distribution(
    rows: list[dict[str, Any]],
    logical_name: str,
    extra_aliases: Iterable[str] | None = None,
) -> dict[str, int] | None:
    """Count distinct values in a categorical field."""
    column = find_column(rows, logical_name, extra_aliases)
    if column is None:
        return None

    counts: Counter[str] = Counter()
    for row in rows:
        value = value_of(row, column)
        if value is not None:
            counts[str(value).strip()] += 1

    return dict(sorted(counts.items(), key=lambda item: item[0].lower()))


def missing_required_values(
    rows: list[dict[str, Any]],
    required_columns: list[str],
) -> dict[str, int]:
    """Count empty values for known required columns that actually exist."""
    if not rows:
        return {}

    lookup = {normalise_name(name): name for name in rows[0].keys()}
    result: dict[str, int] = {}

    for required in required_columns:
        column = lookup.get(normalise_name(required))
        if column is None:
            continue

        count = sum(
            1
            for row in rows
            if row.get(column) is None or str(row.get(column)).strip() == ""
        )
        result[required] = count

    return result


def inspect_dataset(data_dir: Path) -> dict[str, Any]:
    """Inventory tables and calculate data-quality and business summaries."""
    tables: dict[str, list[dict[str, str]]] = {}
    table_inventory: list[dict[str, Any]] = []
    total_rows = 0
    missing_tables: list[str] = []

    for table_name in EXPECTED_TABLES:
        path = data_dir / f"{table_name}.csv"
        rows = read_csv(path)
        tables[table_name] = rows

        exists = path.is_file()
        total_rows += len(rows)

        if not exists:
            missing_tables.append(table_name)

        table_inventory.append(
            {
                "table": table_name,
                "file": path.name,
                "exists": exists,
                "rows": len(rows),
                "columns": list(rows[0].keys()) if rows else [],
                "column_count": len(rows[0].keys()) if rows else 0,
            }
        )

    claims = tables["claim"]
    assessments = tables["assessment"]
    checks = tables["assessment_check"]
    reserves = tables["reserve"]
    settlements = tables["settlement"]
    documents = tables["document"]
    policies = tables["policy"]
    customers = tables["customer"]
    events = tables["claim_status_event"]

    claim_amounts = sum_column(claims, "claim_amount")
    approved_amounts = sum_column(assessments, "approved_amount")
    reserve_amounts = sum_column(reserves, "reserve_amount")
    settlement_amounts = sum_column(settlements, "settlement_amount")

    # Avoid presenting an unrelated "amount" column as a confirmed reserve
    # or settlement value if the specific amount column cannot be found.
    claim_outcomes = distribution(assessments, "assessment_outcome")
    claim_statuses = distribution(claims, "claim_status")
    check_results = distribution(checks, "check_result")
    check_codes = distribution(checks, "check_code")
    document_types = distribution(documents, "check_code", ["doc_type", "document_type"])

    # Fraud scores are optional in the assessment table.
    fraud_column = find_column(assessments, "fraud_score")
    fraud_values = (
        [
            number
            for row in assessments
            if (number := parse_number(row.get(fraud_column))) is not None
        ]
        if fraud_column
        else []
    )

    fraud_summary = {
        "available": fraud_column is not None,
        "column": fraud_column,
        "scored_assessments": len(fraud_values),
        "average_score": money(sum(fraud_values) / len(fraud_values))
        if fraud_values
        else None,
        "scores_at_or_above_50": sum(score >= 50 for score in fraud_values)
        if fraud_values
        else None,
    }

    # Detect duplicate business keys if the relevant claim columns exist.
    policy_col = find_column(claims, "policy_id")
    incident_type_col = find_column(claims, "incident_type")
    incident_date_col = find_column(claims, "incident_date")
    duplicate_groups: dict[tuple[str, str, str], list[str]] = {}

    claim_id_col = find_column(claims, "claim_id")
    if policy_col and incident_type_col and incident_date_col:
        for row in claims:
            key_parts = (
                str(value_of(row, policy_col, "")).strip(),
                str(value_of(row, incident_type_col, "")).strip(),
                str(value_of(row, incident_date_col, "")).strip(),
            )
            if all(key_parts):
                duplicate_groups.setdefault(key_parts, []).append(
                    str(value_of(row, claim_id_col, "UNKNOWN"))
                )

    duplicate_groups = {
        key: ids for key, ids in duplicate_groups.items() if len(ids) > 1
    }

    # Basic document completeness profile; this is descriptive and does not
    # replace the authoritative CHK04 logic in rederive.py.
    mandatory_col = find_column(documents, "is_mandatory")
    received_col = find_column(documents, "received_date")
    doc_type_col = next(
        (
            name
            for name in (documents[0].keys() if documents else [])
            if normalise_name(name) in {"doctype", "documenttype"}
        ),
        None,
    )

    mandatory_document_rows = 0
    received_mandatory_documents = 0
    if mandatory_col:
        for row in documents:
            mandatory_value = str(row.get(mandatory_col, "")).strip().upper()
            if mandatory_value in {"TRUE", "1", "YES", "Y"}:
                mandatory_document_rows += 1
                if received_col and value_of(row, received_col) is not None:
                    received_mandatory_documents += 1

    document_summary = {
        "total_document_records": len(documents),
        "mandatory_document_records": mandatory_document_rows
        if mandatory_col
        else None,
        "mandatory_documents_with_received_date": received_mandatory_documents
        if mandatory_col and received_col
        else None,
        "mandatory_document_received_rate_pct": (
            money(100 * received_mandatory_documents / mandatory_document_rows)
            if mandatory_col and received_col and mandatory_document_rows
            else None
        ),
        "document_type_column_available": doc_type_col is not None,
    }

    # Assessment check pass/fail values may be booleans or text values.
    check_pass_count = 0
    check_fail_count = 0
    check_unknown_count = 0
    check_result_col = find_column(checks, "check_result")
    if check_result_col:
        for row in checks:
            value = str(row.get(check_result_col, "")).strip().upper()
            if value in {"TRUE", "1", "PASS", "PASSED", "YES", "Y"}:
                check_pass_count += 1
            elif value in {"FALSE", "0", "FAIL", "FAILED", "NO", "N"}:
                check_fail_count += 1
            else:
                check_unknown_count += 1

    return {
        "directory": str(data_dir),
        "directory_exists": data_dir.is_dir(),
        "tables_expected": len(EXPECTED_TABLES),
        "tables_found": sum(item["exists"] for item in table_inventory),
        "tables_missing": missing_tables,
        "total_rows_across_expected_tables": total_rows,
        "table_inventory": table_inventory,
        "claim_count": len(claims),
        "customer_count": len(customers),
        "policy_count": len(policies),
        "assessment_count": len(assessments),
        "reserve_record_count": len(reserves),
        "settlement_record_count": len(settlements),
        "status_event_count": len(events),
        "claim_outcome_distribution": claim_outcomes,
        "claim_status_distribution": claim_statuses,
        "assessment_check_distribution": check_results,
        "assessment_check_code_distribution": check_codes,
        "assessment_checks": {
            "total": len(checks),
            "pass": check_pass_count,
            "fail": check_fail_count,
            "unclassified": check_unknown_count,
            "pass_rate_pct": (
                money(100 * check_pass_count / (check_pass_count + check_fail_count))
                if check_pass_count + check_fail_count
                else None
            ),
        },
        "financials": {
            "claimed_amount": claim_amounts,
            "assessed_or_approved_amount": approved_amounts,
            "reserve_amount": reserve_amounts,
            "settlement_amount": settlement_amounts,
            "currency": "INR",
            "note": (
                "Totals are calculated from numeric values in the source CSVs. "
                "Confirm source units and column semantics before financial use."
            ),
        },
        "fraud_summary": fraud_summary,
        "document_summary": document_summary,
        "duplicate_claim_business_key_groups": [
            {
                "policy_id": key[0],
                "incident_type": key[1],
                "incident_date": key[2],
                "claim_ids": ids,
            }
            for key, ids in sorted(duplicate_groups.items())
        ],
        "duplicate_claim_business_key_group_count": len(duplicate_groups),
    }


def count_report_rows(path: Path) -> dict[str, Any]:
    """Summarise an audit/validation CSV without assuming a fixed schema."""
    if not path.is_file():
        return {
            "available": False,
            "path": str(path),
            "row_count": None,
            "column_names": [],
            "status_counts": {},
            "code_counts": {},
        }

    rows = read_csv(path)
    columns = list(rows[0].keys()) if rows else []
    status_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()

    status_candidates = {
        "status", "severity", "result", "outcome", "auditstatus",
        "validationstatus", "mismatchtype",
    }
    code_candidates = {
        "code", "errorcode", "rulecode", "checkcode", "issuecode",
        "mismatchcode", "category",
    }

    for row in rows:
        for column in columns:
            key = normalise_name(column)
            value = str(row.get(column, "")).strip()
            if not value:
                continue
            if key in status_candidates:
                status_counts[value] += 1
            if key in code_candidates:
                code_counts[value] += 1

    return {
        "available": True,
        "path": str(path),
        "row_count": len(rows),
        "column_names": columns,
        "status_counts": dict(status_counts),
        "code_counts": dict(code_counts),
    }


def infer_mismatch_count(audit: dict[str, Any]) -> int | None:
    """Infer mismatch count from a rederive report when the format permits."""
    if not audit.get("available"):
        return None

    # The project rederive report may write one row per mismatch, or a
    # summary column/value. Prefer explicit summary fields if present.
    rows = read_csv(Path(audit["path"]))
    if not rows:
        return 0

    first_row = rows[0]
    normalized = {normalise_name(k): v for k, v in first_row.items()}

    for key in ("mismatches", "mismatchcount", "totalmismatches"):
        if key in normalized:
            value = parse_number(normalized[key])
            if value is not None:
                return int(value)

    # If the file is a row-level mismatch report, row count is the count.
    # Empty/header-only reports are interpreted as zero mismatch rows.
    return len(rows)


def infer_validation_counts(
    validation: dict[str, Any],
) -> dict[str, int | None]:
    """Count validation errors/warnings using the available report columns."""
    if not validation.get("available"):
        return {"errors": None, "warnings": None, "info": None}

    rows = read_csv(Path(validation["path"]))
    if not rows:
        return {"errors": 0, "warnings": 0, "info": 0}

    columns = list(rows[0].keys())
    severity_col = next(
        (
            col
            for col in columns
            if normalise_name(col) in {"severity", "level", "type"}
        ),
        None,
    )

    if severity_col:
        counts = Counter(str(row.get(severity_col, "")).strip().upper() for row in rows)
        errors = sum(v for k, v in counts.items() if "ERROR" in k or "FAIL" in k)
        warnings = sum(v for k, v in counts.items() if "WARN" in k)
        info = max(0, len(rows) - errors - warnings)
        return {"errors": errors, "warnings": warnings, "info": info}

    # Some validation reports use issue/error codes but no severity column.
    # Every row is treated as an issue, not automatically as an error.
    return {"errors": None, "warnings": None, "info": None}


def load_ground_truth(edge_dir: Path) -> dict[str, Any]:
    path = edge_dir / "ground_truth.csv"
    rows = read_csv(path)

    edge_types: Counter[str] = Counter()
    if rows:
        type_col = next(
            (
                col
                for col in rows[0].keys()
                if normalise_name(col)
                in {"edgecase", "edgecasetype", "anomaly", "anomalytype", "description", "case"}
            ),
            None,
        )
        if type_col:
            edge_types.update(
                str(row.get(type_col, "")).strip()
                for row in rows
                if str(row.get(type_col, "")).strip()
            )

    return {
        "available": path.is_file(),
        "path": str(path),
        "injected_case_count": len(rows) if path.is_file() else None,
        "case_type_distribution": dict(edge_types),
    }


def safe_rate(numerator: int | float | None, denominator: int | float | None):
    if numerator is None or denominator in (None, 0):
        return None
    return round(100 * numerator / denominator, 2)


def build_report(
    data_dir: Path,
    edge_dir: Path | None,
    out_dir: Path,
    audit_report: Path | None,
    edge_audit_report: Path | None,
    validation_report: Path | None,
    edge_validation_report: Path | None,
) -> dict[str, Any]:
    """Build the complete consolidated report object."""
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    clean = inspect_dataset(data_dir)

    if audit_report is None:
        audit_report = data_dir / "clean_audit.csv"
    if validation_report is None:
        validation_report = data_dir / "validation_report.csv"

    clean_audit = count_report_rows(audit_report)
    clean_validation = count_report_rows(validation_report)
    clean_audit["mismatch_count"] = infer_mismatch_count(clean_audit)
    clean_validation.update(infer_validation_counts(clean_validation))

    edge: dict[str, Any] | None = None
    edge_audit: dict[str, Any] = {
        "available": False,
        "mismatch_count": None,
    }
    edge_validation: dict[str, Any] = {
        "available": False,
        "errors": None,
        "warnings": None,
        "info": None,
    }
    ground_truth: dict[str, Any] = {
        "available": False,
        "injected_case_count": None,
        "case_type_distribution": {},
    }

    if edge_dir is not None:
        edge = inspect_dataset(edge_dir)

        if edge_audit_report is None:
            edge_audit_report = edge_dir / "audit_mismatches.csv"
        if edge_validation_report is None:
            edge_validation_report = edge_dir / "validation_report.csv"

        edge_audit = count_report_rows(edge_audit_report)
        edge_audit["mismatch_count"] = infer_mismatch_count(edge_audit)
        edge_validation = count_report_rows(edge_validation_report)
        edge_validation.update(infer_validation_counts(edge_validation))
        ground_truth = load_ground_truth(edge_dir)

    clean_mismatch_count = clean_audit.get("mismatch_count")
    clean_validation_errors = clean_validation.get("errors")
    clean_validation_warnings = clean_validation.get("warnings")

    clean_status = "PASS"
    clean_reasons: list[str] = []

    if clean["tables_missing"]:
        clean_status = "REVIEW"
        clean_reasons.append("One or more expected CSV tables are missing.")

    if clean_mismatch_count not in (None, 0):
        clean_status = "FAIL"
        clean_reasons.append("Business-rule audit reports mismatches.")

    if clean_validation_errors not in (None, 0):
        clean_status = "FAIL"
        clean_reasons.append("Validation report contains errors.")

    if clean_validation_warnings not in (None, 0) and clean_status == "PASS":
        clean_status = "REVIEW"
        clean_reasons.append("Validation report contains warnings.")

    if clean_audit.get("available") and clean_mismatch_count is None:
        if clean_status == "PASS":
            clean_status = "REVIEW"
        clean_reasons.append(
            "Audit file exists, but its mismatch count could not be identified."
        )

    if not clean_validation.get("available"):
        if clean_status == "PASS":
            clean_status = "REVIEW"
        clean_reasons.append("Validation report was not found.")

    if not clean_reasons:
        clean_reasons.append(
            "No reported clean-dataset issues were identified by the available reports."
        )

    edge_summary = None
    if edge is not None:
        edge_summary = {
            "dataset": edge,
            "audit": edge_audit,
            "validation": edge_validation,
            "ground_truth": ground_truth,
            "detected_business_key_duplicate_groups":
                edge["duplicate_claim_business_key_group_count"],
        }

    report = {
        "metadata": {
            "project": PROJECT_TITLE,
            "report_version": REPORT_VERSION,
            "generated_at_utc": generated_at,
            "currency": "INR",
            "clean_dataset_directory": str(data_dir),
            "edge_dataset_directory": str(edge_dir) if edge_dir else None,
            "output_directory": str(out_dir),
        },
        "executive_summary": {
            "clean_dataset_status": clean_status,
            "clean_dataset_status_reasons": clean_reasons,
            "clean_claim_count": clean["claim_count"],
            "clean_policy_count": clean["policy_count"],
            "clean_customer_count": clean["customer_count"],
            "clean_table_count": clean["tables_found"],
            "expected_table_count": clean["tables_expected"],
            "clean_validation_errors": clean_validation_errors,
            "clean_validation_warnings": clean_validation_warnings,
            "clean_business_rule_mismatches": clean_mismatch_count,
            "edge_case_dataset_included": edge is not None,
            "injected_edge_case_count": ground_truth.get("injected_case_count"),
            "edge_business_rule_mismatches": edge_audit.get("mismatch_count"),
            "edge_validation_errors": edge_validation.get("errors"),
        },
        "clean_dataset": {
            "dataset": clean,
            "business_rule_audit": clean_audit,
            "validation": clean_validation,
        },
        "edge_case_dataset": edge_summary,
        "interpretation_notes": [
            "The clean dataset is expected to pass validation and business-rule audit.",
            "The edge-case dataset intentionally contains injected anomalies; "
            "detected issues are not automatically treated as clean-data failures.",
            "A missing report is marked unavailable and is not assumed to contain zero issues.",
            "Financial totals depend on the meaning and units of the source columns.",
            "This report is a quality-control summary, not a legal or actuarial opinion.",
        ],
    }
    return report


def flatten_metrics(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten key KPIs into a CSV-friendly key/value format."""
    meta = report["metadata"]
    summary = report["executive_summary"]
    clean = report["clean_dataset"]["dataset"]
    financials = clean["financials"]

    metrics: list[dict[str, Any]] = []

    def add(section: str, metric: str, value: Any, notes: str = "") -> None:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        metrics.append(
            {
                "section": section,
                "metric": metric,
                "value": "" if value is None else value,
                "notes": notes,
            }
        )

    add("Report", "project", meta["project"])
    add("Report", "generated_at_utc", meta["generated_at_utc"])
    add("Clean dataset", "status", summary["clean_dataset_status"])
    add("Clean dataset", "customers", clean["customer_count"])
    add("Clean dataset", "policies", clean["policy_count"])
    add("Clean dataset", "claims", clean["claim_count"])
    add("Clean dataset", "assessments", clean["assessment_count"])
    add("Clean dataset", "tables_found", clean["tables_found"])
    add("Clean dataset", "tables_expected", clean["tables_expected"])
    add("Clean dataset", "total_rows", clean["total_rows_across_expected_tables"])
    add("Clean dataset", "missing_tables", clean["tables_missing"])
    add("Audit", "business_rule_mismatches", summary["clean_business_rule_mismatches"])
    add("Validation", "errors", summary["clean_validation_errors"])
    add("Validation", "warnings", summary["clean_validation_warnings"])

    for metric_name, key in (
        ("total_claimed_amount", "claimed_amount"),
        ("total_assessed_or_approved_amount", "assessed_or_approved_amount"),
        ("total_reserve_amount", "reserve_amount"),
        ("total_settlement_amount", "settlement_amount"),
    ):
        item = financials[key]
        add(
            "Financials",
            metric_name,
            item["total"],
            f"Source column: {item['column']}; numeric rows: {item['count']}",
        )

    add("Claims", "outcome_distribution", clean["claim_outcome_distribution"])
    add("Claims", "status_distribution", clean["claim_status_distribution"])
    add("Business checks", "check_pass_count", clean["assessment_checks"]["pass"])
    add("Business checks", "check_fail_count", clean["assessment_checks"]["fail"])
    add("Business checks", "check_pass_rate_pct", clean["assessment_checks"]["pass_rate_pct"])
    add("Documents", "mandatory_document_received_rate_pct",
        clean["document_summary"]["mandatory_document_received_rate_pct"])
    add("Fraud", "scores_at_or_above_50", clean["fraud_summary"]["scores_at_or_above_50"])
    add("Data quality", "duplicate_claim_key_groups",
        clean["duplicate_claim_business_key_group_count"])

    edge = report.get("edge_case_dataset")
    if edge:
        add("Edge cases", "injected_case_count", edge["ground_truth"]["injected_case_count"])
        add("Edge cases", "business_rule_mismatches", edge["audit"].get("mismatch_count"))
        add("Edge cases", "validation_errors", edge["validation"].get("errors"))
        add("Edge cases", "duplicate_claim_key_groups",
            edge["dataset"]["duplicate_claim_business_key_group_count"])

    return metrics


def format_value(value: Any) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "None"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_markdown(report: dict[str, Any]) -> str:
    meta = report["metadata"]
    summary = report["executive_summary"]
    clean = report["clean_dataset"]["dataset"]
    financials = clean["financials"]

    lines = [
        f"# {meta['project']}",
        "",
        "## Executive summary",
        "",
        f"- **Clean dataset status:** {summary['clean_dataset_status']}",
        f"- **Claims:** {clean['claim_count']:,}",
        f"- **Policies:** {clean['policy_count']:,}",
        f"- **Customers:** {clean['customer_count']:,}",
        f"- **CSV tables found:** {clean['tables_found']} / {clean['tables_expected']}",
        f"- **Business-rule mismatches:** {format_value(summary['clean_business_rule_mismatches'])}",
        f"- **Validation errors:** {format_value(summary['clean_validation_errors'])}",
        f"- **Validation warnings:** {format_value(summary['clean_validation_warnings'])}",
        "",
        "## Dataset inventory",
        "",
        "| Table | Exists | Rows | Columns |",
        "|---|---:|---:|---:|",
    ]

    for table in clean["table_inventory"]:
        lines.append(
            f"| `{table['table']}` | {'Yes' if table['exists'] else 'No'} "
            f"| {table['rows']:,} | {table['column_count']} |"
        )

    lines.extend(
        [
            "",
            "## Claim outcomes",
            "",
            "| Outcome | Count |",
            "|---|---:|",
        ]
    )

    for outcome, count in (clean["claim_outcome_distribution"] or {}).items():
        lines.append(f"| {outcome} | {count:,} |")

    lines.extend(
        [
            "",
            "## Financial summary",
            "",
            "| Metric | Total (INR, source units) | Numeric rows |",
            "|---|---:|---:|",
        ]
    )

    for label, key in (
        ("Claimed amount", "claimed_amount"),
        ("Assessed/approved amount", "assessed_or_approved_amount"),
        ("Reserve amount", "reserve_amount"),
        ("Settlement amount", "settlement_amount"),
    ):
        item = financials[key]
        lines.append(
            f"| {label} | {format_value(item['total'])} | {item['count']:,} |"
        )

    lines.extend(
        [
            "",
            "## Business-check summary",
            "",
            f"- Total assessment checks: {clean['assessment_checks']['total']:,}",
            f"- Passed: {clean['assessment_checks']['pass']:,}",
            f"- Failed: {clean['assessment_checks']['fail']:,}",
            f"- Unclassified: {clean['assessment_checks']['unclassified']:,}",
            f"- Pass rate: {format_value(clean['assessment_checks']['pass_rate_pct'])}%",
            "",
            "## Audit and validation interpretation",
            "",
        ]
    )

    for reason in summary["clean_dataset_status_reasons"]:
        lines.append(f"- {reason}")

    edge = report.get("edge_case_dataset")
    if edge:
        lines.extend(
            [
                "",
                "## Edge-case dataset",
                "",
                f"- Injected cases recorded: {format_value(edge['ground_truth']['injected_case_count'])}",
                f"- Business-rule audit mismatch rows/count: {format_value(edge['audit'].get('mismatch_count'))}",
                f"- Validation errors: {format_value(edge['validation'].get('errors'))}",
                f"- Validation warnings: {format_value(edge['validation'].get('warnings'))}",
                f"- Duplicate claim-key groups: {edge['dataset']['duplicate_claim_business_key_group_count']}",
                "",
                "The edge-case dataset is designed to contain anomalies. "
                "Its findings should be interpreted as detection evidence, not as "
                "a clean-baseline pass/fail result.",
            ]
        )

    lines.extend(
        [
            "",
            "## Methodology and limitations",
            "",
        ]
    )
    for note in report["interpretation_notes"]:
        lines.append(f"- {note}")

    lines.extend(["", f"_Generated at {meta['generated_at_utc']}._", ""])
    return "\n".join(lines)


def html_table(headers: list[str], rows: list[list[Any]]) -> str:
    header_html = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(format_value(value))}</td>" for value in row
        )
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        "<div class='table-wrap'><table><thead><tr>"
        + header_html
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
    )


def build_html(report: dict[str, Any]) -> str:
    meta = report["metadata"]
    summary = report["executive_summary"]
    clean = report["clean_dataset"]["dataset"]
    financials = clean["financials"]

    status = summary["clean_dataset_status"]
    status_class = (
        "pass" if status == "PASS"
        else "fail" if status == "FAIL"
        else "review"
    )

    cards = [
        ("Claims", clean["claim_count"]),
        ("Policies", clean["policy_count"]),
        ("Customers", clean["customer_count"]),
        ("Tables found", f"{clean['tables_found']} / {clean['tables_expected']}"),
        ("Validation errors", summary["clean_validation_errors"]),
        ("Audit mismatches", summary["clean_business_rule_mismatches"]),
    ]

    cards_html = "".join(
        "<div class='card'><div class='card-label'>"
        + html.escape(label)
        + "</div><div class='card-value'>"
        + html.escape(format_value(value))
        + "</div></div>"
        for label, value in cards
    )

    inventory_rows = [
        [t["table"], "Present" if t["exists"] else "Missing",
         t["rows"], t["column_count"]]
        for t in clean["table_inventory"]
    ]

    financial_rows = []
    for label, key in (
        ("Total claimed amount", "claimed_amount"),
        ("Total assessed/approved amount", "assessed_or_approved_amount"),
        ("Total reserve amount", "reserve_amount"),
        ("Total settlement amount", "settlement_amount"),
    ):
        item = financials[key]
        financial_rows.append(
            [label, item["total"], item["count"], item["column"] or "Unavailable"]
        )

    outcome_rows = [
        [name, count]
        for name, count in (clean["claim_outcome_distribution"] or {}).items()
    ] or [["Unavailable", "No matching outcome column found"]]

    check_rows = [
        ["Total checks", clean["assessment_checks"]["total"]],
        ["Passed checks", clean["assessment_checks"]["pass"]],
        ["Failed checks", clean["assessment_checks"]["fail"]],
        ["Unclassified checks", clean["assessment_checks"]["unclassified"]],
        ["Pass rate (%)", clean["assessment_checks"]["pass_rate_pct"]],
    ]

    edge_html = ""
    edge = report.get("edge_case_dataset")
    if edge:
        edge_dataset = edge["dataset"]
        edge_rows = [
            ["Injected cases", edge["ground_truth"].get("injected_case_count")],
            ["Audit mismatch count/rows", edge["audit"].get("mismatch_count")],
            ["Validation errors", edge["validation"].get("errors")],
            ["Validation warnings", edge["validation"].get("warnings")],
            ["Duplicate claim-key groups",
             edge_dataset["duplicate_claim_business_key_group_count"]],
            ["Claims", edge_dataset["claim_count"]],
        ]
        edge_html = (
            "<section><h2>Edge-case test results</h2>"
            "<p class='muted'>These results are expected to include findings "
            "because the edge-case dataset intentionally contains injected anomalies.</p>"
            + html_table(["Metric", "Value"], edge_rows)
            + "</section>"
        )

    reasons_html = "".join(
        f"<li>{html.escape(reason)}</li>"
        for reason in summary["clean_dataset_status_reasons"]
    )

    table_html = html_table(
        ["Table", "File status", "Rows", "Columns"],
        inventory_rows,
    )
    financial_html = html_table(
        ["Financial metric", "Total (source units)", "Numeric rows", "Source column"],
        financial_rows,
    )
    outcome_html = html_table(["Assessment outcome", "Count"], outcome_rows)
    checks_html = html_table(["Business-check metric", "Value"], check_rows)

    notes_html = "".join(
        f"<li>{html.escape(note)}</li>"
        for note in report["interpretation_notes"]
    )

    generated_at = html.escape(meta["generated_at_utc"])
    title = html.escape(meta["project"])

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Summary Report</title>
<style>
:root {{
  --ink: #172033;
  --muted: #637083;
  --line: #dce3ec;
  --surface: #ffffff;
  --page: #f4f7fb;
  --navy: #14233d;
  --blue: #2459a9;
  --green: #167447;
  --green-bg: #e7f6ed;
  --amber: #895900;
  --amber-bg: #fff3d5;
  --red: #a52929;
  --red-bg: #fde9e9;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--page);
  color: var(--ink);
  font: 15px/1.55 "Segoe UI", Arial, sans-serif;
}}
header {{
  background: var(--navy);
  color: white;
  padding: 34px max(22px, calc((100% - 1160px) / 2));
}}
header h1 {{ margin: 0 0 8px; font-size: clamp(25px, 4vw, 35px); }}
header p {{ margin: 0; color: #d7e1f2; }}
main {{ max-width: 1160px; margin: 24px auto; padding: 0 18px 36px; }}
section, .hero-status {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 22px;
  margin-bottom: 18px;
  box-shadow: 0 4px 16px rgba(24, 39, 65, .035);
}}
h2 {{ margin: 0 0 14px; font-size: 21px; }}
h3 {{ margin: 18px 0 8px; font-size: 16px; }}
p {{ margin-top: 6px; }}
.hero-status {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
.hero-status strong {{ font-size: 20px; }}
.status {{
  border-radius: 999px; padding: 7px 13px; font-weight: 800;
  letter-spacing: .04em; white-space: nowrap;
}}
.status.pass {{ color: var(--green); background: var(--green-bg); }}
.status.review {{ color: var(--amber); background: var(--amber-bg); }}
.status.fail {{ color: var(--red); background: var(--red-bg); }}
.cards {{
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px; margin-bottom: 18px;
}}
.card {{ background: white; border: 1px solid var(--line); border-radius: 12px; padding: 18px; }}
.card-label {{ color: var(--muted); font-size: 13px; }}
.card-value {{ font-size: 26px; font-weight: 750; margin-top: 4px; overflow-wrap: anywhere; }}
.table-wrap {{ width: 100%; overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); }}
th {{ color: #34435a; background: #f6f8fb; font-weight: 700; }}
tbody tr:last-child td {{ border-bottom: 0; }}
.muted {{ color: var(--muted); }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
ul {{ padding-left: 22px; }}
footer {{ color: var(--muted); font-size: 13px; text-align: center; padding: 12px; }}
@media (max-width: 760px) {{
  .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .two-col {{ grid-template-columns: 1fr; }}
  .hero-status {{ align-items: flex-start; flex-direction: column; }}
  section {{ padding: 16px; }}
}}
@media print {{
  body {{ background: white; }}
  header {{ background: white; color: var(--ink); padding: 18px 0; }}
  header p {{ color: var(--muted); }}
  main {{ margin: 0; max-width: none; padding: 0; }}
  section, .hero-status, .card {{ box-shadow: none; break-inside: avoid; }}
}}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p>Executive data-quality, claims, audit and financial summary</p>
  <p>Generated (UTC): {generated_at}</p>
</header>
<main>
  <div class="hero-status">
    <div>
      <strong>Clean baseline assessment</strong>
      <div class="muted">Status based on available validation and business-rule audit reports</div>
    </div>
    <span class="status {status_class}">{html.escape(status)}</span>
  </div>

  <div class="cards">{cards_html}</div>

  <section>
    <h2>Executive interpretation</h2>
    <ul>{reasons_html}</ul>
    <p class="muted">A status of REVIEW means one or more expected report inputs were unavailable
    or could not be interpreted. It does not mean that the dataset has passed all checks.</p>
  </section>

  <section>
    <h2>Dataset inventory</h2>
    <p class="muted">Expected transactional tables: {clean['tables_expected']}.
    Total rows across expected tables: {clean['total_rows_across_expected_tables']:,}.</p>
    {table_html}
  </section>

  <div class="two-col">
    <section>
      <h2>Assessment outcomes</h2>
      {outcome_html}
      <h3>Claim status distribution</h3>
      {html_table(["Claim status", "Count"], [
          [name, count] for name, count in
          (clean["claim_status_distribution"] or {}).items()
      ] or [["Unavailable", "No matching status column found"]])}
    </section>
    <section>
      <h2>Business-rule checks</h2>
      {checks_html}
      <h3>Fraud-score profile</h3>
      {html_table(["Metric", "Value"], [
          ["Scores available", clean["fraud_summary"]["scored_assessments"]],
          ["Average score", clean["fraud_summary"]["average_score"]],
          ["Scores ≥ 50", clean["fraud_summary"]["scores_at_or_above_50"]],
      ])}
    </section>
  </div>

  <section>
    <h2>Financial summary</h2>
    <p class="muted">Amounts are calculated from source CSV values. Verify the source column semantics
    and units before using these totals for financial decisions.</p>
    {financial_html}
  </section>

  <section>
    <h2>Document completeness</h2>
    {html_table(["Metric", "Value"], [
        ["Document records", clean["document_summary"]["total_document_records"]],
        ["Mandatory document records", clean["document_summary"]["mandatory_document_records"]],
        ["Mandatory documents with received date",
         clean["document_summary"]["mandatory_documents_with_received_date"]],
        ["Mandatory-document received rate (%)",
         clean["document_summary"]["mandatory_document_received_rate_pct"]],
    ])}
  </section>

  {edge_html}

  <section>
    <h2>Methodology and limitations</h2>
    <ul>{notes_html}</ul>
  </section>
  <footer>{title} · Report version {html.escape(REPORT_VERSION)}</footer>
</main>
</body>
</html>
"""


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["section", "metric", "value", "notes"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(report: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "summary_report.json"
    csv_path = out_dir / "summary_report.csv"
    md_path = out_dir / "summary_report.md"
    html_path = out_dir / "summary_report.html"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, default=str)

    write_csv(csv_path, flatten_metrics(report))

    md_path.write_text(build_markdown(report), encoding="utf-8")
    html_path.write_text(build_html(report), encoding="utf-8")

    return {
        "json": json_path,
        "csv": csv_path,
        "markdown": md_path,
        "html": html_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a consolidated executive summary for clean and "
            "edge-case insurance claims datasets."
        )
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data"),
        help="Directory containing the clean baseline CSV tables (default: data).",
    )
    parser.add_argument(
        "--edge-data",
        type=Path,
        default=Path("data_edge_cases"),
        help=(
            "Optional directory containing injected edge-case CSV tables "
            "(default: data_edge_cases). Use --no-edge-data to skip it."
        ),
    )
    parser.add_argument(
        "--no-edge-data",
        action="store_true",
        help="Generate the report for the clean baseline only.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports"),
        help="Output directory (default: reports).",
    )
    parser.add_argument(
        "--audit-report",
        type=Path,
        default=None,
        help="Path to the clean business-rule audit CSV.",
    )
    parser.add_argument(
        "--edge-audit-report",
        type=Path,
        default=None,
        help="Path to the edge-case business-rule audit CSV.",
    )
    parser.add_argument(
        "--validation-report",
        type=Path,
        default=None,
        help="Path to the clean validation CSV.",
    )
    parser.add_argument(
        "--edge-validation-report",
        type=Path,
        default=None,
        help="Path to the edge-case validation CSV.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    data_dir = args.data
    edge_dir = None if args.no_edge_data else args.edge_data
    out_dir = args.out

    if not data_dir.is_dir():
        print(f"ERROR: Clean dataset directory not found: {data_dir}")
        return 2

    if edge_dir is not None and not edge_dir.is_dir():
        print(
            f"WARNING: Edge-case directory not found: {edge_dir}. "
            "Continuing with the clean dataset only."
        )
        edge_dir = None

    report = build_report(
        data_dir=data_dir,
        edge_dir=edge_dir,
        out_dir=out_dir,
        audit_report=args.audit_report,
        edge_audit_report=args.edge_audit_report,
        validation_report=args.validation_report,
        edge_validation_report=args.edge_validation_report,
    )

    outputs = write_outputs(report, out_dir)
    summary = report["executive_summary"]

    print("\n" + "=" * 68)
    print(f" {PROJECT_TITLE}")
    print(" CONSOLIDATED SUMMARY REPORT")
    print("=" * 68)
    print(f"Clean dataset       : {data_dir}")
    print(f"Clean status        : {summary['clean_dataset_status']}")
    print(f"Customers           : {summary['clean_customer_count']:,}")
    print(f"Policies            : {summary['clean_policy_count']:,}")
    print(f"Claims              : {summary['clean_claim_count']:,}")
    print(
        f"Tables              : {summary['clean_table_count']} / "
        f"{summary['expected_table_count']}"
    )
    print(
        "Audit mismatches    : "
        f"{format_value(summary['clean_business_rule_mismatches'])}"
    )
    print(f"Validation errors   : {format_value(summary['clean_validation_errors'])}")
    print(f"Validation warnings : {format_value(summary['clean_validation_warnings'])}")

    if edge_dir is not None:
        print("\nEdge-case dataset")
        print(f"Directory           : {edge_dir}")
        print(
            "Injected cases      : "
            f"{format_value(summary['injected_edge_case_count'])}"
        )
        print(
            "Audit mismatches    : "
            f"{format_value(summary['edge_business_rule_mismatches'])}"
        )
        print(
            "Validation errors   : "
            f"{format_value(summary['edge_validation_errors'])}"
        )

    print("\nGenerated files")
    for file_type, path in outputs.items():
        print(f"  {file_type:10} : {path}")

    print("\nNote: 'Unavailable' means the required report/column was not found.")
    print("Review the HTML dashboard for the complete interpretation.")
    print("=" * 68)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
