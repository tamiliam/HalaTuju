# Release-note draft — sprint S1b, Cancel invitation archives the invitee (2026-11-19)

**DRAFT. Branch access-s1b-cancel-archives (on top of sprint S1), local, not pushed. The owner says yes before it goes live.**
Programme ACCESS-BY-SWITCHES. Owner ruling 19 Nov (`docs/decisions.md`). Debt: closes TD-615 when live.

## What changes for people

- **Cancel invitation now removes the person in one step.** When you cancel the invitation of someone who was
  invited into a group and never signed in, they leave the group's table and every list you pick people from,
  and the same email address can be invited again straight away. The invitation itself is kept as "cancelled"
  in the records.
- **The Cancel question says so:** "If they were invited into a group, they are removed from it, and you can
  invite the same address again later."
- **If work is still waiting on them** (cases, or scholars they mentor), the invitation is not cancelled, and the
  page says: "They still have work waiting on them, such as cases or scholars, so the invitation was not
  cancelled. Hand that work to someone else first."
- Someone who has already signed in is still removed on the People page, as before.

## Not changed

- No migration, no environment variable, no money path.
- Sponsor invitations: cancelled exactly as before. Source invitations: the unused account is switched off as
  before (not archived, so the address is not held up). Mentor invitations stay on the Mentors page.

## Deploy

Services: both. No migrate step. Publish in a release window with the owner's yes, after (or with) sprint S1.

## Phone check (owner, after live)

As an org admin, invite a test reviewer into a group, then Cancel the invitation: they leave the group table, and
the same address can be invited again.

## For a native reader

The Malay and Tamil words for the new Cancel question and the "cases waiting on them" message need a native read.
