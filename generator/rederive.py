"""Independent audit: recompute every business outcome from the SOURCE records in the exported
CSV files and compare it with what the generator stored.

It proves that outcomes come from rules, not randomness:
  * incident inside coverage period?   * claim amount within the limit?
  * reserve from claim items           * settlement = max(0, min(approved, limit) - deductible)
  * eligibility + reason code from the checks   * claim status consistent with the outcome
  * check log (assessment_check) equals the recomputed checks

Run:  python -m generator.rederive --data data [--report docs/rule_audit.csv]
Exit code 0 = no mismatches, 1 = mismatches found.
"""
import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

from generator import config as C
from generator import rules as R

DATE_COLS = {"date_of_birth", "created_date", "start_date", "end_date", "cancelled_date", "effective_from",
             "effective_to", "incident_date", "reported_date", "claim_date", "received_date", "assigned_date",
             "assessed_date", "payment_date"}
MONEY_COLS = {"premium", "default_limit", "default_deductible", "coverage_limit", "deductible", "max_authority",
              "claimed_amount", "approved_amount", "assessed_amount", "reserve_amount", "settlement_amount",
              "deductible_applied"}
INT_COLS = {"fraud_score", "version"}
TABLES = ["customer", "coverage", "policy", "policy_coverage", "adjuster", "incident", "claim", "claim_item",
          "document", "claim_assignment", "assessment", "assessment_check", "reserve", "settlement",
          "claim_status_event"]


def load(data_dir):
    """Read the CSV files and convert types so the audit sees the same shapes as in-memory rows."""
    out = {}
    for name in TABLES:
        with open(os.path.join(data_dir, f"{name}.csv"), newline="", encoding="utf-8") as fh:
            rows = []
            for r in csv.DictReader(fh):
                for k, v in list(r.items()):
                    if v == "":
                        r[k] = None
                    elif k in DATE_COLS:
                        r[k] = date.fromisoformat(v)
                    elif k in MONEY_COLS:
                        r[k] = float(v)
                    elif k in INT_COLS:
                        r[k] = int(v)
                rows.append(r)
            out[name] = rows
    return out


def _c(x):
    return R.to_cents(x)


def audit(t):
    """Returns (mismatches, stats). mismatches = list of (claim_id, category, expected, actual)."""
    bad, stats = [], Counter()

    def miss(cid, cat, exp, act):
        bad.append((cid, cat, exp, act))

    pol = {p["policy_id"]: p for p in t["policy"]}
    cust_of = {p["policy_id"]: p["customer_id"] for p in t["policy"]}
    pcov = {(r["policy_id"], r["coverage_id"]): r for r in t["policy_coverage"]}
    cov = {c["coverage_id"]: c for c in t["coverage"]}
    inc = {i["incident_id"]: i for i in t["incident"]}
    items, docs, asms, chks, rsv, sets, evs, asg = (defaultdict(list) for _ in range(8))
    for r in t["claim_item"]: items[r["claim_id"]].append(r)
    for r in t["document"]: docs[r["claim_id"]].append(r)
    for r in t["assessment"]: asms[r["claim_id"]].append(r)
    for r in t["assessment_check"]: chks[r["assessment_id"]].append(r)
    for r in t["reserve"]: rsv[r["claim_id"]].append(r)
    for r in t["settlement"]: sets[r["claim_id"]].append(r)
    for r in t["claim_status_event"]: evs[r["claim_id"]].append(r)
    for r in t["claim_assignment"]: asg[r["claim_id"]].append(r)

    claims = sorted(t["claim"], key=lambda c: c["claim_id"])
    dates_by_cust = defaultdict(list)
    for c in claims:
        dates_by_cust[cust_of[c["policy_id"]]].append(c["claim_date"])
    seen = set()

    for c in claims:
        cid = c["claim_id"]
        p, i = pol[c["policy_id"]], inc[c["incident_id"]]
        its = items[cid]
        covs = {x["coverage_id"] for x in its}
        stats["claims audited"] += 1
        if len(covs) != 1:
            miss(cid, "items use more than one coverage", 1, len(covs)); continue
        pc = pcov.get((p["policy_id"], next(iter(covs))))
        if pc is None:
            miss(cid, "claim item coverage not on policy", "exists", "missing"); continue
        limit_c, ded_c = _c(pc["coverage_limit"]), _c(pc["deductible"])
        claimed_c = sum(_c(x["claimed_amount"]) for x in its)
        if claimed_c != _c(c["claimed_amount"]):
            miss(cid, "claim amount != sum of items", claimed_c, _c(c["claimed_amount"]))

        # preliminary reserve (version 1) is calculated from the claim items
        r_list = sorted(rsv[cid], key=lambda r: r["version"])
        exp1 = R.reserve_cents(claimed_c, limit_c, ded_c)
        if not r_list or _c(r_list[0]["reserve_amount"]) != exp1:
            miss(cid, "reserve v1", exp1, _c(r_list[0]["reserve_amount"]) if r_list else None)

        a_list = asms[cid]
        key = (p["policy_id"], i["incident_type"], i["incident_date"])
        if not a_list:
            # no assessment yet: no settlement, only the preliminary reserve, early status only
            if sets[cid]: miss(cid, "settlement without assessment", 0, len(sets[cid]))
            if len(r_list) != 1: miss(cid, "reserve versions without assessment", 1, len(r_list))
            if c["status"] not in ("SUBMITTED", "DOCS_REQUESTED", "UNDER_ASSESSMENT"):
                miss(cid, "status without assessment", "SUBMITTED/DOCS_REQUESTED/UNDER_ASSESSMENT", c["status"])
            seen.add(key); continue

        a = a_list[-1]
        stats["assessments audited"] += 1
        # facts recomputed from source records only
        need = R.mandatory_docs(c["claim_type"], i["incident_type"])
        got = {d["doc_type"] for d in docs[cid]
               if d["is_mandatory"] == "TRUE" and d["received_date"] is not None and d["received_date"] <= a["assessed_date"]}
        missing = [x for x in need if x not in got]
        in12 = sum(1 for x in dates_by_cust[cust_of[p["policy_id"]]]
                   if c["claim_date"] - timedelta(days=C.FRAUD_WINDOW_DAYS) < x <= c["claim_date"])
        fscore, _ = R.fraud_score((i["reported_date"] - i["incident_date"]).days,
                                  (i["incident_date"] - p["start_date"]).days, claimed_c, limit_c, in12)
        checks = R.run_checks(
            claim_date=c["claim_date"], incident_date=i["incident_date"], policy_start=p["start_date"],
            policy_end=p["end_date"], cancelled_date=p["cancelled_date"], missing_mandatory=missing,
            is_duplicate=key in seen, excluded=not R.covers(cov[pc["coverage_id"]]["exclusions"], i["incident_type"]),
            fraud=fscore, claimed_c=claimed_c, limit_c=limit_c)
        elig, reason = R.decide(checks)
        seen.add(key)

        if a["fraud_score"] != fscore: miss(cid, "fraud score", fscore, a["fraud_score"])
        if a["eligibility"] != elig: miss(cid, "eligibility", elig, a["eligibility"])
        if a["reason_code"] != reason: miss(cid, "reason code", reason, a["reason_code"])
        if c["decision_reason"] != a["reason_code"]: miss(cid, "claim.decision_reason", a["reason_code"], c["decision_reason"])

        # check log must equal the recomputed checks
        logged = sorted(chks[a["assessment_id"]], key=lambda r: r["check_code"])
        if [(x["check_code"], x["result"] == "PASS") for x in logged] != [(k["code"], k["passed"]) for k in checks]:
            miss(cid, "assessment_check log", [(k["code"], k["passed"]) for k in checks],
                 [(x["check_code"], x["result"] == "PASS") for x in logged])
        for k in checks:
            stats[f"check {k['code']} {'PASS' if k['passed'] else 'FAIL'}"] += 1

        # amounts
        approved = sum(_c(x["approved_amount"] or 0) for x in its)
        exp_assessed = R.assessed_cents(elig, claimed_c, limit_c)
        if approved != exp_assessed or _c(a["assessed_amount"]) != exp_assessed:
            miss(cid, "assessed amount", exp_assessed, (approved, _c(a["assessed_amount"])))
        if any(x["approved_amount"] is None or _c(x["approved_amount"]) > _c(x["claimed_amount"]) for x in its):
            miss(cid, "item approved amount invalid", "0..claimed", "out of range")
        exp2 = R.reserve_cents(approved, limit_c, ded_c)
        if len(r_list) < 2 or _c(r_list[1]["reserve_amount"]) != exp2:
            miss(cid, "reserve v2", exp2, _c(r_list[1]["reserve_amount"]) if len(r_list) > 1 else None)
        if any(_c(r["reserve_amount"]) > limit_c for r in r_list): miss(cid, "reserve above limit", limit_c, "above")

        s_list = sets[cid]
        if elig in ("ELIGIBLE", "PARTIAL"):
            exp_s = R.settlement_cents(approved, limit_c, ded_c)
            if len(s_list) != 1: miss(cid, "settlement count", 1, len(s_list))
            for s in s_list:
                if _c(s["settlement_amount"]) != exp_s: miss(cid, "settlement amount", exp_s, _c(s["settlement_amount"]))
                if _c(s["deductible_applied"]) != ded_c: miss(cid, "deductible applied", ded_c, _c(s["deductible_applied"]))
                if _c(s["settlement_amount"]) > limit_c: miss(cid, "settlement above limit", limit_c, _c(s["settlement_amount"]))
            want = {"APPROVED": ("APPROVED",), "PAID": ("SETTLED", "CLOSED")}.get(s_list[0]["status"], ()) if s_list else ()
            if c["status"] not in want: miss(cid, "status vs settlement", want, c["status"])
        elif s_list:
            miss(cid, "settlement on a claim that is not payable", 0, len(s_list))
        if elig == "NOT_ELIGIBLE" and c["status"] not in ("REJECTED", "CLOSED"):
            miss(cid, "status vs rejection", "REJECTED/CLOSED", c["status"])
        if elig == "REFER_MANUAL" and c["status"] != "UNDER_ASSESSMENT":
            miss(cid, "status vs manual referral", "UNDER_ASSESSMENT", c["status"])

        # status = last event, transitions legal
        ev = sorted(evs[cid], key=lambda e: e["event_id"])
        prev = None
        for e in ev:
            if e["from_status"] != prev or e["to_status"] not in R.TRANSITIONS[prev]:
                miss(cid, "illegal status transition", f"{prev}->?", f"{e['from_status']}->{e['to_status']}")
            prev = e["to_status"]
        if prev != c["status"]: miss(cid, "status != last event", prev, c["status"])
    return bad, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recompute all outcomes from source CSVs and compare.")
    ap.add_argument("--data", default="data")
    ap.add_argument("--report", default=None, help="optional CSV file listing every mismatch")
    args = ap.parse_args(argv)
    bad, stats = audit(load(args.data))
    for k, v in sorted(stats.items()):
        print(f"  {k:28s} {v}")
    print(f"mismatches: {len(bad)}")
    for row in bad[:20]:
        print("  MISMATCH", row)
    if args.report:
        os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
        with open(args.report, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["claim_id", "category", "expected", "actual"]); w.writerows(bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())