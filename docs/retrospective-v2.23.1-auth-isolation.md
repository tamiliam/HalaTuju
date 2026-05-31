# Retrospective — v2.23.1 · Auth session-isolation fix (PKCE) + sponsor/partner UX polish

**Date:** 2026-05-31
**Scope:** A patch release bundling (1) a real cross-scope session-leak fix, and (2) live-feedback UI polish on the
sponsor forms, the student auth modal, and the partner login. No backend/migration changes.

## What Was Built

**Security fix — cross-scope session leak (the headline).**
- All three browser Supabase clients (`getSupabase` student, `getAdminSupabase`, `getSponsorSupabase`) now set
  `flowType: 'pkce'`. Previously they used the supabase-js default (`implicit`), which returns the OAuth session in the
  URL hash; the globally-mounted student `AuthProvider` read admin/sponsor Google logins off `/admin/auth/callback` +
  `/sponsor/auth/callback` into the student storage key. PKCE returns a `?code=` exchangeable only with the
  initiating client's verifier, so a non-initiating client cannot claim the session.

**UI polish (live feedback):**
- Student auth-gate modal title → "Create Your Free **Student** Account".
- Phone fields → "**Mobile number**" + `12-345 6789` placeholder (leading 0 dropped after `+60`); new
  `formatMyMobile` / `isValidMyMobile` (pure, node-unit-tested) format-as-you-type + validate; inline email + mobile
  error messages on the sponsor register form; sponsor phone stored as `+60 12-345 6789`.
- Required `*` markers turned **red** on the sponsor forms.
- `/admin/login` → "**Partner Login**" / "For partner organisations and invited individuals" (badge "Partner");
  redundant footer **"Admin" link removed**.

## What Went Well

- **The user's repro pinpointed it fast.** "Log into admin → log out → click Dashboard → I'm logged in as the admin
  Gmail" was enough to confirm the bleed direction (admin → student) and that logout didn't clear the student copy.
- **Root-caused in the library, not by guessing.** Grepped the installed `@supabase/auth-js@2.95.3` and found
  `flowType: 'implicit'` as the literal default (`GoTrueClient.js:24`) — so the diagnosis was a fact, not a hunch.
- **The fix is one line per client** and standard (PKCE is the recommended flow), with no migration and no change to
  redirect URLs or the Supabase dashboard.

## What Went Wrong

1. **I shipped two isolated auth clients (admin in March, sponsor in E1c) without setting the OAuth flow to PKCE — so "isolated storage key" gave a false sense of isolation.**
   - *Symptom:* logging into the Partner/admin (or sponsor) console with Google silently logged you into the Student
     app on the same browser; admin logout didn't clear it.
   - *Root cause:* I treated a distinct `storageKey` as sufficient isolation. It isn't — under the **implicit** OAuth
     flow the session arrives in the URL hash, which *any* mounted client reads regardless of storage key, and the
     student client is mounted globally. The isolation was only ever skin-deep; the actual session was up for grabs by
     whatever client happened to be on the callback page.
   - *System change:* lesson added — **any browser Supabase client that does OAuth must use `flowType: 'pkce'`;
     a separate `storageKey` alone does NOT isolate sessions under the implicit flow.** ARCHITECTURE_MAP now records
     PKCE as a load-bearing invariant for the three-client setup, so the next auth client (Phase F mentor?) inherits it.

2. **The bug existed since the admin client (March) but only surfaced now.**
   - *Symptom:* a months-old isolation hole, found only when the user happened to log in/out across scopes.
   - *Root cause:* the admin console and student app are rarely used back-to-back in the same browser by the same
     person, so the bleed was invisible in normal use; adding the sponsor scope (a third client, same defaults) is what
     prompted the user to ask "would they leak?" — which exposed the pre-existing admin↔student case.
   - *System change:* the lesson above is the durable fix; also a reminder that "no one reported it" is not evidence of
     correctness for an auth-isolation property — these need to be reasoned about, not observed into existence.

## Design Decision

(Logged in `docs/decisions.md`.) **PKCE on all browser Supabase clients** — the load-bearing mechanism for keeping the
student / admin / sponsor sessions isolated when they share an origin and the same Google identity.

## Numbers

- **Tests:** 1411 backend pytest (unchanged) · 183 jest (+5 mobile-helper unit tests) · `next build` clean.
- **i18n parity:** 1652 × en/ms/ta (Tamil first-draft for the new strings).
- **No migration.** Files: 3 auth clients (PKCE), 2 sponsor pages + 1 modal + footer + admin login + sponsorAuth lib +
  its test, 3 message files.
- **Residual (TD-073):** the global student `AuthProvider` still mounts under `/admin` + `/sponsor` (anon-session noise
  + a harmless failed-exchange log) — the leak is closed; this is cosmetic.

## Follow-up — v2.23.2 (logout isolation + modal overlay)

User testing of v2.23.1 surfaced two more isolation gaps the login-side PKCE fix didn't cover:

1. **Logout wasn't isolated** — logging out of the student app also logged out admin/sponsor.
   - *Root cause (two):* (a) `clearAll()` on student logout deleted **every** `halatuju_*` localStorage key — including
     the sibling scopes' session keys (`halatuju_admin_session` / `halatuju_sponsor_session`); (b) all three
     `signOut()` used Supabase's default **`global`** scope, which revokes every session for the (shared) identity
     server-side. *Fix:* `clearAll()` now preserves the two sibling session keys; all three signOuts use
     `scope: 'local'`.
   - *Lesson:* session isolation has a **logout half**, not just a login half — I fixed PKCE (login) but left the
     default global-signOut + a prefix-greedy `clearAll` in place. When isolating multi-scope auth, audit *both*
     directions.

2. **Student auth modal overlaid `/admin` + `/sponsor`** (`AuthGateModal` is global in `Providers`). *Fix:* the modal
   route-guards via `usePathname` and renders nothing on those paths. (Deeper provider-scoping stays TD-073.)

*v2.23.2 numbers:* 1411 pytest + 183 jest, `next build` clean, no migration. 5 frontend files.
