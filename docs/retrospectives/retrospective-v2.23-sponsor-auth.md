# Retrospective — v2.23.0 · Phase E Sprint E1c: sponsor self-serve auth

**Date:** 2026-05-31
**Scope:** Live-feedback follow-up to E1 (v2.22.0). Replace the Google-only thin sponsor sign-in with a real
self-serve account — dedicated login page, full email/password registration, and a consistent logged-out header.

## What Was Built

**Backend:**
- `Sponsor` gains `phone`, `source`, `consent_at`, `consent_version` (**migration `scholarship/0032`**, additive,
  applied migrate-first via Supabase MCP — 4 columns on `sponsors`, migration row recorded, prod-verified).
- Register endpoint now requires name+phone+source+consent and **completes** an incomplete (Google/legacy) row in
  place; `/sponsor/me` exposes `profile_complete`; admin vetting dict + `AdminSponsor` carry phone/source.
- Sponsor suite 12 → 15 tests (full-field create, missing-fields 400, consent-required 400, complete-incomplete,
  profile_complete flags).

**Frontend — isolated sponsor auth stack (mirrors admin):**
- `lib/sponsor-supabase.ts` (own `storageKey 'halatuju_sponsor_session'`; email/password + Google + reset),
  `lib/sponsor-auth-context.tsx` (`SponsorAuthProvider`/`useSponsorAuth` → `/sponsor/me`), `app/sponsor/layout.tsx`.
- `/sponsor/login` (email/pw + Google + forgot, styled like `/admin/login`); `/sponsor/register` (Full name as in
  NRIC/Passport, Email, Password w/ live rule checks, Re-enter, Phone +60, Source, PDPA consent); `/sponsor/auth/callback`.
- `/sponsor` portal reworked onto the new auth with a **complete-details** step (covers the Google case and the
  email-confirmation gap — pre-fills from the session/stash).
- `lib/sponsorAuth.ts` (`checkPassword`, `SPONSOR_SOURCES`) — pure, node-env unit-tested (6 tests).
- `components/AuthButtons.tsx` (`Log in ▾ {Student/Sponsor/Partner} | Sign Up`) shared by `AppHeader` **and** the
  landing nav; Sponsor menu → `/sponsor/login`, Sign-Up chooser → `/sponsor/register`. **`KEY_SPONSOR_SIGNIN` removed.**

## What Went Well

- **Mirroring the admin auth stack made this fast and consistent** — the isolated-client + provider + login-page shape
  ported cleanly; the sponsor pages look and behave like the admin ones with little new design.
- **Pure helpers kept logic testable** — password rules + source list live in `lib/sponsorAuth.ts` and are unit-tested
  in node-env jest, so the form component stays a thin renderer (the B40-S2 lesson, applied).
- **One complete-details step unified two awkward paths** — the Google "no phone/source/consent" case and the
  email-confirmation "no session at signup" case both resolve through the same portal form, pre-filled from a stash.
- **Migrate-first was clean** — additive ALTER + `django_migrations` row in one MCP transaction, prod-verified before push.

## What Went Wrong

1. **I reversed my own E1 sign-in decision one day after shipping it.**
   - *Symptom:* E1 (v2.22.0) shipped a sponsor sign-in built on the student Supabase client + a `KEY_SPONSOR_SIGNIN`
     flag; E1c ripped it out and rebuilt on an isolated client.
   - *Root cause:* in E1 I optimised for "least new code" and reused the student client, **without applying the
     project's already-settled answer for a distinct user-type auth** — the "Separate admin auth with isolated Supabase
     clients" decision (decisions.md, 2026-03-16). The pattern existed; I didn't reach for it because E1 only needed
     Google and the shared client *just about* worked. Adding email/password exposed the mismatch immediately.
   - *System change:* lesson added — **when adding auth for a new user-type, start from the isolated-client pattern,
     not the shared student client.** Had I done that in E1, there'd have been no churn.

2. **The email/password flow branches on a Supabase setting I didn't verify.**
   - *Symptom:* sign-up either returns a session (→ create the sponsor row now) or doesn't (→ "confirm your email",
     row created later at complete-details). I built both branches but never confirmed which the prod project does.
   - *Root cause:* didn't check the Supabase Auth "confirm email" setting before designing the flow.
   - *System change:* TD-070 extended to require checking the real setting during the live smoke; the flow is correct
     either way, but the UX (does the user see a confirm-email screen?) depends on it and should be confirmed, not assumed.

## Design Decisions

(Logged in `docs/decisions.md`.)
1. **Sponsor auth = isolated Supabase client mirroring admin** — *supersedes* the E1 "direct Google OAuth via
   `KEY_SPONSOR_SIGNIN` on the student client" decision.
2. **Email/password primary + Google-then-complete-details** — one portal complete-details step absorbs both the
   Google case and the email-confirmation gap.
3. **Shared `AuthButtons` component** for the logged-out cluster — one source for header + landing, no drift.

## Numbers

- **Tests:** 1411 backend pytest (sponsor 12 → 15) · 178 jest (+6 password-rule unit tests) · `next build` clean ·
  golden masters intact (5319/2026).
- **i18n parity:** 1650 keys × en/ms/ta (+52; Tamil first-draft).
- **Migration:** `scholarship/0032` (additive, migrate-first, prod-verified).
- **Files:** ~10 new (sponsor-supabase, sponsor-auth-context, sponsorAuth + test, AuthButtons, login/register/callback/
  layout pages) + ~10 edits (model, migration, 2 serializers/views, api/admin-api types, AppHeader, get-started,
  landing, storage, 3 message files). E1's `KEY_SPONSOR_SIGNIN` + the `/auth/callback` sponsor branch reverted.
- **Deferred:** Turnstile (TD-071), MY-only phone + orphaned register-interest (TD-072), click-test (TD-070).
