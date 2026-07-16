# Retrospective — Officer assignment surfaces: cockpit = list = filter (2026-07-16/17)

An owner live-review arc, all off real records. No plan file (live-review lane); no migration.
Commits `ec9279ed` / `fc43b07f` / `ea7e15ce` / `1178df13`. Ran in parallel with the Payments
P1–P3 sprint (same repo, different files; commits interleaved cleanly on main).

## What Was Built

1. **Cockpit assign dropdown honesty** (`ec9279ed`) — #66 was assigned to Suresh (as `qc`, later
   promoted `org_admin`), but the dropdown read "Unassigned": its option list was
   reviewer/super-only and a controlled `<select>` whose value matches no option silently shows
   the default. Fix: always render the current assignee; a super may pick any review-capable
   staff (matches `services.REVIEW_ROLES`); senior roles suffixed in the label.
2. **List disables a not-ready first assignment** (`fc43b07f`) — the list row gated only on the
   stage (`assignable`), never on the cockpit's first-assign readiness, so #56 (5 open queries,
   window to 18 Jul) invited an assign the server refused with `not_ready`.
   `AdminApplicationListSerializer` now ships `ready_for_assignment` (= the service gate); the
   row disables with a tooltip. +wiring test.
3. **Display copy** (`ea7e15ce`) — "Prefers TA" → "Prefers Tamil"/"English"/"Bahasa Malaysia" via
   the existing `scholarship.apply.callLang.*` keys (no new i18n); reviewer options show ✓/⚠ +
   name only.
4. **One offer rule + Past reviewers filter** (`1178df13`) — the list row dropdown mirrors the
   cockpit (super → all review-capable; non-super → own-org reviewers; current assignee always
   renders). The assignee FILTER gains `past_assignees` from assignable-admins: anyone still on
   record as an application's assignee, org-fenced, independent of is_active/role. +pytest,
   i18n `pastReviewers` ×3.
5. **Data ops (MCP, audited):** #50's duplicate live offers collapsed (genuine UniMAP PDF stays
   live; suspect WhatsApp photo → OLD/REPLACED, superseded_by=1065). RM20,000 manual donation
   credit to sponsor Bharathan Nair (donation id 4; mirrors the Chong Lee Min reference format).
6. **Investigations closing with NO change:** (a) #56/#118 offers scoring `ua_offer`/suspect are
   CORRECT — they are online announcements (pemakluman) of STPM offers whose text mentions a UKM
   campus (hence the UA-name anchor); owner policy floors an announcement at suspect. The
   `stpm`-classified population is uniformly genuine (24 × 0.867). (b) Suresh (org_admin) CAN
   QC-reopen #21 then decline; the FE deliberately offers no direct decline at Awaiting QC — the
   recorded-verdict freeze preserves the two-person trail.

## What Went Well

- **The owner's live testing found real, adjacent defects fast** — one screenshot per defect, each
  traced to a one-rule root cause; the whole arc shipped as four small, individually-tested
  commits with the push held for the owner's deploy cadence.
- **The org-fence CI guard worked as designed** — the new `ScholarshipApplication.objects` query
  in assignable-admins was written fenced (+pragma) on the first pass because the guard test made
  the requirement impossible to miss.
- **Reusing existing i18n** (`scholarship.apply.callLang.*`) delivered a trilingual copy change
  with zero new keys and zero parity risk.
- **Precedent-driven data ops** — the RM20k credit copied the prior manual-credit row shape
  exactly (units, reference format), verified before and after.

## What Went Wrong

1. **I mis-framed a correct verdict as a bug.** Symptom: I diagnosed #56/#118's `ua_offer`/suspect
   reads as a "misclassification class" and proposed a classifier guard to route Tingkatan-Enam
   docs to `stpm`. Root cause: I treated `doc_seen` ≠ declared-pathway as an error without first
   asking what the DOCUMENT actually is — the owner knew they were online announcements, which the
   model deliberately floors at suspect (the policy is even written in `results_doc.py`'s history
   comments). The proposed "fix" would have promoted announcements to genuine. Prevention: memory
   `feedback_stpm_announcement_suspect_correct` saved (check announcement-vs-letter before
   proposing scorer changes); the standing rule — read the scorer's own History comment for the
   policy before calling a verdict wrong.
2. **I answered a capability question from the API layer only.** Symptom: told the owner Suresh
   "could decline straight from Awaiting QC"; the FE deliberately never offers that (the
   decision panel freezes once a verdict is recorded). Root cause: traced the endpoint gate but
   not the UI affordance — for a "can X do Y" question the answer is the INTERSECTION of both.
   Prevention: capability answers must name both layers (server accepts / UI offers) — applied
   later the same day when the owner challenged it, and the correction confirmed the freeze is
   intentional design, not a gap.
3. **Three assignment surfaces had drifted three ways** (the defect under items 1, 2 and 4).
   Root cause: each surface re-encoded "who can be offered" independently — cockpit strict,
   list over-offering, and neither applying the readiness gate — the action-affordance twin of
   the known tally↔paint disease. Prevention: lessons.md entry (offer-set and accept-set are a
   keep-in-sync pair; derive UI option filters from the server's rule and cross-reference both
   ways in comments), which is now how all three surfaces are written.

## Design Decisions (logged in docs/decisions.md)

- **Strict delegation kept:** a non-super org_admin assigns only own-org plain reviewers; UI
  surfaces mirror the server's `bad_assignee` rule rather than the rule being loosened.
- **"Past reviewers" = current-assignee-on-record**, not `AssignmentEvent` history — a
  fully-reassigned person would filter to zero rows (a dead option).

## Numbers

- 4 commits, 13 files, ~+150/−20 net; 0 migrations; 0 deploys during the arc (owner pushed
  between turns; final commit rides the sprint-close push — api + web builds).
- Tests: full backend pytest + 573 jest green at close (combined figure in MEMORY.md registry).
  +2 backend tests (list-serializer readiness wiring; past_assignees content/exclusion).
- Data: 1 supersede (#50 doc 1046 → superseded_by 1065); 1 donation row (id 4, RM20,000,
  sponsor 5); 0 verdict re-bands.
