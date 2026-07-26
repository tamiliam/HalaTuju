# Retrospective — Partner-organisation comms (S1 + S2/S3), 2026-07-26

Roadmap `docs/plans/2026-07-26-partner-comms-roadmap.md`. Design of record: the Tailwind mock at
<https://claude.ai/code/artifact/40bb4e5f-7335-4d88-97c4-d7a9f0399a04> (four revisions).
Shipped in two passes on one day: S1 (controls + wording, live and dark) then S2+S3 together
(rendering + sending, live and dark).

## What it does

A referral organisation used to hear from us exactly once — when a student they referred needed
their witness signature on an agreement. Five emails now exist: a weekly stage summary, a weekly
chase list, two milestone alerts (completed / awarded) and an assignment alert. Each is switchable
by the programme's org_admin from the Sources page, with the wording editable in place.

## What went well

**The owner's corrections landed as code, not as notes.** Three of them:

1. *"I don't want the emails to be selectable by partner organisation… it is either, or."* That
   deleted a whole table (`partner_notification_settings`) and every per-organisation control from
   the screen. Enablement became a property of the template.
2. *"There is no partner console built as of now. You are confusing the Halatuju partners with
   BrightPath partners."* This reversed a decision the owner had already approved — see below.
3. *"We want the partner organisations to see BrightPath as their bursary programme as well… they
   are not merely conduits."* Now enforced by `banned_phrases`, which refuses a save containing
   conduit phrasing or "your students", with the seeds asserted to pass the same check.

**The tests target silence, not just correctness.** A weekly email's real failure modes are
repeating an unchanged scoreboard forever, going quiet on someone who needs chasing, and skipping
an organisation with no trace. Each has a test: the fingerprint skip, the deliberate non-skip of
the chase list, and the "logged once, not 24 times a day" dedup.

**Two traps were caught before they shipped.** `application.updated_at` would have been the obvious
source for "last activity" and is `auto_now`, so our own sweeps bump it — a dormant student would
have read as active and the partner would have stopped chasing them. And the five counts the owner
asked for do not sum to the total, so a partner would have seen 44 of 62 students accounted for.

## What went wrong

**I put an option to the owner without stating its premise, and got approval for the wrong thing.**
I offered "recipients = contact_email + the org's partner logins" and it was approved. The premise
— that those logins were the partner's *bursary* representatives — was false: both are
course-selector accounts from March with no B40 scope at all, and emailing them bursary progress
would have disclosed applicant data to an audience attached to a different product. The owner
caught it. A one-line premise beside each option would have surfaced it before the choice was made.
Recorded in `docs/lessons.md` and reversed explicitly in `docs/decisions.md` rather than quietly
rebuilt.

**I called S1 "the five emails" when it was the five templates.** The owner asked "have we not built
all 5 emails including the weekly ones?" — and the honest answer was that the wording existed and
nothing could send. My own module docstring claimed the module handled "how a stored template
becomes a subject + text + HTML body", which it did not. Corrected. The lesson is narrower than
"be accurate": when a sprint boundary falls between *configuring* a feature and *running* it, the
status line must say which side it landed on.

**The three-sprint split was defensible and still wrong for this owner.** Sending deliberately did
not land with the model, so the controls could be tested in isolation — and that genuinely caught
the counts and `updated_at` problems with nothing live. But it left a boundary that reads as
ceremony, and S2+S3 together were ~20 files. Merging them on request cost nothing.

## Decisions worth remembering

- **Enablement lives on the template**, never on an (org, kind) pair.
- **Recipients are `contact_email` only.** A `PartnerAdmin` row is never consulted; a test asserts it.
- **The house organisation is excluded by rule**, not by whether someone filled in its address.
- **"Last activity" is a document upload**, and the email says so, so the figure cannot be over-read.
- **A milestone is stamped only on a successful send** — so an unreachable partner is told later
  rather than never.
- **Milestones are a sweep, not an inline call**, because the sweep re-checks the current status and
  a reverted transition therefore produces no email at all.

## Numbers

3484 → **3536 pytest** (+97 across both passes), 776 jest (+14), one migration (`0128`, applied
migrate-first with the sibling RLS convention; advisor clean).

## What is owed

The nine partner contact addresses — an owner task, and the only thing gating any real value. Until
they exist the card reads, honestly, "0 of 9 partner organisations can receive an email today".
Then: read a `--dry-run`, flip the flag, switch on the templates, create the two scheduler jobs.

Malay and Tamil are not needed here (every partner email is English, as every staff email is), but
the *screen's* ms/ta strings are first drafts and want an owner pass.
