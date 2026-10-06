# Retrospective — the Now-tier sweep (2026-09-30)

**Scope (owner's "go"):** eight small money, identity and eligibility items from the Now tier of
the debt register — TD-203, TD-252 (cron half), TD-248, TD-315, TD-292, TD-217, TD-167, TD-153 (b).
Built by one agent; an adversarial reviewer who did not build it reads the diff before the lead
commits, pushes or deploys anything.

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-203 | `AUDIT award_amount_set … via=override/verdict/reject/cancel` at every writer, only on a change | `test_award_amount_audit.py` (10) |
| TD-252 | `lapse_expired_offers` command + `CronRunView.JOBS['lapse-expired-offers']`; refusals INFO + one summary WARNING | `test_lapse_expired_offers_cron.py` (6) |
| TD-248 | `timezone.localdate()` for the billing-rate default | `test_billing_rate_default_date.py` (3) |
| TD-315 | explicit tag overridden only on a full-name match | `test_tag_override_full_name.py` (8, two through the POST view) |
| TD-292 | `SNAPSHOT_ORDER = ('-uploaded_at', '-id')`, one home; migration 0162; engine 2026-09-30.1; web pick | `test_document_order.py` (8) + web drift/tie tests |
| TD-217 | clip-tolerant `MLAH\s+MATA\s+PELAJARAN` anchor | `test_clipped_subject_total.py` (7) |
| TD-167 | exact sponsor-visible field sets pinned | `test_sponsor_visible_fields.py` (5) |
| TD-153 b | role gates on sponsorships / graduation queue / verdict metrics | `test_oversight_list_role_gates.py` (5, every role) |

No student- or officer-facing copy changed. No stored data changed. Nothing touches production.

## What bit (22 mutations red, 3 comment-only changes green)

Every guard was bitten by mutating one unique needle, running the guarding tests and restoring
from a byte backup (SHA-256 equal every time). Each of the four TD-203 log lines turned its own
test red; logging an unchanged override turned the "no line" test red. For TD-315 both directions
bite: a partial overriding again turns the brother tests red, and a full match refused turns the
#80/#112 tests red, including the pre-existing `test_post_consent_tag_corrected_when_name_contradicts`.
For TD-292, dropping `-id` from the constant, from `Meta.ordering`, or from one explicit site each
goes red, and so does the web drift test reading the server's source.

## What surprised

- **None of the three TD-153 lists has a page calling it.** The brief's rule (the gate is the union
  of roles on the pages that call the endpoint) gives an empty set, which would silently break the
  hidden AI Reliability card for reviewers and QC if it is ever re-enabled (it swallows errors).
  Each set is anchored instead to the code serving or feeding the same data; decisions.md has the table.
- **An existing test encoded the over-broad gate.** `test_sponsorship.test_oversight_sees_both_sides`
  read the sponsorships list as a REVIEWER. It now reads it as the admin role.
- **The TD-203 cancel test emptied a ledger entry.** Driving `cancel-decline/` through HTTP made
  `test_endpoint_exercise.test_the_list_only_shrinks` demand its removal: TD-257's list is 21 now.
- **pytest collected a borrowed TestCase twice.** Binding `TestParseSpmSlip` to a module-level name
  in the new TD-217 file collected its 16 tests again under that name. The fixtures are now bound as
  plain lists.
- **The `VERDICT_ENGINE_VERSION` history had one line of room.** The TD-285 entry was shortened
  to one line so the TD-292 entry fits without growing `verdict_engine.py`.

## What the adversarial review found (2026-10-01), and what changed

- **F1+F2 (TD-315): the full-name rule was both too loose and too strict.** Word sets ignore order
  and drop A/L, so a son named after his grandfather (`ARUN A/L RAJU` vs father `Raju A/L Arun`)
  was still a full match and still re-filed; and a bare roster name (`Raju`) lost the #80/#112
  correction outright. The rule is now NRIC-first (a readable NRIC equal to exactly one member's
  IC on file), with the name only when no NRIC reads — full match plus the given name in order.
  Nine tests, including the probe's grandfather case; bitten both ways.
- **F3 (TD-203):** the override logged before `save()`; it now logs after, and a failing save
  logs nothing.
- **F4 (TD-252):** the lapse re-reads each row under `select_for_update()` and lapses only a row
  still 'offered' with the same deadline, so an acceptance mid-sweep wins; each lapse logs its
  sponsorship and application ids, and the command prints the lapsed ids.
- **F5 (TD-292):** the version bump is pinned; the web's `latestDocFor` and `clusterAnchorKey`
  break ties on the greater id; the source scan now also catches `.latest(`/`.earliest(`,
  `Max(`/`max(` and sort keys on `uploaded_at` (one timestamp aggregate allowed, with its reason).

The lesson the review teaches is the one already on file ("test the defect's neighbouring states"):
every TD-315 fixture used names whose word ORDER happened to agree.

## Date rot, a second sighting (2026-10-01)

Two tests in `test_reviewer_query_s2.py` went red on 2026-10-01 with nothing changed: they carried
a literal 'June 2026' payslip, `sync_check2_queries` reads the real clock, and at the month turn
the slip crossed the ~3-month staleness line. The lead fixed it with a this-month `CURRENT_PERIOD`
constant. TD-175 had been closed the day before as "no second sighting" — this is the second.
Recorded in the date-rot lesson in `lessons.md`, not as a new lesson.

## Not done, on purpose

- The Cloud Scheduler job for `lapse-expired-offers` (a production step, owner's yes).
- TD-252's console WITHDRAWAL half (waits on TD-198, an owner ruling).
- Other UTC-calendar reads found outside `billing.py` are reported, not fixed (see the sweep report):
  `date.today()` in `courses/profile_claim.py:186`, `fx.py:65`, `income_engine/bill_followups.py:81`,
  `freshness.py:48`, `occupation.py:64`, `utilities.py:241`, `services/consent.py:76`.
