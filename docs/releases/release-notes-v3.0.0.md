# HalaTuju v3.0.0 — Release Notes

**Date:** 2026-10-06 · **Tag:** `v3.0.0` (cut from `main` at `90812950`) · **Previous release:** `v2.0-rc` (2026-03-20)
**Live at:** [halatuju.xyz](https://halatuju.xyz) · **Commits since v2.0-rc:** 2,271

Written for the owner and for whoever works on HalaTuju next. Every change is described in full in
[`CHANGELOG.md`](../../CHANGELOG.md); the reasons behind the choices are in
[`docs/decisions.md`](../decisions.md); the sprint notes in [`docs/sprint-history.md`](../sprint-history.md);
the system map in [`docs/architecture.md`](../architecture.md); the security and access review in
[`docs/security-posture.md`](../security-posture.md) (section "Release review — v3.0.0").

---

## In one paragraph

v2.0-rc was a course guide: tell a school-leaver which courses they qualify for. v3.0.0 keeps that
and adds a **complete bursary platform** that an organisation can run on its own: a student applies
for a named gift, her results and family documents are read by machine and checked for genuineness,
a deterministic engine reaches a verdict an officer can trust, a volunteer reviewer interviews her, a
quality-control step signs it off, a sponsor funds her, and the money reaches her eWallet through
Vircle — with the organisation's own staff, colours, wording, rules, bills and reports. Underneath,
the code was put on a diet and a set of standards now refuses any deploy that breaks them.

## Features Delivered

### Student apply and results
- The B40 programme went from a form to a guided journey: About me, My family, Results, My plans,
  Support, a truthfulness declaration with a typed signature, then the follow-up tabs (Your story,
  Funding, Documents, Consent).
- **The apply link names its gift** (`/scholarship/apply?p=<code>`); a gift code can change without
  breaking old links (code aliases); the form says which gift it is for, and a closed round is
  refused, never re-routed.
- **One application in play** — the server decides (`apply_gate`), the apply page asks it before the
  form opens; a student with a live application is taken to it.
- Results: the student is tagged by the results we hold, not the exam she declared; the SPM exam year
  is asked only when the slip cannot say it; the merit score names its year; STPM students keep their
  SPM prerequisites across logins; electives persist (cap 7).
- An intake year can require minimum grades (A-, B+ and, from request #30, "C or better") and a
  minimum merit score; blank means not applied.
- A silent score at submit, and the decision revealed after an embargo (shortlist or a kind decline).

### Documents and genuineness
- Every upload is read: Cloud Vision OCR, deterministic parsers for the IC, results slip, offer
  letters, STR, EPF, payslips, water and electricity bills, school-leaving and birth certificates,
  with Gemini as a fallback where the parser cannot read.
- **Genuineness models** (a score band plus red chips) for the IC, payslips, bills, certificates and
  offer letters; a document never scored can no longer read "Certain".
- Upload is **stage → judge → promote only if better**, with a circuit-breaker that sends a stuck
  document to an officer instead of looping the student.
- "Cikgu Gopal" coaches the student in three languages on why a document was not accepted.
- The programme decides which documents it asks for (the requirements catalogue), frozen at submit.

### Income and the verdict
- Income has one per-earner answer (`income_shown`): a usable payslip, a readable EPF, or a declared
  amount with a supporting letter. A current, genuine STR of the student's OWN family settles income
  by precedence; a stranger's STR no longer vouches.
- The verdict reads facts with confidence (Identity · Academic · Pathway · Income), is versioned
  (`VERDICT_ENGINE_VERSION`), and can only be raised — never lowered — by the stronger proof.
- Check 2: the AI drafts clarifying questions; officers see them first; the student answers in her
  Action Centre; every ask is tied to the item it chases.
- Singapore payslips are converted from S$ to RM.

### Pathway and offer
- The offer letter is matched to the catalogue: the institution, the level and the course; a
  different university on the letter is flagged; private-arm offers and "Saluran Terbuka" read red;
  an STPM online announcement is recognised as such.
- A student with an offer but nothing declared is asked to confirm or complete the pathway.

### Officer console
- **One console for every role**: scope sidebar, breadcrumb with organisation and gift switchers, a
  command palette, one layout standard, cards on a phone, tables from 25 rows, one save bar.
- **The cockpit**: one page per applicant with the verdict, the blockers that name what is still
  owed, documents with chips, income and household reconciliation, the decision trail; it opens in
  38 database queries instead of 315.
- Reviewer assignment by organisation and gift, interview scheduling with Google Meet, reminders,
  rescheduling, an interview that must be complete before Approve or Decline, a QC gate (accept,
  reopen, decline), closing a stalled application, reopening a decision.
- Programme Overview per gift, arranged by the organisation; Usage and billing; Requests.

### Sponsors, gifts, payments and Vircle
- An anonymised sponsor pool (no name, IC, school or address ever reaches a sponsor), sponsor
  accounts with their own sign-in, terms with a reading quiz, wallet credits signed by two people,
  funding one student in full, a portfolio of the students a sponsor funds.
- **Gifts**: an organisation creates a gift, its intake years (four states, one final), its apply
  copy (with a draft from English), its requirements and its agreement template.
- **Payments**: a payment run per gift, a maker → finance checker → approver chain, the CSV filed to
  Drive and emailed to Vircle; back- and advance-pay window rules; the reporting date as a fact.
- **Vircle**: we tell Vircle who to onboard and Vircle tells us the wallet (webhooks), so the student
  no longer types a wallet id; the install email attaches the live guide from Drive.
- **Spending**: Vircle's spending reports are read from Drive, each payment categorised, summarised
  for the officer and (as a card) for the sponsor; shops can be flagged for review.
- **The bursary agreement** (contract module: clauses, Word import, signing chain with a witness and a
  guarantor PIN) is built and DARK until the lawyer and TD-347 clear it.

### Partners, organisations and requests
- **Organisation configuration**: document limits, interview grid, reviewer and staff clocks,
  agreement clocks, student comms, theme (with a contrast gate, draft, publish and revert), and the
  Overview layout.
- **People and invitations**: invitations in four kinds, one home for everybody who is in, pause,
  restore, cancel; staff invited by the organisation and assigned to a gift.
- **Requests**: an organisation's channel to the engineer — a form, a screenshot paste, an AI triage,
  the engineer's analysis, a discussion thread, owner-gated quotes in hours.
- Tenant invoices and receipts; a usage meter on every billable call.

### Communications: email, WhatsApp
- Branded, tenant-aware emails in English, Malay and Tamil, every one pinned by a golden master.
- Partner and sponsor comms that an organisation admin writes and switches on (two gates each).
- WhatsApp interview reminders through Twilio; reviewer nudges; "you haven't submitted yet" nudges.
- Partner and sponsor mail bills the organisation, not the platform.

### Platform, tenancy and fences
- Tenancy: **organisation → gift → intake year**; every admin endpoint behind the organisation
  fence; the gift narrows inside it and never widens it; a referral organisation is never a tenant.
- Roles: super, org_admin, admin, reviewer, qc, finance, partner — and sponsors as their own identity.
- Light and dark themes, an organisation's own colours, self-hosted fonts (Lexend, IBM Plex).
- A design sandbox an outside team can use without the codebase.

### Security and keyless Google
- The IC claim is a link behind a code, fully audited, and never names the holder (TD-254/259).
- The mock donation route is gated off and the sponsor fund view goes through the fence (TD-258).
- **No Google service-account key exists any more**: Meet, Drive and Sheets are keyless, and an alert
  watches the path (TD-125, TD-329).
- Every new table gets RLS at creation; the advisory tables are read-only to students through the
  public key; Turnstile captcha on every sign-in; a mass-read alert on applicant records; a weekly
  off-platform backup of documents; logs carry a real severity.

### Code health
- Nineteen code-health sprints (H1–H19): the tests run before every deploy; code standards are tests
  inside the gate (file and function size, duplication, skips, suppressions, mirrors, the app
  boundary, the test factory); a first-load JS budget per route and a query budget per page.
- The four largest files became packages (`views_admin`, `models`, `services`, `emails`,
  `income_engine`); a test factory that builds only reachable states; 59 rendered cockpit tests.
- The debt register was read end to end and is kept in working order (see Known Issues).
- Production builds on Node 24; the api image installs an exact lock file.

## Behaviour Changes

What an existing user, officer or operator will notice compared with v2.0-rc:

- A student can hold **one application in play** at a time, in any organisation (stricter than the
  per-organisation ruling until M2 — TD-353).
- A bare `/scholarship/apply` asks which gift; the link carries `?p=<code>`.
- **Decisions are embargoed**: the student sees a decline only when its email goes; cool-offs apply
  to declines and award offers.
- An officer must answer every interview agenda item before Approve or Decline; a closed case takes
  no more review writes; a stalled application can be closed and the student may apply again later.
- The shortlist gate, the sponsor band and the slip parser read the results the student holds.
- An organisation-less super must name a gift on money pages (`400 programme_required`).
- Payments and Spending belong to a gift, not to an organisation.
- A student can no longer write her own advisory rows (profile, saved courses, outcomes, reports)
  through the public key; the app always went through Django, so nothing visible changes.
- The browser downloads one language, not three; the first paint is roughly half the weight.
- The onboarding flag for staff lives on the server, and a password reset link expires in 15 minutes.
- Student phone verification is paused (it gated nothing and cost the most on the Twilio bill).
- A new unauthenticated `GET /api/v1/health/` answers whether the course data loaded (nothing probes it yet).

## Breaking Changes

For an integrator or an operator. **Nothing was removed from the public API relative to v2.0-rc** —
44 routes then, 259 now, none of the old ones gone. What you must know:

### Schema — migrations are applied BY HAND, before the code
The deploy never runs `migrate`. 199 migration files were added since v2.0-rc: **courses 0047–0076**
(30) and **the whole scholarship app, 0001–0169** (169). Every file, with one line each, is in
[`v3.0.0-migrations.md`](v3.0.0-migrations.md); diff it against production's `django_migrations`
before relying on the ledger. The last 35, the ones applied since late July:

| Migration | What it does | Kind |
|---|---|---|
| 0135_application_catalogue | The requirements catalogue: what a programme asks for | new tables |
| 0136_heal_missing_sponsor_memberships | Gives every existing sponsor a gift membership | data |
| 0137_pre_decline_award_amount | Keeps the award amount a cancelled decline restores | column |
| 0138_org_request_comments | Requests become a discussion thread | new table |
| 0139_clarifications_to_comments | Moves old clarifications into the thread | data |
| 0140_org_request_analysis | The engineer's analysis becomes a record | new table |
| 0141_org_request_analysis_proposed_triage | The engineer's proposed triage (kind, lane) | columns |
| 0142_partner_email_student_assigned_kind | A "student assigned" partner email | choices only |
| 0143_reviewer_email_kinds | Reviewer email kinds | choices only |
| 0144_invitation | Invitations become records | new table |
| 0145_invite_email_kinds | Invitation email kinds | choices only |
| 0146_invitation_email_kinds_per_group | One invitation email per group | choices + data |
| 0147_requirements_snapshot | What the programme asked for, frozen at submit | column |
| 0148_sabah_s2a_optional_requirements | Intake-year thresholds become optional; a minimum merit score | columns |
| 0149_s_assign_programme_scope | An invitation names its gift | column |
| 0150_gift_setup_flow_intake_window | An intake year opens and closes on dates | columns |
| 0151_round_finished_for_good | An intake year can be finished for good | columns |
| 0152_alter_orgrequest_component | The Requests component list stops naming one programme | choices only |
| 0153_programme_code_alias | Old gift codes keep working | new table |
| 0154_programme_apply_copy | The apply page's copy belongs to the gift | column |
| 0155_spending_txns | Spending transactions and merchant categories | new tables |
| 0156_verdict_engine_version | Each AI verdict records the engine version | column |
| 0157_billing_adjustment_and_workspace_source | Billing adjustments; a Workspace cost source | new table + choices |
| 0158_extracted_provenance | Where a cost figure came from | choices only |
| 0159_more_cost_sources | More cost sources | choices only |
| 0160_tenant_invoices | Tenant invoices and receipts | new tables |
| 0161_overview_layout | An organisation's Overview layout | new table |
| 0162_applicantdocument_order_tie_break_on_id | Document order breaks ties on id | state only |
| 0163_contracttemplate_programme | The agreement template belongs to a gift (nullable, back-filled) | column + indexes |
| 0164_contracttemplate_programme_not_null | That column becomes NOT NULL | constraint |
| 0165_guardian_contact_changes | The trail of parent-phone changes and parent calls | new table |
| 0166_spend_category_micro_stall | A person-only spending category, `micro_stall` | choices only |
| 0167_merchant_flags | A shop flagged for review, and its notes | new tables |
| 0168_closure_reason_stalled | Closure reason `stalled` | choices only |
| 0169_cohort_min_spm_credit_count | Minimum SPM grades at C or better per intake year | column |

The next migration numbers are **scholarship 0170** and **courses 0077**.

### Environment variables
- **105 api environment variables were added** since v2.0-rc (19 then, 124 now). The full list, with
  what each means, is in `halatuju_api/CLAUDE.md` → "Environment variables". Every new feature flag
  defaults to OFF.
- **Added and then removed in this period — must NOT be set:** `GOOGLE_MEET_SA_JSON` (the Google key,
  deleted 2026-10-04; setting it now does nothing), `VIRCLE_ACTIVATION_ENABLED` / `_EMAIL` / `_BCC` /
  `_FOLDER` (the 48-hour Vircle chaser, retired 2026-09-11), `FOUNDATION_SIGNATORY_NAME` / `_TITLE` /
  `_NRIC` (the signatory now lives on the agreement template).
- **Never in production:** `SPONSOR_MOCK_DONATIONS_ENABLED` (it refuses to arm against a real
  database anyway). **Never set before TD-347 ships:** `BURSARY_AGREEMENT_ENABLED`.
- New Google requirement: the runtime service account needs `roles/iam.serviceAccountTokenCreator` on
  `halatuju-meet@…` and `iamcredentials.googleapis.com` enabled.
- Web: `NEXT_PUBLIC_APP_VERSION` is now stamped from the commit at build time.

### i18n keys
32 English keys from v2.0-rc are gone (4,695 added; 746 → 5,409 per locale): 26 `dashboard.*` keys of
the old dashboard (`allInstitutions`, `allLevels`, `allTypes`, `courses`, `eligibleCourses`,
`insightsLevels`, `insightsMerit`, `insightsTopFields`, `kolej`, `levelAsasi`, `levelDiploma`,
`levelIjazah`, `levelSijil`, `levelSijilLanjutan`, `otherEligible`, `polytechnic`, `rankedCourses`,
`rankedSubtitle`, `regenerateReport`, `teacherTraining`, `topMatches`, `totalEligible`, `tvet`,
`university`), `common.getStarted`, `courseDetail.languageReq`, `courseDetail.viewOnEpanduan`,
`errors.claimFailed`, `errors.notSignedIn`, `quiz.next`, `quiz.notSureYet`, `verifyEmail.pageLoading`.

### Endpoints
No v2.0-rc route was removed. Added **and removed again** within this period, so a client written
against an interim build must not call them: the sponsor register-interest routes (removed v2.26.1,
2026-06-01), the interview-slot `DELETE` (removed 2026-10-01, TD-257), and the IC claim's
`confirm: true` second call (now refused, TD-254). `POST /api/v1/sponsor/wallet/donate/` answers 404
unless the mock flag is armed, which production never does.

### Operations
- **The deploy is gated**: a red test suite, a broken code standard or a heavier route stops the
  push. The hotfix bypass is in each `cloudbuild.yaml` header.
- Production web builds on **Node 24**; rolling back means shifting traffic to the previous revision,
  not editing the version back (a guard refuses Node below 22).

## Known Issues

The open debt register on 2026-10-06: **116 open items**, every one with an entry in
[`docs/technical-debt.md`](../technical-debt.md) (Open Items Index, in the order to work them). Below
they are grouped by **importance** — A money or identity · B eligibility or security · C a student or
an officer sees it · D tooling and hygiene — and **size** — S half a day · M one to three days · L
longer, a migration or an outside party. "What it needs" says what unblocks each one:
**ruling** (the owner decides), **sitting** (the owner reads first-draft copy or walks a screen),
**owner action** (a setting outside the code), **paid** (a billable re-read), **lawyer**,
**mock-up** (a Stitch design first), or **code** (an engineer can just do it).

⚠ Read these four first: **TD-347** must ship before anyone sets `BURSARY_AGREEMENT_ENABLED`;
**TD-367** — a payment run can pay a closed student; **TD-366** and **TD-353** are on hold by the
owner's ruling (until signing is finalised, and until a second organisation joins).

| | S | M | L | total |
|---|---|---|---|---|
| A — money or identity | 3 | 4 | 5 | 12 |
| B — eligibility or security | 2 | 4 | 2 | 8 |
| C — a student or officer sees it | 28 | 19 | 4 | 51 |
| D — tooling and hygiene | 25 | 13 | 7 | 45 |
| total | 58 | 40 | 18 | 116 |


#### A · S — 3

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-252](../technical-debt.md) | An award nobody answers holds the sponsor's money for ever. | code | Now |
| [TD-328](../technical-debt.md) | A gift with no agreement template pays the flat RM200 until the first template goes live; then the default is removed and such a gift is not paid (owner ruling 2026-10-04; trigger = the first live template). | code | Later |
| [TD-367](../technical-debt.md) | A payment run can pay a CLOSED student: `payments.complete` writes a `released` Disbursement for every included item and never re-checks the application's status. | code | Now |

#### A · M — 4

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-198](../technical-debt.md) | No officer can withdraw an award once the email has gone. | ruling | Owner-decision |
| [TD-260](../technical-debt.md) | About 600 students could not reclaim a lost account. | ruling | Owner-decision |
| [TD-347](../technical-debt.md) | A sign-invitation's accept deadline can lapse while the offer waits for a parent call. | code | Now |
| [TD-366](../technical-debt.md) | An AWARDED student who stops answering after the offer email cannot be released by anyone: who may lapse a held offer (an admin door), and does the money return to the sponsor's balance? | ruling (on hold) | Owner-decision |

#### A · L — 5

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-075](../technical-debt.md) | Sponsor money is still mock. | lawyer + ruling | Owner-decision |
| [TD-140](../technical-debt.md) | The bursary agreement cannot go live until a lawyer approves the wording and the signing entity is settled. | lawyer | Owner-decision |
| [TD-142](../technical-debt.md) | Payments are real but not tied to the signed agreement. | lawyer | Owner-decision |
| [TD-152](../technical-debt.md) | The agreement's donor is a named person until the Foundation is registered. | ruling (outside party: the Foundation's registration) | Owner-decision |
| [TD-192](../technical-debt.md) | Sponsor vetting is one button. | ruling | Owner-decision |

#### B · S — 2

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-143](../technical-debt.md) | A birth certificate cropped above its header: treat as suspect, or as not a birth certificate? | ruling | Owner-decision |
| [TD-179](../technical-debt.md) | Two rules decide this partner's students. | ruling | Owner-decision |

#### B · M — 4

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-114](../technical-debt.md) | Old uploads never scored for genuineness can no longer read Certain; re-scoring them costs a paid read per document (the IC scorer is Gemini). | ruling + paid | Owner-decision |
| [TD-128](../technical-debt.md) | Special-needs teaching courses match only a physical disability. | ruling | Owner-decision |
| [TD-348](../technical-debt.md) | Two submits at the same moment to two different rounds can both pass the one-application-in-play check (a script could; a person realistically cannot); nothing in the database holds that rule. | code | Now |
| [TD-356](../technical-debt.md) | `cancel_reopen` turns ANY reopened case at `interviewing` into `interviewed` (AWAITING QC), though only a QC reopen moved it there; a reopen of a decided `interviewing` case then lands in the QC queue it never reached. | code | Now |

#### B · L — 2

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-326](../technical-debt.md) | The first results page offers only SPM and STPM; Matric, Asasi and Poly diplomas are STPM-equivalent held results with no form, catalogue requirements or bursary grade bar, and `results_held` should read the HIGHEST completed qualification. | code (owner deferred it to the Matric/Asasi/Poly sprint) | Later |
| [TD-353](../technical-debt.md) | Applications to two organisations at once stay blocked until M2–M4 (stricter than the per-organisation ruling, on purpose). | ruling (on hold) | Owner-decision |

#### C · S — 28

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-066](../technical-debt.md) | The testing-only help box is still live with a personal mobile number. | ruling | Owner-decision |
| [TD-070](../technical-debt.md) | Sponsor sign-in, sign-up and the admin vetting buttons were never click-tested in a browser. | sitting (a browser walk) | Next |
| [TD-091](../technical-debt.md) | Sponsor landing Tamil is a first draft, and the page is public. | sitting | Next |
| [TD-092](../technical-debt.md) | The public sponsor landing page was never walked in three languages. | sitting (a browser walk) | Next |
| [TD-094](../technical-debt.md) | Award and onboarding Tamil is a first draft. | sitting | Next |
| [TD-101](../technical-debt.md) | The sponsor portal has no Donate-more and no Withdraw-offer button. | code | Next |
| [TD-105](../technical-debt.md) | In-programme and graduation-message Tamil is a first draft. | sitting | Next |
| [TD-108](../technical-debt.md) | Invite-a-friend Tamil, screen and email, is a first draft. | sitting | Next |
| [TD-112](../technical-debt.md) | The income route switch was never click-tested in a browser. | sitting (a browser walk) | Next |
| [TD-127](../technical-debt.md) | Some newer PISMP courses show a copied generic description. | code + a production look | Next |
| [TD-130](../technical-debt.md) | A mistaken Gmail Unsubscribe could silence decision and query emails. | owner action (Brevo setting) | Next |
| [TD-156](../technical-debt.md) | Interview video calls can wait for a host who is never there. | code | Next |
| [TD-166](../technical-debt.md) | The What-you-agreed-to panel shows today's wording. | nothing (accepted) | Accepted by the owner |
| [TD-183](../technical-debt.md) | Sponsor-screen Malay and Tamil, about 200 strings, are machine drafts. | sitting | Next |
| [TD-208](../technical-debt.md) | Sign-up, invite and reset emails land in Gmail's spam folder. | owner action (DMARC, Workspace DKIM) | Next |
| [TD-211](../technical-debt.md) | The Reporting Date tick is green on any date read. | ruling | Owner-decision |
| [TD-227](../technical-debt.md) | Should a rejection need a written reason, and show when the rejecter was not the assigned reviewer? | ruling | Owner-decision |
| [TD-265](../technical-debt.md) | Show the funding gift on each payment row, or once in the header, or not at all? | ruling | Owner-decision |
| [TD-311](../technical-debt.md) | The Tamil Home heading spills on phones. | ruling | Owner-decision |
| [TD-321](../technical-debt.md) | Production serves every page image at full size: there is no sharp package, so Next never resizes. | code | Later |
| [TD-336](../technical-debt.md) | The Programme Overview pools platform-wide money totals for a super with no organisation who names no gift (TD-334's shape, no gift gate). | code | Later |
| [TD-339](../technical-debt.md) | `_open_round_choices` drops rounds of an inactive programme but the bare resolver counts them, so ambiguity can offer ONE choice: no chooser, then a 409 at submit. | code | Next |
| [TD-341](../technical-debt.md) | `ScholarshipBanner.tsx` still reads `applications[0]`. | code | Next |
| [TD-346](../technical-debt.md) | The "more than one application" message says "open" though it now also counts submitted ones. | code | Next |
| [TD-350](../technical-debt.md) | During the embargo of a decline from `shortlisted` she is shown `profile_complete`, but every upload 403s (`_current_application` reads the raw status). | code | Next |
| [TD-351](../technical-debt.md) | Two simultaneous submits to the SAME round: the second answers 500 (`IntegrityError`) instead of 409. | code | Next |
| [TD-354](../technical-debt.md) | The closed application card offers "See programmes that are open" even when none is (a detour to the landing); gating it costs 28 gz bytes `/scholarship/application` lacked. | code | Next |
| [TD-358](../technical-debt.md) | A due decline with no email address is released (unmasked) without an email, and the only trace is a WARNING log line; no officer surface says "tell this student another way". | code | Next |

#### C · M — 19

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-068](../technical-debt.md) | A contractual decline sends the generic email. | ruling (with TD-227) | Later |
| [TD-076](../technical-debt.md) | The Settings page is thin. | mock-up | Later |
| [TD-077](../technical-debt.md) | Course names show a bare # where an Interview label is meant. | mock-up + copy | Later |
| [TD-096](../technical-debt.md) | Sponsor emails go out in one language. | ruling | Owner-decision |
| [TD-111](../technical-debt.md) | Some detected anomalies are never put to the student as questions. | code | Later |
| [TD-119](../technical-debt.md) | Eight genuine family documents are still wrongly flagged in the test set. | code | Later |
| [TD-132](../technical-debt.md) | Sponsor portal wording, English and Tamil, was never reviewed by the owner. | sitting | Later |
| [TD-155](../technical-debt.md) | Partners have no Scholarship view of the students they referred. | code | Later |
| [TD-215](../technical-debt.md) | The donor-pitch email exists only in English. | sitting | Later |
| [TD-216](../technical-debt.md) | A conclusion-only rewrite still takes the interview credit. | mock-up + migration | Later |
| [TD-225](../technical-debt.md) | The logo half-disappears in dark mode. | ruling + design | Owner-decision |
| [TD-228](../technical-debt.md) | Picking an organisation in the crumb filters nothing on Sponsors and Sources (Requests narrows since 2026-10-05; Payments and Spending narrow through the gift — TD-246, closed). | code | Later |
| [TD-230](../technical-debt.md) | Should the apply form's referring-organisation list come from the Sources screen? | ruling | Owner-decision |
| [TD-245](../technical-debt.md) | We cannot tell spent-nothing from wallet-missing-in-the-export. | code + migration | Later |
| [TD-247](../technical-debt.md) | Supplier bills reach the cost ledger only when someone imports them by hand. | code | Later |
| [TD-338](../technical-debt.md) | One programme with two cohorts open: the intake is ambiguous even with its code, the chooser lists the same code twice, and submit 409s for ever. | code | Later |
| [TD-355](../technical-debt.md) | Three decision emails are sent AFTER the status they announce is visible, with no retry: the org-admin drop, a decline with the cool-off at 0, and the engine's pre-shortlist reveal (pass or decline). | code | Later |
| [TD-359](../technical-debt.md) | If the database fails after Brevo accepted a decline email but before the claim's transaction commits, the stamp is lost: the next run sends it again, and a cancel in that window reverses a decline the student has already been emailed. | code | Later |
| [TD-365](../technical-debt.md) | A close and a sponsor's fund can race: `fund_student` does not lock the application, so a fund landing in the same instant as a close can write `awarded` over `closed`. | code | Later |

#### C · L — 4

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-043](../technical-debt.md) | Phone sign-in says coming soon. | ruling + paid | Owner-decision |
| [TD-103](../technical-debt.md) | The student types their own CGPA; nothing reads it off the slip. | code | Later |
| [TD-133](../technical-debt.md) | The Trust hub shows placeholders and example figures until the organisation is formal. | ruling (the organisation becomes formal) | Owner-decision |
| [TD-141](../technical-debt.md) | A parent surety can sign only on the student's device. | lawyer | Later |

#### D · S — 25

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-041](../technical-debt.md) | The Settings page has no account options. | mock-up | Someday |
| [TD-097](../technical-debt.md) | Reviewer-profile Tamil is a first draft. | sitting | Later |
| [TD-104](../technical-debt.md) | The in-programme results form has no slip upload. | code | Later |
| [TD-116](../technical-debt.md) | Older EPF statements use a rougher estimate until re-read. | paid (one re-read, with TD-117) | Later |
| [TD-117](../technical-debt.md) | Older EPF uploads never got the wrong-type check. | paid (one re-read, with TD-116) | Later |
| [TD-126](../technical-debt.md) | The Guide's scheduling step lost its screenshots in the July rewrite. | code + screenshots | Later |
| [TD-129](../technical-debt.md) | Some Tamil-school PISMP courses list an extra language credit; no result changes. | code + a production look | Later |
| [TD-170](../technical-debt.md) | Two Malay and Tamil lines use a different name token; the wording needs the owner's sign-off. | sitting | Later |
| [TD-173](../technical-debt.md) | iPhone photos attached to a request are not converted. | code | Later |
| [TD-174](../technical-debt.md) | A new email type could still bill the platform instead of the organisation. | ruling (billing policy) | Later |
| [TD-180](../technical-debt.md) | Partner-emails screen Malay and Tamil are a first draft. | sitting | Later |
| [TD-184](../technical-debt.md) | No person has walked a real sponsor credit through both signatures. | sitting (a browser walk) | Later |
| [TD-185](../technical-debt.md) | The credit chain reads timestamps, not the credit's status. | code | Later |
| [TD-187](../technical-debt.md) | The admin menu cannot scroll; it is 19 rows today. | code | Later |
| [TD-196](../technical-debt.md) | No person has walked the sponsor-terms wizard. | sitting (a browser walk) | Later |
| [TD-238](../technical-debt.md) | Nothing shows the AI's cost in ringgit, or on a screen. | ruling (a price) | Later |
| [TD-262](../technical-debt.md) | The income rule is almost one rule now. | ruling | Owner-decision |
| [TD-318](../technical-debt.md) | WhatsApp STOP is built but does nothing until the inbound webhook is set in the Twilio console (an owner action). | owner action (Twilio console) | Owner-decision |
| [TD-335](../technical-debt.md) | A cancelled staff invitation's address cannot be invited again (409) until People → Restore. | code | Later |
| [TD-342](../technical-debt.md) | An abandoned Google sign-in leaves a pending `apply` action that can later return the student to `?p=<old gift>` (named on the form, so not silent). | code | Later |
| [TD-343](../technical-debt.md) | If the intake request fails, the apply form names no gift and submits no code (the server then resolves or refuses). | code | Later |
| [TD-344](../technical-debt.md) | The thin first-load lines are now `/scholarship/apply` (0.189 kB of room locally) and `/scholarship/application` (0.179); `/profile` has 0.988 since request #26. | code | Later |
| [TD-357](../technical-debt.md) | A decline whose send fails for good (a refused address, a template error) is retried on every cron run for ever, logs ERROR each time, and `_meter_email()` meters each failed attempt (pre-existing metering). | code | Later |
| [TD-363](../technical-debt.md) | The status a case was closed FROM is only in the AUDIT log line (no field), so the closed summary cannot name it; the Close card cannot pre-check a live sponsorship (hidden at `awarded`, where it is certain; elsewhere the server answers). | code | Someday |
| [TD-368](../technical-debt.md) | Interview times can still be proposed and booked on a FINISHED case (closed, rejected, expired): the officer's propose-times and the student's booking endpoints check no status. | code | Later |

#### D · M — 13

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-064](../technical-debt.md) | The old super-admin switch is kept beside the role field. | code | Someday |
| [TD-065](../technical-debt.md) | Some sponsor screens have no component tests. | code | Someday |
| [TD-074](../technical-debt.md) | Two small sponsor-pool follow-ups remain. | code | Someday |
| [TD-121](../technical-debt.md) | The document test scorecard ignores the genuineness check. | code | Someday |
| [TD-124](../technical-debt.md) | Contact-form messages reach staff by email only. | code | Someday |
| [TD-190](../technical-debt.md) | Sponsor tables sort and page in the browser. | code | Someday |
| [TD-212](../technical-debt.md) | The email-template table is still named partner. | code | Someday |
| [TD-234](../technical-debt.md) | Thirteen repair commands have no approved route to live data. | code | Someday |
| [TD-243](../technical-debt.md) | The AI reliability rate blends engine versions. | code | Someday |
| [TD-283](../technical-debt.md) | Two central files are exactly at their size limit. | code | Someday |
| [TD-345](../technical-debt.md) | No local signed-in smoke path for the student apply flow: the live API's CORS refuses a localhost build and no local api + auth recipe exists. | code | Someday |
| [TD-360](../technical-debt.md) | One English message file (~97 kB gz) rides on almost every route, so any new string moves every budgeted first-load line; split it by audience. | code | Someday |
| [TD-362](../technical-debt.md) | The web mirror guard reads only `src/lib/`, and only a comment that says "mirror": request #28's new category would have been dropped from the Overview chart's money by an unlabelled list in `components/`. | code | Someday |

#### D · L — 7

| TD | What is wrong | What it needs | Tier |
|---|---|---|---|
| [TD-024](../technical-debt.md) | The course-name field is called course. | code | Someday |
| [TD-058](../technical-debt.md) | Production lacks Django's bookkeeping tables; managed by hand. | code | Someday |
| [TD-084](../technical-debt.md) | Two orphaned income fields and their dead copy remain. | code | Someday |
| [TD-115](../technical-debt.md) | The document slot has no database-level guard. | code | Someday |
| [TD-226](../technical-debt.md) | Two intake-year settings are stored and read by nothing. | code | Someday |
| [TD-278](../technical-debt.md) | An unreachable import-count target is still on the roadmap. | code | Someday |
| [TD-361](../technical-debt.md) | `big` (17 files over 1,000 lines) was accepted three readings running; split the two that are also the top hotspots, `scholarship/views.py` and `officerCockpit.ts`. | code | Someday |

**What unblocks them, in total:** code 63 · ruling 24 (incl. 2 on hold) · sitting 15 (10 copy, 5 browser walks) · lawyer 4 · mock-up 4 · owner action 3 · paid 2 · accepted, no work 1. The register adds the order to work them, the clusters worth doing as one job, and the evidence behind each entry.

## Numbers at the cut

Measured on the release branch on 2026-10-06 with the deploy gates' own command lines:

| Gate | Result |
|---|---|
| api `pytest -n auto` | **8,084 passed**, 3 skipped, 0 failed (3,148 subtests) |
| api `manage.py check` / `makemigrations --check` | no issues / no changes detected |
| web `npm run gates` (tsc, lint, i18n, jest) | green; **4,146 jest tests in 252 suites**; 5,409 keys per locale |
| web `npm run bundle-budget` | ok — median first-load JS 228.1 kB (budget 229), worst 273.1 kB, 89 routes |
| `code_health.py` | 0 FAIL, 5 WARN (fix% 45, big 17, long 15, dup 4, mirror 3); td_open 116 |
| Golden masters | SPM 5,319 · STPM 2,026 (inside the pytest run) |

## Upgrade checklist (operator)

1. Production `django_migrations` matches [`v3.0.0-migrations.md`](v3.0.0-migrations.md) — no gap, no row without its schema.
2. `GOOGLE_MEET_SA_JSON`, `VIRCLE_ACTIVATION_*` and `FOUNDATION_SIGNATORY_*` are not set; `SPONSOR_MOCK_DONATIONS_ENABLED` is not set; `BURSARY_AGREEMENT_ENABLED` is not set.
3. The keyless Google path's IAM grant is in place and the alert policy exists (see the security review).
4. The tag: `git tag -a v3.0.0 -m "Release v3.0.0 — the bursary platform"` and `git push origin v3.0.0` (the owner's yes; a tag on its own deploys nothing).
