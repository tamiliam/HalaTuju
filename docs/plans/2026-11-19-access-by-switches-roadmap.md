# Programme ACCESS-BY-SWITCHES: M4 (money), SCHOLARS-SPLIT, mentors, legacy roles, and the related debt

## Context

M2 and M3 moved most staff access from role labels to switches (v2 keys). Several pieces were deliberately left over, and each was planned on its own:
- **Money (M4).** Payment runs and sponsor credits still decide by role label or "lead tier".
- **Org admins' payment switches.** These are still added by role (`LEAD_MONEY_UNTIL_M4`, TD-620/629), so R6 ("no implicit powers") is not complete.
- **Scholars switches.** The owner wants the four Scholars switches reworded and reordered. The "admin" switch is to carry everyday file writes, which today hang off the view key.
- **Mentors.** Mentors' powers are unruled, and a mentor still receives a thank-you's `scan_result` and raw text.
- **Legacy roles.** `finance` and the view-only `admin` label are still in the code (TD-663).
- **Post-award leftovers.** POST-AWARD-CUT left small items (TD-664), including a paid-call leak.

The owner asked for all of this to be planned as one programme, so it is addressed comprehensively rather than piecemeal.

**Intended outcome:** every staff action is decided by a switch the org admin can see and change. "Finance" and "view-only admin" disappear as roles: there are only admins, some holding Payments switches. Payments, Scholars and Mentoring each have their own switches, and the web draws every control from flags the server serves.

## Owner rulings (19 Nov, direct)
- **Q1 (org admins' money).** Store the switches they effectively hold today. Nothing changes on day one, and a super can untick them afterwards.
- **Q2 (credit approval and Vircle ID).** Both use **Payments: Approve**. The maker never approves their own.
- **Q3 (Scholars admin switch).** **One switch**, "Manage scholar files" (`scholars.approve`). It covers every everyday file write AND suspension/termination letters. Today's file writers (`scholars` holders) keep their write power: the data step grants them the switch, and with it the letters.
- **Q4 (mentors).** The one new power is **add activity notes** on an assigned scholar; otherwise read only, beyond today's meetings/concerns log. The owner did NOT choose to hide the thank-you `scan_result` and raw text from mentors, so that stays as it is today. Raise it again only if the owner asks.

## Shape: 6 sprints, in this order

Each sprint follows the same steps:
1. An Opus brief.
2. The owner's rulings.
3. An Opus build in its own worktree.
4. A fresh review, plus an Opus adversarial review for anything touching auth or money.
5. The gates, then a push to main.
6. The HalaTuju publish, with the owner's direct yes, then the owner's phone check.

At most 2 builders run toward main at once. Every data step is migrate-first, written by hand, run on the owner's yes, and counted read-only before and after.

### S1. Case and team leftovers (no money; can run beside S2)
Items, all of them small:
- **TD-664 (f), the paid leak.** `profile_finalise.claimable` / `_claim_row` (`apps/scholarship/profile_finalise.py:90,175`) skip a case whose `staff_lifecycle.case_stage` is not OPEN.
- **TD-664 (a), (b), (c).** The web uses served flags instead of `hasPerm(role,'qc')` (`view.tsx:108`, `QcPanel.tsx:33`) and `holdsDoor(role,'decide')` (`view.tsx:381`, `PostAwardPanels`). `decisionBarShows` (`DecisionBar.tsx:28`) also asks the served stage. The server adds `can_qc` and `can_close_pre_award` to `served_write_flags` (`views_admin/base.py:172`).
- **TD-664 (e).** The PATCH, disbursement, profile PUT/publish and anon-publish replies return `_detail_payload`, as reporting-date and close already do.
- **The activity composer.** The scholar page (`app/admin/scholars/[id]/page.tsx` ~330) uses a served `can_write_activity`. It is needed before S4 moves the write key.
- **Team debt:**
  - TD-634: a super's reviewer picker is limited to the case's organisation, and the refusal gets its own wording.
  - TD-627: `may_hand_to` refuses when both sides have no organisation.
  - TD-630: an archived holder's cases show in the suspended banner.
  - TD-615 and TD-616: delete is refused for an in-group invitee, and the delete payloads follow `in_a_group`.
  - TD-603: archive and restore write a `staff_activity` row.
  - TD-618: pin the Overview row wording.
- **Register hygiene.** Close TD-621, 622, 631 and 633 with live evidence (they are live, but the register still says "built").

### S2. M4a: payment runs on Payments switches (T5d part 1; money)
- **`payments_chain.py`:**
  - Delete `_is_lead_tier` and its uses (:87-89, 226, 234, 240, 272).
  - `may_read` → `payments.view`; `may_prepare` → `payments.prepare`; `_may_approve` / `fallback_approvers` (:204) → `payments.approve` holders, no role query.
- **Remove the carry-over.** Remove `LEAD_MONEY_UNTIL_M4` (`courses/staff_permissions_v2.py:206`, `effective_v2` :321) and `LEAD_MONEY_OLD` (`staff_permissions_admin.py:370`). This closes TD-620 and TD-629.
- **Make the money switches real.** Remove the payments keys from `ALIAS_V2`'s non-grantable set, so the Permissions tab's Payments row becomes four real switches: View, Prepare (maker), Check (optional middle), Approve. Today it is an INFO row of old subs (`lib/permissionLayout.ts:76`). Add the new en/ms/ta strings. The Tamil strings need a native read.
- **Data migration `courses/0100` (owner yes).**
  - Store the money keys on every row that holds them today by role: active org admins get the five keys `LEAD_MONEY_UNTIL_M4` adds today (Q1); `finance` rows (`payments_approve` → `payments.view`, `payments.approve`, `sponsors.check`); `admin` rows (`payments_prepare` → `payments.view`, `payments.prepare`).
  - Read-only counts before and after.
  - The rule: nobody's seat changes (`test_m3_nobody_changes.py` stays green).
- **Web:**
  - `isFinanceViewer` (`payments/[id]/page.tsx:81`) becomes a served `can_open_applicant`.
  - Drop the `r !== 'finance'` fallback (`payments/page.tsx:51`).
  - The nav payments row is drawn by served keys (`navigation.ts:275`).
- **Debt:**
  - TD-560: a never-signed-in approver no longer arms the check.
  - TD-605: lock the waiting check against a new run.
  - TD-614: the Remove confirm shows only real finance consequences.
- **Tests:**
  - The access manifest's payment-run rows move from labels to keys (`finance_a` becomes `payments_holder_a`).
  - Add the maker-checker tests (the manifest's `_about` leaves these to M4): no same signer; a checker who is also an approver; the fallback.
  - Delete the `payments_chain::fallback_approvers` GATE-LEFT entry and the M4 `LEAD_READS` entries (`courses/tests/test_role_is_display_only.py`); never reclassify them.

### S3. M4b: sponsor credits and the Vircle ID on switches (T5d part 2; money)
- **The credit steps:**
  - `credit_steps.step_refusal` (:64-68): maker → `sponsors.edit`; check → `sponsors.check` (renamed from `CHECKER_KEY = 'payments_approve'`); approve → `payments.approve` (Q2), never the maker.
  - `sponsorship/credits.py`: `record_admin_credit` (:42) → `sponsors.edit`; `cancel_admin_credit` (:154) → `sponsors.edit` or `payments.approve`.
- **The Vircle ID correction** (`views_admin/applications.py:272`, TD-664 (d)) → `payments.approve` (Q2) plus the file fence.
- **Web:**
  - `creditActions` / `canRecordCredit` (`lib/sponsorDetail.ts:141-173`) read served per-step flags.
  - `CREDIT_CHECKER_KEY` goes.
- **Debt:**
  - TD-561: row-lock the credit on sign.
  - TD-498 remainder: sponsor terms and emails read on `.view`.
  - TD-503: Overview `wallet_credits` / `sponsors_to_vet` cards follow the same keys as their pages.
- **Delete the GATE-LEFT entries:** `credit_steps::step_refusal`, `credits::record_admin_credit`, `credits::cancel_admin_credit` and `AdminApplicationDetailView.patch`.
- **The gate.** The role-by-endpoint access test (`scholarship/tests/test_access_matrix.py`) must pass with zero money GATE-LEFT entries, and both M4 sprints publish only once it does (owner's standing condition).

### S4. SCHOLARS-SPLIT (scholar file upkeep)
- **The Scholars row in order** (`lib/permissionLayout.ts:69-71`, and en/ms/ta under `admin.perm.*` / `admin.permLayout.*`):
  1. **View scholars** (`scholars.view`): read only.
  2. **Manage scholar files** (`scholars.approve`, the admin switch): every everyday file write, plus suspension and termination per ruling Q3.
  3. Ask to withdraw an award (maker).
  4. Approve award withdrawals (approver).

  The wording is final at the brief, and the owner sees it.
- **Server: one home.**
  - `base.may_write_file` (:98) becomes `scholars.approve` plus `org_allows`.
  - Because everything routes through it, these move together: results review, the activity note, thank-yous (`may_decide_thanks`), non-senior letters (`letters._kinds_for`), and every past-award case write through `may_write_case`.
  - `_LettersBase._senior` reads the same or a separate key per Q3 (folds in TD-598).
  - Tranches stay on Payments (S2), unchanged.
- **Senior letters (Q3).** `_LettersBase._senior` reads the same `scholars.approve`; it already does, via `staff_tables` door `senior_letters`, so one switch now means one rule. This closes TD-598.
- **Data migration `courses/0101` (owner yes).** Every active row that holds `scholars` today also gets `scholars.approve` stored, so nobody loses a write. Their new letter power is named in the phone check. Read-only counts before and after.
- **Presets.** The admin preset carries both keys. `scholars.approve` stops being lead-only in the catalogue, so an org admin can grant it.
- **TD-597 (Development and Surveys open every scholar on their own keys):** brought to the owner at the brief.

### S5. Mentors (Q4: activity notes only)
- **The note write.** `POST scholars/<pk>/activity/` (`views_admin/scholars.py:312`) admits a mentor on a scholar in their `mentor_desk.current_assignments` (`mentor_methods` gains `post` on that view only).
- **What a mentor may write.** Only a note kind; never staff-only or internal kinds.
- **What the note records.** The mentor's name as author, never their email.
- **The web control.** A served `can_write_activity` (from S1) is true for an assigned mentor, and it draws the composer.
- **Everything else stays read-only.** The access manifest gets an assigned-mentor caller and an unassigned-mentor caller: the note is allowed for the assigned mentor and refused (404) for the unassigned one. Every other write stays refused.
- **Small and freeze-safe.** It can share S4's publish.

### S6. Legacy roles retired (TD-663; TD-632 remainder)
- **Data migration (owner yes):**
  - `role='finance'` rows become `admin`, with their keys already stored by S2.
  - Pending invitations carrying `finance` move too.
  - Then remove `finance` from `ROLE_CHOICES` (`courses/models_staff.py:90`).
- **Code:**
  - Remove `finance` from `TEAM_ROLES`, `PRESETS`, `V2_PRESETS`, `ROLE_PAIRS`/`ROLE_PARTNER`, `staff_fence`, `invitations` and `staff_lifecycle`.
  - The admin preset stops being "view-only" wording everywhere (CLAUDE.md, the role matrix).
  - Web: `staffRole`, `adminStaff`, `roleBadge`, `profileCards` (the money chip from keys), the manual (the finance chapter folds into the admin and Payments sections), and the i18n strings.
- **TD-632 remainder.** `may_approve_platform_sponsors` (`surface_gates.py:116`) gets its own key; the owner keeps the D6 platform fence.
- **What stays.** The signature columns (`admin_signed_*`, `finance_signed_*`, `org_admin_signed_*`, `finance_checked_*`) and the `admin_signed` / `finance_checked` statuses are historical data. They stay, with comments describing them as maker, checker and approver.
- **The pin.** `test_role_is_display_only.py` ends with no money and no `finance` reads.

## Outside the programme (stated so nothing is silently dropped)

| Item | Why it is outside |
|---|---|
| TD-353 | On hold until a second organisation joins |
| TD-591 and TD-592 | Owner-ruled, each its own money sprint |
| TD-593 | Vircle task after a withdrawal; small, payments follow-up |
| T5f (gift limits as a fence) | Design first; largest blast radius; after this programme |
| TD-626 | A new page, its own sprint |
| TD-441, TD-485, TD-489 | TD-489: the owner said later |
| TD-075, TD-184, TD-192 | The parked sponsor module |
| TD-619 | Needs a mobile-check page; pairs with any Team UI sprint |

Not code: a native Tamil read of the graduation thank-you strings, and of every new string this programme adds.

## Estimate (hours, to compare with actuals)

| Sprint | Hours |
|---|---|
| S1 | ~6 |
| S2 | ~12 |
| S3 | ~8 |
| S4 | ~10 |
| S5 | ~3 |
| S6 | ~8 |
| **Total** | **~47 build and review hours** |

Plus the owner's rulings, 3 data steps and 6 publishes. S1 and S2 run in parallel. S3 to S6 run in order: S4 needs S1's activity flag and S2's Payments switches; S6 needs every gate on keys first.

## Verification (each sprint)
- **Targeted tests while building.** Then the full API suite (`-n auto` through `test_queue`), `manage.py check` and `makemigrations --check`, the web `npm run gates`, `bundle-budget --gate`, and `mobile-check` for UI changes.
- **Pins:**
  - `test_access_matrix.py` (with the new key-holder callers and the maker-checker cases).
  - `test_role_is_display_only.py` (the GATE-LEFT count only falls).
  - `test_m3_nobody_changes.py` (seats unchanged across the data steps).
  - The payment golden tests.
  - `test_technical_debt_register.py`.
- **Production data.** Read-only counts (`BEGIN READ ONLY`) before and after each data step; Security Advisor shows 0 errors.
- **The owner's phone check after each publish.** For example, S2: an admin with Prepare can build a run and cannot approve it; untick an org admin's Approve and it stays unticked. S4: an admin with View scholars only sees no change controls on a file.
