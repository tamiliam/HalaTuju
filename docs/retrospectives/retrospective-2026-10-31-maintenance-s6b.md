# Retrospective — Student maintenance Sprint 6b: letters on the scholar file and on My Bursary (2026-10-31)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md` (Sprint 6, second half). Design of record: the
LettersAdmin, LettersStudent and CommsLetters boards on https://claude.ai/artifact/LFHNYc4ynsyKLn6ZZtzReC (owner:
"design ok", 2026-10-31). Shipped as `0e506798` (feature) and `98b0f964` (fixes for the adversarial review); live as
api-01213-crq and web-01036-mkf. Migration `scholarship/0192_letters` (two new tables) was applied by hand first.

## What Was Built

- **Five letter kinds** — general, discipline, suspension, termination, close-out — issued from the scholar file's
  Letters tab, a PDF in English or Malay stored privately at `<org>/<app>/letters/<id>.pdf`, a locked "A letter has
  been issued" email in her language, and a reply-by date frozen at issue from `letter_response_days` (default 14).
- **Documents only** (owner ruling): a letter never writes status, sub-state or money. After a termination letter the
  file prompts "Close the file?" and points at the existing Close control.
- **The doors, all on the server:** suspension and termination for super / org_admin only; a typed full name for
  discipline and termination; a closed file takes only general and close-out; no edit or delete, only Withdraw with a
  reason; she acknowledges her own file's letters once ("It does not mean you agree"); no sponsor, partner or source
  reader.
- **Per-organisation wording** on the Student communications page, one tab per PDF language.
- **Bundle (TD-427):** the base was already over the minimum room; the activity-timeline wording moved out of the
  Scholars list into `lib/scholarActivity.ts`, which brought the median back to "ok" (0.4 kB of room).

## What Went Well

- The design was approved before any code, so the build needed no layout rework.
- The adversarial review found no tenant or security hole; it found four real bugs before they shipped.
- The builder proved each fix's test by breaking the fix and watching the test fail.

## What Went Wrong

- **Deploy-order crash (caught in review):** the new web page read a shape the old API did not send. Web and API
  build at the same time, so either can go live first. Lesson: a web page must read a new API field defensively.
- **The PDF header date used UTC** while the body used Malaysian time — a one-day gap for letters issued before 08:00.
- **A double press made two letters**, and letters cannot be deleted. Now one issue key per dialog, unique per
  application.
- **`cleanup_orphan_blobs` knew only applicant documents**, so `--apply` would have deleted letter PDFs, signed
  contracts and request screenshots. It now lists every stored kind, pinned by a test.

## Left Open

- TD-367 (a closed funded file stays on draft payment runs) — a money change for its own sprint; letters add no path.
- No reminder for an overdue acknowledgement; overdue is shown, not chased.
- TD-427: page-size room is 0.4 kB; the next web sprint must give weight back first.

## Next

Sprint 7 — mentors (records), design first.
