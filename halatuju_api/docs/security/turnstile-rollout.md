# Turnstile / captcha rollout (security item C)

Cloudflare Turnstile protects every Supabase Auth entry point (student anonymous
sign-in, sponsor/admin password sign-in, sign-up, password reset) and the public
contact form. The widget runs **invisibly** (Managed mode, `execution: 'execute'`)
— real users see nothing; only flagged traffic gets a visible challenge.

**Keys** (Cloudflare dashboard → Turnstile, account `tamiliam@gmail.com`):
- Site key (public): `0x4AAAAAADi6qwQ0qHQQ5BSg` — in `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
- Secret key: in the local `.env` as `TURNSTILE_SECRET_KEY`. Lives in production only
  in **Supabase Auth config** and the **contact Edge Function secret** — never in a
  tracked file, never in Django/Cloud Run (the contact form bypasses Django).

## Why the order matters

Supabase's "Enable Captcha protection" toggle is **project-wide**: the instant it is
on, EVERY auth call (including the automatic anonymous sign-in on first page load)
must carry a valid token or it fails. So the frontend that *sends* tokens must be
live **before** the toggle is flipped. Likewise, anon INSERT on `contact_submissions`
must stay open until the form is posting to the Edge Function instead.

## Rollout sequence (do in this order)

1. **Deploy the frontend** (`halatuju-web`) with `NEXT_PUBLIC_TURNSTILE_SITE_KEY` set.
   At this point tokens are fetched but Supabase still ignores them (toggle off) —
   every flow keeps working. Safe, reversible.
   - Cloud Run build env var: add `NEXT_PUBLIC_TURNSTILE_SITE_KEY` to the web service.

2. **Deploy the Edge Function** `contact-submit` (`--no-verify-jwt`, it's public) and
   set its secret:
   - `TURNSTILE_SECRET_KEY` = the Turnstile secret (Supabase auto-injects
     `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`).
   - The frontend already posts here (step 1), so contact submissions now verify.

3. **Revoke anon INSERT on `contact_submissions`** so the Edge Function (service role)
   is the ONLY write path — a bot can no longer skip the captcha by inserting with
   the public anon key. (Drop/!replace the anon-insert policy; keep service_role.)
   Do this only AFTER step 1 is live, or the live form breaks in the gap.

4. **Flip the Supabase captcha toggle** — Dashboard → Authentication → Attack
   Protection → **Enable Captcha protection** → Provider **Turnstile** → paste the
   **secret key** → Save. This is the enforcing step. Do it LAST.

5. **Smoke every flow** immediately after step 4:
   - First visit (anonymous sign-in succeeds, no visible captcha).
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
- `getTurnstileToken()` resolves `undefined` when the site key is absent, so local
  dev and any misconfiguration degrade gracefully rather than locking users out.
