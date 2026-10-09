# Per-gift referral sources, Sprint 2 — prod cutover SQL (migrate-first)

**Migration:** `courses/0077_retire_legacy_referral_codes` (courses ledger 0076 → 0077). Data only.
**Status: APPLIED 2026-10-09** by the lead via the Supabase MCP, after 0172 and before the push
of `ffa0983a`: 1 profile `pushparani` → `other` (as expected), ledger row recorded.

Written 2026-10-08 by the sprint; the lead applies it to production
(Supabase `pbrrlyoyyiftckqvzvvo`) via the Supabase MCP before the push. Sprint 1's
`scholarship/0172_programme_referral_sources` (`gift-sources-s1-cutover-sql.md`) must already be
applied: the Sprint 2 image serves the intake's `sources` from that table.

What it does (owner's ruling, 2026-10-08): the legacy individual-coordinator codes `pushparani`
and `govind` leave every form, and every saved profile carrying one moves to `other`. The table is
`api_student_profiles`; `referred_by_org_id` is not touched (neither code was ever a
`partner_organisations` row).

## Pre-check (read-only)

```sql
BEGIN READ ONLY;
SELECT name FROM django_migrations WHERE app = 'courses' ORDER BY name DESC LIMIT 2;   -- ends at 0076
SELECT referral_source, count(*) FROM api_student_profiles
 WHERE referral_source IN ('pushparani', 'govind') GROUP BY referral_source;
-- expected 2026-10-08: pushparani 1 (govind 0 → no row)
COMMIT;
```

## The cutover — ONE transaction

```sql
BEGIN;

UPDATE api_student_profiles
   SET referral_source = 'other'
 WHERE referral_source IN ('pushparani', 'govind');
-- expect: UPDATE 1 (the pre-check's total). A different number: ROLLBACK and look before going on.

INSERT INTO django_migrations (app, name, applied)
  VALUES ('courses', '0077_retire_legacy_referral_codes', now());

COMMIT;
```

No DDL, so no RLS step and no `SET CONSTRAINTS` question. `updated_at` is deliberately left alone
(the Django migration's queryset `update()` does not touch it either).

## Post-check (read-only)

```sql
BEGIN READ ONLY;
SELECT count(*) FROM api_student_profiles WHERE referral_source IN ('pushparani', 'govind');   -- 0
SELECT name FROM django_migrations WHERE app = 'courses' ORDER BY name DESC LIMIT 1;           -- 0077_…
COMMIT;
```

## Reverse

None. Once moved, a profile's `other` cannot be told from one a student chose, so the migration's
reverse is a documented no-op. If the ledger row must be withdrawn before deploy:
`DELETE FROM django_migrations WHERE app = 'courses' AND name = '0077_retire_legacy_referral_codes';`
(the data stays `other`, which every admin surface already showed it as).

**Deploy order:** this data migration is safe either way round. The old image still lists both
codes and accepts `other`; the new one lists neither and refuses both at submit
(`referral_source_not_offered`). The SCHEMA one is not: 0172 must be applied before the push (see
the S1 doc — the new image's public intake and its submit read the new table).

## Deploy window (accepted)

The api and web deploy separately. While the NEW api is live and the OLD web still serves, the old
form still offers its hard-coded list, so a student can submit `sathya_sai`, `tara`, `pushparani`
or `govind`; the new api refuses those (400 `referral_source_not_offered`) and the old form shows
its generic error. Minutes, on a low-traffic form — accepted.
