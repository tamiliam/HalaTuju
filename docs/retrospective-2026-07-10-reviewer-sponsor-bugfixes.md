# Retrospective — Reviewer & sponsor live-bug batch (2026-07-10)

A reactive batch closing three issues reported from live use (two by sponsors/reviewers, one
surfaced while diagnosing). All three shipped and deployed the same day.

## What Was Built

1. **Supabase invite email fix (config only, no code/deploy).** The "Invite a Reviewer" page
   returned "Failed to send invite email". Root cause was **not** app code — the Django invite
   view correctly returned 502 after Supabase `/auth/v1/invite` returned `500 unexpected_failure`.
   Supabase Auth's SMTP log showed `535 "5.7.8 Authentication failed"`: a Brevo SMTP key had been
   rotated (old key deactivated, "Halatuju App 2" created) and Cloud Run's `EMAIL_HOST_PASSWORD`
   was updated but **Supabase Auth's own SMTP setting was left pointing at the dead key**. Fixed by
   pasting the live key (recovered from the `halatuju-api` env var) into the Supabase SMTP form. No
   orphaned user — Supabase rolls back the auth.users row on a failed invite.

2. **QC reviewer could not propose interview times** (`441ad97b`, api rev `…00717`). The assigned
   reviewer on #66 (Suresh, role `qc`) hit "Could not save" on **Propose times** for every time he
   picked. `scheduling._can_review` carried a **stale copy** of the reviewer-role set
   (`'reviewer','super'`) that never learned about the `qc`/`admin` roles added in the 2026-07
   assignment-write model — so an assigned qc passed the real write gate (`_can_review_app` =
   assigned → can act) but was then rejected inside `propose_slots` with `not_reviewer` → 400. Fix:
   extract `services.REVIEW_ROLES` as the single source of truth and import it in `scheduling`;
   regression test (assigned qc can propose) + a drift-guard test asserting the two `_can_review`
   copies agree across all roles. Safe: the self-QC guard still stops a qc QC-ing its own review.

3. **Sponsor pool list stayed stale after funding** (`0f902af8`, web rev `…00616`). Reported by
   LeeMin: after sponsoring a student the student lingered on "available students" until a hard
   refresh (or overnight). `SponsorPortalProvider` fetches its data ONCE on mount and shared it
   across tabs with no `refreshPool`, so the fund handler could refresh the balance but not the
   list. Fix: expose `refreshPool` + `refreshWallet` from the context and call them after a
   successful fund. Also added the web app's **first component-test harness** (jsdom +
   @testing-library/react, per-file docblock so the global node env is untouched; `tsconfig.jest.json`
   sets `jsx: react-jsx` for ts-jest) + a regression test asserting the fund handler refreshes the list.

## What Went Well

- Each bug was diagnosed from **live logs/DB before touching code** — the invite "failure" was
  correctly attributed to Supabase SMTP config (not a code bug), avoiding a pointless code change.
- Both code fixes shipped as *systemic* fixes (shared constant + guard test; shared refresh method),
  not per-case patches.
- The email blast-radius was checked authoritatively (Cloud Logging over 5 days) rather than assumed —
  confirmed student Check-2/interview emails were unaffected (they use Django SMTP, not Supabase Auth).

## What Went Wrong

1. **A role-permission check drifted silently when the `qc` role was added.** *Symptom:* an assigned
   qc reviewer was blocked from proposing interview times. *Root cause:* `_can_review` was duplicated
   in two modules (`services` + `scheduling`); the 2026-07 QC-role work updated `services` but missed
   the `scheduling` copy, and nothing tied them together. *Fix:* one shared `services.REVIEW_ROLES` +
   a drift-guard test that fails if the two `_can_review` copies ever disagree. Lesson added.

2. **A shared "fetch once" client cache had no refresh path for an action that mutates it.** *Symptom:*
   funded student lingered on the available list. *Root cause:* `SponsorPortalProvider` deliberately
   fetches once for tab-switch speed but only exposed `refreshReferrals` — a later mutating action
   (fund) had no way to invalidate the pool/wallet it changes. *Fix:* expose `refreshPool`/`refreshWallet`;
   general lesson: a fetch-once shared store needs a refresh hook for every action that mutates it.

3. **A whole class of UI-refresh bug was untestable — the web suite had no component harness.** *Symptom:*
   this stale-list bug could not have been caught by any test. *Root cause:* the web jest suite ran
   node-only with no testing-library and zero `.test.tsx` (longstanding gap, TD-065). *Fix:* added the
   jsdom + Testing Library harness (isolated per-file so existing tests are untouched); TD-065 unblocked.

## Design Decisions

- **One shared `REVIEW_ROLES` instead of two hand-kept tuples** — see decisions.md.
- **Per-file jsdom docblock (not a global env switch) for the new component harness** — see decisions.md.

## Numbers

- Commits: `441ad97b` (api, QC fix), `0f902af8` (web, sponsor fix + harness). Invite fix was config-only.
- Deploys: `halatuju-api-00717`, `halatuju-web-00616` (one build each; web-only fix did not rebuild api).
- Tests: 2327 scholarship pytest (green) + **490 jest** (+1 new component regression test).
- No migration.
