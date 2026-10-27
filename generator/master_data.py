"""Step 4 - master tables: Customer, Coverage, Policy, PolicyCoverage, Adjuster.

Run:  python -m generator.master_data --policies 2000 --seed 20261022 --out data

Order matters (parents first): Customer -> Coverage -> Policy -> PolicyCoverage -> Adjuster.
Every table has its own random stream derived from (seed, table name), so the output is
identical for the same seed and changing one table's logic does not shuffle the others.
"""
import argparse
import csv
import hashlib
import math
import os
import random
from datetime import timedelta

from generator import config as C
from generator import ids

COLUMNS = {
    "customer": ["customer_id", "full_name", "date_of_birth", "city", "kyc_status", "created_date"],
    "coverage": ["coverage_id", "claim_type", "description", "default_limit",
                 "default_deductible", "exclusions"],
    "policy": ["policy_id", "customer_id", "product", "start_date", "end_date", "status",
               "cancelled_date", "premium"],
    "policy_coverage": ["policy_id", "coverage_id", "coverage_limit", "deductible",
                        "effective_from", "effective_to"],
    "adjuster": ["adjuster_id", "name", "specialization", "region", "max_authority"],
}


def _rng(seed, stream):
    # string seeds are hashed deterministically by Python (independent of PYTHONHASHSEED)
    return random.Random(f"{seed}:{stream}")


def _rand_date(rng, start, end):
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _weighted(rng, pairs):
    values, weights = zip(*pairs)
    return rng.choices(values, weights=weights, k=1)[0]


# ----------------------------------------------------------------------------
def generate_customers(n, seed):
    rng = _rng(seed, "customer")
    rows = []
    for i in range(1, n + 1):
        age = rng.triangular(C.CUSTOMER_AGE_MIN, C.CUSTOMER_AGE_MAX, C.CUSTOMER_AGE_MODE)
        dob = C.AGE_REFERENCE_DATE - timedelta(days=int(age * 365.25) + 1)
        rows.append({
            "customer_id": ids.customer_id(i),
            "full_name": f"{rng.choice(C.FIRST_NAMES)} {rng.choice(C.LAST_NAMES)}",
            "date_of_birth": dob,
            "city": rng.choice(C.CITIES),
            "kyc_status": "VERIFIED" if rng.random() < C.KYC_VERIFIED_PROB else "PENDING",
            "created_date": _rand_date(rng, C.CUSTOMER_CREATED_MIN, C.CUSTOMER_CREATED_MAX),
        })
    return rows


def generate_coverage():
    """Fixed catalog from config; no randomness needed."""
    rows = []
    for product, seq, desc, limit, ded, excl in C.COVERAGE_CATALOG:
        rows.append({
            "coverage_id": ids.coverage_id(product, seq),
            "claim_type": product,
            "description": desc,
            "default_limit": float(limit),
            "default_deductible": float(ded),
            "exclusions": "|".join(excl),
        })
    return rows


def generate_policies(customers, n_policies, seed):
    """Each customer gets at least one policy; the rest are spread randomly.
    Status is DERIVED from dates (never assigned independently)."""
    if n_policies < len(customers):
        raise ValueError("need at least as many policies as customers")
    rng = _rng(seed, "policy")
    created = {c["customer_id"]: c["created_date"] for c in customers}

    owners = [c["customer_id"] for c in customers]
    rng.shuffle(owners)
    owners += [rng.choice(owners) for _ in range(n_policies - len(customers))]

    products = list(C.PRODUCT_WEIGHTS)
    weights = [C.PRODUCT_WEIGHTS[p] for p in products]

    drafts = []
    for cust in owners:
        product = rng.choices(products, weights=weights, k=1)[0]
        window_start = max(created[cust], C.POLICY_START_MIN)       # policy never starts before the customer exists
        start = _rand_date(rng, window_start, C.POLICY_START_MAX)
        end = start + timedelta(days=C.POLICY_TERM_DAYS)

        # termination decided from documented probabilities, only if it already happened
        cancelled, status = None, None
        draw = rng.random()
        days_elapsed = (C.AS_OF_DATE - start).days
        if days_elapsed >= C.MIN_DAYS_BEFORE_CANCEL and draw < C.CANCEL_PROB + C.LAPSE_PROB:
            last = min(C.POLICY_TERM_DAYS - 1, days_elapsed)
            cancelled = start + timedelta(days=rng.randint(C.MIN_DAYS_BEFORE_CANCEL, last))
            status = "CANCELLED" if draw < C.CANCEL_PROB else "LAPSED"
        elif end < C.AS_OF_DATE:
            status = "EXPIRED"
        else:
            status = "ACTIVE"

        premium = rng.lognormvariate(math.log(C.PREMIUM_MEDIAN[product]), C.PREMIUM_SIGMA)
        premium = max(premium, 0.3 * C.PREMIUM_MEDIAN[product])
        drafts.append((start, cust, product, end, status, cancelled, round(premium, 2)))

    drafts.sort(key=lambda d: (d[0], d[1], d[2]))   # IDs increase with start date
    rows = []
    for n, (start, cust, product, end, status, cancelled, premium) in enumerate(drafts, 1):
        rows.append({
            "policy_id": ids.policy_id(product, n),
            "customer_id": cust,
            "product": product,
            "start_date": start,
            "end_date": end,
            "status": status,
            "cancelled_date": cancelled,
            "premium": premium,
        })
    return rows


def generate_policy_coverage(policies, coverages, seed):
    rng = _rng(seed, "policy_coverage")
    by_product = {}
    for cov in coverages:
        by_product.setdefault(cov["claim_type"], []).append(cov)

    rows = []
    for pol in policies:
        for k, cov in enumerate(by_product[pol["product"]]):
            if k > 0 and rng.random() >= C.EXTRA_COVERAGE_PROB:
                continue                                           # coverage 01 is always included
            limit = round(cov["default_limit"] * _weighted(rng, C.LIMIT_FACTORS), 2)
            ded = cov["default_deductible"] * _weighted(rng, C.DEDUCTIBLE_FACTORS)
            ded = float(round(ded / C.DEDUCTIBLE_ROUNDING) * C.DEDUCTIBLE_ROUNDING)
            rows.append({
                "policy_id": pol["policy_id"],
                "coverage_id": cov["coverage_id"],
                "coverage_limit": limit,
                "deductible": min(ded, limit),
                "effective_from": pol["start_date"],
                "effective_to": pol["cancelled_date"] or pol["end_date"],
            })
    return rows


def generate_adjusters(n, seed):
    rng = _rng(seed, "adjuster")
    rows = []
    for i in range(1, n + 1):
        spec = C.PRODUCTS[(i - 1) % len(C.PRODUCTS)]               # round robin: every product is covered
        if i <= len(C.PRODUCTS):
            authority = C.SENIOR_AUTHORITY                           # first adjuster per product is senior
        else:
            authority = _weighted(rng, C.AUTHORITY_TIERS)
        rows.append({
            "adjuster_id": ids.adjuster_id(i),
            "name": f"{rng.choice(C.FIRST_NAMES)} {rng.choice(C.LAST_NAMES)}",
            "specialization": spec,
            "region": rng.choice(C.REGIONS),
            "max_authority": float(authority),
        })
    return rows


# ----------------------------------------------------------------------------
def build_master(n_policies=C.DEFAULT_POLICIES, seed=C.SEED):
    n_customers = max(1, int(n_policies * C.CUSTOMERS_PER_POLICY))
    n_adjusters = max(C.MIN_ADJUSTERS, n_policies // C.POLICIES_PER_ADJUSTER)
    customers = generate_customers(n_customers, seed)
    coverage = generate_coverage()
    policies = generate_policies(customers, n_policies, seed)
    policy_coverage = generate_policy_coverage(policies, coverage, seed)
    adjusters = generate_adjusters(n_adjusters, seed)
    return {"customer": customers, "coverage": coverage, "policy": policies,
            "policy_coverage": policy_coverage, "adjuster": adjusters}


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.2f}"
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def write_csv(name, rows, out_dir):
    path = os.path.join(out_dir, f"{name}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS[name])
        for r in rows:
            w.writerow([_fmt(r[c]) for c in COLUMNS[name]])
    return path


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate master tables (Step 4).")
    ap.add_argument("--policies", type=int, default=C.DEFAULT_POLICIES)
    ap.add_argument("--seed", type=int, default=C.SEED)
    ap.add_argument("--out", default="data")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    tables = build_master(args.policies, args.seed)
    print(f"seed={args.seed} policies={args.policies} as_of={C.AS_OF_DATE}")
    for name, rows in tables.items():
        path = write_csv(name, rows, args.out)
        print(f"  {name:16s} {len(rows):6d} rows  sha256={sha256(path)[:16]}")
    counts = {}
    for p in tables["policy"]:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    print("  policy status:", dict(sorted(counts.items())))
    return tables


if __name__ == "__main__":
    main()