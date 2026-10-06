# Retrospective — Sprint 14: the Finance role (dormant checker) — 2026-07-23

Brief: `docs/plans/2026-07-22-sprint14-finance-role-brief.md` (v2, owner-approved).
Roadmap Phase 5, trigger fired 2026-07-22.

## What Was Built

A third organisation role, `finance`, that **checks a payment run between the maker and the
approver** — plus a funding summary inside the Payments module. It ships **dark**: with no active
finance admin the chain is the original two steps, byte-identical.

- **`payments.finance_check_required(organisation)`** — the activation predicate. An EXISTS on
  active `finance` staff, evaluated live at every sign attempt, never persisted.
- **`payments.sign()` rewritten** to `draft → admin_signed → [finance_checked] → completed`, with
  `same_signer` generalised to pairwise distinctness across every collected signature.
- **`AdminPaymentFundingSummaryView`** + `FundingSummaryRowSerializer` — an explicit allowlist,
  the only student data the role can reach.
- **Three signature cards** on the run detail, and a `paymentStatus.signOffView()` that decides
  the whole conditional layout in one pure function.
- Finance chapter in the Manual + FAQ; the Payments module's first Manual coverage.
- **4346 pytest (+57) / 662 jest (+14).** Migrations `scholarship/0109` + `courses/0066`, applied
  migrate-first. One push, both builds SUCCESS, verified live.

## Design Decisions

**The activation flag is computed, never stored.** This is the sprint's load-bearing choice. A
`PaymentRun.requires_finance_check` column would have been the obvious modelling, and it is wrong:
the owner's rule is that appointing a finance admin arms the check **for a run already sitting at
`admin_signed`**. A flag written at creation cannot express that. The cost is one indexed EXISTS
per sign attempt — a rare operation — and the benefit is that both directions (activation arms,
revocation degrades) fall out of the same expression with no reconciliation job.

**The completed layout keys on the SIGNATURE, not on the org's current setting.** A run completed
before the role existed, in an org that has since appointed a finance admin, must render two cards
and imply nothing was skipped. Reading `finance_check_required` there would have retroactively
accused every historical run of a missing step.

**`same_signer` generalised rather than special-cased.** The brief asked for "super may fill one
slot, never two". Implementing that as a super-specific rule would have been a second concept;
pairwise distinctness across collected signatures produces it for free and also covers the
maker-is-also-finance case nobody had named.

## What Went Well

- **The repo's own guards caught two real gaps before I did.** The `test_org_fence.py` static
  guard failed my new raw `ScholarshipApplication.objects` query for a missing `# org-fence:`
  pragma — and then failed it a *second* time because the pragma sat outside its 200-character
  window. And `Record<ManualRole, string>` on the guide page's `roleLabel` failed the type-check
  until the finance badge existed, rather than rendering an undefined badge. Both are exactly the
  "make the gap a build failure, not a discovery" pattern this codebase keeps investing in, and
  both paid out this sprint.
- **All 82 pre-existing payments tests passed unmodified**, which is what makes "ships dark" a
  verified claim rather than an assertion.
- **Denials are tested as refusals.** Every "finance cannot do X" is an actual 403/False from the
  real gate, not the absence of a nav link — the 2026-07-16 lesson that a capability is the
  intersection of the endpoint gate and the UI affordance.

## What Went Wrong

**I extended a test's role list only because I checked it.** `manual.test.ts` has a
`ROLE_CHAPTERS` array; adding `role-finance` to the registry left every assertion passing while
covering nothing about the new chapter. *Root cause:* a hand-maintained enumeration inside a test
is the same shape as the `_SUBJECT_BM` drift trap already in `lessons.md` — the test looks like it
covers the registry but actually covers a copy of it. *System change:* recorded in `lessons.md` as
a general rule — when a test enumerates the thing it guards, the enumeration must be derived from
the source or asserted complete against it, or the test silently narrows every time the source
grows. (Not fixed structurally this sprint: `visibleChapters` is deliberately role-filtered, so a
derived list would need care. Flagged rather than half-done.)

**Two heredoc failures cost a cycle each.** Writing multi-line TSX patches through
`bash <<'PY'` aborted with shell quoting errors twice, on content that a quoted heredoc should
have passed through literally. *Root cause:* I reached for the shell out of habit despite
`lessons.md` already recording that scripted multi-line source edits belong in a scratch file.
*System change:* none needed — the lesson exists and is correct; I applied it on the third attempt
and every subsequent patch went through a Write-then-run script cleanly. Worth noting that the
existing lesson was *right* and the failure was in following it.

**The brief's endpoint path did not match the codebase.** It specified
`/api/v1/admin/payments/funding-summary/`; every payments route lives under
`admin/scholarship/`. *Root cause:* a brief written at design time, not verified against the URL
conf — the exact shape `lessons.md` already describes ("a plan's verified facts are authoritative
for INTENT, not field-level ground truth"). *Resolution:* followed the codebase, documented the
deviation in `urls.py`, the commit and the CHANGELOG, since no external contract depended on the
spelling. Reinforces the existing lesson rather than adding one.

## Numbers

- **4346 pytest** (+57) + **662 jest** (+14). Type-check clean; migrations `--check` clean.
- Migrations `scholarship/0109` (3 columns + status choices) + `courses/0066` (choices-only),
  applied migrate-first via Supabase MCP, both `django_migrations` rows recorded, columns verified
  in `information_schema`.
- **Prod state at deploy: 0 finance admins** (21 staff: 13 reviewer, 3 admin, 2 org_admin,
  2 partner, 1 super) — the chain is provably unchanged for every existing run.
- One push → both Cloud Build triggers SUCCESS (`d52b3e0`), 100% traffic on
  `halatuju-api-00850-5zd` / `halatuju-web-00706-x2m`. Live: `funding-summary` → 401 (exists),
  nonexistent sibling → 404 (the control), `/admin/payments` → 200.
- **▶ CARRY:** ms/ta first drafts for all new finance strings await the owner's Tamil review.
  Four screenshot placeholders added to the manifest — `finance-signature.png` must be captured
  with an ACTIVE finance admin or it shows the dormant two-column layout.
- **▶ ROLLOUT (owner, not performed):** invite the finance admin via Administration → Invite
  staff → Finance. The moment that account is active the check arms for BrightPath — **including
  the draft run `PR-2026-08-01` if it has reached `admin_signed` by then**.
