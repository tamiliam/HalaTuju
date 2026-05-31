# Retrospective — v2.22.0 · Phase E Sprint E1: sponsor accounts + admin vetting

**Date:** 2026-05-31
**Scope:** First slice of the safeguarded sponsor marketplace (`docs/scholarship/phase-e-sponsor-roadmap.md`).
Self-register → admin vets → approved sponsor lands in a portal shell. **Zero student data in this slice.**
Backend (E1a) was committed earlier this session (`99c7937`); this close covers the whole sprint incl. the E1b frontend.

## What Was Built

**Backend (E1a, `99c7937`):**
- `Sponsor` model — `supabase_user_id`-keyed, status `pending`/`approved`/`rejected`/`suspended`, table `sponsors`
  (**migration `scholarship/0031`**, applied **migrate-first** via Supabase MCP with **RLS deny-by-default**).
- `SponsorMixin` (mirrors `PartnerAdminMixin`): resolve sponsor by Supabase UID; `require_approved_sponsor` gate for E2+.
- Sponsor self-service: `POST /api/v1/sponsor/register/` (idempotent; rejects anonymous; emails admin) +
  `GET /api/v1/sponsor/me/` (own account or `{registered:false}`).
- Admin vetting: `GET /api/v1/admin/sponsors/[?status]` + `POST /api/v1/admin/sponsors/<id>/review/
  {approve|reject|suspend}` (reviewer-gated; stamps `reviewed_at`/`reviewed_by`).
- **Allowlist `SponsorSerializer`** (id/name/email/organisation/status/is_approved/created_at — read-only).
- NRIC-gate middleware whitelists `/api/v1/sponsor/`. +12 tests (`test_sponsor.py`).

**Frontend (E1b):**
- `/sponsor` portal — 6 states off `getSponsorMe()`: loading · signed-out (Google sign-in) · register form
  (name/organisation/note) · pending · approved ("browsing coming soon" E2 shell) · inactive (rejected/suspended).
- `/admin/sponsors` vetting table (status filter) with per-row Approve / Reject / Suspend + a "Sponsors" admin nav link.
- **Sponsor sign-in bypasses the student NRIC modal** via a direct Google OAuth flagged by `KEY_SPONSOR_SIGNIN`
  (sessionStorage), read by `/auth/callback` to route back to `/sponsor`. No change to `AuthGateModal`.
- i18n `sponsorPortal.*` + `admin.sponsors.*` across en/ms/ta (parity 1598; Tamil first-draft).

## What Went Well

- **Pattern-mirroring kept the sprint tight.** `/sponsor` mirrors `sponsor/register-interest` + `get-started`;
  `/admin/sponsors` mirrors the `/admin/scholarship` list. Reusing proven, already-styled patterns meant no design
  churn and a clean first build.
- **The sign-in design fork was resolved without touching fragile code.** The student auth flow (anonymous →
  Google → NRIC claim) has been the subject of multiple bug-fix sprints. Routing the sponsor through a dedicated
  one-shot flag instead of the shared `KEY_PENDING_AUTH_ACTION` meant the NRIC modal is provably never triggered for
  a sponsor, with zero edits to `AuthGateModal`.
- **Hooks discipline held.** All `/sponsor` and `/admin/sponsors` hooks sit above every early return; `next build`
  (now ESLint-gated for `rules-of-hooks` since efd43b7) compiled both routes with no hook errors.
- **Verification was unmasked.** `next build` ran to a logfile and the exit code was read separately from any grep
  (per the TD-059 lesson) — EXIT=0, both routes present in the route table.

## What Went Wrong

1. **Shipped without an interactive smoke (known, accepted, logged).**
   - *Symptom:* the sprint is test-green but the two stateful flows — sponsor Google-OAuth sign-in and admin
     approve/reject — were never click-tested; only `next build` typing + backend pytest cover them.
   - *Root cause:* both flows require credentials headless Playwright can't supply (a real Google account; a vetted
     admin session), so the existing "interactive smoke before imminent users" lesson can't be satisfied by an agent
     alone for this feature class.
   - *System change:* logged as **TD-070** with an explicit manual smoke script, and made **step 0 of the Next
     Sprint** ("live-verify E1 first"). E2 must not expose anything to real sponsors until that smoke passes. This
     converts an un-actionable "should test" into a gated checklist item the user runs.

2. **Stitch was skipped for the new screens (borderline vs the MANDATORY rule).**
   - *Symptom:* the workspace rule "prototype UI in Stitch before coding templates" was not followed for `/sponsor`
     and `/admin/sponsors`.
   - *Root cause:* these screens are near-verbatim reuses of three existing, already-approved layouts (register-interest
     card, get-started chooser, admin list table) — there was no novel layout to prototype, and the user explicitly
     approved proceeding "straight to code mirroring the existing patterns".
   - *System change:* none warranted — the rule's intent (don't code novel UI blind) was met because the UI isn't
     novel. Noting it so a future reader doesn't read the skip as an oversight. If E2's anonymised browse cards (a
     genuinely new layout) come up, Stitch-first applies in full.

## Design Decisions

(Logged in `docs/decisions.md`.)
1. **Sponsor sign-in via a dedicated one-shot flag, bypassing the student NRIC modal** — rather than adding a
   `'sponsor'` `AuthGateReason` and teaching `AuthGateModal` to skip NRIC.
2. **E1 ships as a portal *shell* (no student data), the measured resolution of "auth before product = empty room"**
   — the earlier sponsor-login lesson said don't build auth without a destination; E1 builds exactly the minimum
   destination (own-account view + admin vetting) and nothing that touches a student.

## Numbers

- **Tests:** 1408 backend pytest (+12 from E1a) · 172 jest (+1) · `next build` clean · golden masters intact (5319/2026).
- **i18n parity:** 1598 keys × en/ms/ta (+21; Tamil first-draft).
- **Migrations:** `scholarship/0031` (E1a, already on prod migrate-first). **No E1b migration.**
- **Files touched (E1b):** 2 new pages + 4 edits (admin layout nav, auth callback, storage key, 3 message files).
- **Deploys:** 0 so far (E1b pushed at this close; E1a already live).
