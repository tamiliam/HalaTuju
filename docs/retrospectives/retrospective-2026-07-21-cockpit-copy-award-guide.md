# Retrospective — Cockpit copy pass + award-email guide-from-Drive — 2026-07-21

A live-review batch: a small backend feature (award email sources its installation guide live from
Drive) plus a set of owner-driven copy/UX tweaks to the reviewer cockpit. Web + api; **no migration**.
Not yet deployed — owner gates the push (push = deploy).

## What Was Built

- **Award email — LIVE installation guide from Drive.** `sheets.fetch_drive_pdf(folder, filename)`
  (read-only: `files().list` + `get_media`, reusing the payments filer's SA + full `drive` scope);
  `emails.vircle_guide_attachment()` now fetches the live copy from `03 Vircle/05 Student Guide/`
  (cached `VIRCLE_GUIDE_CACHE_SECONDS`=600) and falls back to the bundled repo asset when Drive is
  unreachable. New settings `VIRCLE_GUIDE_FOLDER`/`_FILENAME`/`_CACHE_SECONDS`. +3 tests
  (`test_vircle.py`: prefers Drive / falls back / caches). Verified live against prod Drive (the real
  code returned the 1.49 MB Drive file, which was newer than the stale bundled copy).
- **Cockpit copy (en/ms/ta):** "Verification verdict" → **AI Prediction** + new subtitle; "Rate AI
  verification" → **Rate AI Prediction**; QC "Reopen" → **Reopen/Reject** + reworded hint; Check-2
  subtitle → "Queries raised and/or documents requested by the system/reviewer".
- **Cockpit UX:** the student's-own-words reveal is now ONE box (note · Student's Story · funding,
  hairline-divided), **open by default**; "Your story" heading → **Student's Story**.

## What Went Well

- The Drive read reused existing auth wholesale — no new DWD scope, no new SA. A quick read-only probe
  against prod confirmed access + the exact folder path before any code was written, so the feature
  worked first try end-to-end.
- Fallback-to-bundled keeps the award email robust: a Drive hiccup can never drop the attachment.

## What Went Wrong

- **A scripted i18n edit clobbered the wrong block, twice.** Symptom: renaming
  `admin.scholarship.verdict.title` via a "first `"verdict":` block that ends with `{`" heuristic hit a
  *different* `verdict` block (there are two in en.json) — overwriting "Interview scheduling". Root
  cause: block-scoping an i18n edit by first-match instead of by the full key path or a
  unique-string anchor. Fix: for a single-key i18n change, replace by the exact current value only
  after asserting it occurs exactly once (`txt.count(f'"{old}"') == 1`), or navigate the full path;
  never select a block by first-match on an ambiguous key name. Captured in `lessons.md`.

## Design Decisions

- **Award guide sourced LIVE from Drive (cached + fallback), not synced once.** See `decisions.md`.

## Numbers

- 4164 pytest collected (scholarship + courses + reports) + 611 jest. i18n parity green.
- Files: `sheets.py`, `emails.py`, `settings/base.py`, `test_vircle.py` (api); `page.tsx` + en/ms/ta
  (web). No migration.
