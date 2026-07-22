# Manual — screenshot capture manifest (2026-07-16)

For the owner-assisted capture pass. Each new chapter ships with a labelled placeholder
(the `ManualImage` component degrades gracefully); drop the real PNGs into
`/public/manual/` with the exact filenames below and they appear automatically — no code
change needed. **Demo / anonymised data only** (standing PII rule): use a fabricated
applicant, or blur names/NRIC/contact before capturing.

The owner's `elanjelian@me.com` org_admin test account **stays an org_admin until this pass
is done** (it's the only account that can show the org-admin surfaces), then the owner
reverts it to `reviewer`.

| File (`/public/manual/…`) | Chapter · section | Page & state | Capture as (role) | Crop hints |
|---|---|---|---|---|
| `qc-queue.png` | QC · what QC is | `/admin/scholarship` filtered to Interviewed (awaiting QC) | qc or org_admin | the list showing awaiting-QC rows; landscape |
| `org-admin-team.png` | Org admin · your team | `/admin/administration` → Invite reviewers & admins (staff table open) | org_admin | the org staff table with Resend/Revoke; landscape |
| `org-admin-assign.png` | Org admin · assigning applicants | `/admin/scholarship` (list) | org_admin | the **Assigned** column + inline reviewer dropdown open; landscape |
| `org-admin-sponsors.png` | Org admin · vetting sponsors | `/admin/sponsors` | org_admin | the sponsor list with Approve/Reject/Suspend; landscape |
| `org-admin-administration.png` | Org admin · the Administration panel | `/admin/administration` (both cards visible) | org_admin | the Organisation section (Invite staff + Billing "coming soon"); landscape |
| `org-admin-payments.png` | Org admin · payment runs | `/admin/payments/<id>` on a run awaiting countersignature | org_admin | the student table + the sign-off box with the maker signed; landscape |
| `finance-payments.png` | Finance · where to find Payments | `/admin/administration` | finance (or org_admin) | the Organisation section showing the **Payments** card; landscape |
| `finance-signature.png` | Finance · checking a run | `/admin/payments/<id>` at `admin_signed` **with a finance admin active** | finance | the THREE sign-off columns (maker ✓ · finance box · approver waiting); landscape |
| `finance-funding-summary.png` | Finance · the funding summary | `/admin/payments` | finance (or org_admin) | the Funding summary table + its totals footer; landscape |

**Reused (already live, still accurate — no re-capture needed):**
`/reviewer-guide/step1-list.png`, `step2-overview.png`, `step3-checks.png`,
`step4-documents.png`, `step5-profile.png`, `step6-outstanding.png`, `step7-interview.png`,
`step8-decision.png` (the last is portrait → floats).

> **Sprint 14 (2026-07-23) added four rows** — one for the org-admin Payments section (the
> Payments module had no Manual coverage at all, the carry recorded in `role-matrix.md`) and
> three for the new Finance chapter. `finance-signature.png` is the only one with a
> precondition: the organisation must have an ACTIVE finance admin at capture time, or the run
> renders the two-column dormant layout and the shot shows the wrong thing.

## After the pass
1. Owner drops the PNGs into `/public/manual/` (five original + four from Sprint 14).
2. A docs-only follow-up commit adds the files (rides the next push; no dedicated deploy).
3. Owner reverts `elanjelian@me.com` → `reviewer`.
