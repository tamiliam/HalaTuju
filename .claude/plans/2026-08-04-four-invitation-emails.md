# Sprint — Four invitation emails, one home, and a sponsor pitch

Owner's brief, 2026-08-04:
1. Two more invitation templates — one for **admin**, one for **source**.
2. "Joining the team" exists twice; **remove the one under Reviewers** so invitations live in one place.
3. The sponsor invitation here is the **organisation's**, not a peer's. It should pitch the concept
   — bright students held back by money — and invite the reader to become a **donor of the
   organisation** who then sponsors deserving students. **Not** "a sponsor of the org".

Owner decision (AskUserQuestion, 2026-08-04): the **Source** letter is written for the console —
sign in and follow the students your organisation referred. It therefore **cannot send until the
Source console exists**, and that is accepted.

---

## Deliverable

Four invitation templates, one per group on the Invitations page, plus the duplicate removed and
the sponsor letter rewritten as a pitch.

| Kind | Group | Sends today? |
|---|---|---|
| `invite_admin` | Admin | yes |
| `invite_reviewer` (renamed from `invite_staff`) | Reviewers | yes |
| `invite_source` | Source | **no — no login, no invite form** |
| `invite_sponsor` (rewritten) | Sponsors | yes |

**Which letter a staff invite uses is decided by `invitations.KIND_ROLES`** — the same map that
groups the page's tables. One source of truth, so the email and the table cannot disagree: `finance`
gets the admin letter, `qc` gets the reviewer letter.

**A `partner` or `super` invite keeps the BUILT-IN wording and reads no stored template.** Those are
platform-level — a Referral Partner is a different product relationship (decisions.md, 2026-08-03) —
and an org_admin editing "the admin invitation" must not silently change what a platform-level
account receives.

---

## Two findings from lessons.md / decisions.md that change the work

### 1. The donor pitch is guarded by the wrong voice guard — IN SCOPE

`invite_sponsor` is a `PartnerEmailTemplate`, so its save runs `partner_comms.banned_phrases`
(`views_admin.py:1731`), which bans conduit phrasings only. The **tax-relief ban lives in
`sponsor_comms.BANNED_PHRASES`** (`views_admin.py:1865`) — a different family this row never
touches.

So the one email on the platform that is explicitly a **donor pitch** — the single most likely place
somebody types "tax deductible" — is validated by the guard that does not check for it. HalaTuju
holds **no LHDN s44(6) approval**; decisions.md 2026-07-28 calls this "the only sentence available on
this surface that could cost the reader money rather than merely read badly."

Rewriting this letter INTO a pitch raises the odds of that sentence appearing. **Fix the guard in the
same change**: the invite family must also refuse tax-relief, student-ownership and urgency copy.
This is lessons.md's *"moving content onto an existing mechanism inherits everything that mechanism
assumes about the content"* — the assumption here is "partner emails are progress reports", and a
pitch breaks it.

### 2. A sponsor NOMINATES; the programme AWARDS — settled, do not re-litigate

decisions.md, owner 2026-07-28: all sponsor-facing copy states that a sponsor *nominates* and **the
final decision on every award rests with the programme**. The "you gift to a student" framing is
retired, because a conduit passing earmarked money to a named beneficiary is a different legal
animal from a charity receiving gifts.

The owner's new brief is **compatible and in fact closer to this** than today's wording: "donor of
the organisation" is the completed-gift framing; "sponsor of {org_name}" was the problem. The pitch
must invite them to give to the programme and nominate whom they would like to support — never
promise they choose and pay a named student directly. Keep the softening clause the rest of the
product uses: *we follow your choice wherever we can*.

## Lessons applied (sprint-start step 2)

- **A seed command is CODE and runs AFTER the deploy; a migration is DATABASE and runs BEFORE.**
  Burned earlier today — the Emails tab was empty because the seed had not run. This sprint has
  BOTH: migration `0146` migrate-first with its ledger row, then push, then `seed-partner-emails`
  once the new image is serving. Do not conflate the two orderings.
- **Render each letter and read it as its recipient, metadata included.** The partner-assignment
  email went out from `interview@` because a shared helper's default was never passed. Print all
  four rendered letters end to end — subject, sender, reply-to, body — before shipping. Note
  `send_sponsor_invitation_email` replies to `email_support` while the peer letter replies to
  `sponsor_reply_to`; decide deliberately rather than inheriting.
- **A test that asserts a call REFUSES has not tested the refusal — read what it SAYS.** The new
  banned-phrase entries and the required-placeholder guard must be asserted on the message, not just
  the raise.
- **Say whether two lists PARTITION or OVERLAP.** Four invite kinds must partition the invite
  family; the Sources screen must show none of them. The existing partition test is the guard —
  it caught the last leak and must stay green.
- **Bite-check every guard**: break it, watch the named test fail, restore.

## Files (~15)

Backend: `models.py` (choices, `INVITE_KINDS`), `migrations/0146_*` (choices + data rename),
`emails.py` (template selection by role; sponsor built-in rewritten), `partner_comms.py`
(placeholders ×2, required tokens, banned phrases), `reviewer_system_emails.py` (drop
`partner_welcome`), `seed_partner_email_templates.py` (4 invite seeds).

Tests: `test_invitations.py`, `test_partner_comms.py`, `test_reviewer_emails.py`,
`test_email_branding.py` (the sponsor golden changes **deliberately**; the staff goldens must NOT —
the built-in staff wording is untouched, which is the regression guard).

Frontend: `InvitationEmailsCard.tsx` (four kinds), i18n en/ms/ta (add three kind/when pairs, remove
the `partner_welcome` system-email keys).

## Execution

Single agent, sequential. The steps are interdependent — model choices → migration → seeds → sender
selection → front-end labels — so there is nothing safely parallel here and file overlap is total.

## Flagged, NOT in scope

The organisation's sponsor invitation is **English-only**, while the peer-to-peer referral invite is
trilingual (en/ms/ta). A donor pitch is exactly the letter that benefits from the reader's language.
Not a regression — it is already English-only — but worth an owner decision later.
