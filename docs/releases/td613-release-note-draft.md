# Release-note draft — sprint TD-613, a case whose reviewer has left can change hands (2026-11-15)

**DRAFT. Branch td613, local, not pushed. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-15, TD-613 builder call, pending architect). Debt: TD-613 (closed), TD-622
(note), one new item for the suspended-cases banner (number from the architect).

## What changes for people

- **A reopened case whose reviewer has gone can be reopened.** Before, a super's Reopen was refused ("the reviewer
  can no longer review") when the reviewer had been suspended, archived or taken out of Reviewers. Now the reopen
  goes through, and the case says it needs a new reviewer.
- **An award that falls through and goes back to Awaiting QC can change hands.** Before, it stayed with its old
  reviewer and could not be moved. Now it can.
- **Who may move it is unchanged:** an organisation admin or super with the assign door, to a signed-in member of
  Reviewers in the same organisation, never to themselves. QC rules are unchanged: the person who held or decided
  the case still cannot QC it.
- **From Awaiting QC on, such a case can never be set back to Unassigned.** The cockpit and the list grey out "Unassigned" and say why
  ("The reviewer on this case can no longer review it. Give it to someone in Reviewers.", in English, Malay and
  Tamil).
- **A suspension alone does not free a case after the interview.** At Awaiting QC or later, a case whose reviewer is
  only suspended stays with them (they may be restored) unless a super reopens it. A case whose reviewer is archived
  or out of Reviewers can change hands. Before the interview, any reviewer who cannot review can be replaced.
- **Closed cases never move:** awarded, active, closed or withdrawn, unless a super reopens them.
- **The student is not emailed** "who will interview you" when a case changes hands after the interview. The new
  reviewer is emailed as usual.
- **A person in No group who still held such a case can be deleted** once the case is handed on.
- **The cockpit's reviewer box at Awaiting QC now follows the server.** It used to look editable after a reopen at
  Awaiting QC and then refuse; it is now locked there unless the reviewer has gone.

## Not changed

- No migration, no environment variable, no money path. Only the case's reviewer changes.
- The Staff list's suspended-cases banner still does not count cases held by an archived person (new debt item).

## Known limits

- The student's "who will interview you" email checks the case's stage when the email is sent (a few minutes
  later), not when the case changed hands.
- An award that falls through to Awaiting QC while its reviewer is only suspended stays with them; restore the
  reviewer, or have a super reopen the case, to hand it on.

## Deploy

Services: both (api and web). No migrate step. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

1. As a super, reopen a decided case whose reviewer has been suspended: it reopens, and the Reviewer box shows the
   amber "can no longer review it" line with "Unassigned" greyed.
2. Choose a reviewer in that box: it saves, and the new reviewer sees the case in their list.
3. Reopen a case at Awaiting QC whose reviewer is still active: the Reviewer box stays locked.
