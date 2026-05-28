# Retrospective — TD-059: drop dead `FundingNeed` amount columns (v2.4.7)

**Date:** 2026-05-28
**Shipped:** web `halatuju-web-00220-7v9`, api `halatuju-api-00179-v26`; `funding_needs` schema reduced from 16 to 7 columns; migration `scholarship 0015_drop_funding_amount_fields` recorded at 04:12 UTC. **Resolves TD-059.**

## What Was Done

Removed 9 dead columns left behind by the S3 funding reframe (v2.4.2): `tuition_gap`, `laptop`, `hostel`, `transport`, `books`, `monthly_allowance`, `allowance_months`, `other`, `other_desc`. Removed the `total` property and the `__str__` line that used it.

- **Backend:** `FundingNeedSerializer.fields` shrunk to `categories`/`funding_note`/`programme_months`. `TestFundingNeedModel` (the `.total`-only class) dropped. Funding-breakdown PATCH tests rewritten to use `categories`.
- **Frontend:** `api.ts FundingNeed` interface trimmed to the 3 kept fields. `DetailsFormState` lost its 8 amount form fields. `fundingTotal` helper + its jest tests removed. `applicationToDetailsForm`/`buildDetailsPayload` mappings shrunk. The admin detail page no longer renders `RM${funding_need.total}` — it shows the **ticked categories list** instead. An orphan "Something else" textarea bound to `form.otherDesc` was removed (the redesigned `fundingNote` open box already serves that purpose).
- **Schema:** destructive migration applied on prod via Supabase MCP under the **expand-contract** pattern.

## What Went Well

- **Expand-contract was the right pattern.** New code went live first (the `FundingNeedSerializer` no longer exposed the dropped fields), THEN `DROP COLUMN ×9` ran on prod via MCP + the `django_migrations` row was recorded. Zero risk of "old code reading a now-missing column."
- **Pre-drop safety hold.** I re-confirmed `SELECT COUNT(*) FROM funding_needs = 0` immediately before the destructive DDL — not just trusting the TD's earlier note.
- **Drop + record in one transaction.** `BEGIN; ALTER TABLE … DROP COLUMN ×9; INSERT INTO django_migrations …; COMMIT;` ran atomically.

## What Went Wrong

This sprint **breached the "never deploy more than twice per feature" rule** — 3 deploys, not 2 — and both failures had the same root cause.

1. **Local "build clean" was a lie I told myself, twice.**
   - *Symptom:* push #1 web build failed (`admin-api.ts FundingNeed` type stale); push #2 web build failed again (orphan `form.otherDesc` textarea); local `next build` had said clean both times.
   - *Root cause:* I was running `npm run build 2>&1 | grep -E "...|✓"` then reading the task notification's exit code as the build's. The pipe's exit code is the **last** command's — grep's, not npm's. So whenever Next.js exited 1 with a TypeScript error, grep matched the `Failed to compile`/`Type error` lines and returned 0, and I read "EXIT=0" as "build green." The same pipeline that surfaced the error masked its disposition.
   - *System change:* **never pipe `npm run build` (or any build/test gate) to `grep` when judging pass/fail.** Either: `set -o pipefail` at the start of the shell, or check `${PIPESTATUS[0]}` explicitly, or capture to a file (`> build.log 2>&1`) and read the unmasked exit code separately (`echo "EXIT=$?"; grep ...`). Added to `lessons.md`.

2. **I updated one shape, missed the parallel shape.** `FundingNeed` is defined twice in the frontend: in `lib/api.ts` (student-facing) and inside `lib/admin-api.ts AdminScholarshipDetail.funding_need` (admin-facing). I updated the first, missed the second. Cloud Build's stricter TS check caught it; if my local check hadn't been masked by point 1, my own build would have too.
   - *System change:* **when changing a shared model's shape, grep for `funding_need|FundingNeed` across both `api.ts` and `admin-api.ts`** (the project keeps separate admin types) before declaring done. Added to `lessons.md`.

Both lessons trace to the same operational discipline: **trust the exit code, not the eyeballed output**, and **scan ALL parallel shape definitions when changing one**.

## Design Decision

- **Expand-contract for destructive migrations on this live system.** For additive migrations we run "migrate-first" (old code keeps working, new column inert). For destructive changes the order **inverts**: deploy new code first (Django ignores extra DB columns), then drop the columns. If we dropped first, the currently-live `FundingNeedSerializer` would 500 on every `GET application` until the new code shipped. (Logged in `docs/decisions.md`.)

## Numbers

- Files changed: 10 (model, migration, serializer, test_details; api.ts, scholarship.ts, scholarship.test.ts, ScholarshipNextSteps.tsx, admin/scholarship/[id]/page.tsx, admin-api.ts) + CHANGELOG.
- Backend: 1141 pytest (−2 for the dropped `total` tests). Frontend: jest 123 (−2 for the dropped `fundingTotal` describe). `next build` clean once monitored properly.
- i18n parity: 1246 unchanged (a few orphan amount-field label keys remain — harmless because they're in all three locales; could be swept in a future cleanup).
- Deploys: **3 (over the 2-deploy budget).** Commits: `4837b0a` (cleanup), `adb32dd` (admin-api type fix), `42bdd69` (orphan textarea removed).
- `funding_needs` schema: 16 columns → **7 columns**. 0 prod rows before drop; no data loss.
