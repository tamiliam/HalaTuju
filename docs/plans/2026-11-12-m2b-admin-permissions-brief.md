# Sprint M2b brief: admin permissions become stored v2 keys

Parent brief: `docs/plans/2026-11-11-m2-team-pages-brief.md` (M2a is live at main 4728cc534; this is its M2b part).
Owner rulings: O8, O13 (T5g-lite), O15, U1-U5 in `docs/decisions.md`. Build on main 4728cc534 or later.

## The one principle

On the day M2b ships, **nobody's pages change except Rohini's** (O8). Every power the `admin` and `finance` role
LABELS give today becomes a STORED v2 key first (the data step), and only then does the code stop reading the label.
Any test that shows a page opening or closing for an existing person (other than row 9) is a bug in M2b.

## Production facts (read-only probe, 2026-11-12, counts only)

- Active `admin` rows: 2, both with a STORED list (none on the preset, NULL). Active `finance` rows: 1, stored list.
- Rohini's row: **id 9**, role `reviewer`, active, 4 stored keys (she sits in Admins through an old admin key). The
  owner confirms id 9 before the data step. Never write her name in the repo; the migration names the id only.
- No schema change is needed: v2 keys go in the same `PartnerAdmin.permissions` JSON list.

## Verified facts (main 4728cc534) — re-check each before building on it; stop and report if one is wrong

- `staff_permissions_v2.py`: `CATALOGUE_V2` (key → group, table, level, LEAD_ONLY flag), `ORG_READ_V2 =
  staff_tables.DOOR_KEYS['org_read']`, `ADMIN_WORK_V2 = staff_tables.DOOR_KEYS['admin_work']`, `TABLE_GRANTS =
  {ADMINS: ORG_READ_V2}`, `LABEL_GRANTS = {'admin': ADMIN_WORK_V2}`, `effective_v2(admin)` (~line 194).
- `staff_tables.py:51` `ADMIN_ROLES = ('admin', 'finance')`; `in_admins` (line 70) seats by label OR `admin_keys`.
  `tables()` returns `()` for an inactive row (keep).
- `staff_permissions.clean` drops unknown and v2 keys — so the OLD image, reading a list that now holds v2 keys,
  ignores them (0095 precedent). This is what makes migrate-first safe.
- `asked_set` lives in `apps/scholarship/staff_permissions_admin.py:67-90`; the GET/PATCH endpoint is
  `admin/admins/<id>/permissions/` in `views_admin/staff.py:118-180`.
- Add / Remove to Admins: `staff_tables_admin._plan_add` (`ADD_KEYS`) and `_plan_remove` / `table_keys`.
- The last courses migration is 0096; this sprint's is **0097**. Pattern: `0095_grant_scholars_key.py` (RunPython,
  an audit row with `changed_by_role='migration'`, reversible).

## Decisions taken by the architect (do not re-open; flag if one cannot hold)

| # | Decision |
|---|----------|
| D1 | Storage: v2 keys in `PartnerAdmin.permissions`, mixed with old keys. No new field, no schema migration. |
| D2 | New `stored_v2(admin)` in `staff_permissions_v2` (a leaf; no new imports into it). NULL list → no v2 keys. |
| D3 | `NEVER_GRANTABLE = {'billing.edit', 'requests.approve'}` (plus `manage_team`, already lead-only). Refused with its own error code. Other LEAD_ONLY keys are refused too until M3 (existing code path). |
| D4 | `ADMIN_PRESET_V2 = ORG_READ_V2 + ADMIN_WORK_V2` (invitations.view, team.view, sources.view/edit, sponsors.view/edit, announcements / surveys / development / mentoring view+edit — derive from the two tuples, do not retype). No money, no lead-only key. Assert that in a test. |
| D5 | `effective_v2`: drop the `LABEL_GRANTS` line, add `stored_v2`; keep `TABLE_GRANTS`. Delete `LABEL_GRANTS` if nothing else reads it. |
| D6 | `in_admins`: drop the label seat (`admin.role in ADMIN_ROLES`); seat by an old admin key OR any stored v2 key. Keep `ADMIN_ROLES` only if something else needs it (M4's money checks do — do not touch those). |
| D7 | `asked_set` accepts v2 keys; refuses NEVER_GRANTABLE (new code) and LEAD_ONLY (until M3). It stores NULL only when the old part equals the role preset AND the v2 part is empty. `is_custom` / `preset_diff` / `table_presets`: compare the old part to the old preset and the v2 part to `ADMIN_PRESET_V2`; a row holding exactly the preset on both is not "Custom". |
| D8 | Add to Admins applies `ADMIN_PRESET_V2` with `ADD_KEYS`; Remove from Admins strips every v2 key. Same lock order as today's save. |
| D9 | GET adds `v2_keys` grouped by `GROUPS` (key, label, level, grantable, held) and `v2_held`; `table_presets` gains the admin preset. PATCH takes v2 keys in the same list. The web `PermissionEditor` draws v2 keys by group (heading per group, a toggle per key, NEVER_GRANTABLE and LEAD_ONLY drawn disabled with the reason). |
| D10 | Data step = migration 0097, applied BY HAND to production before the push (migrate-first): active `admin` rows: materialise NULL from `PRESETS[role]`, append `ADMIN_PRESET_V2`; active `finance` rows: append `ORG_READ_V2` only (today they read the org through the Admins seat, nothing more); row id 9: append `ADMIN_PRESET_V2`. Inactive rows untouched. **Amended (architect, 2026-11-12): revoked `admin` and `finance` rows are treated exactly as active ones (same plan, audit row and reverse), so a later Restore gives back what they had; row id 9 stays "active and a team role".** Idempotent (no duplicate keys). Reverse removes exactly what it added (record it in the audit row). One audit row per changed person. |
| D11 | Web label mirrors switch to the door keys from `admin/me` (G14 changed `lib/admin-auth-context.tsx`; build on it): `pageGuard` `MENTORS_READ_ROLES` / `mayReadMentors`, `scholars.ts` `MENTORING_ROLES`, the team page's `mayEditEmails`, `scholarship/[id]/view.tsx` `canManageSources` (check that file's G8 freeze note first; if frozen, leave it and say so). Mirrors of `ADMIN_PRESET_V2` / `NEVER_GRANTABLE` in the web get a drift test against the API. |
| D12 | **TD-503 part 1, only if cheap (≤ ~30 lines):** a shared predicate in `surface_gates` for the sponsor-vet door (today the inline role check at `views_admin/sponsors.py:260`), used by the door AND by the `sponsors_to_vet` card in `scholarship/my_pending.py:145`. `views_admin.py` has 0 lines of room — if it needs a line there, skip it and leave it for M3. |

## Out of scope (do not touch)

- **M4 (money):** credit maker/void label checks (`credit_steps.py:64`, `sponsorship/credits.py:42,154`),
  `canRecordCredit`, `isFinanceViewer`, `payments.py:432`, the wallet-credit card (TD-503 part 2). Money freeze:
  no money-code push from the evening of 14 Nov to 09:00 MYT 15 Nov.
- **M3 (lead keys):** `SECTIONS_BY_ROLE`, `canFilterByAssignee`, `R1_SUPER_TARGET_ROLES`, `profileCards`, the ~44 lead
  checks, granting any LEAD_ONLY key. Leave `awaiting_qc` alone.

## Tests (targeted while building; full suites once at the end)

- **Nobody changes (the principle):** a fixture per production shape (admin with stored list, admin with NULL,
  finance, reviewer with old admin keys like row 9, pure reviewer, org_admin, super, inactive admin) — run the
  migration's function on it, then assert `effective_v2` and `tables()` and every web door are the SAME as before
  the migration with the OLD code's label reading. Rohini's shape is the one row allowed to gain `ADMIN_PRESET_V2`.
- An admin-labelled row with a stored list and no admin key, NOT migrated, loses Admins — pinned, so the data step
  is shown to be required.
- `asked_set`: v2 keys stored; NEVER_GRANTABLE refused with its code; LEAD_ONLY refused; NULL only for the exact
  preset; idempotent saves.
- Add / Remove to Admins: preset on, all v2 off; old keys unchanged by Remove's v2 strip beyond today's behaviour.
- The old image's `clean` still drops every v2 key (compat test).
- `holders` / `team_holding` / payments / stranding ignore v2 keys.
- Migration 0097: forwards, idempotent re-run, backwards; audit rows; revoked admin and finance rows covered as active ones (amended 2026-11-12).
- Web: PermissionEditor by group, disabled keys with reasons, the drift tests, the switched mirrors.
- Parity test `test_team_tables_t5c_doors` follows the move.
- Budgets: `views_admin.py` 765/765 (do not touch), courses→scholarship imports 16/16 (add none),
  `test_permission_catalogue_v2.py` has 19 lines left (put new tests in a new file). Never raise a budget or ledger.
- Gates: API `manage.py check`, `makemigrations --check --dry-run`, full pytest `-n auto` via test_queue once; web
  `npm run gates`, `npm run bundle-budget -- --gate`, `npm run mobile-check` (compare against base; ~125 environmental
  cells fail on base too).

## Order of release (architect and owner, not the builder)

1. Owner confirms row id 9 and says yes to the data step.
2. Apply 0097 by hand to production (data + the `django_migrations` ledger row in one transaction). The old image
   ignores v2 keys, so nothing changes for anyone yet.
3. Owner says yes to the push; deploy the new image.
4. Owner's phone check before it is called live: Rohini sees the admin pages; the two admins and the finance person
   see exactly what they saw before; the Permissions tab draws by group.

## Risks

- **Silent loss of access** if the data step and the code disagree — pinned by the "nobody changes" tests.
- **"Custom" chip flipping** on materialised rows — D7 and a test.
- **The old image** reading v2 keys — `clean` compat test.
- **Shared files with other lanes** (`lib/admin-auth-context.tsx`, `messages/*.json`) — rebase on main before the
  gates.
