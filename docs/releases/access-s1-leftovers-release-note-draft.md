# Release-note draft — sprint S1, case and team leftovers (2026-11-19)

**DRAFT. Branch access-s1-leftovers, local, not pushed. The owner says yes before it goes live.**
Programme ACCESS-BY-SWITCHES. Brief: `docs/plans/2026-11-19-s1-leftovers-brief.md`.
Debt: TD-664 (all but d), TD-627, TD-634, TD-616, TD-630, TD-618.

## What changes for people

- **A case's buttons follow the person's permissions, as the server checks them.** The quality-check panel, the
  Re-verify IC card and the pre-award Close card show only for people the server will let use them. Before, some of
  them were worked out from the person's title on the phone or computer. Nobody with a standard permission set
  should notice a difference.
- **No Save button on a closed case.** A super who reopens a case that is past the award, or ended before it, no
  longer sees a Save button that the server would refuse.
- **The buttons stay right after every change.** After saving, nudging, scheduling a payment or asking the student
  for information, the case keeps its buttons. Before, a few of these replies left them out.
- **A funded scholar's file:** you can add an activity note only while the file is open and you hold the Scholars
  permission.
- **Handing a case to someone in another organisation** now says "This reviewer is in another organisation" instead
  of "You can only assign to a reviewer". In the picker on a case, that person is shown but greyed out.
- **Delete on the team pages** is offered only when the person is in no group, everywhere it is shown, as the
  Delete button already required. Someone who never signed in can still be deleted as before.
- **The Staff list's warning** about open cases now also counts cases held by people who were deleted, and says
  "suspended or deleted".
- **Background profile writing** stops for a case that has been awarded, declined, withdrawn or closed (no AI call
  is paid for it).

## Not changed

- No migration, no environment variable, no money path. What each door allows is unchanged.
- The PATCH's Vircle ID correction still checks the organisation admin's title (TD-664 d, left open).
- Invitees: removing them is the next step, S1b (owner, 19 Nov).

## Deploy

Services: both. No migrate step. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

On your phone, as a QC person, open a case waiting for QC: the QC panel shows as before. As someone without
'Reject or close applications', open a submitted case: there is no Close card. Open a funded scholar's file: you
can add an activity note only while the file is open. As a super, try to give a case to a reviewer from another
organisation: you are told they are in another organisation.

## For a native reader

The Tamil (and Malay) words for the two changed Staff-list warnings and the new "another organisation" message
need a native read.
