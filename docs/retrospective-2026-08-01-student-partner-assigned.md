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

**The owner could not find the email on the screen where every sending email lives.**

*Symptom:* they opened Sources → Partner emails, saw five rows, and asked where the new one was.
It was on and sending, with no switch, no wording editor and nothing on any screen saying it
existed. Its only control was a value in the deployment settings.

*Root cause:* I chose the pattern from the wrong neighbour. `emails.py` holds ~30 hard-coded
student emails behind settings flags, so "a student email is hard-coded" felt like the house style
— and it is, for emails nobody has ever needed to switch. But this platform has a **surface** for
exactly this family: a template with a switch and a wording editor that an owner operates. I built
the thing and not the control, and never asked where the owner would go to see it.

*What prevents recurrence:* the general rule this project already carries — *a stored field with no
surface is a defect* — extends to a **switch** with no surface, and to a **behaviour** with no
surface. Concretely: when a feature can be on or off, decide in the plan **which screen shows its
state**, and if the answer is "none", that is the design not being finished. The fix here was to
make the row the real thing: the wording the owner edits IS what sends, so the screen cannot lie.

**Flattening a bilingual email into one template body silently anglicised half of it.**

*Symptom:* the Malay half rendered "Program BrightPath Bursary", signed "The BrightPath Bursary
Team".

*Root cause:* `programme_name` and `team_signoff` are single tokens resolving to English, because
every previous template in that family is English throughout. Moving a bilingual email onto a
mechanism built for monolingual ones inherits that assumption invisibly — the copy still *looked*
bilingual, and only the brand words were wrong.

*What prevents recurrence:* `programme_name_ms` / `team_signoff_ms` tokens, and a test asserting
both halves read as their own language. The transferable point: **when moving content onto an
existing mechanism, list what that mechanism assumes about the content** — here, one language.


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

Planned **3.5h** (quoted 30 July, accepted the same day). Spent **2.8h** — 1.5h building it, and a
further 1.3h re-homing it onto the Sources screen after the owner could not find it. That second
pass was fixing my own miss, not new scope; it happens to land inside the quote, which does not
make it free work anyone should have had to ask for. The original quote assumed a new
bilingual template and its tests, which is exactly what it was — the saving came from the hook
already existing and the requester having answered the reassignment question in the thread before
work started.
