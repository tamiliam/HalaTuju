# Release-note draft — sprint M4b, sponsor credits and the Vircle ID on Payments switches (2026-11-23)

**DRAFT. Branch access-s3-m4b, local, not pushed. The owner says yes before it goes live.**
Programme ACCESS-BY-SWITCHES S3. Owner rulings 23 Nov, Q-A to Q-D (`docs/decisions.md`).
Debt: closes TD-498, TD-561 and TD-664 (d) when live, and the wallet half of TD-503.

## What changes for people

- **Recording a sponsor's wallet credit** (and signing it first) is for an admin who has the Sponsors: edit
  switch on their own card. An organisation admin no longer records or first-signs a credit; they approve it.
- **Approving a credit** is for the organisation admin, through Organisation admin powers, or for anyone with
  the Payments: Approve switch. Nobody approves a credit they recorded or checked.
- **Checking a credit** (when a check is needed) is for an admin with the Payments switches, as before.
- **Cancelling a credit** before it is confirmed stays with Sponsors: edit.
- **The sponsor page shows only the buttons you may use.** The server now says, for each credit, whether you may
  sign it, whether it is waiting for a check first, and whether you may cancel it.
- **Correcting a student's Vircle ID** is for an admin with the Payments switches, or the organisation admin
  (a new line in Organisation admin powers: "Correct a student's Vircle ID").
- **Organisation admin powers gain two lines:** "Countersign a sponsor's wallet credit (never one they recorded
  or checked)" and "Correct a student's Vircle ID".
- **The Overview's wallet credits card** now shows for anyone who records, checks or approves credits, not only
  for the checker.
- **Sponsor terms and sponsor emails** can now be read by anyone with Sponsors: view (the server allows it).
  The page still shows these two tabs only to editors; that follows in a later change.
- **Two people signing the same credit at the same moment** can no longer both act: the second waits, and if the
  credit moved on meanwhile they see "This credit moved on while you were signing. Reload and check again."
  instead of signing a step they did not mean to.
- **Correcting a Vircle ID with the Payments switches** works on the server only for now; the case page does not
  yet offer it to them.
- **The Overview's wallet credits card** now also shows for organisation admins and for people who record
  credits; it may read 0.
- **People who may only view sponsors** read the terms and emails without the email address of the staff member
  who last changed them.

## Not changed

- No migration, no environment variable. No money moves differently: the three-signer rule, the check and the
  amounts are as before.
- The 10 sponsor credits in production are all confirmed; none is part-way through signing.

## Deploy

**HARD LINE: S3 serves only after courses/0100 has run and its post-checks read 0.**

Services: both. No migrate step of its own, but it must go live **after** sprint S2's courses 0100
(Organisation admin powers stored). Before 0100, an organisation admin could not approve a credit or correct a
Vircle ID. Publish in a release window with the owner's yes.

## Phone check (owner, after live)

From the organisation admin's seat, open a sponsor with a recorded credit and approve it; then open a scholar's
case and check that the Vircle ID correction still saves. From an admin seat with Sponsors: edit, record and
sign a credit: the Approve button is not offered on it.

## For a native reader

The Malay and Tamil lines for the two new Organisation admin powers
(`admin.permLayout.orgAdminPowers.power.credit_approve` and `.vircle_id`) and the "moved on" line
(`admin.sponsors.detail.creditError.stale`) are drafts and need a native read.
