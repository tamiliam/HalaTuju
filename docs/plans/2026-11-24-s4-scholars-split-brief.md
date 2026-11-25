# Sprint S4 brief (ACCESS-BY-SWITCHES): SCHOLARS-SPLIT, View scholars and Manage scholar files

Branch `access-s4-scholars`, cut from `ed84e1a4b` (S3/M4b merged with `side/laptop`: S1 live; S1b, S2/M4a, #78 and
S3 local, none on main). Written 24 Nov 2026. Programme plan: `~/.claude/plans/tingly-snuggling-tiger.md`, "S4.
SCHOLARS-SPLIT" and owner ruling Q3. Template: `docs/plans/2026-11-23-m4b-sponsor-credits-brief.md`.

**Status: BRIEF ONLY. No code changed.** The build waits for the owner's rulings below (Q-A to Q-F). The data step
(courses 0101) runs only on the owner's yes.

**Services:** both (api + web). **Migration:** courses `0101_grant_scholars_manage` (data only, by hand, owner yes).
**Lands:** with or after S2's courses 0100 (the same release train). S5 (mentor notes) may share the publish.

## Owner rulings that bind this sprint

- **Q3 (19 Nov):** one switch, "Manage scholar files" (`scholars.approve`). It covers every everyday file write AND
  suspension and termination letters. Today's file writers (`scholars` holders) keep their write power: the data step
  gives them the switch, and with it the letters.
- **Groups first, switches second (24 Nov):** switches are powers inside a group; they never decide membership.
- **Q1 (19 Nov):** store what people effectively hold today; nothing changes on day one except a gain the owner names.
- **Permissions, not role labels (15 Nov):** keys decide. No "view-only admin" wording anywhere.

### Owner rulings on this brief (25 Nov, direct, in the Team Work session). These OVERRIDE the questions below

- **Q-A: no.** Surveys and Development do not need View scholars. Close TD-597 as accepted (count 8 = 0).
- **Q-B: yes.** A tranche, release, withhold, return or hold past the award = View scholars (`scholars`) +
  Payments: Prepare. "Manage scholar files" is never a second key to money. Day one: nobody changes (count 6 = 0).
- **Q-C: yes.** Mentor assignment, meetings and lesson review stay on the Mentoring and Development switches.
- **Q-D: falls away.** Count 3: both org admins hold `scholars.approve`.
- **Q-E: OFF.** A newly invited Admin starts with switch 1 ("The scholars page and every scholar's file", now view
  only) ON and "Manage scholar files" OFF; an org admin switches it on. So `ADMIN_PRESET_V2` does NOT gain
  `scholars.approve`; invites, Restore (gives back what was held) and a role switch to admin use the preset as it
  is. This also settles surprise 7's role-switch case: no `ADMIN_SWITCH_V2` is needed. `holds_scholars_key` still
  reads the v2 view key so Manage always brings View.
- **Q-F / reviewers (owner): "Reviewers have nothing to do with scholars. Only admins do, based on permissions
  given them."** So:
  - 0101 grants `scholars.approve` only to rows that hold `scholars` AND sit in Admins (`staff_tables.in_admins`
    on the stored keys; the org admin rows already hold it). Live: 2 `admin` rows + the one reviewer row that sits
    in Admins by ruling O8 (row id 9, by id only). These 3 gain the letters on day one: name the count in the
    phone check, never a name.
  - 0101 REMOVES `scholars` (and any `scholars.approve`, `award_withdraw_request`, `award_withdraw_approve` it
    holds) from every team row that holds it but does NOT sit in Admins. Live: 1 active reviewer, who got it from
    0095 (10 Nov) only because it then held `see_all`. Audit row, kind `edit`, `changed_by_role` 'migration';
    the reverse puts back exactly what this migration took. Their applications work is unchanged.
  - The Permissions editor offers the Scholars row only on a person in Admins (and the org admin); on anyone
    else it is not drawn. The server enforcing "Scholars keys only inside Admins" is S6 (groups first), not S4.
- **Production counts (25 Nov, read-only):** 1: admin 2, org_admin 2, reviewer 2. 2: org_admin 2. 3: admin
  view-only 2, org_admin both 2, reviewer view-only 2 (one of them in Admins). 4: no NULL admin row. 5: 0.
  6: 0. 7: 0. 8: 0. 9: `0099_grant_scholars_approve` only (0100 runs at the 25 Nov 11:00 landing).

## The one principle

After S4 a scholar's file has two powers: **reading** it (`scholars`, shown as "View scholars", the v2
`scholars.view`) and **changing** it (`scholars.approve`, "Manage scholar files"). Every scholar-file write asks
ONE predicate, `base.may_write_file`. Every read keeps asking `scholars_scope` / `holds_scholars_key`. Money stays
on the Payments switches.

## Verified facts (branch `ed84e1a4b`). Re-check each before building on it

### The keys today
- `scholars` is an OLD key (`courses/staff_permissions.py:43`), read by `has_perm`. It is in the admin preset
  (`:86`) and the lead tier (`:99`), and it seats a team member at Admins (`staff_tables.ADMIN_KEYS`, `:47`).
- `scholars.view` is its v2 spelling (`staff_permissions_v2.ALIASES`, `:130`); it is never stored.
- `scholars.approve` is a v2 key (`staff_permissions_v2.py:65`, flagged `LEAD_ONLY`). It IS in `GRANTABLE_V2`
  (not an alias, not never-grantable), so `stored_v2` reads it on a team member's row today, on main as well.
  It implies `scholars.view` (`IMPLIES`); the editor stores that view through the old key `scholars`
  (`VIEW_ALIAS_OLD`, `:187`; `staff_permissions_admin.py:107-110`).
- **The `LEAD_ONLY` flag is data only since M3c (A9).** No code outside tests reads it
  (`staff_permissions_v2.py:235`); an organisation admin may already give `scholars.approve` if they hold it (A12).
  So "stops being lead-only" changes no behaviour. It is needed because `test_m2b_stored_v2` pins "no lead-only key
  in the admin preset", and the preset is about to carry it.
- Organisation admins hold `scholars.approve` through migration 0099 (stored lists) or a NULL row (read as the
  full set, `org_admin_v2`). A super may have unticked it since M3c.

### Reader map (server)

| Where | What it decides today | After S4 |
|---|---|---|
| `views_admin/base.py:60-78` `scholars_scope` | Scholars list and file READ: `scholars` → 'all', else mentor record | Unchanged (View) |
| `base.py:81-84` `holds_scholars_key` | `has_perm('scholars')` (old key) | Unchanged in meaning; **reads the v2 `scholars.view` through `staff_tables.opens`** so Manage brings View on the server too (see "Manage without View" below) |
| `base.py:98-103` `may_write_file` | `holds_scholars_key` + `org_allows` | **`opens_door(admin, 'scholar_files')` (`scholars.approve`) + `org_allows`** |
| `base.py:113-119` `reads_case` | Applications read, or `scholars` + a file | Unchanged (View) |
| `base.py:122-153` `may_write_case` PAST_AWARD (`:146`) | `may_write_file` and `reads_case` | Moves with `may_write_file` (Manage) |
| `base.py:156-169` `may_tranche` | `may_write_case` AND `payments.may_prepare` | **Q-B.** Recommended: past the award, `org_allows` + `reads_case` + `payments.may_prepare`; Manage not needed |
| `base.py:178-192` `served_write_flags` | `can_write`, `can_tranche`... | Follow the two rows above |
| `base.py:405-411` `_can_review_app` / `_may_write_file` | the two predicates | Unchanged (they delegate) |
| Every `_require_app_write` / `_can_review_app` door past the award (34 call sites: `applications.py` 262-593, `profiles.py` 33-167, `lifecycle.py` 108/150/177/204, `resolution.py` 23/49/113, `verdict.py` 240, `pre_interview.py` 34, `guardian_contact.py` 30, `interview_slots.py` 53, `scholars.py` 173) | `scholars` | Manage (through `may_write_case`). Before the award: unchanged |
| `lifecycle.py:201-208` maintenance sub-state, `on_hold` | app write + `payments.may_prepare` | **Q-B**, same as tranches for `on_hold`; other sub-states Manage |
| `views_admin/scholars.py:175-176` file `controls` | `can_review_results`, `can_write_activity` = `_may_write_file` | Manage (served) |
| `scholars.py:238` results review POST | `_may_write_file` | Manage |
| `scholars.py:313` activity note POST | `_may_write_file` | Manage (S5 adds the mentor) |
| `scholar_thanks.py:37-40` `may_decide_thanks` (GET `:66`, POST `:88`) | `_may_write_file` | Manage |
| `letters.py:44-49` `_senior` | `surface_gates.may_send_senior_letters` = door `senior_letters` (`scholars.approve`) | **Deleted**: one rule |
| `letters.py:51-57` `_kinds_for` | senior → every kind; `_may_write_file` → non-senior kinds | `_may_write_file` → every kind (`svc.KINDS`), else none |
| `letters.py:81` `can_withdraw`, `:138` withdraw POST | `_senior` | `_may_write_file` |
| `letters.py:99,120,143` issue, preview, resend | `_kinds_for` | Unchanged (follow `_kinds_for`) |
| `surface_gates.py:130-133` `may_send_senior_letters` | door `senior_letters` | **Deleted** (no other caller) |
| `courses/staff_tables.py:201` door `senior_letters` | `('scholars.approve',)` | **Renamed `scholar_files`**, same key; the web mirror follows |
| `staff_tables.py:265` `INVITE_START['admin']` + `ADMIN_PRESET_V2` | new Admin starts `see_all`, `scholars` + work pages | **Q-E**: + `scholars.approve` |
| `views_admin/mentors.py:257` | Mentors list read: `scholars_scope == 'all'` | Unchanged (View) |
| `development.py:233` per-scholar review, `mentoring.py:85,120` assign / end / log a meeting | their own Engagement switches | **Q-C** (recommended unchanged) |
| `award_withdrawal_chain.py:116-180` | `award_withdraw_*` + the Applications read (`b40_scope == 'all'`) | Unchanged (sits in the Scholars row, reads Applications) |

**Nothing decides a scholar-file write by role label.** The last one (TD-598, `_senior` read `org_admin`) was
converted in M3c; its GATE-LEFT entry is already gone. S4 closes TD-598 in the ledger and deletes the second door.

**Manage without View.** `has_perm('scholars')` reads only old keys, so a row storing `scholars.approve` without
`scholars` could write and not read (`reads_case` false, every past-award write refused). The editor never stores
that shape, but `staff_lifecycle.change_role` does (`:288-295`): a switch TO `admin` keeps the old keys exactly and
adds `ADMIN_PRESET_V2`. Once the preset carries `scholars.approve`, a reviewer switched to Admin would hold Manage
without View. **Decision:** the role switch adds the work pages only (a new frozen `ADMIN_SWITCH_V2`, today's
`ADMIN_PRESET_V2` without `scholars.approve`: a switch never gives a write key), and `holds_scholars_key` reads the
v2 `scholars.view` (Manage implies it), so the server and the editor agree. Count 7 below must be 0.

### Web map

| Where | What it draws from | After S4 |
|---|---|---|
| `lib/permissionLayout.ts:73-75` Scholars row | `sw('scholars')` + 3 subs (withdraw request, withdraw approve, `scholars.approve`) | `INFO` + 4 subs in order (below) |
| `components/admin/PermissionEditor.tsx:83,116` | Payments View locked on while Prepare / Check / Approve on | Same lock for View scholars while Manage is on (generalise `brings`) |
| `app/admin/scholars/[id]/page.tsx:329,359` activity composer | served `controls.can_write_activity` | Unchanged |
| `page.tsx:335` results review | served `controls.can_review_results` | Unchanged |
| `ScholarThanks.tsx:92` | served `may_decide` | Unchanged |
| `ScholarLetters.tsx:126` / `IssueLetterDialog.tsx:39,95,102` | served `can_issue` | Unchanged |
| `ScholarLetters.tsx:201` withdraw | served `can_withdraw` | Unchanged |
| **`ScholarLetters.tsx:167` Resend** | **`!readOnly` = not a mentor (browser-derived)** | **Served `can_resend` (the kinds `_kinds_for` answers, unfiltered by `CLOSED_FILE_KINDS`, as `resend` asks); drawn per letter on `can_resend.includes(l.kind)`** |
| `ScholarControls.tsx:70-85` sub-state, hold | served `can_set_substate`, `can_hold` | Unchanged; but `can_hold` is served as `payments.may_prepare` alone (`apps/scholarship/scholars.py:382,401`) while the door also needs the app write. Serve `can_hold = can_write-or-Q-B-rule and may_prepare` so the offer equals the door |
| `PostAwardPanels.tsx:45-78` | served `can_write`, `can_tranche`, `can_hold` | Unchanged |
| `lib/pageDoors.ts:58` `senior_letters` mirror | — | Renamed `scholar_files` |
| `lib/profileCards.ts:93` `CASE_PERMS` | My activity "Students" chip, display | Unchanged (display; a viewer still has case history) |

Only one control is still derived in the browser: **Resend**. Today it is harmless (every `scholars` holder can
resend a non-senior letter); after S4 a View scholars holder would see it and be refused.

## The Scholars switches: final wording

The row keeps its name ("Scholars") and description ("The Scholars page and every scholar's file."). Its four
switches, in order (en final; ms and ta are drafts **for a native read by Sol**):

| # | Key | en name | en description |
|---|---|---|---|
| 1 | `scholars` (`admin.perm.scholars`) | View scholars | Open the Scholars page and read every scholar's file in this organisation. Read only. |
| 2 | `scholars.approve` (`admin.permLayout.scholarsApprove`) | Manage scholar files | Review results, add activity notes, decide thank-you messages, send and withdraw letters (suspension and termination included), and update or close a scholar's file. Brings View scholars. |
| 3 | `award_withdraw_request` | Ask to withdraw an award | Asks for an award to be withdrawn, with an explanation. A different staff member must approve before anything changes. (unchanged) |
| 4 | `award_withdraw_approve` | Approve award withdrawals | Approves or refuses requests to withdraw an award. Never a request they made themselves. (unchanged) |

**ms (draft, Sol):**
1. Lihat penerima biasiswa — Buka halaman Penerima biasiswa dan baca fail setiap penerima biasiswa dalam organisasi
   ini. Baca sahaja.
2. Urus fail penerima biasiswa — Semak keputusan, tambah nota aktiviti, putuskan mesej terima kasih, hantar dan tarik
   balik surat (termasuk penggantungan dan penamatan), serta kemas kini atau tutup fail penerima biasiswa. Termasuk
   Lihat penerima biasiswa.
3. and 4. unchanged.

**ta (draft, Sol):**
1. உதவித்தொகை மாணவர்களைப் பார்த்தல் — உதவித்தொகை மாணவர்கள் பக்கத்தைத் திறந்து, இந்த நிறுவனத்தின் ஒவ்வொரு
   உதவித்தொகை மாணவரின் கோப்பையும் படித்தல். படிக்க மட்டும்.
2. உதவித்தொகை மாணவர் கோப்புகளை நிர்வகித்தல் — முடிவுகளைச் சரிபார்த்தல், செயல்பாட்டுக் குறிப்புகளைச் சேர்த்தல், நன்றிச்
   செய்திகளை முடிவு செய்தல், கடிதங்களை அனுப்புதல், திரும்பப் பெறுதல் (இடைநிறுத்தல், முடிவுறுத்தல் உட்பட), உதவித்தொகை
   மாணவரின் கோப்பைப் புதுப்பித்தல் அல்லது மூடுதல். "உதவித்தொகை மாணவர்களைப் பார்த்தல்" உடன் வரும்.
3. and 4. unchanged.

Where else the old name "Scholars" (`admin.perm.scholars.name`) shows (People chips, the history list, the
manual), it now reads "View scholars": the builder greps every use and lists them in the CHANGELOG.

## OWNER: questions (plain words, with a recommendation each)

**Q-A (TD-597). Surveys and Development show scholars by name.** Someone with the Surveys or Development switch
but without View scholars can still see each scholar's survey answers, lesson progress and uploads by name on
those pages, though the Scholars page itself stays shut to them. Should those pages also need View scholars?
*Recommended: leave it as it is and close TD-597 as accepted.* Today every admin who has those switches also has
View scholars (count 8 below checks this), and the Permissions tab already warns when they do not. Changing it
would hide names from someone whose job is running a survey. If the count is not 0, decide again with the count.

**Q-B. Payments on a scholar's file.** Today, scheduling or releasing a payment for a scholar, and putting a
scholar's money on hold, needs both the Scholars switch and Payments: Prepare. After S4, should an admin with the
Payments switches need "View scholars" only, or "Manage scholar files" as well?
*Recommended: View scholars plus Payments: Prepare.* Payments is its own page with its own switches (your 18 Nov
ruling), so the file switch should not be a second key to money. Nobody changes on day one either way: today's
holders get both.

**Q-C. Mentoring and Development on a scholar's file.** Assigning or ending a scholar's mentor, logging a meeting,
and reviewing a scholar's lesson work are done from the scholar's tabs but are ruled today by the Mentoring and
Development switches. Do they move to "Manage scholar files"?
*Recommended: no, they stay on their own switches.* They are those pages' own work; moving them would take them
from people who run mentoring without managing files.

**Q-D. An organisation admin whose letters were switched off.** Since 15 Nov a super can switch off "Suspend or end
a scholarship" on an organisation admin. After S4 that same switch is "Manage scholar files", so such an admin
would lose every file change, not only those letters. Should the data step switch it back on for them?
*Recommended: yes, switch it back on, and name each one (by row shape and count, never by name) in the phone
check.* Nobody should lose a write on day one (your Q3 ruling); a super can switch it off again afterwards with its
new, wider meaning. Count 3 below shows whether anyone is in this position; if it is 0, the question falls away.

**Q-E. A newly invited Admin.** Should a newly invited Admin start with "Manage scholar files" on?
*Recommended: yes.* Today a new Admin starts able to change scholar files; your 24 Nov rule says a group's
switches start on. An org admin can switch it off on the person's card.

**Q-F. The day-one gain, named.** Every admin who changes scholar files today also gains, on day one, suspension
and termination letters and withdrawing any letter. Is that the gain you want, as Q3 says?
*Recommended: yes, as Q3 rules; it is named in the phone check with the count of people who gain it (count 1
minus count 2).*

## The data step: courses `0101_grant_scholars_manage` (hand-written, migrate-first, owner yes)

Follows 0097 / 0099 / 0100 exactly: frozen constants (`KEY = 'scholars.approve'`, `VIEW = 'scholars'`,
`ADMIN_PRESET` frozen as 0097's), a `plan_row` the test pins the SQL's WHERE text to, docstring with PRE-CHECK,
DATA block, LEDGER row in the same transaction, POST-DEPLOY CHECK, and a REVERSE.

- **Writes:** append `scholars.approve` to every row whose `permissions` is a JSON array that holds `scholars` and
  lacks `scholars.approve`, **any role** (admin, finance, qc, reviewer custom lists, org_admin lists).
  **Active, revoked, archived and pending alike** (the 0097 amendment and the 0099 / 0100 rule: a later Restore must
  give back what they had). The brief asked for "active rows"; precedent says all rows, and the reverse is exact
  either way. Lead call: follow precedent.
- **A NULL `admin` row** (preset carries `scholars`, but `stored_v2` reads no v2 key on NULL) is materialised as the
  admin preset plus 0097's v2 preset plus the key, audit kind `edit_null`, as 0097. Expected 0 (count 4).
- **NULL org_admin rows:** untouched (read as the full set, which holds the key). Other NULL roles: their presets
  hold no `scholars`; untouched.
- **Audit:** one `staff_permission_changes` row per row changed, kind `edit` (or `edit_null`), before and after,
  `changed_by_email` '', `changed_by_role` 'migration'. Idempotent: a row holding the key is not written.
- **Reverse:** removes the key only from rows whose latest audit row is this migration's (the 0097 rule); an
  `edit_null` row goes back to NULL.
- **Not invisible to the old image.** The live image already reads a stored `scholars.approve` on a team row
  (senior letters through `senior_letters`). So running 0101 opens the senior letters to today's writers at once,
  before S4 serves. **Run it in the same window as the S4 publish, straight before it**, and do the phone check
  then. Re-run rule as 0100: once more after the new image carries all traffic, then never (a super may switch the
  key off from then on).
- **After 0099:** if 0099 is ever re-run, nothing is lost (it only appends to org admin lists).

### Production counts (read-only, lead fills; counts only, no PII)

```sql
BEGIN READ ONLY;
-- 1. active rows holding `scholars` (stored list), by role
SELECT role, count(*) FROM partner_admins
 WHERE is_active AND jsonb_typeof(permissions) = 'array' AND permissions ? 'scholars' GROUP BY role ORDER BY role;
-- 2. active rows holding `scholars.approve` (stored list), by role
SELECT role, count(*) FROM partner_admins
 WHERE is_active AND jsonb_typeof(permissions) = 'array' AND permissions ? 'scholars.approve' GROUP BY role ORDER BY role;
-- 3. the cross: View and Manage held, by role (org_admin with has_view true, has_manage false = Q-D)
SELECT role, permissions ? 'scholars' AS has_view, permissions ? 'scholars.approve' AS has_manage, count(*)
  FROM partner_admins WHERE is_active AND jsonb_typeof(permissions) = 'array'
   AND (permissions ? 'scholars' OR permissions ? 'scholars.approve') GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
-- 4. NULL (or non-list) rows by role; an `admin` here carries `scholars` by preset
SELECT role, is_active, count(*) FROM partner_admins
 WHERE permissions IS NULL OR jsonb_typeof(permissions) <> 'array' GROUP BY 1, 2 ORDER BY 1, 2;
-- 5. inactive rows the DATA block will also write
SELECT role, count(*) FROM partner_admins
 WHERE NOT is_active AND jsonb_typeof(permissions) = 'array'
   AND permissions ? 'scholars' AND NOT permissions ? 'scholars.approve' GROUP BY role ORDER BY role;
-- 6. Q-B: active Payments: Prepare holders without `scholars`
SELECT role, count(*) FROM partner_admins
 WHERE is_active AND jsonb_typeof(permissions) = 'array'
   AND permissions ? 'payments_prepare' AND NOT permissions ? 'scholars' GROUP BY role ORDER BY role;
-- 7. Manage without View (must be 0)
SELECT count(*) FROM partner_admins
 WHERE jsonb_typeof(permissions) = 'array' AND permissions ? 'scholars.approve' AND NOT permissions ? 'scholars';
-- 8. Q-A: team rows with a Surveys or Development key but no `scholars`
SELECT role, count(*) FROM partner_admins
 WHERE is_active AND role <> 'org_admin' AND jsonb_typeof(permissions) = 'array' AND NOT permissions ? 'scholars'
   AND (permissions ?| array['surveys.view','surveys.edit','development.view','development.edit']) GROUP BY role;
-- 9. the ledger
SELECT name FROM django_migrations WHERE app = 'courses' AND name >= '0099' ORDER BY name;
COMMIT;
```

| # | Result (lead fills) |
|---|---|
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |
| 6 | |
| 7 | |
| 8 | |
| 9 | |

## Day-one table ("nobody changes", by row shape)

`test_s4_nobody_changes.py`, the way `test_m3_nobody_changes.py` works: for each shape, build the row as stored
today, apply `0101.plan_row`, and compare every scholar-file flag the old code served (frozen copy of today's
`may_write_file`, `_kinds_for`, `_senior`) with the new code's. Equal, except the named gain.

| Row shape | Today | After 0101 + S4 |
|---|---|---|
| `admin`, list with `scholars` (the preset shape) | every everyday write; no senior letter, no withdraw | same writes; **gains suspension / termination and withdraw** (Q-F) |
| `reviewer` / `qc` / `finance`, custom list with `scholars` (e.g. the person in both Reviewers and Admins) | as above | as above, the same gain |
| team row already storing `scholars.approve` (given since M3c) | everything | unchanged |
| `org_admin`, list with the key (0099), or NULL | everything | unchanged |
| `org_admin`, list without the key (a super switched it off) | everyday writes, no senior | Q-D: everything again (recommended) |
| `admin` NULL | everyday writes (preset) | materialised; same as the preset shape |
| any row without `scholars` | no write | no write |
| super | everything | unchanged |
| mentor login / staff mentor | read only, own students | unchanged (S5 adds notes) |
| Payments: Prepare without `scholars` | no tranche past the award (no read) | Q-B: unchanged (still no read) |

Pins: a row reshaped by hand to View only (`['scholars']`) is refused every write and keeps every read.

## GATE-LEFT and ledgers (may only fall)

- **Server** (`courses/tests/test_role_is_display_only.py`): `GATE_LEFT_PINNED` stays the 10 target rules;
  `lead_gates == 0`. S4 adds no label read and has none to delete (TD-598's went in M3c).
- **Web** (`lib/__tests__/roleIsDisplayOnly.test.ts`): the scholar entries are KIND reads (source / mentor login
  screens) and stay; the `HITS >= 137` floor is not touched. The Resend change removes a derived control, not a
  label read.
- **Query budgets:** `may_write_file` moves from `has_perm` to `opens` (`effective_v2`, which reads the row and
  `in_admins`, no mentor query): no new query. The scholar file detail, letters GET and thanks GET budgets must not
  rise; if one does, find the query, never raise the budget.

## Access-matrix cells to add

- `access_world.py`: `scholars_viewer_a` (`admin`, `['see_all', 'scholars']` + work pages) and
  `scholars_manager_a` (the same + `scholars.approve`), in a new `SCHOLAR_CALLERS`. `admin_a` (factory preset)
  gains the key with the preset; `scholars_only_a` (`['scholars']`) becomes a View holder and its case-stage replay
  cells past the award flip to refused (declared, not silent); add `manage_only_a` (`['scholars.approve']`) to
  `WRITERS_WITHOUT_A_READ` and pin that it reads (Manage brings View).
- `test_access_matrix.py`, `test_scholar_files_open_by_switch` over `SCHOLAR_WRITE_PAIRS` (the scholars/ POSTs:
  results review, activity, letters issue / preview / withdraw / resend, thanks review; plus past-award case writes
  on the funded case: reporting date, sub-state not `on_hold`, close, cancel-decline): viewer refused (403),
  manager allowed, org admin A allowed. The same routes' GETs: both 200. `test_the_scholar_routes_are_served`
  (>= 8 pairs).
- Tranches and `on_hold` (per Q-B): `payments_holder_a` with View scholars allowed, without it refused; the
  viewer without Payments refused.
- `test_team_tables_matrix.py`: the shapes holding `scholars` without the key (`admin_see_all_spending`,
  `reviewer_admin_keys`, `qc_spending` and the reviewer-in-both shape) lose the scholar-file writes; declare them
  in a new `team_matrix_s4.py` (`s4_moved_cells`, as `team_matrix_s1`), and add each shape again with the key to
  prove it equals today's answers. The web `teamTablesMatrix.test.ts` / `teamTablesT5cDoors` follow the door rename.

## Groups first

S4 changes no seat. Everyone given the key already sits at Admins by `scholars` (an `ADMIN_KEYS` key) or is an
organisation admin; a stored `scholars.approve` also seats by `stored_v2`, so `in_admins` answers the same for
every row. "Manage scholar files" is an Admins switch: it is drawn only in the Admins card's Programme box, never on
Reviewers. A person in both groups holds it as an Admins switch, as Sponsors: edit. S4 adds no membership rule;
the stored Admins / Reviewers membership is S6 / S6b, which must seat today's `scholars` holders at Admins.

## Debt

- Close **TD-598** (fixed by M3c, ledger entry still open; S4 makes it one rule).
- **TD-597**: per Q-A.
- New: none expected. If Q-B is answered "Manage too", log nothing; if "View", note in decisions that
  `may_tranche` no longer asks `may_write_case` past the award.

## Out of scope

Mentor notes (S5). Retiring `finance` (S6). Stored group membership (S6b). The withdrawal seats' Applications read.

## Risks

- Migrate-first opens the senior letters before the publish (above): run 0101 in the publish window.
- A role switch to Admin giving Manage without View: closed by `ADMIN_SWITCH_V2` and the v2 read.
- A missed write door: the matrix sweeps every scholars/ POST and the case-stage replay sweeps every past-award door.
- Wording: "Scholars" becomes "View scholars" in other places; the builder lists each.

## Build order

1. Owner rulings Q-A to Q-F; lead fills the production counts.
2. Server: door `scholar_files` (delete `senior_letters`, `may_send_senior_letters`); `may_write_file`;
   `holds_scholars_key` on the v2 view; `letters` collapse (`_senior` gone, `can_resend` served); `may_tranche` /
   `on_hold` per Q-B; `can_hold` served as the door.
3. Presets: `ADMIN_PRESET_V2` + `scholars.approve` (catalogue order); flag `LEAD_ONLY` off for it;
   `ADMIN_SWITCH_V2` for `change_role`; `INVITE_START` per Q-E; factory.
4. Migration 0101 + `test_s4_migration_0101.py` (frozen constants equal live, WHERE text pinned, idempotent,
   exact reverse, inactive rows written, NULL admin materialised).
5. `test_s4_nobody_changes.py`.
6. Matrices (server, then web mirrors).
7. Web: layout row, editor lock, Resend from `can_resend`, door mirror, en / ms / ta strings, tests.
8. Docs: decisions entry, TD-598 close, TD-597 per Q-A, CHANGELOG (ms / ta flagged for Sol), release note with
   the 0101 SQL, CLAUDE.md permission lines.
9. Gates, then an independent review round.

## Gates

- api: full pytest on `/Users/elanjelian/.venvs/halatuju-py311` (pin guard); `test_role_is_display_only`,
  `test_access_matrix`, `T1_WRITE_MATRIX=1 test_team_tables_matrix`, `test_m2b_stored_v2`,
  `test_permission_catalogue_v2`, the M3 / M4a nobody-changes tests green unchanged.
- web: `tsc`, lint, vitest (permissionLayout, PermissionEditor, ScholarLetters, roleIsDisplayOnly, teamTables);
  i18n parity en / ms / ta; mobile-check on the scholar file sandbox (with `.env.local` symlinked in the worktree).
- No budget, floor or ledger raised.

## Phone check (proposed)

1. An Admin with today's preset: open a scholar's file, accept a result, add a note, send a suspension letter
   preview (the NEW power, named), withdraw nothing.
2. Switch off "Manage scholar files" on a test admin: the file opens, every write control is gone (Resend
   included), a POST is refused.
3. Permissions tab: the Scholars row shows the four switches in order; View locks on while Manage is on.

## File budget and hours

About 30 files: api 10 code (base, letters, scholar_thanks docstring, scholars views docstring, lifecycle,
`scholarship/scholars.py`, surface_gates, staff_tables, staff_permissions_v2, staff_lifecycle) + migration 0101 +
8 tests (two new, access_world, factories, three matrices, the pins); web 9 (layout, editor, ScholarLetters,
letters api type, pageDoors, en / ms / ta, tests); docs 4.

| Step | Hours |
|---|---|
| Server gates and presets | 2.0 |
| Migration 0101 and its tests | 2.0 |
| Nobody-changes and matrices | 2.5 |
| Web | 2.0 |
| Strings, docs, release note | 1.0 |
| Review round and fixes | 1.0 |
| **Total** | **10.5** (plan ~10) |
