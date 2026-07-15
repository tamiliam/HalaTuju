# Implementation Brief — Org-Admin Powers v1 + Role-Matrix Alignment

**For:** the implementing agent (Opus 4.8), in `c:\Users\tamil\Python\Production\HalaTuju`
**Shape:** ONE sprint, one commit per side optional but **one deploy**. NO migrations (no schema change anywhere in this brief). Owner decisions settled — do not reopen.
**Authority: `docs/scholarship/role-matrix.md`** — the owner-settled canonical permission matrix (2026-07-15). Every gate this brief touches must land exactly on that table.

## Context

The org admin role (`org_admin`, shipped 2026-07-15) is "true super admin within the organisation" (owner's words), but today its write powers stop at QC + staff invites. Owner exploration (as `elanjelian@me.com`, a second BrightPath org_admin) plus the owner's permission matrix produced this batch: (1) org admins assign reviewers from the applicants list; (2) org admins get the three cockpit action boxes (Check-2 outstanding / interview stage / recommendation) on ANY own-org application; (3) BUG — the QC box is invisible to org admins (frontend `canQc` never learned the role; backend already accepts it); (4) a last-org-admin revoke guard; (5) a NEW verdict-recorder QC guard so the broadened powers can't collapse two-person control; **(6) QC becomes hybrid — review-all like org_admin, protected by the same guard; (7) sponsor vetting MIGRATES to org_admin (today it is reviewer-gated — investigation finding) and sponsor visibility tightens per the matrix; (8) the view-only `admin` role gets READ-ONLY access to the Administration org section.** Deliberately WITHHELD from all organisation roles (owner-approved — do not add): decision reopen/cancel-reopen, award-amount setting, bursary countersign, appointing another org_admin. The Finance role stays future (payout rails).

## Ground rules

1. `Settings/_workflows/sprint-start.md`/`sprint-close.md`; full pytest (3,783+) green + jest (530+) + `next build` before the push; never two heavy suites at once (8GB).
2. `docs/build-for-tenancy-conventions.md`; the org-fence CI guards will fail the build until §Tests is satisfied.
3. FE/BE gates are keep-in-sync pairs (house lesson — this batch exists partly because `canQc` drifted): every backend gate change lands with its frontend twin in the same commit.
4. After push: match the Cloud Build by YOUR SHORT_SHA (`gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com`).

## Backend (`halatuju_api`)

1. **`_can_review_app`** (`apps/scholarship/views_admin.py:152-165`): after the cross-org check (`_org_allows`, :163) add — `if admin.role == 'org_admin': return True` (same-org is already guaranteed at that point). Update the docstring: org_admin = write on any OWN-ORG application; admin/reviewer stay assigned-only. This single change lights up the three cockpit boxes' endpoints (all route through `_require_app_write`).
2. **`_require_qc`** (`apps/scholarship/views_admin.py` ~:186-210): NEW recorder guard for non-super callers — refuse (403, error code `self_verdict_qc_forbidden`) when `app.verdict_decided_by` (recorder's email, set at :1225, model field `models.py:762`) case-insensitively equals the caller's email. Keep the existing self-assignment guard. Rationale in code comment: with org_admin write powers, assignment no longer proves who recorded the verdict — the recorder must never QC their own verdict (two-person control; `models.py:482` states the principle).
3. **`AdminAssignReviewerView`** (super-only gate, `has_role('super')` around :1540s — re-locate by class name): allow `org_admin`; the application is already org-fenced via `_scoped_application`; ADD — for non-super callers the target reviewer must be an ACTIVE `role='reviewer'` in the CALLER's `owning_organisation` (never a super, never cross-org → same error shape as today's `bad_assignee`). AssignmentEvent audit unchanged.
4. **`AdminAssignableAdminsView`**: for non-super callers, scope the dropdown to the caller's own organisation. This flips its classification in the S3b completeness map (`test_org_fence.py` `FENCED_OR_EXEMPT`) from cross-org-by-design to list-fenced — the CI guard forces the update.
5. **`AdminRevokeView`** (`apps/courses/views_admin.py`): last-org-admin guard — refuse `action='revoke'` (400, `last_org_admin`) when the target is an active `org_admin` and no OTHER active `org_admin` shares its `owning_organisation`. Mirrors the existing cannot-revoke-super guard. Restore unaffected.
6. **QC hybrid (matrix row `qc`)**: in `_can_review_app`, the same own-org branch added for `org_admin` also covers `role == 'qc'` (review all within own org). The recorder guard from §2 is what makes this safe — a QC who records a verdict cannot QC that case.
7. **Sponsor-power migration (matrix Sponsors column)**: `AdminSponsorReviewView` (`views_admin.py:862-870`) — replace the `_require_reviewer` gate (do NOT modify `_require_reviewer` itself; other views use it) with super-or-`org_admin`. `AdminSponsorListView` (`views_admin.py:842-848`, currently ANY admin) — restrict to super / `org_admin` / `admin` (Admin-General keeps view); `qc` and `reviewer` are refused. Update both views' entries in the S3b completeness map accordingly.
8. **Admin-General read-only Administration (matrix `admin` row)**: `AdminListView` (`apps/courses/views_admin.py`) — allow `role='admin'` callers with the SAME org-scoped, non-super filter as org_admin (read only; invite/resend/revoke gates unchanged — they stay super/org_admin).

## Frontend (`halatuju-web`)

6. **`app/admin/scholarship/page.tsx`**: the Assigned column (:261) and the inline assign control (:286) — extend `isSuper` to a `canAssign = isSuper || role?.role === 'org_admin'` flag. The assignable-reviewers fetch (:118 `if (!token || !isSuper) return`) must also run for org_admin.
7. **`app/admin/scholarship/[id]/page.tsx`**: `canQc` (:207) += `org_admin` (**the bug**); `canWrite` (:212) += `org_admin` (backend fences org membership; detail fetch already 404s cross-org); the assign panel follows `canAssign`. **Do NOT touch** the reopen/cancel-reopen blocks (:2191-2231, stay `isSuper`) — withheld.
8. **`app/admin/administration/page.tsx`**: hide the Revoke link on a tenant-admin row when it is that organisation's only active org_admin (derive from the already-loaded list; backend guard is the authority). **Matrix additions:** page guard also admits `role === 'admin'` in a READ-ONLY render — org-section staff table visible, NO invite forms, NO resend/revoke links, no icon-card subpanels that act.
9. **Matrix nav/gate tightening**: `app/admin/layout.tsx` — remove Sponsors from the `qc` branch (matrix: QC Sponsors = ✗); `admin` and `org_admin` branches keep Sponsors; `admin` branch gains `administration`. `[id]/page.tsx` `canWrite` also includes `qc` (hybrid QC). Sponsor pages: any FE affordances for vetting follow the new backend gate (org_admin, not reviewer).
10. i18n ×3 (en/ms/ta): new error strings for `last_org_admin` and `self_verdict_qc_forbidden` (surface them where QC/revoke errors already render); any new assign-control strings. The `admin.administration.*` guard test must stay green.

## Tests

- **Fence-proof / gates** (`test_org_fence.py`, `test_org_gates.py`): org_admin AND qc writes on own-org apps succeed (a Check-2 action + verdict record), cross-org still 404; completeness-map reclassifications (§4, §7).
- **Matrix conformance**: sponsor vetting — org_admin allowed, reviewer now refused (regression on the OLD gate), qc/reviewer refused on the sponsor list, admin still reads it; Admin-General reads the staff list but invite/resend/revoke refused; nav snapshot per role matches `docs/scholarship/role-matrix.md`.
- **QC recorder guard**: org_admin records a verdict → their own QC-accept on that case 403s (`self_verdict_qc_forbidden`); a DIFFERENT org_admin/qc of the same org may QC it; super unaffected; existing self-assignment guard still holds. Grep the test tree for all `_require_qc`/qc-decision callers and re-verify each under the new precondition (relaxed/tightened-gate house lesson).
- **Assignment**: org_admin assigns own-org reviewer OK (+AssignmentEvent row); cross-org target and super target rejected; dropdown scoped; existing super assignment tests unchanged.
- **Revoke guard**: sole org_admin revoke blocked; with two active org_admins revoke succeeds; restore unaffected; view test in `test_org_admin_role.py`.
- **FE**: jest additions for `canAssign`/`canQc`/last-admin-revoke-hide where the existing page tests live; full jest + `next build`.

## Rollout (after suite green + push + build SUCCESS by SHA)

1. Smoke as the owner's org_admin test account (`elanjelian@me.com`): assign a reviewer from the list; open an unassigned application — the three boxes act; the QC box is visible; record-then-QC on the same case is refused; Administration shows no Revoke on a sole tenant admin.
2. Owner then reverts `elanjelian@me.com` → `reviewer` (owner-gated, Supabase MCP) and briefs Suresh.
3. Sprint-close workflow; update the admin Guide/FAQ if they describe assignment or QC powers (currency rule); memory update (`halatuju_org_roles_billing.md`: batch SHIPPED, list what remains parked).

## Sizing & risks

~20–26 files, no migration, one deploy. Top risks: (1) a `_require_app_write` caller whose behaviour assumed assigned-only writers — mitigated by the caller-sweep test discipline; (2) the recorder guard matching on email while an admin's email changes — accept (emails are the stable staff key here; note as TD if it bites); (3) FE/BE drift — rule 3; (4) stripping reviewer sponsor-vetting breaking an existing flow/test that assumed it — sweep the test tree for the old gate's callers before changing it.

## Update the docs in the same change
`docs/scholarship/role-matrix.md` §Implementation state → mark this brief SHIPPED; admin Guide/FAQ pages if they describe reviewer sponsor-vetting, QC scope, or assignment (currency rule).
