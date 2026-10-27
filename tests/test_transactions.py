"""Tests for Step 5 (clean baseline transaction tables). Run with:  python -m pytest -v"""
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from generator import config as C
from generator import rules as R
from generator.master_data import build_master
from generator.transactions import build_transactions, main

POLICIES, CLAIMS = 800, 400          # same generator, smaller scale = fast tests


@pytest.fixture(scope="module")
def data():
    m = build_master(POLICIES, C.SEED)
    return m, build_transactions(m, CLAIMS, C.SEED)


def cents(x):
    return int(round(x * 100))


def test_row_counts(data):
    _, t = data
    assert len(t["claim"]) == CLAIMS and len(t["incident"]) == CLAIMS
    assert len(t["claim_status_event"]) >= CLAIMS
    assert len(t["claim_item"]) >= CLAIMS and len(t["document"]) >= 3 * CLAIMS


@pytest.mark.parametrize("table,key", [
    ("incident", "incident_id"), ("claim", "claim_id"), ("claim_item", "claim_item_id"),
    ("document", "document_id"), ("claim_assignment", "assignment_id"), ("assessment", "assessment_id"),
    ("reserve", "reserve_id"), ("settlement", "settlement_id"), ("claim_status_event", "event_id")])
def test_primary_keys_unique(data, table, key):
    values = [r[key] for r in data[1][table]]
    assert len(values) == len(set(values))


def test_id_formats(data):
    _, t = data
    assert all(re.fullmatch(r"CLM-2026-\d{6}", r["claim_id"]) for r in t["claim"])
    assert all(re.fullmatch(r"INC-2026-\d{6}", r["incident_id"]) for r in t["incident"])
    for table, prefix, key in [("document", "DOC", "document_id"), ("claim_assignment", "ASN", "assignment_id"),
                               ("settlement", "SET", "settlement_id"), ("assessment", "ASM", "assessment_id"),
                               ("reserve", "RSV", "reserve_id"), ("claim_status_event", "EVT", "event_id"),
                               ("claim_item", "ITM", "claim_item_id")]:
        for r in t[table]:
            assert re.fullmatch(rf"{prefix}-CLM-2026-\d{{6}}-\d{{3}}", r[key])
            assert r[key][len(prefix) + 1:-4] == r["claim_id"]          # child ID embeds its own claim ID


def test_claim_ids_are_sequential_by_claim_date(data):
    claims = data[1]["claim"]
    assert [r["claim_id"] for r in claims] == [f"CLM-2026-{i:06d}" for i in range(1, len(claims) + 1)]
    dates = [r["claim_date"] for r in claims]
    assert dates == sorted(dates)


def test_foreign_keys(data):
    m, t = data
    pol = {p["policy_id"]: p for p in m["policy"]}
    inc = {r["incident_id"]: r for r in t["incident"]}
    clm = {r["claim_id"] for r in t["claim"]}
    adj = {a["adjuster_id"] for a in m["adjuster"]}
    asg = {r["assignment_id"]: r for r in t["claim_assignment"]}
    asm = {r["assessment_id"]: r for r in t["assessment"]}
    pc = {(r["policy_id"], r["coverage_id"]) for r in m["policy_coverage"]}
    assert all(r["policy_id"] in pol for r in t["incident"])
    for c in t["claim"]:
        assert c["policy_id"] in pol and c["incident_id"] in inc
        assert inc[c["incident_id"]]["policy_id"] == c["policy_id"]
        assert c["claim_type"] == pol[c["policy_id"]]["product"]
    for table in ("claim_item", "document", "claim_assignment", "assessment", "reserve",
                  "settlement", "claim_status_event"):
        assert all(r["claim_id"] in clm for r in t[table])
    pol_of = {c["claim_id"]: c["policy_id"] for c in t["claim"]}
    assert all((pol_of[r["claim_id"]], r["coverage_id"]) in pc for r in t["claim_item"])
    assert all(r["adjuster_id"] in adj for r in t["claim_assignment"])
    for a in t["assessment"]:
        assert a["assignment_id"] in asg and asg[a["assignment_id"]]["claim_id"] == a["claim_id"]
    for r in t["reserve"] + t["settlement"]:
        assert r["assessment_id"] is None or (r["assessment_id"] in asm and asm[r["assessment_id"]]["claim_id"] == r["claim_id"])
    assert all(s["assessment_id"] in asm for s in t["settlement"])


def test_incident_is_inside_coverage_period_in_clean_baseline(data):
    m, t = data
    pol = {p["policy_id"]: p for p in m["policy"]}
    for i in t["incident"]:
        p = pol[i["policy_id"]]
        assert p["start_date"] <= i["incident_date"] <= (p["cancelled_date"] or p["end_date"])
        assert i["incident_date"] <= C.AS_OF_DATE
        assert i["reported_date"] >= i["incident_date"]
        assert i["incident_type"] in C.INCIDENT_TYPES[p["product"]]


def test_date_ordering(data):
    _, t = data
    inc = {r["incident_id"]: r for r in t["incident"]}
    claim = {c["claim_id"]: c for c in t["claim"]}
    for c in t["claim"]:
        assert c["claim_date"] >= inc[c["incident_id"]]["reported_date"] >= inc[c["incident_id"]]["incident_date"]
        assert c["claim_date"] <= C.AS_OF_DATE
    asg = {r["assignment_id"]: r for r in t["claim_assignment"]}
    for a in t["claim_assignment"]:
        assert a["assigned_date"] >= claim[a["claim_id"]]["claim_date"]
    for a in t["assessment"]:
        assert a["assessed_date"] >= asg[a["assignment_id"]]["assigned_date"]
        assert a["assessed_date"] <= C.AS_OF_DATE
    for d in t["document"]:
        assert d["received_date"] >= claim[d["claim_id"]]["claim_date"]
    for s in t["settlement"]:
        if s["status"] == "PAID":
            asm_date = next(a["assessed_date"] for a in t["assessment"] if a["claim_id"] == s["claim_id"])
            assert s["payment_date"] >= asm_date and s["payment_date"] <= C.AS_OF_DATE
        else:
            assert s["payment_date"] is None


def test_item_amounts_reconcile_to_claim(data):
    _, t = data
    claimed = defaultdict(int)
    approved = defaultdict(int)
    for i in t["claim_item"]:
        claimed[i["claim_id"]] += cents(i["claimed_amount"])
        if i["approved_amount"] is not None:
            assert 0 <= cents(i["approved_amount"]) <= cents(i["claimed_amount"])
            approved[i["claim_id"]] += cents(i["approved_amount"])
    for c in t["claim"]:
        assert claimed[c["claim_id"]] == cents(c["claimed_amount"]) > 0
        assert c["claimed_amount"] <= C.MAX_CLAIM_AMOUNT
    for a in t["assessment"]:
        assert approved[a["claim_id"]] == cents(a["assessed_amount"])


def test_reserves_and_settlements_obey_limits_and_deductibles(data):
    m, t = data
    pc = {(r["policy_id"], r["coverage_id"]): r for r in m["policy_coverage"]}
    pol_of = {c["claim_id"]: c["policy_id"] for c in t["claim"]}
    cov_of = {}
    for i in t["claim_item"]:
        cov_of.setdefault(i["claim_id"], set()).add(i["coverage_id"])
    claimed = {c["claim_id"]: cents(c["claimed_amount"]) for c in t["claim"]}
    asm = {a["assessment_id"]: a for a in t["assessment"]}
    for cid, covs in cov_of.items():
        assert len(covs) == 1                                  # one coverage per claim in baseline

    def terms(cid):
        row = pc[(pol_of[cid], next(iter(cov_of[cid])))]
        return cents(row["coverage_limit"]), cents(row["deductible"])

    for r in t["reserve"]:
        limit, ded = terms(r["claim_id"])
        base = claimed[r["claim_id"]] if r["assessment_id"] is None else cents(asm[r["assessment_id"]]["assessed_amount"])
        assert cents(r["reserve_amount"]) == R.reserve_cents(base, limit, ded)
        assert cents(r["reserve_amount"]) <= limit
    for s in t["settlement"]:
        limit, ded = terms(s["claim_id"])
        a = cents(asm[s["assessment_id"]]["assessed_amount"])
        assert cents(s["deductible_applied"]) == ded
        assert cents(s["settlement_amount"]) == R.settlement_cents(a, limit, ded)
        assert 0 < cents(s["settlement_amount"]) <= limit
        assert asm[s["assessment_id"]]["eligibility"] in ("ELIGIBLE", "PARTIAL")


def test_reserve_versions_are_consecutive_and_history_is_kept(data):
    by = defaultdict(list)
    for r in data[1]["reserve"]:
        by[r["claim_id"]].append(r)
    for cid, rows in by.items():
        assert [r["version"] for r in rows] == list(range(1, len(rows) + 1))
        assert rows[0]["assessment_id"] is None
        assert [r["created_date"] for r in rows] == sorted(r["created_date"] for r in rows)


def test_every_claim_has_complete_mandatory_documents(data):
    _, t = data
    inc = {i["incident_id"]: i for i in t["incident"]}
    have = defaultdict(set)
    for d in t["document"]:
        if d["is_mandatory"] == "TRUE":
            have[d["claim_id"]].add(d["doc_type"])
        assert d["status"] in ("RECEIVED", "VERIFIED")
    for c in t["claim"]:
        assert set(R.mandatory_docs(c["claim_type"], inc[c["incident_id"]]["incident_type"])) == have[c["claim_id"]]


def test_adjuster_specialization_and_authority(data):
    m, t = data
    adj = {a["adjuster_id"]: a for a in m["adjuster"]}
    claim = {c["claim_id"]: c for c in t["claim"]}
    for a in t["claim_assignment"]:
        c = claim[a["claim_id"]]
        assert adj[a["adjuster_id"]]["specialization"] == c["claim_type"]
        assert adj[a["adjuster_id"]]["max_authority"] >= c["claimed_amount"]


def test_assignment_history_is_not_overwritten(data):
    by = defaultdict(list)
    for a in data[1]["claim_assignment"]:
        by[a["claim_id"]].append(a)
    assert any(len(v) == 2 for v in by.values())               # at least one reassignment exists
    for rows in by.values():
        for r in rows[:-1]:
            assert r["status"] == "REASSIGNED"
        assert rows[-1]["status"] in ("ASSIGNED", "COMPLETED")


def test_lifecycle_and_audit_trail(data):
    _, t = data
    ev = defaultdict(list)
    for e in t["claim_status_event"]:
        ev[e["claim_id"]].append(e)
    claim = {c["claim_id"]: c for c in t["claim"]}
    assert set(ev) == set(claim)
    for cid, rows in ev.items():
        prev, prev_ts = None, None
        for e in rows:
            assert e["from_status"] == prev
            assert e["to_status"] in R.TRANSITIONS[prev]
            ts = datetime.strptime(e["event_timestamp"], "%Y-%m-%dT%H:%M:%SZ")
            assert prev_ts is None or ts > prev_ts
            assert e["reason"]                                  # every decision has a reason
            prev, prev_ts = e["to_status"], ts
        assert claim[cid]["status"] == prev                     # claim status = last event
        assert rows[0]["to_status"] == "SUBMITTED"


def test_decisions_come_from_the_rules_and_have_reasons(data):
    _, t = data
    claim = {c["claim_id"]: c for c in t["claim"]}
    for a in t["assessment"]:
        assert a["reason_code"].startswith("R") and 0 <= a["fraud_score"] <= 100
        expected = {"ELIGIBLE": R.R01, "PARTIAL": R.R08, "REFER_MANUAL": R.R09}.get(a["eligibility"], R.R07)
        assert a["reason_code"] == expected                     # clean baseline: only R01, R07, R08, R09
        assert (a["fraud_score"] >= C.FRAUD_REFER_THRESHOLD) == (a["eligibility"] == "REFER_MANUAL") or a["reason_code"] == R.R07
        assert claim[a["claim_id"]]["decision_reason"] == a["reason_code"]
    for c in t["claim"]:
        if c["status"] in ("APPROVED", "REJECTED", "SETTLED", "CLOSED"):
            assert c["decision_reason"]


def test_status_matches_settlement_and_assessment(data):
    _, t = data
    claim = {c["claim_id"]: c for c in t["claim"]}
    asm = {a["claim_id"]: a for a in t["assessment"]}
    sets = Counter(s["claim_id"] for s in t["settlement"])
    assert max(sets.values()) == 1                              # nobody is paid twice in the baseline
    for s in t["settlement"]:
        want = {"PAID": ("SETTLED", "CLOSED"), "APPROVED": ("APPROVED",)}[s["status"]]
        assert claim[s["claim_id"]]["status"] in want
    for cid, a in asm.items():
        if a["eligibility"] == "NOT_ELIGIBLE":
            assert cid not in sets and claim[cid]["status"] in ("REJECTED", "CLOSED")


def test_no_duplicate_incidents_in_clean_baseline(data):
    keys = [(i["policy_id"], i["incident_type"], i["incident_date"]) for i in data[1]["incident"]]
    assert len(keys) == len(set(keys))


def test_all_five_claim_types_and_variety_present():
    m = build_master(C.DEFAULT_POLICIES, C.SEED)
    t = build_transactions(m, C.DEFAULT_CLAIMS, C.SEED)
    assert len(t["claim"]) == 1000
    assert {c["claim_type"] for c in t["claim"]} == set(C.PRODUCTS)
    assert {a["eligibility"] for a in t["assessment"]} == {"ELIGIBLE", "PARTIAL", "NOT_ELIGIBLE", "REFER_MANUAL"}
    assert {c["status"] for c in t["claim"]} >= {"SUBMITTED", "UNDER_ASSESSMENT", "APPROVED", "SETTLED", "CLOSED"}


def test_same_seed_same_output_and_different_seed_differs():
    m = build_master(300, C.SEED)
    assert build_transactions(m, 100, C.SEED) == build_transactions(m, 100, C.SEED)
    assert build_transactions(m, 100, C.SEED) != build_transactions(m, 100, C.SEED + 1)


def test_csv_files_identical_on_rerun(tmp_path):
    main(["--policies", "200", "--claims", "80", "--out", str(tmp_path / "a")])
    main(["--policies", "200", "--claims", "80", "--out", str(tmp_path / "b")])
    names = sorted(p.name for p in (tmp_path / "a").iterdir())
    assert len(names) == 14
    for n in names:
        assert (tmp_path / "a" / n).read_bytes() == (tmp_path / "b" / n).read_bytes()