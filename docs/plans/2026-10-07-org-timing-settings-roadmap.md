# Student message timing becomes an organisation setting — roadmap

**Status:** PROPOSED 2026-10-07, awaiting the owner's approval. No code written.
**Owner direction (2026-10-07, verbatim):** *"it seems all them could be moved to the organisation
setting"* · *"I want the values to have range — min and max — for the proper functioning of the
process. And if any are dependent on another timing, this should be managed as well."* · approved the
list of timings, limits and rules below ("proceed").
**This is the platform roadmap's planned "per-org timing" sprint** (Phase 2 Sprint 7, gated to ≈21 Aug
2026 by the rule-stability clock; that gate has passed).

## Why

1. **A real defect.** The Sabah intake round shortlists students after **48 hours**; the flagship does
   it after **55 minutes**. Nobody chose 48 for Sabah. `success_delay_hours` is a column on the intake
   round, the create-a-round endpoint never sets it (`views_admin/intake_years.py:128`), so it took the
   model default of 48 (`models/programmes.py:347`). The flagship's 55 minutes was set by hand in SQL on
   2026-05-31. No screen shows or edits it.
2. **The timings are scattered over four homes.** Of the 13 scheduled student messages, 3 are timed
   per intake round, 3 per organisation, 4 by platform settings and 3 by literals in code. An
   organisation can change only 3 of them.

## The decisions this roadmap stands on (owner, 2026-10-07)

- **Every timing lives on the ORGANISATION** (Organisation → Settings → Configuration, the existing
  `org_config` registry). Not on the gift, not on the intake round. The platform value remains only as
  the default behind a blank box.
- **Every timing has a minimum and a maximum**, chosen for the process to work (table below).
- **Timings that depend on each other are checked together**, and a save that breaks a rule is refused
  with the box named (rules R1–R7 below).
- **The interview reminders stay fixed** at 1 day and 1 hour before. Their wording ("tomorrow", "in
  about an hour") and the Meta-approved WhatsApp templates state the time.
- **Undo windows have a floor above zero** (the decline holds and the award-email delay).

## The settings

Units are the ones the owner reads. `org_config` stores integers only, so the shortlist delay is held
in MINUTES (the flagship needs 55).

### New keys (13)

**Narrow ranges (owner, 2026-10-07: *"the range is too wide … closer to the default but the org is
given some flexibility"*).** Roughly half to double the default, never finer than the job that acts
on it, never past a public promise.

| # | Key | Unit | Default | Min | Max | Replaces |
|---|---|---|---|---|---|---|
| 1 | `shortlist_email_delay_minutes` | minutes | 60 | 30 | 180 | cohort `success_delay_hours` |
| 2 | `not_shortlisted_email_delay_hours` | hours | 48 | 24 | 48 | cohort `decline_delay_hours` |
| 3 | `reminder_1_days` | days | 2 | 1 | 3 | `services/reminders.py:15` literal |
| 4 | `reminder_2_days` | days | 9 | 7 | 14 | same |
| 5 | `reminder_3_days` | days | 23 | 18 | 30 | same |
| 6 | `reminder_4_days` | days | 53 | 45 | 60 | same |
| 7 | `auto_close_after_final_reminder_days` | days | 5 | 3 | 7 | `services/reminders.py:16` literal |
| 8 | `query_answer_days` | days | 5 | 3 | 7 | cohort `query_response_sla_days` |
| 9 | `query_reminder_lead_days` | days | 2 | 1 | 2 | `services/query_emails.py:141` literal |
| 10 | `decline_hold_days` | days | 7 | 3 | 10 | setting `DECLINE_COOLOFF_DAYS` |
| 11 | `qc_decline_hold_hours` | hours | 24 | 12 | 48 | setting `DECLINE_QC_COOLOFF_HOURS` |
| 12 | `award_email_delay_hours` | hours | 24 | 12 | 48 | setting `AWARD_OFFER_EMAIL_COOLOFF_HOURS` |
| 13 | `award_confirm_hold_days` | days | 2 | 1 | 3 | setting `AWARD_COOLOFF_DAYS` |

Reasons for the limits: the decision and nudge jobs run every 15 minutes, the query-email job hourly
and the reminder job once a day, so a value finer than the job's tick does nothing. The 48-hour ceiling
on both shortlisting emails keeps the public promise (`en.json` "Shortlisting — within 48 hours"). The
decline holds and the award-email delay are the windows in which a mistake can be undone before the
student is told, so they may not be zero. The flagship's 55 minutes sits inside #1.

### Existing keys whose range narrows

Student timings already on the tab:

| Key | Default | Now | New |
|---|---|---|---|
| `nudge_auto_delay_minutes` | 30 | 5–1440 | **15–60** |
| `query_email_delay_hours` | 2 | 1–168 | **1–6** |
| `interview_min_lead_hours` | 24 | 1–168 | **12–48** |
| `interview_reschedule_cutoff_hours` | 12 | 1–168 | **6–24** |
| `sign_accept_deadline_days` | 30 | 1–180 | **14–45** |

Staff timings (same principle, owner to confirm they narrow too):

| Key | Default | Now | New |
|---|---|---|---|
| `review_sla_days` | 10 | 1–60 | **7–14** |
| `review_nudge_soon_days` | 2 | 1–30 | **1–3** |
| `review_escalate_grace_days` | 4 | 1–30 | **2–7** |
| `nudge_cooldown_hours` | 24 | 1–168 | **12–48** |
| `sign_reminder_days` | 3 | 1–60 | **2–7** |

Non-timing settings on the tab (sponsor page, interview length and hours, documents) are out of scope
and keep their ranges.

⚠ Before tightening, read `organisation_configurations` on production: a stored value outside the new
range would make that organisation's whole row fail validation on its next save. Measured 2026-10-07:
the only row (BrightPath) stores `pool_funded_grace_days` and `sponsor_email_max_cards`, neither
affected.

## The rules (timings checked together)

Each rule is checked on the MERGED settings (stored values, else the platform default), never on the
changed keys alone — the pattern `_check_pairs` already uses for the interview window. A refusal names
the box the person was most likely editing.

| Rule | Check | Code | Blames |
|---|---|---|---|
| R1 | not-shortlisted (h × 60) ≥ shortlist (min) | `decline_before_shortlist` | #2 |
| R2 | each reminder ≥ the one before + 2 days | `reminders_too_close` | the later reminder |
| R3 | questions email (h) + 24 ≤ (answer days − reminder lead days) × 24 | `questions_after_reminder` | `query_email_delay_hours` |
| R4 | reminder lead < answer days | `reminder_outside_window` | #9 |
| R5 | reschedule cut-off ≤ earliest slot | `cutoff_beyond_lead` | `interview_reschedule_cutoff_hours` |
| R6 | QC hold (h) ≤ decline hold (days × 24) | `qc_hold_too_long` | #11 |
| R7 | reviewer nudge days < verdict-due days | `nudge_after_due` | `review_nudge_soon_days` |

The existing `window_inverted` rule (interview window start before end) joins the same table.

At the defaults every rule passes (R3: 2 + 24 = 26 ≤ 72). A guard test asserts that for the platform
defaults, so a default changed in an env var can never ship a combination the page would refuse.

**With the narrow ranges, only R3 and R5 can actually be broken** (R3: answer 3 days with lead 2 days
leaves 24 hours, and the questions email is at least 1 hour; R5: a 24-hour cut-off against a 12-hour
earliest slot). R1, R2, R4, R6 and R7 are always met inside these ranges. They are KEPT as guards: if a
range is ever widened, the rule is already in place, and a test asserts each rule still bites when its
inputs are placed outside the narrow ranges.

## What changes for people at deploy

- **Sabah shortlisting goes from 48 hours to the default 60 minutes.** This is the fix.
- **The flagship stays at 55 minutes** only if BrightPath's own value is set to 55 after the deploy
  (owner, on the tab — or an audited MCP update). Until then it reads 60. The flagship round is closed,
  so in practice only Sabah is affected.
- **Nothing else moves.** Every other default equals today's live value (decline hold 7 days and award
  hold 2 days are read from production's env vars today; their code defaults change from 0 to match).
- A changed timing reaches only cases from then on: each application's `decision_due_at`,
  `decline_due_at` and award release time are stamped when the event happens.

## Things the sprint must handle (found while planning)

1. **The answer window is also the reviewer-assignment floor.** `queries_sla.is_ready_for_assignment`
   lets a case be assigned once every student task is done OR `submit + answer days` has passed. So
   `query_answer_days` changes when reviewers can be given a case, not only the reminder. Say so in the
   tab's hint and the manual.
2. **Reminder 4's wording states "5 days"** (`emails/student_reminders.py:120`, `:127`, en + ms). It
   must read `auto_close_after_final_reminder_days`. At the default the bytes are unchanged, so the
   email golden must pass UNMODIFIED — ⛔ never set `UPDATE_EMAIL_GOLDEN`.
3. **The award-email release is a SQL cutoff** (`sponsorship.py:655–664`, one cutoff for every
   tenant). It needs a per-organisation window, spelled `~Q(owning_organisation_id__in=…) |
   Q(isnull=True)` for the default arm — the `pool._funded_grace_window` spelling, whose reason is
   pinned by a test.
4. **The reminder sweep has two copies of its ladder** — `services/reminders.py` and the dry-run in
   `management/commands/send_application_reminders.py:40–54`. Both must read the same per-organisation
   ladder, or the dry run reports a schedule the live run does not follow.
5. **`DECLINE_COOLOFF_DAYS` and `AWARD_COOLOFF_DAYS` default to 0 in `base.py`** while production sets
   7 and 2. The registry default must sit inside its own range, so the code defaults become 7 and 2.
   Tests that rely on 0 (an immediate decline / award email) must say so explicitly. Measure how many
   before changing anything.
6. **The cohort fields stay for now (expand-contract).** Sprint 1 stops READING
   `success_delay_hours`, `decline_delay_hours` and `query_response_sla_days`; Sprint 2 drops them.
   Read sites: `services/intake.py:204` (also reached by `rescore_pending_decisions`),
   `services/queries_sla.py:25`, `management/commands/send_query_reminders.py`, the seed command
   `seed_b40_2026_cohort.py`, and the docstrings that quote them.

## Files that are near their size limit (code-standards ledger, measured 2026-10-07)

| File | Lines | Allowed | Room | Plan |
|---|---|---|---|---|
| `apps/scholarship/sponsorship.py` | 1018 | 1019 | **1** | Swap lines in place; put the per-org award window in a new small module. If that is not enough, split first (moves only, own commit). |
| `halatuju/settings/base.py` | 617 | 631 | 14 | Two default values change; no new lines needed. |
| `apps/courses/org_config.py` | 514 | 600 (not on the ledger) | 86 | 13 new entries (~130 lines) would make a new giant file, which the standard refuses. **Split first:** move the registry and its default helpers to `org_config_registry.py` and the rules to `org_config_rules.py`, leaving `org_config.py` as the read seam. Moves only, own commit. |

Grep both `code-standards.json` files for every path before touching it (the standing rule).

## Sprints

### Sprint 1 — the timings move to the organisation (medium-high)

**Goal:** all 13 student timings are settings on the organisation's Configuration tab, with ranges and
the rules R1–R7 enforced, and every read site reads them.

**Scope (≈35 files):**
- Split `org_config.py` (moves only, own commit), then add the 13 keys, tighten the 5, and generalise
  `_ORDERED_PAIRS` into the rule table (`org_config_rules.py`).
- Wire every read site to `org_config.value(application.owning_organisation, key)`:
  `services/intake.py`, `services/queries_sla.py`, `services/query_emails.py`,
  `services/reminders.py` + its dry-run command, `services/decline.py`, `views_admin/verdict.py` (two
  sites), `sponsorship.py` (two sites, per-org SQL window for the award release).
- `base.py`: decline and award hold defaults 0 → 7 and 2.
- Reminder 4 email reads the close number (en + ms).
- Configuration endpoint (`views_admin/org_config.py`) returns any rule code with its key.
- Web: `OrganisationConfigurationTab.tsx` shows any rule refusal under the named box (today it
  special-cases `window_inverted`); new groups and labels, hints and rule messages in en/ms/ta.
- Manual: the org-admin chapter's Configuration section lists the timings and the
  assignment-floor effect of the answer window (`content/manual/role-org-admin.tsx`).
- Tests (factories for any new test file): one per rule both ways; every default in range and passing
  every rule; each read site bites (disable it → a test fails); the per-org SQL window keeps NULL-org
  rows; email goldens byte-identical.

**Acceptance:** full api suite with the deploy gate's own line (`pytest -q -n auto -p no:cacheprovider`)
and `npm run gates` green; `makemigrations --check` clean (no migration expected); bundle budget green;
a production read shows BrightPath's row unchanged; after deploy, BrightPath's shortlist value set to 55
and a Sabah test submission scheduled 60 (or 55) minutes out.

**No migration. No new table.** UI: rows on an existing registry-driven tab using the existing row
component, so no new layout — the owner may still ask for a Stitch look first.

### Sprint 2 — retire the old homes (low)

**Goal:** remove the three intake-round timing columns (and the dead `fail_email_delay_days`).

**Scope (≈8 files):** destructive migration under expand-contract (deploy first, then `DROP` via
Supabase MCP), model fields, `seed_b40_2026_cohort.py`, the tests that set them.

**Trigger:** one week after Sprint 1 is live with no timing incident.

## Out of scope

- Per-gift timing (owner ruled organisation-level).
- The interview reminders' 1-day / 1-hour offsets.
- One-time codes and PIN lifetimes (security, not process timing).
- Partner and sponsor email timing.
