# Retrospective — B40 Phase E/F Sprint 11: Sponsor referral / invitation (F4)

**Date:** 2026-06-09
**Branch:** `main` (held local, not pushed — deploy owner-gated)
**Migration:** `0054` (new `SponsorReferral` model)

## What Was Built

An approved sponsor can invite a prospective sponsor to the F1 landing, with attribution on join.

- **`SponsorReferral` model + `apps/scholarship/referrals.py`** (writes only; imports `emails` + `models`):
  `create_referral` (validates email → `bad_email`, opaque code, best-effort invite email; duplicate still-pending invite
  to the same email is idempotent), `attribute_referral` (a `/sponsor?ref=<code>` register flips the row to `joined` +
  links the account; self-/unknown-code is a safe no-op), `purge_expired_referrals` (scrubs invitee email/name + marks
  `expired` after 60 days).
- **Trilingual invite email** (`send_sponsor_referral_invite`) with the inviter's optional note + the `?ref=` link.
- **Endpoint** `GET/POST /api/v1/sponsor/referrals/` (approved sponsors only); `SponsorRegisterView` attributes a `ref`.
- **Daily PDPA purge** as `purge-referrals` in `CronRunView.JOBS` + a `purge_sponsor_referrals` command.
- **Frontend** `/sponsor`: an "Invite a friend" form + a "Your invitations" list (Joined/Invited/Expired pills); the
  invite link's `?ref=` is captured to `sessionStorage` (`KEY_SPONSOR_REF`) on arrival and threaded through register so
  attribution survives the sign-in round-trip.

## What Went Well

- **Owner decision settled before the schema.** The model-shape + retention window (full guest-book, 60 days) were
  confirmed up front via a plain-language explanation, so the `SponsorReferral` table was built once — no churn (the
  lesson #148 pattern: lock the product call before `makemigrations`).
- **Reused every existing seam.** Invite email rides the established trilingual `send_mail` pattern; the purge is the
  `CronRunView.JOBS` + management-command pattern (lesson #137); the FE invite section is the approved sponsor-portal
  card style; the `?ref` capture reuses the sessionStorage round-trip pattern already used for sponsor sign-in. Nothing
  bespoke.
- **Attribution survives the round-trip by construction.** Capturing `?ref` to `sessionStorage` on arrival (not relying
  on the URL persisting through the OAuth/sign-in navigation) means a brand-new sponsor who clicks an invite, signs in,
  and registers is still attributed — the failure mode a query-param-only approach would have had.
- **PDPA built in, not bolted on.** The 60-day purge command + the RLS/cron carries (TD-106/107) were logged the moment
  the table was created, so "we hold strangers' emails" is a tracked, time-boxed obligation rather than a silent risk.

## What Went Wrong

- **The Stitch generation failed with an auth error (expired MCP credential), not the usual timeout.** *Symptom:* the
  `generate_screen_from_text` call returned "missing authentication credential", so no screen was produced to approve
  against. *Root cause:* the interactively-authenticated Stitch MCP session had lapsed — a known property of these
  servers (they can be absent/expired between sessions). *System change:* fell back immediately to the established
  ASCII-mock-via-AskUserQuestion path (lesson #153) rather than retrying a dead credential; the owner approved the design
  directly because it extends the already-signed-off sponsor-portal card pattern. The takeaway (reinforces #153): treat
  a Stitch auth failure the same as a timeout — present the concrete mock for sign-off, don't block the sprint on the MCP.

## Design Decisions

- **Full `SponsorReferral` guest-book + 60-day purge** (owner, 2026-06-09) over a lightweight `referred_by`. Logged in
  decisions.md with the PII trade-off (RLS + daily purge are now go-live prerequisites).
- **Referral endpoints gated on `require_approved_sponsor`**, not merely registered — an unvetted sponsor shouldn't send
  invites in the programme's name. (Routine; noted here.)
- **`?ref` persisted in `sessionStorage`, cleared on successful register** — threading via the URL alone would lose it
  across the sign-in navigation (the lesson #59/#104 family: prefer the durable channel for a value that must survive a
  multi-step/redirect flow, and clear it at the legitimate exit).

## Numbers

- **Backend:** 947 scholarship (+12) + 1051 courses/reports = **1998 pytest** green. Migration `0054` applies locally;
  `makemigrations --check` clean; `manage.py check` clean.
- **Frontend:** `next build` clean (`/sponsor` 7.21 kB); `tsc --noEmit` clean for changed files; **283 jest** (the page
  is render-only, lesson #47).
- **i18n:** parity **2416** ×en/ms/ta (+17; Tamil first-draft, TD-108).
- **Files touched:** ~15 (model, `referrals.py` [new], emails, views_sponsor, views [cron], urls, serializers, command
  [new], migration `0054`, 1 new test file; FE: sponsor page, api.ts, storage.ts, 3 message files) + close docs.
- **Deploys:** 0 (held). **Carried:** TD-106 (migration `0054` MCP+RLS at deploy), TD-107 (Cloud Scheduler purge job),
  TD-108 (F4 Tamil refine).
