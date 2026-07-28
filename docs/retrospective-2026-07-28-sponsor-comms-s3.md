# Retrospective — sponsor comms (S3): an org_admin decides what sponsors hear

**Date:** 2026-07-28
**Branch:** `feat/sponsor-detail` (worktree). **Migration `0133` — NOT yet applied.**
**Roadmap:** `docs/plans/2026-07-27-sponsor-module-roadmap.md` · design of record
<https://claude.ai/code/artifact/9eec1f75-e38d-49d3-9df9-d4ad7a7b9fe3>

---

## What Was Built

Nine editable sponsor emails, each with its own switch and wording, behind two independent gates
(`SPONSOR_COMMS_ENABLED` **and** each template's `enabled`), with every attempt logged including
the skips.

**The gap it closes:** a sponsor registered, was vetted and was approved without hearing anything.
`AdminSponsorReviewView` flipped a field and returned. Eight people on production were approved in
silence, and the only mail a sponsor had ever had from us was a new-student alert.

Six kinds are new (`welcome`, `approved`, `rejected`, `suspended`, `reinstated`,
`credit_confirmed`). Three already existed as hardcoded emails and were adopted onto templates via
a `{student_cards}` structural token, so the panel covers what a sponsor actually receives rather
than the two-thirds that happened to be new.

**Shared, not duplicated:** the block renderer moved out of `partner_comms` into
`email_templates.py`, and the wording editor into `components/emails/TemplateEditor`. Both families
use one implementation.

**Owner decisions at sprint start:** nine kinds rather than eleven, and one sprint end-to-end
rather than the wording-then-send split.

---

## What Went Well

- **The extraction was verified by somebody else's tests.** `partner_comms.render` delegating to
  the shared seam is guarded by 113 email goldens and 259 partner/email tests, all passing
  unmodified. That is a better proof than anything I could have written for the new module.
- **The seeds are validated by the guards they will later face.** The seed command runs each of
  the nine through `unknown_placeholders` and `banned_phrases` before writing, and a test asserts
  it — so the panel cannot ship with copy an org_admin would be unable to re-save after touching.
- **The org-fence guard and the i18n hygiene guard both fired unprompted** and both were right:
  one wanted the new endpoints classified, the other caught a genuinely novel pattern (below).
- **The `KINDS` / `PLACEHOLDERS` / `SEEDS` consistency test derives from the model's own choices**
  rather than a hand-copied list — the failure mode recorded in an earlier lesson, avoided here on
  purpose.

---

## What Went Wrong

**1. The sprint's central risk was one I nearly designed straight into it — and my fix was
still half wrong until the owner corrected the seeding.**
*What happened:* the plan was "route the three existing hardcoded emails through the new template
system". Both gates default to off, so the first deploy would have silently stopped three emails
that are live on production — no error, no failing test, and a panel showing a tidy row of
switches all correctly reading "off". I caught that and added a fallback to the pre-S3 senders.
But I keyed the fallback on `is_enabled(kind)` — platform gate AND switch — and seeded all nine
off. The owner then said to keep the already-active ones active, which exposed the rest of the
problem: with those three shipping ON, "off" stops meaning "not yet adopted" and starts meaning
"stop sending this", and a fallback keyed on the switch would have made that **unenforceable**.
Ticking `weekly_digest` off would have fallen straight back to the hardcoded sender: the email
carries on, the screen says otherwise.
*Why it happened:* a dark launch is a safe pattern for NEW behaviour, and I applied it by analogy
to the partner sprint, where all five emails were new. The word "adopt" hid a migration inside
what read like a build. Then, having found the fallback, I picked the gate condition that looked
symmetrical with `is_enabled` elsewhere instead of asking what "off" would come to MEAN once these
three were switched on — a question only the seeding decision surfaced.
*What prevents recurrence:* the fallback keys on `comms_enabled()` alone, giving two clean worlds
(pre-flip: nothing changes; post-flip: templates govern completely), with tests asserting both
that the legacy sender still fires while dark AND that switching an adopted email off after the
flip really stops it. Lesson recorded in the general form: **when a sprint moves an EXISTING
feature behind a flag, list what is live first, treat each as a migration with a fallback, and
then ask what the flag's "off" position will MEAN to the person who owns it** — a fallback that
silently overrides "off" is worse than no fallback, because it makes the control a lie.

**2. Generalising the editor broke an i18n guard, for a reason worth keeping.**
*What happened:* passing `prefix="admin.sources.emails"` to the shared editor failed the
`admin.sources` hygiene test, which scans for literals matching `admin.sources.*` and asserts each
resolves to a string. A namespace resolves to an object.
*Why it happened:* the guard's contract is "every literal that looks like a key is a leaf", and a
prefix-prop breaks that contract by design — a new idiom the scanner predates.
*What prevents recurrence:* the scanner now carries an explicit `NAMESPACE_PROPS` allowlist with
the reason written next to it, rather than a loosened regex that would stop it catching real
missing keys. Noted in lessons for the next component parameterised by i18n prefix.

**3. A heredoc-driven edit silently truncated and produced a syntax error.**
*What happened:* the i18n block for three locales was large enough that the shell heredoc was cut
off mid-string.
*Why it happened:* I used a heredoc for content far past the size where that is sensible.
*What prevents recurrence:* the content went into a scratchpad script file instead, and the result
was verified by comparing leaf-key SETS before and after (+59 per locale, 0 lost) rather than by
reading the diff — the diff was noisy with formatting, and a key-set comparison is the check that
actually answers "did I destroy anything".

---

## Design Decisions

All three in `docs/decisions.md`:

1. **Nine kinds, not eleven** — `low_balance` and `annual_statement` edge into marketing, and
   sponsor consent is a bare version string with no stored wording behind it (TD-186), so what was
   agreed to cannot be checked.
2. **The three already-sending emails ship switched ON, and the fallback keys on the PLATFORM
   gate** — not on each template's switch, so "off" is enforceable on precisely the emails that
   already reach people.
3. **The voice guard refuses a tax-relief claim** — no LHDN s44(6) approval exists; it is the one
   sentence on this surface that could cost a donor money rather than merely read badly.

Smaller, recorded in code: the emails panel is gated NARROWER than the sponsor list it sits on
(finance reads sponsors, but deciding what donors are told is editorial); an empty optional token
drops its paragraph rather than rendering a gap; and the card cap announces what it dropped, where
the pre-template email truncated at five in silence.

---

## Numbers

| | Before | After |
|---|---|---|
| scholarship pytest | 3622 | **3662** |
| jest | 918 | **956** |
| jest suites | 62 | 64 |
| migrations | — | **0133** (not applied) |

New files: `email_templates.py`, `sponsor_comms.py`, `sponsor_notify.py`,
`seed_sponsor_email_templates.py`, `migrations/0133`, `test_sponsor_comms.py`,
`lib/sponsorComms.ts`, `components/emails/TemplateEditor.tsx`,
`components/sponsors/SponsorEmailsCard.tsx` + its test, `lib/__tests__/sponsorComms.test.ts`.
i18n: +59 leaves × 3 locales.

---

## Carry

1. **▶ AT DEPLOY: apply migration `0133` MIGRATE-FIRST** (two tables, RLS + one `service_role`
   policy each), then push. **THEN run `seed_sponsor_email_templates` once** — all nine arrive OFF
   and `SPONSOR_COMMS_ENABLED` is unset, so nothing sends.
2. **▶ OWNER:** the three already-sending emails arrive switched ON, so the flip is safe — read
   their wording first if you want to change it, since the flip moves them onto these templates.
   The six new ones arrive OFF: read each, edit the wording, switch on the ones you want. Then
   `SPONSOR_COMMS_ENABLED=1` via `--update-env-vars`. After the flip, switching an email off
   really does stop it.
3. **ms/ta first drafts** for the ~59 new `admin.sponsors.emails.*` leaves — TD-183, ideally the
   same sitting as the partner drafts (TD-180). The nine `error.*` strings matter most.
4. **TD-185** (`creditChain` should key on status, not the timestamp) folds naturally into S4.
5. **S4 remains:** mandatory reject/suspend reason — which also gives `rejected` and `suspended`
   the `{reason}` token they currently ship without — the per-sponsor email log on the detail
   page, and CSV export.
