"""Tests for the independent audit (generator/rederive.py). Run with:  python -m pytest -v"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from generator import config as C
from generator.master_data import build_master
from generator.rederive import audit, load, main as audit_main
from generator.transactions import build_transactions, main as gen_main

POLICIES, CLAIMS = 800, 400


@pytest.fixture(scope="module")
def tables():
    m = build_master(POLICIES, C.SEED)
    return {**m, **build_transactions(m, CLAIMS, C.SEED)}


def categories(t):
    return {b[1] for b in audit(t)[0]}


def test_clean_baseline_has_zero_mismatches(tables):
    bad, stats = audit(tables)
    assert bad == []
    assert stats["claims audited"] == CLAIMS and stats["assessments audited"] > 0.8 * CLAIMS


def test_audit_of_exported_csv_files_matches(tmp_path):
    gen_main(["--policies", "300", "--claims", "150", "--out", str(tmp_path)])
    bad, _ = audit(load(str(tmp_path)))
    assert bad == []
    assert audit_main(["--data", str(tmp_path)]) == 0


def test_every_check_code_is_logged_for_every_assessment(tables):
    n = len(tables["assessment"])
    assert len(tables["assessment_check"]) == 8 * n
    ids = {c["assessment_id"] for c in tables["assessment_check"]}
    assert ids == {a["assessment_id"] for a in tables["assessment"]}


def test_failed_checks_always_carry_a_reason_code(tables):
    for c in tables["assessment_check"]:
        assert (c["result"] == "FAIL") == (c["reason_code"] is not None)


# ---- tampering: the audit must notice each of these -----------------------------------------
def tamper(tables, fn):
    t = copy.deepcopy(tables)
    fn(t)
    return t


def test_detects_wrong_eligibility(tables):
    def f(t):
        a = next(x for x in t["assessment"] if x["eligibility"] == "ELIGIBLE"); a["eligibility"] = "NOT_ELIGIBLE"
    assert "eligibility" in categories(tamper(tables, f))


def test_detects_wrong_settlement_amount(tables):
    def f(t): t["settlement"][0]["settlement_amount"] += 1
    assert "settlement amount" in categories(tamper(tables, f))


def test_detects_settlement_above_limit(tables):
    def f(t): t["settlement"][0]["settlement_amount"] = 99999999.0
    assert "settlement above limit" in categories(tamper(tables, f))


def test_detects_wrong_reserve(tables):
    def f(t): t["reserve"][0]["reserve_amount"] += 5
    assert "reserve v1" in categories(tamper(tables, f))


def test_detects_claim_amount_not_matching_items(tables):
    def f(t): t["claim"][0]["claimed_amount"] += 1
    assert "claim amount != sum of items" in categories(tamper(tables, f))


def test_detects_missing_mandatory_document(tables):
    def f(t):
        cid = t["assessment"][0]["claim_id"]
        t["document"] = [d for d in t["document"] if not (d["claim_id"] == cid and d["doc_type"] == "ID_PROOF")]
    assert {"eligibility", "assessment_check log"} <= categories(tamper(tables, f))


def test_detects_incident_moved_outside_coverage_period(tables):
    def f(t):
        i = t["incident"][0]
        p = next(x for x in t["policy"] if x["policy_id"] == i["policy_id"])
        i["incident_date"] = p["start_date"].replace(year=p["start_date"].year - 1)
    assert categories(tamper(tables, f)) & {"eligibility", "reason code", "assessment_check log"}


def test_detects_altered_check_log(tables):
    def f(t): t["assessment_check"][0]["result"] = "FAIL"
    assert "assessment_check log" in categories(tamper(tables, f))


def test_detects_illegal_status_change_and_status_not_matching_last_event(tables):
    def f(t): t["claim_status_event"][1]["to_status"] = "SETTLED"
    assert "illegal status transition" in categories(tamper(tables, f))

    def g(t): t["claim"][0]["status"] = "CLOSED" if t["claim"][0]["status"] != "CLOSED" else "SUBMITTED"
    assert "status != last event" in categories(tamper(tables, g))


def test_detects_second_settlement_for_the_same_claim(tables):
    def f(t):
        s = copy.deepcopy(t["settlement"][0]); s["settlement_id"] = s["settlement_id"][:-3] + "002"
        t["settlement"].append(s)
    assert "settlement count" in categories(tamper(tables, f))


def test_detects_decision_reason_removed(tables):
    def f(t): next(c for c in t["claim"] if c["decision_reason"])["decision_reason"] = None
    assert "claim.decision_reason" in categories(tamper(tables, f))