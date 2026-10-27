"""Business rules in ONE place. The generator, the validator and the ground truth all call
these functions, so a decision can never differ between them.

Money is handled in integer cents to avoid floating point drift.

Decision order in assess() (first match wins):
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


def assess(*, claim_date, incident_date, policy_start, policy_end, cancelled_date,
           missing_mandatory, is_duplicate, excluded, fraud, claimed_c, limit_c):
    """Returns (eligibility, reason_code)."""
    if claim_date < policy_start:
        return "NOT_ELIGIBLE", R10
    if incident_date < policy_start:
        return "NOT_ELIGIBLE", R02
    if incident_date > policy_end:
        return "NOT_ELIGIBLE", R03
    if cancelled_date is not None and incident_date > cancelled_date:
        return "NOT_ELIGIBLE", R04
    if missing_mandatory:
        return "NOT_ELIGIBLE", R05
    if is_duplicate:
        return "NOT_ELIGIBLE", R06
    if excluded:
        return "NOT_ELIGIBLE", R07
    if fraud >= C.FRAUD_REFER_THRESHOLD:
        return "REFER_MANUAL", R09
    if claimed_c > limit_c:
        return "PARTIAL", R08
    return "ELIGIBLE", R01


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