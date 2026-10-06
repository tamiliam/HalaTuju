# Retrospective — Upload-race fix + exact income-document request (2026-06-12)

Live-testing fixes surfaced while the owner tested the Action Centre on test account #16
(ELANJELIAN, STR route). Backend + i18n + FE; **no migration**. Shipped to `main` (`a38f484`).

## What Was Built

1. **Unread uploads no longer greenlight their task (the race fix).**
   `resolution.doc_match_verdict` returned `'ok'` for a document that hadn't actually been
   read yet. Under the hourly doc-assist cap (`DOC_ASSIST_RATE_LIMIT_PER_HOUR=15`, hit during
   heavy testing), a re-uploaded slip was marked `review_manually` (deferred read) → read as
   `'pending'` → accepted as `'ok'` → the task auto-closed before the scan finished. So a
   wrong/blurry re-upload could satisfy an officer's "this is unclear, send a better one"
   request. Fixes:
   - `doc_match_verdict` now returns a distinct **`'pending'`** (hold the task) for an
     unscanned doc: results-slip name/subjects not read, an **unreadable subject table**
     (previously only the name was checked), and an `ic`/`parent_ic` whose Vision scan
     hasn't run. `resolve_doc_items_for_upload` only closes on `'ok'`, so `'pending'` keeps
     the task open.
   - The interactive upload **force-reads** the just-submitted file past the hourly cap
     (`views._maybe_extract_fields(force=True)`), so the one doc the student uploaded in
     response to a request is always scanned before its verdict.
   - FE (`ActionCentre`) shows a calm "still checking" note on `'pending'`, not Gopal's
     error coach.

2. **The income request names the exact document.** `income_proof_missing` only ever fires
   on the STR route (`verdict_engine._verdict_income`), but its student / officer / consent
   copy said the generic "salary slip, EPF, or STR" — which actively invited a wrong upload
   (the Upload button files whatever the student picks as `doc_type='str'`, so an EPF gets
   filed as an STR and fails). Reworded to name the STR (Sumbangan Tunai Rahmah) specifically
   in en/ms/ta (Tamil first-draft).

## What Went Well

- Root cause was pinned on **real prod data** via the pooler shell before writing code: doc
  666's `vision_fields_run_at` was +13s after `uploaded_at`, and `student_verdict` was set —
  proving the read happens but the accept decision could run against a not-yet-read state.
- The investigation found a second, sharper edge the owner hadn't (the str-typed Upload
  button files *any* picked file as an STR), which made "name the exact doc" clearly correct
  rather than cosmetic.
- One existing test (`test_ai_throttle_skips_gemini_but_uploads`) caught the behaviour change
  and was updated to assert the new force-read policy — the suite did its job.

## What Went Wrong

- **"We haven't read it yet" was treated identically to "we read it and it's clean."**
  Symptom: an unscanned re-upload greenlit its task. Root cause: `doc_match_verdict`'s
  original D1 policy ("pending → accept, don't trap the student behind a slow scanner")
  conflated a genuine OCR outage with a merely-deferred read, so a rate-limited read was
  waved through as OK. Fix: a distinct `'pending'` verdict that holds the task, plus a
  force-read of the interactive upload so 'pending' only persists on a true read failure
  (where the reviewer is the backstop). Added to `docs/lessons.md`.
- **A route-specific requirement was described with route-generic copy.** Symptom: an
  STR-route student was told "salary slip, EPF, or STR" when only the STR counts. Root cause:
  the verdict code (`income_proof_missing`) was route-aware but its i18n string wasn't — the
  copy was written once, generically, and never reconciled against which route can raise it.
  Fix this sprint (name the doc); the durable fix is the **student self-serve route-switch**
  (next sprint) so "I don't have an STR" has a real exit instead of a dead end.

## Design Decisions

See `docs/decisions.md` — "Unread document holds its task ('pending' ≠ 'ok')".

## Numbers

- 1156 scholarship pytest (+9) · 303 jest · i18n parity 2543×3 · `next build` clean.
- 9 files, no migration. 1 deploy (api + web). Verified on prod #16 (STR route): the income
  verdict raises `income_proof_missing`; the real results slip still reads `mismatch`; an
  unscanned IC now returns `pending`.

## Deferred / Next

- **Student self-serve income route-switch** (the planned feature): a "I don't have an STR —
  prove my income another way" action in the Action Centre that re-runs the income mini-wizard
  post-submit, flips `income_route`, and surfaces the new route's document tickets. Needs a
  post-submit income-route endpoint + an Action-Centre UI (Stitch-first). Owner approved
  *student self-serve* as the driver.
- **Tamil refine** on the three reworded `income_proof_missing` strings + the new
  `actionCentre.stillChecking` note (first-draft).
