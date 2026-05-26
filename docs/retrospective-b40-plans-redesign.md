# Retrospective — B40 apply-form "Your Plans" redesign (P1–P5)

**Shipped:** 2026-05-27 (deployed to prod). **Branch:** `feature/plans-redesign` → `main` (`acdb2a4`).
**Releases:** `halatuju-api-00156`, `halatuju-web-00205`. **Version:** 2.2.0.

## What Was Built

A context-aware, progressive-disclosure rebuild of Step 4 ("Your Plans") of the B40 apply form. The old step was
a flat wall of controls (multi-select pathway chips, UPU radio, manual field dropdown, top-3 saved-courses picker,
other-scholarships) that the user flagged as generating no usable signal. The redesign:

- Opens with **one question** — *"Do you know which pathway you'll take?"* → **Decided / Still deciding**. Nothing
  else shows until answered.
- **Decided + SPM leaver:** eligible-only **pathway dropdown** (counts) → then, by pathway type:
  - programme pathways (poly/foundation/uni/community/PISMP/ILJTM/ILKBS) → **course picker** (eligible-only, field derived);
  - matriculation → eligible **track** → **college**;
  - STPM/Form 6 → **stream** → **school** (584 centres).
- **Decided + STPM student:** straight to an eligible **degree picker**.
- **Still deciding:** optional leanings + "where are you right now?" reason chips + free text (never blocks).

Delivered in 5 sub-sprints on a feature branch, shipped in **one migrate-first + deploy**. New components:
`PathwaySelect`, `ProgrammePicker`, `InstitutionPicker`. Reused the live eligibility engine read-only
(`/eligibility/check/`, `/calculate/pathways/`, `/stpm/eligibility/check/`) — **no new endpoint**. Migration `0010`
added 7 optional fields. Mentoring stays coordinator-set (reasons captured + surfaced, not auto-flagged).

## What Went Well

- **Incremental on a branch, atomic ship.** Each sub-sprint (P1 storage → P2 shell → P3 course → P4 institution →
  P5 STPM+uncertain) was independently built, tested, previewed, and committed, but nothing deployed until the
  feature was complete — prod never carried a half-built step.
- **Logic-in-lib discipline paid off.** All filtering/validation/mapping went into `lib/scholarship.ts` (node-env
  jest), so the suite grew 47 → 97 with real coverage while components stayed thin renderers.
- **Delete-as-you-replace** kept the file clean: the old chips/UPU/field/top-3 controls + their i18n keys were
  removed in the sprint that replaced them.
- **Eligibility reuse** meant zero new backend endpoints and the engine stayed the single source of truth.
- **Migrate-first worked exactly as intended** — additive migration applied + verified before the push; old code
  kept serving throughout; the deploy was a clean two-service rebuild.

## What Went Wrong

1. **Verification false alarm: checked the wrong table name.**
   - *What happened:* after the prod migrate, my verification query checked `scholarship_scholarshipapplication`
     (Django's default table name) and reported **0/7 columns** + "table does not exist" — a heart-stopping result
     mid-deploy.
   - *Root cause:* I assumed Django's default `<app>_<model>` table name. The models use custom `Meta.db_table`
     (`scholarship_applications`, `scholarship_cohorts`, `funding_needs`, …), so the real table has a different name.
   - *System fix:* added a lesson — when verifying a prod migration via raw SQL, **read the model's `Meta.db_table`
     first** (or verify through Django's ORM / `dbshell`), never assume default table names.

2. **`migrate` exited non-zero on a successful migration.**
   - *What happened:* `manage.py migrate` printed "Applying scholarship.0010… OK" but then errored
     `relation "django_content_type" does not exist` and returned exit code 1 — looking like a failed migration.
   - *Root cause:* the prod DB has **no `django_content_type` / auth tables** (the contenttypes/admin apps' tables
     were never created in this prod). Django's `post_migrate` signal (create_contenttypes / create_permissions)
     runs after the schema change and queries `django_content_type`, which fails. The additive `ADD COLUMN`s had
     already committed + recorded `0010`.
   - *System fix:* lesson — on this prod, a non-zero `migrate` exit from the `post_migrate` contenttypes step is
     **not** a migration failure; verify the actual schema change (columns + `django_migrations` row) directly.
     Logged TD-058 for the missing contenttypes/auth tables (latent risk for any future model-creating migration).

## Design Decisions

- **Eligible-only, progressive disclosure, derived destination** (logged in `decisions.md`, P2) — the step shows one
  decision at a time, only options the student's results qualify them for, and derives `upu_status` from the chosen
  public pathway instead of asking.
- **Mentoring stays coordinator-set.** The Uncertain branch captures `uncertainty_reasons` (surfaced on the admin
  detail) but does **not** auto-set `mentoring_candidate` — the coordinator decides. Honoured the model's existing
  "coordinator-set, not collected at intake" design; kept the ship frontend-only. Auto-flagging is a safe follow-up.
- **`field_of_study` left empty for pre-U pathways** (matric/STPM institution) — they haven't chosen a degree field
  yet; the track/stream is the signal. A coarse track→field map would be imprecise.

## Numbers

- 5 sub-sprints, 9 commits (incl. merge), one deploy (api + web).
- Tests: frontend jest **47 → 97** (+50); backend **1105** (P1's +2). i18n parity **1123 → 1156** keys (en/ms/ta).
- `/scholarship/apply` bundle ~36–37.5 kB through the redesign.
- Migration `0010`: 7 optional fields, applied migrate-first, 7/7 verified on prod.
