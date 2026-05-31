# Retrospective — v2.25.1 · Anon-profile pre-publish identifier scan (TD-074b)

**Date:** 2026-06-01
**Scope:** A focused safety hardening closing TD-074b — the one soft surface in the anonymised pool. Backend only,
no migration, no frontend.

## What Was Built

- `pool.scan_anon_for_identifiers(text, profile)` — scans a generated anonymous blurb for the student's **own**
  identifying tokens: name + school distinctive tokens (generic school words SMK/Sekolah/Menengah/… and name
  connectors bin/binti/a-l/… stoplisted to limit false positives), city, NRIC, phone, email. Returns the leaked
  fields; empty = clean.
- `AdminPublishAnonProfileView` runs the scan on publish and **refuses** (`400 anon_identifier_leak` + `fields`) when
  anything is found; the profile stays unpublished, the admin must regenerate.
- 7 tests (scan catches each planted identifier; clean passes; publish blocked + stays unpublished).

## What Went Well

- **Turned a model-trust gap into a structural gate cheaply.** The blurb now has three layers — prompt forbids →
  admin reviews → system blocks publish on a detected leak — and the hard allowlist card is unchanged. This was the
  TD-074b plan from the E2a retro, executed as-is.
- **Erring toward blocking was the right default.** For an anonymity gate, a false positive (over-block) is a minor
  admin annoyance; a false negative (a leaked name reaching a sponsor) is the actual harm. The stoplists trim the
  worst false positives without weakening the catch.

## What Went Wrong

- Nothing notable. The one judgement call is the **stoplist** (generic school words / name connectors): too aggressive
  and a real leak slips; too lax and legitimate blurbs are blocked. Kept it small and documented; if real use shows
  either failure mode, tune the lists (and the scan errs toward blocking, so the safe direction is the default).

## Lesson

(Added to `docs/lessons.md`.) When an LLM generates text that will be shown to an outside party who must NOT learn
identifying facts, add a deterministic **pre-publish scan for the subject's own identifying tokens** as a structural
gate — prompt-instruction + human review are necessary but not sufficient. Err toward blocking.

## Numbers

- **Tests:** 1435 backend pytest (+7) · 183 jest (unchanged) · golden masters intact. Backend only, no migration.
