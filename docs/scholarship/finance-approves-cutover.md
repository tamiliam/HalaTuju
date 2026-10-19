# Finance approves payment runs (request #39, Sprint 2) — cutover note

**Migrations: NONE.** The three signature triples on `payment_runs` are reused (maker →
`admin_signed_*`, check → `finance_signed_*`, approver → `org_admin_signed_*`). No column, no
ledger row, no backfill. The change is code only: the presets in `apps/courses/staff_permissions.py`
(`finance` now holds `payments_approve`; the organisation admin's lead tier no longer does) and the
chain in `apps/scholarship/payments_chain.py`.

**Status:** written 2026-10-19 by the sprint; the lead runs the query below READ-ONLY before the
deploy and tells the owner if it returns anything (roadmap question 5: deploy on a day it returns
none).

## Before the deploy — the read-only check (lead)

Run on production (Supabase `pbrrlyoyyiftckqvzvvo`), read-only. Expected on 2026-10-19 (measured by the
lead): **no run mid-chain**; BrightPath (organisation 11) has 1 active `finance`, 2 `org_admin`,
2 `admin`.

```sql
-- 1. Runs still on their way (anything short of completed / cancelled), with who has signed.
--    Expected: 0 rows. If any, see "What each in-flight run does" — nothing strands, but tell the owner.
SELECT r.id, r.reference, r.organisation_id, r.status,
       r.admin_signed_email, r.finance_signed_email, r.org_admin_signed_email, r.created_by
FROM payment_runs r
WHERE r.status IN ('draft', 'admin_signed', 'finance_checked')
ORDER BY r.organisation_id, r.id;

-- 2. Who will approve, per organisation, the day this ships: active finance people (the new
--    approvers — ELIGIBLE only once they have signed in, `first_seen_at` NOT NULL) and active
--    organisation admins (the fallback). A NULL `permissions` is the preset. Expected for
--    BrightPath (11): finance 1 with signed_in 0 (Periasamy Sinnan, id 24, has never signed in —
--    so Suresh keeps approving under the fallback until he does), org_admin 2. Any row with a
--    NON-NULL permissions list is a custom set (none exist until Sprint 4) — tell the owner.
SELECT owning_organisation_id, role, count(*) AS active,
       count(*) FILTER (WHERE first_seen_at IS NOT NULL) AS signed_in,
       count(*) FILTER (WHERE permissions IS NOT NULL) AS custom_sets
FROM partner_admins
WHERE is_active AND NOT is_super_admin AND role IN ('finance', 'org_admin', 'admin')
GROUP BY owning_organisation_id, role
ORDER BY owning_organisation_id, role;

-- 3. Wallet credits mid-chain (they keep TODAY's chain; listed only so nobody is surprised).
SELECT d.id, d.status, d.programme_id, d.recorded_by_email, d.finance_checked_by_email
FROM sponsor_donations d
WHERE d.status IN ('draft', 'admin_signed', 'finance_checked')
ORDER BY d.id;
```

## Deploy order

**API FIRST, then web.** The new web reads `can_prepare` / `your_step` from the api; served by the old
api they are absent, and admins would lose the edit and cancel controls until the api lands. The old
web against the new api is safe (it ignores the new keys; the server refuses any wrong step).

## A Finance person who has never signed in (review fix 4)

A `payments_approve` (or `payments_check`) holder counts as eligible only once they have signed in
(`first_seen_at`, stamped on their first console request). Until then the organisation admin
approves under the fallback, the "awaits your approval" email goes to the organisation admin (not
to Finance, who cannot act on it yet), and nothing waits for somebody who cannot sign in. The
moment Finance first signs in, they become the approver for every run still in flight.

## What each in-flight run does (no data change; tests in `test_finance_approves.py`)

| Run status when the change lands | What happens |
|---|---|
| `draft` | Unchanged. The maker signs and the "ready" email goes to Finance ("awaits your approval") — or, while Finance has never signed in, to the org admins. |
| `admin_signed`, organisation has no Finance person | Nobody holds `payments_approve`, so the org admin approves under the fallback, exactly as before. |
| `admin_signed`, BrightPath with a Finance person (was waiting for Finance's CHECK) | Finance now APPROVES directly and the run completes on that signature; Suresh's countersignature is skipped — the change the owner asked for. |
| `finance_checked` (Finance already checked it) | Distinctness bars Finance from approving too; nobody else is eligible, so the fallback lets the org admin approve, as today. Nothing strands. |

## After the deploy — what to look at

- The Payments page shows Finance a **Waiting for you** block and a count on the Payments menu row
  when a run is waiting for them; the org admin sees no approve box on a run Finance can approve.
- Wallet credits: Finance still CHECKS, the org admin still COUNTERSIGNS (unchanged; question 6).
- Rollback: redeploy the previous image. No data was written by the change, so nothing to undo; a
  run completed under the new chain carries Finance's email in `org_admin_signed_email`, which the
  old image reads as "the approver" and renders correctly.
