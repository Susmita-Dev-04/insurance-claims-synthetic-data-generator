"""Step 5 - dependent (transaction/event) tables, CLEAN BASELINE ONLY.

Order (parents first): Incident -> Claim -> ClaimItem -> Document -> ClaimAssignment ->
Assessment -> Reserve -> Settlement, plus ClaimStatusEvent (history of every status change).

Run:  python -m generator.transactions --policies 2000 --claims 1000 --seed 20261022 --out data

Everything that looks like an outcome (eligibility, reason, reserve, settlement, status) is
DERIVED from the rules in generator/rules.py and from the claim's own dates. Nothing is
assigned at random. Anomalies are NOT injected here; that is the next step.
"""
import argparse
import itertools
import os
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from generator import config as C
from generator import ids
from generator import rules as R
from generator.master_data import _fmt, build_master, write_csv as write_master_csv, sha256, _rng

TXN_COLUMNS = {
    "incident": ["incident_id", "policy_id", "incident_type", "incident_date", "location", "reported_date"],
    "claim": ["claim_id", "policy_id", "incident_id", "claim_type", "claim_date", "claimed_amount",
              "status", "decision_reason"],
    "claim_item": ["claim_item_id", "claim_id", "coverage_id", "item_type", "claimed_amount", "approved_amount"],
    "document": ["document_id", "claim_id", "doc_type", "is_mandatory", "status", "received_date"],
    "claim_assignment": ["assignment_id", "claim_id", "adjuster_id", "assigned_date", "status"],
    "assessment": ["assessment_id", "claim_id", "assignment_id", "eligibility", "reason_code",
                   "assessed_amount", "fraud_score", "assessed_date"],
    "assessment_check": ["check_id", "assessment_id", "claim_id", "check_code", "check_name", "result",
                         "observed_value", "threshold_value", "reason_code"],
    "reserve": ["reserve_id", "claim_id", "assessment_id", "reserve_amount", "version", "created_date"],
    "settlement": ["settlement_id", "claim_id", "assessment_id", "settlement_amount", "deductible_applied",
                   "status", "payment_date"],
    "claim_status_event": ["event_id", "claim_id", "from_status", "to_status", "event_timestamp", "reason"],
}


def _days(rng, lo_hi):
    return timedelta(days=rng.randint(*lo_hi))


def _weighted(rng, pairs):
    values, weights = zip(*pairs)
    return rng.choices(values, weights=weights, k=1)[0]


# ----------------------------------------------------------------------------
def _draft_claims(master, n_claims, seed):
    """Pick policy, incident type, coverage, dates and amount for each claim. No IDs yet."""
    rng = _rng(seed, "claim_draft")
    policies = master["policy"]
    cov_by_id = {c["coverage_id"]: c for c in master["coverage"]}
    pcs = defaultdict(list)
    for pc in master["policy_coverage"]:
        pcs[pc["policy_id"]].append(pc)

    weight_of = {}
    for cust in master["customer"]:
        weight_of[cust["customer_id"]] = (C.FREQUENT_CLAIMANT_WEIGHT
                                          if rng.random() < C.FREQUENT_CLAIMANT_PROB else 1)
    cum = list(itertools.accumulate(weight_of[p["customer_id"]] for p in policies))

    used, drafts = set(), []
    while len(drafts) < n_claims:
        pol = rng.choices(policies, cum_weights=cum, k=1)[0]
        pc_list = pcs[pol["policy_id"]]
        prod = pol["product"]

        # incident type and the coverage that will be claimed on
        covered, uncovered = [], []
        for t in C.INCIDENT_TYPES[prod]:
            (covered if any(R.covers(cov_by_id[pc["coverage_id"]]["exclusions"], t) for pc in pc_list)
             else uncovered).append(t)
        if uncovered and rng.random() < C.EXCLUDED_CLAIM_PROB:
            itype = rng.choice(uncovered)
            pc = pc_list[0]                                   # coverage 01 is always on the policy
        else:
            itype = rng.choice(covered)
            pc = rng.choice([p for p in pc_list if R.covers(cov_by_id[p["coverage_id"]]["exclusions"], itype)])

        # dates: incident always inside the coverage period (clean baseline)
        eff_end = min(pol["cancelled_date"] or pol["end_date"], C.AS_OF_DATE)
        incident_date = pol["start_date"] + timedelta(days=rng.randint(0, (eff_end - pol["start_date"]).days))
        key = (pol["policy_id"], itype, incident_date)
        if key in used:
            continue                                           # keep baseline free of duplicate incidents
        used.add(key)

        if rng.random() < C.LATE_REPORT_PROB:
            delay = rng.randint(*C.LATE_REPORT_RANGE)
        else:
            delay = rng.randint(0, C.REPORT_DELAY_MAX[prod])
        reported = min(incident_date + timedelta(days=delay), C.AS_OF_DATE)
        claim_date = min(reported + timedelta(days=rng.randint(0, C.FILING_DELAY_MAX)), C.AS_OF_DATE)

        # amount
        lo, hi, _w = _weighted(rng, [((a, b, w), w) for a, b, w in C.AMOUNT_BUCKETS])
        limit = pc["coverage_limit"]
        amount = limit * rng.uniform(lo, hi)
        amount = int(amount / C.CLAIM_ROUNDING) * C.CLAIM_ROUNDING
        amount = max(amount, C.MIN_CLAIM_AMOUNT, int(pc["deductible"] * 1.5))
        amount = min(amount, C.MAX_CLAIM_AMOUNT)

        drafts.append(dict(policy=pol, pc=pc, itype=itype, incident_date=incident_date,
                           reported=reported, claim_date=claim_date, claimed_c=R.to_cents(amount),
                           location=rng.choice(C.CITIES)))
    return drafts


def _ts(rng, day, prev):
    t = datetime(day.year, day.month, day.day, 9 + rng.randint(0, 8), rng.randint(0, 59), 0)
    if prev is not None and t <= prev:
        t = prev + timedelta(minutes=rng.randint(5, 90))
    return t


def build_transactions(master, n_claims=C.DEFAULT_CLAIMS, seed=C.SEED):
    drafts = _draft_claims(master, n_claims, seed)
    rng = _rng(seed, "claim_flow")
    as_of = C.AS_OF_DATE

    customer_of = {p["policy_id"]: p["customer_id"] for p in master["policy"]}
    adjusters = master["adjuster"]

    # incident IDs follow incident date, claim IDs follow claim date (both deterministic)
    for i, d in enumerate(sorted(range(len(drafts)), key=lambda k: (
            drafts[k]["incident_date"], drafts[k]["policy"]["policy_id"], drafts[k]["itype"]))):
        drafts[d]["incident_id"] = ids.incident_id(i + 1)
    order = sorted(range(len(drafts)), key=lambda k: (
        drafts[k]["claim_date"], drafts[k]["policy"]["policy_id"], drafts[k]["incident_date"], drafts[k]["itype"]))
    claims_sorted = [drafts[k] for k in order]
    for i, d in enumerate(claims_sorted):
        d["claim_id"] = ids.claim_id(i + 1)

    dates_by_customer = defaultdict(list)
    for d in claims_sorted:
        dates_by_customer[customer_of[d["policy"]["policy_id"]]].append(d["claim_date"])

    T = {name: [] for name in TXN_COLUMNS}
    seen_keys = set()

    for d in claims_sorted:
        pol, pc = d["policy"], d["pc"]
        cid, prod = d["claim_id"], pol["product"]
        claimed_c, limit_c, ded_c = d["claimed_c"], R.to_cents(pc["coverage_limit"]), R.to_cents(pc["deductible"])
        claim_date = d["claim_date"]

        T["incident"].append(dict(incident_id=d["incident_id"], policy_id=pol["policy_id"],
                                  incident_type=d["itype"], incident_date=d["incident_date"],
                                  location=d["location"], reported_date=d["reported"]))

        # ---- items (sum of items == claim amount, exactly) ----
        n_items = _weighted(rng, C.ITEMS_PER_CLAIM)
        item_c = R.allocate(claimed_c, [rng.randint(1, 10) for _ in range(n_items)])
        item_types = [rng.choice(C.ITEM_TYPES[prod]) for _ in range(n_items)]

        # ---- documents: mandatory ones always exist; some arrive late after a request ----
        mand = R.mandatory_docs(prod, d["itype"])
        docs_late = (claim_date + timedelta(days=C.DOCS_LATE_MIN_AGE) <= as_of
                     and rng.random() < C.DOCS_LATE_PROB)
        late_types = set()
        events = [(claim_date, "SUBMITTED", "CLAIM_RECEIVED")]
        docs_complete = claim_date
        recv_late = None
        if docs_late:
            pool = [t for t in mand if t != "CLAIM_FORM"]
            late_types = set(rng.sample(pool, k=min(len(pool), rng.randint(1, 2))))
            req_date = claim_date + timedelta(days=1)
            recv_late = req_date + _days(rng, C.DOCS_RECEIVE_DELAY)
            events.append((req_date, "DOCS_REQUESTED", "MANDATORY_DOCUMENT_PENDING"))
            docs_complete = recv_late
        doc_rows = [(t, True, recv_late if t in late_types else claim_date) for t in mand]
        if rng.random() < C.OPTIONAL_DOC_PROB:
            extra = [t for t in C.OPTIONAL_DOC_POOL[prod] if t not in mand]
            if extra:
                doc_rows.append((rng.choice(extra), False, claim_date))

        # ---- assignment (maybe one reassignment) ----
        qualified = [a for a in adjusters
                     if a["specialization"] == prod and a["max_authority"] * 100 >= claimed_c]
        a1_date = docs_complete + _days(rng, C.ASSESSMENT_START_DELAY)
        assignments = []          # (adjuster, date, status)
        assess_date = None
        if a1_date <= as_of:
            events.append((a1_date, "UNDER_ASSESSMENT", "ADJUSTER_ASSIGNED"))
            first = rng.choice(qualified)
            final_adj, final_date = first, a1_date
            others = [a for a in qualified if a["adjuster_id"] != first["adjuster_id"]]
            if others and rng.random() < C.REASSIGN_PROB:
                a2_date = a1_date + timedelta(days=rng.randint(1, 2))
                if a2_date <= as_of:
                    final_adj, final_date = rng.choice(others), a2_date
                    assignments.append((first, a1_date, "REASSIGNED"))
            assignments.append((final_adj, final_date, "ASSIGNED"))
            ad = final_date + _days(rng, C.ASSESSMENT_DURATION)
            if ad <= as_of:
                assess_date = ad

        # ---- preliminary reserve (version 1) exists for every claim ----
        T["reserve"].append(dict(reserve_id=ids.reserve_id(cid, 1), claim_id=cid, assessment_id=None,
                                 reserve_amount=R.reserve_cents(sum(item_c), limit_c, ded_c) / 100,
                                 version=1, created_date=claim_date))

        approved_c = [None] * n_items
        reason_for_claim = None
        asm = None
        if assess_date is not None:
            asm_id = ids.assessment_id(cid, 1)
            # fraud score from observable facts
            cust = customer_of[pol["policy_id"]]
            in_12m = sum(1 for x in dates_by_customer[cust]
                         if claim_date - timedelta(days=C.FRAUD_WINDOW_DAYS) < x <= claim_date)
            fscore, _flags = R.fraud_score((d["reported"] - d["incident_date"]).days,
                                           (d["incident_date"] - pol["start_date"]).days,
                                           claimed_c, limit_c, in_12m)
            cov_row = next(c for c in master["coverage"] if c["coverage_id"] == pc["coverage_id"])
            missing = [t for (t, m, rd) in doc_rows if m and rd > assess_date]
            key = (pol["policy_id"], d["itype"], d["incident_date"])
            checks = R.run_checks(
                claim_date=claim_date, incident_date=d["incident_date"],
                policy_start=pol["start_date"], policy_end=pol["end_date"],
                cancelled_date=pol["cancelled_date"], missing_mandatory=missing,
                is_duplicate=key in seen_keys, excluded=not R.covers(cov_row["exclusions"], d["itype"]),
                fraud=fscore, claimed_c=claimed_c, limit_c=limit_c)
            elig, reason = R.decide(checks)               # status is derived from the checks
            for n, ck in enumerate(checks, 1):
                T["assessment_check"].append(dict(
                    check_id=f"CHK-{asm_id[4:]}-{n:02d}", assessment_id=asm_id, claim_id=cid,
                    check_code=ck["code"], check_name=ck["name"],
                    result="PASS" if ck["passed"] else "FAIL", observed_value=ck["observed"],
                    threshold_value=ck["threshold"], reason_code=ck["reason"]))
            a_c = R.assessed_cents(elig, claimed_c, limit_c)
            approved_c = R.allocate_approved(item_c, a_c)
            asm = dict(assessment_id=asm_id, claim_id=cid,
                       assignment_id=ids.assignment_id(cid, len(assignments)),
                       eligibility=elig, reason_code=reason, assessed_amount=a_c / 100,
                       fraud_score=fscore, assessed_date=assess_date)
            T["assessment"].append(asm)
            reason_for_claim = reason
            T["reserve"].append(dict(reserve_id=ids.reserve_id(cid, 2), claim_id=cid, assessment_id=asm_id,
                                     reserve_amount=R.reserve_cents(sum(approved_c), limit_c, ded_c) / 100,
                                     version=2, created_date=assess_date))

            if elig in ("ELIGIBLE", "PARTIAL"):
                events.append((assess_date, "APPROVED", reason))
                pay_date = assess_date + _days(rng, C.PAYMENT_DELAY)
                paid = pay_date <= as_of
                T["settlement"].append(dict(
                    settlement_id=ids.settlement_id(cid, 1), claim_id=cid, assessment_id=asm_id,
                    settlement_amount=R.settlement_cents(sum(approved_c), limit_c, ded_c) / 100,
                    deductible_applied=ded_c / 100, status="PAID" if paid else "APPROVED",
                    payment_date=pay_date if paid else None))
                if paid:
                    events.append((pay_date, "SETTLED", "PAYMENT_MADE"))
                    close = pay_date + _days(rng, C.CLOSE_DELAY)
                    if close <= as_of:
                        events.append((close, "CLOSED", "CASE_CLOSED"))
            elif elig == "NOT_ELIGIBLE":
                events.append((assess_date, "REJECTED", reason))
                close = assess_date + _days(rng, C.REJECT_CLOSE_DELAY)
                if close <= as_of:
                    events.append((close, "CLOSED", "CASE_CLOSED"))
            # REFER_MANUAL: claim stays UNDER_ASSESSMENT; the assessment row is the audit record
        seen_keys.add((pol["policy_id"], d["itype"], d["incident_date"]))

        # ---- write child rows ----
        for i in range(n_items):
            T["claim_item"].append(dict(
                claim_item_id=ids.claim_item_id(cid, i + 1), claim_id=cid, coverage_id=pc["coverage_id"],
                item_type=item_types[i], claimed_amount=item_c[i] / 100,
                approved_amount=None if approved_c[i] is None else approved_c[i] / 100))
        for i, (t, m, rd) in enumerate(doc_rows):
            T["document"].append(dict(
                document_id=ids.document_id(cid, i + 1), claim_id=cid, doc_type=t,
                is_mandatory="TRUE" if m else "FALSE",
                status="VERIFIED" if assess_date is not None else "RECEIVED", received_date=rd))
        for i, (adj, adate, st) in enumerate(assignments):
            T["claim_assignment"].append(dict(
                assignment_id=ids.assignment_id(cid, i + 1), claim_id=cid, adjuster_id=adj["adjuster_id"],
                assigned_date=adate,
                status=("COMPLETED" if (st == "ASSIGNED" and assess_date is not None) else st)))
        prev_status, prev_ts = None, None
        for i, (day, status, why) in enumerate(events):
            prev_ts = _ts(rng, day, prev_ts)
            T["claim_status_event"].append(dict(
                event_id=ids.event_id(cid, i + 1), claim_id=cid, from_status=prev_status, to_status=status,
                event_timestamp=prev_ts.strftime("%Y-%m-%dT%H:%M:%SZ"), reason=why))
            prev_status = status
        T["claim"].append(dict(
            claim_id=cid, policy_id=pol["policy_id"], incident_id=d["incident_id"], claim_type=prod,
            claim_date=claim_date, claimed_amount=claimed_c / 100, status=prev_status,
            decision_reason=reason_for_claim))
    return T


# ----------------------------------------------------------------------------
def write_table(name, rows, out_dir):
    path = os.path.join(out_dir, f"{name}.csv")
    import csv
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(TXN_COLUMNS[name])
        for r in rows:
            w.writerow([_fmt(r[c]) for c in TXN_COLUMNS[name]])
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate master + clean transaction tables (Steps 4-5).")
    ap.add_argument("--policies", type=int, default=C.DEFAULT_POLICIES)
    ap.add_argument("--claims", type=int, default=C.DEFAULT_CLAIMS)
    ap.add_argument("--seed", type=int, default=C.SEED)
    ap.add_argument("--out", default="data")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    master = build_master(args.policies, args.seed)
    txn = build_transactions(master, args.claims, args.seed)
    print(f"seed={args.seed} policies={args.policies} claims={args.claims} as_of={C.AS_OF_DATE}")
    for name, rows in master.items():
        p = write_master_csv(name, rows, args.out)
        print(f"  {name:20s} {len(rows):6d} rows  sha256={sha256(p)[:16]}")
    for name, rows in txn.items():
        p = write_table(name, rows, args.out)
        print(f"  {name:20s} {len(rows):6d} rows  sha256={sha256(p)[:16]}")
    print("  claims by type:  ", dict(sorted(Counter(r["claim_type"] for r in txn["claim"]).items())))
    print("  claim status:    ", dict(sorted(Counter(r["status"] for r in txn["claim"]).items())))
    print("  eligibility:     ", dict(sorted(Counter(r["eligibility"] for r in txn["assessment"]).items())))
    print("  reason codes:    ", dict(sorted(Counter(r["reason_code"] for r in txn["assessment"]).items())))
    print("  failed checks:   ", dict(sorted(Counter(r["check_code"] for r in txn["assessment_check"] if r["result"] == "FAIL").items())))
    return master, txn


if __name__ == "__main__":
    main()