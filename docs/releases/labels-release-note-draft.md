# Release-note draft — sprint LABELS, the Overview and the case holder follow the keys (2026-11-16)

**DRAFT. Branch labels, local, not pushed. The owner says yes before it goes live.**
Decisions: `docs/decisions.md` (2026-11-16, LABELS builder calls, pending architect). Debt: TD-621 and TD-622
(built), TD-632 (note).

## What changes for people

- **Nothing changes for anyone on a standard set of permissions.** Super, organisation admin, Admin, Finance, QC,
  Reviewer, and the partner, source, mentor and member logins see the same Programme Overview as before, and the
  same people can hold and be given a case. A test checks every one.
- **The Programme Overview now follows the permissions ticked for a person, not their role.**
  - The applicant boxes (funnel, needs attention, applications by week) show for someone who sees every
    application and sits in Admins.
  - The money boxes show for someone with Spending or any Payments permission.
  - The "my cases" page shows for a team member with Review; the QC page for a team member with QC.
- **What this means for people with hand-ticked permissions:**
  - An Admin invited with the starting set (no Spending or Payments ticked) no longer sees the money boxes. Tick
    Spending or a Payments permission to bring them back.
  - A Reviewer who was also given "see every application" and Spending now sees the applicant and money boxes
    above their own cases.
  - A Finance person given Review now also sees their own cases.
- **Who can hold a case now follows the permissions too:** anyone with Review, or who can see every application.
  - A Finance person given "see every application" or QC can now hold a case.
  - Staff with neither permission no longer appear in the reviewer picker. They could never be picked anyway.
  - Who may GIVE a case, and to whom (the Reviewers table only), is unchanged.

## Not changed

- No migration, no environment variable, no money path, no web change.
- Graduation thank-you messages still need approving before a sponsor sees them. That screen stays.

## Known limits

- Some web code comments still name the old role table. Comments only, no behaviour.

## Deploy

Services: api. Migration: none. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

1. As an organisation admin, open a gift's Programme Overview: the five boxes show, as before.
2. As a Reviewer, open the same gift: your own cases show, as before.
3. As a super, open a case's reviewer picker: the same reviewers are listed and can be picked, as before.
