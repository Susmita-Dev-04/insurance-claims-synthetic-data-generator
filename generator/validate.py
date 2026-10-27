
"""
Step 8 - Structural and data-integrity validation.

Run:
    python -m generator.validate --data data --report data/validation_report.csv

Validate the injected edge-case dataset:
    python -m generator.validate --data data_edge_cases \
        --report data_edge_cases/validation_report.csv

Exit codes:
    0 = no validation errors
    1 = validation errors found
    2 = input or execution error

This validator checks data integrity. Use generator.rederive separately
for detailed business-rule and assessment reconciliation.
"""

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime


TABLES = {
    "customer": {
        "pk": "customer_id",
        "required": [
            "customer_id", "full_name", "date_of_birth",
            "city", "kyc_status", "created_date",
        ],
    },
   "coverage": {
    "pk": "coverage_id",
    "required": [
        "coverage_id", "claim_type", "description",
        "default_limit", "default_deductible",
    ],
    },  
    "policy": {
        "pk": "policy_id",
        "required": [
            "policy_id", "customer_id", "product",
            "start_date", "end_date", "status", "premium",
        ],
    },
    "policy_coverage": {
        "pk": None,
        "required": [
            "policy_id", "coverage_id", "coverage_limit",
            "deductible", "effective_from", "effective_to",
        ],
    },
    "adjuster": {
        "pk": "adjuster_id",
        "required": [
            "adjuster_id", "name", "specialization",
            "region", "max_authority",
        ],
    },
    "incident": {
        "pk": "incident_id",
        "required": [
            "incident_id", "policy_id", "incident_type",
            "incident_date", "location", "reported_date",
        ],
    },
    "claim": {
        "pk": "claim_id",
        "required": [
            "claim_id", "policy_id", "incident_id",
            "claim_type", "claim_date", "claimed_amount", "status",
        ],
    },
    "claim_item": {
        "pk": "claim_item_id",
        "required": [
            "claim_item_id", "claim_id", "coverage_id",
            "item_type", "claimed_amount",
        ],
    },
    "document": {
        "pk": "document_id",
        "required": [
            "document_id", "claim_id", "doc_type",
            "is_mandatory", "status",
        ],
    },
    "claim_assignment": {
        "pk": "assignment_id",
        "required": [
            "assignment_id", "claim_id", "adjuster_id",
            "assigned_date", "status",
        ],
    },
    "assessment": {
        "pk": "assessment_id",
        "required": [
            "assessment_id", "claim_id", "assignment_id",
            "eligibility", "reason_code", "assessed_amount",
            "fraud_score", "assessed_date",
        ],
    },
    "assessment_check": {
        "pk": "check_id",
        "required": [
            "check_id", "assessment_id", "claim_id",
            "check_code", "check_name", "result",
        ],
    },
    "reserve": {
        "pk": "reserve_id",
        "required": [
            "reserve_id", "claim_id", "reserve_amount",
            "version", "created_date",
        ],
    },
    "settlement": {
        "pk": "settlement_id",
        "required": [
            "settlement_id", "claim_id", "assessment_id",
            "settlement_amount", "deductible_applied", "status",
        ],
    },
    "claim_status_event": {
        "pk": "event_id",
        "required": [
            "event_id", "claim_id", "to_status",
            "event_timestamp", "reason",
        ],
    },
}


DATE_FIELDS = {
    "date_of_birth", "created_date", "start_date", "end_date",
    "cancelled_date", "effective_from", "effective_to",
    "incident_date", "reported_date", "claim_date",
    "received_date", "assigned_date", "assessed_date",
    "payment_date",
}

MONEY_FIELDS = {
    "premium", "default_limit", "default_deductible",
    "coverage_limit", "deductible", "max_authority",
    "claimed_amount", "approved_amount", "assessed_amount",
    "reserve_amount", "settlement_amount", "deductible_applied",
}

INTEGER_FIELDS = {"fraud_score", "version"}

ALLOWED_VALUES = {
    ("customer", "kyc_status"): {"VERIFIED", "PENDING"},
    ("policy", "status"): {"ACTIVE", "CANCELLED", "LAPSED", "EXPIRED"},
    ("document", "is_mandatory"): {"TRUE", "FALSE"},
    ("document", "status"): {"VERIFIED", "RECEIVED", "PENDING"},
    ("claim_assignment", "status"): {
        "ASSIGNED", "REASSIGNED", "COMPLETED",
    },
    ("assessment", "eligibility"): {
        "ELIGIBLE", "NOT_ELIGIBLE", "PARTIAL", "REFER_MANUAL",
    },
    ("assessment_check", "result"): {"PASS", "FAIL"},
    ("settlement", "status"): {"PAID", "APPROVED"},
}

# Matches the permitted transitions in generator/rules.py.
ALLOWED_TRANSITIONS = {
    None: {"SUBMITTED"},
    "SUBMITTED": {"DOCS_REQUESTED", "UNDER_ASSESSMENT"},
    "DOCS_REQUESTED": {"UNDER_ASSESSMENT", "REJECTED"},
    "UNDER_ASSESSMENT": {"APPROVED", "REJECTED"},
    "APPROVED": {"SETTLED"},
    "SETTLED": {"CLOSED"},
    "REJECTED": {"CLOSED"},
    "CLOSED": set(),
}

REPORT_COLUMNS = [
    "severity",
    "table_name",
    "record_id",
    "category",
    "details",
]


def read_table(data_dir, table_name):
    path = os.path.join(data_dir, f"{table_name}.csv")

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Required CSV file not found: {path}")

    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(f"{path} has no CSV header.")

        rows = list(reader)
        columns = set(reader.fieldnames)

    return rows, columns


def parse_date(value):
    if value in (None, ""):
        return None
    return date.fromisoformat(value)


def parse_number(value):
    if value in (None, ""):
        return None
    return float(value)


def validate(data_dir):
    errors = []
    warnings = []
    tables = {}
    columns = {}

    def issue(severity, table, record_id, category, details):
        target = errors if severity == "ERROR" else warnings
        target.append({
            "severity": severity,
            "table_name": table,
            "record_id": str(record_id or ""),
            "category": category,
            "details": str(details),
        })

    # ---------------------------------------------------------
    # 1. Load every expected table and verify column names.
    # ---------------------------------------------------------
    for table_name, specification in TABLES.items():
        rows, actual_columns = read_table(data_dir, table_name)
        tables[table_name] = rows
        columns[table_name] = actual_columns

        missing_columns = (
            set(specification["required"]) - actual_columns
        )

        if missing_columns:
            issue(
                "ERROR", table_name, "",
                "MISSING_COLUMNS",
                f"Missing columns: {sorted(missing_columns)}",
            )

    # Stop dependent checks if the schema is incomplete.
    if errors:
        return errors, warnings, tables

    # ---------------------------------------------------------
    # 2. Required fields, primary keys and duplicate IDs.
    # ---------------------------------------------------------
    primary_keys = {}

    for table_name, specification in TABLES.items():
        rows = tables[table_name]
        pk = specification["pk"]

        if pk:
            counts = Counter(
                row.get(pk, "").strip()
                for row in rows
                if row.get(pk, "").strip()
            )

            primary_keys[table_name] = set(counts)

            for value, count in counts.items():
                if count > 1:
                    issue(
                        "ERROR", table_name, value,
                        "DUPLICATE_PRIMARY_KEY",
                        f"{pk} occurs {count} times.",
                    )
        else:
            primary_keys[table_name] = set()

        for index, row in enumerate(rows, start=2):
            record_id = (
                row.get(pk, "")
                if pk else f"row {index}"
            )

            for field in specification["required"]:
                if not row.get(field, "").strip():
                    issue(
                        "ERROR", table_name, record_id,
                        "REQUIRED_FIELD_EMPTY",
                        f"Required field '{field}' is empty.",
                    )

            for field, allowed in ALLOWED_VALUES.items():
                expected_table, column = field

                if expected_table != table_name:
                    continue

                value = row.get(column, "").strip()

                if value and value not in allowed:
                    issue(
                        "ERROR", table_name, record_id,
                        "INVALID_ENUM",
                        f"{column}='{value}'; allowed values: "
                        f"{sorted(allowed)}",
                    )

            if table_name == "assessment_check":
                value = row.get("check_code", "")
                if value and value not in {
                    "CHK01", "CHK02", "CHK03", "CHK04",
                    "CHK05", "CHK06", "CHK07", "CHK08",
                }:
                    issue(
                        "ERROR", table_name, record_id,
                        "INVALID_CHECK_CODE",
                        f"Unknown check code: {value}",
                    )

    # ---------------------------------------------------------
    # 3. Foreign-key checks.
    # ---------------------------------------------------------
    foreign_keys = [
        ("policy", "customer_id", "customer", "customer_id"),
        ("policy_coverage", "policy_id", "policy", "policy_id"),
        ("policy_coverage", "coverage_id", "coverage", "coverage_id"),
        ("incident", "policy_id", "policy", "policy_id"),
        ("claim", "policy_id", "policy", "policy_id"),
        ("claim", "incident_id", "incident", "incident_id"),
        ("claim_item", "claim_id", "claim", "claim_id"),
        ("claim_item", "coverage_id", "coverage", "coverage_id"),
        ("document", "claim_id", "claim", "claim_id"),
        ("claim_assignment", "claim_id", "claim", "claim_id"),
        ("claim_assignment", "adjuster_id", "adjuster", "adjuster_id"),
        ("assessment", "claim_id", "claim", "claim_id"),
        ("assessment", "assignment_id", "claim_assignment", "assignment_id"),
        ("assessment_check", "assessment_id", "assessment", "assessment_id"),
        ("assessment_check", "claim_id", "claim", "claim_id"),
        ("reserve", "claim_id", "claim", "claim_id"),
        ("reserve", "assessment_id", "assessment", "assessment_id"),
        ("settlement", "claim_id", "claim", "claim_id"),
        ("settlement", "assessment_id", "assessment", "assessment_id"),
        ("claim_status_event", "claim_id", "claim", "claim_id"),
    ]

    for child_table, child_col, parent_table, parent_col in foreign_keys:
        parent_ids = {
            row[parent_col]
            for row in tables[parent_table]
            if row.get(parent_col, "").strip()
        }

        for row in tables[child_table]:
            value = row.get(child_col, "").strip()

            # Some foreign keys are legitimately nullable.
            if not value and (
                (child_table, child_col)
                in {
                    ("reserve", "assessment_id"),
                    ("settlement", "assessment_id"),
                }
            ):
                continue

            record_id = (
                row.get(TABLES[child_table]["pk"], "")
                if TABLES[child_table]["pk"]
                else row.get("check_id", "")
            )

            if value and value not in parent_ids:
                issue(
                    "ERROR", child_table, record_id,
                    "FOREIGN_KEY_NOT_FOUND",
                    f"{child_col}='{value}' does not exist in "
                    f"{parent_table}.{parent_col}.",
                )

    # ---------------------------------------------------------
    # 4. Parse dates and numeric fields.
    # ---------------------------------------------------------
    for table_name, rows in tables.items():
        for row in rows:
            pk = TABLES[table_name]["pk"]
            record_id = row.get(pk, "") if pk else row.get("check_id", "")

            for field in DATE_FIELDS.intersection(row.keys()):
                value = row.get(field, "").strip()

                if not value:
                    continue

                try:
                    parse_date(value)
                except ValueError:
                    issue(
                        "ERROR", table_name, record_id,
                        "INVALID_DATE",
                        f"{field} has invalid date '{value}'.",
                    )

            for field in MONEY_FIELDS.intersection(row.keys()):
                value = row.get(field, "").strip()

                if not value:
                    continue

                try:
                    amount = parse_number(value)
                    if amount is None:
                        continue
                    if amount < 0:
                        issue(
                            "ERROR", table_name, record_id,
                            "NEGATIVE_AMOUNT",
                            f"{field} must not be negative; found {amount}.",
                        )
                except ValueError:
                    issue(
                        "ERROR", table_name, record_id,
                        "INVALID_NUMBER",
                        f"{field} is not numeric: '{value}'.",
                    )

            for field in INTEGER_FIELDS.intersection(row.keys()):
                value = row.get(field, "").strip()

                if not value:
                    continue

                try:
                    int(value)
                except ValueError:
                    issue(
                        "ERROR", table_name, record_id,
                        "INVALID_INTEGER",
                        f"{field} must be an integer; found '{value}'.",
                    )

    # ---------------------------------------------------------
    # 5. Policy and incident date consistency.
    # ---------------------------------------------------------
    policies = {
        row["policy_id"]: row for row in tables["policy"]
    }

    incidents = {
        row["incident_id"]: row for row in tables["incident"]
    }

    for policy in tables["policy"]:
        pid = policy["policy_id"]

        try:
            start = parse_date(policy["start_date"])
            end = parse_date(policy["end_date"])
            cancelled = parse_date(policy.get("cancelled_date", ""))

            if start and end and start > end:
                issue(
                    "ERROR", "policy", pid,
                    "INVALID_POLICY_PERIOD",
                    "start_date is after end_date.",
                )

            if cancelled and start and cancelled < start:
                issue(
                    "ERROR", "policy", pid,
                    "INVALID_CANCELLATION_DATE",
                    "cancelled_date is before start_date.",
                )
        except ValueError:
            # Invalid dates are already reported above.
            pass

    for incident in tables["incident"]:
        iid = incident["incident_id"]

        try:
            incident_day = parse_date(incident["incident_date"])
            reported_day = parse_date(incident["reported_date"])

            if (
                incident_day and reported_day
                and reported_day < incident_day
            ):
                issue(
                    "ERROR", "incident", iid,
                    "REPORT_BEFORE_INCIDENT",
                    "reported_date is earlier than incident_date.",
                )
        except ValueError:
            pass

    # ---------------------------------------------------------
    # 6. Composite keys and coverage membership.
    # ---------------------------------------------------------
    policy_coverage_keys = {
        (row["policy_id"], row["coverage_id"])
        for row in tables["policy_coverage"]
    }

    seen_policy_coverage = set()

    for row in tables["policy_coverage"]:
        key = (row["policy_id"], row["coverage_id"])

        if key in seen_policy_coverage:
            issue(
                "ERROR", "policy_coverage", row["policy_id"],
                "DUPLICATE_POLICY_COVERAGE",
                f"Duplicate policy/coverage pair: {key}.",
            )

        seen_policy_coverage.add(key)

    for item in tables["claim_item"]:
        if not item["claim_id"] or not item["coverage_id"]:
            continue

        claim = next(
            (
                row for row in tables["claim"]
                if row["claim_id"] == item["claim_id"]
            ),
            None,
        )

        if claim is None:
            continue

        pair = (claim["policy_id"], item["coverage_id"])

        if pair not in policy_coverage_keys:
            issue(
                "ERROR", "claim_item", item["claim_item_id"],
                "COVERAGE_NOT_ON_POLICY",
                f"Coverage {item['coverage_id']} is not attached "
                f"to policy {claim['policy_id']}.",
            )

    # ---------------------------------------------------------
    # 7. Claim amount and item amount reconciliation.
    # ---------------------------------------------------------
    items_by_claim = defaultdict(list)

    for item in tables["claim_item"]:
        items_by_claim[item["claim_id"]].append(item)

    for claim in tables["claim"]:
        cid = claim["claim_id"]
        items = items_by_claim[cid]

        if not items:
            issue(
                "ERROR", "claim", cid,
                "CLAIM_HAS_NO_ITEMS",
                "Claim has no claim_item rows.",
            )
            continue

        try:
            claimed_total = round(
                sum(float(item["claimed_amount"]) for item in items), 2
            )
            claim_total = round(float(claim["claimed_amount"]), 2)

            if claimed_total != claim_total:
                issue(
                    "ERROR", "claim", cid,
                    "CLAIM_ITEM_TOTAL_MISMATCH",
                    f"Claim amount={claim_total}; "
                    f"sum of item amounts={claimed_total}.",
                )
        except (ValueError, TypeError):
            pass

    # ---------------------------------------------------------
    # 8. Duplicate business keys and duplicate settlements.
    # ---------------------------------------------------------
    claim_keys = defaultdict(list)

    for claim in tables["claim"]:
        incident = incidents.get(claim["incident_id"])

        if incident:
            key = (
                claim["policy_id"],
                incident["incident_type"],
                incident["incident_date"],
            )
            claim_keys[key].append(claim["claim_id"])

    for key, claim_ids in claim_keys.items():
        if len(claim_ids) > 1:
            for cid in claim_ids:
                issue(
                    "ERROR", "claim", cid,
                    "DUPLICATE_CLAIM_KEY",
                    f"Duplicate policy/incident-type/incident-date key: "
                    f"{key}; claims={claim_ids}.",
                )

    settlements_by_claim = defaultdict(list)

    for settlement in tables["settlement"]:
        settlements_by_claim[settlement["claim_id"]].append(settlement)

    for cid, settlements in settlements_by_claim.items():
        if len(settlements) > 1:
            issue(
                "ERROR", "settlement", cid,
                "MULTIPLE_SETTLEMENTS",
                f"Found {len(settlements)} settlement records for one claim.",
            )

    # ---------------------------------------------------------
    # 9. Check assessment and assignment references match claims.
    # ---------------------------------------------------------
    assignments = {
        row["assignment_id"]: row
        for row in tables["claim_assignment"]
    }
    assessments = {
        row["assessment_id"]: row
        for row in tables["assessment"]
    }

    for assessment in tables["assessment"]:
        assignment = assignments.get(assessment["assignment_id"])

        if assignment and (
            assignment["claim_id"] != assessment["claim_id"]
        ):
            issue(
                "ERROR", "assessment", assessment["assessment_id"],
                "ASSIGNMENT_CLAIM_MISMATCH",
                "Assessment and assignment refer to different claims.",
            )

    for table_name in ("assessment_check", "reserve", "settlement"):
        for row in tables[table_name]:
            aid = row.get("assessment_id", "").strip()

            if not aid:
                continue

            assessment = assessments.get(aid)

            if assessment and (
                assessment["claim_id"] != row["claim_id"]
            ):
                record_id = (
                    row.get(TABLES[table_name]["pk"], "")
                    if TABLES[table_name]["pk"]
                    else row.get("check_id", "")
                )

                issue(
                    "ERROR", table_name, record_id,
                    "ASSESSMENT_CLAIM_MISMATCH",
                    "Assessment and linked record refer to different claims.",
                )

    # ---------------------------------------------------------
    # 10. Claim status event transition validation.
    # ---------------------------------------------------------
    events_by_claim = defaultdict(list)

    for event in tables["claim_status_event"]:
        events_by_claim[event["claim_id"]].append(event)

    claims_by_id = {
        row["claim_id"]: row for row in tables["claim"]
    }

    for cid, events in events_by_claim.items():
        events.sort(key=lambda row: (
            row.get("event_timestamp", ""),
            row.get("event_id", ""),
        ))

        previous_status = None

        for event in events:
            from_status = event.get("from_status", "").strip() or None
            to_status = event.get("to_status", "").strip()

            if from_status != previous_status:
                issue(
                    "ERROR", "claim_status_event", event["event_id"],
                    "STATUS_CHAIN_MISMATCH",
                    f"Expected from_status={previous_status!r}; "
                    f"found {from_status!r}.",
                )

            allowed = ALLOWED_TRANSITIONS.get(previous_status, set())

            if to_status not in allowed:
                issue(
                    "ERROR", "claim_status_event", event["event_id"],
                    "INVALID_STATUS_TRANSITION",
                    f"Transition {previous_status!r} -> "
                    f"{to_status!r} is not permitted.",
                )

            previous_status = to_status

        claim = claims_by_id.get(cid)

        if claim and events and claim["status"] != previous_status:
            issue(
                "ERROR", "claim", cid,
                "CLAIM_STATUS_EVENT_MISMATCH",
                f"Claim status={claim['status']!r}; "
                f"last event status={previous_status!r}.",
            )

    # ---------------------------------------------------------
    # 11. Report missing optional links as warnings.
    # ---------------------------------------------------------
    claims_with_assessments = {
        row["claim_id"] for row in tables["assessment"]
    }

    for claim in tables["claim"]:
        if (
            claim["claim_id"] not in claims_with_assessments
            and claim["status"] in {"APPROVED", "SETTLED", "REJECTED", "CLOSED"}
        ):
            issue(
                "WARNING", "claim", claim["claim_id"],
                "FINAL_STATUS_WITHOUT_ASSESSMENT",
                f"Claim status is {claim['status']} but no assessment exists.",
            )

    return errors, warnings, tables


def write_report(report_path, errors, warnings):
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)

    rows = errors + warnings

    with open(report_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate insurance claim dataset integrity."
    )
    parser.add_argument(
        "--data",
        default="data",
        help="Directory containing the CSV tables.",
    )
    parser.add_argument(
        "--report",
        default="data/validation_report.csv",
        help="Path for the validation report CSV.",
    )
    args = parser.parse_args(argv)

    try:
        errors, warnings, tables = validate(args.data)
        write_report(args.report, errors, warnings)

    except (OSError, ValueError, KeyError, csv.Error) as exc:
        print(f"Validation could not complete: {exc}", file=sys.stderr)
        return 2

    print(f"Dataset directory: {args.data}")

    for table_name in TABLES:
        print(
            f"  {table_name:20s} "
            f"{len(tables.get(table_name, [])):6d} rows"
        )

    print(f"Validation errors:   {len(errors)}")
    print(f"Validation warnings: {len(warnings)}")
    print(f"Report: {args.report}")

    if errors:
        print("\nValidation failed. First 20 errors:")

        for row in errors[:20]:
            print(
                f"  [{row['table_name']}] "
                f"{row['record_id']} - "
                f"{row['category']}: {row['details']}"
            )

        return 1

    print("\nValidation passed: no errors found.")

    if warnings:
        print("Review the warnings in the report.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
