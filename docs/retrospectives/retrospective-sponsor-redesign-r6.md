# Retrospective — Sponsor Portal Redesign, R6 (Standing gift / AutoSponsor)

**Date:** 2026-06-20 · **Branch:** `sprint/r6-autosponsor` (off `origin/main`, worktree `.worktrees/r6`)
**Scope:** BE (new model + service + cron + endpoint) + FE (Account card), **migration `scholarship/0066`**, ships dark
behind `SPONSOR_POOL_ENABLED`.

## Goal
The AutoInvest-style innovation: a sponsor's balance auto-supports the next matching student, "set it and forget it" —
without weakening any safety property (the student still accepts; no real money moves).

## Owner decisions (at sprint start)
- **Trigger:** event-driven — when a matching student is published.
- **Low balance:** skip silently (retry once topped up).
- **Consent:** none — rely on the existing donation terms (the donation is already final into the trust; this only
  automates the "offer" click).

## What shipped
- **`StandingGift` model** (OneToOne sponsor): `field_pref` / `state_pref` (empty = any) + optional `max_amount` cap +
  `active` + `last_allocated_at`. Migration `0066` (new `standing_gifts` table).
- **`standing_gift.py`** — `matching_gifts(application)` (prefs + cap + live balance, least-recently-allocated first) +
  `run_standing_gifts()` (funds every currently-fundable pool student with the first matching gift; flag-guarded,
  best-effort per student).
- **`auto_sponsor` management command** + `auto-sponsor` in `CronRunView.JOBS` → an **hourly** Cloud Scheduler job
  (mirrors `sponsor-realtime`).
- **`GET/PUT /api/v1/sponsor/standing-gift/`** (`SponsorStandingGiftView`, flag + approved-sponsor gated) +
  `StandingGiftSerializer` (the sponsor's own config; positive-`max_amount` validation).
- **FE:** AutoSponsor card on My Account (on/off + field/state dropdowns from the portal pool facets + per-student cap +
  save), `getSponsorStandingGift`/`putSponsorStandingGift` clients. Trilingual `sponsorPortal.autoSponsor.*`.

## Design decisions (see docs/decisions.md)
- **Hourly cron as the "event-driven" seam, not the admin publish request.** Allocation reuses `fund_student` (a money
  mutation), so it runs in a dedicated hourly job over currently-fundable students — never synchronously inside the
  admin anon-publish request. Hourly = "event-driven enough"; keeps money-ops out of an unrelated admin action.
- **Balance is the throttle, no extra state.** Processing *all* currently-fundable students each run is naturally
  idempotent (a funded student gets a holding sponsorship → leaves the set) and self-limiting (each allocation holds the
  award), so low-balance "skip silently + retry" needs no flag, no count cap, no per-student stamp.

## Lessons applied (from docs/lessons.md)
- **`BigAutoField` in the hand-written `CreateModel` migration** (the R5 lesson) + `makemigrations --check` clean before
  commit.
- **Allowlist-safe:** the standing-gift endpoint returns the sponsor's own config only — no student data crosses; the
  allocation goes through the existing allowlist-safe `fund_student`.
- **jest is node-env:** no new jest test — the card is render-only and reuses the already-tested `poolFacets`; coverage
  is `next build` (TS) + the backend allocation tests.
- **Migration off `origin/main`** (0065 → 0066); read code from the worktree (`main`), never the other agent's primary
  checkout.
- **`npm ci`** for an isolated `node_modules` (the shared junction stays broken while the other agent's branch deps
  diverge).

## What went wrong
- Nothing notable. The migration matched the model first try (BigAutoField + OneToOne FK), and all 13 new tests passed
  on the first run. (The only friction was the harness requiring a fresh `Read` of each file in the new worktree before
  `Edit` — expected.)

## Verification
- `pytest` — **13 new** (`test_standing_gift.py`: matching, allocation, idempotency, low-balance skip, field/state/cap
  filters, inactive, fair-spread, flag-off inert, endpoint GET/PUT upsert, bad-amount 400, pending 403, flag-off 404) +
  **1412 scholarship green**; `makemigrations --check` clean.
- `jest` — **361** (no new; card render-only).
- `next build` — **EXIT=0**, ✓ Compiled successfully (`/sponsor/account` 5.3 kB).
- i18n parity — **2747 × 3**, zero diff.
- No interactive smoke (needs an approved sponsor session + a published match; ships dark — click-through at go-live).

## Tech debt / follow-ups
- **Cloud Scheduler job** `halatuju-auto-sponsor` (hourly) is created at deploy (this sprint's ops step).
- **Top-up nudge (deferred):** the owner chose "skip silently" for low balance; a future "your AutoSponsor paused — top
  up" email is an easy add if engagement data wants it.
- **Tamil refinement (TD-132):** the new `autoSponsor.*` Tamil strings are first-drafts for the owner's refine pass.

## Next
R7 — **Polish + i18n parity + fold into go-live** (the final redesign sprint): full en/ms/ta refinement (Tamil per the
style guide), accessibility, empty states, mobile; hands the redesigned portal to the existing flag-flip. After R7 the
7-sprint redesign is complete.
