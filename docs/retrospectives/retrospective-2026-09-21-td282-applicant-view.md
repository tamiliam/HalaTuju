# Retrospective — TD-282: opening one applicant costs 38 queries, not 315

**Date:** 2026-09-21 · **Sprint:** TD-282, the officer's applicant view · **Scope:** the detail
endpoint only, by brief.

H18 counted what nobody had counted since June and stopped: **315 database queries to open one
applicant with no documents, 385 with three**. This sprint fixed it. The number is now **38, with
or without documents**, and the two budgets being equal is the part worth remembering — the
per-document slope, roughly twenty queries for every document a family uploads, is gone.

The interesting output is not the number. It is that the change moves **no answer at all**, and
that this is provable on demand rather than by assertion: a permanent 238-case test compares the
endpoint's response BYTES with the snapshot on and with it switched off.

---

## What Was Built

| | before | after |
|---|---|---|
| Applicant detail, no documents | **315** queries | **38** |
| Applicant detail, three documents | **385** | **38** |
| Applicant detail, six documents | **425** (H18 read 437 on a different six) | **39** |
| Cost per extra document | ~20 queries | **0**, bar one |
| Reads of `applicant_documents` in that request | **283** | **6** (one snapshot load + three deliberately untouched + the payload's own list + one write-path `.exists()`) |
| `VERDICT_ENGINE_VERSION` | 8 | **8 — unchanged, and that is the claim** |
| pytest | 7,086 / 3 skipped | **7,104 / 3 skipped** |
| jest | 2,982 / 166 suites | **2,982 / 166** |

Two new files; twenty edited.

1. **`apps/scholarship/document_snapshot.py` (new).** One `SELECT` of an application's documents,
   held for the length of one read-only computation in a `contextvars.ContextVar` keyed on the
   application id. Five readers — `latest_doc`, `live_docs`, `has_live_doc`, `present_doc_types`,
   `tagged_members` — answer from that list when a snapshot is open **for that
   application** and run exactly the query they replaced when one is not.
2. **`apps/scholarship/tests/test_document_snapshot.py` (new).** The ON==OFF matrix, plus the
   staleness tests, plus a reader-by-reader agreement test.
3. **One place opens it**: `AdminApplicationDetailView.get`, around the serializer build.
4. **Both query budgets lowered** in `code-standards.json` — `budget` only. The frozen `baseline`
   is untouched, no ledger gained or lost a member, no key was renamed, so no `_moved` record and
   no `BASELINE_SHA256` re-pin. (TD-286 asks how a NEW standard enters a frozen record; this
   sprint needed neither a new key nor a rename, so it did not have to answer that question. The
   question is still open.)

---

## Design Decisions

**Why not `prefetch_related`.** Because H18 already proved it does nothing here, and this sprint
re-proved it before designing anything: a `.filter(...)` on a related manager ignores a prefetch
cache. The reflex fix passes every test and moves the measurement by zero.

**Why not hang the cache on the model instance.** That is the same mechanism as a prefetch cache
and it has the same hazard in a worse form: the instance outlives the read. A later write in the
same request, or a second computation on the same object, would silently answer from a
photograph. A `ContextVar` scoped by a `with` block cannot do that — `reset(token)` in a `finally`
closes it whatever happens, including an exception.

**Why keyed on the application id.** Several engines walk from a document back to
`doc.application`. A snapshot that answered for *any* application would hand one family's
documents to another's verdict. A reader handed a different application falls straight through to
its query.

**Why the fallback returns the QUERYSET and not a list.** The first cut made every reader return
a list subclass. Four engine tests broke immediately, because they pass a stand-in object whose
`documents.filter(**kw)` returns a fixed double — and a list forced evaluation the double could
not survive. That was the right failure at the right time: the **un-snapshotted path must be
byte-identical in shape, not only in result**, down to a single `.filter()` call and its
laziness. `DocRows` (a `list` with `.first()` and `.exists()`) now appears only inside a snapshot.

**Why `services.application_completeness` and `check2_queries` were left alone.** The first
because the brief forbade touching it; the second because it sits inside a write, and the one
rule this module has is that a write path may not read a snapshot. Between them they are 4 of the
remaining 38 queries. Leaving them is cheaper than the argument about whether they are safe.

**Why TD-287 was not folded in.** It was re-priced instead. Inside the snapshot the doubled
`_utility_context` now costs **nothing** — the four reads it wasted were exactly the
`applicant_documents` SELECTs the snapshot removed. Threading the context through
`verdict_income_salary`'s four functions still means editing `_verdict_income`, which is in the
`long_functions` ledger, on the eligibility path, for a saving that no longer appears on the
surface the entry was written about. Its register entry now says that and carries a new trigger.

---

## What Went Well

1. **Measuring the whole 315 first, not just the 265, changed the design.** The brief insisted on
   a call-site table for every query, and building one found that the document reads were **283**
   of 315, not the 265 TD-282 recorded — the original figure had grouped three distinct SQL
   shapes (a `.first()` with a `LIMIT`, an unbounded iteration, and a `household_member IN`
   filter) as one statement because they share a prefix. Three shapes means three reader
   signatures. A design built on "it is one query, 265 times" would have needed a fourth pass.

2. **The other 50 were worth knowing about.** They are not one problem: ~13 `resolution_items`
   reads (Check 2 and the SLA both re-query), 5 interview reads, 3 `partner_admins`, 3 `consents`,
   and one `auth.users` statement that only PostgreSQL can run. None is an N+1 and none is worth a
   sprint — which is itself a finding, because it says the endpoint's remaining cost is about
   thirty ordinary reads and not a second hidden loop.

3. **The ON==OFF matrix found two pre-existing defects on its first run.** The
   `garbage-vision-fields` row 500s the endpoint for two stored shapes
   (`{"authenticity": "a string"}` and `{"authenticity": {"status": 12345}}`). Both raise
   identically with the snapshot switched off, so neither belongs to this sprint — but nobody had
   ever pointed a fixture at malformed `vision_fields` before. The first is the instructive one:
   nine production sites write `(vf.get('authenticity') or {}).get(...)`, each carefully checking
   that `vision_fields` is a dict and then assuming `authenticity` is one. TD-293.

4. **Both budgets fell to the same number, and the test said so in words.** `"LOWER it to 38"`,
   twice, which is exactly what H18 predicted the ratchet would do when the fix landed.

---

## What Went Wrong

1. **The first superseded fixture was too kind, and the bite-check came back SILENT.**
   *What happened:* injecting "make the snapshot ignore `superseded_at`" left the 34-case
   `superseded` row of the ON==OFF matrix **green**. The fault was real and the matrix did not see
   it.
   *Why:* the fixture re-uploaded **identical** documents — an old IC replaced by an identical IC,
   an old STR by an identical STR. Every helper that reads "the latest" still got the newest row
   (a superseded row is by definition older than the one that replaced it), and every helper that
   iterates got the same values twice. So a snapshot that included dead rows produced the same
   answers. The fixture modelled a state a student almost never creates. Real students re-upload
   **because the first one was refused, unreadable, or the wrong address**.
   *The system change:* the fixture now pairs each dead row with a materially WORSE one — a
   `Tidak Lulus` STR replaced by an approved one, a bill whose address mismatched, a payslip
   scored `not_salary`, a results slip carrying someone else's name. The same injection now turns
   all 34 cases red, naming each one. The general lesson is in `docs/lessons.md`: **a superseded /
   soft-deleted row must differ from its replacement in the fixture, or a guard that forgets to
   exclude it cannot fail.**

2. **`_has_read_doc` took the related manager, not the application, and only the second caller
   revealed it.** A helper written to receive `docs` cannot reach a snapshot, because the snapshot
   is keyed on the application. Changing the signature was two call sites and no risk, but it is a
   small instance of a real shape: **a helper that takes a queryset has already thrown away the
   identity of the thing it is querying.** Worth noticing the next time one is written.

3. **The matrix costs the suite about half a minute and it nearly cost more.** Written as one
   test method holding all 238 cases it ran on a single xdist worker at 2m21s and became the
   longest thing in the suite. Split into one method per document set it spreads across workers.
   Total suite: about 4m40s before, about 5m after (the wall-clock varies by a minute or two with
   what else this machine is doing, so treat it as "half a minute", not as a reading).

4. **A bite-check harness left running while its subject is edited will silently undo the
   edit.** The harness restores the ORIGINAL BYTES it read at the start of each injection, which
   is exactly right — and it means any edit made to that file while it runs is reverted by the
   next `finally`. Two small changes to `document_snapshot.py` were lost that way and had to be
   re-applied, and the SHA-256 restore check happily confirmed a restore to the stale copy,
   because that IS what it promises. *The system change:* the harness prints the digest it is
   restoring to; the rule to add beside it is **do not edit a file while a bite harness holds a
   copy of it, and take the final bite run against the bytes that ship.** The seven results
   quoted in Numbers are from that final run.

---

## Numbers

* pytest **7,104 passed / 3 skipped** (`python -m pytest -q -n auto` in `halatuju_api`),
  baseline 7,086 / 3 measured before any edit. jest **2,982 passed / 166 suites**
  (`npm run gates` in `halatuju-web`), unchanged either side.
* `manage.py check` — no issues. `makemigrations --check --dry-run` — no changes. No migration.
* Query budgets: `no-documents` **315 → 38**, `three-documents` **385 → 38**. A six-document
  fixture, measured for this retrospective and not budgeted, reads **425 → 39**; the one extra
  query is an `applicant_documents` read from one of the three sites deliberately left on its own
  query (`check2_queries`, inside a write), and it fires only once however many documents follow.
  `STUDENT_READ_BUDGETS` (7 / 13 / 20) and `FALL_THROUGH_BUDGETS` (27 / 39) **unchanged**, which
  is the proof that nothing outside the detail endpoint moved.
* ON==OFF matrix: **238 cases** — 17 stage cases × 2 income routes × 7 document sets.
* Bite-checks: seven, each injected into the original bytes and restored in a `finally` with the
  SHA-256 verified. Six faults red as expected; one comment-only edit green. One silent bite,
  found and closed (above).

---

## What Is Still Open

* **TD-291** — the admin Requests list is 3 + 2N (org) / 3 + 4N (super) queries for N requests,
  measured. It is NOT this defect: nothing there touches `applicant_documents`, and the fix is a
  filtered `Prefetch`. The student's own read is this defect and a snapshot would take a
  two-earner family from 20 to about 7 — but it serves a LIST, so the snapshot must be opened per
  application inside the loop.
* **TD-292** — no tie-breaker on `ORDER BY uploaded_at DESC`, anywhere. Pre-existing; the snapshot
  makes the helpers agree with each other for the first time. Needs a production count before the
  one-word fix, because it could move a band.
* **TD-293** — two malformed `vision_fields` shapes 500 the officer's screen. Pre-existing and
  proven so.
* **TD-287** — re-priced, not done. See above.
* **TD-286** — still open, and still the reason a new budget has nowhere to live but a test file.
  This sprint did not have to answer it.
