# Insurance Claims Synthetic Data Generator

## Executive summary

- **Clean dataset status:** PASS
- **Claims:** 1,000
- **Policies:** 2,000
- **Customers:** 1,400
- **CSV tables found:** 15 / 15
- **Business-rule mismatches:** 0
- **Validation errors:** 0
- **Validation warnings:** 0

## Dataset inventory

| Table | Exists | Rows | Columns |
|---|---:|---:|---:|
| `customer` | Yes | 1,400 | 6 |
| `coverage` | Yes | 15 | 6 |
| `policy` | Yes | 2,000 | 8 |
| `policy_coverage` | Yes | 4,400 | 6 |
| `adjuster` | Yes | 40 | 5 |
| `incident` | Yes | 1,000 | 6 |
| `claim` | Yes | 1,000 | 8 |
| `claim_item` | Yes | 2,177 | 6 |
| `document` | Yes | 4,051 | 6 |
| `claim_assignment` | Yes | 988 | 5 |
| `assessment` | Yes | 902 | 8 |
| `assessment_check` | Yes | 7,216 | 9 |
| `reserve` | Yes | 1,902 | 6 |
| `settlement` | Yes | 866 | 7 |
| `claim_status_event` | Yes | 4,588 | 6 |

## Claim outcomes

| Outcome | Count |
|---|---:|

## Financial summary

| Metric | Total (INR, source units) | Numeric rows |
|---|---:|---:|
| Claimed amount | 337,630,710.00 | 1,000 |
| Assessed/approved amount | 284,616,500.00 | 902 |
| Reserve amount | 592,995,830.00 | 1,902 |
| Settlement amount | 270,987,050.00 | 866 |

## Business-check summary

- Total assessment checks: 7,216
- Passed: 7,109
- Failed: 107
- Unclassified: 0
- Pass rate: 98.52%

## Audit and validation interpretation

- No reported clean-dataset issues were identified by the available reports.

## Edge-case dataset

- Injected cases recorded: 8
- Business-rule audit mismatch rows/count: 35
- Validation errors: 3
- Validation warnings: 0
- Duplicate claim-key groups: 0

The edge-case dataset is designed to contain anomalies. Its findings should be interpreted as detection evidence, not as a clean-baseline pass/fail result.

## Methodology and limitations

- The clean dataset is expected to pass validation and business-rule audit.
- The edge-case dataset intentionally contains injected anomalies; detected issues are not automatically treated as clean-data failures.
- A missing report is marked unavailable and is not assumed to contain zero issues.
- Financial totals depend on the meaning and units of the source columns.
- This report is a quality-control summary, not a legal or actuarial opinion.

_Generated at 2026-10-27T15:07:29+00:00._
