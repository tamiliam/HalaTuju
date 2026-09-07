# Retrospective — Org Config Sprint E: the document limits become organisation-tunable

**Date:** 2026-09-07
**Worktree:** `.worktrees/org-config-sprint-e`, branch `feat/org-config-sprint-e` (base = the
clock-box fix, `9b0a454e`)
**Migration:** none.

---

## What shipped

Four settings under a new **Documents** group: `max_doc_size_mb` (8, ceiling 25),
`max_docs_per_application` (40), `max_other_docs` (10), `doc_stage_max_attempts` (3).

**The two traps were found BEFORE writing code, by the sprint's own survey**, because Sprint D
had just written both of them down as lessons:

1. `ScholarshipDocuments` carried `MAX_DOC_SIZE_BYTES = 8 * 1024 * 1024` — under a comment saying
   the server was authoritative, which was true and beside the point: the browser still needed the
   number to warn a student before a doomed upload, and a copy cannot be right for two tenants.
2. `"Each file must be under 8 MB"` stated the limit as fact in three languages.

Both were handled the way the lessons say: serve the number on the payload the screen already
fetches, and interpolate the copy.

## Design decisions worth keeping

**One conversion, named.** The tab speaks MB and the wire speaks bytes.
`org_config.max_doc_size_bytes()` is the only place the two meet; every door calls it and none
carries its own `* 1024 * 1024`. The refusal reports MB by reading the registry, not by dividing
again. A second conversion is how one door starts refusing a file another door accepted.

**Rounding DOWN, on purpose.** `MAX_DOC_SIZE_BYTES` is env-overridable and need not be a whole
number of MB. Integer division means an 8.7 MB platform value shows as 8 — the screen never
promises more than the server accepts. A test pins this.

**The ceiling was checked against storage, not guessed.** Before offering the owner a 25 MB
ceiling I read `storage.buckets`: `b40-documents` sets no `file_size_limit`, so the real wall is
the Supabase project default (50 MB). A ceiling above that would have been a setting that lets an
organisation promise an upload the storage layer then refuses — the kind of number that looks
configurable and is a lie.

**The refusal prefers the server's own number.** The 400 body carries `max_mb`; the message reads
that first and falls back to the served limit. If a browser is holding a stale payload, the
sentence still matches the rejection the student just got.

## What went wrong

**Three test failures on the first run, all mine, none in the product code.**

1. *Symptom:* the document endpoints returned `403 nric_required`. *Cause:* `SupabaseAuthMiddleware`
   gates every student route on the profile carrying an NRIC, and my fixture profile had none — a
   gate that lives in middleware, not in the view I was reading. *Prevention:* the fixture now sets
   an NRIC with a comment naming the middleware, so the next student-endpoint test in this file
   starts from a profile that can actually reach a view.
2. *Symptom:* `out_of_range: max_docs_per_application`. *Cause:* my fixture set the total cap to 2
   while the registry floor I had just written is 5 — I wrote the test against the behaviour and
   forgot it must also pass the fence. *Prevention:* none needed beyond the fix; the storage fence
   refusing my own fixture is the fence working.
3. The third was the same NRIC gate on a second test.

The general shape: **a test that exercises a real endpoint must satisfy every gate in front of it,
including the ones in middleware that the view never mentions.**

## Numbers

| Gate | Result |
|------|--------|
| pytest (`apps/`) | **5956** (+8; `test_org_config.py` 56 → 64) |
| jest | **1776** (+7) |
| `next lint` | 0 errors |
| `tsc --noEmit` | 24 (baseline, none new) |
| i18n | **4845 × 3** (+12 keys; ms/ta first drafts) |
| `next build` | compiled successfully |
| `makemigrations --check` | no changes detected |

Four bite-checks landed and were restored by writing the original back: the size cap de-orged,
the payload serving a literal, the breaker re-globalled, and the browser ignoring the served size.

## The lesson worth carrying

Sprint D's two lessons — *serve, never mirror* and *the message files are read sites* — were
applied here as a **checklist during the survey**, before any code. Both traps were present, both
were found in the first ten minutes, and neither cost a defect or a live-review round. That is the
whole return on writing a lesson down: the next sprint spends the cost as a search instead of as a
bug.
