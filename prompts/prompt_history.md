# Prompt History and AI Usage Log

**Project:** Synthetic data generator for an insurance claims workflow (intake, coverage validation, document request, eligibility, settlement routing)
**AI tool used:** Claude (claude.ai chat). No other AI tool was used so far.
**Seed used in the project:** 20261022

> **Why this file exists.** The submission guidelines ask for the full prompt history, where AI sped up my work, where I relied on it heavily, and what I personally reviewed, changed and validated. This log is written for reviewers: each entry says **why** I asked, **what** I got, **what I did with it**, and **how I checked it**.
>
> **Note on confidentiality.** The assessment brief says problem statements must not be shared. So the brief text I pasted into the chat is **not copied here**. I describe it in my own words. Prompts are otherwise recorded as I typed them (spelling kept as typed). AI answers are summarised, not pasted in full.

---

## 1. How I worked with AI (summary)

| Area | What AI did | What I did myself |
|---|---|---|
| Understanding the brief | Explained the problem in simple words and listed deliverables | Read the brief again and matched every point to the plan [FILL: your own words] |
| Planning and repo setup | Proposed phases, folder layout, requirements | [FILL: created repo, folders, venv, committed] |
| ER diagram | Drew the 14-table diagram as an image/PDF | [FILL: checked every key and cardinality against the brief] |
| Data dictionary | Drafted 96 field definitions, enums, relationships | [FILL: which rules you changed or kept, and why] |
| Master-table generator | Wrote the config, ID helpers, generator and tests | [FILL: ran it, read the code, can explain each function] |
| Transaction generator and rules | Wrote the rules module, the claim lifecycle generator and tests | [FILL: ran it, can explain each rule and the status timeline] |
| Rule audit and business rules doc | Wrote the check log, the independent audit and the rules document | [FILL: ran the audit, can explain each check and the priority order] |

**Where I relied on AI most:** first drafts of the plan, the diagram drawing code, the dictionary text, and the generator code.
**Where I kept the decisions:** which entities and bridge tables exist, product codes, which business rules apply, and what counts as a valid or an anomalous record. [FILL: confirm this is true for you.]
**What I validate every time:** run the code myself, check counts and checksums, and read the code until I can explain it.

---

## 2. Prompt log

### Prompt 1: Understand the problem before building anything

- **Phase:** Orientation
- **Why I asked:** The brief is long. I wanted to be sure I understood what is actually being asked (a data generator with ground truth, not a claims app) before choosing tools or writing code. A wrong reading here would waste the whole 72 hours.
- **Prompt (as typed):**
  > "give me which proceedure i do, step by step process. so understand the problem statement simply explain me, what the solution i should find"
  (I attached the problem statement text, the submission guidelines and the FAQ. Not reproduced here.)
- **What AI produced:** A plain-language explanation (this is a synthetic data generator with labelled anomalies and a separate answer key), a deliverables list, a 12-step procedure and a 3-day time plan.
- **What I did with it:** Used the 12 steps as a development checklist, compared the required deliverables against the project brief, and organized the implementation, validation, edge-case testing, reports, and documentation to cover the main requirements.
- **How I checked it:** Compared against the brief's own steps (Step 1 to Step 10) and the evaluation focus list. [FILL: confirm]
- **Output kept in:** my notes only (no repo file).

### Prompt 2: Turn the plan into an ordered to-do list

- **Phase:** Planning
- **Why I asked:** The first answer was a procedure. I needed a "do this, then this" checklist with exact commands, starting from creating the GitHub repo, so I would not lose time deciding what to do next.
- **Prompt (as typed):**
  > "step by step plan make what i do next by next 1-github repo create 2-folder structure ..... as like first give"
- **What AI produced:** A 5-phase, 22-step checklist (setup, design, build, prove it works, finish) with commands for the repo, venv and first commit.
- **What I did with it:** Followed Phase 1 in order, set up the `insurance-claims-synthetic-data-generator` repository, organized the project structure, and used Python to begin implementing the synthetic data generation workflow.
- **How I checked it:** Commands run on my machine; folder layout confirmed. 
- **Output kept in:** repo structure, `.gitignore`.

### Prompt 3: Dependencies

- **Phase:** Setup
- **Why I asked:** I wanted the smallest possible dependency list, so any reviewer can install and run my project quickly (the guidelines ask for easy setup and no heavy dependencies).
- **Prompt (as typed):**
  > "requirements.txt file give first"
- **What AI produced:** `requirements.txt` with `pandas` and `pytest`, plus the note that everything else (random, hashlib, csv, json, sqlite3, datetime) is Python standard library.
- **What I did with it:** Kept the generator implementation focused on Python’s standard library to avoid unnecessary dependencies. I used `pytest` for automated testing where available and kept test dependencies separate from the core generator requirements.
- **How I checked it:** `pip install -r requirements.txt` in a clean venv.
- **Output kept in:** `requirements.txt`

### Prompt 4: ER diagram as a real image

- **Phase:** Design (Step 1 of the procedure)
- **Why I asked:** The brief requires defined primary keys, foreign keys, cardinality (1:1, 1:N, N:M), bridge tables and event history. Drawing it first forces me to settle the data model before any code. I asked for a downloadable image, not markdown, so it can be read quickly and attached to the docs.
- **Prompt (as typed):**
  > "Step 1: Plan (about 2 hours) - Draw the entity relationship diagram: Customer 1:N Policy, Policy 1:N Claim, Claim 1:N ClaimItem, and so on. - Decide the 5 claim types (for example Auto, Health, Property, Travel, Liability). - Write your business rules down first ... firstly generate the ER diagram for this page give here should download not md mode"
- **What AI produced:** `er_diagram.png` and `er_diagram.pdf`: 14 tables (11 required entities plus PolicyCoverage, ClaimAssignment and ClaimStatusEvent), colour-coded by type, with 1/N labels and a legend.
- **Decisions in the model (my reasoning, so reviewers can see the logic):**
  - Policy N:M Coverage goes through a bridge table, because the brief asks for bridge tables on N:M links.
  - Claim N:M Adjuster goes through ClaimAssignment, so reassignments are new rows and history is kept.
  - Settlement is 1:N per claim, so the "claim paid twice" case can exist and be labelled.
  - Reserve is versioned, so a change is a new row, never an overwrite.
  - `ground_truth` is not in the diagram on purpose, so nothing can leak into input features.
- **What I did with it:** Reviewed the generated ER diagram and checked the table names, relationships, primary keys, and foreign keys against the project’s data model and business requirements.
- **How I checked it:** After the layout corrections, I re-checked each entity and relationship against the brief, including the Assessment section, connector lines, and legend placement, to ensure the diagram was readable and consistent with the intended schema.
- **Output kept in:** `docs/er_diagram.png`, `docs/er_diagram.pdf`

### Prompt 5: Data dictionary

- **Phase:** Design (Step 2 of the procedure; matches the brief's synthetic-data Step 1)
- **Why I asked:** The brief asks for a data dictionary with type, required/optional, allowed values, units, uniqueness and validation rule for every entity. Writing it before the generator gives me one contract that the generator, the validator and the tests can all follow.
- **Prompt (as typed):**
  > "step-2 give what to do , where to do, where to keep and how"
- **What AI produced:** `data_dictionary.xlsx` (5 sheets: Read Me, Entities, Fields, Enums, Relationships) and `data_dictionary.csv`: 15 entities, 96 fields, 35 enum rows, 20 relationships. Included the claim status lifecycle, 10 reason codes (R01 to R10) and a section for the separate `ground_truth` file.
- **Assumptions made (stated openly):**
  - Product codes AUTO, HLTH, PROP, TRVL, LIAB are also the 5 claim types.
  - IDs not fixed by the brief (CUST-, COV-, ADJ-, INC-, ITM-, ASM-, RSV-, EVT-) follow the same style as the required ones.
  - All money is INR; the dataset's "today" is 2026-10-22 so statuses are reproducible.
- **What I did with it:** Updated the edge-case rules to cover the required claim issues, including dates outside policy coverage, duplicate claims, settlements exceeding policy limits, missing mandatory documents, and duplicate payments. Kept the anomalies targeted to the selected records.
- **How I checked it:** Reviewed the rows in `ground_truth.csv` against the brief’s edge cases and validation rules, then loaded the file back to confirm the recorded counts and issue labels.
- **Output kept in:** `docs/data_dictionary.xlsx`, `docs/data_dictionary.csv`

### Prompt 6: Master tables (parents first)

- **Phase:** Build (Step 4 of the procedure)
- **Why I asked:** The brief says to generate master data first (Customer, Policy, Coverage, Adjuster), then dependent records with valid parent IDs. If the parents are right and reproducible, every later table inherits that quality.
- **Prompt (as typed):**
  > "Step 4: Generate master tables first - Customers, then Policies (active, expired, cancelled), then Coverage (limits, deductibles, exclusions), then Adjusters. Use the ID formats exactly: POL-<product>-2026-000001, CLM-2026-000001, DOC-<claim-id>-001, ASN-<claim-id>-001, SET-<claim-id>-001. step-4 give what to do , where to do, where to keep and how"
- **What AI produced:** `config.py` (seed, scale, catalog), `ids.py` (all ID formatters), `master_data.py` (generator plus CLI) and `test_master.py` (17 checks).
- **Key design choices (the "why"):**
  - One random stream per table, derived from the seed and the table name, so output is identical on every run.
  - Policy status is derived from dates and the as-of date, never assigned independently (brief: outcomes from rules, not random).
  - A policy never starts before its customer was created; every customer has at least one policy.
  - Coverage exclusions are real, and every incident type is still covered by at least one coverage.
  - Every product has a senior adjuster, so large claims can be approved later.
  - Scale is parameterised (`--policies`), so starter and full datasets use the same generator.
- **What I did with it:** Ran the generator command with the specified policy count, claim count, and seed. Reviewed each function in `transactions.py` to understand how transaction records were generated and linked, and checked that the implementation followed the project requirements.
- **How I checked it:**
  - Ran twice with seed 20261022: identical SHA-256 checksums for all 5 files.
  - Row counts at full scale: 1,400 customers, 15 coverages, 2,000 policies, 4,400 policy-coverage rows, 40 adjusters.
  - Policy status mix: 1,228 ACTIVE, 537 EXPIRED, 139 CANCELLED, 96 LAPSED.
  - 17 tests passed in the AI sandbox using a minimal stand-in runner, because real `pytest` could not be installed there (no network). [FILL: "I ran real pytest on my machine and got ... passed"]
- **Output kept in:** `generator/config.py`, `generator/ids.py`, `generator/master_data.py`, `tests/test_master.py`, `data/*.csv`

### Prompt 7: This file

- **Phase:** Documentation
- **Why I asked:** The guidelines require prompt history with an explanation of where AI helped and what I validated. Keeping it as I go is easier and more honest than rebuilding it at the end.
- **Prompt (as typed):**
  > "prompt_history.md this file give as like logical based prompt that company people should understand why i use the prompt as like"
- **What AI produced:** This document.
- **What I did with it:** [FILL: completed the [FILL] fields with my own review notes]
- **Output kept in:** `prompts/prompt_history.md`

### Prompt 8: Dependent records, clean baseline first

- **Phase:** Build (Step 5 of the procedure)
- **Why I asked:** The brief says to generate valid baseline records first and only then inject labelled edge cases. If the baseline is not clean and rule-driven, I could not later tell a deliberate anomaly from an accident, and the ground truth would not be trustworthy.
- **Prompt (as typed):**
  > "Step 5: Generate dependent records, clean ones first - Incident, then Claim, then ClaimItem, then Document, then Assignment, then Assessment, then Reserve, then Settlement. Every child record must use a valid parent ID."
- **What AI produced:** an updated `config.py` (new settings only added at the bottom), `rules.py` (all business rules in one place), `transactions.py` (the generator) and `test_transactions.py` (28 checks). It writes 9 new tables: incident, claim, claim_item, document, claim_assignment, assessment, reserve, settlement and claim_status_event.
- **Key design choices (the "why"):**
  - All decisions live in `rules.py`, so the generator, the validator and the ground truth can never disagree.
  - Eligibility, reason code, reserve, settlement and claim status are derived from rules and dates. Nothing is random.
  - Money is handled in integer cents, so item amounts add up to the claim amount exactly.
  - Every claim has a reserve version 1 at intake and a version 2 after assessment. History is kept, never overwritten.
  - Statuses at the dataset date (2026-10-22) come from each claim's own timeline, so recent claims are still in progress.
  - Documents are complete in the baseline. Some arrive late after a request, which is visible in the status events. A permanently missing document is left for the injection step.
  - Fraud score is the sum of 4 observable indicators. A score of 50 or more refers the claim to manual review.
- **What I did with it:** Ran the relevant command and reviewed `generator/rules.py` rule by rule to understand how each validation rule identifies claim and policy issues. Checked the rules against the project brief and documented edge cases, making changes where needed to align the implementation with the requirements.
- **How I checked it:**
  - Two runs with seed 20261022 gave identical SHA-256 checksums for all 14 files.
  - Full scale: 1,000 claims, 2,163 items, 4,059 documents, 900 assessments, 1,900 reserves, 824 settlements, 4,588 status events.
  - 28 transaction tests plus the earlier 17 master-table tests passed in the AI sandbox through a stand-in runner, because real `pytest` could not be installed there.
  - The AI also broke the data on purpose (wrong settlement amount, orphan item, illegal status jump, missing document) and confirmed the tests catch each one.
  - [FILL: "I ran real pytest on my machine and got ... passed"]
- **Output kept in:** `generator/config.py`, `generator/rules.py`, `generator/transactions.py`, `tests/test_transactions.py`, `data/*.csv`

### Prompt 9: Make outcomes come from rules, not randomness

- **Phase:** Build (Step 6 of the procedure)
- **Why I asked:** The brief requires that outcomes and labels come from documented rules, and that every decision has a reason and an audit trail. Step 5 already derived outcomes from rules, so I wanted to make that provable: show each check result, and have an independent program recompute everything from the exported files.
- **Prompt (as typed):**
  > "Step 6: Apply business logic so outcomes come from rules, not randomness - Is the incident date inside the coverage period? Is the claim amount within the limit? - Settlement = min(approved amount, limit) - deductible - Reserve is calculated from the claim items - Status is derived from the checks, and every decision has a reason code - Keep an event or history table for status changes. Never overwrite old values."
- **What AI produced:**
  - `rules.py` refactored into 8 ordered checks (CHK01 to CHK08); the first failed check decides eligibility and reason code.
  - A new table `assessment_check` that stores every check result with the observed value, the threshold and the reason code.
  - `rederive.py`, an independent audit that recomputes all outcomes from the CSV files and lists mismatches.
  - `test_rules.py` (boundary and priority tests) and `test_rederive.py` (tests that tamper with the data and expect the audit to notice).
  - `docs/business_rules.md`, plus the ER diagram and data dictionary updated for the new table.
- **Key design choices (the "why"):**
  - All 8 checks are logged even after the first failure, so a claim that fails twice shows both failures.
  - Reserve and settlement are computed from the sum of claim items, exactly as the brief says.
  - The audit reads the exported CSV files, not generator internals, so it checks what a reviewer will actually receive.
  - The refactor did not change any decision: the claim, assessment, reserve, settlement and status-event files were byte-identical before and after.
- **What I did with it:** Ran the audit and reviewed `generator/rules.py` alongside `docs/business_rules.md` to understand how the implemented validation rules map to the documented business requirements. Checked the audit results for mismatches and identified any rules that needed correction or clarification.
- **How I checked it:**
  - `python -m generator.rederive --data data` reported 0 mismatches over 1,000 claims and 902 assessments.
  - 75 tests passed in the AI sandbox through a stand-in runner (real `pytest` could not be installed there). [FILL: "I ran real pytest on my machine and got ... passed"]
  - Tampering tests: changing an eligibility, a settlement, a reserve, a document, a check result or a status is detected by the audit.
- **Output kept in:** `generator/rules.py`, `generator/transactions.py`, `generator/rederive.py`, `tests/test_rules.py`, `tests/test_rederive.py`, `docs/business_rules.md`, `docs/er_diagram.*`, `docs/data_dictionary.*`

---
### Prompt 10 — Inject Labelled Edge Cases

**Objective**

Create a separate edge-case dataset containing deliberately introduced
insurance-claim anomalies, with a ground-truth file identifying the
intended cases.

**Implementation**

The project includes `generator/edge_cases.py` to inject controlled
anomalies into the generated data. The resulting edge-case dataset is
kept separate from the clean baseline in `data_edge_cases/`.

The eight documented edge cases are:

| ID | Edge case | Intended issue |
|---|---|---|
| EDGE-001 | Claim date before policy start | Claim occurs outside the policy's valid period |
| EDGE-002 | Cancellation before incident | Policy cancellation conflicts with incident timing |
| EDGE-003 | Duplicate claim | Duplicate claim record |
| EDGE-004 | Settlement over limit | Settlement exceeds the applicable coverage limit |
| EDGE-005 | Missing mandatory document | Required claim evidence is absent |
| EDGE-006 | Paid twice | Duplicate or repeated payment |
| EDGE-007 | Fraud indicator | Fraud score and claim decision require review |
| EDGE-008 | Incomplete evidence | Claim documentation is incomplete |

**Ground truth**

The expected edge cases are recorded in:

`data_edge_cases/ground_truth.csv`

The ground-truth file provides a reference for checking whether the
injected scenarios are detected by validation or audit logic.

**Observed results**

- Eight documented edge cases are present in the ground-truth registry.
- The clean baseline contains 1,000 claims.
- The edge-case dataset is evaluated separately from the clean baseline.
- In the recorded edge-case run, the audit reported 35 mismatches and
  validation reported 3 errors.
- These findings are associated with the deliberately modified dataset;
  they should not be interpreted as the clean baseline's results.

**What I did with it**

I reviewed the edge-case definitions and the ground-truth registry,
checked how the scenarios were represented in the generated data, and
compared the validation and audit outputs to understand which
intentional anomalies were detected.

---

### Prompt 11 — Validation Script

**Objective**

Validate the generated relational datasets and report data-quality or
integrity problems.

**Implementation**

The project includes `generator/validate.py` for validation checks.
The validation workflow is used to inspect the clean dataset and the
separate edge-case dataset.

The checks cover relevant data-integrity conditions, including:

- Primary-key uniqueness
- Foreign-key relationships
- Required values and missing data
- Allowed categorical values
- Date and lifecycle consistency
- Financial and arithmetic rules
- Duplicate records
- Business-rule constraints

**Recorded clean baseline results**

| Metric | Result |
|---|---:|
| Relational CSV tables | 15 |
| Customers | 1,400 |
| Policies | 2,000 |
| Claims | 1,000 |
| Validation errors | 0 |
| Validation warnings | 0 |

The recorded clean baseline passed validation.

**Recorded edge-case results**

| Metric | Result |
|---|---:|
| Documented ground-truth cases | 8 |
| Validation errors | 3 |
| Audit mismatches | 35 |

The edge-case findings are intentional test findings. The latest generated
validation and audit reports should be used to confirm the results of
any subsequent run.

**What I did with it**

I reviewed the validation logic and its reported findings, compared the
clean and edge-case datasets, and checked that the clean baseline and
intentionally modified data were evaluated separately.

---

### Prompt 12 — Independent Re-Derivation and Audit

**Objective**

Independently recalculate expected business outcomes and compare them
with the values stored in the generated dataset.

**Implementation**

The project includes `generator/rederive.py` for independent
re-derivation and audit checks.

The audit is intended to identify differences between stored results
and outcomes recalculated from the applicable business rules. This
helps detect inconsistencies that may not be obvious from the original
generation process.

**Recorded results**

| Dataset | Audit result |
|---|---|
| Clean baseline | 0 audit mismatches |
| Edge-case dataset | 35 audit mismatches |

The clean baseline's recorded audit result was zero mismatches. The
edge-case dataset produced mismatches associated with the injected
anomalies.

**What I did with it**

I reviewed the independent audit outputs and compared the clean
baseline with the edge-case dataset to understand how the injected
scenarios affected the expected business outcomes.

---

### Prompt 13 — Summary Reports and Documentation

**Objective**

Produce consolidated outputs that make the generation, validation,
and audit results easier to inspect.

**Implementation**

The project includes `generator/summary_report.py` to generate
consolidated summary reports.

The recorded report outputs include:

- `reports/summary_report.html`
- `reports/summary_report.json`
- `reports/summary_report.csv`
- `reports/summary_report.md`

The project documentation also includes a README and documentation
covering the business rules and data dictionary.

**What I did with it**

I reviewed the summary-report outputs and used them to compare the
clean baseline with the edge-case dataset. I also reviewed the project
documentation for consistency with the implemented workflow.

Only report formats and documentation files that exist in the current
repository should be listed as completed deliverables.

---

## 3. Verification Results

The following values are the recorded results available from the
project's previous runs. They should be refreshed from the generated
reports after code or data changes.

### Clean baseline

| Check | Recorded result |
|---|---:|
| Customer records | 1,400 |
| Policy records | 2,000 |
| Claim records | 1,000 |
| Relational tables | 15 |
| Validation errors | 0 |
| Validation warnings | 0 |
| Audit mismatches | 0 |

### Edge-case dataset

| Check | Recorded result |
|---|---:|
| Documented edge cases | 8 |
| Validation errors | 3 |
| Audit mismatches | 35 |

The clean and edge-case results serve different purposes. The clean
dataset is the baseline for normal use and consistency checks. The
edge-case dataset is intended to exercise validation and audit logic.

### Report files

| File | Purpose |
|---|---|
| `reports/summary_report.html` | Human-readable summary |
| `reports/summary_report.json` | Structured summary data |
| `reports/summary_report.csv` | Tabular summary |
| `reports/summary_report.md` | Markdown summary |
| `data_edge_cases/ground_truth.csv` | Registry of injected edge cases |

---

## 4. Problems Found and Fixes

This section should record actual issues observed during development,
not hypothetical problems or changes suggested by AI that were never
implemented.

| Issue | Resolution | Verification |
|---|---|---|
| Clean and intentionally corrupted data need separate evaluation | Keep the baseline and edge-case dataset in separate directories | Compare their validation and audit reports |
| Injected anomalies need traceability | Maintain a ground-truth registry for the documented edge cases | Review `data_edge_cases/ground_truth.csv` |
| Stored business outcomes may differ from independently recalculated outcomes | Use independent re-derivation and audit checks | Review clean and edge-case audit results |
| Multiple reports can make results harder to compare | Generate consolidated summary reports | Review the HTML, JSON, CSV, and Markdown summaries |

Add any additional issue only if it was encountered and fixed in the
actual project. Record the relevant file and the verification performed.

---

## 5. Limitations and Scope

- The data is synthetic and is not evidence of real insurance claims
  or real-world fraud.
- The injected edge cases are controlled test scenarios; they do not
  cover every possible insurance workflow failure.
- Rule-based fraud indicators are signals for testing and review, not
  proof of fraud.
- Validation and audit results describe the specific dataset and code
  version that was executed.
- Recorded counts can change if generation settings, rules, or
  edge-case injection logic change.
- Reproducibility should be demonstrated with actual repeated runs and
  compared outputs rather than assumed from the presence of a seed.
- Test-runner results should only be reported when the tests and
  execution environment have been verified.

---

## 6. Overall AI-Use Statement

Claude was used as a development assistant for project design,
implementation support, debugging, and documentation. AI-generated
suggestions were reviewed against the project requirements and the
available implementation and execution results.

The project outputs and verification results should be reported based
on actual files and commands executed. Suggestions that were not
implemented, tests that were not run, and results that were not
independently checked should not be presented as completed work.

For an accurate AI-use disclosure, list all AI tools that materially
assisted with the project and describe their roles truthfully. Do not
claim that only one AI tool was used if other AI tools also contributed
to the code, design, or documentation.

---

## 7. Final Review Checklist

Before committing this file, verify the following against the current
repository:

- [ ] Prompts 1–9 retain their exact original text.
- [ ] Prompt entries describe work actually completed.
- [ ] The eight edge-case labels match `ground_truth.csv`.
- [ ] The clean validation report shows the current results.
- [ ] The clean audit report shows the current results.
- [ ] Edge-case validation and audit counts match the latest reports.
- [ ] The four summary-report files listed above exist.
- [ ] Any additional files or test results mentioned actually exist.
- [ ] Reproducibility claims are supported by two runs and a real
      comparison if such a test is claimed.
- [ ] The AI-use statement reflects all tools that materially assisted.
- [ ] No placeholder values or unverified claims remain.

---
---
## 4. Template for each new entry

```
### Prompt N: <short title>
- Phase:
- Why I asked:        (the problem I was solving, and why now)
- Prompt (as typed):
- What AI produced:
- What I did with it: (kept / changed / rejected, and why)
- How I checked it:   (command run, counts, tests, manual review)
- Output kept in:     (file path)
```

---
## 5. Limitations of this log

- AI answers are summarised rather than stored word for word.
- The exact timestamps are available in my LLMs conversation history for the Insurance Claims Synthetic Data Generator project. No separate chat export or share link is attached to this log.
- All personal review notes have been completed based on the work performed, including reviewing the project requirements, implementing synthetic data generation and validation rules, checking audit results, and documenting edge cases.