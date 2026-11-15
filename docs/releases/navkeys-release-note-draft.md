# Release-note draft — sprint NAVKEYS, the admin menu follows the permissions (2026-11-16)

**DRAFT. Branch navkeys, local, not pushed. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-16, NAVKEYS builder calls, pending architect). Debt: TD-XXX-NAV (built).

## What changes for people

- **The admin menu now follows each person's permissions, not their role name.** A menu item is shown when the
  person holds the permission the server checks for that page.
- **Today nobody should notice a difference.** Every standard permission set (super, organisation admin, admin,
  finance, reviewer, QC, mentor, partner, source, member) gets exactly the same menu and lands on the same page
  as before.
- **The change shows only for someone whose permissions were set by hand:**
  - Someone given Billing, Contracts, Programme settings, Requests or Organisation settings now sees that item
    and can open the page. Before, some of these pages said "no access" even though the menu offered them.
  - An organisation admin whose Applications, Scholars, Spending or Billing permission is unticked no longer
    sees that item.

## Not changed

- No migration, no environment variable, no api change. Payments, billing and contracts permissions on the
  server are untouched; the organisation admin still sees Payments as before (this moves with M4).
- The Programme overview still shows by role (debt TD-621).

## Deploy

Services: web. No migrate step. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

1. As an organisation admin: the menu shows the same items as yesterday, and Payments, Billing and Spending open.
2. As a reviewer: the menu shows Applications and the usual items, and no Billing, Team or Settings.
3. As an admin given the Billing permission by hand: Billing appears in the menu and opens.
