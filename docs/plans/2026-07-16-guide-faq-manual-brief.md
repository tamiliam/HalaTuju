# Implementation Brief — Role-Aware Guide & FAQ Manual

**For:** the implementing agent (Opus 4.8), in `c:\Users\tamil\Python\Production\HalaTuju`
**Shape:** ONE sprint, frontend + content only (NO backend changes, NO migrations), one deploy.
**Authority:** `docs/scholarship/role-matrix.md` (all capability facts) + the owner-APPROVED Stitch manual mock (`stitch.withgoogle.com/preview/10844973747787673276?node-id=66df4c111877470bb80fee82ea8d4dd8` — sidebar layout, role-badged chapter, step cards, no-conflict banner; the imagery inside its screenshot boxes is Stitch-invented — build neutral placeholders instead) + the existing reviewer guide's voice.

## Context

The Guide (`app/admin/guide/page.tsx`, ~12 illustrated steps) and FAQ (`app/admin/faq/page.tsx`, ~20 Q&As) are excellent but reviewer-only and hard-coded English JSX — yet every role (reviewer/qc/admin/org_admin) sees them, so a QC or org admin reads statements that are wrong for their role ("you'll see only the applicants assigned to you"). The role matrix is now LIVE (org-admin powers v1 + alignment, shipped 2026-07-15), so all four roles' real behaviour is stable and documentable. This sprint turns the two pages into ONE role-aware self-help manual: shared basics + a chapter per role + a role-filtered FAQ, with need-based navigation.

## Architecture

1. **Content modules, not one giant page.** Move content into `src/content/manual/` — one module per chapter (`basics-programme.tsx`, `basics-four-checks.tsx`, `basics-statuses.tsx`, `basics-confidentiality.tsx`, `role-reviewer.tsx`, `role-qc.tsx`, `role-org-admin.tsx`, `role-admin-general.tsx`, `faq.tsx`), each exporting a typed chapter object (`{ slug, titleKey|title, minRole/audience, sections: [{ anchor, title, body, img?, alt? }] }`). English content now; the module shape must make a future `ms`/`ta` sibling per chapter trivial (per-locale module resolution with EN fallback). Do NOT machine-translate Tamil — the owner is the Tamil authority; ship EN with the existing quiet convention (the current pages are EN-only too).
2. **Guide page** rebuilds to the approved Stitch layout: sticky left sidebar ("Basics" group / "Your role" group / "Help" group), role-aware landing (open on the caller's own role chapter, from `useAdminAuth().role`), breadcrumb, role badge on role chapters (reuse the `roleBadge` colour map), numbered step cards matching the existing guide's card style, prev/next footer, and **stable anchors** (`/admin/guide#org-admin-assigning` style) so emails/queries can deep-link.
3. **Access based on need (UX, not security — content only):** reviewer/qc/admin see Basics + THEIR chapter + Help; **org_admin sees all four role chapters** (they manage those people); super sees everything. A hidden chapter is absent from the sidebar AND direct-anchor lands on the visitor's default chapter (no error).
4. **FAQ page:** keep the native `<details>` accordion; regroup into audience sections (Everyone / Reviewer / QC / Org admin / General admin); default filter = caller's role with an "All" chip for org_admin/super; existing reviewer Q&As are re-homed, not rewritten.

## Content requirements (the bulk of the work — write in the existing guide's warm, plain voice; British English)

Every capability statement MUST derive from `docs/scholarship/role-matrix.md` and the live UI — no invented behaviour. Chapter outlines:

- **Basics** (extract + generalise from the existing reviewer guide): the programme picture; the four checks + colour code (currently step 3); statuses glossary (lift from the FAQ answer); confidentiality/PDPA + contact.
- **Reviewer** (mostly exists): profile setup, your assigned applicants, working a case, queries, interview scheduling + stage, your decision. Remove sponsor-vetting references if any linger (that power moved).
- **QC**: what QC is (the second pair of eyes); the awaiting-QC queue; Accept vs Reopen and what each does; the gap floor; **the no-conflict rule** ("you cannot QC a case whose verdict you recorded — and you now CAN review cases, so this matters"); their new review-all powers and when to step in as overflow reviewer.
- **Org admin** (the flagship new chapter): running your programme — your team (invite reviewer/view-only admin/QC; resend; revoke; the last-admin rule), assigning applicants (the list column + control), acting on cases (the three boxes) and QC with the conflict guard, sponsor vetting (approve/reject/suspend and what it means), the Administration panel tour, billing coming soon, and **what stays with the platform** (reopen, award amounts, countersign, adding organisations) — say it plainly so expectations are set.
- **General admin**: the view-only remit — what you can see (everything in your organisation, read-only, incl. the Administration staff list) and why action buttons don't appear for you.
- **FAQ additions** (per audience): org admin — "Why can't I revoke my other admin?", "Why was my QC refused on a case I reviewed?", "Can I add another organisation admin?" (no — the platform does), "What will Billing & usage show?"; QC — "Can I review now, not just QC?", "Why can't I QC this particular case?"; General admin — "Why can't I click anything?". Keep every existing reviewer Q&A.

## Screenshots

Reuse the existing `/public/reviewer-guide/` images where still accurate. New chapters ship with the Stitch-style placeholder blocks + descriptive alt text + a **screenshot manifest** (`docs/plans/<date>-manual-screenshot-manifest.md`: page, state, which account role, crop hints) for an owner-assisted capture pass — the owner's `elanjelian@me.com` org_admin test account STAYS an org_admin until that pass is done (revert to reviewer afterwards is an owner action). Screenshots must show demo/anonymised data only (standing PII rule).

## Code & tests

- Files: `guide/page.tsx` + `faq/page.tsx` rebuilds, `src/content/manual/*` modules, small sidebar/chapter components (local to the guide), no new deps. ~15–20 files.
- Jest: chapter visibility per role (reviewer cannot see the org-admin chapter in the sidebar; org_admin sees all; default landing per role); anchor integrity (every sidebar link resolves to a rendered section); FAQ filter behaviour. If any new `t()` keys are introduced for chrome (sidebar labels etc.), they go in all three locales and under the guarded namespace pattern.
- Existing i18n guard tests must stay green; `next build` + full jest before commit; pytest untouched (no backend changes) — run it anyway before push (house rule).

## Rollout

1. Push (one deploy) → verify build by SHORT_SHA → smoke: each role lands on its own chapter (owner has accounts to check reviewer/org_admin/super; General admin via any `admin` account).
2. Owner screenshot pass per the manifest → images dropped into `/public/manual/` → follow-up docs-only commit fills the placeholders (rides the next push, no dedicated deploy).
3. THEN owner reverts `elanjelian@me.com` → reviewer.
4. Sprint close: CHANGELOG, retro, `role-matrix.md` gains a line pointing at the manual as the user-facing rendering of the matrix, currency rule now covers ALL chapters (any role-power change updates its chapter + FAQ in the same change), memory update.

## Sizing & risks

Content-dominant sprint (~15–20 files, one deploy). Risks: (1) capability drift between prose and reality — mitigated: every claim traces to the role matrix, and the currency rule; (2) writing beyond the matrix (inventing behaviour) — the agent must check the live gate code when unsure, not guess; (3) the trilingual gap widening — accepted consciously: EN-first modules shaped for per-locale siblings; ms/ta scheduled as follow-up content passes.
