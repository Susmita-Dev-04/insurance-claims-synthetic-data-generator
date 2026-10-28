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
- **What I did with it:** Used the 12 steps as the skeleton for my work. [FILL: e.g. "I compared the deliverables list against the brief and found nothing missing / I added X"]
- **How I checked it:** Compared against the brief's own steps (Step 1 to Step 10) and the evaluation focus list. [FILL: confirm]
- **Output kept in:** my notes only (no repo file).

### Prompt 2: Turn the plan into an ordered to-do list

- **Phase:** Planning
- **Why I asked:** The first answer was a procedure. I needed a "do this, then this" checklist with exact commands, starting from creating the GitHub repo, so I would not lose time deciding what to do next.
- **Prompt (as typed):**
  > "step by step plan make what i do next by next 1-github repo create 2-folder structure ..... as like first give"
- **What AI produced:** A 5-phase, 22-step checklist (setup, design, build, prove it works, finish) with commands for the repo, venv and first commit.
- **What I did with it:** Followed Phase 1 in order. [FILL: what you actually did, e.g. repo name, Python version]
- **How I checked it:** Commands run on my machine; folder layout confirmed. [FILL]
- **Output kept in:** repo structure, `.gitignore`.

### Prompt 3: Dependencies

- **Phase:** Setup
- **Why I asked:** I wanted the smallest possible dependency list, so any reviewer can install and run my project quickly (the guidelines ask for easy setup and no heavy dependencies).
- **Prompt (as typed):**
  > "requirements.txt file give first"
- **What AI produced:** `requirements.txt` with `pandas` and `pytest`, plus the note that everything else (random, hashlib, csv, json, sqlite3, datetime) is Python standard library.
- **What I did with it:** [FILL: kept / changed. Note: the generator code written later uses only the standard library; `pytest` is needed for tests.]
- **How I checked it:** `pip install -r requirements.txt` in a clean venv. [FILL]
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
- **What I did with it:** [FILL: what you checked or changed]
- **How I checked it:** The AI rendered the image and spotted two layout problems (legend overlapping boxes, a line crossing the Assessment box) and fixed them. I [FILL: re-checked each key against the brief].
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
- **What I did with it:** [FILL: rules you edited, e.g. thresholds, enums]
- **How I checked it:** Read every row and compared against the brief's edge cases and validation rules. The file was also loaded back to confirm the counts. [FILL]
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
- **What I did with it:** [FILL: ran the command, read each function, any change you made]
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
- **What I did with it:** [FILL: ran the command, read rules.py until I could explain each rule, any change I made]
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
- **What I did with it:** [FILL: ran the audit, read rules.py and business_rules.md, any change I made]
- **How I checked it:**
  - `python -m generator.rederive --data data` reported 0 mismatches over 1,000 claims and 902 assessments.
  - 75 tests passed in the AI sandbox through a stand-in runner (real `pytest` could not be installed there). [FILL: "I ran real pytest on my machine and got ... passed"]
  - Tampering tests: changing an eligibility, a settlement, a reserve, a document, a check result or a status is detected by the audit.
- **Output kept in:** `generator/rules.py`, `generator/transactions.py`, `generator/rederive.py`, `tests/test_rules.py`, `tests/test_rederive.py`, `docs/business_rules.md`, `docs/er_diagram.*`, `docs/data_dictionary.*`

---
### Prompt 10: Inject labelled edge cases

- **Phase:** Build (the brief's "inject labelled edge cases" step)
- **Why I asked:** The brief requires six named edge cases, plus fraud indicators and incomplete evidence, each tagged in a separate `ground_truth.csv`, on selected rows only. This step turns clean data into a useful test set for someone else's claims-detection system. It is also where the rule "don't corrupt unrelated rows" is easiest to break, so I asked for it explicitly in the prompt.
- **Prompt (as typed):**
  > "Step 7: Inject labelled edge cases - Add the six required ones, each tagged with an `issue_type` in `ground_truth.csv`: 1. Claim date before policy start 2. Policy cancelled before the incident 3. Duplicate incident or claim 4. Settlement exceeds limit 5. Missing mandatory document 6. Claim paid twice - Also include fraud indicators and incomplete evidence. Do this to selected rows only, and don't corrupt unrelated rows."
- **What AI produced:** an edge-case injection module (10 injection types, counts set in `config.py` and scaled by `--claims`), a ground-truth builder (one row per claim, expected decision recomputed from source records by the same rules engine as the audit), a single entry point that runs everything, refactors so each claim has its own random stream, a test file (25 tests), and updates to the data dictionary and `business_rules.md`.
- **Key design choices (the "why"):**
  - **Two kinds of anomaly.** Input-fact anomalies (dates, duplicates, missing documents, fraud patterns) are changed before the workflow runs, so each claim's history stays consistent and the workflow handles them by the rules (rejections and referrals). Process errors (settlement above limit, claim paid twice) are written into the stored settlement rows afterwards and are caught by the audit. This gives both "the system should reject this" cases and "the system made a mistake" cases.
  - **Unrelated rows are protected.** Claim and incident IDs are fixed from the clean baseline, every claim has its own random stream, the injection uses a separate stream, master tables are never touched, and a claim gets at most one injected label.
  - **Ground truth is separate and complete.** It lives in its own folder, covers every claim, and marks clean claims as `NONE`. Natural cases (over limit, excluded incident type, fraud score at threshold) are labelled `injected = FALSE`, so they are not confused with injected ones.
  - **Incomplete evidence is not the same as a missing document.** A pending claim still waiting for documents has the expected decision `PENDING`. A claim whose documents never arrived ends in rejection (R05).
  - **Fraud is injected as real indicators** (new policy, amount near limit, late report, repeat claimant), not as a flag, so the fraud score is still computed from data.
  - **Repository layout:** the clean data (`data/`) and the edge-case data (`data_edge_cases/`) are kept in separate folders.
- **What I did with it:** ⟦1 sentence: that you ran the generator and read the injection code, plus any change you made⟧
- **How I checked it:**
  - Every requested injection was made: 12 claim-before-start, 12 cancelled-before-incident, 14 duplicates, 12 outside-coverage, 15 incomplete evidence, 12 missing documents, 22 fraud (10 single + 4 bursts of 3), 12 settlement-over-limit, 10 paid-twice. That is 121 injected claims; 104 further claims carry natural labels and 775 are `NONE`.
  - The independent audit finds exactly the 22 process-error claims (settlement over limit, paid twice) and nothing else.
  - A clean run without injection is audited with 0 mismatches.
  - Unrelated claims are identical to the clean baseline (tested over more than 700 claims), master tables are byte-identical, and all IDs are unchanged.
  - 100 tests passed in the AI sandbox through a stand-in runner, because real `pytest` could not be installed there. ⟦real pytest result on your machine, e.g. "100 passed"⟧
- **Output kept in:** the edge-case module in `generator/`, the injected dataset in `data_edge_cases/`, `ground_truth` file, `tests/`, `docs/business_rules.md`, `docs/data_dictionary.*`

### Prompt 11: Validation script

- **Phase:** Verification
- **Why I asked:** The brief requires a validation run over the generated data and a summary of its results. The checks it names are: primary-key uniqueness, foreign-key integrity, allowed values (enums), date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks. Generating data is not enough. A reviewer needs evidence that the clean rows are valid, and that the only rows that break the rules are the ones I deliberately injected.
- **Prompt (as typed):**
  > ⟦paste the exact prompt you typed for the validation step⟧
- **What AI produced:** a validation script and a summary-report generator (`validate.py` and `summary_report.py` in `generator/`), with the results written to the `reports/` folder.
- **Acceptance criteria for this step (taken from the brief):**
  - Clean rows must produce zero violations.
  - Every violation found in the edge-case dataset must be explained by a label in the ground truth. A violation with no label means an unrelated row was corrupted.
  - Every labelled anomaly must produce a detectable violation. A label with no violation means the injection did not work.
  - The summary must be readable by a reviewer without running any code.
- **Why validation is separate from the generator:** a generator that checks its own output can hide its own mistakes. The validator reads the exported files, so it checks what a reviewer actually receives, and it applies the same rules as the rules module (`rules.py`) so the two cannot disagree.
- **What I did with it:** ⟦1 or 2 sentences: the command you ran, and anything you changed or fixed after seeing the output⟧
- **How I checked it:** ⟦number of checks run and number of violations in the clean data, e.g. "0 violations in `data/`; N violations in `data_edge_cases/`, all matching ground-truth labels"⟧
- **Output kept in:** `generator/validate.py`, `generator/summary_report.py`, `reports/`

### Prompt 12: Reproducibility proof

- **Phase:** Verification
- **Why I asked:** The brief requires that regenerating with the same fixed seed (20261022) gives the same data, shown by comparing row counts and checksums across two runs. Without this proof, a reviewer cannot trust that the dataset they received is the dataset my generator produces.
- **Prompt (as typed):**
  > ⟦paste the exact prompt you typed for the reproducibility step⟧
- **What AI produced:** a way to run the generator twice with the same seed and compare row counts and SHA-256 checksums of every output file, including the ground truth.
- **Design logic (the "why"):**
  - The seed and the dataset's "today" (2026-10-22) are fixed in `config.py`, so statuses never depend on the date the code is run.
  - Each table, and each claim, has its own random stream derived from the seed. Changing one table or one claim cannot shift the random values of another.
  - Output is written with fixed line endings and fixed number formats, so the same data always gives the same bytes.
  - The ground truth file is included in the comparison, not only the input tables.
- **What I did with it:** ⟦1 sentence: the two run commands you used⟧
- **How I checked it:** ⟦result: row counts equal and checksums equal on both runs; name the file where the result is saved⟧
- **Output kept in:** `reports/` (reproducibility result) and the test files that run the generator twice

### Prompt 13: Exports, source manifest and README

- **Phase:** Packaging
- **Why I asked:** The brief requires a README, a schema and data dictionary, the generator command, the fixed seed, a source manifest and a validation summary, so another person can install, run and verify the project without help. It also asks for lawful provenance: if no external data is used, that must be stated.
- **Prompt (as typed):**
  > ⟦paste the exact prompt you typed for the README and manifest step⟧
- **What AI produced:** a README (setup, run commands, assumptions, limitations), a source manifest stating that all data is synthetic and that no external or personal data is used, and the CSV, JSON and SQL exports.
- **Key decisions:**
  - Only the Python standard library is needed to generate the data. `pytest` is only for the tests, so setup is quick.
  - The assessment brief is not copied into the public repository, because the confidentiality notice says problem statements must not be shared. The README describes what was built, in my own words.
  - No secrets, credentials or personal information are in the repository.
- **What I did with it:** ⟦1 sentence: that you ran the setup steps from the README in a clean environment⟧
- **Output kept in:** `README.md`, `docs/`, `data/`, `data_edge_cases/`, `reports/`

---

## 3. Planned prompts

All planned steps are logged above. No steps are planned.

---

## 4. Problems found and fixed during development

These show that results were checked and not accepted as first produced. Each one was found by running the checks, and then fixed.

| # | Problem found | How it was found | Fix |
|---|---|---|---|
| 1 | The ER diagram legend overlapped the bottom boxes, and the "history" line crossed the Assessment box | Rendering the image and looking at it | Moved the legend and routed the line around the box |
| 2 | Too many claims (about 7%) were referred to manual review as suspected fraud | Looking at the distribution of eligibility results | Raised the referral threshold from 45 to 50, which gives about 2.4% |
| 3 | Some row counts quoted in an earlier step came from two different runs | Comparing the written summary with the actual files | Corrected the counts and re-ran from scratch |
| 4 | A new column name (`description`) clashed with `Coverage.description` | A test that checks ground-truth columns never appear in input tables | Renamed the ground-truth column to `label_note` |
| 5 | The process-error injection could pick the original claim of a duplicate pair, so that original was no longer a clean claim | A test that requires originals to stay unlabelled | Protected originals of duplicates from later injections |
| 6 | Injecting one claim could change the random values of other claims | Designing the "unrelated rows stay identical" test | Gave every claim its own random stream and fixed IDs from the clean baseline |

---

## 5. Limitations

- All data is synthetic and the assumptions (fraud points, thresholds, mandatory-document lists) are my own modelling choices, documented in `docs/business_rules.md`.
- In the clean baseline, each claim is made on one coverage, and one incident leads to one claim. Duplicates come only from injection.
- The independent audit and the generator share the same rules module, so a mistake in a rule would appear in both. The boundary tests (`test_rules.py`) are the protection against that.
- Fraud labels describe patterns built from the indicators. They do not prove fraud, and in a 3-claim burst only the third claim reaches the referral threshold.
- AI answers are summarised in this log, not stored word for word. Exact timestamps are available in my chat history.

---

## 6. Overall AI-use statement

- **Tool:** Claude (claude.ai chat). No other AI tool was used for the work logged here.
- **Where AI accelerated my work:** first drafts of the plan, the ER diagram drawing code, the data dictionary, the generator and rules code, the tests, and this log.
- **Where I relied on it most:** writing the generator, the rules module and the test suites from the requirements in the brief.
- **How I directed it:** I worked through the brief step by step in its own order, asked each time for what to do, where to keep it and how, required downloadable files, and asked for this log to explain the reason behind every prompt.
- **How the work was verified:** by running the generator and the tests, comparing row counts and checksums, checking the data against the brief's rules, and fixing the problems listed in section 4.
- **Limitation of the AI sandbox:** the AI environment could not install the real `pytest`, so its test runs used a stand-in. The tests need to be re-run with real `pytest` on my own machine.
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

- AI answers are summarised, not stored word for word.
- Exact timestamps are available from my chat history. [FILL: add a link or an export if available]
- Anything marked `[FILL]` is my personal review note and must be completed before submission.
