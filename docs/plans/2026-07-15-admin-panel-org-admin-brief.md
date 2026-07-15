# Implementation Plan — Administration Panel + Surface Partition + `org_admin` role

**For:** the implementing agent (Opus 4.8), in `c:\Users\tamil\Python\Production\HalaTuju`
**Structure (owner decision):** TWO sprints (A = backend, B = frontend), each fully tested + committed; **ONE push after B** (push = deploy), then smoke + rollout. Owner decisions settled — do not reopen: the new org-superadmin role **includes QC powers** (documented small-team compromise); Stitch v2 design approved (cPanel icon grid, two sections).

## Context

BrightPath's promoter (Suresh, currently QC) is taking over day-to-day staff management. The current "Invite" page is a super-only grab-bag, and — critical finding — the frontend nav already hides platform pages from org roles, but the **backend does not**: a `role=admin` account can fetch the platform-wide student directory, dashboard stats, and course data by direct API call (`get_partner_students` grants `admin` ALL students). This sprint pair: (1) partitions the platform surface backend-side, (2) introduces the **`org_admin`** role (organisation superadmin: org-wide read + QC + staff management), (3) rebuilds Invite as a two-section **Administration** panel per the approved Stitch v2 (platform section: invite referral partner + add tenant; org section: invite reviewers/admins + disabled "Billing & usage — coming soon"), and (4) ends with Suresh promoted to BrightPath org superadmin. Design/role rationale is in memory `halatuju_org_roles_billing.md`; the platform plan of record is `docs/plans/2026-07-14-platform-roadmap-draft.md` (this work = the agreed gate-split pull-forward of Sprint-12/10 slices).

## Ground rules

1. Follow `Settings/_workflows/sprint-start.md`/`sprint-close.md`; full pytest (3,713+, ~6½ min) green before each commit; jest + `next build` green for Sprint B. Never two heavy suites at once (8GB).
2. Follow `docs/build-for-tenancy-conventions.md`. Access control NEVER keys off `PartnerAdmin.org`/`referred_by_org` (referral semantics). "Super" vocabulary = platform only; Suresh-facing label is **"Organisation admin"**.
3. The org-fence CI guards are live and WILL fail your build until satisfied (see §A7).
4. Migration numbering: next is `courses/0064` (courses at 0063, scholarship at 0100). The role addition is **choices-only (no DDL)** — precedent: courses/0060. Migrate-first therefore = record the `django_migrations` row via Supabase MCP before push (house pattern; runbook style of `docs/plans/2026-07-15-sprint1-migrate-first.md`, DDL section empty).
5. British English UI text; i18n en/ms/ta (Tamil per the style guide; follow existing `admin.*` translations for register).
6. After push: match Cloud Build by YOUR SHORT_SHA (`gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com`).

---

## Sprint A — backend: `org_admin` role + surface partition + panel endpoints

### A1. New role value
- `apps/courses/models.py:471-477` add `('org_admin', 'Organisation admin')` to `ROLE_CHOICES`; update the role doc-comment block (:457-470): org-wide read + QC gate + staff management for their own organisation; never cross-org; never platform pages. `is_super` property (:513-516) unchanged — `org_admin` is NOT super.
- Migration `courses/0064` (choices-only, auto-generated).

### A2. Role wiring (the sweep checklist — every site, none optional)
- `apps/scholarship/views_admin.py:91-105` `_b40_scope`: `org_admin` → `'all'` (org-fenced by the existing `_org_scoped`/`_org_allows`, same as qc).
- `apps/scholarship/views_admin.py:186-210` `_require_qc`: accept `org_admin` alongside super/qc (self-QC guard stays).
- `apps/scholarship/services.py:491` `REVIEW_ROLES`: add `'org_admin'` (QC-capable ⇒ can act).
- `apps/scholarship/views_admin.py:1033-1047` `AdminAssignableAdminsView` filter: add `'org_admin'` to `role__in` (matches qc's inclusion).
- `apps/scholarship/tests/test_interview_scheduling.py:279` drift tuple: add `'org_admin'`.
- `apps/courses/views_admin.py:489` owning-org binding tuple: add `'org_admin'` (see A5 for tenant binding).

### A3. Surface partition (the security fix)
- `apps/courses/views_admin.py:164-188` `get_partner_students`: the `has_role(admin,'admin')` → ALL-students branch becomes **super-only** (`admin.is_super`); the `partner` own-org branch stays (that IS the partner role's purpose). This one choke-point fixes Dashboard (:208), Students list (:243), export (:339), and detail-GET (:303) together.
- `AdminCourseDataView` (:802) and `AdminCourseDataCheckView` (:829): super-only.
- Unchanged (must stay any-role): `AdminRoleView` (:191), `AdminProfileView` (:743), `AdminSetPasswordView` (:617).
- Regression tests: role=admin/qc/org_admin get 403 on dashboard/students/export/course-data; partner keeps own-org students; super unchanged.

### A4. Staff endpoints gain org_admin delegation (extend, don't duplicate)
Extend the four existing views in `apps/courses/views_admin.py` with role-aware behaviour (super keeps today's full behaviour):
- `AdminInviteView` (:436): allow caller `org_admin` with target role restricted to `{'reviewer','admin','qc'}` (never partner/super/org_admin), `owning_organisation` forced to the CALLER's org (ignore any org inputs). Add `org_admin` to `INVITABLE_ROLES` (:452) for SUPER callers only.
- `AdminListView` (:690): org_admin gets their own org's staff only (`owning_organisation=caller's`, exclude supers); super unchanged.
- `AdminResendView` (:564) / `AdminRevokeView` (:714): org_admin may act only on targets in their own org with role in `{'reviewer','admin','qc'}`; cross-org or super target → 404 (don't leak existence). The durable-invite machinery (temp password, Google skip, `expire_temp_passwords`) is role-agnostic — reuse untouched.

### A5. Add tenant (super-only, minimal — the approved icon 2)
Extend `AdminInviteView`: when a SUPER invites `role='org_admin'`, accept `org_id` or `new_org_name`+`new_org_code`; resolve/create the `PartnerOrganisation` as a TENANT — bind `owning_organisation` to it (NOT the referral `org` field) and on create set `module_scholarship=True`. This reuses the existing partner new-org code path (:465-482) with tenant semantics. No new endpoint.

### A6. Role payload for the frontend
`AdminRoleView` (:191-205): add `owning_org_name` (and `owning_org_id`) — the org section's heading needs it, and `org_name` is the *referral* org (None for org_admin).

### A7. CI-guard + fence updates (build fails without these)
- `apps/scholarship/tests/test_org_fence.py` `FENCED_OR_EXEMPT` (:150-185): no new `_AdminBase` subclasses are added, but the fence-proof suite (:37-142) gains an `org_admin` admin per tenant asserting: org-A org_admin sees only org-A lists, cross-org detail/write/QC → 404, QC-accept works for org_admin (same-org).
- `apps/scholarship/tests/test_org_gates.py`: add org_admin cases to the gate unit tests.
- New courses-side tests (the courses app has no org fence guard — these are the equivalent): org_admin invite binds to caller's org; cannot invite partner/super/org_admin; cannot resend/revoke cross-org or super; staff list scoped; add-tenant creates org + bound org_admin invite; `test_admin_auth.py` gains the positive org_admin invite case.

**Commit A:** `feat(platform): org_admin role + platform surface partition + org-scoped staff endpoints`. Full suite green. ~16–20 files.

---

## Sprint B — frontend: the Administration panel

### B1. New page `app/admin/administration/page.tsx` (route `/admin/administration`; `/admin/invite` becomes a redirect to it)
Per approved Stitch v2 — cPanel icon grid, click opens subpanel below:
- **Page guard:** allow `super` and `org_admin` (message via `apiErrors.superAdminRequired`-style key otherwise), mirroring the invite page's in-page guard pattern (invite/page.tsx:42).
- **Platform section** (rendered for super only): badge "Super admin only"; icon cards *Invite referral partner* (opens the existing partner-invite subform: org select/new-org fields — lift from invite/page.tsx:138-166) and *Add tenant* (name, code, administrator name + email → `inviteAdmin` with role `org_admin`); the all-staff table (current Admin List, invite/page.tsx:174-250).
- **Org section** (rendered for super AND org_admin; heading = `owning_org_name` + " administration", blue "Organisation" badge): icon cards *Invite reviewers & admins* (role pills Reviewer / View-only admin / QC; name+email; the org-scoped staff table with Resend/Revoke) and *Billing & usage* (disabled card, "Coming soon" pill — new muted-card styling; nearest analog `disabled:opacity-50` + `text-gray-400`).
- Reuse: dashboard stat-card grid classes (`app/admin/page.tsx:66-70`), `roleBadge` map (invite/page.tsx:81-86 — add `org_admin` → e.g. amber), card/table containers, `getAdmins`/`inviteAdmin`/`resendAdminInvite`/`revokeAdmin`/`getOrgs` in `lib/admin-api.ts`. Build a small local `IconCard` component in the page (none exists in `components/`).

### B2. Role plumbing + nav
- Type unions: `admin-auth-context.tsx:17` (`AdminRole.role`), `admin-api.ts:173` (`AdminItem.role`), `admin-api.ts:330` (`inviteAdmin` role param) — add `'org_admin'`; add `owning_org_name`/`owning_org_id` to `AdminRole`.
- `app/admin/layout.tsx:56-71`: nav item `administration` (`/admin/administration`, label "Administration") replaces `invite` in the super branch; **`org_admin` branch** = `[scholarship, sponsors, administration, profile, guide, faq]`.
- `app/admin/page.tsx:22-31`: include `org_admin` in the dashboard redirect list.
- Direct-URL hardening: add the dashboard-style client redirect to `students/page.tsx` and `course-data/page.tsx` for non-super (backend 403 from A3 is the real gate; this is UX).
- `app/admin/scholarship/page.tsx:43-47`: `canFilterByAssignee` includes `org_admin`.

### B3. i18n (en/ms/ta ×3) + guard coverage
- New keys under a scoped sub-namespace **`admin.administration.*`** (section headings, icon labels/sublabels, role pill labels incl. "Organisation admin", coming-soon, tenant form) — and **extend the i18n guard**: copy the `sponsor-i18n.test.ts` engine (messages/__tests__/) to cover `admin.administration` (the flat `admin.*` namespace is currently untested — the explorer-flagged gap; do not leave the new keys uncovered).
- If the admin Guide/FAQ pages mention "Invite", update them in the same change (currency rule).

**Commit B:** `feat(admin): Administration panel — platform/org sections, org_admin UI, invite→administration`. Full pytest + jest + `next build` green. ~14–18 files.

---

## Checkpoint (one deploy) + rollout

1. Migrate-first: record `courses/0064` in `django_migrations` via Supabase MCP (choices-only — no DDL; verify with a SELECT). If the MCP is absent, STOP and hand over — do not push.
2. Push both commits → match build by SHORT_SHA → smoke: super login sees Administration (both sections) + Dashboard/Students/Course Data intact; a reviewer sees no Administration and gets 403 on `/api/v1/admin/students/`.
3. **Rollout (owner-gated, document in the close):** promote Suresh — `UPDATE partner_admins SET role='org_admin' WHERE email='surithiru@gmail.com'` via Supabase MCP (house precedent: the qc-grant), verify `owning_organisation` is BrightPath, then live walkthrough with him: sees only the org section, invites one reviewer end-to-end, still can QC, CANNOT reach Students/Dashboard/Course Data.
4. Sprint-close workflow: retro, CHANGELOG (both sprints), CLAUDE.md Next Sprint, memory update (`halatuju_org_roles_billing.md`: panel SHIPPED, Suresh promoted), `wat_lint.py`.

## Verification

- Backend: the A3/A4/A5 test matrix + fence-proof suite with org_admin tenants green in the full run.
- Frontend: jest (incl. the new i18n guard) + `next build`; visual check of the panel vs the approved Stitch v2.
- Live: the smoke + Suresh walkthrough above; zero new error logs.

## Sizing & risks

A ≈ 16–20 files (Med-High: role wiring breadth), B ≈ 14–18 files (Med). Both within cap. Top risks: (1) a missed role-literal branch — mitigated by the sweep checklist in A2/B2 (it is exhaustive; do not improvise beyond it); (2) the partition breaking the partner role's own-org students view — explicit regression test in A3; (3) new i18n keys silently missing in ms/ta — mitigated by the new guard test in B3; (4) org_admin invite binding to the wrong org — the A7 courses-side tests pin caller-org forcing.

## Pre-flight note (added at packaging, 2026-07-15)

At packaging time this checkout carried UNCOMMITTED in-progress feature work (school-leaving-certificate parsing: `doc_parse.py`, `academic_engine.py`, `serializers.py`, `vision.py`, web cockpit + i18n, `test_school_leaving_fields.py`) belonging to ANOTHER session. **If `git status` shows uncommitted work you did not create: STOP and report — do not commit it, do not build on top of it.** Start this brief only on a clean tree (that feature committed/pushed by its own session), or work in a separate worktree per `parallel-work-isolation.md`. Note the role-literal sweep in A2/B2 predates that feature — if it landed meanwhile, re-grep `admin-api.ts` and `serializers.py` for new role branches before wiring `org_admin`.
