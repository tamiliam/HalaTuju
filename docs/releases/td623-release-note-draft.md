# Release-note draft — sprint TD-623, the web reads the served keys only (2026-11-15)

**DRAFT. Branch td623, local, not pushed. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-15, TD-623 builder calls, pending architect). Debt: TD-623 (resolved).

## What changes for people

- **What a person may see and do on a page now comes only from their permissions.** The role name (admin, QC,
  reviewer and so on) is a label. Before, a few pages also let someone in by their role name if their permissions
  had not been sent; every sign-in sends them now, so nobody should notice a difference on those pages.
- **QC people now see the "All assignees" filter on Applications.** It shows for whoever can read every application
  or assign cases. Admins keep it; reviewers still do not see it (their list is already their own cases).
- **The pages concerned:** Announcements, Surveys and Development (making and reading them), the scholar's Mentor,
  Surveys and Growth tabs, the Mentors tab and Emails tab on Team, the Sponsors emails panel, the Sources invite
  button, the cockpit's witness card and its "Reject" card for organisation admins, and the request actions on an
  organisation request.

## Not changed

- No migration, no environment variable, no api change, no money path. Payments and sponsor credits are untouched
  (frozen until M4).
- The menu and where a person lands after sign-in are unchanged.

## Deploy

Services: web. No migrate step. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

1. As an organisation admin: Announcements, Surveys and Development open and let you make one; Team shows the
   Mentors and Emails tabs.
2. As a QC person: Applications shows the "All assignees" filter.
3. As a reviewer: Applications shows no assignee filter, and Announcements is not offered.
