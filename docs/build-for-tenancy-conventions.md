# Build-for-Tenancy Conventions

**Effective 2026-07-15 — applies to ALL ongoing BrightPath/HalaTuju work, every sprint, every agent.**

HalaTuju is becoming a multi-tenant platform (plan of record: `docs/plans/2026-07-14-platform-roadmap-draft.md`). The platform work itself is phased and gated — but from today, **no new work may deepen the platform↔tenant coupling** the tenancy audit inventoried. These conventions cost nothing now and save a migration later. They are checked at code review.

## The rules

1. **New tunable numbers go on `ScholarshipCohort`, never as module constants.**
   Any new threshold, ceiling, delay, cadence, or amount that a different programme could plausibly want different → a cohort field (with today's value as default). Statutory/national constants (EPF rates, SPM grade vocabulary, STR portal wording) stay in code.
   *Anti-pattern this prevents:* `_HEADROOM_THIN_RM = 1584.0` — a hard-coded duplicate of a cohort field (`income_engine.py:1274`).

2. **No new hard-coded programme identity.**
   "BrightPath", "Cikgu Gopal", team sign-offs, support addresses, `halatuju.xyz` URLs — never as new string literals. In backend emails, use/extend the existing sign-off and alias helpers (`emails.py:16-20`); in the web app, new i18n strings that mention the programme use a `{programmeName}` interpolation variable, not the name in the string value.

3. **New admin endpoints go through the central `_AdminBase` gates.**
   Never a fresh `ScholarshipApplication.objects...` query in a new view — inherit `_AdminBase` and read through `_scoped_application` / the shared scope helpers. (These gates are where the org fence will be inserted; a query outside them is a future data leak.)

4. **New models that belong to the programme must be reachable from `ScholarshipApplication` or `ScholarshipCohort` by FK.**
   The future owning-organisation scope will flow through those two roots. A free-floating scholarship model with no FK path to a root cannot be fenced.

5. **New document types extend `ApplicantDocument.DOC_TYPES`** (the master catalogue) — never a parallel enum or an ad-hoc doc store. New storage writes go through `scholarship/storage.py` helpers, never a hand-built bucket path.

6. **New billable calls (AI, SMS, email) go through the existing seams** — `vision.py` / `profile_engine.py` / `contracts.py` `_gemini_generate` for Gemini, the `emails.py` `_send*` helpers, `whatsapp.py` for Twilio — never a fresh client instantiation elsewhere. (The per-tenant usage meter will wrap those seams; a stray call site escapes metering.)
   *Sanctioned Gemini seams, in full:* `vision._call_gemini_json` (structured document reads), `profile_engine._call_gemini_text` (prose), and `contracts._gemini_generate` (contract-quiz generation). The third was added to this list on 2026-07-23 — it was already the single mockable call site for its feature, so this records the fact rather than changing anything.

7. **Referrer ≠ owner.** `PartnerAdmin.org` / `referred_by_org` mean *the organisation that referred* a student — an attribution marker, not a security boundary. Never use them for access control. The future tenant boundary is a separate `owning_organisation` concept (roadmap Sprint 1); don't name anything new plain `org`.

8. **Engine logic stays programme-agnostic.** New verification logic (genuineness, income, verdict) must not read programme identity to branch behaviour ("if BrightPath then…"). It reads inputs and cohort config only — the "shared engine, org-selectable" promise.

## Review checklist (add to every sprint's review)

- [ ] No new module-level tunable constants that belong on the cohort
- [ ] No new "BrightPath"/persona/support-address/URL literals (backend or i18n values)
- [ ] No admin query outside the `_AdminBase` gates
- [ ] New scholarship models FK-reachable from an application or cohort
- [ ] No storage/billable call outside the existing seams
- [ ] No access control keyed on referral fields
