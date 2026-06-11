# Retrospective — Guided school capture + officer-cockpit refinements (#1–#7)

**Shipped:** 2026-06-12 · branch `feature/cockpit-school-ux` → `main` · **no migration** · frontend + i18n only.

## Objective
Seven small clarity/UX fixes from the owner's live review of HalaTuju — two about capturing the student's **school** in a
guided way, five polishing the **officer scholarship cockpit**. Executed in an isolated git worktree because another agent
is active in the repo (the parked `feature/family-section-redesign`).

## What shipped
| # | Change | File(s) |
|---|--------|---------|
| #1 | Guided **optional** school field in the normal onboarding (reuse `SchoolSelect` + MOE list); synced only when non-empty | `app/onboarding/profile/page.tsx` |
| #3 | Editable guided school in the profile, above Angka Giliran | `app/profile/page.tsx` |
| #2 | Cockpit status pill → the **real** status (10 `admin.scholarship.statuses.*`), colour-banded | `admin/scholarship/[id]/page.tsx` |
| #4 | Cockpit header "**Applied**" milestone (when `profile_completed_at` set) | `admin/scholarship/[id]/page.tsx` |
| #5 | "Parent/Guardian" → **dynamic** "Parent" or "Guardian" from the consent relationship | `admin/scholarship/[id]/page.tsx`, `admin-api.ts` |
| #6 | Hide the legacy `siblings_studying_count` row; captioned fallback only for old unsplit rows | `admin/scholarship/[id]/page.tsx`, `ScholarshipReview.tsx` |
| #7 | Cockpit prev/next applicant navigation following the list's current filter order | `admin/scholarship/page.tsx`, `admin/scholarship/[id]/page.tsx` |

## Decisions
- **#5 needed no backend change** — `ConsentSerializer` already exposes `guardian_relationship`; only the `admin-api.ts`
  type was missing it. The relationship signal is the active consent's `granted_by=='guardian'` + a non-parent
  `guardian_relationship`; `father`/`mother`/adult-self → "Parent".
- **#6 deliberately minimal (owner chose option a).** The legacy field is no longer collected (the Story form captures
  the school/tertiary split). Rather than a data migration, the cockpit/review simply prefer the split and fall the legacy
  count back **only** when the split is null and the count is positive — captioned "confirm at interview". A prod `SELECT`
  sized this at **10 of 76** applications. The parked family-redesign branch will later supersede the family card entirely,
  so this stays a 2-surface display tweak.
- **#7 uses `sessionStorage`, not a new endpoint.** The list page stashes the ordered id list for the current filters; the
  detail page reads it and computes prev/next. A direct link (id not in the list) simply hides the controls. No backend.

## Gates
`next build` clean · 297 jest (render-only — no new unit coverage) · i18n parity **2519×3** (en/ms/ta; Tamil first-draft).

## Lessons / carried notes
- **Cockpit page is a shared hotspot** with the parked family-redesign branch — worktree isolation kept them apart;
  expect a trivial merge reconcile there later (esp. the family card + sibling rows).
- **Tamil is first-draft** on all new keys (school/optional, the 10 statuses, applied, parent/guardian labels, the legacy
  caption) — worth the owner's eye before it's user-facing.
