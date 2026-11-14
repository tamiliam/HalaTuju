# Release-note draft — sprint M3c, the organisation admin grants its keys; the web reads them (2026-11-15)

**DRAFT. Branch m3c, not pushed, not published. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-15, M3c). Brief: `docs/plans/2026-11-14-m3-lead-keys-brief.md`.
Services: both (api and web). Needs M3a's 0098 (live 14 Nov) and M3b in the same or an earlier publish.

## What changes for people

- **An organisation admin can give a team member its own powers** on the person's Permissions tab: Settings,
  gift settings, assigning and nudging, rejecting or closing applications, sponsors, billing view, requests,
  contracts, and the new "Suspend or end a scholarship". You can give only what you hold yourself; anything
  else shows a padlock. Three stay with the role and are never given: changing the team's permissions,
  paying the platform bill, approving requests that use paid hours.
- **Payments stay with the role** until payments move to permissions: the organisation admin starts runs and
  approves one when no one else can, never prepares one. The card says so.
- **Suspension and termination letters** now need the key "Suspend or end a scholarship". Every organisation
  admin gets it (migration 0099); a super can take it away.
- **Sponsor account vetting and publishing sponsor terms** stay with supers and organisation admins (they
  reach every organisation). A team member given sponsor approval accepts sponsors into their own gifts only.
- **"Give cases to reviewers and nudge them. Never to yourself."** Assigning a case to yourself now says
  "You cannot give a case to yourself." instead of the general error.
- **E5:** anyone who can view Invitations sees the Mentor tab, read-only. Inviting needs "View and change".
- **E8:** Announcements, Surveys and Development use the full console width, like Scholars.

## Migration 0099_grant_scholars_approve (additive) — by hand, migrate-first

The old image ignores the new key, so the DATA block runs BEFORE the push. Read-only probes: `BEGIN READ ONLY`.

1. **PRE-CHECK (read-only).** Expect 0098 listed and 0099 not.
```sql
BEGIN READ ONLY;
SELECT jsonb_typeof(permissions) AS shape, permissions ? 'scholars.approve' AS has_key, count(*)
  FROM partner_admins WHERE role = 'org_admin' GROUP BY 1, 2 ORDER BY 1, 2;
SELECT name FROM django_migrations
 WHERE app = 'courses' AND name IN ('0098_store_org_admin_keys', '0099_grant_scholars_approve');
COMMIT;
```
2. **DATA block, before the push** (one transaction, ledger row included; safe to re-run).
```sql
BEGIN;
WITH plan AS (
  SELECT id, email, owning_organisation_id, role, permissions AS base,
         permissions || '["scholars.approve"]'::jsonb AS after
    FROM partner_admins
   WHERE role = 'org_admin'
     AND jsonb_typeof(permissions) = 'array'
     AND NOT permissions ? 'scholars.approve'
), audit AS (
  INSERT INTO staff_permission_changes (target_id, target_email, organisation_id, kind, role, before,
                                        after, changed_by_email, changed_by_role, created_at)
  SELECT id, COALESCE(email, ''), owning_organisation_id, 'edit', role, base, after, '', 'migration', now()
    FROM plan
)
UPDATE partner_admins p SET permissions = g.after FROM plan g WHERE p.id = g.id;
INSERT INTO django_migrations (app, name, applied)
SELECT 'courses', '0099_grant_scholars_approve', now()
 WHERE NOT EXISTS (SELECT 1 FROM django_migrations
                    WHERE app = 'courses' AND name = '0099_grant_scholars_approve');
COMMIT;
```
3. Push and move `live` (owner's yes).
4. **After the new api image carries all the traffic:** re-run the DATA block (step 2), then the
   **POST-DEPLOY CHECK** (read-only). It must return ZERO rows; if not, re-run the DATA block only.
```sql
SELECT id FROM partner_admins
 WHERE role = 'org_admin'
   AND jsonb_typeof(permissions) = 'array'
   AND NOT permissions ? 'scholars.approve';
```

⚠ If 0098's DATA block is ever re-run, run 0099's DATA block straight after it, or the key is lost. 0099's
POST-DEPLOY CHECK replaces 0098's equality check from now on.
⚠ Run 0099's DATA block again only as part of this release: from M3c a super may take the key away, and a
later re-run would give it back.

## Owner's phone check (after the publish)

1. As an organisation admin, open a team member's Permissions: a key you do not hold shows a padlock; the
   others can be switched on.
2. As a super, open an organisation admin's Permissions: the Payments row says it comes with the role.
3. As an organisation admin, open the assign picker on a case: the wording says "Never to yourself", and
   choosing yourself (if offered) says "You cannot give a case to yourself."
4. As an organisation admin, open a scholar's file: the suspension and termination letters are offered as before.
5. As an admin granted sponsor approval: you can accept a sponsor into a gift, but the sponsors list shows no
   Approve / Reject for the sponsor account, and the terms page shows no Publish.
6. As an admin who can view Invitations (but not edit), the Mentor tab shows, read-only.
7. Announcements, Surveys and Development tables now use the full console width, like Scholars.
