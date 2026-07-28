# Retrospective — TD-182: console Google sign-in on a local origin

**Date:** 2026-07-28
**Scope:** one bug, its own commit. No feature work.
**Verification:** 1071 jest / 69 suites · i18n 4154 × 3 · `next build` clean · driven in a real browser on both hosts.

---

## What it turned out to be

Sign-in began at `http://localhost:3000` and came back at `http://127.0.0.1:3000`. Browser storage
is scoped to the **origin**, so the PKCE verifier written by the first was invisible to the second.
Same machine, same dev server, same browser, same code.

That is the whole bug. It took weeks to find because it was never measured.

## The part worth keeping

TD-182 already carried two recorded wrong diagnoses, both confident. It also carried a third — its
own **"To resolve"** — which I was one commit away from implementing:

> adopt `@supabase/ssr` for the admin client (and the sponsor client, which shares the pattern) so
> the PKCE verifier lives in a cookie rather than `localStorage`.

That came verbatim from Supabase's failure message. It would have migrated the auth storage layer
for every admin and sponsor login, touched live auth, and fixed **nothing** — cookies are scoped to
the host too, so a cookie on `127.0.0.1` is exactly as absent from `localhost`.

The message was not lying. It was answering the question it usually gets asked, from a library that
cannot see that the two ends of this flow were different origins. **A failure message is a
hypothesis from someone who cannot see your setup.**

## What actually broke the deadlock

The three prior attempts all assumed investigating this needed a real Google sign-in, so they
theorised instead. It didn't. Clicking the Google button writes the verifier **before** leaving for
Google — so the question "does storage survive login → callback" was answerable by clicking once,
navigating straight to the callback, and reading `localStorage` on each host:

| Origin | verifier after sign-in starts at `localhost:3000` |
|---|---|
| `http://localhost:3000/admin/auth/callback` | **PRESENT** |
| `http://127.0.0.1:3000/admin/auth/callback` | **ABSENT** — owner's error, word for word |

Two minutes. It killed the accepted remedy outright.

The Supabase auth log then corroborated it independently: the owner's two attempts, nine seconds
apart, one from each host.

## A near-miss worth recording

Checking whether `localhost:3000` was in Supabase's redirect allowlist, my first probe echoed the
origin back — which read as confirmation. Then I passed `https://evil.example.com` and it echoed
that back too: that endpoint defers validation, so the probe **could not fail**, and had therefore
told me nothing. A different endpoint answered properly (both real origins honoured, the bogus one
rewritten to the site URL).

I caught this one only because I ran the negative control. I have no reason to think I always
would.

## What shipped

- `lib/oauthOrigin.ts` — `canonicalLoopbackUrl`, `oauthOriginMismatch`, `verifierKeyFor`, plus one
  four-line `enforceCanonicalOrigin()`.
- The guard on the admin + sponsor **login** pages: a sign-in that can only start on `localhost`
  can only finish there.
- The two **callback** pages: replace Supabase's misdirecting text with a sentence naming the real
  cause (`errors.authOriginMismatch`, en/ms/ta).
- 19 tests, including both production hostnames — a guard that ever fired on `halatuju.xyz` would
  redirect live admins to their own laptop.

**Deliberately not guarded: the callbacks.** A sign-in that legitimately begins on `127.0.0.1` also
returns there and works; bouncing it would manufacture this exact bug. Normalise state where it is
created, not where it is consumed.

## Cost of the delay

Six sprints closed without a browser pass, N2/N3b/N4 explicitly citing this ticket. Three defects
in the last sprint alone were found by the owner reading screenshots, none by a test. The debt was
never in the auth code — it was in not having spent two minutes measuring.

## Follow-on

- **TD-188** (rail never felt by a person) is unblocked; it now needs ten minutes, not a fix.
- ms/ta for the new leaf are my drafts, not owner-reviewed — same standing caveat as TD-183.
