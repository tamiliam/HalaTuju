# Release-note draft — sprint NAVKEYS, the admin menu follows the permissions (2026-11-16)

**DRAFT. Branch navkeys, local, not pushed. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-16, NAVKEYS builder calls and review round, pending architect).
Debt: TD-XXX-NAV (built).

## What changes for people

- **The admin menu now follows each person's permissions, not their role name.** A menu item is shown when the
  person holds the permission the server checks for that page.
- **Today nobody should notice a difference.** Every standard permission set (super, organisation admin, admin,
  finance, reviewer, QC, mentor, partner, source, member) gets exactly the same menu and lands on the same page
  as before.
- **The change shows only for someone whose permissions were set by hand:**
  - Someone given Billing, Contracts, Programme settings, Requests or Organisation settings now sees that item
    and can open the page. Before, some of these pages said "no access" even though the menu offered them.
  - An organisation admin whose Applications, Scholars, Spending or Billing permission is unticked now loses
    that menu item. The server already refused those pages, so the menu was offering a page that would not open.
  - Someone who may read the contracts but not edit them no longer sees "New version" (saving it was refused).
  - Someone given Organisation settings but not Billing no longer sees a Billing tab there that could not load.

## Fixed: a gap on the server (billing)

- **A team member given only "view billing" could mark an invoice as paid and change who the bill is
  addressed to.** Paying the bill belongs to the organisation admin (owner rule O15), and it now needs the
  "edit billing" permission. An organisation admin holds that by role, and no team member can be given it.
  - A team member with "view billing" still reads the invoices and the bill-to details, but cannot use
    "We have paid" or save the bill-to.
  - The organisation admin is unchanged: both still work.
  - The super is unchanged: still cannot declare a payment for a customer, and can still edit the bill-to.
  - The screens follow: the "We have paid" form and the bill-to Save show only to someone the server allows.

## Not changed

- No migration and no environment variable. Payments and contracts permissions on the server are untouched;
  the organisation admin still sees Payments as before (this moves with M4).
- The Programme overview still shows by role (debt TD-621).

## Deploy

Services: both (api and web). No migrate step. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

1. As an organisation admin: the menu shows the same items as yesterday, and Payments, Billing and Spending open.
2. As an organisation admin: on Billing, an unpaid sent invoice still offers "We have paid"; on Organisation →
   Settings → Billing, the bill-to still saves.
3. As a reviewer: the menu shows Applications and the usual items, and no Billing, Team or Settings.
4. As an admin given the Billing permission by hand: Billing appears in the menu and opens, the invoices show,
   and there is no "We have paid" form.
