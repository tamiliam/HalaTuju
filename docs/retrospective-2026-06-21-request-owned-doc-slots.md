# Retrospective — Request-owned document slots (2026-06-21)

Branch `feat/request-owned-doc-slots` (commit `d9278f3`, off `origin/main` `a6dad1d`). One coherent
deliverable: stop live document data loss when a reviewer requests multiple extra / cross-person docs.

## What Was Built
- **`ApplicantDocument.request_code`** (migration `scholarship/0067`, additive) — the officer
  ResolutionItem code (`officer_N`) a reviewer-requested upload satisfies. `''` = the student's own
  apply-form/route doc (shared slot, unchanged).
- **Slot key is now `(doc_type, household_member, request_code)`** in the upload view's sweep — so a
  re-upload of the *same* request replaces, but two different requests (and multiple "Other" docs)
  coexist instead of overwriting each other.
- **STR force-tag skipped for request-keyed uploads** — a reviewer asking for the father's IC on a
  mother-STR route no longer gets the doc force-tagged to the earner (which overwrote the mother's IC).
- **`resolve_doc_items_for_upload` resolves by code** when the upload is request-keyed — two open
  "Other" tasks don't both clear on one upload.
- **`MAX_OTHER_DOCS=10`** per-application cap on reviewer-requested extras (40-total cap still applies).
- **FE:** Action Centre passes `item.code` for `officer_*` requests only; system docs keep the shared slot.
- **+6 tests** (`test_documents.py::TestRequestOwnedSlots`): multi-Other coexist, same-request replace,
  cross-person income no-overwrite, the 10-cap, resolve-by-code.

## What Went Well
- Root cause confirmed against live data *before* coding (per Iron Law): a DB audit showed Theepicaa
  (app 4) 5 "Other" requests → 1 stored, Divashini (18) 2→1 — not a hypothesis, a measured loss.
- One field unified two symptoms (multi-Other collapse + cross-person overwrite) — both were the same
  missing dimension in the slot key.
- All gates green first pass: 81 doc/resolution pytest, `next build` clean, 327 jest.

## What Went Wrong
1. **The slot model shipped (TD-115) with a key that couldn't represent reviewer-requested duplicates.**
   - *Symptom:* every "Other" upload overwrote the previous one; live applicants silently lost documents.
   - *Root cause:* the slot key `(doc_type, household_member)` assumed each `(type, member)` pair is
     unique per application. That holds for the apply form but not for the Action Centre, where a
     reviewer can legitimately request several docs of the *same* type (`other`, or the same income doc
     for a different person). The request dimension was never modelled.
   - *Prevention:* lesson added — when a slot/uniqueness key is introduced, enumerate **every** writer
     of that slot (apply form AND reviewer requests AND system gaps), not just the primary path. Added a
     regression test asserting multiple same-type requests coexist.
2. **Migration number `0067` collides with the unmerged `feat/whatsapp-comms` branch.**
   - *Symptom:* two branches each define `scholarship/0067`.
   - *Root cause:* parallel feature branches off the same `origin/main` each take the next free number
     independently; neither is on main yet so `makemigrations` can't see the other.
   - *Prevention:* documented in CHANGELOG + memory; whichever merges second renumbers to `0068`. This
     is an inherent cost of parallel branches, not a process miss — the mitigation is the merge-time check.

## Design Decisions
- See `docs/decisions.md` → "Request-owned document slots".

## Numbers
- Files: 10 (6 backend incl. migration, 2 FE, CHANGELOG, +1 retrospective). 1 additive migration.
- Tests: +6 (scholarship). `next build` clean; 327 jest unchanged.
- Live impact: prevents further loss on all in-review applicants. Already-lost blobs unrecoverable
  (owner: do not attempt recovery, prevent going forward).
