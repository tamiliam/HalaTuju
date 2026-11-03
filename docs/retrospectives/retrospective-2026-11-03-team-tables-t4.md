# Retrospective — Team tables T4 (Emails and Terms in three sections) — 2026-11-03

Live 2026-11-03: main 7871bb39 (feat d94af772); api-01244-2rq, web-01073-jxr. Both builds passed first time. No
migration.

## What shipped
- Team → Emails in three sections: Admin emails (a read-only list of the ten emails an organisation's own people are
  sent, from one backend registry, `admin_email_catalogue.py`, served by `GET admin/admin-emails/`), Reviewer emails
  (`ReviewerEmailsCard` moved whole), Mentor emails (the Invitations card showing only the mentor letter: one
  template, two doors).
- Team → Terms in three "Soon" sections (the tab was disabled and empty before).
- Guide and FAQ updated; en/ms/ta.

## What went well
- The registry was built off the sender code, not off the approved board. That caught four wrong lines on the board
  (payment run completed, new organisation request, profile complete, contact form) and five emails the board had
  missed (verdict escalation, countersign request, signed copy, invoice, receipt).
- `test_admin_email_catalogue` sorts every non-student `send_*` into the list or `NOT_ADMIN_SENDERS`, so a new admin
  email cannot ship unlisted.
- No flaky test: jest 405/405 suites alone, both deploy builds green.

## What to improve
- The design board's "who receives it" lines were written from memory. For any screen that describes system
  behaviour (recipients, triggers), read the code before drawing the board, not only before building it.
- The builder had to ask the lead for the list's scope (HalaTuju-inbox emails in or out). Put that scope question in
  the brief next time.

## Next
T5a (catalogue v2 + aliases, no gate converted), on the owner's word. Offered and unanswered: list HalaTuju-inbox
emails separately.
