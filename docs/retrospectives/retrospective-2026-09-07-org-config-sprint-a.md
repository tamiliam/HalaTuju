# Retrospective — Org Config Sprint A: the Configuration tab (2026-09-07)

## What was asked

Owner, 2026-09-06: the sponsor page removes an awarded student's card after 2 days; extend it to
30 — but NOT by hard-coding it. Make it a configurable value under Organisation → Settings →
Configuration (a new tab; only Colours existed), and make that tab the home for organisation-wide
values that are hard-coded today. The owner approved the PHASED roadmap
(`docs/plans/2026-09-06-org-configuration-roadmap.md`): Sprint A ships the engine, the tab, and
the funded-card window; Sprints B–F migrate the other groups one at a time.

## What shipped

- **`courses/org_config.py`** — registry + storage fence + read seam. Blank = platform default,
  read live from Django settings. The fence runs in `OrganisationConfiguration.save()` (the
  `OrganisationTheme` precedent), so a shell caller cannot store junk.
- **`OrganisationConfiguration`** (migration `courses/0074`, one additive table, RLS + one
  service_role policy, migrate-first). One row per organisation; `values` holds ONLY changed keys.
- **`pool._funded_grace_window()`** — the funded-card window, per organisation, with the platform
  default (48h = 2 days) for everyone who never chose.
- **`AdminOrganisationConfigurationView`** — GET/PUT, org derived, cross-org 404, org_admin +
  super, all-or-nothing PUT, `AUDIT org_config_set` per changed key. A **mirror** of the theme
  view's fence, not a subclass (inheritance would drag DELETE onto this route).
- **The second tab** on Organisation → Settings (`OrganisationConfigurationTab`), i18n en/ms/ta.

## Decisions

1. **A setting appears on the tab only when code reads it.** `sponsor_email_max_cards` was planned
   for Sprint A and DEFERRED in-sprint: its two email-render sites carry no organisation, and a
   row shown before it is wired is the "UI asserts what nothing checks" defect. Recorded in the
   roadmap with the reason.
2. **The registry speaks the owner's unit (days), the platform's env var stays in hours.** The
   default converts (48h → 2.0) at read time; nothing was renamed and no env var moved.
3. **Store the diff, never a snapshot of the defaults.** A copied default is right on the day it
   is written and wrong the day the platform default moves — the backfill-without-a-write-path
   rot, applied to configuration.

## Lessons

- **⚠ `~Q(col__in=…)` silently drops NULL rows.** SQL's `NOT (col IN …)` is NULL-false. The
  default arm of the per-org window is spelled `~Q(in) | Q(isnull)` and
  `test_a_null_org_application_follows_the_default_and_never_vanishes` pins it. Any future
  per-org queryset split must copy that spelling — applications with a NULL
  `owning_organisation` still exist (the NOT-NULL tightening is an open TD).
- **An application's `owning_organisation` copies from the COHORT's own `owning_organisation`
  FK, not from `programme.organisation`.** Three tests failed on fixtures that wired only the
  programme. When a fixture needs an org on an application, set it on the cohort.
- **The test DB is seeded** (migration 0119 creates a BrightPath tenant), so a super's
  organisation list is asserted as a SUBSET, never equality.

## Gates

+24 pytest (`test_org_config.py`) · full backend suite green · jest 1709 → 1722 (13 rendered
tests on the tab) · `next lint` 0 errors · i18n 4746 → 4763 × 3 · `next build` clean ·
`makemigrations --check` clean. Per-org filter bite-checked: disabled → exactly the two tests
that own the claim fail, then restored by writing the original line back.

## Carried

- ms/ta strings for `admin.orgSettings.config.*` are my first drafts — owner's eye owed.
- Sprint B next (roadmap): `sponsor_email_max_cards` (thread the org through the sponsor email
  senders) + the student-comms group.
- Design of record: Stitch failed twice on 2026-09-06 (both generations timed out, no screen
  ever listed); the owner approved the described layout in-thread and said "start sprint a".
  The built tab mirrors the Colours tab's established shell instead — same rule as the A2
  colours mock fallback.
