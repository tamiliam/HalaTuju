# Retrospective — Org-admin reject of a stuck shortlisted student — 2026-07-21

## What Was Built

An org admin (or super) can now close out an applicant who stalled in the **shortlisted** stage.
At that stage a red **"Reject this student"** card takes the slot of **Assign a reviewer** — inert
there anyway, since `services.is_assignable` forbids assignment before the student completes.
Three steps: button → **mandatory** reason → in-page "Are you sure? … cannot be undone".

- **`POST .../applications/<pk>/org-reject/` (`AdminOrgRejectView`)** — super / org_admin ONLY,
  narrower than `_require_app_write` (which also admits a `qc` and the assigned reviewer).
- **`services.org_admin_reject()` + `ORG_REJECT_FROM`** — immediate and irreversible; no cool-off,
  no embargo, no Cancel banner. The decline email goes in the same call.
- **New bucket `incomplete` + `rejection_comments`** (migration **0108**) — the reason is recorded
  verbatim but stays INTERNAL; the student gets the generic warm decline (`emails.FAIL_*`).
- `officerCockpit.canOrgReject()` mirrors the server gate. +17 pytest, +4 jest.

## What Went Well

- **The investigation deleted a whole mechanism.** The brief said "email 48 hours later"; tracing
  the student write paths proved the lockout the owner actually wanted is already immediate and
  independent of any delay. Reported that, the owner dropped the delay — removing the embargo
  wiring, the Cancel window, and a latent masking bug (see below) from the sprint. See lessons.md.
- **Almost nothing was net-new.** `_record_reject`, `_send_decline_for`, the bucket→email mapping,
  the org fence and the audit stamps all already existed. The sprint added one field, one gate,
  one service function and one card.
- **Two existing guard rails did their job unprompted.** `test_org_fence.py` failed the moment the
  new endpoint appeared, forcing an explicit fence classification; and the i18n key-existence test
  would have caught a missing `reject.category.incomplete` label. Neither needed remembering.

## What Went Wrong

- Nothing broke. Two near-misses worth recording:
  - **The dropped 48h delay would have shipped a visible bug.** During an embargo,
    `ApplicationReadSerializer.get_status` masks a rejection as `'interviewed'`. That is fine for a
    QC-stage decline, but a *shortlisted* student would have been shown a stage they never reached
    while their uploads silently 403'd. The masking is hardcoded to `'interviewed'` — **it should
    mask to `pre_decline_status`, which is already snapshotted.** Logged as TD-164, parked as
    managed debt by the owner (2026-07-22).
  - **⚠️ I asserted a production flag value from the CODE DEFAULT, and this retrospective shipped
    with it.** This section originally read "the embargo has never run in production
    (`DECLINE_COOLOFF_DAYS=0`), so this path had never been exercised" — and the same false claim
    went into TD-164, CLAUDE.md, decisions.md and project memory, all concluding the bug was safe to
    defer *because* it was inert. **Live value is `DECLINE_COOLOFF_DAYS = 7`**, with two
    applications mid-embargo at the time of writing. Root cause: I read
    `os.environ.get('DECLINE_COOLOFF_DAYS', '0')` in `settings/base.py` and reported the default as
    the deployed value, never running `gcloud run services describe`. **This is the second
    occurrence in two days** — the 2026-07-21 Vircle retrospective logged the identical mistake
    (asserting `VIRCLE_SETUP_ENABLED` was off) and its lesson says "for any claim about a feature
    flag, run `gcloud run services describe` FIRST — memory rots, env is truth". Writing the lesson
    did not prevent the repeat, because the failure is *not noticing that a claim is about live
    state at all* — a code default reads like a fact. **System change:** the lessons entry now
    carries an explicit trigger (see lessons.md) — any sentence naming an env var AND a value is a
    live-state claim and must be pasted from `gcloud`/`information_schema` output, never from a
    settings default; if it cannot be verified, write "unverified" rather than a number.
  - **Reusing the `interview` decline copy would have lied to the student.** It opens *"thank you
    for **completing** your application"* — false for exactly the cohort this feature targets.
    Caught by reading the template rather than assuming the bucket was generic.

## Design Decisions

- **Immediate + irreversible, no cool-off** — the owner's call once the lockout was shown to be
  free. There is NO undo; the three-step confirm is the safety net. See decisions.md.
- **Reopened a settled decision, under its own `Revisit if:` clause** — the 2026-07-19 "no
  rejection-note field" entry anticipated this case. At `shortlisted` there is no `DecisionReopen`
  row to hang a reason on, so the field is necessary, not merely preferable. See decisions.md.

## Numbers

- **4235 pytest** (+17) + **617 jest** (+4). Migration **0108** (one added column; the two
  `AlterField`s are choices-only, no DDL). `next build` clean; `tsc` clean.
- **▶ CARRY:** Malay/Tamil `orgReject.*` + `reject.category.incomplete` are first-drafts awaiting
  owner review.
