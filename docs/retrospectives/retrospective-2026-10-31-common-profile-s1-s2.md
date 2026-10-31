# Retrospective — Common profile S1 + S2 (2026-10-31)

Roadmap: `docs/plans/2026-10-31-common-profile-roadmap.md`. Mock-ups (owner-approved): https://claude.ai/artifact/2w7vJhKNhjpkNuy8oa5582.
Shipped together: main `3ad1f387`, migration `scholarship/0193_staff_profile_card` applied by hand first.

## What Was Built

- **S1 — one page, one card list.** `/admin/profile` renders `cardsFor(ctx)` from `lib/profileCards.ts` for every
  role; the separate source profile screen was retired. `GET admin/me/` (own account, opted in for sources).
  Reviewer cards and `admin/reviewer-profile/` follow the `review` permission; the first-sign-in hold stays
  Reviewer-role only (pinned by tests). Sign-in card: method, last signed in, and a server-side password change
  (`POST admin/me/password/`) — the client `updateUser({password})` is refused by the live project.
- **S2 — personal details.** Photo (Pillow re-encode, metadata stripped, 16 MP cap, private bucket, signed URLs,
  removed with the account, known to the orphan sweep), job title, About (600), phone for everyone with "show to
  my team", and the owner's fourth optional language (`other_language` + fluency, for Sabah). Team page and the
  source roster show photos and shared phones; header avatar from one cached `admin/me/` per session.

## What Went Well

- The adversarial review earned its place: one HIGH (a self-chosen password later overwritten by the temp-password
  expiry job, and the no-current-password door left open) and three MEDIUMs (a "hidden" phone served on the reviewer
  detail, other sessions not ended, a non-atomic attempt counter) — none on the roadmap's door list, all fixed
  before the push.
- Splitting the new endpoint into `apps/scholarship` (not `courses`) kept the cross-app import count at its budget.
- Additive-only migration with database defaults: the old image kept inserting rows during migrate-first.

## What Went Wrong

1. **The first Sign-in card used the client password update, which production refuses.**
   Why: the builder read the Supabase docs, not the project's own record (`app/admin/set-password/page.tsx` already
   documented "Current password required"). Prevention: the lead's review caught it by reading the existing sibling
   flow; the brief template for any auth change now names the sibling flow to read first (lesson below).
2. **Changing a password ignored the temp-password flag** (HIGH). Why: the door list (D1–D10) was written around the
   new feature, not around every existing job that reads the same Supabase metadata (`expire_temp_passwords`).
   Prevention: for an auth write, list every reader of the account's metadata, including crons — added to lessons.
3. **A captcha refusal would have read as "wrong password".** Why: `verify_password` treated every 400 as wrong
   credentials. The live captcha setting could not be read before deploy (credential access is blocked by policy,
   correctly). Prevention: only GoTrue's wrong-credential codes mean "wrong"; anything else is 503 (lead fix
   `3ad1f387`, tested).

## Design Decisions

- Card registry + one rule per card; reviewer cards by permission; hold by role (decisions.md, S1).
- `StaffProfile` is an ALIAS of `ReviewerProfile`, not a rename, so 0193 is ADD COLUMNs only.
- Phone rule revised: Team list shows a phone only when shared; reviewer detail shows it to assigners for review
  holders (the 2026-08-02 "assigner must reach the reviewer" rule) or when shared; address stays private.
- Attempt limit by five `cache.add` slots (atomic on DatabaseCache; `incr` is not); DRF throttle removed.

## Numbers

- pytest 10,964 passed / 3 skipped (baseline 10,861) · jest 5,523 / 346 suites (baseline 5,432 / 340).
- `/admin/profile` first load 174 → 166 kB; median 147.751 → 147.697 kB (0.30 kB room after Maintenance S6b's gain).
- Debt: TD-435 (hold with nothing to fill), TD-436 (raised + resolved), TD-437 (no source Website column),
  TD-438 (header photo link expires after an hour), TD-439 (reviewer-profile phone read-only once the web is live).
