# Retrospective — the student is told who else is involved (request #3), 2026-08-01

**Deliverable:** when an administrator assigns a partner organisation to a sourceless student, the
student is now emailed too. **The first request anyone paid for.**

**Shipped:** `129da5bd` (the email + hook + 10 tests), `0e8adcee` (the sender fix + an 11th test).
No migration. Two deploys — the second because I read the rendered email and found it wrong.

---

## What was built

A new bilingual (EN + BM) student email, HTML with a plain-text fallback, hung off the same
`AdminApplicationWitnessView` hook that has told the *organisation* since July. It names the
organisation, says it may act as a witness to the bursary contract and can see certain details of
the application in order to do so, and asks for nothing — there is no accept, decline or reply.

The requester's framing decided the shape: *"We DO NOT want the student's consent, but a
notification is a must."* And their answer to the one open question — *"We do not want to reassign
a student to another organisation. It raises privacy and confidentiality issues"* — decided what
happens on a change: it still emails, because if a reassignment ever does occur the student's
interest is in knowing who holds their details **now**. Silence there would be the worse failure.

## Design decisions

- **The copy names the access.** The owner chose the plain version over the warm-and-brief one.
  Access is BrightPath's own stated reason for insisting on a notification, so a version that
  omitted it would have been a softer email that failed the request's purpose.
- **The switch defaults ON.** Every comparable email in this codebase dark-launches OFF, but each
  of those is dark because something outside the code is unresolved. Nothing is pending here: the
  feature was requested, quoted, accepted and paid for. **A paid feature that ships switched off is
  a non-delivery dressed as caution.**
- **It does not share `PARTNER_COMMS_ENABLED`.** That flag answers "what do organisations receive?"
  Hanging a student's notification off it would mean turning partner comms dark silently withholds
  something the student is owed. Both directions have a test.
- **The organisation's own email is untouched.** It still fires on every save, including a same-org
  re-save. Narrowing it to match the student's rule would be a change to partner comms nobody asked
  for.

## What went wrong

**The email was going out from the interview alias, and no test would ever have caught it.**

*Symptom:* rendered output showed `From: interview@halatuju.xyz` on a message with nothing to do
with interviews — which also stamps interview unsubscribe headers on it.

*Root cause:* `_send_html` defaults `from_email` to the interview alias because interview mail is
its main caller. The default is invisible at the call site: the correct call and the wrong call
look identical, and the wrong one is shorter. Every test I had written asserted things *inside* the
body, and the golden fixture would have recorded the wrong sender as the expected value — the
snapshot pins whatever it is given.

*What prevents recurrence:* an explicit test that the sender and reply-to are not the interview
alias, and this entry. The general habit is the one that actually found it: **render the artefact
and read it as its recipient before shipping**, because a default nobody passes is invisible to
tests written from the code.

## Numbers

- 11 tests added, all through the real endpoint; two guards bite-checked (the change-of-org
  condition, and the best-effort wrapper — patched at the student mailer itself, not upstream).
- Email branding golden: 20 lines added for the two new specs; no existing email's bytes changed.
- Backend suite 5280 passing; the 7 red are TD-209, unrelated and pre-existing.

## Hours

Planned **3.5h** (quoted 30 July, accepted the same day). Spent **1.5h**. The quote assumed a new
bilingual template and its tests, which is exactly what it was — the saving came from the hook
already existing and the requester having answered the reassignment question in the thread before
work started.
