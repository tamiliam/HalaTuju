# Retrospective — v2.25.0 · Phase E Sprint E2b: anonymised pool frontend

**Date:** 2026-05-31
**Scope:** The frontend for the anonymised sponsor pool — completing Phase E2 end-to-end. Frontend only, no migration,
and (like E2a) it **deploys dark**: while `SPONSOR_POOL_ENABLED` is off the pool API 404s, so the UI degrades to the
pre-feature "coming soon" shell. The real browse experience appears only when the flag is flipped (post-lawyer).

## What Was Built

- **Sponsor browse:** `/sponsor` approved state fetches `getSponsorPool()` → an **anonymised cards grid** (alias ·
  state · field · academic band · funding categories), or the coming-soon shell on a 404/error. New
  `/sponsor/pool/[id]` detail page: the non-identifying summary + the generated **anonymous blurb** (`react-markdown`)
  + an "identities are protected" note.
- **Admin controls:** a teal "Anonymous profile (sponsor pool)" card on `/admin/scholarship/[id]` mirroring the
  Final-profile panel — Generate (AI) → preview `anon_markdown` → Publish / Unpublish + a "published to pool" badge,
  reviewer-gated.
- **Clients + i18n:** `getSponsorPool`/`getSponsorPoolDetail` (api.ts) + `generateAnonProfile`/`publishAnonProfile`
  (admin-api.ts; `anon_*` on `AdminSponsorProfile`); `sponsorPool.*` + `admin.scholarship.anonProfile.*` (en/ms/ta).

## What Went Well

- **The frontend degrades to the pre-feature state on the gated error, so the dark deploy is safe on both tiers.**
  The backend flag-off returns 404; the FE catches that and shows the existing "coming soon" shell rather than an
  error — so shipping E2b to prod with the flag off changes nothing a sponsor sees, exactly like E2a.
- **Mirroring paid off.** The admin anon-profile card is a near-copy of the existing Final-profile panel (same
  generate/publish handler shape, same `busy` state), and the browse grid reuses the standard card-grid idiom — so it
  was fast and consistent with no new layout risk (the user chose "mirror existing patterns" over a Stitch round-trip).
- **The safety guarantee stays in the backend test.** The FE only renders the allowlist payload, so the
  "no identifier leaks" property is proven once in `test_sponsor_pool.py` and the FE can't reintroduce it.

## What Went Wrong

1. **E2 (both tiers) ships without an interactive smoke.**
   - *Symptom:* the browse grid + admin generate/publish can't be exercised headless — they need the flag on, dummy
     data, and real sponsor/admin sessions.
   - *Root cause:* the same class as TD-070 — multi-screen stateful flows behind auth + a flag.
   - *System change:* the local smoke (flag on + seeded dummy data) is now **step 1 of the Next Sprint**, gating the
     flag flip; TD-065 + TD-070 extended. The dark deploy makes shipping safe regardless; the smoke gates *going live*.

## Design note

(Logged as an addendum to the E2a flag decision in `docs/decisions.md`.) A flag-gated backend pairs with a frontend
that **degrades to the pre-feature state on the gated error (404)**, so one env var keeps both tiers dark and flipping
it on lights up the whole feature at once.

## Numbers

- **Tests:** 1428 backend pytest (unchanged) · 183 jest (unchanged — pages are render-only) · `next build` clean
  (new `/sponsor/pool/[id]` route compiled, no rules-of-hooks errors). i18n parity 1675 × en/ms/ta (Tamil draft).
- **No migration.** 8 frontend files. Flag OFF — dark deploy.
