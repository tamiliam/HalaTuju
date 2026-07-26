# Partner-organisation comms — Roadmap (weekly + milestone emails to referral partners)

**Status:** owner-approved, 2026-07-26, **revised the same day** after two owner corrections (below).
Sprint briefs are ready for `sprint-start.md`.
**Design of record:** <https://claude.ai/code/artifact/40bb4e5f-7335-4d88-97c4-d7a9f0399a04> (revision 2).
Stitch was skipped deliberately; see "Why no Stitch screen".

---

## Why now

Ten referral organisations send us students. Today a partner hears from us **exactly once**:
`send_witness_pending_email` (`halatuju_api/apps/scholarship/emails.py:1197`), when a student they
referred needs their witness signature. Everything before that — applying, completing, being
reviewed, being awarded — is invisible to them. We ask a partner to countersign a journey they never
saw. Owner's framing: *"I don't want them to hear about it only when they are required to witness a
contract."*

## Owner corrections (2026-07-26) — these supersede the first draft

1. **No per-organisation selection.** *"If the email template is active, it goes out to all
   qualifying partners. It is either, or."* The matrix of orgs × email types is **dropped**: there
   are **five switches**, one per email type, programme-wide. Consequence for the schema — enablement
   is a property of the **template**, not of an (org, kind) pair, which removes a whole table.
2. **There is no partner console, and HalaTuju partners are not BrightPath partners.** Verified:
   the only two `partner`-role logins are both *Sivamani Rajagopal* at CUMIG, created **2026-03-17**,
   with `owning_organisation_id = NULL` — i.e. **no B40 access at all** (`_b40_scope` → `'none'` for
   role `partner`). They belong to the **HalaTuju course-selector** relationship and see
   `StudentProfile` rows, not bursary applications. Two consequences:
   - **Partner logins are never used as recipients.** Emailing them bursary progress would put
     applicant data in front of an audience attached for a different product. Recipients are an
     organisation's own `contact_email` and nothing else. *(This reverses the earlier
     "contact_email + partner logins" decision, which I had put to the owner on a wrong premise.)*
   - **No email may link to a partner console.** Every email stands alone — which is why the chase
     list carries the **whole** list of names rather than a few plus a link.

## The voice of these emails (owner, 2026-07-26) — a build constraint, not a style note

*"We want the partner organisations to see BrightPath as their bursary programme as well. They may
market it as if it is theirs. So the students are their students, and they are not merely conduits or
middlemen. Also, the individuals receiving the emails are representatives of the organisation; so it
is not their personal students but the organisation's."*

Two rules follow, and every template must obey both:

1. **Co-owned, never a referral pipeline.** Banned phrasing: "the students you send us", "your
   referrals", "referred by you", "thank you for referring". Required register: "{org_name} runs this
   bursary alongside us", "{org_name}'s bursary students", and on an award — *"this is {org_name}'s
   achievement as much as ours — please do share the news as your own"*, which is the licence to
   market it as theirs, stated in the email itself. The assignment email says a student **joins
   {org_name}'s bursary students**, not that one has been handed to a middleman.
2. **The organisation owns the students, not the reader.** Every possessive names the organisation —
   "Sri Murugan Centre's students", never "your students". The only second person left is where the
   reader's own team is asked to act ("your team knows them far better than we do"). Greetings stay
   personal (`Dear {contact_person}`), because you greet a person, not an institution.

Pinned by a test: `test_partner_comms.py` asserts no seeded template contains a banned conduit
phrase, and that no body outside the greeting uses "your student". Copy rules that live only in a
reviewer's head get edited away six months later.

**HTML by default** (owner, 2026-07-26). Every partner email is HTML-primary through the existing
`_html_email_shell`, with a plain-text alternative carrying the same information — including the
chase table, rendered as aligned text so a text-only client still sees the dates.

## The remaining findings

- **No referral partner has an email address.** Verified against prod: of ten rows, only BrightPath
  has `contact_email`, and that address is *our own staff member* (Poongulali Veeran, role `admin`).
  **BrightPath is us** — the house org is the residual bucket in `_source_application_counts` and is
  excluded from partner emails outright, not sent a summary of its own students. So the honest count
  of reachable partners today is **zero of nine**. The screen says so.
- **"Org admin" = the *programme's* admin.** `PartnerAdmin.role` has `org_admin` (BrightPath's
  programme lead); a referral rep is role `partner`. Sources is already gated to
  super/admin/org_admin (`_SourcesBase._sources_admin`, `views_admin.py:1186`), so the switches
  inherit the right gate and **no partner-facing surface is built**.
- **Two attribution signals already disagree.** The Sources count uses the referral **chip**
  (`profile.referral_source == org.code`, `_source_application_counts`, `views_admin.py:1139`) —
  deliberately, because the `referred_by_org` FK drifts. The course-selector partner list uses that
  **FK** over `StudentProfile`, a different population. The digest uses the **chip** so its numbers
  match the Sources page and the Applications-list Source filter. The divergence is logged as debt,
  **not** silently changed.

## Two owner items that do not block the build

- **Consent.** `2026-draft-7` enumerates what a **sponsor** sees; it says nothing about the referring
  organisation. Naming a student to their referrer has precedent (the witness email) and the student
  named that org themselves on the apply form — but a weekly named list is broader than the consent
  describes, and with no console the names now travel *in the email*. **Mitigation built in: the
  weekly summary carries counts only.** Worth a line in the consent + agreement when the contract
  clause is next opened.
- **English only.** Every staff/partner email today is English. v1 matches. Several partners are
  Tamil-community organisations, so a per-org language column is the obvious later extension.

---

## The five emails

| Kind | Trigger | Audience when ON | Names students? |
|---|---|---|---|
| `weekly_summary` | Mondays 08:00 MYT | every qualifying partner | **no** — counts only |
| `shortlisted_followup` | Mondays 08:00 MYT | every qualifying partner with ≥1 straggler | yes, all of them, **as a table** |
| `awaiting_review` | hourly sweep after `profile_complete` | the partner(s) whose students completed | yes |
| `awarded` | hourly sweep after award | the partner(s) whose students were awarded | yes |
| `assigned` | an admin assigns a sourceless student | **that one** partner | yes |

**Qualifying partner** (`partner_comms.qualifying_partners()`): `is_active`, `contact_email != ''`,
and **not** the house org (`code != HOUSE_ORG_CODE`). Nothing else — explicitly not `PartnerAdmin`.

### The counts must reconcile

The five figures asked for do not sum to the total, so three more lines exist or a partner sees
numbers that do not add up:

| Line | Statuses |
|---|---|
| Applicants | every application with this chip |
| Not yet shortlisted | `submitted` |
| Shortlisted — application incomplete | `shortlisted` |
| Awaiting review | `profile_complete` (its own label already *is* "Awaiting review") |
| Under review | `interviewing`, `interviewed`, `recommended` |
| Awarded | `awarded`, `active`, `maintenance` |
| Rejected | `rejected` |
| Closed or lapsed | `withdrawn`, `expired`, `closed` |

**`recommended` is folded into "Under review" on purpose.** It is masked from the student
(`models.py:206`); it must not leak to a partner as a near-certainty either.

### The chase table — `{student_table}` (owner, 2026-07-26)

The chase list is a three-column HTML table, not a bare list: **Student · Applied · Last activity**,
both dates plain (`12 Jun 2026`), amber where a date is over a fortnight old so the reader can see
whom to ring first. Its own placeholder, `{student_table}`, allowed on this kind only.

| Column | Source | Why |
|---|---|---|
| Applied | `ScholarshipApplication.submitted_at` (`models.py:927`, `auto_now_add`) | exact, set once |
| Last activity | **the newest `ApplicantDocument.uploaded_at`** for that application among live docs (`superseded_at IS NULL`), falling back to `submitted_at` | the only student action we timestamp |

**`ScholarshipApplication.updated_at` must NOT be used** — it is `auto_now`, so our own background
work bumps it: verdict scoring, re-extraction, the institution sync, even a notification stamp. A
student untouched for a month would read as active this morning, and the partner would stop chasing
precisely the person who needs chasing. The email footnote states what the column measures, so the
figure cannot be over-read. Pinned by a test: a system-side `save()` must not move Last activity.

### Quiet weeks — one deliberate split from the literal rule

- `weekly_summary` — skip when that org's count fingerprint is unchanged since its last send.
- `shortlisted_followup` — skip only when the list is **empty**. An unchanged list still sends,
  because a partner whose stragglers have not moved is precisely who needs chasing.

Flagged as an interpretation; one constant (`SKIP_UNCHANGED`) flips it.

---

## Approach

### Backend

**New seam — `halatuju_api/apps/scholarship/partner_comms.py`.** One module owns every decision:
`KINDS` (+ per-kind placeholder allowlists), `qualifying_partners()`, `partner_applications(org)`,
`stage_counts(org)`, `fingerprint(counts)`, `recipient_for(org)`, `is_enabled(kind)`,
`render(kind, context)`.

**Refactor `_source_application_counts` to call `partner_applications`** so the digest and the Sources
count cannot disagree (the "one named predicate" rule in `docs/lessons.md`).

**Two new tables** (migration `0128`, additive) — one fewer than the first draft, because enablement
moved onto the template:

1. `partner_email_templates` — `kind` **unique**, `enabled`, `subject`, `body`, `updated_by_email`,
   `updated_at`. Five rows, seeded by `seed_partner_email_templates` (precedent:
   `seed_contract_template.py`). **This row is the switch.**
2. `partner_email_log` — org, kind, `recipients` JSON, subject, nullable application, `fingerprint`,
   `sent_at`, `ok`. Serves three jobs: the audit trail, the "last sent" line, and — as the most
   recent row for an (org, kind) pair — the **fingerprint the weekly skip compares against**. No
   duplicate send-state anywhere else.

Plus two nullable stamps on `ScholarshipApplication` for milestone idempotency —
`partner_awaiting_notified_at`, `partner_awarded_notified_at` (the `SponsorProfile.realtime_notified_at`
pattern).

**Migration discipline:** hand-written Postgres DDL (`migrate` does not run on deploy),
`bigint GENERATED BY DEFAULT AS IDENTITY` PKs, and each new table with **RLS enabled plus exactly one
`Backend service role only` policy**, mirrored from a sibling table — per the P1a lesson, or they land
in the Supabase advisor as `rls_enabled_no_policy`.

**Rendering.** `render()` substitutes `{placeholders}`, turns blank-line blocks into `<p>`, and wraps
with the existing `_html_email_shell` / `_send_html` (`emails.py:2748+`) so a partner email is shaped
like every other email and stays inside the branding guard. Sender identity is the **programme's**
(`branding.platform()`), reply-to `email_support` — the emails invite a reply, since there is nowhere
to send anyone. **No CTA button**, because there is no console. An unknown placeholder is rejected on
save (400) and pinned by a test (the `consentText.test.ts` precedent).

**Sending.**
- `send_partner_digests` → cron slug `partner-digests`, weekly Mon 08:00 Asia/KL.
- `send_partner_milestones` → cron slug `partner-milestones`, hourly. **Batched per org**, and it
  re-checks each application is *still* in the target state — which is what neutralises
  `revert_if_profile_incomplete` and `awarded → recommended` (`sponsorship.py:493`). That is why
  milestones are a sweep, not an inline call.
- `assigned` fires **inline**, best-effort, in `AdminApplicationWitnessView.patch`
  (`views_admin.py:1267`) — an explicit admin action, nothing to revert.
- Both commands take `--dry-run` and honour `PARTNER_NOTIFY_MAX_PER_RUN` (default 100).
  Registered in `CronRunView.JOBS` (`views.py:1789`).

**Feature flag** `PARTNER_COMMS_ENABLED`, beside `PROFILE_COMPLETE_EMAIL_ENABLED`
(`halatuju/settings/base.py:309`). Dark until the owner flips it; checked by both commands and the
inline send. Two independent gates therefore exist: the platform flag and each template's `enabled`.

**API** (on the existing `_SourcesBase`, gate inherited):
`GET …/admin/scholarship/partner-emails/` — the five templates + who currently qualifies;
`PATCH …/admin/scholarship/partner-emails/<kind>/` — `enabled`, `subject`, `body`.

### Frontend

`app/admin/sources/page.tsx` gains **one** card above the existing table:
`components/sources/PartnerEmailsCard.tsx` — five rows, each `switch · name + cadence + what it
contains · Wording`.

**The wording editor expands INSIDE its own row** (owner, 2026-07-26), not in a separate card or a
modal: `PartnerTemplateEditor.tsx` renders as the row's expanded panel — subject, body, placeholder
chips, live preview beside it, and a Save/Cancel bar. **One row open at a time.** This deliberately
mirrors the Organisations table directly below, whose Edit action already expands a full-width panel
in place (`page.tsx:187-228`), so the page has one editing idiom instead of two.

A collapsible "Who qualifies" panel lists every organisation with its address status, and the card
carries an amber banner while nobody qualifies. The page's existing `Toggle` moves to
`components/sources/shared.tsx` and is reused — no second switch.

Pure logic in `lib/partnerComms.ts` (kinds, labels, placeholder allowlist, `qualifies()`), tested in
`lib/__tests__/partnerComms.test.ts` — this repo tests helpers, not heavy component trees.
New i18n under `admin.sources.emails.*` in en/ms/ta (Tamil first-draft, flagged for review).

### Why no Stitch screen

`CLAUDE.md` mandates Stitch-first for a genuinely new component or layout redesign. This is neither:
the card repeats the existing Sources idiom (`bg-white rounded-xl shadow-sm border`, `divide-y`, the
page's own 44×24 switch) on an existing page. Per the `stitch-mcp-workflow` memory (2026-07-21), when
a high-fidelity Tailwind mock the owner has signed off already exists, that mock **is** the design of
record and Stitch adds a slow round-trip that invents its own styling.

---

## Sprints

Three sprints, split by **what can be verified alone**: controls that persist (S1), scheduled sending
(S2), event-driven sending plus the live flip (S3). Sending is deliberately not in the same sprint as
the model — otherwise there is no moment where the controls can be tested in isolation, and every
send costs Brevo quota.

### S1 — Foundation & controls (dark)

**Goal:** an org_admin can switch each email on or off and edit its wording. Nothing sends.

**Scope:** migration `0128` (2 tables + 2 stamps, hand-written DDL + RLS); `partner_comms.py`; the
`_source_application_counts` refactor; the two endpoints + `urls.py`;
`seed_partner_email_templates`; `PARTNER_COMMS_ENABLED` + `PARTNER_NOTIFY_MAX_PER_RUN`;
`PartnerEmailsCard` + `PartnerTemplateEditor` + `shared.tsx`; `admin-api.ts`; `partnerComms.ts`;
en/ms/ta; `tests/test_partner_comms.py`; `lib/__tests__/partnerComms.test.ts`.

**Acceptance**
- A switch persists across reload; `qc`/`reviewer`/`partner` get **403** on both endpoints.
- `qualifying_partners()` returns **empty** today, the banner says so, and **no `PartnerAdmin` row is
  ever consulted** — asserted by a test, since that is the correction that matters most.
- The house org is excluded from `qualifying_partners()` even after someone gives it an address.
- Every status in `STATUS_CHOICES` lands in exactly one count line, and the lines sum to Applicants.
- `recommended` never appears as its own line.
- `partner_applications` and `_source_application_counts` agree for every org.
- A template saved with an unknown placeholder is rejected (400), and one containing a console URL is
  flagged — there is no console to link to.
- All new tables report `relrowsecurity = true` with exactly one policy in Supabase.

**Complexity:** medium (~22 files). **Blockers:** none.

### S2 — The two weekly emails

**Goal:** Monday emails a partner would welcome, provably not duplicated.

**Scope:** `render()`; `send_partner_digests.py` (`--dry-run`, cap, fingerprint skip, log rows);
cron slug `partner-digests`; `tests/test_partner_digests.py` + the branding golden.

**Acceptance**
- Unchanged fingerprint → no email. Empty chase list → no email. **Non-empty unchanged list → sends.**
- One email per organisation, never one per student; the chase table carries every student (capped at
  50 rows with an explicit note when longer).
- **Last activity does not move when a system job saves the application** — the whole point of not
  using `updated_at`; and it equals the newest live document's `uploaded_at` when one exists.
- Every seeded template passes the voice guard: no banned conduit phrase, no "your student".
- The plain-text alternative of the chase email carries the same three columns, aligned.
- No recipient → skipped **and logged** (silence is not success).
- Template `enabled = false` **or** flag off → nothing sends, both proven separately.
- `--dry-run` prints recipients, subject and counts without sending.

**Complexity:** medium (~11 files). **Depends on:** S1.

### S3 — Milestones, assignment, then flag-on

**Goal:** event-driven emails that survive a reverted state, then go live.

**Scope:** `send_partner_milestones.py` (hourly, batched, state re-checked); cron slug
`partner-milestones`; the inline `assigned` send in `AdminApplicationWitnessView.patch`; "last sent"
in the card from `partner_email_log`; `tests/test_partner_milestones.py`.

**Then, in order:** owner adds a real address to one partner → preview send to the owner → owner
reads it → `PARTNER_COMMS_ENABLED=1` via `--update-env-vars` → the two Cloud Scheduler jobs with
`--account tamiliam@gmail.com --project gen-lang-client-0871147736` → trigger each once.

**Acceptance**
- A milestone is sent once and never again (stamp), and **not at all** if the application left the
  target state before the sweep ran.
- Reassigning a witness org emails the new org, not the old one.
- The owner has read a real email before the flag goes on (the "show it before the flag-on ask"
  lesson, `docs/lessons.md`).

**Complexity:** medium (~11 files). **Depends on:** S2.

---

## Sequencing rationale

Hard chain S1 → S2 → S3; risk front-loaded (the migration and the count reconciliation are expensive
to get wrong and cheap to test); value early (S1 alone records intent, which the Sources screen
cannot do today).

**External blocker, owner-side:** partner contact addresses. All three sprints ship without them;
only real-world value waits.
