# Release-note draft — sprints THANKS and THANKS-SCHOLARS, approve a graduation thank-you from the scholar's file (2026-11-16)

**DRAFT. Branches thanks and thanks-scholars, local, not pushed. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-16, THANKS-SCHOLARS, which supersedes THANKS). Debt: TD-632 (note updated).

Owner, 2026-11-16: "Thank yous are part of the scholar maintenance process."

## What changes for people

- **A student's graduation thank-you can be approved again.** Since the moderation list was retired
  (2026-11-07), no screen could approve one, so a thank-you stayed waiting and never reached the sponsor.
  One is waiting in production now.
- **It is done on the scholar's file** (Scholars, open the scholar, Overview). A card, "Graduation
  thank-you", shows what the student wrote and its status: waiting for review, held back, approved or
  rejected. The application's case page no longer shows it.
- **Waiting for review:** the text the sponsor will see starts as the student's own words and can be edited
  (to take out anything that could name the student). **Approve and send**, or **Reject** with an optional note.
  The text is checked again on approval; if it still names the student (name, school, town, IC number,
  phone or email), the card says so and nothing is sent.
- **Held back:** the automatic check found something that may name the student, and the card says what.
  Only **Reject** is offered; the student edits and sends it again.
- **Who sees the card:** whoever holds the **Scholars** permission in that organisation (a super holds every
  permission). An organisation admin holds Scholars on their standard set, so they can approve. A reviewer
  cannot: their work ends at the award, so a reviewer holding Review alone, even the one who was given the
  case, does not see or decide a thank-you.
- **A mentor** sees their own current student's thank-you, read only, with no buttons. A reject note is staff-only: a mentor never sees it.
- A thank-you can still be decided after the scholar's file is closed.
- Earlier versions of a thank-you (each send adds one) are listed underneath, read only.

## Not changed

- No migration, no environment variable, no money path, no new permission. The sponsor page still shows
  approved thank-yous only, with the student's reference and never their name.
- A thank-you from another organisation's student cannot be read or decided (the server answers "not found").
- What a reviewer can do anywhere else is unchanged.
- Later: the Scholars permission will be split into View and View-and-change for every change on the
  scholar's file. Until then, everyone who holds Scholars keeps the power to approve.

## Deploy

Services: both (api, then web). No migrate step. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

1. As an organisation admin, open the scholar's file of the student whose thank-you is waiting (Scholars, open
   the scholar, Overview). Check the text, take out anything that names the student, then tap Approve and
   send. The card then shows "Approved" and the text sent.
2. As that student's sponsor, the thank-you now appears under "Messages from students you supported",
   with no name.
3. As a reviewer (holding Review, not Scholars): the thank-you is not reachable. The case page shows no card,
   and the scholar's file does not open.
4. As that student's mentor: the scholar's file shows the thank-you, read only, with no Approve or Reject buttons.
5. On a phone (375px wide): the card fits, the text box and both buttons are easy to tap, and nothing scrolls
   sideways.
