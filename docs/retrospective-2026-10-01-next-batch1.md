# Retrospective — Next-tier batch 1 (2026-10-01)

**Scope (owner's "go" on the Next tier; the lead chose the batch):** nine small api fixes from the
debt register — TD-242, TD-249, TD-047, TD-160, TD-316, TD-314, TD-089, TD-317 and TD-130's code
half. (TD-145 and TD-169 were read with them and left out: TD-145 needs a production measurement
first, TD-169 is owner-parked.) Built by one agent; an adversarial reviewer who did not build it
reads the diff before the lead commits, pushes or deploys anything.

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-242 | a failed Drive READ is `IngestReport.failed_reads`: needs attention, alert email, `PARTLY APPLIED - SHORT`; an empty sheet is still quiet | `test_spending_import.py::TestFailedReadIsAFinding` (4) |
| TD-249 | `timezone.localtime(due).date()` in the nudge email | `test_review_nudges.py` (+1; every old assertion kept) |
| TD-047 | lazy retry (`CoursesConfig.ensure_data`, once a minute, no thread); `GET /api/v1/health/` (`apps/courses/health.py`) | `test_course_data_health.py` (6) |
| TD-160 | MOVE `_service_headers` + `_create_supabase_user` → `apps/courses/supabase_admin.py`; then read the UID back by email on a 2xx without one; WARNING if that fails | `test_invite_uid_readback.py` (5) |
| TD-316 | the STR-IC ask resolves only when `str_ic_slots` no longer names the member | `test_str_ic_ask_resolution.py` (3) |
| TD-314 | `_str` joins the TD-306 set: one bills question, re-worded in place | `test_high_utility_variants.py` (+6); 3 changed expectations in `test_income_whose_str_vouches.py` |
| TD-089 | the guardian's name from `fields.guardian_name` (`vision_name` for old rows); engine `2026-10-01.1` | `test_guardian_letter_relationship.py` (5) |
| TD-317 | MOVE the KWSP parser → `apps/scholarship/doc_parse_epf.py`; then emit the split totals, all or nothing | `test_doc_parse.py::TestEpfParser` (+6), `test_income_engine.py::TestEpfMonthlySalary` (+1) |
| TD-130 | the mailto `List-Unsubscribe` shim on the decision (`student_decisions._send`) and query sends; a tenant's own support address | `test_unsub_shim_td130.py` (3) |

No student- or officer-facing copy changed. No stored data changed. Nothing touches production.

## What bit

Thirteen mutations went red and two comment-only changes stayed green, each from a byte backup with
SHA-256 equal on restore: a failed read treated as empty again (twice — in `drive_sources` and by
folding the seam's None back into `[]`); `.date()` back in the nudge; the retry removed; the health
route always 200; the read-back removed; the IC ask resolved on any 'ok' again; `_str` outside the
set again (which also turns the three updated TD-285 tests red); `vision_name` only; the split
totals dropped; the shim dropped on the query path and, separately, on the decision path.

The whole api suite: 7,292 → **7,332 passed**, 3 skipped (40 new tests); the web suite unchanged
at 3,193 / 187 suites. `manage.py check` clean; `makemigrations --check` no changes.

## What surprised

- **`verdict_engine.py` had ONE line of room**, again: a four-line version note for TD-089 pushed
  it to 1,169 against an allowance of 1,166. The note is one line.
- **The `doc_parse` move tightened the ratchet**: 688 → 614 lines, so the tightness test demanded
  the budget fall 669 → 614. Still over 600 — the next split is the BC parser (P4, ~150 lines).
- **TD-314 changes a documented TD-285 behaviour.** decisions.md (2026-09-29) said the sync CLOSES
  an open `_str` clarify and raises the plain one; it is now re-worded in place, and at interview it
  is no longer closed. Three existing tests carried the old expectation and now say what changed.
- **The two moves create one import-order rule.** `doc_parse_epf` imports its helpers from
  `doc_parse`, which imports it back at the line the section used to occupy; `doc_parse` must load
  first. Every caller goes through `doc_parse.parse_by_labels`, and a test pins that the registered
  parser is the moved one.
- **The shim on `_send` reaches more than the decision mail.** `student_reminders` and `signing`
  send through the same `_send`, so the application-completion reminders (named in TD-130's body)
  and the sign invitation carry it too — the intended reach, stated here so nobody is surprised.

## What the adversarial review found (2026-10-01), and what changed

- **F2 (TD-317) was the big one: the fix never ran on a real statement.** Every one of the 13
  `eval/snapshots/epf__*` OCR texts prints the CARUMAN table one CELL per line, and the parser read
  one ROW per line — so the five statements that have a table all read `contribution_status
  'unknown'`, no contribution figure, no split. The synthetic fixture was the only thing that ever
  read. Now both layouts read (all-or-nothing: three figures per date, months = rows, the grand
  total equals the rows to the sen); all five read both totals, pinned by a test over the corpus.
  The review also found the older gap behind it: an 'unknown' parse never falls back to Gemini
  (`vision.py:2114`). That is a paid call, so it is TD-319, an owner decision, not a fix here.
- **F1 (TD-089): a letter about another child linked the guardian.** And while fixing it, the
  bigger miss: the verdict engine read the letter in THREE more places, all on `vision_name` — so
  round one's fix reached only the cockpit's IC check, and no letter ever confirmed a guardian in
  the verdict. One reading, `letter_names` (guardian + ward), now serves all four; four verdict
  tests (STR and salary routes, right ward and wrong) went red before it and green after.
- **F3:** `doc_parse_epf` imported from `doc_parse`, which imports it back — a circular ImportError
  if imported first. The shared helpers moved verbatim to the leaf `doc_parse_text.py`; `doc_parse`
  registers the parser. A fresh-interpreter test pins either order.
- **F4:** the engine-version pin test, and a decisions.md sentence.
- **F5 (TD-047):** the load now publishes every map first and `requirements_df` last, and the
  retry clock is re-checked under the lock. Only the eligibility route retries; ranking stays
  empty until an eligibility check has run (every student runs one first) — not widened.
- **F6 (TD-130):** the mailto subject said "B40" on every organisation's mail; it now names the
  sender's programme — which also changes the interview mail's header to "BrightPath Bursary".

**The lesson is one already on file** ("`doc_parse` parsers MUST be validated against real
documents", in `doc_parse.py`'s own contract and lessons S15/L86): the build said so in "Not done,
on purpose" below and shipped anyway on the synthetic fixture. A real corpus was in the repo.

## Not done, on purpose

- **Cloud Run wiring for `/api/v1/health/`.** Nothing calls it; a startup or liveness probe is a
  production step for the lead. The route does not retry the load itself, so a probe hitting it
  cannot make the service hammer the database.
- **The Brevo List-Help setting (TD-130).** The owner's action with Brevo support; TD-130 stays open.
- **The Gemini fallback for an 'unknown' EPF parse (TD-319)** — a paid call, the owner's decision.
