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

**Reused (already live, still accurate — no re-capture needed):**
`/reviewer-guide/step1-list.png`, `step2-overview.png`, `step3-checks.png`,
`step4-documents.png`, `step5-profile.png`, `step6-outstanding.png`, `step7-interview.png`,
`step8-decision.png` (the last is portrait → floats).

## After the pass
1. Owner drops the five PNGs into `/public/manual/`.
2. A docs-only follow-up commit adds the files (rides the next push; no dedicated deploy).
3. Owner reverts `elanjelian@me.com` → `reviewer`.
