# Release-note draft — sprint M3a, the organisation admin's powers are stored keys (2026-11-14)

**DRAFT. Not applied anywhere but the local test database. The owner says yes before any step below runs.**
Decisions: `docs/decisions.md` (2026-11-14, M3a). Brief: `docs/plans/2026-11-14-m3-lead-keys-brief.md`.
The SQL below is copied from the docstring of `courses/0098_store_org_admin_keys.py`, which is the source: if
the two ever differ, the docstring wins.

## What changes for people

- **Nothing anybody can do changes.** An organisation admin's powers are now written on their row as keys
  instead of being read from the label. Every page and button answers as before (server only; no web change).
- **Display only, during the window:** while the OLD image still serves, its Permissions editor shows a migrated
  organisation admin's page keys as ticked. Nothing it gates reads them, and it stops when the new image serves.
- **A role change on the Django admin screen now resets the row's permissions** to the new role's starting set
  and records it in the permission history (kind `role_change`).

## Migration — MIGRATE-FIRST, by hand, before the push

`courses` `0098_store_org_admin_keys` (data only, reversible). Every `org_admin` row, in every lifecycle state,
has its list REPLACED by `review` (only if held today) + the five old keys + the 25 v2 page keys. One
`staff_permission_changes` row per row written (`edit_null` for a NULL row, `edit` otherwise). A value that is
neither NULL nor a list is left alone; every other role is untouched. A stored jsonb `null` counts as NULL.

### ⚠ The window

The window lasts from step 2 until the DATA block is **RE-RUN in step 4, after the new image carries 100% of
the traffic** — not merely until the push. Until that re-run:

- do not change an organisation admin's role;
- **do not use Team -> Reviewers Add / Remove on an organisation admin.** The old image's writers overwrite the
  list with `["review"]` or NULL; `["review"]` would read under the new image as `review` and `manage_team` only.
  The re-run repairs either, which is why step 4 is not optional.

At any time, a role change BY HAND (SQL) must set `permissions = NULL` in the same statement
(`docs/deployment.md`, item 3).

### 1. Pre-check (read-only). Expect 2 organisation admin rows and no ledger row. Anything else: STOP and ask.

```sql
BEGIN READ ONLY;
SELECT count(*) FROM partner_admins WHERE role = 'org_admin';                                   -- expect 2
SELECT count(*) FROM partner_admins
 WHERE role = 'org_admin' AND NOT (permissions IS NULL OR jsonb_typeof(permissions) IN ('array', 'null'));  -- expect 0
SELECT count(*) FROM django_migrations WHERE app = 'courses' AND name = '0098_store_org_admin_keys'; -- expect 0
COMMIT;
```

### 2. DATA block (one transaction; the ledger row is written inside it)

```sql
BEGIN;
WITH plan AS (
  SELECT id, email, owning_organisation_id, role,
         (permissions IS NULL OR permissions = 'null'::jsonb) AS was_null,
         COALESCE(NULLIF(permissions, 'null'::jsonb),
                  '["see_all","scholars","qc","spending","award_withdraw_approve"]'::jsonb) AS base,
         (CASE WHEN permissions ? 'review' THEN '["review"]' ELSE '[]' END)::jsonb
         || '["see_all","scholars","qc","spending","award_withdraw_approve","invitations.view",
              "invitations.edit","team.view","sources.view","sources.edit","sponsors.view","sponsors.edit",
              "sponsors.approve","billing.view","requests.view","requests.edit","settings.edit",
              "students.edit","students.approve","contracts.view","contracts.edit","programmes.edit",
              "announcements.view","announcements.edit","surveys.view","surveys.edit","development.view",
              "development.edit","mentoring.view","mentoring.edit"]'::jsonb AS after
    FROM partner_admins
   WHERE role = 'org_admin'
     AND (permissions IS NULL OR jsonb_typeof(permissions) IN ('array', 'null'))
), audit AS (
  INSERT INTO staff_permission_changes (target_id, target_email, organisation_id, kind, role, before,
                                        after, changed_by_email, changed_by_role, created_at)
  SELECT id, COALESCE(email, ''), owning_organisation_id, CASE WHEN was_null THEN 'edit_null' ELSE 'edit' END,
         role, base, after, '', 'migration', now()
    FROM plan WHERE was_null OR after <> base
)
UPDATE partner_admins p SET permissions = g.after FROM plan g WHERE p.id = g.id AND (g.was_null OR g.after <> g.base);
INSERT INTO django_migrations (app, name, applied)
SELECT 'courses', '0098_store_org_admin_keys', now()
 WHERE NOT EXISTS (SELECT 1 FROM django_migrations
                    WHERE app = 'courses' AND name = '0098_store_org_admin_keys');
COMMIT;
```

Expect `UPDATE 2` (one NULL row, one `["review"]` row) and `INSERT 0 1`. The old image reads an organisation
admin's list for `review` only, and `review` is kept, so it is safe to apply before the push.

### 3. Push (api), then CONFIRM the new api revision serves 100% of the traffic

### 4. Re-run the DATA block (step 2, word for word), then the POST-DEPLOY CHECK

The re-run writes nothing if nothing changed in the window (expect `UPDATE 0`, `INSERT 0 0`); otherwise it
repairs the rows the old image overwrote. The check must return ZERO rows; if not, re-run the DATA block only.

```sql
SELECT id, (permissions IS NULL OR permissions = 'null'::jsonb) AS was_null FROM partner_admins
 WHERE role = 'org_admin'
   AND (permissions IS NULL OR jsonb_typeof(permissions) IN ('array', 'null'))
   AND permissions IS DISTINCT FROM ((CASE WHEN permissions ? 'review' THEN '["review"]' ELSE '[]' END)::jsonb
         || '["see_all","scholars","qc","spending","award_withdraw_approve","invitations.view",
              "invitations.edit","team.view","sources.view","sources.edit","sponsors.view","sponsors.edit",
              "sponsors.approve","billing.view","requests.view","requests.edit","settings.edit",
              "students.edit","students.approve","contracts.view","contracts.edit","programmes.edit",
              "announcements.view","announcements.edit","surveys.view","surveys.edit","development.view",
              "development.edit","mentoring.view","mentoring.edit"]'::jsonb);
```

The window closes here.

## Rollback

⚠ **Run the reverse ONLY AFTER rolling the api image back** to one before M3a. Under the M3a image a reversed
`["review"]` row reads as `review` and `manage_team` alone, which cripples that organisation admin.
The reverse is Django's (`migrate courses 0097`) against production, run by the architect: for each row it reads
only the NEWEST audit row 0098 wrote, gives back the `before` (NULL for `edit_null`) to a row still holding that
row's `after`, leaves a row changed since as it is, and deletes 0098's audit rows. Never run 0095's reverse by
hand while 0098 is applied.

## Afterwards

- Run the Supabase Security Advisor (no schema change, so expect no new finding).
- No new strings; nothing for ms / ta review.
