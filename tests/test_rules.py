"""Boundary and priority tests for the business rules. Run with:  python -m pytest -v"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from generator import config as C
from generator import rules as R

START, END = date(2026, 1, 1), date(2026, 12, 31)


def facts(**kw):
    base = dict(claim_date=date(2026, 6, 10), incident_date=date(2026, 6, 1), policy_start=START, policy_end=END,
                cancelled_date=None, missing_mandatory=[], is_duplicate=False, excluded=False, fraud=0,
                claimed_c=100000, limit_c=500000)
    base.update(kw)
    return base


def test_clean_claim_is_eligible_with_reason_r01():
    assert R.assess(**facts()) == ("ELIGIBLE", R.R01)


def test_all_eight_checks_are_always_evaluated_and_ordered():
    checks = R.run_checks(**facts())
    assert [c["code"] for c in checks] == [f"CHK0{i}" for i in range(1, 9)]
    assert all(c["passed"] and c["reason"] is None for c in checks)


def test_incident_on_start_and_end_dates_is_inside_the_period():
    assert R.assess(**facts(incident_date=START, claim_date=START))[0] == "ELIGIBLE"
    assert R.assess(**facts(incident_date=END))[0] == "ELIGIBLE"


def test_incident_one_day_before_start_or_after_end_fails():
    assert R.assess(**facts(incident_date=START - timedelta(days=1), claim_date=START)) == ("NOT_ELIGIBLE", R.R02)
    assert R.assess(**facts(incident_date=END + timedelta(days=1), claim_date=END + timedelta(days=2))) == ("NOT_ELIGIBLE", R.R03)


def test_claim_date_before_policy_start_is_r10():
    assert R.assess(**facts(claim_date=START - timedelta(days=1))) == ("NOT_ELIGIBLE", R.R10)


def test_cancellation_boundary():
    cancel = date(2026, 6, 1)
    assert R.assess(**facts(cancelled_date=cancel, incident_date=cancel))[0] == "ELIGIBLE"          # same day still covered
    assert R.assess(**facts(cancelled_date=cancel, incident_date=cancel + timedelta(days=1))) == ("NOT_ELIGIBLE", R.R04)


def test_amount_exactly_at_limit_is_eligible_one_cent_over_is_partial():
    assert R.assess(**facts(claimed_c=500000, limit_c=500000)) == ("ELIGIBLE", R.R01)
    assert R.assess(**facts(claimed_c=500001, limit_c=500000)) == ("PARTIAL", R.R08)


def test_fraud_threshold_boundary():
    t = C.FRAUD_REFER_THRESHOLD
    assert R.assess(**facts(fraud=t - 1))[0] == "ELIGIBLE"
    assert R.assess(**facts(fraud=t)) == ("REFER_MANUAL", R.R09)


def test_missing_document_duplicate_and_exclusion():
    assert R.assess(**facts(missing_mandatory=["ID_PROOF"])) == ("NOT_ELIGIBLE", R.R05)
    assert R.assess(**facts(is_duplicate=True)) == ("NOT_ELIGIBLE", R.R06)
    assert R.assess(**facts(excluded=True)) == ("NOT_ELIGIBLE", R.R07)


def test_priority_first_failed_check_wins_but_all_failures_are_logged():
    f = facts(is_duplicate=True, claimed_c=900000, limit_c=500000, fraud=80)
    checks = R.run_checks(**f)
    failed = [c["code"] for c in checks if not c["passed"]]
    assert failed == ["CHK05", "CHK07", "CHK08"]
    assert R.decide(checks) == ("NOT_ELIGIBLE", R.R06)       # duplicate beats fraud review and over-limit
    f2 = facts(fraud=80, claimed_c=900000, limit_c=500000)
    assert R.assess(**f2) == ("REFER_MANUAL", R.R09)          # fraud review beats over-limit


def test_fraud_indicator_boundaries():
    t, lim = 100000, 500000
    assert R.fraud_score(14, 100, t, lim, 1)[0] == 0
    assert R.fraud_score(15, 100, t, lim, 1)[0] == C.FRAUD_LATE_REPORT_POINTS
    assert R.fraud_score(0, 30, t, lim, 1)[0] == C.FRAUD_NEW_POLICY_POINTS
    assert R.fraud_score(0, 31, t, lim, 1)[0] == 0
    assert R.fraud_score(0, 100, 450000, lim, 1)[0] == C.FRAUD_NEAR_LIMIT_POINTS        # exactly 90%
    assert R.fraud_score(0, 100, 449999, lim, 1)[0] == 0
    assert R.fraud_score(0, 100, t, lim, 3)[0] == C.FRAUD_REPEAT_POINTS
    assert R.fraud_score(0, 100, t, lim, 2)[0] == 0
    assert R.fraud_score(99, 0, 10 ** 9, lim, 9) == (90, ["LATE_REPORT", "NEW_POLICY", "NEAR_LIMIT", "REPEAT_CLAIMANT"])


def test_money_formulas():
    assert R.reserve_cents(100000, 500000, 5000) == 95000
    assert R.reserve_cents(900000, 500000, 5000) == 495000          # capped at limit, then deductible
    assert R.reserve_cents(3000, 500000, 5000) == 0                  # never negative
    assert R.settlement_cents(900000, 500000, 5000) == 495000
    assert R.settlement_cents(100000, 500000, 0) == 100000


def test_assessed_amount_by_eligibility():
    assert R.assessed_cents("NOT_ELIGIBLE", 100, 50) == 0
    assert R.assessed_cents("PARTIAL", 900, 500) == 500
    assert R.assessed_cents("ELIGIBLE", 400, 500) == 400


def test_allocation_adds_up_exactly_and_respects_item_amounts():
    for total, w in [(10000, [1, 2, 3]), (1, [5, 5]), (999999, [7, 1, 9, 3])]:
        assert sum(R.allocate(total, w)) == total
    items = [10001, 5000, 333]
    for target in (0, 1, 7, 9000, 15333, 20000):
        a = R.allocate_approved(items, target)
        assert sum(a) == min(target, sum(items)) and all(0 <= x <= y for x, y in zip(a, items))


def test_every_status_transition_target_is_a_known_state():
    states = set(R.TRANSITIONS) - {None}
    for src, dst in R.TRANSITIONS.items():
        assert dst <= states