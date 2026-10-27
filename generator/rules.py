"""Business rules in ONE place. The generator, the validator and the ground truth all call
these functions, so a decision can never differ between them.

Money is handled in integer cents to avoid floating point drift.

Decision order = order of CHECKS below (first failed check wins):
  R10 claim date before policy start      -> NOT_ELIGIBLE
  R02 incident before policy start        -> NOT_ELIGIBLE
  R03 incident after policy end           -> NOT_ELIGIBLE
  R04 incident after cancellation/lapse   -> NOT_ELIGIBLE
  R05 mandatory document missing          -> NOT_ELIGIBLE
  R06 duplicate of an earlier claim       -> NOT_ELIGIBLE
  R07 incident type excluded / not covered-> NOT_ELIGIBLE
  R09 fraud score >= threshold            -> REFER_MANUAL
  R08 claimed amount above limit          -> PARTIAL (paid up to the limit)
  R01 otherwise                           -> ELIGIBLE
"""
from generator import config as C

R01 = "R01_OK"
R02 = "R02_INCIDENT_BEFORE_START"
R03 = "R03_INCIDENT_AFTER_END"
R04 = "R04_CANCELLED_BEFORE_INCIDENT"
R05 = "R05_MISSING_MANDATORY_DOC"
R06 = "R06_DUPLICATE_CLAIM"
R07 = "R07_EXCLUSION_APPLIES"
R08 = "R08_OVER_LIMIT_CAPPED"
R09 = "R09_FRAUD_REVIEW"
R10 = "R10_CLAIM_BEFORE_POLICY_START"

# allowed claim status transitions (None = no previous status)
TRANSITIONS = {
    None: {"SUBMITTED"},
    "SUBMITTED": {"DOCS_REQUESTED", "UNDER_ASSESSMENT"},
    "DOCS_REQUESTED": {"UNDER_ASSESSMENT", "REJECTED"},
    "UNDER_ASSESSMENT": {"APPROVED", "REJECTED"},
    "APPROVED": {"SETTLED"},
    "SETTLED": {"CLOSED"},
    "REJECTED": {"CLOSED"},
    "CLOSED": set(),
}


def to_cents(x):
    return int(round(x * 100))


def mandatory_docs(product, incident_type):
    return list(C.DOC_BASE[product]) + list(C.DOC_EXTRA.get((product, incident_type), []))


def covers(exclusions, incident_type):
    """exclusions is the pipe-separated string from the Coverage table."""
    return incident_type not in (exclusions.split("|") if exclusions else [])


def fraud_score(report_delay_days, days_since_policy_start, claimed_c, limit_c, claims_in_12m):
    """Returns (score, list of triggered flags). Inputs are all observable facts."""
    score, flags = 0, []
    if report_delay_days > C.FRAUD_LATE_REPORT_DAYS:
        score += C.FRAUD_LATE_REPORT_POINTS; flags.append("LATE_REPORT")
    if days_since_policy_start <= C.FRAUD_NEW_POLICY_DAYS:
        score += C.FRAUD_NEW_POLICY_POINTS; flags.append("NEW_POLICY")
    if claimed_c >= C.FRAUD_NEAR_LIMIT_RATIO * limit_c:
        score += C.FRAUD_NEAR_LIMIT_POINTS; flags.append("NEAR_LIMIT")
    if claims_in_12m >= C.FRAUD_REPEAT_CLAIMS:
        score += C.FRAUD_REPEAT_POINTS; flags.append("REPEAT_CLAIMANT")
    return min(score, 100), flags


# The ordered list of eligibility checks. Each check has a stable ID, the reason code it raises
# when it FAILS, and the eligibility outcome that follows. The first failing check decides.
CHECKS = [
    ("C01_CLAIM_ON_OR_AFTER_POLICY_START", R10, "NOT_ELIGIBLE"),
    ("C02_INCIDENT_ON_OR_AFTER_POLICY_START", R02, "NOT_ELIGIBLE"),
    ("C03_INCIDENT_ON_OR_BEFORE_POLICY_END", R03, "NOT_ELIGIBLE"),
    ("C04_POLICY_IN_FORCE_AT_INCIDENT", R04, "NOT_ELIGIBLE"),
    ("C05_MANDATORY_DOCUMENTS_RECEIVED", R05, "NOT_ELIGIBLE"),
    ("C06_NOT_A_DUPLICATE_CLAIM", R06, "NOT_ELIGIBLE"),
    ("C07_INCIDENT_TYPE_COVERED", R07, "NOT_ELIGIBLE"),
    ("C08_FRAUD_SCORE_BELOW_THRESHOLD", R09, "REFER_MANUAL"),
    ("C09_CLAIM_WITHIN_LIMIT", R08, "PARTIAL"),
]


def run_checks(*, claim_date, incident_date, policy_start, policy_end, cancelled_date,
               missing_mandatory, is_duplicate, excluded, fraud, claimed_c, limit_c):
    """Evaluate EVERY check (not only the first failure). Returns a list of
    (rule_id, passed, reason_if_failed, outcome_if_failed, detail) in CHECKS order."""
    passed = [
        claim_date >= policy_start,
        incident_date >= policy_start,
        incident_date <= policy_end,
        cancelled_date is None or incident_date <= cancelled_date,
        not missing_mandatory,
        not is_duplicate,
        not excluded,
        fraud < C.FRAUD_REFER_THRESHOLD,
        claimed_c <= limit_c,
    ]
    detail = [
        f"claim_date={claim_date} policy_start={policy_start}",
        f"incident_date={incident_date} policy_start={policy_start}",
        f"incident_date={incident_date} policy_end={policy_end}",
        f"incident_date={incident_date} cancelled_date={cancelled_date or 'none'}",
        "missing=" + (",".join(missing_mandatory) if missing_mandatory else "none"),
        f"duplicate_of_earlier_claim={bool(is_duplicate)}",
        f"incident_type_excluded={bool(excluded)}",
        f"fraud_score={fraud} threshold={C.FRAUD_REFER_THRESHOLD}",
        f"claimed={claimed_c / 100:.2f} limit={limit_c / 100:.2f}",
    ]
    return [(rid, ok, reason, outcome, det)
            for (rid, reason, outcome), ok, det in zip(CHECKS, passed, detail)]


# Ordered checks. The FIRST failed check decides the outcome; all checks are still evaluated and
# logged (table assessment_check), so a claim that fails twice shows both failures.
CHECKS = [
    # code,   name,                                   reason if failed, outcome if failed
    ("CHK01", "CLAIM_AFTER_POLICY_START",             R10, "NOT_ELIGIBLE"),
    ("CHK02", "INCIDENT_IN_POLICY_TERM",              None, "NOT_ELIGIBLE"),   # R02 (before start) or R03 (after end)
    ("CHK03", "POLICY_NOT_CANCELLED_BEFORE_INCIDENT", R04, "NOT_ELIGIBLE"),
    ("CHK04", "MANDATORY_DOCS_COMPLETE",              R05, "NOT_ELIGIBLE"),
    ("CHK05", "NOT_A_DUPLICATE_CLAIM",                R06, "NOT_ELIGIBLE"),
    ("CHK06", "INCIDENT_TYPE_COVERED",                R07, "NOT_ELIGIBLE"),
    ("CHK07", "FRAUD_SCORE_BELOW_THRESHOLD",          R09, "REFER_MANUAL"),
    ("CHK08", "AMOUNT_WITHIN_LIMIT",                  R08, "PARTIAL"),
]


def _m(c):
    return f"{c / 100:.2f}"


def run_checks(*, claim_date, incident_date, policy_start, policy_end, cancelled_date,
               missing_mandatory, is_duplicate, excluded, fraud, claimed_c, limit_c):
    """Evaluates every check. Returns a list of dicts in CHECKS order:
    code, name, passed, observed, threshold, reason (set only when failed), outcome (only when failed)."""
    passed = {
        "CHK01": claim_date >= policy_start,
        "CHK02": policy_start <= incident_date <= policy_end,
        "CHK03": cancelled_date is None or incident_date <= cancelled_date,
        "CHK04": not missing_mandatory,
        "CHK05": not is_duplicate,
        "CHK06": not excluded,
        "CHK07": fraud < C.FRAUD_REFER_THRESHOLD,
        "CHK08": claimed_c <= limit_c,
    }
    observed = {
        "CHK01": claim_date.isoformat(), "CHK02": incident_date.isoformat(),
        "CHK03": incident_date.isoformat(),
        "CHK04": ("missing: " + "|".join(missing_mandatory)) if missing_mandatory else "0 missing",
        "CHK05": "duplicate" if is_duplicate else "unique",
        "CHK06": "excluded" if excluded else "covered",
        "CHK07": str(fraud), "CHK08": _m(claimed_c),
    }
    threshold = {
        "CHK01": f">= {policy_start.isoformat()}",
        "CHK02": f"{policy_start.isoformat()}..{policy_end.isoformat()}",
        "CHK03": f"<= {cancelled_date.isoformat()}" if cancelled_date else "no cancellation",
        "CHK04": "0 missing", "CHK05": "unique", "CHK06": "covered",
        "CHK07": f"< {C.FRAUD_REFER_THRESHOLD}", "CHK08": f"<= {_m(limit_c)}",
    }
    out = []
    for code, name, reason, outcome in CHECKS:
        ok = passed[code]
        if code == "CHK02" and not ok:
            reason = R02 if incident_date < policy_start else R03
        out.append(dict(code=code, name=name, passed=ok, observed=observed[code],
                        threshold=threshold[code], reason=None if ok else reason,
                        outcome=None if ok else outcome))
    return out


def decide(checks):
    """Eligibility and reason code come from the FIRST failed check, else ELIGIBLE / R01."""
    for c in checks:
        if not c["passed"]:
            return c["outcome"], c["reason"]
    return "ELIGIBLE", R01


def assess(**facts):
    """Shortcut: run all checks and decide. Returns (eligibility, reason_code)."""
    return decide(run_checks(**facts))


def assessed_cents(eligibility, claimed_c, limit_c):
    """Amount the assessment approves (before deductible)."""
    if eligibility == "NOT_ELIGIBLE":
        return 0
    if eligibility == "PARTIAL":
        return min(claimed_c, limit_c)
    return claimed_c                                  # ELIGIBLE and REFER_MANUAL (pending review)


def reserve_cents(amount_c, limit_c, deductible_c):
    """Reserve = max(0, min(amount, limit) - deductible)."""
    return max(0, min(amount_c, limit_c) - deductible_c)


def settlement_cents(assessed_c, limit_c, deductible_c):
    """Settlement = max(0, min(assessed, limit) - deductible). Never above the limit."""
    return max(0, min(assessed_c, limit_c) - deductible_c)


def allocate(total_c, weights):
    """Split total_c cents over len(weights) parts; parts add up exactly to total_c."""
    s = sum(weights)
    parts = [total_c * w // s for w in weights]
    parts[-1] += total_c - sum(parts)
    return parts


def allocate_approved(item_cents, target_c):
    """Approved amount per item so that sum == target_c and each <= its claimed amount."""
    total = sum(item_cents)
    if target_c >= total:
        return list(item_cents)
    approved = [c * target_c // total for c in item_cents]
    rest = target_c - sum(approved)
    i = 0
    while rest > 0:                                   # hand out leftover cents one at a time
        if approved[i % len(approved)] < item_cents[i % len(approved)]:
            approved[i % len(approved)] += 1
            rest -= 1
        i += 1
    return approved