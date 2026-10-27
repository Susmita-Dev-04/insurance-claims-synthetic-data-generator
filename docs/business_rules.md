# Business Rules

These are the rules the generator applies. They are implemented once, in `generator/rules.py`, and are used by the generator, by the audit (`generator/rederive.py`) and, later, by the ground truth. Every outcome in the data (eligibility, reason code, reserve, settlement, status) is derived from these rules and from the claim's own dates. Nothing is assigned independently at random.

**Dataset date ("as-of"):** 2026-10-22. Events dated after it do not exist, so recent claims are still in progress.
**Currency:** INR. Amounts are handled in integer cents inside the code.

---

## 1. Coverage period and policy status

| Rule | Definition |
|---|---|
| Policy term | `end_date = start_date + 364 days` (365 days counting both ends) |
| Covered dates | `start_date` to `end_date`, both days included |
| Cancelled or lapsed policy | Cover ends on `cancelled_date` (that day is still covered) |
| Policy status | CANCELLED or LAPSED if a `cancelled_date` has already happened; else EXPIRED if `end_date` is before the as-of date; else ACTIVE |

## 2. Eligibility checks (in this order)

All 8 checks are always evaluated and stored in the table `assessment_check`. The **first failed check** decides the outcome and the reason code.

| Check | Question | Fails when | Reason code | Outcome |
|---|---|---|---|---|
| CHK01 | Was the claim filed on or after the policy start? | claim date < policy start | R10_CLAIM_BEFORE_POLICY_START | NOT_ELIGIBLE |
| CHK02 | Is the incident date inside the coverage period? | incident date before start / after end | R02_INCIDENT_BEFORE_START / R03_INCIDENT_AFTER_END | NOT_ELIGIBLE |
| CHK03 | Was the policy still active at the incident? | incident date > cancelled date | R04_CANCELLED_BEFORE_INCIDENT | NOT_ELIGIBLE |
| CHK04 | Are all mandatory documents received? | a mandatory document is missing at assessment date | R05_MISSING_MANDATORY_DOC | NOT_ELIGIBLE |
| CHK05 | Is it a new claim? | same policy + incident type + incident date as an earlier claim | R06_DUPLICATE_CLAIM | NOT_ELIGIBLE |
| CHK06 | Is the incident type covered? | the claimed coverage excludes the incident type | R07_EXCLUSION_APPLIES | NOT_ELIGIBLE |
| CHK07 | Is the fraud score low enough? | fraud score >= 50 | R09_FRAUD_REVIEW | REFER_MANUAL |
| CHK08 | Is the claim amount within the limit? | claimed amount > coverage limit | R08_OVER_LIMIT_CAPPED | PARTIAL |
| (none failed) | | | R01_OK | ELIGIBLE |

Because the first failure wins, a duplicate claim that is also over the limit is rejected as a duplicate (R06), and the over-limit failure is still visible in the check log.

## 3. Money rules

| Item | Formula |
|---|---|
| Claim amount | sum of its claim items |
| Approved (assessed) amount | NOT_ELIGIBLE: 0. PARTIAL: `min(claimed, limit)`. ELIGIBLE and REFER_MANUAL: `claimed` |
| Reserve v1 (preliminary, at intake) | `max(0, min(sum of claimed items, limit) - deductible)` |
| Reserve v2 (after assessment) | `max(0, min(sum of approved items, limit) - deductible)` |
| Settlement | `max(0, min(approved amount, limit) - deductible)` |

Limit and deductible are those of the claimed coverage on **that policy** (table `policy_coverage`), not the catalog default.

**Worked examples** (limit 500,000, deductible 5,000):

| Claimed | Eligibility | Approved | Reserve v1 | Settlement |
|---|---|---|---|---|
| 100,000 | ELIGIBLE (R01) | 100,000 | 95,000 | 95,000 |
| 600,000 | PARTIAL (R08) | 500,000 | 495,000 | 495,000 |

## 4. Fraud score

Points are added from four facts in the data. The maximum is 90, the referral threshold is 50.

| Indicator | Rule | Points |
|---|---|---|
| Late reporting | reported more than 14 days after the incident | 20 |
| New policy | incident within 30 days of the policy start | 25 |
| Near limit | claimed amount at least 90% of the coverage limit | 20 |
| Repeat claimant | customer has 3 or more claims in the last 12 months (including this one) | 25 |

## 5. Mandatory documents

| Product | Always required | Extra, by incident type |
|---|---|---|
| AUTO | CLAIM_FORM, ID_PROOF, REPAIR_ESTIMATE | POLICE_REPORT for THEFT and COLLISION |
| HLTH | CLAIM_FORM, ID_PROOF, MEDICAL_REPORT, INVOICE | none |
| PROP | CLAIM_FORM, ID_PROOF, INCIDENT_REPORT, PHOTOS | POLICE_REPORT for BURGLARY |
| TRVL | CLAIM_FORM, ID_PROOF, INVOICE | MEDICAL_REPORT for MEDICAL_ABROAD |
| LIAB | CLAIM_FORM, ID_PROOF, INCIDENT_REPORT | none |

Optional documents (`is_mandatory = FALSE`) are added to about 30% of claims.

## 6. Claim lifecycle

Allowed status transitions (anything else is a violation):

| From | To |
|---|---|
| (start) | SUBMITTED |
| SUBMITTED | DOCS_REQUESTED, UNDER_ASSESSMENT |
| DOCS_REQUESTED | UNDER_ASSESSMENT, REJECTED |
| UNDER_ASSESSMENT | APPROVED, REJECTED |
| APPROVED | SETTLED |
| SETTLED, REJECTED | CLOSED |

How the status follows from the checks:

- ELIGIBLE or PARTIAL: APPROVED, then SETTLED when the payment is made, then CLOSED.
- NOT_ELIGIBLE: REJECTED, then CLOSED.
- REFER_MANUAL: stays UNDER_ASSESSMENT (waiting for a human). The assessment row is the audit record.
- `claim.status` always equals the `to_status` of the latest event.

## 7. History is never overwritten

| What changes | How it is recorded |
|---|---|
| Claim status | a new row in `claim_status_event` (with reason, timestamp strictly increasing) |
| Reserve amount | a new row with `version + 1` in `reserve` |
| Adjuster assignment | the old assignment becomes REASSIGNED, a new row ASN-...-002 is added |
| Eligibility decision | `assessment` row plus 8 rows in `assessment_check` |

## 8. Adjusters

An adjuster is assigned only to claims of his or her own product, and only if the claim amount is within the adjuster's `max_authority`. The first adjuster of each product is senior (authority 5,000,000). The claim amount is capped at 5,000,000 so a qualified adjuster always exists.

## 9. How the planned edge cases are classified by these rules

| Required edge case | How it will be injected | Expected decision (from the rules) |
|---|---|---|
| Claim date before policy start | claim date moved before policy start | NOT_ELIGIBLE, R10 |
| Policy cancelled before incident | incident date after the cancelled date | NOT_ELIGIBLE, R04 |
| Duplicate incident | second claim, same policy + type + date | NOT_ELIGIBLE, R06 |
| Settlement exceeds limit | stored settlement above the coverage limit | settlement must be `min(approved, limit) - deductible` |
| Missing mandatory document | a mandatory document removed | NOT_ELIGIBLE, R05 |
| Claim paid twice | a second PAID settlement for the same claim | only one payment is valid |

The audit (`python -m generator.rederive`) recomputes all of this from the CSV files, so every injected case will be detected as a mismatch against the rules, and each one will be listed in `ground_truth.csv`.

## 10. Assumptions and limitations

- Each claim in the clean baseline is made on one coverage.
- One incident leads to one claim in the clean baseline; duplicates come only from injection.
- Rejections for an excluded incident type (R07) are normal rule outcomes, not injected anomalies.
- All data is synthetic. No external or personal data is used.
