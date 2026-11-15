# Release-note draft — sprint TD-631, Surveys, Development and Announcements open on their view permission (2026-11-15)

**DRAFT. Branch td631, local, not pushed. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-15, TD-631 builder calls, pending architect). Debt: TD-631 (resolved).

## What changes for people

- **Someone given only the "view" permission for Surveys, Development or Announcements can now open that page.**
  They see the list, the results or the progress, and can download the CSV. They are not offered New, Edit,
  Close, Delete, Archive, Withdraw, Remind or "Mark reviewed". Before, the page said "no access".
- **The same applies to the Surveys and Growth tabs on a scholar's file.** The Growth tab's "Progress" link now
  follows the permissions as well.
- **The menu offers these pages to a "view" holder.**
- **Today nobody should notice a difference.** Every standard permission set gives both "view" and "edit" for these
  areas, or neither. The change shows only for someone whose permissions were set by hand.

## Not changed

- No migration, no environment variable, no api change, no money path. Payments, billing and contracts are untouched.
- Whoever holds "edit" sees every button as before.

## Deploy

Services: web. No migrate step. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

1. As an organisation admin: Surveys, Development and Announcements open, and you can still make, edit and send.
2. As someone given only the "view" permission for Surveys: Surveys opens and shows the results, with no New,
   Edit, Close, Delete or Remind button.
3. As a reviewer: Surveys, Development and Announcements are not offered.
