# Turnstile / captcha rollout (security item C)

Cloudflare Turnstile protects every Supabase Auth password entry point (sponsor/admin
password sign-in, sponsor sign-up, password reset) and the public contact form. (Student
anonymous sign-in was one of them until 2026-11-19; the site no longer creates anonymous
sessions — see "Captcha repair" below.) The widget runs **invisibly** (Managed mode, `execution: 'execute'`)
— real users see nothing; only flagged traffic gets a visible challenge.

**Keys** (Cloudflare dashboard → Turnstile, account `tamiliam@gmail.com`):
- Site key (public): `0x4AAAAAADi6qwQ0qHQQ5BSg` — in `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
- Secret key: in the local `.env` as `TURNSTILE_SECRET_KEY`. Lives in production only
  in **Supabase Auth config** and the **contact Edge Function secret** — never in a
  tracked file, never in Django/Cloud Run (the contact form bypasses Django).

## Why the order matters

Supabase's "Enable Captcha protection" toggle is **project-wide**: the instant it is
on, EVERY auth call must carry a valid token or it fails. (Until 2026-11-19 that included
an automatic anonymous sign-in on every first page load; that sign-in is gone.) So the frontend that *sends* tokens must be
live **before** the toggle is flipped. Likewise, anon INSERT on `contact_submissions`
must stay open until the form is posting to the Edge Function instead.

## Rollout sequence (do in this order — no step leaves a broken window)

1. **Deploy the Edge Function** `contact-submit` first (`--no-verify-jwt`, it's
   public) and set its secret. The live contact form is still on the old
   direct-insert path, so the function just sits ready and unused — zero impact.
   - `TURNSTILE_SECRET_KEY` = the Turnstile secret (Supabase auto-injects
     `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`).

2. **Deploy the frontend** (`halatuju-web`) — the site key is baked into the image
   via the Dockerfile `ENV NEXT_PUBLIC_TURNSTILE_SITE_KEY`. Now the contact form
   posts to the (already-live) Edge Function, and auth tokens are fetched but
   Supabase still ignores them (toggle off) — every flow keeps working. Reversible.

3. **Revoke anon INSERT on `contact_submissions`** so the Edge Function (service role)
   is the ONLY write path — a bot can no longer skip the captcha by inserting with
   the public anon key. (Drop/replace the anon-insert policy; keep service_role.)
   Safe now because the live form (step 2) no longer direct-inserts.

4. **Flip the Supabase captcha toggle** — Dashboard → Authentication → Attack
   Protection → **Enable Captcha protection** → Provider **Turnstile** → paste the
   **secret key** → Save. This is the enforcing step. Do it LAST.

5. **Smoke every flow** immediately after step 4:
   - First visit: no visible captcha, and no anonymous sign-in request (`/auth/v1/signup`)
     in the browser's network tab (since 2026-11-19).
   - Sponsor login + register + password reset.
   - Admin login + password reset.
   - Contact form submit (success) — and confirm a direct anon insert now fails.

## Rollback

- Auth problems after step 4 → turn the Supabase toggle **off** (instant; tokens are
  then ignored again). The frontend keeps working with or without the toggle.
- Contact problems → re-grant anon INSERT on `contact_submissions` (step 3 reverse)
  to fall back to the direct-insert path while investigating.

## Notes

- Google OAuth sign-in is exempt — Supabase does not enforce captcha on the OAuth
  redirect, so those buttons are unaffected.
- With no site key (local dev), `getTurnstileResult()` returns `off` and the doors call
  Supabase without a token, which works only while the toggle is off.

## Captcha repair (2026-11-19)

Owner decision 19 Nov: keep the toggle ON and fix the code. Before the fix, a token fetch
that failed for any reason (script blocked, slow network, 8 s timeout) resolved to
`undefined`, the door called Supabase anyway, and the visitor read Supabase's raw
"captcha protection: request disallowed".

- **Typed outcome** (`halatuju-web/src/lib/turnstile.ts`, `getTurnstileResult`):
  `ok` (token), `off` (no site key), `blocked` (the script never loaded within 10 s, or
  was refused: ad blocker, firewall, network), `failed` (the challenge errored or timed
  out). `getTurnstileToken()` stays for the contact form.
- **Budgets:** script load 10 s; silent challenge 15 s per attempt (was 8 s; a Managed
  pass makes several round trips to Cloudflare, and on congested mobile data those alone
  ran past 8 s); 2 attempts (reset + execute) for the silent path. A visible challenge gets
  120 s and is never retried: it is one attempt, and when it ends without a token (ran out of
  time or errored) the fetch fails. The retry after a Supabase captcha refusal gets ONE
  attempt, not a second full round. When the last attempt fails the widget is reset and kept
  hidden, so no challenge box can appear after the error is shown.
- **Worst-case waits** for one sign-in, sign-up or reset, Supabase's own time aside (one
  attempt = up to 15 s silent, then up to 120 s more if Cloudflare shows a challenge):
  - silent (no box ever shown): **40 s** = script 10 s + 2 x 15 s; **55 s** if Supabase
    refuses the token and the one-attempt retry also runs out (15 s more);
  - visible (Cloudflare asks the person to click): **160 s** = script 10 s + 15 s (the first
    attempt fails silently) + 15 s (the second attempt, until the challenge appears) + 120 s;
    and **295 s** only in the rare case that Supabase then refuses that token AND Cloudflare
    shows a challenge again on the retry (15 s + 120 s more). A visible challenge is never
    retried, and a person mid-challenge is never cut off.
- **Missing site key:** if Supabase refuses a door while the build has no site key (the
  switch is on but `NEXT_PUBLIC_TURNSTILE_SITE_KEY` was left out of the deploy), the
  browser console logs a `[captcha]` warning; the visitor sees the plain "did not finish"
  words.
- **Expiry:** `refresh-expired: 'manual'` plus an `expired-callback` that resets the
  widget; a token is never kept between calls. If Supabase still refuses a token
  (lapsed in flight, or duplicate), the door asks for one fresh token and tries once more.
- **The doors** (`halatuju-web/src/lib/captchaAuth.ts`, `withCaptcha`): admin/partner
  sign-in and reset, sponsor sign-in, sign-up and reset. On `blocked` / `failed` they
  return `error.code` `captcha_blocked` / `captcha_failed` and do **not** call Supabase.
  The screens show plain words from `messages/*.json` (`errors.captchaBlocked`,
  `errors.captchaFailed`, plus `errors.captchaGoogle` where the door offers Google).
- **Guest session removed:** `AuthProvider` no longer calls Supabase's anonymous sign-in
  on page load (it cost one Turnstile challenge and one auth row per visitor). Browsers that
  already hold an anonymous session keep it. The API ignores an anonymous token for data
  (profile, NRIC gate, quiz signals), but **one thing does change for visitors: throttling.**
  An anonymous token used to identify the visitor (`request.user_id` is set for it), so the
  per-IP throttle skipped them. A visitor with no session now calls the API **without a
  token**, so they fall under the per-IP throttle (`halatuju.throttling.ClientAnonRateThrottle`,
  `anon` = 1000 requests a minute per IP, IPv6 cut to /64).
  - **Classroom risk:** a school lab or library behind one shared address shares ONE
    1000-a-minute bucket. A full class clicking through course pages together could reach
    it and see refusals (HTTP 429) for the rest of that minute.
  - **Why this is a small change in practice:** with the captcha switch on, most anonymous
    sign-ins were already being refused before this repair (no token, a blocked script, a
    timed-out challenge), so most visitors were already calling without a token and already
    on the per-IP throttle. If a classroom report comes in, the rate is in
    `halatuju_api/halatuju/settings/base.py` (`DEFAULT_THROTTLE_RATES['anon']`); the API is
    not changed here.
- **Shared-phone wipe (TD-458):** with no session, browser `halatuju_*` student data tagged
  to another account is dropped only when `getSession()` returned no error AND the browser
  is online. A token refresh that failed on the network or with 502/503/504 also reads as
  "no session" (Supabase keeps the session and retries later), and must never wipe a
  student's grades, profile, quiz signals or half-filled apply form.
- **Unchanged:** Google sign-in (OAuth carries no captcha) and the `contact-submit` Edge
  Function. The contact form code is unchanged too, **but its wait is not**: it calls
  `getTurnstileToken()`, which now uses the same budgets. Before it posts, the form can wait
  up to **40 s** on the silent path (10 s script load + 2 silent tries of 15 s), against 8 s
  before this repair; with a visible challenge, up to 160 s (was 128 s). With no token it
  still posts, and the Edge Function decides, as before.
- **What a support reply can say:** the words on screen already tell the visitor to turn
  off the ad blocker, try another browser or mobile data, or use Google where offered.
