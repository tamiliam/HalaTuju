# Release-note draft — sprint THANKS, approve a graduation thank-you from the case page (2026-11-16)

**DRAFT. Branch thanks, local, not pushed. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-16, THANKS). Debt: TD-632 (note updated).

## What changes for people

- **A student's graduation thank-you can be approved again.** Since the moderation list was retired
  (2026-11-07), no screen could approve one, so a thank-you stayed waiting and never reached the sponsor.
  One is waiting in production now.
- **It is done on the student's case page** (Applications, open the case). A new card, "Graduation
  thank-you", shows what the student wrote and its status: waiting for review, held back, approved or
  rejected.
- **Waiting for review:** the text the sponsor will see starts as the student's own words and can be edited
  (to take out anything that could name the student). **Approve and send**, or **Reject** with an optional note.
  The text is checked again on approval; if it still names the student (name, school, town, IC number,
  phone or email), the card says so and nothing is sent.
- **Held back:** the automatic check found something that may name the student, and the card says what.
  Only **Reject** is offered; the student edits and sends it again.
- **Who sees the card:** whoever holds the **Review** permission and can open that case (a reviewer opens the
  cases given to them; a super holds every permission and opens any). The role name decides nothing. Organisation admins do not hold Review on their standard set, so they do not see the
  card unless Review was given to them.
- Earlier versions of a thank-you (each send adds one) are listed underneath, read only.

## Not changed

- No migration, no environment variable, no money path. The sponsor page still shows approved thank-yous only,
  with the student's reference and never their name.
- A thank-you from another organisation's student cannot be read or decided (the server answers "not found").
  The same holds for a case in your own organisation that you cannot open: a reviewer decides only for the
  cases given to them, unless they may see every case.

## Deploy

Services: both (api, then web). No migrate step. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

1. As the reviewer assigned to the case of the student whose thank-you is waiting (a reviewer opens only the
   cases given to them; a super opens any), open that case: the "Graduation thank-you" card shows the
   message, marked "Waiting for review".
2. **Approve the one waiting thank-you, as a reviewer.** Check the text first and take out anything that
   names the student, then tap Approve and send. The card then shows "Approved" and the text sent.
3. As that student's sponsor, the thank-you now appears under "Messages from students you supported",
   with no name.
4. As an organisation admin without Review: the same case page shows no thank-you card.
5. On a phone (375px wide): the card fits, the text box and both buttons are easy to tap, and nothing scrolls
   sideways.
