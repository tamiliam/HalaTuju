# Staff permissions and Finance approval of payment runs: roadmap (org request #39)

**Status (2026-10-21):** Sprints 1-3 and TD-360 LIVE. Sprint 4 (the editor) BUILT on `perm-s4` (migration
scholarship 0175, to be applied by hand before deploy), not pushed or deployed; adversarial review
pending. **Earlier status (2026-10-19):** Sprints 1 and 2 LIVE; Sprint 3 built. **Original status:** PLAN, written 2026-10-19 on
`perm-plan` (base `d15c0f14`). Request #39
was quoted at **34 h (30 permissions + 4 payments, indicative)** and is waiting for the organisation
to accept it. This plan **re-estimates it at 36 h** (see "Hours"), offers a way to hold it at 34 h, and
lists six questions for the owner. Sprint 1 must not start until the roadmap and the answers are in.
**Workflows followed:** `Settings/_workflows/implementation-planning.md`, plus the door-list rule
in `sprint-start.md` step 3b (every sprint here touches who may see files, sign money or be invited).

**Owner decision, 2026-10-19 ("a"):** hours option A — the quote stays at **34 h**; the 2 extra
hours found by this plan (the payment-chain details the quote missed) are absorbed, not billed. The
plan's recommendations on the six open questions stand unless the owner overrules them. Sprint 1
starts once the organisation accepts the #39 quote.

---

## What the owner asked for (verbatim, 2026-10-19)

> "Can we change all to admin and control only access permission? So, a reviewer is someone with
> review permission. A QC likewise is an admin with QC permission. In that way, we can have different
> combinations."

What prompted it: BrightPath wants **Rohini** (a Reviewer) to also help **Kulaly** manage student
spending. Today that is impossible: one person has one role, and only Admin and Organisation admin
open the Spending page.

> Payments (option A): "Finance role currently doesn't have clear action items. I would like the role
> to be able to approve payment — the work that Suresh does today."

So a payment run becomes: an **Admin PREPARES** (and signs as maker) → **FINANCE APPROVES**, and
that approval completes the run (Vircle releases the money to students). The organisation admin
(Suresh) stops countersigning runs. Moving the organisation's money INTO Vircle is a manual step
outside HalaTuju and is not modelled. Finance gets a clear "waiting for you" list, and the "run is
ready" email goes to Finance. The maker can never be the approver. A third signer must still be
possible later just by granting a permission.

## What the organisation was promised (the #39 analysis; this plan keeps to it)

1. Everyone is a team member, and the organisation switches permissions on or off for each person.
2. Today's roles become **ready-made presets**, so on go-live everyone keeps exactly what they can
   do today. **The one exception is the payment change.**
3. The safety rules hold for every mix: nobody QCs their own decision; nobody approves a run they
   prepared; cases are assigned only to people with review permission.
4. Finance + Review **will** see the files of students assigned to them. This reverses the
   2026-07-23 ruling "finance never sees applicant files", so it is open question 1 below.
5. The misleading invite message ("Admin with this email already exists") is fixed.
6. Built in about three stages, each released and reviewed. This plan says at which stage Rohini can
   be given review + spending (**Stage 3, when Sprint 4 is live**; see "Stages").
7. 34 h, indicative. The owner has promised not to go over it without coming back first.

---

## The model in one picture

| Layer | Who | How their access is decided |
|---|---|---|
| **Platform** (outside this change) | `super`, referral `partner` | Exactly as today. A super passes every permission check and can still fill only ONE signature on a run. A partner has no team permissions. |
| **Organisation lead** (a fixed tier) | `org_admin` (Suresh) | A fixed bundle that nobody edits: everything the role matrix gives an org_admin today (configuration, gifts, contracts, sponsors' acceptance, assigning cases, managing the team, the parent's contact, billing, requests) **minus countersigning payment runs**. They also act as the **fallback approver** when nobody else can approve a run (see "The payment chain"). |
| **Team members** | today's `admin`, `finance`, `qc`, `reviewer` | **A set of permissions.** `role` stays on the record as the **preset label** (where they sit on People, which invitation letter they get, which Guide chapter they open). The permissions decide what the converted gates allow. |

### The permission catalogue (8 keys, refined from the code)

| Key | Plain name (UI) | What it opens (the gates that convert, Appendix A) | Today held by |
|---|---|---|---|
| `review` | Review assigned students | Can be ASSIGNED cases, opens and works on the cases assigned to them (files included), proposes interview times, can be paused | reviewer |
| `see_all` | See all students | Reads every application in the organisation (no writes unless assigned) | admin, qc, org_admin |
| `qc` | Quality check | The QC gate, and working on any case in the organisation (today's QC power). Requires `see_all`; the editor adds it automatically | qc, org_admin |
| `spending` | Student spending | The Spending page: named students' spending, flags, categories | admin, org_admin |
| `payments_prepare` | Prepare payment runs | Create, edit and cancel runs; sign as MAKER | admin (org_admin creates/edits/cancels but never signs as maker; kept as a lead-tier power) |
| `payments_check` | Check payment runs | The OPTIONAL middle signature. Dormant until someone holds it. **No preset holds it after the change**; it exists so a third signer is one switch away | finance (today, as the "finance check") |
| `payments_approve` | Approve payment runs | The FINAL signature, which completes the run and releases the money | org_admin today; **finance after the change** |
| `manage_team` | Manage team and invitations | Invite, resend, revoke, restore, delete, change role, **change permissions** | org_admin. **Reserved: stays a lead-tier power in #39, not switchable** (question 3) |

Reading payments (list, run detail, CSV, funding summary) is open to anyone holding any of the three
`payments_*` keys, as `_PAYMENTS_READ_ROLES` is today.

### Presets: what everyone holds on go-live

| Preset (`role`) | Permissions | Same as today? |
|---|---|---|
| `reviewer` | `review` | Yes |
| `qc` | `see_all`, `qc` | Yes |
| `admin` | `see_all`, `spending`, `payments_prepare` | Yes |
| `finance` | `payments_approve` | **No, deliberately:** was the finance CHECK, becomes the APPROVAL |
| `org_admin` | lead tier (all of the above except `payments_prepare` signing and `payments_approve`; fallback approver) | **No, deliberately:** stops countersigning runs |

Two rules that keep the presets exact, found in the code (lead rulings; the owner can overrule):

- **R1, assignment targets.** Today an org_admin may assign only `role == 'reviewer'`
  (`verdict.py:520`, and the web picker filters the same way), while a **super** may assign any of
  `REVIEW_ROLES` (reviewer, admin, qc, org_admin). The new rule "assignment only to people with
  `review`" reproduces the org_admin side exactly. The super's wider choice is kept as a super
  override, and any case already assigned to an admin keeps working, because "assignment grants
  write" (`_can_review_app`) is unchanged. Sprint 1 runs one read-only query: how many in-play cases
  sit with a non-reviewer today. If none, the override is offered to the owner for removal.
  **Result (read-only, production, measured by the lead 2026-10-19):** in-play applications (status
  not rejected / withdrawn / expired / closed) by the assignee's role — **reviewer**: awarded 64,
  interviewed 1, interviewing 1, profile_complete 2; **org_admin**: awarded 1. **No in-play case is
  assigned to an admin, a qc or a finance person.** So the super's wider choice is in use exactly
  once, by an org_admin, on an awarded case (past assignment; an awarded case can no longer change
  hands). The override is therefore not needed for any case an admin or qc holds; it is kept for S3
  (the org_admin's awarded case keeps working through "assignment grants write" whatever is decided),
  and its removal is offered to the owner as a question, not done. The golden table
  (`apps/courses/tests/test_permission_presets.py`) declares the four R1 rows where `review` alone
  differs from today (assignment target, interview times, pause target, the super's assignable list).
- **R2, preset-bound surfaces.** Some gates cannot be stated as permissions without changing
  somebody's access. Example: the Programme Overview gives `qc` (which holds `see_all`) no funnel,
  while `admin` gets one. Gates like this **keep reading `role`** in #39 and are listed as
  "preset-bound" in Appendix A: Overview sections, the reviewer profile hold and profile cards,
  graduation review, sponsors, sources, sponsor emails, wallet credits, team read-only views. So
  Rohini (reviewer + spending) sees the reviewer's Overview (no money totals) and gets the Spending
  page. Because no gate is widened by accident, this is the safe default.

---

## Data model

**Recommendation: one nullable JSON list on the person, where NULL means "the preset".**

`PartnerAdmin.permissions = JSONField(null=True, blank=True)`, a list of catalogue keys.

- **NULL = take the preset of `role`.** Every one of today's staff, and every future invitee, gets
  the preset with **no backfill**. This is the owner's own pattern for `PartnerAdmin.programme`
  (NULL = every gift, 2026-09-04), and it avoids the lesson of migration 0123 (a column filled for
  everybody alive that day and for nobody after). The invite, re-invite, `bursary_e2e`,
  `backfill_invitations` and factory doors need no change, because they never have to write
  permissions.
- **A saved edit stores the full explicit list.** A list equal to the preset is stored as NULL,
  so "custom" is derivable: `permissions IS NOT NULL`.
- **Reads go through one door:** `PartnerAdmin.permission_set` / `PartnerAdmin.has_perm(key)`,
  delegating to a new leaf module `apps/courses/staff_permissions.py` (catalogue, presets, the
  `qc ⇒ see_all` dependency, the lead-tier rule, `holders(org, key)`). Because it is a method on the
  model, scholarship callers write `admin.has_perm('qc')` and the code gains **no new cross-app
  import statement** (`courses_to_scholarship_imports` is a ratchet at 17).
- **Querying "who holds X in this organisation"** (approvers, checkers, email recipients, the
  assignable list) is done in Python over the organisation's active staff: tens of rows, on rare
  operations. The reason: **Django's JSONField `__contains` is not supported on SQLite, which the
  test suite runs on** (Django 5.2). A queryset lookup would pass on Postgres and fail in the
  tests, or the reverse. `holders()` is the one place this happens, and it gets a test.

Alternatives considered:

- (a) A join table of (person, permission) rows. It is queryable on both databases, but it must be
  materialised for every existing person and written by every door that creates staff. That is
  six doors, and a forgotten one leaves a person with no permissions.
- (b) One boolean column per permission. It needs a migration for every new permission, and NULL
  tri-state logic in every query.
- (c) Rows only for deviations from the preset. This was rejected as two sources of truth.

**History (Sprint 4):** a small `staff_permission_changes` table (who changed whom, before → after,
when) in `scholarship`, with RLS on and one `service_role` policy. A role change was audited by log
line only. For a permission that releases money, a 30-day log is not enough, which is the reasoning
behind `guardian_contact_changes`. An `AUDIT staff_permissions_changed …` log line is written as
well.

**Expand–contract:** `role` is never dropped. It becomes the preset label. Nothing is contracted in
#39. **Migrate-first:** each migration is additive and nullable, and the old image never selects the
new column. Ledger numbers are settled at sprint start (`courses/0081` and `scholarship/0174` are
the next free names today, if Sources Sprint B's 0173/0079/0080 land first).

**How the browser learns them:** `GET /admin/role/` (`AdminRoleView`) adds `permissions` (always
the RESOLVED list, never NULL), `preset` (= role) and `custom` (bool). `role` stays, so old bundles
keep working. A new `halatuju-web/src/lib/staffPermissions.ts` holds the catalogue keys and
`hasPerm()`, with a drift test in **both directions** (lessons.md, 2026-09-19: the reverse sweep is
derived from the api side). The server stays the fence and the menu is only visibility. A person
can never edit their own row, so the editor never makes the editor's own cached `/admin/role/`
stale. Another person's open session keeps its old menu until a refresh, while the server refuses
anything they no longer hold.

**`super` / `partner` / `org_admin`:** a super passes `has_perm` for every key (as `has_role` does).
A partner holds nothing. An org_admin is the lead tier and **their permissions are not editable**.
`_staff_target_manageable` already refuses an org_admin target, and the editor uses that same check.

---

## The payment chain after the change

```
draft ──(payments_prepare: MAKER signs)──▶ admin_signed
admin_signed ──(payments_check, ONLY IF someone in the organisation holds it)──▶ finance_checked
admin_signed / finance_checked ──(payments_approve: APPROVER signs)──▶ completed → complete(run) → Vircle
any pre-completion status ──(payments_prepare or org_admin tier)──▶ cancelled
editing an item at any signed status ──▶ draft, every signature cleared (unchanged)
```

- **No migration.** The three signature triples are reused: maker → `admin_signed_*`, check →
  `finance_signed_*`, approver → `org_admin_signed_*`. The last name becomes a misnomer. That is
  accepted, as Sources Sprint A kept `referred_by_org`, because a column rename on a live money
  table costs a cutover and changes no behaviour. The screen labels the cards by STEP ("Prepared",
  "Checked", "Approved"), not by role.
- **The check step stays live and computed, never stored** (decision 2026-07-23, kept): the predicate
  `finance_check_required(org)` is re-keyed to "an active member holds `payments_check`". No preset
  holds it, so on deploy the chain is two steps for everyone. Granting `payments_check` to anyone
  later arms it, including for a run already sitting at `admin_signed`, both ways as before. The
  payload key `finance_check_required` keeps its name for one release (old bundles read it), and a
  new `check_step_required` key is added beside it.
- **⚠ The wallet-credit chain shares that predicate today** (`views_admin/sponsors.py:437`,
  `sponsorship.py:350`). Re-keying it would silently switch OFF Finance's check on sponsor credits.
  Sprint 2 therefore splits it: credits get their own `credit_check_required(org)`, which keeps
  today's rule (an active `role='finance'` person exists), with a test that credits are byte-identical.
  Whether credits should follow runs is question 6.
- **Approver, with a per-run fallback.** The approvers of a run are the organisation's active
  `payments_approve` holders **who have not already signed this run**. **If there are none, the
  organisation admin may approve** (today's path). This one live rule:
  - keeps every other tenant (no Finance person) working exactly as today;
  - removes Suresh from BrightPath's chain as soon as a Finance person exists;
  - can never strand a run: the sole approver who is also its maker, the last approver revoked or
    switched mid-run, or a run already `finance_checked` by the only Finance person (see in-flight).
  The payload serves `approver_fallback: true` so the page can explain why the org admin sees the
  button.
- **Pairwise-distinct signers, unchanged** (`_collected_signer_emails`): the same person may hold
  prepare AND approve and use them on DIFFERENT runs, never both on one (question 4).
- **"Waiting for you":** the server computes `your_step` per run (`sign` / `check` / `approve` /
  null) with one pure predicate, `payments.next_step_for(run, admin)`, which `sign()` also uses, so
  the list and the gate cannot disagree. The Payments page shows a "Waiting for you" block above the
  run list. The Payments menu row carries a count badge. A badge is a number, so it adds no message
  string.
- **Emails:** the "ready" email after the maker signs goes to the approvers (Finance), else to the
  checkers when the check is armed, else to the org admins under the fallback. The wording becomes
  "awaits your approval". The Vircle instruction email says "approved by" and copies the approver
  (`payment_mail.py:144-151`).

### In-flight runs on deploy day

| Run status when the change lands | What happens (no data change) |
|---|---|
| `draft` | Unchanged. The maker signs and the email now goes to Finance. |
| `admin_signed`, waiting for the org admin (organisation had no Finance person) | Under the new rule the approver is a `payments_approve` holder. If there is none, the org admin approves under the fallback, exactly as before. |
| `admin_signed`, waiting for Finance's check (BrightPath today, if Finance exists) | Finance now APPROVES directly, and the run completes on that signature. Suresh's countersignature is skipped, which is the change the owner asked for. |
| `finance_checked`, waiting for the org admin | Finance has already signed, so distinctness bars them from approving too. Nobody else is eligible, so **the fallback lets the org admin approve, exactly as today**. Nothing is stranded. |

Belt and braces: the cutover note (`docs/scholarship/finance-approves-cutover.md`, Sprint 2) lists
runs mid-chain with a read-only query, and recommends deploying on a day when the query returns
none (question 5).

---

## Safety rules that hold for every mix

| Rule | Where it is enforced today | After |
|---|---|---|
| Nobody QCs a case they reviewed or a verdict they recorded | `base.py:348`, `base.py:357` | Unchanged. These rules key on the PERSON, not the role |
| Nobody approves (or checks) a run they prepared or already signed | `payments._collected_signer_emails` | Unchanged, pairwise across all three slots; super fills one slot |
| Assigned only to people with `review` | `verdict.py:520`, `lifecycle.py:288`, web picker | `has_perm('review')`, served as an `assignable` flag per row so the web never re-derives it. Super override per R1 |
| `qc` requires `see_all` | n/a | The editor adds it and the server refuses the list without it |
| Removing `review` from somebody holding in-play cases is refused | `staff_lifecycle` (`has_open_cases`, Admin→Finance) | The same refusal on the permissions PATCH, under a row lock (the TD-382 class; use TD-383's choke-point if built by then) |
| Nobody edits their own permissions, an org_admin's, a super's or a partner's | `_staff_target_manageable` | The same check |
| Lead-tier powers (`manage_team`, assign, configuration) cannot be granted | n/a | The catalogue marks them; the PATCH refuses them |
| A role change (pairs, 2026-10-09) resets a custom set to the new preset | n/a | The dry run names what is lost; `ROLE_PAIRS` is unchanged |

---

## Roadmap (four sprints, three released stages)

Ordering: the hard dependency comes first (S1, the foundation), then the riskiest change (S2,
money), then the broad conversion (S3), then the editor (S4), which is what Rohini needs. Every sprint
is money, identity or eligibility work, so **every sprint gets an adversarial review before its push**
by an agent that did not build it. The review brief carries that sprint's door list and asks for the
door that is not on it.

### Sprint 1 — the foundation, and the invite message (medium) · 9.0 h · Stage 1

**Goal:** permissions exist, are served and are proven to reproduce today, with no visible change
except the invite message.

**Scope:**
1. **Moves-only split first, as its own commit:** `PartnerAdmin` → `apps/courses/models_staff.py`,
   re-exported from `models.py` (`models.py` reads 1240 lines against its 1244 budget). Then the
   invite, resend, list and revoke views move from `courses/views_admin.py` (1161 of 1165) into
   `courses/views_staff.py`. Ledger keys move through `_moved`, and `AdminInviteView.post`'s
   183-line function budget moves with it.
2. `apps/courses/staff_permissions.py`: the catalogue, presets, dependency rule, lead-tier rule,
   `holders(org, key)`. `PartnerAdmin.permissions` (nullable JSON) +
   `permission_set` / `has_perm`. Migration `courses/00NN` (additive, migrate-first; the DDL and
   ledger row in its docstring).
3. **Characterisation, the heart of the sprint:** `apps/courses/tests/test_permission_presets.py`, a
   golden table of every converted gate in Appendix A × every preset (+ super, partner), written
   **against today's role checks and green on today's code before anything converts**. S2 and S3
   must keep it green. S2 changes only the payment rows, each named in the test with the owner's
   2026-10-19 ruling. Plus a reverse sweep: every catalogue key reaches at least one gate, and every
   preset role resolves.
4. `/admin/role/` serves `permissions` / `preset` / `custom`. `lib/staffPermissions.ts` +
   `staffPermissionsDrift.test.ts` (both directions, read from the api source).
5. **The invite message fix** (`views_staff.py`, ex-`views_admin.py:652-655`, also `:728`, `:754`):
   when the address belongs to somebody **already in the caller's own organisation**, answer
   409 `already_on_team` with their name and preset: "Rohini is already on your team as Reviewer.
   To change what she can do, open People → Rohini." When the address belongs to anyone else (another
   organisation, a platform account, a student login), keep one neutral answer that confirms nothing
   about the other account: "This email address can't be invited. Ask HalaTuju support." The web
   (`organisation/staff/page.tsx` invite dialog) shows the served message and makes **no new string
   for the cross-org case** (the text is served).
6. R1's read-only production query (in-play cases assigned to non-reviewers), with the result written
   into this plan. **Done 2026-10-19 — see R1 above: 68 with reviewers, 1 with an org_admin (awarded),
   none with admin / qc / finance.**

**As built (2026-10-19, branch `perm-plan`):** commits 1-2 are the moves-only splits; commit 3 adds the
catalogue, the field, migration `courses/0081_partneradmin_permissions` and the golden table — green
on the unconverted code, before anything else changed; the last commit serves `/admin/role/`, the web
lib + drift test and the invite message. Two build notes for S2/S3:
- **The S1 presets are TODAY's powers**, not the go-live table above: `finance` holds
  `payments_check` and `org_admin`'s lead tier holds `payments_approve`, because S1 must reproduce
  today and no payment gate converts until S2. S2 changes exactly those two presets and the three
  golden rows marked `s2` (check, approval, check-armed), quoting the owner's ruling.
- **⚠ SUPERSEDES item 5's "a student login" (lead ruling 2026-10-19, adversarial review):** an
  address that belongs to a student's or sponsor's own login is NOT answered with the neutral 409. It
  keeps the existing 201 "already has an account — access granted" path: a person with a student
  login may legitimately become staff, and the inviter learns only that the address has a HalaTuju
  login — pre-existing behaviour, accepted. The neutral `not_invitable` answer covers existing STAFF
  accounts the caller cannot see on People (another organisation, a super, a referral partner).
- **Review fixes (same day):** a TD-335 re-invite resets `permissions` to NULL (the new role's preset,
  never a stale custom set — the S4 door-list ruling, brought forward); the invite matches the stored
  address case-insensitively; a listed-but-unmanageable colleague (a fellow org_admin) is told "Ask
  HalaTuju support to change this." instead of being sent to People; `permissions` is read-only in
  the Django admin until S4; the golden table gained seven rows (payment email recipients ×2, the
  served check flag, `_other_active_finance`, the run-in-progress and open-cases switch refusals, the
  assignable list as an org_admin reads it) — 26 rows, 8 marked `s2`.
- **S3 finding:** the lead tier holds `qc`, so "people who hold `review` or `qc` appear on Reviewers"
  would ADD org_admins to the Reviewers tab, where they are not today. Declared as a divergence in
  the golden table; S3 must exclude the lead tier there (or ask the owner).

**Acceptance:** the golden table is green on the unconverted code and after the split; migrate-first
is applied with no ledger gap; both suites and `bundle-budget` are green; the invite fix has tests for
the same organisation, another organisation, super and Google-address cases.

**Door list (S1: who may be invited):** `AdminInviteView` both branches (Google / password), the
TD-335 re-invite (`staff_reinvite.may_reuse`, `provision`), `AdminResendView`, the
`invitations.create_or_refresh` writer, `/admin/role/`'s `withdrawn` answer. Readers of the new
message: the invite dialog, People. The adversarial question: **can the new message tell an
org_admin that an address exists in ANOTHER organisation?** It must not.

**Files (~16):** `courses/models.py`, new `courses/models_staff.py`, new `courses/staff_permissions.py`,
migration, `courses/views_admin.py`, `courses/views_staff.py`, `courses/urls*.py` (imports only),
`code-standards.json` (api), 3 api tests; web `lib/staffPermissions.ts`, `lib/admin-auth-context.tsx`
(type), the staff page invite dialog, 2 web tests; docs (`decisions.md`, `role-matrix.md` header,
`ARCHITECTURE_MAP.md`, `CHANGELOG.md`).

| Task | h |
|---|---|
| Moves-only splits (two commits, ledger `_moved`) | 1.0 |
| Catalogue module, field, migration, `has_perm` | 1.5 |
| Golden characterisation table + reverse sweep | 2.75 |
| `/admin/role/` + web lib + drift test | 1.0 |
| Invite message fix + tests | 0.75 |
| Docs, adversarial review, migrate-first, deploy check | 2.0 |
| **Total** | **9.0** |

### Sprint 2 — Finance approves payment runs (high: money) · 8.0 h · Stage 2

**Goal:** the owner's option A, live. Admin prepares, Finance approves, Suresh drops out, and
nothing in flight strands.

**Scope:** `payments.sign` / `cancel` / `set_item` gates on `payments_*` (+ lead-tier
create/edit/cancel, + the per-run approver fallback); `finance_check_required` re-keyed to
`payments_check` with the new `check_step_required` key alongside; **`credit_check_required` split
out for wallet credits, unchanged**; `next_step_for` + `your_step` on the list and detail payloads;
`_PaymentsBase` read/write gates on permissions; emails (`payment_mail.py`); `staff_lifecycle`
consequence words (switching to Finance = "becomes a payment approver; wallet credits gain the
finance check"; the last Finance leaving = "the org admin approves runs again; credits lose the
check"); web: `payments/page.tsx` (canCreate → prepare, the "Waiting for you" block),
`payments/[id]/page.tsx` + `paymentStatus.signOffView` (buttons from the served `your_step`, cards by
step, the fallback notice), `navigation.ts` Payments row (roles → any `payments_*`, count badge);
Guide + FAQ for **Finance, Admin and Org admin** (the "Why can't I countersign" entries become "Who
approves a run"); `role-matrix.md` Payments section rewritten; a `decisions.md` entry superseding
"the finance role holds the CHECK, not the decision" (role-matrix, Money bullet); the cutover note.

**Acceptance:** the golden table is green except the named payment rows; tests for every door below;
credits byte-identical (their own snapshot test); the adversarial review is done and its findings
fixed or answered; the cutover query has been run read-only.

**Door list (S2: every path that signs, completes, cancels or reverts a run, and every reader of the
new state):**
- **Into a signed state:** `sign` at draft (maker), at admin_signed (check when armed), at
  admin_signed / finance_checked (approve), the approver fallback, a super in any one slot.
- **Completion:** `complete()` (Disbursements released, `payment_credit` decremented, the maintenance
  flip, the CSV, the Vircle email with the approver CC'd, `actioned_by` = the approver's email).
- **Out:** `cancel` (prepare holders + lead tier; Finance still cannot); `set_item` revert to draft
  (clears all three triples); the run CSV (readable from `admin_signed`).
- **Live-rule movers:** granting or removing `payments_check` (arms or disarms a run sitting at
  `admin_signed`); granting or removing `payments_approve` (fallback on or off); revoke / restore of a
  Finance person; Admin ↔ Finance change role (`staff_lifecycle.runs_in_progress`, consequence);
  delete (footprint counts all three signatures, unchanged).
- **Readers:** run list, run detail, `your_step`, the badge count, funding summary, CSV, both emails,
  the Vircle email, `staff_footprint`, the People "work" tooltip, Guide/FAQ text,
  **wallet credits' `finance_check_required` (`sponsors.py:437`)**, Programme Overview money (it reads
  disbursements, so no change, but asserted), `test_org_fence.py` classification of any changed view.
- **In-flight:** the four rows in the table above, each a test.

**Files (~24):** `payments.py`, `views_admin/payments.py`, `emails/payment_mail.py`, `sponsorship.py`
(predicate split only), `views_admin/sponsors.py` (one line), `staff_lifecycle.py`, `models/funding.py`
(docstrings), 3 api tests; web `payments/page.tsx`, `payments/[id]/page.tsx`, `lib/paymentStatus.ts`,
`lib/navigation.ts`, `lib/admin-api/payments.ts`, the badge source, 3 web tests; manual
`role-finance.tsx`, `role-admin-general.tsx`, `role-org-admin.tsx`, `faq.tsx`; en/ms/ta; docs.

| Task | h |
|---|---|
| `sign` / gates on permissions, approver fallback, check re-key, credit split | 2.25 |
| `next_step_for`, `your_step`, "Waiting for you" block, badge | 1.25 |
| Emails (ready → Finance, Vircle wording) | 0.5 |
| Web sign-off view and run page | 1.0 |
| `staff_lifecycle` consequences | 0.5 |
| Guide/FAQ (3 chapters + FAQ), role-matrix, decision, cutover note, Sol tag | 1.25 |
| Adversarial review + fixes | 1.25 |
| **Total** | **8.0** |

**As built (2026-10-19, branch `perm-s2`, base `378c7601`):** a moves-only commit first
(`payments.py` 748 → 632: the chain to new `payments_chain.py`, re-exported), then the change. Notes for
the reviewer and for S3/S4:
- **Exactly the plan's chain**, in `payments_chain.py`: `next_step_for` (the one predicate behind `sign`
  and `your_step`), `may_read` / `may_prepare` (the view gates), the per-run `approver_fallback`,
  `finance_check_required` re-keyed to `payments_check` holders (+ `check_step_required`), and
  `credit_check_required` (the old role rule) for wallet credits. Presets: `finance` = `payments_approve`;
  `LEAD_TIER` minus `payments_approve`. No migration.
- **Two hardenings beyond the plan (lead may overrule):** `sign()` re-reads the run under
  `select_for_update` (two approvers could otherwise both complete — and pay — a run; a test proves a
  stale copy now gets `bad_state`); and the service refuses a signer from another organisation
  (`wrong_role`), not only the view's 404.
- **Golden table:** the 8 `s2` rows now hold the new truth with the old answer kept in `was`
  (`sign_the_check` is armed by a custom holder, since no preset holds the check);
  `other_active_finance` and `switch_refused_for_unfinished_run` keep their answers (their rules now
  read `payments_approve`); `payments_read`'s RULE gained "or the lead tier" — its answers did not move.
- **Role-change consequences** keep the codes `finance_check_on` / `_off` (keyed on the finance ROLE,
  which is what both the approver preset and the credit check turn on); only the words changed. S4's
  `approver_fallback_on` / `_off` consequences for custom sets are still S4's.
- **⚠ Deferred to S3 (not a contradiction, a mechanism):** the Payments MENU row's `roles` → "any
  `payments_*`" predicate. `navigation.ts` sits at its line limit and S3 builds the perms predicate for
  Applications / Spending / Payments together; for every preset the row's visibility is identical
  either way. S2 added only the row's `badge`.
- **⚠ For S4's editor (door list):** the CHECK is armed per ORGANISATION, as planned. A person given
  Prepare + Check who prepares a run while being the only checker would hold it at `admin_signed` until
  someone else holds Check (or the run is edited / cancelled). No preset can produce this; the editor
  should warn, or the owner may ask for a per-run check fallback.
- **Bundle:** en.json gained 3 keys and lost 7 proven-dead ones; median 228.513 → 228.641 kB (0.4 kB
  headroom left).
- **⚠ SUPERSEDED by review fix 2:** the "check armed per ORGANISATION" door above — the check is now
  armed PER RUN (`check_required_for`), so it cannot strand. **Review fixes (adversarial review, 2026-10-19 — SHIP AFTER FIXES):**
  1. **HIGH — an edit or cancel racing the approval could pay a run twice** (old bug, on the door
     list): `set_item` and `cancel` are now atomic and re-read the run under `select_for_update`,
     refusing a completed / cancelled run (`not_editable` / `bad_state`); `_revert_to_draft` clears ALL
     THREE triples; `set_item` writes only the item's three fields (the disbursement link can no longer
     be overwritten); `complete()` refuses a run already paid (`already_paid`, belt and braces).
  2. **The CHECK is armed PER RUN** (`check_required_for(run)` = somebody eligible for THAT run holds
     `payments_check`), like the approval — a Prepare+Check maker can never strand their own run. The
     payload's `check_step_required` / `finance_check_required` are this per-run answer (true also once
     a check is collected, for the layout); the email routing follows it.
  3. (Owner decision pending: the org admin's notice of a released run — not changed.)
  4. **A holder who has never signed in is not eligible** (`first_seen_at IS NULL`): production —
     BrightPath's only Finance person (id 24) had never signed in. Until they do, the org admin approves
     under the fallback **and receives the "awaits your approval" email; Finance is not emailed** (they
     cannot act on it yet); the moment they first sign in they are the approver for every run in flight.
  5. `_in_organisation` / the holder reads use `organisation_id` (no per-run organisation query); the
     detail payload shares one holders cache.
  6. `_refusal` says `finance_check_required` only to someone who would approve after the check (an org
     admin while Finance can approve gets `wrong_role`); somebody who already signed is told
     `same_signer` first. The Guide's "including yours" line (Finance's approval can never be cleared)
     is reworded. Deploy order: **API first, then web.**

### Sprint 3 — the gates read permissions (medium-high: who sees files) · 10.0 h · Stage 3a

**Goal:** every gate in Appendix A, groups A–D, reads `has_perm`. For presets nothing changes (the
golden table proves it). Mixed sets work end to end on the server, though only a reviewed SQL update
can make one until S4.

**Scope (server):** `_b40_scope` (none / assigned / all from `see_all` and `review`),
`_can_review_app`, `_require_qc`, `services.REVIEW_ROLES` → `has_perm('review')` (+ R1 super
override) in `_can_review`, `set_paused` and `scheduling._can_review`; the assignable-admins list
(served `assignable`); the assign endpoint's target rule; the AI-reliability card gate; the Spending
gate (`_SPENDING_ROLES` → `spending`); the Reviewers tab list (people who hold `review` or `qc`
appear on Reviewers, where pause and gift live). **Web:** `navigation.ts` items Applications,
Spending and Payments gain a `perms` predicate (`canSee` / `canAccess` take the served set);
`view.tsx` `canQc` / `canWrite` and `QcPanel` swapped one-for-one to `hasPerm` (line-neutral, hotspot);
the picker filters (`scholarship/page.tsx:404,516`, `officerCockpit.ts:1632`) read the served
`assignable`; `useGiftGate` unchanged (no door for a team member, the page asks).

**Acceptance:** the golden table is unchanged and green; new combination tests: **Reviewer +
Spending** (Spending page 200, Applications assigned-only, no Payments, no money on the Overview),
**Finance + Review** (assigned files 200, unassigned 403, the funding-summary serializer key set
unchanged), **Admin minus Spending** (Spending 403), **QC without `see_all`** refused at save; the web
drift test is green both ways; the adversarial review is done.

**Door list (S3: every path that puts a person in reach of an applicant's file, or a case in a
person's hands):** `_scoped_application` and every caller (cockpit detail, documents and signed URLs,
interviews, interview slots, resolution, lifecycle, profiles, verdict); `_require_app_write` /
`_require_open_case`; `_require_qc`; assign / reassign / unassign; the assignable list;
`scheduling` propose and book; pause and unpause; the review nudges (`send_review_nudges` reads
`assigned_to`); reviewer emails to the assigned person; the Overview `mine` section (preset-bound by
R2: a Finance + Review person sees no "my cases" tile; the Applications row is their door, which is
asserted); `reviewer_profile_complete` (preset-bound: a non-reviewer preset holding `review` is NOT
held on the profile page, and the picker shows their languages as unknown, which is asserted);
Applications list / filters / CSV through `_b40_scope`; the Spending page, its flags and categories,
and its CSV if any. **Readers newly reachable:** the files of assigned students for a Finance +
Review person (question 1); the named-student Spending page for a Reviewer + Spending person.

**Files (~30):** `views_admin/base.py`, `services/assignment.py`, `scheduling.py`, `views_admin/lifecycle.py`,
`views_admin/verdict.py`, `views_admin/spending.py`, `views_admin/reviewers.py`, 4 api tests; web
`lib/navigation.ts`, `lib/staffPermissions.ts`, `app/admin/scholarship/[id]/view.tsx`,
`view/QcPanel.tsx`, `view/AssignAndWitness.tsx`, `app/admin/scholarship/page.tsx`,
`lib/officerCockpit.ts`, `app/admin/spending/page.tsx`, `components/admin/AppShell.tsx` (passes
perms), `navigation.test.ts` snapshot, 3 web tests; docs.

| Task | h |
|---|---|
| Server gates: scope, write, QC, review targets, pause, scheduling | 3.0 |
| Spending + Reviewers-tab gates | 0.75 |
| Web nav predicate, cockpit swaps, picker `assignable` | 2.5 |
| Combination tests; golden table re-run; drift both ways | 1.5 |
| Adversarial review + fixes | 1.25 |
| Docs (role-matrix rows A–D, decisions, ARCHITECTURE_MAP) | 1.0 |
| **Total** | **10.0** |

**As built (2026-10-19, branch `perm-s3`, base `09b8766e`):** a moves-only commit first (`navigation.ts`
675 → 621: `searchNav` / `chordTarget` / `CHORD_PREFIX` to `navigationJump.ts`, re-exported), then the
change. No migration, no new strings. Notes for the reviewer and S4:
- **Owner ruling (2026-10-19, "yes"):** org admins stay OFF the Reviewers tab. Built: the tab lists TEAM
  members holding `review` or `qc` (`staff_permissions.team_holding`), never the lead tier; the golden
  row's divergence is gone and its rule says so.
- **R1 as built:** `services.REVIEW_ROLES` is gone. `is_review_target` = `review` OR the role is in
  `R1_SUPER_TARGET_ROLES` (admin, qc, org_admin) — the super's wider choice, keyed on ROLE because the
  service is caller-agnostic. `may_assign_to(caller, target)` is the endpoint's rule (org_admin → own
  org `review` holders, never a super) and is SERVED as `assignable` on the list.
- **The assignable LIST is the old five roles PLUS `review` holders** (not "review holders only"), so a
  reviewer whose set loses `review` while holding a case still renders (bug #66); `assignable` narrows.
- **Web fallback rule:** a registry row's `perms` answer only a TEAM member whose payload carries
  `permissions`; everyone else (org admin, super, partner, an old payload) is answered by `roles`. The
  preset-parity sweep (`staffPermissionsDrift.test.ts`) asks every `perms` row × role with the api's
  presets. The cockpit switches have no fallback: the cockpit test harness now serves each role's
  preset list, read from the api (`src/test/staffPresets.ts`).
- **Deliberately left on role** (reason in decisions.md): `_require_reviewer`, the Overview sections,
  `reviewer_profile_complete`, `canFilterByAssignee`, the reviewer-detail `mayPause` (it mirrors the
  group-G pause / gift endpoints), the picker's role suffix, wallet credits, H/I.
- **For S4's editor:** removing `review` from someone holding in-play cases must stay refused (their
  cases would leave `_b40_scope` 'assigned'); **and so must removing `see_all` from an admin / qc
  holding in-play cases** (review fix 1: without `see_all` or `review` they cannot open a case they
  hold); `team_holding` and `may_assign_to` are the readers to re-check; a `qc` without `see_all` is
  already read fail-closed.
- **For S4 (review fix 4):** the reviewer-detail page's `mayPause` is still on ROLE (super /
  org_admin), which matches the pause / gift endpoints' gate; but the server now lets a Finance +
  Review person be PAUSED (`is_review_target`) and lists them on the Reviewers tab. S4 must align the
  page with the server (the target side), so their row offers what the endpoint accepts.
- **Review fixes (adversarial review, 2026-10-19 — SHIP AFTER FIXES):**
  1. (medium) **The R1 super override now needs `see_all`:** `is_review_target` = `review`, or an R1
     role (admin / qc / org_admin) that still holds `see_all`. A custom-set admin / qc with neither
     could otherwise be handed a case their scope cannot open (stranded, while nudges named the
     student). The served `assignable` follows (a super's flag is `is_review_target`). Presets
     unchanged (every R1 preset holds `see_all`).
  2. (low) **Golden row for the legacy super flag:** `is_super_admin=True` with role `reviewer`
     answers every gate as a super; the one moved answer (an org_admin could assign a same-org
     legacy super with role reviewer before S3; `may_assign_to` says never a super) is declared in
     `LEGACY_FLAG_MOVED`. Production has no such row (lead, 2026-10-19).
  3. (low) **`defaultRoute` passes the served permissions to `canSee`**, so the landing matches the
     menu for a custom set (line-neutral; `AdminRoleLike` gains `permissions`).
  4. (low) The reviewer-detail `mayPause` stays on role; S4 must align it with the server.
  5. (nit) Org-fence tests for custom-set holders (org A vs org B: `_scoped_application`,
     `_can_review_app` / `_require_qc` with `qc`, the assignable list, the Reviewers tab); the two
     staff lists joined `test_query_budgets.py` (4 admitted records, 6 queries flat at 2 and 5 staff).
- **Bundle:** no i18n key added; median 228.640 → 228.813 kB (code only; 0.2 kB headroom left — S4 must pay for its editor, TD-360).

### Sprint 4 — the permission editor on People (medium) · 9.0 h · Stage 3b

**⚠ DESIGN OF RECORD (owner, 2026-10-21): the owner approved a clickable HTML mock IN PLACE OF the Stitch
prototype below** — Stitch timed out twice. The mock is the approval: on the person's page a card "What
<name> can do", subtitle "Starts from the <preset> set…", groups STUDENTS (Review assigned students / See
all students / Quality check, held behind "Needs See all students") and MONEY (Spending / Prepare / Check /
Approve payment runs), each row a label, a one-line description and a site Toggle; a "Custom" chip beside
the preset chip; a "changed" marker per row; a live consequence line from the server's dry run; "Save
changes" and "Reset to <preset>"; the footnote "You cannot change your own permissions or an organisation
admin's."

**Goal:** an org admin (or super) changes what a person can do, safely, and Rohini gets review +
spending.

**Before code: a Stitch prototype** (workspace rule; HalaTuju Stitch project `10844973747787673276`)
of People → a person → **Permissions**: the preset name with a "custom" marker, the switches grouped
**Students** (Review assigned / See all / Quality check) and **Money** (Spending / Prepare runs /
Check runs / Approve runs), the dry-run consequence line, Save. **Site Toggles, never tick boxes**
(owner rule). The owner approves before any template is coded.

**Scope:** `PATCH admin/admins/<id>/permissions/ {permissions, dry_run?}` (super / org_admin;
`_staff_target_manageable`; row lock; refuses `lead_tier`, `qc_needs_see_all`, `has_open_cases`
when removing `review`, `not_active`; consequences `check_on` / `check_off`,
`approver_fallback_on` / `off`, `files_widened` when `review` meets a Finance preset); the
`staff_permission_changes` table (migration, RLS + policy) and the AUDIT line; People rows show
permission chips; `staff_lifecycle.change_role` resets `permissions` to NULL (the dry run says so);
the editor is a lazy chunk; Guide: a new org-admin section "Changing what someone can do", and each
role chapter says "your organisation may have given you more" (the Guide also opens the chapter
sections for permissions held beyond the preset: `manualRole` → chapter set); FAQ entries; Sol tag;
`role-matrix.md` restructured as **catalogue + presets + lead tier** (the matrix's own currency rule).

**Acceptance:** Rohini's combination is made through the screen in a local run and every gate
answers as S3's tests say; every refusal and consequence is tested; `test_org_fence.py` classifies
the new endpoint; `bundle-budget` is green with the measured headroom stated; the adversarial
review is done.

**Door list (S4: every path that changes who may see, review, QC or sign):** the PATCH (each key
added or removed); Change role (resets); revoke and restore (permissions survive a revoke unchanged
and come back on restore, which is asserted); delete (footprint unchanged); a TD-335 re-invite of a
switched-off account (**ruling: a re-invite resets the set to the invited preset**, because the
inviter chose a preset and an old grant must not come back with it; the 2026-10-09 lesson about the
re-invite that resurrected a revoked worker); the invite (NULL); assignment racing a `review` removal (lock + re-check, the
TD-382 class); granting `payments_approve` / `payments_check` mid-run (S2's live rules); the cached
`/admin/role/` of the edited person (server refuses, asserted). **Readers:** People list
`manageable` / chips, Invitations grouping (by preset, unchanged), the welcome letter (by preset,
unchanged), the Guide chapter set.

**Files (~22):** new `apps/scholarship/staff_permissions_admin.py` (service), `views_admin/staff.py`,
urls, migration, model module for the history table, `staff_lifecycle.py`, 3 api tests; web new
`components/admin/PermissionEditor.tsx` (+ lazy wrapper), `components/admin/StaffAdmin.tsx`,
`app/admin/organisation/reviewers/page.tsx`, `lib/admin-api/admins.ts`, `content/manual/index.ts`,
`role-org-admin.tsx` + the four other role chapters (a line each), `faq.tsx`, en/ms/ta, 2 web tests;
docs.

| Task | h |
|---|---|
| Stitch prototype + owner approval round | 1.0 |
| PATCH service: rules, lock, consequences, history table, audit | 2.25 |
| Editor UI (lazy), chips, change-role reset wording | 2.0 |
| Strings within budget (see below) + Sol tag | 0.5 |
| Guide + FAQ (new section, chapter visibility, five chapters a line each) | 1.25 |
| Adversarial review + fixes | 1.25 |
| Docs (role-matrix restructure, decisions) | 0.75 |
| **Total** | **9.0** |

**As built (2026-10-21, branch `perm-s4`, base `cd9b69ea`, commit `a6cc35d1`):** no moves-only split was
needed (no touched file sat at its line). Migration **scholarship `0175_staff_permission_changes`** (the
next free number in the tree; DDL + RLS + policy + ledger row in its docstring). Notes for the reviewer:
- **Design:** the owner's approved mock, not Stitch (see the ruling at the top of this section).
- **Endpoint:** `GET / PATCH admin/admins/<id>/permissions/` — GET serves `preset`, `permissions`,
  `custom`, `editable`, `keys`; PATCH (and its dry run) answers `added`, `removed`, `consequences`,
  `changed`. Refusals: `own_permissions` (403), `not_editable`, `unknown_permission`, `lead_tier`,
  `qc_needs_see_all`, `bad_request`, `not_active` (400), `has_open_cases` (409, with `open_cases`).
- **Stranding (S3 notes):** refused when the set loses `review`, or loses `see_all` without keeping
  `review`, while the person holds in-play cases. **The TD-382-class race** is closed by one lock on the
  PERSON's row, which `assign_reviewer` now also takes (re-reading its target); the test feeds it a stale
  object holding `review` after the removal and gets `not_reviewer`.
- **Consequences** are computed against SIGNED-IN holders (S2 fix 4); a target who never signed in gets
  `not_signed_in` instead of a fallback change that would not happen yet. `files_widened` = a Finance
  person gaining `review` or `see_all`. `prepare_and_approve` added (not in the plan's list) because the
  mock's line says it.
- **Readers:** People chips on both tabs; `pausable` on the reviewer detail (S3 fix 4 closed); the Guide's
  per-section `perm` tags (only keys no other preset holds — a test sweeps every preset); the Invitations
  grouping and the welcome letter stay on the preset (`role`), unchanged.
- **Doors and their tests (`test_permission_editor.py`):** the PATCH per key (refusals and consequences
  classes); Change role resets + history (`TestChangeRoleResets`); revoke/restore keep the set; delete
  keeps the history (footprint unchanged — a permission change is not "work"); re-invite resets (S1's test
  stands); the invite (NULL, unchanged); assignment racing a removal; granting `payments_approve` mid-run
  (`approver_fallback` flips live, `next_step_for` → approve) and `payments_check` (`finance_check_required`
  flips); the edited person's cached `/admin/role/` (Spending 403 on the next request).
- **Not done / for the lead:** the browser click-through (the console needs a Supabase session; the local
  run drove a real `runserver` over HTTP with the screen's exact calls instead); a re-invite's reset
  writes no history row (it lives in `courses`; the cross-app ratchet); the Django admin keeps
  `permissions` read-only on purpose; ms/ta strings are first drafts for Sol.
- **Bundle:** median 178.831 → 178.855 kB (1.1 kB headroom); the editor is its own chunk.
- **Review fixes (adversarial review, 2026-10-21 — SHIP AFTER FIXES; `f9499251`):**
  1. (HIGH) A Reviewer / QC set holding neither `review` nor `qc` is refused (`would_leave_people`):
     they would appear on neither People tab, so nobody could reach their card, Revoke or Delete. The
     editor warns first. The PATCH is the only writer of a custom set (Change role and re-invite reset to
     a preset; the Django admin is read-only).
  2. (MEDIUM) The run's CREATOR (`created_by`, casefolded) may not check or approve it by permission
     (`payments_chain._barred_from_approving`, read by `eligible_checkers` / `eligible_approvers`,
     `next_step_for` and `_refusal` → `same_signer`), so the list, the gate and the emails agree. The
     organisation admin's fallback keeps today's rule (the org admin creates runs and approves only
     when nobody else can). ⚠ An EDIT is not recorded per person (no column); an edit reverts the run to
     draft and clears every signature, so the editor would have to sign again as maker to be barred.
  3. (MEDIUM) `files_widened` split: `files_widened_all` (gains `see_all`, any role — a Reviewer too)
     and `files_widened_assigned` (gains `review` from no file access).
  4. (MEDIUM) Change role's dry run serves `consequences` = the editor's own rule from the held set to
     the new preset (so a reset's approval-fallback / check change is named); `finance_check_on/off` now
     word only the wallet-credit check.
  5. (LOW) `staff_lifecycle.open_cases` also counts an assigned case whose decision is REOPENED
     (`decision_reopened_at`), for both the editor and Admin → Finance.
  6. (LOW) `approver_fallback_off` wording excepts runs the person prepared or already signed.
  7. (LOW) `assign_reviewer` re-asks `may_assign_to(by_admin, target)` on the LOCKED row.
  8. (LOW) GET `editable` is false for a revoked person; the card says "restore them first".
  9. (LOW) The editor drops the previous preview when a new dry run starts (Save needs the new one).
  10. (NIT) `dry_run` only on JSON `true`; a save resolving to the same keys writes nothing
      (`changed: false`, no history row).
  Bite-checked 1-4 (each guard removed: its test fails). api 8554 → 8566; jest 4372 → 4375; bundle
  median 178.856 kB (1.1 kB headroom).

---

## Stages, and when Rohini is unblocked

| Stage | Sprints | What people notice | Released |
|---|---|---|---|
| 1 | S1 | Only the clearer invite message. | Alone |
| 2 | S2 | Finance approves runs, has a "Waiting for you" list and gets the "ready" email; Suresh stops countersigning. | Alone (money; its own review) |
| 3 | S3 then S4 | S3: nothing (presets proven identical). S4: the permission editor. **Rohini can be given review + spending the day S4 is live.** | S3 may ship on its own, which keeps the blast radius small; S4 follows |

If BrightPath needs Rohini sooner, the earliest honest point is **S3 live**, using a reviewed SQL
update of her `permissions` (as referral partners are marked today). This is offered, not
recommended.

## Bundle budget (TD-360)

`en.json` rides on almost every route, and the tightest student routes have about 0.2–0.5 kB of room.
New strings by sprint: S1 ≈ 1 key (the cross-org message is served), S2 ≈ 6 keys ("Waiting for you",
"Approved by", the fallback notice and similar; the badge is a number), S4 ≈ 20 keys (the editor).

- **Recommended:** schedule TD-360 (split the catalogue by audience, already promoted to the next
  hygiene sprint, platform cost, not billed to #39) **before S4**. Console strings then never reach a
  student route, and the editor's ~20 keys cost the tightest routes nothing.
- **If TD-360 has not landed by S4:** permission names and one-line descriptions are **served by the
  api with the catalogue** (en/ms/ta held in `staff_permissions.py`; precedent: the served pre-U
  track label, TD-280). The editor then keeps only ~6 frame keys in `en.json`, paid for by deleting
  proven-dead keys. Run `npm run bundle-budget` BEFORE adding any string (lessons.md, 2026-10-05).
  Caveat: server-held Malay and Tamil labels are invisible to Sol. They need an export for the owner's
  review, which is a reason to prefer TD-360.
- S2's ~6 keys are measured at sprint start, and are reused from existing keys where one says the same
  thing.

## Code health: files near their size line, and hotspots (re-measure at each sprint start)

| File | Lines (wc) / ledger budget | Rule for this arc |
|---|---|---|
| `courses/models.py` | 1240 / 1244 | S1 moves `PartnerAdmin` out first (moves-only commit) |
| `courses/views_admin.py` (hotspot #6) | 1161 / 1165; `AdminInviteView.post` 183-line function budget | S1 moves the staff views to `views_staff.py` first |
| `scholarship/payments.py` | 748 / 736 (ledger count) | S2 puts `next_step_for` and approver logic in it only if the ledger allows; otherwise new `payments_chain.py` |
| `scholarship/sponsorship.py` | 1006 (over 1000) | S2 touches one line (the predicate name) |
| `web lib/navigation.ts` | 675 / 655 (ledger count) | The perms predicate lives in `lib/staffPermissions.ts`; navigation gains a field, not logic |
| `web …/scholarship/[id]/view.tsx` (hotspot #3) | 1351 / 1338 | Line-neutral swaps only |
| `web lib/officerCockpit.ts` (hotspot #1) | 1650 / 1637 | One filter line swapped to the served flag |

The ledger's own count is authoritative. Read it with `Settings/_tools/code_health.py` at each sprint
start; do not trust these figures (sprint-start: re-derive the plan's numbers). New logic goes into
new small modules (`staff_permissions.py`, `staffPermissions.ts`, `PermissionEditor.tsx`), never
into a hotspot. A run of `code_health.py --write` at each close; the S3 close must show `xapp` not up.

## Lessons from `docs/lessons.md` that shape this plan

- A NEW shape in a table needs every reader checked (2026-10-05). That is why S3's door list names
  every caller of `_scoped_application`, and why R2 keeps the gates that cannot take a mixed set
  preset-bound.
- Reverse-sweep drift tests (2026-09-19): `staffPermissionsDrift` and the golden table both run from
  the api side.
- A number in a brief is a hypothesis (2026-09-19): the inventory figure below replaces the brief's
  "~190 in ~53".
- Test the neighbouring states (2026-09-28): the combination tests in S3 are deliberately the mixes
  nobody holds today.
- A shared message file moves every route (2026-10-05): see "Bundle budget".

---

## Open questions for the owner (six, each with a recommendation)

1. **May a Finance person who is also given Review see the files of the students assigned to them?**
   This reverses the 2026-07-23 ruling. *Recommend YES, narrowly:* only the files of students
   ASSIGNED to them (`review` gives "assigned" scope, never "all"); the Finance preset alone still sees
   no file; the funding-summary allowlist is untouched; the editor warns before saving. Worth knowing:
   that person could then approve money for a student they reviewed. Reviewing and paying are
   different decisions, but if you want a rule against it, it is a later small change (the approver is
   refused a run containing a student they reviewed).
2. **Are permissions per organisation, or per gift?** *Recommend per organisation:* one person's
   permissions apply across their organisation's gifts. The existing "which gift a reviewer covers"
   (`PartnerAdmin.programme`, offered work only) stays as it is.
3. **Who may change permissions?** *Recommend the organisation admin and the platform super only;
   never on their own row; never on an org admin, super or partner. "Manage team" stays an org-admin
   power and cannot be switched on for a team member in #39.* Making it switchable needs a "you cannot
   grant what you do not hold" rule: about +2 h, a later change.
4. **May one person hold both Prepare and Approve, and use them on different runs?** *Recommend YES.*
   No one may sign twice on the same run (unchanged). Small teams need this.
5. **What happens to runs already part-signed on deploy day, and to an organisation with nobody who
   can approve?** *Recommend the live fallback:* when nobody eligible holds Approve for a run, the org
   admin approves, as today. No run can strand (see the in-flight table). Deploy Sprint 2 on a day the
   cutover query shows no run mid-chain anyway.
6. **Wallet credits (sponsor money IN) use the same sign-off chain today. Should they follow, so that
   Finance approves credits too?** *Recommend NO for #39:* credits keep today's chain (Admin records,
   Finance checks, the org admin countersigns, since accepting money is the organisation's act). The
   shared live rule is split so credits are untouched. Recorded as a deliberate divergence from the
   2026-07-26 "one chain" decision; moving credits later is about 3 h.

## Hours

| Sprint | What | Estimate |
|---|---|---|
| S1 | Foundation + characterisation + invite message | 9.0 h |
| S2 | Finance approves payment runs | 8.0 h |
| S3 | Gates read permissions | 10.0 h |
| S4 | Permission editor on People (+ Stitch) | 9.0 h |
| **Total** | | **36.0 h** |

**Against the 34 h quoted, this is 2 h (6 %) over.** Where the difference comes from:

- **Payments: 4 h quoted, about 8 h here.** The quote did not price the per-run approver fallback,
  splitting the predicate that wallet credits share, the "Waiting for you" list and badge, the
  in-flight cases or its own adversarial review.
- **Permissions: 30 h quoted, 28 h here** (S1 + S3 + S4 less the payment parts S2 now carries). The
  presets-as-NULL design removed the backfill and the six invite-door changes a table would have
  needed.

**To hold it at 34 h (the owner's choice, not recommended):** release S3 and S4 together with ONE
adversarial review and one deploy (−1.0 h, but a bigger change to review at once), and in S4 write
the Guide as the one new "Changing what someone can do" section plus a line per chapter, without
chapter-visibility changes (−1.0 h; a person with extra permissions then sees only their preset's
chapter). **Not counted in either figure:** TD-360 (platform hygiene, already promoted), any time the
owner spends on Stitch rounds beyond one, and question 3's +2 h or question 6's +3 h if chosen.

## Out of scope

Billing of the organisation; modelling the organisation → Vircle funding (manual, outside
HalaTuju); permissions for sponsors, sources, configuration, contracts, Overview layout (preset-bound
or lead tier, R2); renaming the `org_admin_signed_*` columns; dropping `role` or `is_super_admin`;
per-gift permissions (question 2); a rule barring an approver from paying students they reviewed
(question 1).

---

## Appendix A — inventory of staff-role checks (non-test code, measured 2026-10-19 on `d15c0f14`)

**Totals.** About **225 role-touching code lines in 45 api files** (`halatuju_api/apps`; comments,
docstrings and the unrelated family/parent "role" fields excluded) and about **194 in 55 web files**
(`halatuju-web/src`, imports, type-only lines and tests excluded): **≈ 420 lines in ≈ 100 files**.
That is more than the brief's "~190 in ~53", because a page often repeats one decision across
several JSX lines. Counted as **gate decisions**:

| Bucket | Sites | Files | Fate in #39 |
|---|---|---|---|
| A–E: express a team-member permission | **≈ 66** (45 api, 21 web) | ≈ 28 | **Converted** (S2: E; S3: A–D) |
| F: wallet credits | ≈ 14 | 5 | Preset-bound (question 6); predicate split in S2 |
| G: team and invitations | ≈ 45 | 16 | Lead tier; editor added (S4); invite message (S1) |
| H: org-admin lead powers + preset-bound shared reads | ≈ 60 | 30 | Unchanged |
| I: platform / super / partner | ≈ 230 lines | ≈ 40 | Unchanged |

### A. `review` (convert, S3)
- api `scholarship/views_admin/base.py:80` (`_b40_scope` → assigned), `:247` (`_scoped_application`
  assigned check), `:273` (`_can_review_app` assigned branch: "assignment grants write", kept)
- `scholarship/services/assignment.py:32` `REVIEW_ROLES`, `:52` `_can_review`, `:79` `set_paused`
  target, `:142` refusal reason
- `scholarship/scheduling.py:106-118` `_can_review`, `:307`, `:315-316`
- `scholarship/views_admin/lifecycle.py:288` assignable list `role__in`, `:336` role in payload (+ served
  `assignable`)
- `scholarship/views_admin/verdict.py:520-521` the org_admin assigns only `role == 'reviewer'`
- `scholarship/views_admin/reviewers.py:234` Reviewers tab (`role__in reviewer, qc`)
- `scholarship/staff_lifecycle.py:93-99` `has_open_cases` (reused by the S4 PATCH)
- web `lib/navigation.ts:334` Applications row; `app/admin/scholarship/page.tsx:404`, `:516` picker
  filter; `lib/officerCockpit.ts:1625-1632` assignable filter;
  `app/admin/scholarship/[id]/view/AssignAndWitness.tsx:88` role suffix;
  `app/admin/organisation/reviewers/[id]/page.tsx:106-107` `mayPause`
- **Preset-bound (R2, stay on `role`):** `views_admin/base.py:49` `_require_reviewer` (callers
  `views_admin/graduation.py:56`, `views_admin/reviewers.py:460`, `:467`);
  `views_admin/graduation.py:31`; `reviewer_onboarding.py:37-40`; web `app/admin/profile/page.tsx:48`,
  `lib/adminLanding.ts:40`, `lib/navigation.ts:665`, `app/admin/set-password/page.tsx:68`,
  `app/admin/scholarship/page.tsx:75` (`canFilterByAssignee`)

### B. `see_all` (convert, S3)
- api `views_admin/base.py:76`, `:78` (`_b40_scope` none/all), `:265` (`_can_review_app` none), `:238`
  and `views_admin/applications.py:63` (scope readers, unchanged code)
- `views_admin/verdict.py:476` AI-reliability card (org_admin / admin / qc / reviewer → `see_all` or `review`)

### C. `qc` (convert, S3)
- api `views_admin/base.py:271` org-wide write (org_admin, qc), `:336` `_require_qc` gate; callers
  `views_admin/verdict.py:305`, `:343`
- **Safety rules, unchanged:** `views_admin/base.py:348` (self-QC), `:357` (recorder guard)
- web `app/admin/scholarship/[id]/view.tsx:150` `canQc`, `:158` `canWrite`;
  `app/admin/scholarship/[id]/view/QcPanel.tsx:44`

### D. `spending` (convert, S3)
- api `views_admin/spending.py:29` `_SPENDING_ROLES`, `:68` gate (`:74` super pooled, platform);
  reached through `_SpendingBase` by `views_admin/spending_flags.py:25` and `merchant_flags.py:38`
- web `lib/navigation.ts:362`; `app/admin/spending/page.tsx:82`

### E. `payments_prepare` / `payments_check` / `payments_approve` (convert, S2)
- api `views_admin/payments.py:111` read roles, `:112` write roles, `:126` gate, `:168`, `:239`,
  `:290` (write gates), `:103` served `finance_check_required`
- `payments.py:493-512` `finance_check_required`; `:548-603` `sign` (`:551` maker, `:571-573`
  checker, `:591` approver); `:625` `complete` `actioned_by`; `:666` `cancel`
- `emails/payment_mail.py:45` (ready → org admins), `:93` (check → finance), `:144-151` (Vircle
  email wording + CC)
- `staff_lifecycle.py:56-67` `runs_in_progress`, `:70-74` `_other_active_finance`, `:100-110`
  `run_in_progress` + consequence
- `staff_footprint.py:14`, `:53`, `:60` (signature counts, reader); `models/funding.py:60`, `:288`
  (docstrings)
- **⚠ Shared reader:** `views_admin/sponsors.py:437-438` (wallet credits read
  `payments.finance_check_required`), split in S2
- web `lib/navigation.ts:353`; `app/admin/payments/page.tsx:45` `canCreate`;
  `app/admin/payments/[id]/page.tsx:75`, `:108`, `:226`, `:311`, `:405-445` (step buttons);
  `lib/paymentStatus.ts:62-71` `signOffView`; `lib/admin-api/payments.ts:75`

### F. Wallet credits (preset-bound in #39, question 6)
- api `sponsorship.py:118` (record = admin), `:347-379` `sign_admin_credit` (`:353` maker,
  `:364-366` finance, `:379` org_admin), `:405` void roles; `views_admin/credits.py:32`, `:38`
- web `app/admin/sponsors/[id]/page.tsx:92`, `:386`, `:397`, `:435-440`;
  `lib/sponsorDetail.ts:121-135`, `:152-153`, `:179-180`, `:244`

### G. Team and invitations (`manage_team`, lead tier; S1 message, S4 editor)
- api `courses/views_admin.py:559` `_ORG_ADMIN_MANAGEABLE_ROLES`, `:565` `PROGRAMME_STAFF_ROLES`,
  `:570` `_DELETABLE_ROLES`, `:590`, `:602-608` `_staff_target_manageable`, `:623-626` invite gate,
  `:637-646` invitable roles, **`:652-655` the "already exists" 409 (S1)**, `:728`, `:754`, `:798`
  resend, `:936`, `:951` staff list (admin read-only), `:1025` revoke, `:1041-1046` last org admin,
  `:305` `AdminRoleView` serves role (S1 adds permissions)
- `courses/views_staff.py:55`, `:76`, `:79`; `courses/staff_reinvite.py:53`, `:124`, `:151`
- `scholarship/views_admin/staff.py:42`; `staff_lifecycle.py:33` `ROLE_PAIRS`, `:84`, `:135-142`
  (S4: reset permissions)
- `scholarship/invitations.py:73` `KIND_ROLES`, `:79` `KIND_INVITABLE_ROLES`, `:92`, `:101-102`;
  `views_admin/invitations.py:110`, `:140`, `:233`, `:243`, `:248-252`
- `views_admin/reviewers.py:212` (People read), `:342` (pause), `:386` (set gift)
- `emails/reviewer_mail.py:110-116` role labels, `:139` `_invite_kind_for_role`;
  `management/commands/backfill_invitations.py:48-49`, `:75`
- web `lib/navigation.ts:218`, `:226`, `:239`; `app/admin/organisation/staff/page.tsx:64`, `:354`;
  `app/admin/organisation/reviewers/page.tsx:83`, `:88`, `:290`, `:359`;
  `components/admin/StaffAdmin.tsx:95`, `:169`, `:203`, `:313-314`; `lib/staffRole.ts:10-21`;
  `lib/adminStaff.ts:7-55`

### H. Org-admin lead powers, and preset-bound shared reads (unchanged)
- Lead tier, api: `views_admin/applications.py:120`, `:209`, `:362`, `:418`;
  `views_admin/guardian_contact.py:33`, `:38`; `views_admin/lifecycle.py:161`;
  `views_admin/verdict.py:507` (assign); `views_admin/sponsors.py:257`;
  `views_admin/sponsorships.py:80`; `views_admin/sponsor_terms.py:243`;
  `views_admin/gift_programmes.py:28`, `:34`; `views_admin/org_config.py:47`, `:53`, `:221`, `:227`;
  `views_admin/theme.py:71`, `:77`; `views_admin/overview.py:102`, `:108`; `programme_overview.py:92`;
  `views_admin/contracts.py:128`; `views_admin/billing.py:52`; `views_admin/invoices.py:100`, `:390`;
  `views_admin/requests.py:79`, `:89`, `:311`, `:374`; `management/commands/send_review_nudges.py:75`;
  `courses/models.py:432` (`tenants()`: a tenant is an organisation with an org_admin)
- Preset-bound shared reads, api: `views_admin/sponsors.py:63`, `:117`;
  `views_admin/sponsorships.py:39`, `:174`; `views_admin/sources.py:111`;
  `views_admin/org_emails.py:215`; `views_admin/sponsor_terms.py:95`;
  `programme_overview.py:77`, `:106-107` `SECTIONS_BY_ROLE`
- web: `lib/navigation.ts:244`, `:246`, `:249`, `:252`, `:267`, `:331`, `:337`, `:368`, `:380`,
  `:383`, `:514` (`hasGiftDoor`); `app/admin/scholarship/[id]/view.tsx:143` (`canAssign`), `:146`;
  `view/BlockersPanel.tsx:87`; `lib/officerCockpit.ts:1376-1378` (`canOrgReject`);
  `app/admin/sponsors/page.tsx:64`, `:88`; `app/admin/sponsors/terms/[id]/page.tsx:39`;
  `app/admin/organisation/page.tsx:44`; `app/admin/requests/page.tsx:40`; `lib/requestStatus.ts:119`;
  `content/manual/index.ts:32-56`; `content/manual/faq.tsx:469-480`; `app/admin/guide/page.tsx:21`;
  `components/admin/AppShell.tsx:292`

### I. Platform / super / partner (outside the matrix, unchanged)
- api `courses/views_admin.py:120-127` (`has_role`), `:148`, `:153`, `:920`, `:1033`, `:1132`,
  `:1150`; `courses/models.py:794-796` (`is_super`); `views_admin/base.py:94`, `:116`, `:158`, `:177`,
  `:213`, `:228`, `:267`; `org_requests.py:149-150` and its nine call sites (`:346` … `:742`), `:804`;
  `views_admin/invoices.py` (16 lines); `views_admin/billing.py` (8 more); `views_admin/contracts.py:144`,
  `:152`, `:190`, `:208`, `:386`; `contracts.py:911-916`; `views_admin/graduation.py:107`, `:141`;
  `views_admin/requests.py:67`, `:101`, `:111`, `:138`, `:160`, `:207`, `:453-479`;
  `views_admin/sponsors.py:80`, `:89`, `:202`; `views_admin/sponsorships.py:45`, `:119`;
  `views_admin/sources.py:120`, `:138`; `views_admin/theme.py:89`; `views_admin/org_config.py:61`, `:245`;
  `views_admin/gift_programmes.py:43`; `views_admin/overview.py:69`, `:116`;
  `views_admin/lifecycle.py:229`, `:248`, `:290`; `views_admin/verdict.py:215`, `:448`;
  `views_admin/payments.py:136`, `:161`, `:356`; `bursary.py:649`
- web: `lib/navigation.ts:179-200` (platform rows), `:441-447` (`effectiveRole`); every
  `effectiveRole(role) === 'super'` page (billing, contracts, course-data, requests, students, sources,
  sponsors, login, auth callback, `sessionPolicy.ts:56-85`); `components/admin/InvoicesSection.tsx`;
  `components/contracts/DeployPanel.tsx`; `lib/decisionReopenOffer.ts:24`;
  `view/ReopenHeaderControl.tsx:26`; `view/PostAwardPanels.tsx:111`
