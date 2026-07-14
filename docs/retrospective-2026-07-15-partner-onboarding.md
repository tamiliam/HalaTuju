# Retrospective — Partner onboarding: durable invite + Google-skip + 7-day expiry, 2026-07-14

The durable-invite feature (create the Supabase account + email a temp password, replacing the
24h-expiring invite link) was built on the remote station and had sat unmerged. This close covers
landing it plus two owner refinements, merged + deployed as one unit (build `4b79d13`). No migration.

## What Was Built

- **Durable invite** — `AdminInviteView` creates the account itself + our own token-less welcome email;
  `AdminResendView` rotates + re-sends at any time; first login forces a password change; failed sends
  are surfaced, not swallowed. Plus the sponsor fix: an award withdrawal returns the student to the pool.
- **Google emails skip the password** — `gmail`/`googlemail` → no Supabase account, no password, a "sign
  in with Google" email (`PartnerAdmin` row links by verified email on first sign-in).
- **7-day temp-password expiry** — a `temp_password_issued_at` stamp + a login gate + the daily
  `expire_temp_passwords` cron that rotates a stale unchanged temp password dead. `PARTNER_TEMP_PASSWORD_TTL_DAYS`
  (default 7). Recovery = Resend (fresh password + fresh clock).

## What Went Well

- **A pressured design held up under questioning.** The owner probed the design three times before any
  code (Google-vs-all, the Workspace-domain edge, "does the temp password expire?") — each answer was
  grounded in the actual code and Supabase mechanics, not memory, and the "no drawback to a Google user
  holding an unused password" analysis is what let us keep option 1 simple (no allowlist).
- **The expiry was built as a real boundary, not theatre.** The instinct "a frontend expired-message is
  enough" was rejected because it's bypassable; the cron actually invalidates the credential in Supabase.
  Belt-and-suspenders (gate for UX + cron for the boundary), matching the project's defence-in-depth habit.
- **Everything green before deploy, and the cron proven on prod** (checked 15, expired 0) before handing
  over — so the only unverified surface is the human click-through.

## What Went Wrong

1. **The git commit message was mangled twice by the shell.** Symptom: `git commit -m "... \`must_change_password\` ..."`
   printed `command not found` and dropped words, needing an amend both times.
   **Root cause:** a `-m` message containing backticks (or `$()`) is run through Bash command substitution
   before git sees it — the backticked tokens are executed and replaced with their (empty) output.
   **Prevention:** for any commit/PR message containing backticks, `$(...)`, or other shell metacharacters,
   write it to a file and use `git commit -F <file>` (or a quoted heredoc) — never inline `-m`. Captured as
   a workspace feedback memory so it stops recurring across projects.

2. **Shipped auth code that has never been exercised against real Supabase.** Symptom: the invite/resend/
   Google/expiry flow is unit-tested (Supabase mocked) but the real round-trip is unproven.
   **Root cause:** the remote station's Python was too old to run the suite, and no environment here can
   drive the admin UI or receive the invite email — the live check is inherently human.
   **What prevents a bad surprise:** existing partner accounts are untouched (no `temp_password_issued_at`
   → the login gate and cron both skip them), the cron was dormant until the Scheduler job + was smoke-
   tested, and the flow is behind no destructive change. The live click-through is booked as the owner's
   post-deploy step; anything it surfaces is a fix-forward.

## Design Decisions

Logged to `docs/decisions.md`: Google addresses skip the temp password (gmail/googlemail only, no
Workspace allowlist); the 7-day TTL is enforced by a rotation cron because Supabase has no native TTL.

## Numbers

- **pytest:** 2431 scholarship + 1287 courses/reports/cron/admin; golden masters intact (5319/2026).
- **jest:** i18n parity green (+ `errors.tempPasswordExpired` across en/ms/ta). **+7 tests** (gmail
  no-password, the issued-at stamp, 4 expiry-cron cases).
- **Migration:** none. **Deploys:** 1 (build `4b79d13`, api + web). **Cron:** `halatuju-expire-temp-passwords`
  ENABLED (09:30 Asia/KL).

## Follow-ups
- **OWNER (blocking full sign-off):** the live invite → temp-password login → set-password; Resend;
  Google-address no-password; and (optional, via a temporary `PARTNER_TEMP_PASSWORD_TTL_DAYS=0`) the
  expiry rotation.
- **TD-160** (low): a Supabase 200-without-a-parseable-body leaves `supabase_user_id` null so Resend
  won't rotate — GET-by-email to capture the UID when convenient.
