# Retrospective — Role-Aware Guide & FAQ Manual

**Date:** 2026-07-16
**Brief:** `docs/plans/2026-07-16-guide-faq-manual-brief.md`
**Authority:** `docs/scholarship/role-matrix.md` + owner-approved Stitch mock.
**Shape:** One sprint, **frontend + content only** (no backend, no migration), one deploy.
**Tests:** 552 jest (+22 new) · `next build` clean · 2565 scholarship pytest (backend untouched — run per house rule).

## What shipped

The reviewer-only Guide and FAQ became **one role-aware self-help manual**. Both pages were
hard-coded English JSX shown to every role, so a QC or org admin read statements that were wrong
for them ("you'll see only the applicants assigned to you"). Now:

- **Content moved into modules** — `halatuju-web/src/content/manual/`: `types.ts`, `index.ts`
  (registry + pure helpers), four Basics chapters (programme, four checks, statuses,
  confidentiality), four role chapters (reviewer, qc, org-admin, general-admin), a help chapter,
  and `faq.tsx` (audience-grouped Q&As). Each chapter is a typed `ManualChapter` with stable
  section anchors — the shape makes a future `ms`/`ta` sibling per chapter trivial. English only
  for now (the existing quiet convention; **Tamil is the owner's authority — not machine-translated**).
- **Guide** (`/admin/guide`) rebuilt to the Stitch layout: sticky sidebar (Basics / Your role /
  Help), **role-aware landing** (opens on the caller's own role chapter), breadcrumb, role badge
  (reusing the Administration palette), numbered step cards, prev/next, and **stable deep-link
  anchors** (`/admin/guide#org-admin-assigning`). A hidden chapter is absent from the sidebar and
  a direct anchor to it falls back to the visitor's default chapter (never an error).
- **Access by need (UX, not security):** reviewer/qc/admin see Basics + their own chapter + Help;
  **org_admin and super see all four role chapters** (they manage those people).
- **FAQ** (`/admin/faq`) regrouped into audiences (Everyone / Reviewer / QC / Org admin / General
  admin), default filter = the caller's role (Everyone always shown), with a **"For me / All roles"**
  toggle for org_admin/super. Every existing reviewer Q&A is re-homed, not rewritten; new QC,
  org-admin and general-admin Q&As added.
- **Content traces to the matrix** — every capability claim derives from `role-matrix.md` and the
  live UI. A currency-rule note was added to the matrix pointing at the manual.
- **Screenshots**: reused the eight accurate `/reviewer-guide/` images; the five new org-admin/QC
  images are labelled placeholders (`ManualImage` degrades gracefully) with a capture manifest
  (`docs/plans/2026-07-16-manual-screenshot-manifest.md`).

## Content corrections caught (currency wins)

- The old reviewer guide/FAQ said Save "sends the final profile to sponsors" — but since the QC
  gate (2026-07-02), publishing is bound to **QC-Accept**, not the reviewer's save. The reviewer
  chapter + FAQ now say Save sends the case **on for QC**; the student becomes sponsor-visible only
  when QC accepts.
- Reviewer sponsor-vetting references removed (that power moved to the org admin, 2026-07-15).

## What went well

- **Pure helpers made the role→content contract testable** without rendering: `visibleChapters`,
  `defaultChapterSlug`, `resolveTarget`, `manualRole`, `defaultFaqAudiences`/`canSeeAllFaq` — 22
  jest tests cover visibility per role, landing, deep-link fallback, anchor uniqueness, and FAQ
  filtering.
- **No i18n churn / no backend** — chrome is English literals (matching the existing pages), so the
  i18n guard tests were untouched and there was zero migration/gate risk.
- **Graceful placeholders** — a missing `/manual/*.png` shows a labelled box, so the owner can drop
  real files in later with no code change.

## Lessons

- **Documentation drifts silently.** Two factual errors (publish-at-QC, moved sponsor-vetting) had
  been live in the guide for weeks because prose isn't gate-tested. The new **currency rule** (matrix
  change ⇒ chapter + FAQ change in the same commit) is the guardrail; the manual now traces to the
  matrix by construction.

## Rollout / carry

- **elanjelian@me.com STAYS org_admin** until the screenshot pass (it's the only account that can
  show the org-admin surfaces); the owner reverts it to `reviewer` afterwards.
- Owner screenshot pass per the manifest → PNGs into `/public/manual/` → docs-only follow-up commit
  (rides the next push).
- Follow-up content passes: `ms`/`ta` chapter siblings (owner-authored Tamil).
