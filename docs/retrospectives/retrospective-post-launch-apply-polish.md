# Retrospective — Post-launch apply-flow polish + truthfulness declaration (v2.2.1–2.3.0, 2026-05-27)

Sprint scope: the run of post-launch fixes and additions made after the B40 "Your Plans" redesign
(v2.2.0) went live, surfaced by live new-user testing — plus the truthfulness declaration. Commits
`aa074e3`→`9b8a77b`.

## What Was Built

- **2.2.1** — `/eligibility/check/` accepts an explicit `coq_score: null` (strips nulls in `to_internal_value`),
  unblocking the decided-pathway dropdown that was empty for 100% of profiles.
- **2.2.2** — persist `coq_score` to the profile (collected at onboarding but never synced; null for every row).
- **2.2.3** — `coq` round-trips to the edit form (auth-context cache merged, not overwritten; maps
  `coq_score → coqScore`); 584 STPM centre names canonicalised to the MOE secondary list by code; "Public
  University degree" → "Public university".
- **2.2.4** (critical) — STPM eligibility returned 0 degrees for **every** STPM student; fixed by normalising
  demographics in the STPM view; scholarship list replaced (JPA/Khazanah/PETRONAS/…); "Anything to add" box shown
  on the decided branch too.
- **2.2.5** — STPM "still deciding" students rank their **top 3 degrees** (3 ranked pickers, dedupe, `top_choices`);
  SPM leaning pills show all 9 pathways incl. **PISMP**.
- **2.2.6** — stop Chrome's saved-address autofill covering the course/institution comboboxes
  (`autoComplete="new-password"` + password-manager ignore attrs).
- **2.2.7** — NRIC pre-fills the apply form for new users; clearer "no results yet" prompt naming the Results step;
  `/scholarship/application` wrapped in the real `AppHeader`/`AppFooter` with the comms-email note + onward CTAs.
- **2.3.0** — truthfulness **declaration** + required typed-name **signature** before submit; new
  `declaration_name` + `declared_at` audit fields (migration `scholarship 0011`, applied migrate-first).

## What Went Well

- **Live diagnosis discipline.** Four distinct prod bugs were diagnosed against the live Supabase DB + by replaying
  the real endpoints, always pulling DB creds via `gcloud run services describe` and keeping passwords out of the
  transcript. Each fix was verified live by grepping the served bundle / replaying the endpoint (e.g. STPM 0 → 601).
- **Migrate-first via the Supabase MCP.** `scholarship 0011` was applied by replicating Django's DDL through
  `execute_sql` and recording the `django_migrations` row in the same connection, then verifying both — cleaner than
  `manage.py migrate` here and it sidesteps TD-058's non-zero `post_migrate` exit and the credential juggling.
- **Visual gate before every deploy.** Auth-gated UI (the top-3 picker, the declaration block, the rebuilt
  application page) was rendered via throwaway preview routes + Playwright and confirmed before pushing, then the
  preview deleted — no orphans left.
- **Static gates held.** `next build` + jest + `check-i18n` parity + (for 2.3.0) the full backend suite ran green
  before each push; deploys stayed at one per change.

## What Went Wrong

1. **Empty pathway dropdown for 100% of profiles (2.2.1).**
   - *Symptom:* the decided-pathway dropdown was always empty on the live apply form.
   - *Root cause:* the apply page POSTed the full profile, including `coq_score: null`; the eligibility serializer
     tolerated the field being **omitted** but rejected it being **explicitly null** (400), which the page swallowed
     into an empty list. The null-vs-absent distinction wasn't considered when the field was made optional.
   - *System change:* `to_internal_value` now strips nulls so optional fields fall back to defaults; lesson added —
     "a nullable optional field sent as explicit `null` can 400 a serializer that only tolerates omission."

2. **`coq` took three commits (2.2.1 → 2.2.3) to fully fix.**
   - *Symptom:* after unblocking the 400 and then persisting `coq`, the edit form still read `0`.
   - *Root cause:* each fix addressed one segment of the pipeline (serializer → sync payload → cache round-trip) in
     isolation; the whole path (onboarding → sync → DB → GET → auth-context cache → form) wasn't traced up front, so
     each fix only revealed the next gap. This is exactly the failure the existing "trace the full pipeline at a
     boundary bug" lesson warns about — it recurred because the bug spanned **two repos** (web cache + api) and the
     cache-overwrite segment wasn't on the obvious path.
   - *System change:* reinforced the existing lesson; no new lesson (already captured).

3. **STPM degree picker empty for ALL STPM students (2.2.4, critical, pre-existing).**
   - *Symptom:* 0 eligible degrees for every STPM student; the redesign surfaced it.
   - *Root cause:* `StpmEligibilityCheckView` passed **raw** profile demographics (`male`/`malaysian`) to an engine
     that compares the Malay canonical forms (`Lelaki`/`Warganegara`). The SPM serializer normalised; the STPM view
     never did. Normalisation lived in one entry point, not at the engine boundary, so a second caller bypassed it.
   - *System change:* extracted shared `normalize_gender`/`normalize_nationality`, now used by both paths; lesson
     added — "normalise demographics at every engine entry point, not just the one that happened to do it."

4. **NRIC didn't pre-fill for new users (2.2.7).**
   - *Symptom:* the NRIC box was blank on the apply form even though the student gave it at sign-up (and it was in
     the DB).
   - *Root cause:* the one-time prefill effect set its "done" ref on the **first** `profile` snapshot. For a
     brand-new user that snapshot has no NRIC (it's claimed at the gate moments after mount); when the NRIC arrived,
     the prefill was already locked and skipped. "profile exists" was treated as "profile is ready", which isn't true
     during the gate.
   - *System change:* the prefill now waits for the awaited field (`profile.nric`) before seeding/locking; lesson
     added.

5. **Chrome autofill covered the course list (2.2.6).**
   - *Symptom:* Chrome's saved-address dropdown (postcodes/localities) rendered over the course combobox.
   - *Root cause:* the inputs already set `autoComplete="off"`, but Chrome **ignores `off`** for fields it
     heuristically classifies as address/contact.
   - *System change:* switched custom comboboxes to `autoComplete="new-password"` (+ `data-1p-ignore`/`data-lpignore`);
     lesson added.

## Design Decisions

- **Truthfulness signature as a soft attestation, not an identity gate** — see `docs/decisions.md`
  ("Typed-name signature is a soft attestation…, 2026-05-27").

## Numbers

- 8 versioned releases (v2.2.1 → v2.3.0); 1 additive migration (`scholarship 0011`, migrate-first).
- Tests: **1110 backend pytest** + **102 frontend jest**, 0 failures. SPM golden master 5319 / STPM 2026 intact.
- i18n parity: **1171 keys** × 3 locales.
- Deploys: web-only for 2.2.5/2.2.6/2.2.7; both services for 2.3.0. One deploy per change; all verified live.
