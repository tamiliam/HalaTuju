# Retrospective — TD-085 Sprint 2: Officer Documents-panel redesign (feature close)

**Date:** 2026-06-05 · **Migration:** none · **Status:** SHIPPED + DEPLOYED. **Completes TD-085.**
**Spec:** `docs/scholarship/consent-gate-v2-plan.md` (Documents-panel section).

## What was built
The officer cockpit Documents drawer was redesigned (Stitch-first; the existing S5 drawer was the approved layout base,
the redesign adds the colour coding):
- **`officerCockpit.documentFacts(doc)`** — the coloured fact-labels for a document: only the facts THAT document
  provides, each 🟢 verified / 🟡 partial / 🔴 not, read straight from the per-fact `*_check` serializer fields. The
  **relationship is movable** — it sits on a father/elder-sibling IC (shared student-IC patronymic), on the **birth
  certificate** for a mother, on the **guardianship letter** for a guardian; never on a mother's/guardian's IC.
- **`officerCockpit.incomeDocLayout(app, docs)`** — the income section's Required→Optional ordering, route + selection
  aware, with a slot (uploaded doc or `null` → placeholder) per compulsory document. Reuses `incomeWizard`
  (`workingMembers` / `relationshipDocFor`) — the same source the gate uses.
- **`documentPill` now rolls up the fact colours** (verified iff every assessable fact is verified; unread iff none can
  be assessed). This fixes the long-standing **"earner IC always shows Unread"** bug for free — the earner IC is judged
  by its income relationship check, not the student-identity verdict it never receives.
- Cockpit `[id]/page.tsx` renders the coloured fact-labels, the **Required / Optional** income split, and red **Missing**
  placeholder rows.
- `admin-api.ts` declares the `*_check` interfaces (imported from `api.ts`) + `household_member` + the income wizard
  fields; `AdminApplicationDetailSerializer` surfaces `income_route`/`income_earner`/`income_working_members`. No migration.

## What went well
- **The data was already there.** The admin detail serialises documents via `ApplicantDocumentSerializer`, which already
  returns every `*_check` field — so no new backend computation, just FE type declarations. The cockpit reads the same
  verdicts the student sees.
- **One source held across the feature.** `documentPill` derives from `documentFacts`; `incomeDocLayout` reuses
  `incomeWizard`; the gate reuses `income_requirements`. The panel, the student checklist, and the gate can't disagree.
- **Pure logic, fully unit-tested.** 35 `officerCockpit` jest cases (documentFacts per doc type, the pill roll-up, the
  income layout slots/placeholders); the rendering's type-safety was caught by `next build`.

## What went wrong
1. **`next build` failed: `AdminScholarshipDetail` had no income wizard fields.**
   - *What happened:* `incomeDocLayout(app, …)` needs `income_route`/`income_earner`/`income_working_members`, but neither
     the FE `AdminScholarshipDetail` type **nor** `AdminApplicationDetailSerializer` declared them — so the type didn't
     compile (and the data wouldn't have been there at runtime either).
   - *Why:* I assumed the admin detail exposed the same fields as the student application. It doesn't —
     `AdminApplicationDetailSerializer` is a **curated allowlist** (`Meta.fields`), so a model field is invisible to the
     cockpit until explicitly listed.
   - *System change (lesson):* when a cockpit/admin feature reads application fields, verify the **admin** serializer's
     `Meta.fields` exposes them — don't assume parity with the student serializer. The build caught it (lesson #127), but
     a serializer check up front would have saved the round-trip.
2. **Stitch timed out and dropped the fresh coloured mock** (the content-dense flakiness, lesson #72). Recovered by using
   the already-approved S5 drawer as the layout base and describing the single delta (the colour coding) for sign-off,
   rather than burning retries. *System change:* for a redesign of an existing screen, prefer "show the existing approved
   pattern + describe the delta" over regenerating the whole screen when Stitch is flaky.

## Design decisions
1. **The row badge is the roll-up of its fact colours** (`documentPill` ← `documentFacts`) — one definition, and it
   removes the earner-IC "Unread" bug as a side effect.
2. **The relationship is movable** (father/sibling IC · mother→BC · guardian→letter) — each document shows only what it
   can establish.
3. **The income panel renders `incomeDocLayout`** (route+selection-aware, reusing `incomeWizard`) rather than a flat doc
   list — compulsory on top with placeholders, optional at the bottom.
4. **Fact LABELS only, not values** — the coloured labels are the at-a-glance verdict; the actual values stay behind "View".

## Numbers (TD-085 feature total)
- **258 jest** · **697 scholarship + 1037 courses/reports pytest** = 1734 · i18n parity **2013** · no migration (S1 + S2).
- TD-085 shipped in: S1 (consent gate v2) + 3 live-testing fixes + S2 (cockpit) — all 2026-06-05, no migrations.

## Residual (own backlog, not TD-085)
- The PARKED post-consent **summary page + "lock at Continue"** (spec in the plan doc).
- Gopal income doc-coach copy; remove orphaned `str_claimed_no_doc`; TD-084 column/i18n cleanup.
- Legacy docs show grey/unread facts until re-read (the user's manual cockpit "Re-run"); a one-time re-extraction was
  deliberately dropped from TD-085.
