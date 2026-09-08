# BrightPath request #23 — where we are, and what step 4 is

Written 2026-09-08 to survive a context compaction. Read this before touching step 4.

**Worktree** `.worktrees/bc-verdict`, branch `feat/bc-verdict`, base `origin/main` at `8b9d19f4`.
**NOTHING IS DEPLOYED.** No migration in any of it. Three commits, steps 1–3.

---

## The request, and the plan the owner approved

Request #23 is `scheduled`, classified **bug / sprint, 9.0h, no charge**. Analysis **52** was approved
and posted to BrightPath as comment **77** — that is the promise we are delivering against.

| Step | What | State |
|---|---|---|
| 1 | Read the child's IC from the certificate + re-read the 62 on file | **shipped** `f8836d36` |
| 2 | Unreadable ≠ clean: amber + ask for a re-upload | **shipped** `6317bf80` |
| 3 | The merged green/amber/red rule + father does not block | **shipped** `7099c61d` |
| 4 | Income no longer switches off the relationship check | **shipped** `79826979` (measured first, owner ruled 2026-09-08) |
| 5 | A document type for an explanation letter | **DEFERRED** — try the QC override first |

---

## ✅ STEP 4 — MEASURED FIRST, THEN RULED ON, THEN SHIPPED

The promise in comment 77, verbatim:

> 4. Stop income evidence from switching off the relationship check. SEVEN live applications, named
> for you first, and your decision before it ships.

Kept: the seven were measured on production and put to the owner, who ruled **turn the check back
on** (2026-09-08). `birth_certificate` and `guardianship_letter` are out of
`services._INCOME_CLUSTER_DOC_TYPES`; the income softening beside it is unchanged and tested in the
same class. Four tests in `test_one_clean_cluster.py::TestProvingIncomeDoesNotSettleParentage`.

### The mechanism to measure

`apps/scholarship/services.py`, `document_red_blockers`:

```python
_INCOME_CLUSTER_DOC_TYPES = ('parent_ic', 'salary_slip', 'epf', 'str',
                             'birth_certificate', 'guardianship_letter')
...
    income_ok = income_engine.income_established(application)
    for doc in application.documents.filter(superseded_at__isnull=True):
        dt = doc.doc_type
        if income_ok and dt in _INCOME_CLUSTER_DOC_TYPES:
            continue          # ← the birth-certificate check is skipped entirely
```

Once income is established by ANY route, every income-cluster document stops being checked —
including the birth certificate, whose question ("is this her mother?") is a different question from
"is this family poor?". That is how Lina (app 144) submitted with an unreadable certificate.

### ✅ MEASURED ON PRODUCTION 2026-09-08 — ONE APPLICATION MOVES, AND IT IS THE TEST ACCOUNT

Seven live (undecided) applications: **16 · 32 · 106 · 132 · 133 · 140 · 144**. Four of them hold a
birth certificate (16, 32, 133, 144); 106, 132 and 140 hold none, so the relationship check cannot
reach them at all.

Every row scored by running the REAL `_name_bucket` / `_nric_bucket` / `_combine_relationship` over
the production values (pure functions, no DB — script kept in the session scratchpad):

| app | status | child row | mother row | newly blocks? |
|---|---|---|---|---|
| **16** | shortlisted | **mismatch** | match | **YES** — the owner's own test account |
| 32 | interviewing | match | match | no |
| 133 | profile_complete | match | match | no |
| 144 | interviewed | no_ref | no_ref | no |

**Application 16 is `ELANJELIAN VENUGOPAL` — the owner's test record.** Its certificate belongs to
`THEEPICAA A/P SELVINAYAGAM` (a different person, correctly read as a mismatch). It holds an approved
2026 STR in the mother's name, so income IS established and the check is skipped today.

**So: no real student is affected. Zero of the seven.**

⚠ **Applications 43 and 124 were awarded DURING this measurement** (`awarded_at` 2026-09-08 05:01
UTC), so they left the live set mid-count. Any re-measurement must re-read the statuses; do not
carry this table forward as though it were static.

### The whole 62-certificate corpus, for safety

Every row that is not a byte-identical match on both cells was scored the same way. **Three reds in
62**, and none of them is a false alarm:
- **#5** (expired) — genuinely a different family's certificate.
- **#9** (awarded) — the script reads red, but the LIVE engine rescues it: `chain_verified_earner`
  matches the mother's IC number on the income proof. Not a real red.
- **#16** — the test account above.

Everything else lands `match`, or amber (`check_one` ×7 on a child row with no number,
`check_name` ×1 on #84). The rule is safe to run for the next intake.

---

## ✅ SETTLED BY THE OWNER 2026-09-08 — THE FATHER ROW STAYS AS IT IS

**Should the father row go amber when we only hold a name? — NO. Leave it.** The owner accepted the
recommendation below verbatim. Do not re-open it, and do not "finish the one-cell rule" by extending
it to the father row: that is a decision, not an oversight.

The owner's rule says one cell alone is amber, and their own example was the father. But the father
row never went through `_combine_relationship`: it compares the certificate against the patronymic
in the STUDENT'S OWN name, so it has only ever had one cell by construction.

Measured: applying the rule there turns **51 of 62** father rows amber, because only **11**
applications carry a father's IC to compare a number against.

Recommendation given: leave it. The row already corroborates two documents, just not two numbers,
and amber on 51 of 62 is a chip reviewers learn to ignore. **Awaiting the owner.**

---

## ⚠ SEQUENCING AT DEPLOY — THE RE-READ GOES WITH STEP 3, NOT AFTER

21 of 62 certificates carry a child name and no number, so step 3's rule turns those child rows
amber. **20 of them are already awarded/rejected/expired; exactly ONE live application moves.**
Those blanks exist because our own Gemini prompt said *"leave bc_child_nric empty"*. The re-read
fills them, so most go back to green.

**To run the re-read on the live service** (`reextract_documents` takes `--doc-type`, and the cron
endpoint passes NO arguments — that was TD-234's shape and step 1 fixed it):

1. Set on the api service: `REEXTRACT_DOC_TYPE=birth_certificate` and
   `REEXTRACT_PASS=reextract_bc_child_ic` (a NEW pass name makes those docs eligible again without
   re-sweeping the whole corpus).
2. Run the `reextract-documents` cron job repeatedly (20 docs a run) until it reports nothing left.
3. **UNSET both.**

⚠ Never re-extract from a local checkout — no Storage access, so it reads "no text" and destroys
`vision_fields`.

---

## Rules from steps 1–3 that must not be "tidied"

- **`vision.nric_dob_agrees` is load-bearing, not belt-and-braces.** `bc_child_nric` feeds
  `_nric_bucket` against the student's own NRIC, so a misread number is a CONFIDENT mismatch where a
  blank was nothing. The register number (`BZ21723`) sits in the same corner of the page.
- **The two readers are guarded differently on purpose.** `bc_parse` (geometry, and the one that
  actually runs) reads the number from a position bracket, so it drops only a number the date
  REFUTES. The Gemini fallback has no bracket, so there the number is kept only when the date
  confirms it.
- **`_usable_relationship_fields` returns a REASON string**, not a boolean — `''` / `'wrong_type'` /
  `'unreadable'`. Truthy at every existing call site. The two states owe the student different
  words: telling a family with a poor scan that their certificate is not genuine is the wrong
  message.
- **`relationship_doc_unreadable` is DOCUMENT-level, never row-level.** A blank father row on a
  certificate that names no father is a real absence.
- **Verdict codes are written out as literals, never picked by a ternary** — a computed code escapes
  `test_no_new_unverifiable_dynamic_call_site` and the whole i18n coverage check. The first cut used
  a ternary and the guard caught it, correctly.
- **`STUDENT_DOC_REQUEST_CODES` is derived from the `_unreadable` suffix** — that is what turns a
  finding into an Action-Centre re-upload a form-locked student can act on.
- **A red father row blocks nothing, at BOTH gates** — `services.document_red_blockers` and
  `resolution.doc_match_verdict`. The second matters as much: without it a student re-uploads for
  ever over a row they cannot change.

---

## Still outstanding for the owner (carried, not part of step 4)

- **~~Lina's own file is not repaired.~~ CLOSED BY THE OWNER 2026-09-08: leave it.** Verbatim:
  *"This is water under the bridge. Future Lina will not be prevented when she submits the BC only."*
  Verified true — application 144's certificate rows all read `no_ref`, so nothing about it blocks
  her; step 2 asks her for a clearer copy and that ask does not hold the door. **Do not build the
  multi-page reader for this.**
- **ms/ta are first drafts** for everything new here: `birth_cert_unreadable`,
  `guardianship_letter_unreadable`, the `unreadable` fact label, plus the older
  `scholarship.docs.relCheck.checkName` and the #16/#17 strings.

## Gates at the last commit

pytest **4668** · jest **1826** · tsc **24** (baseline, TD-221) · lint **0** · i18n **4892 × 3** ·
`next build` exit 0 · `makemigrations --check` clean. Five bite-checks landed across the three steps.

⚠ The shared checkout's `node_modules` lost `@jest` and `.bin` mid-session; repaired with
`npm install` from the committed lockfile, and the one-line lockfile churn was reverted. If jest
suddenly reports "not recognized", that is the cause — not the branch.
