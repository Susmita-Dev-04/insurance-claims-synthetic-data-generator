"""Tests for Step 4 master tables. Run with:  python -m pytest -v"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from generator import config as C
from generator.master_data import build_master, main

N = 300   # small scale: the same generator, just parameterised


@pytest.fixture(scope="module")
def t():
    return build_master(N, C.SEED)


def test_row_counts(t):
    assert len(t["policy"]) == N
    assert len(t["customer"]) == int(N * C.CUSTOMERS_PER_POLICY)
    assert len(t["coverage"]) == len(C.COVERAGE_CATALOG)
    assert len(t["adjuster"]) >= C.MIN_ADJUSTERS


@pytest.mark.parametrize("table,key", [("customer", "customer_id"), ("policy", "policy_id"),
                                        ("coverage", "coverage_id"), ("adjuster", "adjuster_id")])
def test_primary_keys_unique(t, table, key):
    values = [r[key] for r in t[table]]
    assert len(values) == len(set(values))


def test_policy_coverage_composite_key_unique(t):
    keys = [(r["policy_id"], r["coverage_id"]) for r in t["policy_coverage"]]
    assert len(keys) == len(set(keys))


def test_id_formats(t):
    assert all(re.fullmatch(r"POL-(AUTO|HLTH|PROP|TRVL|LIAB)-2026-\d{6}", r["policy_id"]) for r in t["policy"])
    assert all(re.fullmatch(r"CUST-\d{6}", r["customer_id"]) for r in t["customer"])
    assert all(re.fullmatch(r"COV-[A-Z]{4}-\d{2}", r["coverage_id"]) for r in t["coverage"])
    assert all(re.fullmatch(r"ADJ-\d{3}", r["adjuster_id"]) for r in t["adjuster"])
    # product inside the policy ID equals the product column; counter is sequential
    for n, r in enumerate(t["policy"], 1):
        assert r["policy_id"] == f"POL-{r['product']}-2026-{n:06d}"


def test_foreign_keys(t):
    cust = {r["customer_id"] for r in t["customer"]}
    pol = {r["policy_id"]: r for r in t["policy"]}
    cov = {r["coverage_id"]: r for r in t["coverage"]}
    assert all(r["customer_id"] in cust for r in t["policy"])
    for r in t["policy_coverage"]:
        assert r["policy_id"] in pol and r["coverage_id"] in cov
        assert cov[r["coverage_id"]]["claim_type"] == pol[r["policy_id"]]["product"]


def test_every_customer_has_a_policy_and_every_policy_has_coverage(t):
    assert {r["customer_id"] for r in t["policy"]} == {r["customer_id"] for r in t["customer"]}
    assert {r["policy_id"] for r in t["policy_coverage"]} == {r["policy_id"] for r in t["policy"]}


def test_policy_dates_and_status_are_derived_from_dates(t):
    created = {r["customer_id"]: r["created_date"] for r in t["customer"]}
    for r in t["policy"]:
        assert r["end_date"] > r["start_date"]
        assert r["start_date"] >= created[r["customer_id"]]
        assert r["premium"] > 0
        if r["status"] in ("CANCELLED", "LAPSED"):
            assert r["cancelled_date"] is not None
            assert r["start_date"] <= r["cancelled_date"] <= min(r["end_date"], C.AS_OF_DATE)
        else:
            assert r["cancelled_date"] is None
            expected = "EXPIRED" if r["end_date"] < C.AS_OF_DATE else "ACTIVE"
            assert r["status"] == expected


def test_policy_status_mix_has_all_four_states():
    big = build_master(C.DEFAULT_POLICIES, C.SEED)
    assert {r["status"] for r in big["policy"]} == {"ACTIVE", "EXPIRED", "CANCELLED", "LAPSED"}


def test_customer_rules(t):
    for r in t["customer"]:
        age = (C.AGE_REFERENCE_DATE - r["date_of_birth"]).days / 365.25
        assert 18 <= age <= 80.5
        assert r["kyc_status"] in ("VERIFIED", "PENDING")
        assert r["city"] in C.CITIES


def test_coverage_rules(t):
    for r in t["coverage"]:
        assert r["default_limit"] > 0 and 0 <= r["default_deductible"] < r["default_limit"]
        for ex in filter(None, r["exclusions"].split("|")):
            assert ex in C.INCIDENT_TYPES[r["claim_type"]]
    # every incident type is covered by at least one coverage (not excluded by all)
    for product, types in C.INCIDENT_TYPES.items():
        covs = [r for r in t["coverage"] if r["claim_type"] == product]
        for it in types:
            assert any(it not in r["exclusions"].split("|") for r in covs)


def test_policy_coverage_limits_and_dates(t):
    cov = {r["coverage_id"]: r for r in t["coverage"]}
    pol = {r["policy_id"]: r for r in t["policy"]}
    for r in t["policy_coverage"]:
        base = cov[r["coverage_id"]]["default_limit"]
        assert 0.5 * base <= r["coverage_limit"] <= 2.0 * base
        assert 0 <= r["deductible"] < r["coverage_limit"]
        p = pol[r["policy_id"]]
        assert r["effective_from"] == p["start_date"]
        assert r["effective_to"] == (p["cancelled_date"] or p["end_date"])


def test_adjusters_cover_every_product_with_a_senior(t):
    for product in C.PRODUCTS:
        specs = [r for r in t["adjuster"] if r["specialization"] == product]
        assert specs and max(r["max_authority"] for r in specs) == C.SENIOR_AUTHORITY


def test_same_seed_same_output_and_different_seed_differs():
    assert build_master(N, C.SEED) == build_master(N, C.SEED)
    assert build_master(N, C.SEED) != build_master(N, C.SEED + 1)


def test_csv_files_written_and_identical_on_rerun(tmp_path):
    main(["--policies", "100", "--out", str(tmp_path / "a")])
    main(["--policies", "100", "--out", str(tmp_path / "b")])
    for name in ("customer", "coverage", "policy", "policy_coverage", "adjuster"):
        a = (tmp_path / "a" / f"{name}.csv").read_bytes()
        b = (tmp_path / "b" / f"{name}.csv").read_bytes()
        assert a == b and len(a) > 0
    with open(tmp_path / "a" / "policy.csv", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 100