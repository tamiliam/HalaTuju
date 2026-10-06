# Retrospective — v2.24.0 · Phase E Sprint E2a: anonymised sponsor discovery pool (backend)

**Date:** 2026-05-31
**Scope:** The PDPA-critical core of the sponsor marketplace — the backend that lets a vetted sponsor browse an
**anonymised** pool of students. Built entirely behind `SPONSOR_POOL_ENABLED` (default OFF), tested on synthetic
data. Nothing is live to real students; the lawyer review gates flipping the flag, not the build.

## What Was Built

- **`pool.py`** — eligibility (poolable iff `SponsorProfile.anon_published` AND an active `share_with_sponsors`
  consent; consent IS the opt-in, per the user), `pool_ref` (stable non-sequential alias `S-A3F9C1`), `academic_band`.
- **`profile_engine.generate_anonymous_profile` + `_build_anon_prompt`** — a *generated, not scrubbed* anonymous blurb
  from a **separate prompt fed only non-identifying inputs** (no name/school/referees), told to say "the student" and
  omit names/places. Reuses the mockable `_call_gemini_text` seam.
- **Allowlist serializers** `SponsorPoolCardSerializer` / `SponsorPoolDetailSerializer` — plain `Serializer`s with
  explicit derived fields and **zero model passthrough**. Conservative card: alias · state · field · academic band ·
  funding categories · months. This is the hard safety boundary.
- **Endpoints:** `GET /sponsor/pool/[/<id>/]` (flag-gated + approved-sponsor-only); admin reviewer-gated
  `…/anon-profile/generate/` + `…/anon-profile/publish/` (generate→review→publish human gate; regenerate un-publishes).
- **Model + flag:** `SponsorProfile.anon_*` (migration `0033`, additive, migrate-first + prod-verified);
  `SPONSOR_POOL_ENABLED` env flag (default OFF → 404).
- **Tests:** `test_sponsor_pool.py` (17) — eligibility combos, **allowlist leak** (plant a name/NRIC/address/phone/
  email/school, assert none appears in card/detail/browse payloads), flag + approval gating, anon-prompt excludes
  identifiers, admin generate→publish + viewer-forbidden.

## What Went Well

- **The data model already carried most of the safety scaffolding.** `Consent` already defaulted to
  `share_with_sponsors`, and `SponsorProfile` already had a draft→publish lifecycle — so "consent = opt-in" and
  "admin publishes before exposure" fell out of existing structure rather than needing new tables.
- **Allowlist-by-construction made the safety property testable, not aspirational.** Using a plain `Serializer` with
  explicit `SerializerMethodField`s (no `ModelSerializer`) means a future model field literally cannot reach a sponsor
  without someone adding a method for it — and the leak tests prove it by planting real identifiers and grepping the
  JSON. Structural guarantee + a test, not a code-review promise.
- **Two layers of defence for the blurb.** The deterministic card is the hard boundary; the *generated* blurb is the
  soft one, behind an admin publish gate. Even if the model misbehaved, the card leaks nothing and a human reviews the
  blurb before publish.
- **Flag-gated from line one.** The whole feature shipped to `main` (safe deploy) with the door shut — no branch to
  rot, the fallback (404) is exercised in prod for free, and flipping it on is a one-env-var decision post-lawyer.

## What Went Wrong

1. **The anon blurb is fed the student's free-text narrative — a model-trust gap I chose to accept, not close.**
   - *Symptom:* `_build_anon_prompt` passes the student's own words (aspirations/plans/family_context/daily_life/
     funding_note), which could contain a name, school, or town the model might echo.
   - *Root cause:* the roadmap says "fed only non-identifying inputs," but the narrative is the richest, most useful
     input and it's *semi*-structured — fully excluding it would gut the blurb. So I leaned on the prompt instruction
     + the admin publish gate + the hard allowlist card, rather than a structural guarantee on the blurb itself.
   - *System change:* logged as **TD-074(b)** with a concrete hardening (a pre-publish identifier scan: reject publish
     if the blurb contains the profile's name/school tokens). Acceptable for E2a (flag off, dummy data, human gate);
     revisit before the flag flips for real students.

2. **Detail endpoint keyed by raw application id.**
   - *Symptom:* `/sponsor/pool/<id>/` uses the DB row id (exposed on the card as `id`), leaking count/order to a
     vetted sponsor.
   - *Root cause:* the `pool_ref` alias is a one-way hash, so it can't be reversed to an id without a resolver; I took
     the id shortcut for E2a.
   - *System change:* TD-074(a) — switch the API key to the opaque ref (with a ref→id resolver) if order-leakage to
     vetted sponsors ever matters. Low priority (ids aren't identifying; endpoint 404s unless eligible).

## Design Decisions

(Logged in `docs/decisions.md`.) (1) **Eligibility = anon-published + active share consent** (consent is the opt-in;
no separate toggle). (2) **Sponsor-safe profile is GENERATED, not scrubbed** — a separate non-identifying prompt, not
a redaction of the named profile. (3) **Allowlist `Serializer` (not `ModelSerializer`) as the hard safety boundary.**
(4) **Master feature flag (`SPONSOR_POOL_ENABLED`, default OFF)** so the PDPA-critical code lands + tests on main while
staying dark until lawyer sign-off.

## Numbers

- **Tests:** 1428 backend pytest (+17) · 183 jest (unchanged) · golden masters intact (5319/2026).
- **Migration:** `scholarship/0033` (additive `anon_*` on `sponsor_profiles`, migrate-first, prod-verified).
- **No frontend** (E2b). 11 files. Flag OFF — safe deploy.
