# Retrospective — Org Config Sprint C: reviewers & staff (2026-09-07)

Worktree `.worktrees/org-config-c`, branch `feat/org-config-sprint-c`. **No migration** — the
exact shape the roadmap promised: registry entries + wired read sites + rows on the existing
Organisation → Settings → Configuration tab. Roadmap
`docs/plans/2026-09-06-org-configuration-roadmap.md` (A ✔ B ✔ C ✔ · D/E/F open).

## What shipped

Five settings joined the tab under a new **Reviewers & staff** group, all in days:

| key | default | read sites |
|---|---|---|
| `review_sla_days` | 10 | `send_review_nudges` (due date), `send_interview_reminders` (verdict-due line), `services.assign_reviewer` (review-by date in the assignment email) |
| `review_nudge_soon_days` | 2 | `send_review_nudges` (the "due soon" window) |
| `review_escalate_grace_days` | 4 | `send_review_nudges` (escalation to the org's admins) |
| `temp_password_ttl_days` | 7 | `invitations.staff_ttl_days` (invitation expiry), `expire_temp_passwords` (per-admin rotate-dead cutoff), `AdminRoleView` (serves the resolved TTL the login gate reads) |
| `admin_dormant_days` | 90 | `AdminListView` (served PER ROW), read by the FE `standingOf` |

All three review clocks resolve per APPLICATION (`owning_organisation`); the staff clocks
resolve per ADMIN / per INVITATION organisation. Every read is a per-row Python read — none of
these sweeps carries its cutoff in SQL (the nudge queryset filters on assignment/verdict state
only), so no per-org SQL window was needed this sprint, unlike B's two.

## Two latent inconsistencies retired (found in the survey, fixed by the delegation)

- **`services.py`'s assignment email said the SLA default was 7; the sweep said 10.** Both were
  DEAD defaults — `settings/base.py` always defines `REVIEW_SLA_DAYS=10`, so the 7 never fired —
  but it was the drift waiting for the day someone deleted the base.py line. Same for
  `send_review_nudges`' grace default of 3 against base.py's 4. All readers now go through the
  ONE registry delegation, so a disagreement is no longer expressible.

## The sprint's new shape: a SERVED value replaces a hard-coded FE mirror (twice)

This is the pattern Sprint D's warning is about (`interviewSlots.ts`), exercised here first on
two smaller cases:

- **The login page's temp-password gate** carried `const TTL_MS = 7 * 24 * 60 * 60 * 1000` with
  a "keep in step" comment — the exact lock-step copy the roadmap forbids once a value is
  org-tunable. The role payload (already fetched BEFORE the gate runs) now carries
  `temp_password_ttl_days`, resolved for the caller's organisation; the page computes nothing.
  The check itself moved into a pure, tested helper (`invitations.tempPasswordExpired`).
- **The Invitations page's dormancy threshold** was `DORMANT_DAYS = 90` in `lib/invitations.ts`
  — and its backend twin (`invitations.dormant_days()`) had ZERO callers: the rule lived only in
  the browser. `AdminListView` now serves `dormant_days` **per staff row**, because a super's
  list spans organisations and one page-wide number would mislabel other tenants' people.
  `standingOf` reads the served value; the FE constant survives only as the fallback for a
  payload predating the field.

## What must not be "tidied"

- **`admin_dormant_days` is served PER ROW, not per page.** Collapsing it to one value on the
  list payload re-introduces the wrong-tenant mislabel for supers.
- **ONE temp-password clock, four readers** — invitation expiry, the rotate-dead cron, the
  served login gate, and the Resend reset all key on the same organisation. The invitations.py
  docstring has always warned that two clocks let the screen and the login disagree; per-org
  tuning makes that warning binding across ORGANISATIONS too.
- **`tempPasswordExpired` fails OPEN on an unreadable date** — the cron is the hard boundary;
  the FE gate exists only for the clearer message. Do not make it refuse on parse failure.
- **The sweep caches per org id** (`org_days_cache` beside the existing `org_admin_cache`) —
  the config row is stable across one run; do not "simplify" to a per-app read that N+1s, and do
  not hoist back to one module-level read that un-does the per-org resolution.

## Bite-checks (fault injected, owning test failed, original written back)

1. Sweep reads platform instead of org (`value(None, 'review_sla_days')`) → 2 tests failed.
2. `create_or_refresh` stops passing the organisation to `staff_ttl_days` → expiry test failed.
3. Expiry cron reverts to a global cutoff → cron test failed.
4. FE `standingOf` reverts to the constant → served-threshold test failed.

## Test-count / gates

pytest full `apps/` suite green (test_org_config.py 35 → **45**); jest, lint 0, tsc baseline,
i18n **4815 × 3** (+12 keys: `group.reviewers_staff` + 5 label/desc pairs), `next build` —
final numbers in the CHANGELOG entry. ms/ta strings are first drafts.

## Lessons

- **A dead getattr default is still a defect.** Three readers of one setting carried three
  defaults; all unreachable, none flagged by any test, and one (7 vs 10) would have printed a
  wrong date in a reviewer's email the day the base.py line moved. When a value gains a second
  reader, the default must live once.
- **A backend helper with zero callers can mask where a rule really lives.** `dormant_days()`
  looked like the platform home; the actual rule was a browser constant. The grep for READ SITES
  has to cover the web app, not just `apps/`.
