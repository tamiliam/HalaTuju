# Sprint S2 brief (ACCESS-BY-SWITCHES): M4a, payment runs on keys; the organisation admin powers key

Parent plan: `/Users/elanjelian/.claude/plans/tingly-snuggling-tiger.md` (S2; owner rulings Q1-Q4 of 19 Nov, revised
below). Earlier briefs: `docs/plans/2026-11-14-m3-lead-keys-brief.md` (M3, its data steps 0098/0099 and the
nobody-changes pattern). This is T5d part 1. It touches money and auth.

Worktree `.worktrees/access-s2-m4a`, branch `access-s2-m4a`, cut from main `dbbf1de88`. Rebase on main before each part
ships. Requests lands scholarship migrations 0215-0217 first; S2 adds none, but rebase after them. **Do not push until
the gates below pass and the Opus adversarial review has signed off.** The data step needs the owner's own yes.

## Owner rulings (19 Nov, direct; these replace the plan's Q1-Q4 for this sprint)

- **Q1, org admins.** Verbatim: "Org admins are not invited like other members of Team. They are added by Super Admin in
  the HalaTuju platform. They are special, but their powers must be documented and visible somewhere so that they do not
  fall in a crack, taken for granted. It could be a single Org Admin power switch that is on only for org admins."
  The design (below): ONE new key, **Organisation admin powers**. It is stored on every org admin row and shown on that
  person's Permissions card with a plain list of what it grants. Only a super changes it. Nothing changes on day one. No
  Payments switch is stored on an org admin.
- **Q2, the fallback approver.** Yes. When nobody else can approve a run, anyone with Approve may approve it. That
  includes the person who built it, as long as they did not sign it as maker. The maker never approves their own run. The
  org admin's fallback comes through the new key.
- **Q3, A12 for money.** Yes: an org admin may give only the Payments switches they hold. What this means in practice
  is the one OWNER: line below.
- **Q4, wording.** English approved as written (table below). Malay follows. Tamil is flagged for a native read.

## The one principle

On ship day nobody's seat at Payments, or anywhere else, changes, except the Q2 widening. "Seat" means four things:
- who opens Payments;
- who builds, edits and cancels a run;
- who signs as maker, who checks, who approves;
- when the check step and the fallback switch on.

Every gate reads a key, never a role label. The only role read left is the one that confines the new key to org admin
rows. A nobody-changes test per live row shape proves the seats hold.

## Production counts (19 Nov, read-only, taken by the coordinator)

- 1 organisation, with 2 active org admins. Both are signed in and have stored-array permissions. Neither stores a money
  key, old or v2. One of the two is the owner's own seat, kept for testing; in practice an organisation has ONE org
  admin. S2 adds no rule that enforces one org admin, and 0100 still stores the key on every org admin row.
- Team rows:
  - 2 active admins, both signed in, stored arrays; 1 holds `payments_prepare`.
  - 1 active finance row, signed in, stored array, holds `payments_approve`.
  - No admin or finance row has NULL permissions.
- No payment run in flight. 35 runs in total, 1 of them built by an org admin.
- 1 active super.
- Latest migrations: courses `0099_grant_scholars_approve`, scholarship `0214_document_ocr_text`.

What the counts mean:
- 0100 writes exactly 2 rows (the organisation's org admin and the owner's test seat).
- No team row holds both Prepare and Approve, and no run is in flight, so the Q2 widening touches nobody on day one.
- 0099 already did the org-admin half of S4's planned data step: it stored `scholars.approve` on org admin rows. S4's
  0101 still has to store it on the team rows that hold `scholars`.

## The new key

- **Name:** `organisation.admin`; the label is "Organisation admin powers". I propose it over `org.admin` because no
  catalogue key abbreviates, and the catalogue already spells the scope out (`ORGANISATION`).
- **Where it lives:** in `staff_permissions_v2.py`, next to the hats: `V2_KEYS = (*CATALOGUE_V2, *HATS, ORG_ADMIN_KEY)`
  (:97, :94). It is **outside `CATALOGUE_V2`**, so the page/tier grid, `ALIAS_V2` (:171), `GRANTABLE_V2` (:176) and
  `ORG_ADMIN_V2` (:189) never pick it up. It can therefore never be stored on a team member or given by an org admin
  through the normal machinery, and `v2_order` (:238, which raises on unknown keys) accepts it.
- **Definition:** define the constant in the leaf `staff_permissions.py`, so `resolve` can read it without an import
  cycle, and re-export it from v2.
- **One helper is the only reader:** `staff_permissions.holds_org_admin_powers(admin)`.
  - It answers True for a non-super, `role == 'org_admin'` row whose stored list holds the key.
  - It also answers True when the row is NULL or not a list. This is the same fail-safe as `org_admin_v2` (:269-277):
    a role change writes NULL, and that must not lock anyone out.
  - It answers False for every other row, even one that somehow stores the key.
  - It is a DEFINITION-class lead read, like `lead_reviews`.
  - Every gate below calls this helper; none calls `is_lead_tier` for a power.
- **Who changes it:**
  - Only a super, and only on an org admin card. `may_edit` already lets only a super edit an org admin card (M3c D1).
  - The write path refuses the key on any team row, and from any non-super.
  - New org admin rows get it from `invite_permissions` (`staff_tables.py:252-263`); a role change writes NULL, which
    reads as holding it.
- **Last-holder guard:** unticking the key on the last active org admin of an organisation who holds it is refused. This
  follows the sole-org-admin guard, which never leaves an organisation without its admin (T2 review N4,
  `staff_delete_rules`). Reuse `sole_org_admin_ids`. It guards against zero holders only; it never limits how many org
  admins an organisation has.
- **Where it shows:** the org admin's Permissions card shows it as a switch, with the plain list of what it grants. A
  super can change it. The org admin sees their own card with the switch locked: an own card is already drawn as locked
  controls (`may_edit` :219-228 refuses your own; `PermissionEditor.tsx:320-322`). The list is served from one
  constant, `ORG_ADMIN_POWERS`. A drift test checks that every gate calling the helper is named in the list, and that
  the list names nothing else.

### What `organisation.admin` grants (the plain list; en, approved wording style)

1. Change team members' permissions (`manage_team`).
2. Pay the platform bill (`billing.edit`).
3. Approve requests that commit paid hours (`requests.approve`).
4. Open Payments, and build, edit and cancel payment runs. Never sign one as maker.
5. Approve a payment run when nobody else can. Never one they signed.
6. Vet sponsor accounts and publish sponsor terms for the whole platform. This needs Sponsors: approve as well.

Items 1-3 are the O15 three. Today they are held by role. They move onto the key with no change for anyone, because
every org admin holds the key from day one. S3 adds the credit approver and the Vircle ID correction to this list.

## Every remaining org-admin-only power that reads the role or the lead tier, and the call on each

Source: the two scans in `apps/courses/tests/test_role_is_display_only.py`: `ALLOWLIST` (:103-353) and `LEAD_READS`
(:419-485). Supers' own overrides are left out (they are not org admin powers).

| # | Where | What it does today | Call |
|---|---|---|---|
| 1 | `payments_chain.py` `_is_lead_tier` (:86-89), used in `_may_approve` :226, `may_read` :234, `may_prepare` :240, `_refusal` :272 | Org admin reads, builds and cancels runs, is the fallback approver, and gets the creator-bar exemption | **Move now** (the sprint's core) |
| 2 | `payments_chain.py::fallback_approvers` :199-206 (`role='org_admin'` query :204; GATE-LEFT) | Who gets the fallback | **Move now**: key holders plus Approve holders (Q2), filtered from `org_staff`, which already includes org admins and excludes supers (`staff_permissions.py:226-231`) |
| 3 | `staff_permissions.resolve` :174-176, `LEAD_BY_ROLE = ('manage_team',)` :104 | `manage_team` by role (O15) | **Move now**: added only when the helper says yes. This is two lines and the same pattern as the money. The owner's Q1 words ask for exactly this visibility. |
| 4 | `staff_permissions_v2.effective_v2` :321, `LEAD_BY_ROLE_V2 = NEVER_GRANTABLE` (:166, :200) | `billing.edit`, `requests.approve` by role (O15) | **Move now**: added only when the helper says yes. They stay `NEVER_GRANTABLE`, so no team member can get them. |
| 5 | `staff_permissions_v2` `LEAD_MONEY_UNTIL_M4` :206-207, used :321 | Five display-only money keys by role (TD-620) | **Delete.** The key implies `payments.view` only, so the org admin keeps opening Payments. |
| 6 | `surface_gates.may_approve_platform_sponsors` :108-116 (`sp.is_lead_tier`, PLATFORM class) | Platform-wide sponsor vetting: super or org admin, plus `sponsors.approve` | **Move now**: one line, same pattern. This is not a credit (S3) gate. |
| 7 | `staff_tables.in_admins` :81, `groups_to_leave`, `staff_tables_admin._cheap_refusal` (LEAD_FIXED) | The org admin always sits at the Admins table | **Leave.** This is a table seat for the kind of account, not a power. An org admin with the key off is still listed. |
| 8 | Target rules: `staff_fence` ×3, `staff_delete_rules` ×3, `views_staff` delete/revoke/invite, `staff_tables_admin.may_act`, `views_admin/invitations` cancel, `staff_permissions_admin.may_edit` / `_refuse_target` / `plan_change` | Who may act ON an org admin row (only a super adds, edits or removes one) | **Leave.** These protect the org admin account; they are not powers the org admin holds. The owner's words ("added by Super Admin") confirm them. |
| 9 | `staff_permissions.lead_reviews` :120, `team_holding`, `in_reviewers`, `staff_person.on_reviewer_route` | An org admin joins Reviewers through a stored `review` | **Leave.** It is already a stored key; the role read only says how the row is read. |
| 10 | `lead` badges: `staff_person.person`, `staff_list.list_rows`, `staff_tables_admin.row_fields`, `AdminTeamCandidatesView.get`, `mentors.mentor_rows` | Display | **Leave** (display). |
| 11 | Storage shape: `stored_v2`, `stored_page_keys`, `v2_editor`, `table_keys`, `_plan_add`, `_plan_remove`, `invite_permissions`, `preset_for` | How an org admin row is stored and read | **Leave.** `invite_permissions` gains the key, so its entry stays DISPLAY. |
| 12 | Recipient routing: `emails/payment_mail._instruction_cc` (org admins copied); `send_review_nudges` escalation | Who gets a copy | **Leave.** Receiving mail is not a power. A follow-up could route by the key; not now. |
| 13 | Requests: `views_admin/requests.py` `by_role` audit strings (:304, :368); the internal note refused unless super (:446) | Labels on the record; a super override | **Leave.** The area's gates already read `requests.*` keys (M3b G8). |
| 14 | `credit_steps.step_refusal` (org admin approver), `sponsorship/credits.py` record/cancel, `AdminApplicationDetailView.patch` (Vircle ID) | Credits and the Vircle ID | **S3.** S3 should read `organisation.admin` for any org admin arm and add it to the list. |
| 15 | `finance` role everywhere | | **S6** |

The scans after S2:
- Delete the ALLOWLIST GATE-LEFT `payments_chain.py::fallback_approvers` (:203-204) and its `GATE_LEFT_PINNED` line
  (:524-541).
- Delete the five M4 `LEAD_READS` entries (:452-457) and the PLATFORM `surface_gates` entry (:473-475). Delete them;
  never reclassify.
- Add `holds_org_admin_powers` as DEFINITION.
- Reword the `resolve` (:432-433) and `effective_v2` (:443-444) reasons to "through `organisation.admin`".
- Reword the `plan_change` TARGET reason (:468-469).

## Verified facts (main `dbbf1de88`). Re-check each before building on it; stop and report if one is wrong

### The payment chain: `halatuju_api/apps/scholarship/payments_chain.py` (370 lines)

Team rows keep their old money keys (aliases stand), so the chain keeps reading them. Only the org admin's role reads
change.

| Line | Today | Change |
|---|---|---|
| :59-74 `_holders` | `staff_permissions.holders` (old keys, Python over `org_staff`, cached) | unchanged |
| :86-89 `_is_lead_tier` | `is_lead_tier(admin)` | **Delete** with every use (:226, :234, :240, :272) |
| :92-104 `finance_check_required` | signed-in `payments_check` holders | unchanged (an org admin never holds Check) |
| :111-137 `credit_check_required` | `CHECKER_KEY` holders, no signed-in filter | TD-560 (see Debt) |
| :154-167 `_barred_from_approving` | signers plus creator. The docstring says the fallback ignores the creator bar for the org admin. | Code unchanged; reword the docstring for Q2 |
| :170-190 `eligible_checkers`, `check_required_for`, `eligible_approvers` | old keys, signed in, not barred | unchanged |
| :199-206 `fallback_approvers` | active `role='org_admin'` rows, not signers | Active `org_staff` (the cache) who are not signers and either hold the key or hold `payments_approve` (Q2). No role query. |
| :223-226 `_may_approve` | regular arm, else `_is_lead_tier and approver_fallback` | regular arm, else `approver_fallback(run)` and not a signer and (`holds_org_admin_powers` or `_holds_eligibly(admin, 'payments_approve')`). The creator is allowed (Q2); the maker never is (signer bar). |
| :229-234 `may_read` | any old `payments_*`, or lead tier | any old `payments_*`, or `payments.view` in `stored_v2(admin)` (the new View-only team switch), or the helper. All are read from the loaded row, so no query is added. |
| :237-240 `may_prepare` | `payments_prepare`, or lead tier | `payments_prepare`, or the helper |
| :254 `next_step_for` draft | `has_perm('payments_prepare')` | unchanged: an org admin never signs as maker |
| :271-274 `_refusal` | the creator gets `same_signer` "unless lead tier" | The creator gets `same_signer` only when the fallback is off. Under the fallback, `_may_approve` already says yes. |

A super still passes through `has_perm` as today.

Callers of `may_read` / `may_prepare` follow automatically; run the targeted tests for each:
- `staff_activity_read.py:223`
- `my_pending.py:149`
- `detail_blocks.py:28-30`
- `lifecycle.py:25, 201, 210`
- `views_admin/base.py:159-169`
- `views_admin/scholars.py:174`
- `scholars.py:379`
- `views_admin/payments.py` `_payments_admin` :141-155 (docstring :142-146 names "the organisation admin": reword)
- `emails/payment_mail.py:49`

Reword the `staff_lifecycle.py:20` docstring.

### The key catalogue: `halatuju_api/apps/courses/staff_permissions_v2.py` (324 lines)

- `ALIASES` (:122-137) **stay**: `payments_prepare` → (view, prepare); `payments_check` → (view, check);
  `payments_approve` → (view, approve, `sponsors.check`). Team rows need no data step.
- `ALIAS_V2` (:171) is computed from `ALIASES`; `GRANTABLE_V2` (:176) and `ORG_ADMIN_V2` (:189) exclude it; 26 keys are
  pinned at `courses/tests/test_m2b_stored_v2.py:104`. **Change:** `GRANTABLE_V2` gains exactly `payments.view`, listed
  explicitly so the team View switch can be stored. `ORG_ADMIN_V2` gains nothing, because an org admin stores no
  Payments switch. The pin `GRANTABLE_V2 == ORG_ADMIN_V2` (:116-118) becomes "plus `payments.view`".
- `effective_v2` (:290-324). For an org admin (:321), replace
  `(*org_admin_v2(admin), *LEAD_BY_ROLE_V2, *LEAD_MONEY_UNTIL_M4)` with `org_admin_v2(admin)`, plus, when the helper
  says yes, `(ORG_ADMIN_KEY, *LEAD_BY_ROLE_V2, 'payments.view')`. Delete `LEAD_MONEY_UNTIL_M4` (:202-207) and its pin
  (`test_m2b_stored_v2.py:110-114`).
- No code outside this module reads `payments.prepare/.check/.approve` or `sponsors.check`: grep over `apps/` non-test,
  and the web `src/` outside the sandbox. Losing them from the org admin's effective set is therefore display-only.
  Re-grep before deleting.
- The 0098/0099 pin tests (`scholarship/tests/test_m3_migration_0098.py` :40-43, `test_m3c_migration_0099.py` :31-34)
  compare frozen lists with `ORG_ADMIN_V2`. `ORG_ADMIN_V2` does not change, so they stay green. If `GRANTABLE_V2` is used
  there, exclude `payments.view` the way `M3C_KEYS` is excluded.

### The editor: `halatuju_api/apps/scholarship/staff_permissions_admin.py` (448 lines)

| Line | Today | Change |
|---|---|---|
| :370-372 `LEAD_MONEY_OLD`, :375-385 `_lead_after` | old money spellings on an org admin card raise `money_by_role` | Keep refusing. Also refuse v2 money keys on an org admin card. The code becomes `money_through_org_admin`, a TARGET-class read. Storing an old money key on an org admin row is unsafe: `resolve` keeps it (`clean`) and the old image's `holders()` would count it. |
| new | | Refuse `organisation.admin` on a team row and from a non-super. Refuse unticking it from the last holder in an organisation. |
| :150-159 `not_held` | counts only `ORG_ADMIN_SET` keys, so an org admin may give any old money key today | A12 for money (Q3); see the OWNER: line |
| :286-322 `consequences` | old-key money codes (:294-305), `CREDIT_CHECK_ON`, `PREPARE_AND_APPROVE` (:315) | Add `ORG_ADMIN_POWERS_OFF`, which lists what unticking the key takes away. `FALLBACK_ON` is now "nobody left can approve". |

### Seating, doors, work lists

- `staff_tables.py`:
  - add the door `payments_read: ('payments.view',)` to `DOOR_KEYS` (:159-202);
  - `in_admins` (:76-87) seats a team member with a stored `payments.view` through `stored_v2`, already (:87);
  - `invite_permissions` (:252-263) adds `ORG_ADMIN_KEY` for an org admin.
- `staff_work.py` :101-104 (`ADMIN_WAITING`, `'payments_prepare'`) and `staff_lifecycle.runs_in_progress` (:176-184):
  unchanged (old key). The org admin's waiting card comes from `may_prepare`; check its callers.
- `programme_overview.py` `MONEY_KEYS` (:78, old keys): add the key's Payments reach, or read
  `payments.view` through `effective_v2`. **839 lines = its ledger limit 819 + growth allowance 20: net change zero or
  negative.**
- `staff_tables_admin.py` :369 `consequences` is not gated on `live` (:353) (TD-614).
- `credit_steps.py:34` `CHECKER_KEY = 'payments_approve'`: unchanged (S3).

### Web (`halatuju-web/src`)

| File:line | Today | Change |
|---|---|---|
| `lib/permissionLayout.ts:76-77` (98 lines) | Payments is an INFO row (:48) of `oldSub(payments_prepare/check/approve)` | A team card gets four toggles: View (`payments.view`), Prepare (`payments_prepare`), Check (`payments_check`), Approve (`payments_approve`). View is locked on while any other is on. |
| `components/admin/PermissionEditor.tsx:86` (412 lines), :343 | `BY_ROLE_ROWS = { payments: ...byRole }` | An org admin card shows the "Organisation admin powers" toggle (super only) with its served list. The Payments row there reads "Comes with Organisation admin powers" and has no toggles. Delete `BY_ROLE_ROWS`. |
| `components/admin/PermissionBox.tsx:141-186` (211 lines) | the byRole branch | Reuse it for the org admin powers line, or delete it |
| `app/admin/payments/[id]/page.tsx:81` (552 lines), uses :232, :326 | `isFinanceViewer = effectiveRole(role) === 'finance'` | A served `can_open_applicant` (`b40_scope(admin) == 'all'`, `views_admin/base.py:32-55`; equal today for every preset) |
| `app/admin/payments/page.tsx:51` (418 lines) | `canPrepare ?? r !== 'finance'` | `canPrepare === true` (served) |
| `lib/navigation.ts:275-281` (581 lines; 19 lines of headroom) | `roles: ['org_admin']`, `perms: [3 old keys]` | `door: 'payments_read'` |
| `lib/pageDoors.ts` (74 lines) | the `DOOR_KEYS` mirror | Add `payments_read: ['payments.view']` |
| `sandbox/servedKeys.ts` and any `V2_KEYS` mirror | | Add `organisation.admin` (the drift tests will name the files) |
| `messages/{en,ms,ta}.json` | `byRole`, the INFO description | The new strings (below); delete `byRole` |

Move the web tests that set the `finance` role to served flags:
- `payments/page.test.tsx`
- `payments/page.url.test.tsx`
- `payments/[id]/page.signOff.test.tsx`
- `spending/page.test.tsx:870-871`

Keep one case proving a role string alone opens nothing.

Approved English (Q4):

| Toggle | Label | Help |
|---|---|---|
| View | View payment runs | See runs and their funding. Cannot change them. |
| Prepare | Prepare payment runs | Build a run and sign it as the maker. |
| Check | Check payment runs | An optional middle check before approval. Turning it on for anyone who has signed in adds the step to every run. |
| Approve | Approve payment runs | Releases payments from Vircle to students. Never on a run they prepared or built. Also checks sponsor credits. |
| Organisation admin powers | Organisation admin powers | Set by HalaTuju for the organisation's admins. Only HalaTuju can change it. (Then the plain list above.) |

The Approve help says "or built", which is not quite true after Q2: a builder who did not sign may approve when nobody
else can. Under Q4 the wording stands as approved. The builder must not reword it; the review notes it for the owner.

Malay: "Lihat / Sediakan / Semak / Luluskan larian pembayaran", plus "Kuasa pentadbir organisasi"; drafted, then read.
Tamil: drafted from the existing `perm` strings, then a native read before publish. Two Tamil terms for "payment runs"
are in use today ("கட்டண இயக்கங்கள்" and "கொடுப்பனவுச் சுற்றுகள்"); the read settles one.

### How keys are stored, and the nobody-changes pin

- Old keys and v2 keys share `PartnerAdmin.permissions` (JSONB, `partner_admins`). NULL means the role's preset; for an
  org admin, NULL means the full set (`resolve` :174-176, `org_admin_v2`).
- Old-image safety for the new key:
  - `clean` keeps only `CATALOGUE` keys, so it drops it;
  - `org_admin_v2` reads only `ORG_ADMIN_V2` keys, so it ignores it;
  - `stored_v2` answers none for an org admin.
- **`apps/scholarship/tests/test_m3_nobody_changes.py` (242 lines) stays green, with two edits and no seat exceptions.**
  - Its `migrate()` (:123-130) gains M0100.
  - Its `read()` compares `effective_v2` and `page_keys` (:150). For the org admin shapes these now differ, by exactly
    `-payments.prepare, -payments.check, -payments.approve, -sponsors.check` and `+organisation.admin`. That is the
    deletion of `LEAD_MONEY_UNTIL_M4` (TD-620): four keys nothing reads, plus the new key.
  - The test gets one named constant, `M4A_DISPLAY_ONLY`, applied to org admin shapes only.
  - Everything that decides a seat compares equal unchanged: doors, "may_approve a run", the `HOLDER_KEYS` holders,
    `fallback_approvers`, `approver_fallback`, `finance_check_required` (:155-162).
  - The one owner-ruled seat change (Q2) shows only for an Approve holder who built a run they did not sign. If the
    test's world has one, list it by name next to the Q2 ruling; otherwise nothing more changes.
- Factory: `scholarship/tests/factories.py:297` `make_admin` builds the production shape through 0098/0099 `plan_row`.
  Add 0100's `plan_row` and a `pre_m4a=True` flag. Test files are not size-capped.

## Day-one table

| Row (production count) | After 0100 | Day one |
|---|---|---|
| org admin, stored array (2) | + `organisation.admin` | unchanged: reads Payments; builds, edits and cancels runs (never as maker); approves only when nobody else can; manages the team; pays the bill; approves requests; vets platform sponsors |
| org admin, NULL or not a list (0) | untouched; reads as holding the key | as above |
| new org admin (a super adds; invitation or role change) | `invite_permissions` adds the key; a role change writes NULL | as above |
| admin with `payments_prepare` (1) | untouched (alias) | unchanged: reads, builds, signs as maker |
| admin without money (1) | untouched | unchanged: no Payments |
| finance with `payments_approve` (1) | untouched (alias) | unchanged. Q2 adds approving a run they built but did not sign when nobody else can; they cannot build, so no effect. |
| team `payments_check` holders (0 known) | untouched | unchanged |
| qc, reviewer, member | untouched | unchanged |
| super (1) | untouched | unchanged; holds every key |

No row stores a Payments switch it did not have. The only new stored value is the key, on 2 rows.

## OWNER: ruled (19 Nov)

**RULED (owner, 19 Nov): as recommended. For GIVING only, Organisation admin powers count as holding Payments View,
Prepare and Approve, never Check, so an org admin still staffs Payments and only a super gives Check.** (Was the one
unruled point: with Q3 an org admin holds no Payments switch, so A12 would have stopped them giving any.)

**Also ruled (owner, 19 Nov): the Approve help text is "Releases payments from Vircle to students. Never on a run they
signed as maker. Also checks sponsor credits."** It replaces the "prepared or built" text in the Approve row below;
the Malay and Tamil strings follow it (Tamil flagged for a native read).

## The data step: `courses/0100_store_org_admin_powers` (owner yes)

- **Number:** latest courses `0099_grant_scholars_approve`; 0100 is free on main and in every worktree. No scholarship
  migration; Requests' 0215-0217 land first. If Requests adds a courses migration, renumber.
- **Content:** this is the only thing 0100 does. It is hand-written and copies 0099 (don't import):
  - a frozen `KEY = 'organisation.admin'`;
  - a pure `plan_row(permissions) -> after | None`;
  - `RunPython` forward and reverse;
  - a DATA block of plain SQL: one transaction, idempotent, the `django_migrations` ledger row included.
- **Rows:** `role = 'org_admin'` whose `permissions` is a JSON array, in any lifecycle state. APPEND the key when it is
  missing; never remove anything. Write one `staff_permission_changes` audit row per changed row (kind `edit`,
  `changed_by_role 'migration'`, `changed_by_email ''`, copying 0099's INSERT). NULL rows, non-array rows and team rows
  are untouched.
- **Migrate first, under the OLD image.** This is safe because the old image ignores the key (see above). Before trusting
  that, grep main for any raw read of `permissions` that passes an unknown key to `v2_order` (which raises), and land
  `test_m4a_migration_0100.py` with a case that reads a keyed row through today's readers.
  The reverse order is not safe: the new image reading an array row without the key would take every listed power away.
- **Window rule:** between the migration and 100% traffic on the new image, nobody edits an org admin's card. An
  old-image save writes `ORG_ADMIN_SET`, which drops the key. Re-run the DATA block once the new image carries all
  traffic, then never again: from S2 a super may untick the key, and a later re-run would give it back. This is the
  0099 rule.
- **Reverse:** remove the key only from rows whose `permissions` still equals 0100's `after`.
- **PRE-CHECK:** Q12 returns `0099_grant_scholars_approve`; Q1 shows 2 array rows without the key.
- **POST-DEPLOY CHECK:** 0 org admin array rows without the key; 0 non-org-admin rows storing it; 0 org admin rows
  storing any money key.
- **Test:** `scholarship/tests/test_m4a_migration_0100.py`, as `test_m3c_migration_0099.py`:
  - the frozen key equals the live one;
  - idempotent;
  - NULL and team rows untouched;
  - the audit row;
  - the reverse touches only rows still holding `after`;
  - the DATA SQL's WHERE matches `plan_row`.

### Read-only counts, before and after (not run by me; counts only)

```sql
BEGIN READ ONLY;
-- Q1 org admin rows by state, shape, the new key and any money key stored
SELECT is_active, (archived_at IS NOT NULL) AS archived, (first_seen_at IS NOT NULL) AS signed_in,
       CASE WHEN permissions IS NULL THEN 'null'
            WHEN jsonb_typeof(permissions) <> 'array' THEN 'not_array' ELSE 'array' END AS shape,
       (jsonb_typeof(permissions) = 'array' AND permissions ? 'organisation.admin') AS has_key,
       (jsonb_typeof(permissions) = 'array' AND permissions ?| array['payments_prepare','payments_check',
            'payments_approve','payments.view','payments.prepare','payments.check','payments.approve',
            'sponsors.check']) AS has_money,
       count(*)
  FROM partner_admins WHERE role = 'org_admin'
 GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY 1, 2, 3, 4, 5, 6;
-- Q2 non-org-admin rows storing the new key (expect 0 before and after)
SELECT count(*) FROM partner_admins
 WHERE role <> 'org_admin' AND jsonb_typeof(permissions) = 'array' AND permissions ? 'organisation.admin';
-- Q3 team rows by role, state, shape and each old money key stored (NULL = the role's preset)
SELECT role, is_active, (first_seen_at IS NOT NULL) AS signed_in,
       CASE WHEN permissions IS NULL THEN 'null'
            WHEN jsonb_typeof(permissions) <> 'array' THEN 'not_array' ELSE 'array' END AS shape,
       count(*) FILTER (WHERE jsonb_typeof(permissions) = 'array' AND permissions ? 'payments_prepare') AS prepare,
       count(*) FILTER (WHERE jsonb_typeof(permissions) = 'array' AND permissions ? 'payments_check') AS check_,
       count(*) FILTER (WHERE jsonb_typeof(permissions) = 'array' AND permissions ? 'payments_approve') AS approve,
       count(*) AS total
  FROM partner_admins WHERE role IN ('admin', 'finance', 'qc', 'reviewer', 'member')
 GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4;
-- Q4 rows of any role storing a v2 money key (expect 0 before; after, team payments.view only)
SELECT role, count(*) FROM partner_admins
 WHERE jsonb_typeof(permissions) = 'array'
   AND permissions ?| array['payments.view','payments.prepare','payments.check','payments.approve','sponsors.check']
 GROUP BY role ORDER BY role;
-- Q5 active team rows storing BOTH prepare and approve (who the Q2 widening can reach)
SELECT count(*) FROM partner_admins
 WHERE is_active AND role <> 'org_admin' AND jsonb_typeof(permissions) = 'array'
   AND permissions ? 'payments_prepare' AND permissions ? 'payments_approve';
-- Q6 organisations whose check step is armed today
SELECT count(DISTINCT owning_organisation_id) FROM partner_admins
 WHERE is_active AND first_seen_at IS NOT NULL AND role NOT IN ('org_admin', 'super')
   AND jsonb_typeof(permissions) = 'array' AND permissions ? 'payments_check';
-- Q7 in-flight payment runs by status
SELECT status, count(*) FROM payment_runs
 WHERE status IN ('draft', 'admin_signed', 'finance_checked') GROUP BY status ORDER BY status;
-- Q8 runs (any status) built by an org admin of the run's organisation
SELECT r.status, count(*) FROM payment_runs r
  JOIN partner_admins p ON lower(trim(p.email)) = lower(trim(r.created_by))
                       AND p.role = 'org_admin' AND p.owning_organisation_id = r.organisation_id
 GROUP BY r.status ORDER BY r.status;
-- Q9 organisations by CHECKER_KEY holders signed in or never (TD-560)
SELECT (signed > 0) AS any_signed_in, (never > 0) AS any_never, count(*) AS organisations
  FROM (SELECT owning_organisation_id,
               count(*) FILTER (WHERE first_seen_at IS NOT NULL) AS signed,
               count(*) FILTER (WHERE first_seen_at IS NULL) AS never
          FROM partner_admins
         WHERE is_active AND role NOT IN ('org_admin', 'super')
           AND ((jsonb_typeof(permissions) = 'array' AND permissions ? 'payments_approve')
                OR (role = 'finance' AND permissions IS NULL))
         GROUP BY owning_organisation_id) t
 GROUP BY 1, 2 ORDER BY 1, 2;
-- Q10 in-flight sponsor credits (TD-560 changes when their check is required)
SELECT status, count(*) FROM sponsor_donations
 WHERE status IN ('draft', 'admin_signed', 'finance_checked') GROUP BY status ORDER BY status;
-- Q11 organisations by active org admins
SELECT n AS org_admins, count(*) AS organisations
  FROM (SELECT owning_organisation_id, count(*) AS n FROM partner_admins
         WHERE role = 'org_admin' AND is_active GROUP BY owning_organisation_id) t
 GROUP BY n ORDER BY n;
-- Q12 last migrations (expect courses 0099_grant_scholars_approve before, 0100_store_org_admin_powers after)
SELECT app, max(name) FROM django_migrations WHERE app IN ('courses', 'scholarship') GROUP BY app ORDER BY app;
-- Q13 active supers
SELECT count(*) FROM partner_admins WHERE role = 'super' AND is_active;
ROLLBACK;
```

## Maker-checker after S2, and the tests to add

The rules, all in `payments_chain.py` under `sign`'s `_lock(run)`:
1. Only a `payments_prepare` holder signs a draft (maker). An org admin never does.
2. Nobody signs twice.
3. Check: a signed-in Check holder who neither signed nor built the run. The step exists only if such a person exists.
4. Approve: a signed-in Approve holder who neither signed nor built the run.
5. Fallback, only when rule 4 finds nobody: a key holder, or an Approve holder, who has not signed. The builder is
   allowed (Q2).
6. A super acts anywhere, once per run.
7. Two different people always sign.

New `scholarship/tests/test_m4a_maker_checker.py` (the manifest's `_about`, `access_manifest.json:2`, leaves these to M4):
- The maker cannot check or approve their own run (`same_signer`), at the service and at `PaymentRunSignView`.
- The builder who did not sign cannot approve while another eligible approver exists, and can under the fallback (Q2).
- A person with Check and Approve who checked a run cannot also approve it.
- The fallback:
  - is on when the only Approve holder signed;
  - is off once another signed-in Approve holder appears;
  - never lets the maker approve.
- The org admin:
  - builds but cannot sign as maker;
  - approves only under the fallback;
  - with the key unticked, cannot read, build or approve, and is not in `fallback_approvers`.
- A role alone opens nothing:
  - an `org_admin` row without the key cannot reach any of the six listed powers;
  - a `finance` row whose stored list lacks `payments_approve` cannot approve.
- A View-only team member opens Payments and cannot build or sign.
- A super acts once.

New `scholarship/tests/test_m4a_org_admin_powers.py`:
- The key is never stored on a team row: the write path refuses it, and a stored one is ignored.
- Only a super sets or clears it.
- A NULL org admin row reads as holding it.
- The last holder in an organisation cannot lose it.
- `invite_permissions` carries it.
- Each of the six powers turns off with the key.
- The `ORG_ADMIN_POWERS` drift test.

The access matrix: in `access_manifest.json` (6477 lines), the payment-run rows (:2835-2970) move from labels to keys.
Add three callers rather than renaming `finance_a`, which has 46 entries plus `access_world.py` :52 and :323; S6
removes `finance_a`:
- `payments_holder_a`: an admin with Approve only;
- `payments_viewer_a`: View only;
- `oa_unkeyed_a`: an org admin with the key off.

Seed them in `access_world.py` (464 lines) next to `admin_granted_a` (:310-315). In `test_access_matrix.py`,
`GRANTED_DIFFERS` (:279-301, comment :275) drops its payment entries.

The payment goldens:
- `test_permission_combinations.py` (338 lines): changes only where Q2 applies, named in the commit;
- `test_a38_money_goldens.py` (538 lines): **must not change**.

## Debt

- **TD-560** (`docs/technical-debt.md:8709`). The wallet credit check counts a never-signed-in `payments_approve` holder.
  - Fix in `credit_check_required` (:111-137): add the `_signed_in` filter.
  - Keep `consequences` `CREDIT_CHECK_ON` and `staff_lifecycle.other_active_checker` (:187-194) in step.
  - It changes when a credit's check is required. Q9/Q10 size it; name any organisation it moves in the report. The
    production counts show all three money holders signed in, so expect none.
- **TD-605** (:8811). Run create and the maker sign do not lock the actor's `PartnerAdmin` row.
  - `create_run` (`payments.py:373-405`) and the draft sign first `select_for_update` the actor's row, re-read
    `may_prepare` / `next_step_for`, then lock the run.
  - `payments.py` is 588 lines and not in the ledger, so it has 12 lines of headroom. Put the helper in
    `payments_chain.py`.
  - One lock order everywhere: actor row, then run. Check the editor's apply lock (`staff_tables_admin.py:480-490`).
  - Test: a Prepare (or the key) taken away inside the lock refuses.
- **TD-614** (:8936, which says ~359; the line is :369). Gate the money `consequences` in `plan_table_change` on `live`
  (:353), and test that an inactive member's removal shows none.
- TD-620 closes with `LEAD_MONEY_UNTIL_M4`; TD-629 with `LEAD_MONEY_OLD`'s rewording. `test_technical_debt_register.py`
  passes with each entry closed the register's way.

## Out of scope

- S3:
  - credits and `credit_steps` (`CHECKER_KEY` stays);
  - `sponsors.check` (stays an alias, never stored);
  - `sponsorship/credits.py`;
  - the Vircle ID correction;
  - `lib/sponsorDetail.ts`.

  Each org admin arm there should read `organisation.admin` and join the list.
- S6: the `finance` role, its preset, invitations and `finance_a`. Note for S6: there are no NULL finance rows today
  (counts), but S6 still writes `payments_approve` before any role change, in case one appears.
- Payment-mail routing by key (row 12 above), as a possible later tidy.

## Phases, files, size risks

Part 1, API:
- `courses/staff_permissions.py` (283 lines): the key constant, the helper, `resolve`.
- `courses/staff_permissions_v2.py` (324): `V2_KEYS`, `ORG_ADMIN_POWERS`, `GRANTABLE_V2`, `effective_v2`, deleting
  `LEAD_MONEY_UNTIL_M4`.
- `courses/staff_tables.py` (263): the door, `invite_permissions`.
- `scholarship/payments_chain.py` (370), `payments.py` (588, 12 lines of headroom).
- `staff_permissions_admin.py` (448).
- `staff_tables_admin.py` (558, 42 lines of headroom).
- `surface_gates.py`.
- `programme_overview.py` (839 lines, no growth room).
- `views_admin/payments.py` (416).
- The docstrings in `staff_lifecycle.py` and `payment_mail.py`.
- Migration `courses/migrations/0100_store_org_admin_powers.py`.

Part 1 tests:
- New: `test_m4a_maker_checker.py`, `test_m4a_org_admin_powers.py`, `test_m4a_migration_0100.py`.
- Edited:
  - `test_m3_nobody_changes.py`, `test_m2b_stored_v2.py`, `test_role_is_display_only.py`;
  - `test_access_matrix.py`, `access_world.py`, `access_manifest.json`;
  - `test_permission_combinations.py`, `factories.py`;
  - where they set lead or finance seats: `test_payments.py`, `test_payment_endpoints.py`,
    `test_payment_programme.py`, `test_payment_declarations.py`, `courses/tests/test_permission_presets.py`.

Part 2, web:
- `lib/permissionLayout.ts`, `components/admin/PermissionEditor.tsx`, `PermissionBox.tsx`;
- `lib/navigation.ts` (581 lines, 19 lines of headroom, net negative), `lib/pageDoors.ts`, `sandbox/servedKeys.ts`;
- the two payments pages;
- `messages/{en,ms,ta}.json`;
- their tests.

Size: API sources cap at 600 lines unless in the `oversize_files` ledger (13 entries, growth allowance 20). The web caps
at 600 with the same allowance. **Never raise a ledger or a budget.** If a file would cross, split it.

Query budgets (`code-standards.json` `_admitted`, e.g. `my-pending` finance-1-run = 9):
- every new read is from the loaded row;
- `fallback_approvers` filters the cached `org_staff`, so it adds no query and may save one.

## Gates

1. Targeted tests while building:
   - the three new `test_m4a_*` files, `test_m3_nobody_changes.py`, `test_m2b_stored_v2.py`;
   - the 0098/0099 pin tests;
   - `test_permission_combinations.py`, `test_a38_money_goldens.py` (unchanged);
   - `test_access_matrix.py`, `test_role_is_display_only.py`, `test_technical_debt_register.py`, `test_code_standards.py`.
2. The full API suite through the queue, once, before the push:
   `python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <suite command, -n auto>`.
3. `python manage.py check`; `python manage.py makemigrations --check` (clean: 0100 is data only).
4. Web, through the queue: `npm run gates`, `npm run bundle-budget -- --gate`, `mobile-check` (the editor and the payments
   pages).
5. An Opus adversarial review of the whole diff before the push. It covers:
   - no power reads a role;
   - the key can't reach a team row or be given by an org admin;
   - no money key on an org admin row;
   - check arming;
   - fallback and builder;
   - the last-holder guard;
   - migrate-first safety;
   - lock order.
6. The data step:
   1. the owner's yes;
   2. the PRE-CHECK;
   3. migrate first;
   4. the window rule;
   5. the single re-run;
   6. the POST-DEPLOY CHECK.
7. The owner's phone check before publish is called done.

## Commit plan (one combined publish)

1. `feat(api): migration 0100 stores Organisation admin powers on org admin rows`: the migration and its test, including
   the old-readers case. Trailer `Migration: courses 0100 (additive data)`.
2. `feat(api): payment runs and the org admin's powers read keys, not the role (M4a)`: the key, the chain, the
   catalogue, the editor, the doors, the debt fixes and the API tests.
3. `feat(web): Payments toggles and the Organisation admin powers line; payments pages read served flags`.

Trailers on the last commit:

```
Phone-check: <the steps below, one line>
Migration: courses 0100 (additive data)
Services: both
```

Release order:
1. The owner's yes.
2. The read-only counts.
3. 0100 under the old image.
4. Deploy the API and web together.
5. Re-run the data step once at 100% traffic.
6. The post-deploy counts.
7. The owner's phone check.

## Phone check (the owner, on a phone, after publish, from the owner's own org admin seat)

1. Open your own Permissions card. "Organisation admin powers" is on and locked, with its six-line list. The Payments
   row says "Comes with Organisation admin powers" and has no toggles.
2. Open the card of the team admin who holds Prepare. Payments shows four toggles (View, Prepare, Check, Approve), with
   View and Prepare on. If the OWNER: line is ruled as recommended, Check is locked for you and the other three can be
   changed: untick Prepare, save and reload, and it stays off; tick it back and save. If it is ruled the other way, all
   four are locked for you.
3. Open Payments. "New run" is there. Build a small test run. It opens as a draft, waiting for a maker, with no
   sign-as-maker button and no Approve button for you.
4. Cancel the test run. It shows as cancelled; nothing was paid.
5. Open Team. Your seat is still at the Admins table, and nobody else's card changed.

## Hours

The plan says ~12h. Estimate: **about 14h**:
- the key, helper and catalogue: 2h;
- the chain and Q2: 2h;
- the editor and the last-holder guard: 2h;
- web toggles, card and strings: 2.5h;
- 0100 and its test: 1.5h;
- maker-checker, org-admin-powers and matrix tests: 2.5h;
- three TD fixes: 1.5h.

That is less than the earlier 16h: no v2 holder sets, and nothing new to store on team rows. Log actual agent run times
and lead time as the work happens.

## Where the plan was wrong against the code

1. Storing `LEAD_MONEY_UNTIL_M4`'s five keys on org admins would have changed behaviour once gates read them: maker,
   check arming, regular approver, credit checker. The owner's ruling replaces it with one key and no stored switch.
2. `test_m3_nobody_changes.py` cannot stay green byte for byte. Its `effective_v2` / `page_keys` comparison for org
   admin shapes moves by four display-only keys plus the new key. Every seat comparison stays equal.
3. Storing keys on `finance` and `admin` rows is unnecessary while the aliases stand. The production counts confirm there
   are no NULL admin or finance rows.
4. `ALIAS_V2` drives `GRANTABLE_V2` / `ORG_ADMIN_V2` / `ORG_ADMIN_SET`. Dropping the aliases would put Check into every
   NULL read and every invitation, so the change is explicit (team `payments.view` only).
5. The plan omits these:
   - `BY_ROLE_ROWS` and the `byRole` strings;
   - `_refusal`'s lead clause;
   - `invite_permissions`;
   - `not_held`;
   - the O15 three and `may_approve_platform_sponsors` (role-held powers outside Payments);
   - `programme_overview.py` having no growth room;
   - the docstrings in `_barred_from_approving`, `_payments_admin` and `staff_lifecycle.py:20`.
6. TD-560 is the wallet credit check, though its fix is in `payments_chain.py`. TD-605's register text is the actor-row
   lock, not "the waiting check".
7. Line numbers:
   - TD-614 is at `staff_tables_admin.py:369` (the register says ~359);
   - `LEAD_MONEY_OLD` is at :372;
   - `_is_lead_tier` is at :86.
8. "`finance_a` becomes `payments_holder_a`" is 46 manifest entries plus the world; the brief adds key callers instead.
9. "The payment golden tests" are `test_permission_combinations.py` (changes only for Q2) and `test_a38_money_goldens.py`
   (no change).
