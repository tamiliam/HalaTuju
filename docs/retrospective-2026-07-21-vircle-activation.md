# Retrospective — 48h Vircle activation request + cockpit fixes + Vircle data ops — 2026-07-21

## What Was Built

- **48-hour Vircle activation request (LIVE).** A cron reads the `Vircle_account` relay sheet, finds
  accounts INSTALLED (eWallet ID present) but NOT yet activated (the owner's manual "Activated On"
  column blank), and emails Vircle the list + a CSV, Bcc'ing a reference mailbox and filing the CSV
  to Drive `03 Vircle/03 Activation`. New `sheets.read_sheet_values` (the first inbound sheet read) +
  `file_csv_to_folder`; `vircle.pending_activation_rows`/`activation_csv_text`;
  `emails.send_vircle_activation_email`; `vircle_activation_request` command (`--dry-run`) + cron slug.
  Behind `VIRCLE_ACTIVATION_ENABLED`. +7 tests, no migration. Cloud Scheduler
  `halatuju-vircle-activation-request` (`0 9 */2 * *` Asia/KL) created by me; flag flipped on after a
  full verification pass.
- **Invite-form focus fix.** `Section` was defined inside `AdministrationPage`, so every keystroke
  remounted the subtree and stole focus; hoisted it to module scope.
- **Own-words toggle** now alternates Show/Hide (`ownWords.hide`, en/ms/ta).
- **Vircle relay data ops (one-time):** backfilled 8 offline-onboarded students (Emailed 28/06 /
  Confirmed 29/06 / Mobile) then normalised all 8 mobiles to E.164; RM10,000 manual credit to sponsor
  Goban Arasu.

## What Went Well

- **Reused existing infra wholesale** — the SA auth + folder-path resolution, the cron registry +
  `X-Cron-Secret` pattern, the email-to-Vircle sender, and the NRIC/sheet conventions all already
  existed; the ONLY net-new primitive was an inbound sheet-row read. That kept a "new feature" to a
  small, low-risk change.
- **Verified at every layer before it could touch Vircle:** `--dry-run` against the live sheet →
  triggered the deployed cron with the flag OFF (proved the endpoint wiring while sending nothing) →
  sent a real preview email to the owner → only then flipped the flag. Nothing reached the external
  party until each layer was confirmed.

## What Went Wrong

- **Asserted a feature-flag state from stale project memory.** Symptom: I told the owner the Vircle
  setup flow was "dark" and that a direct sheet edit would persist; the owner corrected both —
  `VIRCLE_SETUP_ENABLED` was actually `1` and the relay sheet re-syncs every 15 minutes. Root cause: I
  trusted a memory note instead of checking the live env / scheduler. Fix: for any claim about a
  feature flag or a scheduled job, run `gcloud run services describe` / `gcloud scheduler jobs list`
  FIRST — memory rots, env is truth. (→ lessons.md.)
- **Backfilled a field in the wrong format.** Symptom: the 8 backfilled mobiles read `019-459 2358`
  while every student-confirmed row reads `+60…`; the owner spotted the mismatch. Root cause: I wrote
  the backfill from the raw `contact_phone` without checking how the live confirm path stores the
  value. Fix: when backfilling a field, mirror the exact normalisation the write-path uses (here the
  Action Centre runs `normalise_msisdn` → E.164). (→ lessons.md.)

## Design Decisions

- **Activation is tracked ONLY in the owner's manual "Activated On" sheet column**; the app never
  learns activation from Vircle. The 48h flow reads that column as its prune signal. See decisions.md.
- **Reference copy = Bcc a mailbox + archive the CSV to Drive** (owner's A+B), not the sender's Sent
  folder (which would need a Gmail `send` scope). See decisions.md.

## Numbers

- 4218 pytest collected (scholarship + courses + reports) + 611 jest; +7 tests. No migration.
- Feature is LIVE + dark-first (flag, then verified, then enabled). One pending account at go-live.
