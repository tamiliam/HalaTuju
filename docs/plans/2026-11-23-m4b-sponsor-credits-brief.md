# Sprint S3 brief (ACCESS-BY-SWITCHES): M4b, sponsor credits and the Vircle ID on Payments switches

Branch `access-s3-m4b`, cut from `2edab4dab` (S1, S1b and S2/M4a inside). Written 23 Nov 2026.
Roadmap: `docs/plans/2026-11-19-access-by-switches-roadmap.md`, S3 (lines 73-86). Template: the S2 brief
`docs/plans/2026-11-19-m4a-payment-runs-brief.md`.

**Status: STOPPED AT THE BRIEF.** The stop rule fires: three readings of the roadmap text would change who
may do what on day one beyond the roadmap plus ruling Q2 (Q-A, Q-B below), one choice has no obvious
precedent (Q-C), and one debt item needs a ruling the register already asks for (Q-D). No data step is
needed. Nothing is built until the owner answers.

## Owner rulings that bind this sprint

- **Q2 (19 Nov):** credit approval and the Vircle ID both use **Payments: Approve**. The maker never approves
  their own.
- **Request #39, point 4 (`docs/decisions.md`, 2026-10-19):** payment runs moved to "the payments approver
  approves, the organisation admin is the fallback"; **wallet credits keep today's chain** (an Admin
  records, the payments checker checks if armed, the organisation admin approves). This is why S2's
  fallback rule is NOT the obvious analogue for credits.
- **The rule for every access sprint:** nobody's seat changes on day one. `test_m3_nobody_changes.py` stays
  green, unedited in its expectations.

## The one principle

Every gate below reads a key (or S2's `organisation.admin` through `holds_org_admin_powers`), never the
`role` label. The label stays for display. A gate that would let a new person in, or keep an old person out,
on day one is a question for the owner, not an implementation choice.

## Verified facts (branch `2edab4dab`). Re-check each before building on it

### Current gates (all read the label)

| Gate | File:line | Today |
|---|---|---|
| Credit maker signs (draft → admin_signed) | `apps/scholarship/credit_steps.py:64` | super or `role == 'admin'` |
| Credit check (admin_signed → finance_checked, when armed) | `credit_steps.py:66-67` | super or holder of `CHECKER_KEY = 'payments_approve'` (line 34) |
| Credit approve (→ confirmed) | `credit_steps.py:68` | super or `role == 'org_admin'` |
| No one signs twice | `credit_steps.py:70` | `same_signer` by email, against every collected signature |
| Record a credit | `apps/scholarship/sponsorship/credits.py:42` | super or `role == 'admin'` (docstring: the org admin is kept out on purpose so the approver stays free) |
| Cancel a credit | `sponsorship/credits.py:154-156` | super or role in (`admin`, `org_admin`) |
| Vircle ID correction | `views_admin/applications.py:272-274` (file at 600, the cap) | super or `role == 'org_admin'`, after `_require_app_write` (`base.py:413` → `may_write_case`, `base.py:122`) |
| Credit doors | `apps/courses/staff_tables.py:174-179` | `credits_read`, `credits_sign` = `sponsors.view`; `credits_write` = `sponsors.edit` |
| Terms / emails doors (TD-498) | `staff_tables.py:171-172` | `sponsor_terms`, `sponsor_emails` = `sponsors.edit` |
| Is the check armed? | `payments_chain.py:137-160` `credit_check_required` | any active, signed-in holder of `payments_approve` who has not signed this credit |
| Who is waited for | `credit_steps.py:81-96` `waiting_for` | `staff_permissions.holders(org, CHECKER_KEY)` |
| Wallet-credits card | `my_pending.py:151` | `credit_steps.checks_credits(admin)` (checker only; TD-503) |
| Credit row lock | `views_admin/credits.py:86-87` `_credit_for` | no lock (TD-561) |

Other readers of `CHECKER_KEY`: `staff_lifecycle.py:189-198` (last-checker guard),
`staff_tables_admin.py:371-378`, `staff_permissions_admin.py:48-51, 328-330`,
`views_admin/sponsors.py:319-334` (`_credits_armed`) and `:470`.

Web (`halatuju-web/src`): `lib/sponsorDetail.ts:14` `CREDIT_CHECKER_KEY = 'payments_approve'`;
`creditActions` (136-165) and `canRecordCredit` (173-175) decide by role; callers
`app/admin/sponsors/[id]/page.tsx:156` and `:387`. Tests `lib/__tests__/sponsorDetail.test.ts:143-245`,
`lib/__tests__/roleIsDisplayOnly.test.ts:215`.

### Keys as stored after S2's `0100`

- `payments_approve` (old) expands through ALIASES (`staff_permissions_v2.py:127-142`) to `payments.view`,
  `payments.approve` and `sponsors.check`. So the `sponsors.check` holders ARE today's checker holders.
- Org admins store `organisation.admin` (S2) and hold `ORG_ADMIN_V2` (line 197), which includes
  `sponsors.edit`. `stored_v2` (line 241) returns `()` for an org admin: an org admin holds keys by the
  powers, not by stored rows.
- Admins hold `sponsors.edit` by `ADMIN_PRESET_V2` today; the finance row holds `payments_approve` and no
  `sponsors.edit`.
- `ORG_ADMIN_POWERS` (lines 220-227) is the drift list. The S2 brief says S3 adds the credit approver and the
  Vircle ID correction to it.

### GATE-LEFT

`apps/courses/tests/test_role_is_display_only.py`: 14 entries in `GATE_LEFT_PINNED` (511-526), **4 of them
money**: `credit_steps.py::step_refusal`, `credits.py::record_admin_credit`, `credits.py::cancel_admin_credit`
(ALLOWLIST 221-226, owner T5d) and `applications.py::AdminApplicationDetailView.patch` (270-271, owner M4).
Target after S3: **0 money, 10 left** (all `target rule`). The four entries are DELETED, never reclassified.

## Target gates (with the recommended answers to Q-A to Q-D)

| Step | Target | Day one |
|---|---|---|
| Maker records and signs | the person's own STORED `sponsors.edit` (`stored_v2`), never through the org admin powers; super stays | the same Admins as today (Q-A) |
| Check (when armed) | `sponsors.check`; `CHECKER_KEY` retired; holders read through the v2 holders reading | the same holders (alias) |
| Approve | `payments.approve` OR `holds_org_admin_powers`; never the maker, never the checker of the same credit | org admins as today; a Payments: Approve holder now also approves (Q2) but in every in-flight credit they are the checker, so `same_signer` bars them (Q-C) |
| Record | the maker seat (stored `sponsors.edit`) | unchanged (Q-A) |
| Cancel | `sponsors.edit` (today's `credits_write` door), any holder including the org admin powers | unchanged (Q-B) |
| Vircle ID | `payments.approve` OR `holds_org_admin_powers`, after `_require_app_write` | org admins as today; a Payments: Approve holder gains it only on a case they may already write (Q2) |
| Terms / emails pages | stay `sponsors.edit` unless the owner rules (Q-D) | unchanged |

`ORG_ADMIN_POWERS` gains two plain lines: "approves sponsor credits" and "corrects a scholar's Vircle ID".

## Day-one table (by today's role holders)

| Holder | Record | Maker sign | Check | Approve | Cancel | Vircle ID |
|---|---|---|---|---|---|---|
| super | yes → yes | yes → yes | yes → yes | yes → yes | yes → yes | yes → yes |
| org admin | no → no | no → no | only if holds `payments_approve` → same | yes → yes | yes → yes | yes → yes |
| admin (preset) | yes → yes | yes → yes | only if keyed → same | no → no (unless keyed `payments_approve`: Q2) | yes → yes | no → no (unless keyed: Q2) |
| finance row (`payments_approve`) | no → no | no → no | yes → yes | no → **yes, Q2**, never on a credit it checked | no → no | no → **yes, Q2**, only with `scholars` on that case |
| reviewer / qc / partner | no | no | no | no | no | no |

Changes on day one are only the two Q2 additions, which the owner ruled. In production every in-flight
credit that a Payments: Approve holder could approve is one they already checked, so even that addition
changes no outcome until a second key holder exists. The production counts below confirm it before build.

**Literal roadmap readings that would change seats (the reasons for the stop):**

- "maker → `sponsors.edit`" read through the org admin powers lets every org admin record and maker-sign a
  credit (they hold `sponsors.edit` by `ORG_ADMIN_V2`). Today they are deliberately kept out.
- "cancel → `sponsors.edit` or `payments.approve`" lets the finance row cancel credits. It cannot today.

## OWNER: questions (plain words, with a recommendation each)

**Q-A. Who may record a credit and sign it first?** Today only Admins (and the platform). The roadmap says
"Sponsors: edit", and organisation admins hold that switch through their powers, so a plain reading lets an
organisation admin record and first-sign a credit, then be unable to approve it (no one signs twice). In an
organisation with one organisation admin and no other Admin the credit would be stuck.
*Recommend:* the first signer is a team member whose own Sponsors: edit switch is on. An organisation admin
never records or first-signs a credit, the same as a payment run. Nobody changes.

**Q-B. Who may cancel a credit?** Today Admins and organisation admins. The roadmap says "Sponsors: edit or
Payments: Approve", which would let the person with only the Payments switches cancel credits too, a new
power. The roadmap line was written before S2 moved the organisation admin's money powers onto their own key.
*Recommend:* cancel is Sponsors: edit only (Admins and organisation admins, as today). Nobody changes.

**Q-C. Is the organisation admin the regular credit approver, or only the fallback (as for payment runs)?**
Request #39 kept today's chain for credits (the organisation admin approves). Ruling Q2 adds anyone with
Payments: Approve. On day one both answers give the same result in production.
*Recommend:* keep the organisation admin as a regular approver (through the organisation admin powers), and
add anyone with Payments: Approve, never the person who recorded or checked that credit. No fallback rule.

**Q-D. TD-498: should the sponsor terms and sponsor emails pages open to anyone who may view sponsors?**
That would let the person with the Payments switches, and any Admin given Sponsors: view only, read terms and
emails. It is read-only, but it is a widening, and the register says it needs your ruling.
*Recommend:* your call. If yes, read-only on Sponsors: view, writing stays on Sponsors: edit. If no, TD-498's
remainder stays open and S3 leaves both doors as they are.

## The data step: none

- `sponsors.check` holders are `payments_approve` holders through the alias.
- Record and cancel already need `sponsors.edit` at the door; the service gate only narrows.
- `organisation.admin` is stored by S2's `0100`.
So `Migration: none`.

### Read-only counts for the lead (counts only, `BEGIN READ ONLY`; not run by me)

1. Active non-admin, non-org-admin team rows that STORE `sponsors.edit` (Q-A widening size if read literally).
2. Active `admin` rows that do NOT hold `sponsors.edit` (would lose record or sign under the target).
3. Active rows holding `payments_approve`, per organisation, and how many also hold `scholars` (Vircle ID).
4. Credits by status (`draft`, `admin_signed`, `finance_checked`), per organisation, with whether the
   `admin_signed` / `finance_checked` signer holds `payments_approve` (Q2 outcome check).

## Maker-checker after S3, and the tests to add

- Maker cannot check or approve the same credit; checker cannot approve the same credit (`same_signer`
  stays, by email, against every collected signature).
- A Payments: Approve holder approves a credit they did not sign (new, Q2).
- An org admin never records or maker-signs (Q-A); an org admin approves (Q-C).
- The check arms only on a signed-in holder who has not signed this credit (TD-560 rule kept, read on
  `sponsors.check`).
- `test_access_matrix.py`: key-holder callers (an Admin with only stored `sponsors.edit`, a team member with
  `payments.approve` and no `sponsors.edit`, one with `payments.approve` and `scholars`) on record, sign,
  cancel and the Vircle ID PATCH; `access_manifest.json` credit rows updated to match.
- `test_m3_nobody_changes.py`: `read()` gains "may record", "may cancel", "which step may sign" on a seeded
  credit at each status, and "may correct the Vircle ID"; expectations unchanged for every existing seat.
- `test_role_is_display_only.py`: delete the four entries from ALLOWLIST and `GATE_LEFT_PINNED`; add an S3
  note to the header.
- Web: `creditActions` / `canRecordCredit` read served flags (`can_record_credit` on the sponsor payload;
  `can_sign`, `blocked`, `can_void` per credit); `CREDIT_CHECKER_KEY` and the role logic deleted; the M4
  entry in `roleIsDisplayOnly.test.ts` goes.

## Debt

- **TD-561:** lock the credit row in the sign path: `select_for_update(of=('self',))` inside the transaction,
  re-check the status after the lock, no network call under the lock. Closed "when live".
- **TD-498 remainder:** waits for Q-D.
- **TD-503:** the wallet-credits card shows to anyone holding a credit step seat (maker, checker or
  approver), each seeing only credits waiting on them. Display only; implementation choice.
- **TD-664 (d):** the Vircle ID gate on keys. Closed "when live".
- `applications.py` is at 600 lines: the Vircle gate becomes one call to a helper in `credit_steps.py` (or a
  small `vircle_gate` in `views_admin/base.py`) so the file does not grow.

## Out of scope

S4, S5, S6; the payment runs (S2); any change to the Vircle payout code.

## Risks

- Bundle headroom is 0.3 kB on the lead tree. The web change must remove more than it adds (served flags
  replace role logic); measure the laptop median before and after.
- `views_admin/sponsors.py` is at 514 lines; adding served flags there must stay under 600.
- A missed `CHECKER_KEY` reader would keep reading the old key name. The alias keeps it working, but grep
  every reader (list above) before deleting the constant.

## Gates (after the rulings)

Targeted tests; full api suite through the queue; `manage.py check`; `makemigrations --check --dry-run`;
web `npm run gates`, then `npm run bundle-budget`; `npm run mobile-check` for the sponsor page.

## Phone check (proposed)

From the owner's org admin seat: open a sponsor with a recorded credit, approve it, and see the Vircle ID
correction still saves on a scholar's case. From an Admin seat: record and sign a credit; the approve button
is not offered.

## Hours

Brief: about 2.5 h (reading and writing). Build after rulings: estimated 6-8 h (api 3-4, web 1.5-2, tests and
docs 1.5-2).
