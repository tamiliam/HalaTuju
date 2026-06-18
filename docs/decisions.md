# Architectural Decisions — HalaTuju

## PISMP picker: aliran on the eligibility payload, browse replaces type-search — Sprint 2 (PISMP), 2026-06-19
**Decision:** The PISMP Aliran→Bidang picker consumes an `aliran` field added to the eligible-courses payload
(backend-derived via `pismp_taxonomy.aliran_of`), and the school-type→subject browse **replaces** the type-a-course-name
box for PISMP (other programme pathways keep the plain `ProgrammePicker`). The subject step reuses that same compact
`ProgrammePicker` combobox; the only new component is `AliranPicker` (school-type chips, eligible-only).
**Alternatives considered:** (a) re-derive aliran in TypeScript from `course_id`/name suffix (no backend change); (b)
show the browse alongside the type-search box; (c) a bespoke vertical bidang list (the first cut).
**Rationale:** (a) would duplicate the suffix + id-digit + MBPK-edge-case logic that already lives authoritatively in
`pismp_taxonomy` — drift risk; exposing one field keeps the frontend a pure consumer. Replacing (not augmenting) the box
is strictly easier for the student and avoids two code paths. Reusing `ProgrammePicker` matches every other pathway's
UX and deletes the custom list.
**Trade-offs:** a serializer field means a backend deploy alongside the web deploy (a small full-stack sprint). Aliran
chips are eligible-only, so a student never sees a school type they can't enter (no "browse-all" discovery of SKPK etc.).
**Revisit if:** we want students to *explore* aliran they're not yet eligible for (then show all + a "not eligible"
state), or if eligibility ever needs the aliran server-side (then it earns more than a display field).

## PISMP aliran derived read-time; laluan to earn a column — Sprint 1 (PISMP), 2026-06-18
**Decision:** PISMP **aliran** (SK/SJKC/SJKT/SKPK) is derived at read-time by `apps/courses/pismp_taxonomy.py` from the
course-name suffix / `course_id` 6th char — **no DB column**. **Laluan** (admission route: Perdana/MBPK/STPM), which
*gates eligibility*, is specced to earn a real `pismp_laluan` column in the deferred STPM sprint.
**Alternatives considered:** a column for aliran too; parsing `course_id` inside the eligibility hot path for laluan.
**Rationale:** aliran only drives display + an Explore filter, so a pure derivation keeps the schema clean and needs no
migration; laluan changes *who is eligible*, so it must be auditable + queryable in the `requirements_df` rather than
re-parsed on every eligibility check.
**Trade-offs:** the derivation parser must stay in sync with naming conventions; two different mechanisms (derived
aliran vs column laluan) for two facets of the same hierarchy.
**Revisit if:** aliran ever starts gating eligibility (then it earns a column too), or naming conventions drift enough
that read-time derivation becomes unreliable.

## MBPK eligibility gated on the existing "Physical disability" signal — Sprint 1 (PISMP), 2026-06-18
**Decision:** MBPK (special-needs) PISMP courses are recommended only to students who ticked **"Physical disability"** at
onboarding, via a new `req_disability` must-HAVE flag (the inverse of the existing `no_disability` exclusion) — rather
than a browse-only badge or a new typed special-needs field.
**Alternatives considered:** (a) browse-only MBPK with a "you must be a registered MBPK student" note (no eligibility
gate); (b) add a typed Special-Needs field (learning/hearing/visual/physical) and gate on the union.
**Rationale:** reuses data the student already provides; gives MBPK a real eligibility match (the owner's insight) with
zero new onboarding friction; ships now.
**Trade-offs:** a known **partial proxy** — "Physical disability" misses non-physical MBPK (learning/hearing/visual, the
old B/D/L categories), so some eligible students won't be matched. Logged as TD-128.
**Revisit if:** MBPK matching proves too narrow in practice — then broaden the Special-Needs field into typed categories
(TD-128) and gate on the union.

## Reversing a recorded decision ("Reopen") — 2026-06-18

**Decision:** A super-only **Reopen** reverses a finalised decision by (a) **holding the profile from the sponsor pool**
(flip `SponsorProfile.anon_published` off) and (b) opening a `DecisionReopen` audit row, with `decision_reopened_at`
persisted on the application so the reopened state survives a reload. **Cancel** restores the prior published state
exactly; **re-saving** the decision (record-verdict / reject) regenerates + republishes per the new decision. A reopen
that leads to a saved change increments a per-reviewer **corrections** count, **derived from the audit log**
(`COUNT(resulted_in_change=True)`), shown only internally.

**Alternatives considered:** (1) Keep "Edit" frontend-only (no pool effect) — leaves a published profile live while a
reviewer corrects the decision behind it. (2) Auto-detect "did anything change?" on close instead of explicit
Cancel/Save buttons. (3) A bare `reopen_count` integer on the reviewer instead of an audit table. (4) Count every
reopen (model A) rather than only saved-change reopens (model B).

**Rationale:** The profile in the sponsor pool is the consequential artefact — reversing the decision must hold it, not
just unlock a form. Explicit Cancel-vs-Save is unambiguous and auditable (no guessing whether a field changed). An audit
row (not a counter) keeps the corrections metric reconstructable + carries the reason/who/when. The owner chose model B
so an exploratory reopen that's cancelled never penalises a reviewer.

**Trade-offs:** Re-saving on a real correction re-runs the Gemini refine (a billable call) — accepted, since a changed
conclusion *should* regenerate the profile. The reviewer attribution is the assigned reviewer at reopen time (not
whoever recorded the verdict) — deliberate: the reviewer owns the interview + recommendation.

**Revisit if:** corrections need to distinguish error severity, or the metric is ever surfaced outside the admin team,
or partial re-publish (without regeneration) is wanted on a trivial correction.

## Prompt versioning for AI-generated profiles — 2026-06-16

**Decision:** `profile_engine.PROMPT_VERSION` (a bumped string), stamped onto every generated `SponsorProfile`
(`prompt_version` column, migration `0058`). The backfill is version-aware: it skips drafts already on the current
version and regenerates only stale/empty-version ones. Bump the version on any meaningful prompt/input change.

**Alternatives considered:** (1) Detect stale drafts by date (generated_at < redesign date). (2) Always regenerate all
assigned drafts on every backfill run. (3) Do nothing — regenerate manually when noticed.

**Rationale:** A prompt redesign silently left a stale draft (#18) that was only caught by a side-by-side comparison.
Date heuristics are fragile (a draft made after the redesign by old code, or an app assigned later, both fool them).
A version stamped at generation is the ground truth.

**Trade-offs:** One additive column + the discipline to remember to bump the constant. The auto-generate sweep is still
idempotent (skips existing drafts), so refreshing after a bump needs the version-aware backfill to be run.

**Revisit if:** we want drafts to self-heal — schedule the version-aware backfill or trigger it on a version change.

## Academic results summarised by GROUP + ethnicity generalised — 2026-06-16

**Decision:** The profile never lists individual subjects/grades. `_grades_summary` reports the A-grade count, band mix,
and broad subject GROUPS (sciences/mathematics/languages/social sciences/humanities/the arts/technical), with unmapped
keys → "other subjects". Ethnicity is not revealed or implied: vernacular-language/literature subjects fold into generic
groups, and ethnic/cultural specifics in the student's own narrative are GENERALISED in the prompt (motivation kept,
label dropped — "her mother tongue", not "Tamil").

**Alternatives considered:** (1) Complete the per-subject label map so every subject renders by name. (2) List subjects
but strip only Tamil/Chinese. (3) Strip culturally-specific aspirations entirely from the narrative.

**Rationale (owner):** A long subject list is skipped by readers; naming a vernacular subject (or a "Tamil teacher")
signals ethnicity, which should not influence a sponsor. Grouping summarises AND hides ethnicity in one move, and makes
a raw-key leak structurally impossible. Generalising (not stripping) keeps the student's authentic motivation.

**Trade-offs:** The profile no longer names a standout single subject. The group map needs occasional extension as new
subjects appear (graceful fallback covers the gap meanwhile).

**Revisit if:** reviewers ask to see a specific standout subject, or the owner wants named subjects for non-language ones.

## Set-password page via the recovery flow — admin auth, 2026-06-16

**Decision:** A dedicated `/admin/set-password` page handles the session from an invite or password-reset email link and
calls `auth.updateUser({password})`. Both the invite `redirect_to` and the "Forgot password" reset link point there.

**Alternatives considered:** (1) Leave non-Google invitees on Google-only sign-in. (2) Set passwords manually in the
Supabase dashboard per user.

**Rationale:** Invited non-Google reviewers (e.g. a Yahoo address) had no way to set a password — the app had no
set/reset-password screen at all, so invites and resets led nowhere. The recovery flow (client-initiated PKCE) is the
robust, same-browser path; the page reuses it for both invite and reset.

**Trade-offs:** The invite-link token path is less predictable than recovery and needs a live test to confirm; the
recovery path is the dependable fallback.

**Revisit if:** the invite-link token handling proves unreliable in practice — standardise on recovery-only onboarding.

## One PII-redacted narrative profile (no separate anonymous version) — AI profile, 2026-06-15

**Decision:** A single AI student profile serves both the reviewer and (once approved) the sponsor. It is generated
twice by the system: a draft at the Check 2 → reviewer handoff (Flash) and a final at Save-verdict (Pro) that replaces
it and becomes the sponsor/pool version. It is **PII-redacted, not strictly anonymous**: alias instead of name; only
name/NRIC/photo/phone/email/street (student + guardian) are withheld — school, town, institution and occupations are
allowed. Prose is narrative (no section headers), he/she (never "they"), few em-dashes.

**Alternatives considered:** (1) The prior model — a named, headed draft for the reviewer PLUS a separately-generated,
strictly-anonymous pool profile, with manual Generate/Save/Publish/Refine buttons. (2) Keep strict anonymity (no
school/town) for the sponsor-facing version.

**Rationale (owner):** "There is only one profile common to all." One document removes drift and the manual ceremony;
the reviewer verifies identity via the documents/verdict panel, not the profile, so the profile needn't carry the name.
The owner accepts sponsors seeing school/town (it aids connection) while protecting the six contact/ID items.

**Trade-offs:** Looser than the original "permanently-anonymous pool". The shared leak scanner had to split into a
strict one (graduation-message relay) and a relaxed `scan_profile_pii` (this profile). Existing pre-redesign drafts keep
their old format until regenerated (draft at next handoff, or final at verdict).

**Revisit if:** the programme needs strict sponsor anonymity again (re-tighten `scan_profile_pii` + add an anon variant),
or PDPA guidance changes what sponsors may see.

## Income honesty: STR proves B40, not an amount; payslip/EPF is authoritative — AI profile, 2026-06-15

**Decision:** The profile must not present STR/JKM as confirming an income figure (they confirm B40 / welfare status
only). An income amount is stated authoritatively only when evidenced by a payslip/EPF on file (either income route, via
`income_engine`); otherwise it is presented as "reported" and never attributed to a specific earner the data doesn't name.

**Rationale:** A reviewer flagged a generated line ("RM750 confirmed through STR") as false — STR can't confirm a figure,
and below-minimum-wage totals shouldn't be invented into a story. **Revisit if:** the income verdict model changes what
counts as documented income.

## Funding-need estimate: single per-pathway shortfall × fixed duration (no ranges, no device, no student-duration override) — Funding estimate, 2026-06-15

**Decision:** Estimate funding need as one **monthly shortfall per pathway** (living costs − government allowance −
PTPTN), multiplied by a **fixed per-pathway duration** from an owner-validated table, rounded to RM100. No low–high
ranges, no device one-off, and the student's stated `programme_months` is **ignored** for the duration. Diploma is split
into Politeknik (`poly`) vs public-university (`university`); there is **no degree category** (post-SPM students can't
enter a bachelor's directly, except PISMP); `kkom`/`iljtm`/`ilkbs` are deliberately un-estimated.

**Alternatives considered:** (1) The previous range model with a device + registration one-off and a 12-month default.
(2) Keep the device line. (3) Honour the student's `programme_months` as a duration override. (4) One lumped `poly_diploma`
bucket for all diplomas. (5) Keep a `degree` estimate.

**Rationale:** It's an **assistance top-up**, not a full ride, paid out in small tranches — so device (a lump sum) doesn't
fit, and the realistic figure is the gap *after* the government allowance + PTPTN. Owner interviews gave standard
shortfalls + durations per pathway; the student's `programme_months` is rounded to whole years (12/24/36) and so is *less*
accurate than the known programme length (STPM is 18 months, not a "2-year" 24). Politeknik and university diplomas have
genuinely different cost/duration; degree isn't reachable post-SPM.

**Trade-offs:** Loses per-student duration nuance (all same-pathway students get the same estimate) — accepted, since it's
a ballpark for award-sizing and the officer adjusts at interview. The `variable` flag (asasi, uni-diploma) signals where
the single figure is least trustworthy.

**Revisit if:** a government allowance / PTPTN policy changes; real award data shows a pathway is consistently over/under;
or we gather figures for kkom/iljtm/ilkbs. Figures live in `docs/scholarship/funding-estimate-basis.md` (keep in sync
with `apps/scholarship/funding_estimate.py`).

## Classify a blank-pathway application from its chosen programme — Funding estimate, 2026-06-15

**Decision:** When the pathway-type fields are blank, `classify_pathway` falls back to the **chosen programme** (course_id
prefix + course_name keywords) before giving up.

**Rationale:** The offer-letter auto-fill (`autofill_pathway_from_offer`) sets `chosen_programme` for tertiary offers but
not `chosen_pathway`, so a real Politeknik-diploma student (e.g. #62) otherwise showed "Pathway not chosen yet". The
concrete programme is the strongest signal and the cockpit already displays it — the estimate must agree with it.
**Revisit if:** the auto-fill is changed to also set `chosen_pathway` (then this becomes belt-and-suspenders).

## Reviewer-assignment email rides the app's own Brevo path; Brevo is also Supabase Auth's SMTP — Notifications, 2026-06-15

**Decision:** The reviewer-assignment notification is a normal Django/Brevo `send_mail` (the app email path), separate
from Supabase Auth emails (invites/resets). Separately, Supabase Auth's custom SMTP is pointed at the **same Brevo
account + verified sender** the app already uses.

**Rationale:** Two independent email systems already exist (app transactional vs Supabase Auth); the assignment notice is
app-domain, so it belongs on the app path (its own copy, not a Supabase template). Supabase's built-in mailer is
rate-limited (~a few/hour) which blocked a 4th reviewer invite; reusing the app's verified Brevo sender clears it without a
new sender to verify. **Trade-off:** both now draw on the same Brevo free-tier quota (300/day). **Revisit if:** volume
approaches the Brevo daily cap.

## Course-data health monitoring: READ-ONLY (no catalogue writes), concurrent in-request check, weekly cron + manual button — Course Data health, 2026-06-13

**Decision:** Keep the dashboard's freshness/link-health/audit current via a **read-only** check that runs **weekly
(cron)** and **on demand (a super/admin button)**. The check = `audit_data` + `validate_course_urls` **without `--fix`**;
it parallelises the ~650 link GETs (`--workers`) so it finishes in <1 min inside a single Cloud Run request. The browser
catalogue scrapes stay manual/local and only ever dry-run.

**Alternatives considered:** (1) A Cloud Run Job for the long link-check (no request-timeout limit). (2) Sequential
in-request check (risks the ~300s timeout at 650 URLs). (3) Concurrent in-request check + weekly cron + sync button
(chosen). (4) Update-triggers from the UI (rejected — owner wants reporting only, no overwrite).

**Rationale:** Owner intent is explicit: *monitor* freshness/links, **never update/overwrite**. Read-only by
construction (no `--fix`, no `--apply`, no scrape) means no UI/cron path can mutate the catalogue. Concurrency turns the
651-URL check into a sub-minute request, so neither the cron endpoint nor the synchronous admin button needs a separate
Cloud Run Job — minimal infra. Manual trigger is gated super/admin because it issues ~650 outbound requests.

**Trade-offs:** The cron only covers the server-runnable reporters (audit + link reachability); STPM/SPM/UP_TVET
*catalogue* freshness (new/changed programmes) still updates only when the owner runs the browser scrapes locally (dry-run).
A ~650-URL synchronous button is ~30–60s (acceptable with a spinner).

**Revisit if:** the catalogue URL set grows ~10× (move the check to a Cloud Run Job), or the owner later wants UI-driven
*updating* (the deferred Dashboard "Sprint B" triggers — explicitly out of scope here).


## UP_TVET coverage: scrape + inventory FIRST (no DB writes); ingest deferred; coverage matched by institution name — UP_TVET Sprint 1, 2026-06-13

**Decision:** The first UP_TVET sprint builds only the scraper (`scrape_uptvet`) + a no-write coverage
inventory (`audit_uptvet`). It does NOT ingest programmes into the DB. Coverage (new-vs-already-held) is
reported by **institution name overlap**, explicitly as an **upper bound**, not by course code.

**Alternatives considered:** (1) Scrape + ingest the Awam programmes into the `tvet` bucket this sprint.
(2) Scrape + inventory first, ingest as a separate sprint (chosen). (3) Read-only inventory with no reusable
scraper.

**Rationale:** The live spike showed UP_TVET is a **~1000-programme acquisition** (not a refresh): codes
(`TVET/QP…`, `SLW…`) don't match our synthetic `IJTM-*`/`IKBN-*` IDs, requirements sit behind Semak-Kelayakan
detail pages, and the catalogue mixes Awam/Swasta. Ingesting adds new `CourseRequirement` rows that feed the
**golden-master** eligibility DataFrame — doing that without first knowing the real Awam/Swasta split + the
per-institution gap would be reckless. The inventory produces exactly those numbers to scope the ingest +
settle the Swasta question on evidence. Institution-name matching is fuzzy because the portal uses full names
("INSTITUT KEMAHIRAN BELIA NEGARA …") while our DB uses abbreviations ("IKBN …"), so the inventory surfaces the
institution list for human judgement rather than asserting a clean diff (same family as the SPM `course_id`
mismatch).

**Trade-offs:** No coverage improvement ships this sprint (the inventory is decision-data, not new courses);
the precise new-vs-existing count needs a name-reconciliation step the ingest sprint must do anyway.

**Revisit if:** the ingest sprint is scoped — then decide Awam-only vs include Swasta from the inventory
numbers, pick the course_id scheme (likely the portal `id_kursus`), and a TVET requirements strategy
(parse Semak-Kelayakan pages vs a conservative TVET default).

## SPM catalogue sync is restricted to the MOHE-coded (UA/Asasi) subset; synthetic-ID crosswalk deferred — Sprint 3, 2026-06-13

**Decision:** `sync_spm_mohe` compares the e-Panduan `jenprog=spm` scrape against the `courses` catalogue **only for
courses whose `course_id` is a MOHE/UPU KOD PROGRAM** (`^[A-Z]{2}[0-9]{7}$` — the ~89 `U*` UA/Asasi programmes). The
other ~300 courses use internal synthetic IDs (`POLY-*`, `KKOM-*`, `IKBN-*`/`ILP-*`, numeric `50PD…` PISMP) that
e-Panduan never emits, so they are excluded from the diff entirely — never matched, never deactivated. A new
`Course.is_active` (migration `0054`) is populated by the sync, but **no read path filters on it yet**.

**Alternatives considered:** (1) Diff the whole catalogue against the scrape — would flag ~300 synthetic-ID courses as
"removed" and trip the mass-deactivation guard (or, forced, wipe most of the catalogue). (2) Build a MOHE-code ↔
synthetic-ID crosswalk by name+institution now, so all 390 sync. (3) Restrict to the MOHE-coded subset, defer the
crosswalk (chosen).

**Rationale:** The 89 UA/Asasi courses sync cleanly and safely today (real value: their merit moves yearly). The
crosswalk is genuinely separate work with real risk — name-based matching across two ID schemes can false-merge into the
golden-master eligibility data (cf. lessons #19, #88). Shipping the safe 80%-effort/clean part now beats blocking on the
risky long tail. Mirrors how STPM was done (sync the matchable; parse requirements / add new courses as separate tooling).

**Trade-offs:** Poly/KK/TVET/PISMP courses get no automated refresh until the crosswalk (3b) lands; new MOHE-coded
courses are reported but not auto-added (requirements parsing = 3c). Adding `is_active` without a read filter means
deactivated SPM courses still render until a later sprint wires the filter — accepted to keep the golden master provably
untouched this sprint.

**Revisit if:** the Poly/KK merit/links go materially stale (build 3b), or new UA/Asasi programmes appear often enough
to want auto-add with parsed requirements (build 3c), or a sponsor/advisory view needs inactive SPM courses hidden
(wire the `is_active` read filter, mirroring `StpmCourse`).
## Course Data dashboard: reporting-only first (no run-triggers); coverage live, freshness recorded — Course Data Dashboard Sprint 1, 2026-06-13

**Decision:** The first `/admin/course-data` dashboard is **read-only reporting**: per-source freshness, coverage
(have/available/gap), link-health, audit. NO buttons that run a scrape/sync/audit. Coverage is computed **live** from
the DB; freshness/link-health/audit come from a small `CourseDataStatus` store the tools write to when they run.

**Alternatives considered:** (1) Full hybrid (reporting + server-run triggers) now. (2) Reporting-only first, triggers
later (chosen). (3) Compute everything live with no status store (then no freshness/history possible).

**Rationale:** The owner's directive is *"build the tools, then a dashboard that shows status for decisions — no
harvesting now."* Reporting-only honours that literally (no UI path can harvest) and is the smaller, safer build.
Coverage counts don't need persistence; freshness does (a recorded `last_run_at`), so a tiny status model is the
minimum that makes the dashboard truthful. The empty/"never run" state is first-class and itself decision-useful.

**Trade-offs:** Until a tool is actually run, its card reads "never refreshed" — expected under "no harvesting now".
The SPM + UP_TVET tools (on separate branches) aren't instrumented yet, so those two read "never" until those branches
merge and call `record_status`.

**Revisit if:** the owner wants the hybrid update-triggers (server-runnable Run-audit / Check-links / Apply-refresh
buttons) — a later sprint; the scrape itself stays local (browser), so a trigger would upload a CSV, not scrape server-side.


## Operational reminders stay email/Cloud-Scheduler — no in-app notification system yet — 2026-06-12

**Decision:** Admin/operational reminders (refresh the catalogue, backup status, link-rot, anomaly alerts)
are delivered by **email via Cloud Scheduler** (mirroring the live `vision-outage` pattern), **not** a
purpose-built in-app notification centre. User-facing notifications already have homes (student Action
Centre, sponsor digests); this decision is only about the *operational/admin* class.

**Alternatives considered:** (1) Build an in-app notification/reminder centre now (model + scheduler→DB
writes + admin UI + read/ack/snooze state + ×3 i18n). (2) Email + Cloud Scheduler (chosen).

**Rationale:** At ~2–3 recurring operational reminders and a single admin operator, a notification
framework is premature infrastructure — email already does this at zero maintenance, and a centre is just
one more place to check. Building it now would burn multi-sprint effort to replace what email does free.

**Revisit when** any of: **~5+ recurring operational reminders** accrue, OR **more than one admin** needs to
act on them, OR we need reminder **state** (snooze/acknowledge/assign). The cheapest first step at that
point is a **"system freshness" strip on the admin dashboard** (e.g. "STPM catalogue last refreshed N
months ago · UPU refresh due Dec", derived from the dated archive + job timestamps) — a full notification
system only if that proves insufficient.

## B40 applications snapshot the chosen course; the catalogue is deactivated, never hard-deleted — Course-data robustness, 2026-06-12

**Decision:** Two linked rules that keep the course catalogue and B40 applications decoupled:
1. A B40 application captures the student's pathway/course choice as **point-in-time snapshots** — denormalised
   strings + JSON (`intended_pathway`, `chosen_pathway`, `chosen_field`, `pre_u_institution`,
   `chosen_programme = {course_id, course_name, institution, source}`, `top_choices = [{course_id, course_name,
   institution}]`). There is **no foreign key** from `ScholarshipApplication` to `Course`/`StpmCourse`, and no B40
   view re-reads the live catalogue by the stored `course_id` (only the merit *calculator*, on the student's grades).
2. Catalogue courses are **deactivated** (`is_active=False`), **never hard-deleted**. STPM already soft-deletes via
   `sync_stpm_mohe`; the same rule applies to the SPM `Course` catalogue.

**Alternatives considered:** (1) Normalise `chosen_programme` into a real FK to the course row ("tidier"). (2) Hard-delete
courses that MOHE drops. (3) Snapshot + soft-delete (chosen).

**Rationale:** Course data is accurate only at a point in time — offerings, merit, requirements and links change yearly.
A B40 application is a *historical record* of what the student chose then, and its eligibility verdict keys off the
stored pathway + the cohort's own thresholds + the student's grades (and is ultimately anchored to the uploaded offer
letter), **not** live course data. Snapshotting means a catalogue refresh never mutates or breaks a submitted
application. Soft-delete (not hard-delete) keeps the convenience link from the officer review screen
(`chosen_programme.course_id` → `/course/<id>` or `/stpm/<id>`) alive even after a course is withdrawn — the detail
views are intentionally unfiltered by `is_active`, so a deactivated course still renders via a direct link; only a
*hard* delete would 404 it. The displayed course **name** always comes from the snapshot, so it is correct regardless.

**Trade-offs:** The officer link shows the course's *current* details, not the apply-time version (usually a feature —
the officer wants "where / how long" now). The stored `course_id` is a loose string, not referentially enforced. A
hard-deleted course would dead-link (mitigated: the detail page already degrades to a `CourseNotFound` card, never a
raw 404).

**Revisit if:** a feature genuinely needs the application to track the *live* course (then add a read-only, clearly
labelled "current status — for reference" view that never feeds the verdict — do NOT convert the snapshot to an FK), or
if apply-time course facts (duration/institution/level) must be preserved verbatim (then snapshot those 2–3 fields into
`chosen_programme` at capture, rather than relying on the live link).

## progress_state is a DERIVED card field (stub now), not a stored column — B40 Phase E/F Sprint 8, 2026-06-09

**Decision:** The sponsor-facing `progress_state` (on_track / semester_completed / needs_attention / graduated) is a
`SerializerMethodField` on the allowlist card, computed by `pool.derive_progress_state(application)` — a **stub** that
returns `null` until the student is `sponsored` and `on_track` thereafter. No DB column, no migration. The real
derivation (from the latest-semester results upload) lands in F9a (Sprint 9), at which point only the helper changes.

**Alternatives considered:** (1) Add a `progress_state` column to `ScholarshipApplication` now + a migration. (2) Derive
it live on the card (chosen).

**Rationale:** F2's job is the sponsor *view*; the data that determines real progress (semester results) doesn't exist
until F9a. A stored column now would be a second source of truth to keep in sync with the (future) results pipeline and
would ship a migration for a value we can't yet compute honestly. A derived field keeps the single source of truth in
the results data (once it exists) and means F2 is a pure read-surface — no schema, no migration, and the leak test
proves the new field carries nothing identifying. It also keeps the value off the *browse* cards (null unless
sponsored), so it never shows a misleading "progress" for a student no one funds yet.

**Trade-offs:** `derive_progress_state` is called per card render (cheap — a status check now; F9a will read the latest
results row, so add `select_related`/prefetch there). Until F9a, every sponsored student reads `on_track` regardless of
reality.

**Revisit if:** Progress needs to be queryable/filterable at the DB level (e.g. "show all needs_attention students"),
or the derivation becomes expensive enough that caching/denormalising to a column pays off.

## One super-only audited assign endpoint (assign + reassign + unassign), not two — B40 Phase E/F Sprint 7, 2026-06-09

**Decision:** Reviewer (re)assignment is a single `POST .../assign/` endpoint backed by one `services.assign_reviewer`
service. It handles first-assign, reassign, and unassign; the ready-gate (`is_ready_for_assignment`) applies **only**
to the first assignment of an unassigned app. The pre-existing loose, reviewer-gated `PATCH assigned_to` branch was
**removed** so assignment has exactly one (super-only, audited) path.

**Alternatives considered:** (1) Two endpoints `assign/` + `reassign/` as the roadmap sketched. (2) Keep the PATCH
`assigned_to` path for backward-compat alongside the new endpoint. (3) One `assign/` endpoint + one service (chosen).

**Rationale:** Two endpoints would be near-identical and share all validation/audit logic — a recurring source of
drift (cf. the FE/BE and verdict dup-path lessons). Collapsing assign/reassign/unassign into one service with the
gate keyed on "is this the first assignment" expresses the actual rule ("a super may redistribute work any time, but
can't assign before the app is ready") in one place. Removing the PATCH path closes a real gap: it let *any* reviewer
silently reassign with no audit and no role check on the target — F7 makes assignment super-only, reviewer-validated,
and traceable via `AssignmentEvent`.

**Trade-offs:** A tiny divergence from the roadmap's two-endpoint sketch (documented here). Any caller of the old PATCH
`assigned_to` had to move to the new endpoint (only the cockpit used it — migrated in the same sprint).

**Revisit if:** A non-super role legitimately needs to self-assign, or assignment needs to fire side effects (e.g. an
email to the reviewer) that warrant distinct assign vs reassign semantics.

## ReviewerProfile is a separate model in `apps/scholarship`, not fields on `courses.PartnerAdmin` — B40 Phase E/F Sprint 5, 2026-06-09

**Decision:** The reviewer's credentials + contact details (F6) live in a new `ReviewerProfile` model **in
`apps/scholarship`** with a OneToOne FK to `courses.PartnerAdmin`, fed by its own narrow serializer and a dedicated
self-scoped `GET/PATCH /api/v1/admin/reviewer-profile/` endpoint. The two new cards render on the **existing**
`/admin/profile` page, but the data comes from this new endpoint — **not** by widening the `courses` `AdminProfileView`.

**Alternatives considered:** (1) Add the six fields directly to `courses.PartnerAdmin` and extend the existing
`AdminProfileView`/`AdminProfile` serializer. (2) A `ReviewerProfile` 1:1 placed in `apps/courses` (next to
`PartnerAdmin`). (3) `ReviewerProfile` in `apps/scholarship` with a cross-app FK + its own endpoint (chosen).

**Rationale:** Two forces. **Dependency direction** — `apps/scholarship` already depends on `apps/courses` (it
imports `PartnerAdminMixin`, FKs `StudentProfile`); the reverse (courses importing a scholarship model to widen
`AdminProfileView`) would invert the layering and risk an import cycle. The reviewer concept is itself a
B40/scholarship concern (reviewer-scoping, Check-2/3 all live in scholarship), so the model belongs there. **PII
isolation** — `phone`/`address` are sensitive staff PII; keeping them in their own table with its own RLS and a narrow
serializer means they are reachable by *no* outward (student/sponsor) serializer by construction, consistent with the
structural-data-wall pattern. A separate endpoint also keeps the existing org/name `AdminProfileView` untouched.

**Trade-offs:** A second profile endpoint + a second fetch on the `/admin/profile` page (the one Save button fires two
PATCHes). A cross-app FK and a separate migration history (already the norm for this app). `get_or_create` means a row
is materialised on first GET.

**Revisit if:** A unified staff-identity model is built (then fold reviewer fields in), or `PartnerAdmin` itself moves
into a shared identity app — at which point the cross-app FK could become same-app.

## Separate STPM ranking module — STPM Sprint 3, 2026-03-13

**Decision:** Created `stpm_ranking.py` as a standalone module rather than extending the existing `ranking_engine.py`.

**Alternatives considered:** Adding STPM scoring to `ranking_engine.py` with a pathway-type switch.

**Rationale:** The SPM ranking engine handles merit tiers, credential priority, pathway scoring, and category caps — none of which apply to STPM. Merging would require branching on every scoring step, making both paths harder to test and reason about.

## CharField → BooleanField for colorblind/disability — i18n & Bug Fixes Sprint, 2026-03-19

**Decision:** Converted `StudentProfile.colorblind` and `disability` from `CharField(max_length=10, default='Tidak')` to `BooleanField(default=False)`. Removed the serializer's `Bool→"Ya"/"Tidak"` conversion layer. Engine comparisons changed from string equality to boolean logic.

**Alternatives considered:** (A) Make the serializer accept both booleans and "Ya"/"Tidak" strings, normalising to "Ya"/"Tidak" for the engine. (B) Normalise on the frontend before sending to the API.

**Rationale:** The root cause of the dashboard "Failed to load recommendations" bug was a type mismatch — `restoreProfileToLocalStorage()` stored "Ya"/"Tidak" strings from the profile API, which the eligibility serializer's `BooleanField` rejected as invalid. Option A would have papered over the inconsistency. The canonical fix eliminates the entire string-boolean conversion layer.

**Trade-offs:** Required updating ~50 test data entries and 8 source files. Migration converts existing Supabase data in-place.

**Revisit if:** Never — booleans are the correct type for binary flags.

**Trade-offs:** Two ranking modules to maintain. Some scoring concepts (CGPA margin, field match) are duplicated at the constant level but with different values.

**Revisit if:** A unified ranking API is needed that handles both SPM and STPM in a single call, or if a third pathway (e.g. UEC) is added and a shared abstraction becomes worthwhile.

## Legacy grade aliases in GRADE_ORDER — STPM Sprint 5, 2026-03-13

**Decision:** Keep E and G as legacy aliases at the end of `STPM_GRADE_ORDER` in `stpm_engine.py`, even though the real STPM scale uses D+ and D instead.

**Alternatives considered:** (1) Remove E/G entirely and migrate parsed CSV data to use D/F. (2) Map E→D and G→F at CSV parse time.

**Rationale:** The parsed CSV requirement data (`stpm_subject_group` JSON fields) contains `min_grade: 'E'` in many records. Removing E from GRADE_ORDER causes `meets_stpm_grade()` to raise ValueError, breaking 48 programmes. Migrating the source data is risky and the CSVs are externally maintained.

**Trade-offs:** GRADE_ORDER has 13 entries instead of 11. The user-facing grade dropdown (`STPM_GRADES` in `subjects.ts`) correctly excludes E/G. There's a semantic gap between what users see and what the engine accepts.

**Revisit if:** The STPM CSV data is re-parsed with corrected grade codes, or if a data migration script is built to normalise all `min_grade` values.

## Merit traffic light thresholds — STPM Sprint 6, 2026-03-13

**Decision:** Student merit (CGPA/4.0 × 100) vs course merit: ≥ course = High, within 5% below = Fair, >5% below = Low.

**Alternatives considered:** (1) Tertile-based (top/mid/bottom third of merit range). (2) Fixed thresholds (≥90 High, ≥75 Fair, else Low). (3) No threshold — show raw percentage only.

**Rationale:** Comparing student merit directly against course merit gives personalised, actionable feedback. The 5% "fair" zone represents a realistic improvement margin. Fixed thresholds ignore per-course competitiveness.

**Trade-offs:** The 5% threshold is somewhat arbitrary. Very competitive courses (merit 100%) will show nearly everyone as "Low". But this is honest — students should know.

**Revisit if:** User testing reveals the 5% zone is too narrow or too wide, or if UPU publishes official competitiveness bands.

## Koko 0–10 scale with 4% CGPA weight — STPM Sprint 6, 2026-03-13

**Decision:** Koko score input accepts 0–10, formula: `(academicCgpa × 0.9) + (kokoScore × 0.04)`.

**Alternatives considered:** (1) Koko as 0–4 with 10% weight (previous implementation). (2) Koko as 0–100 percentage.

**Rationale:** The actual STPM system grades co-curriculum on a 0–10 scale. Previous implementation used 0–4 which was incorrect. 10 × 0.04 = 0.40 max, matching the known max CGPA of 4.00 (3.60 academic + 0.40 koko).

**Trade-offs:** None significant. This corrects a factual error.

**Revisit if:** The STPM grading system changes its koko weight or scale.

## Unified search endpoint for SPM + STPM — STPM Sprint 7, 2026-03-13

**Decision:** Extended the existing `CourseSearchView` to query both `Course` (SPM) and `StpmCourse` (STPM) tables with a `?qualification=SPM|STPM` filter, rather than maintaining separate endpoints.

**Alternatives considered:** (1) Keep `/api/v1/courses/search/` and `/api/v1/stpm/search/` as separate endpoints, with frontend merging results client-side. (2) Create a unified `UnifiedCourse` model/view that duplicates data.

**Rationale:** Single endpoint means one fetch, one set of filters, one pagination mechanism. STPM results are mapped to the same `CourseCard` shape at the view level, so the frontend doesn't need to handle two different response formats. Smart filter skipping (e.g. state filter skips STPM since STPM courses don't have state data) keeps results sensible.

**Trade-offs:** The view is more complex (~200 lines) with conditional query building. STPM courses lack some SPM fields (state, pathway_type), so some filters silently skip one qualification. If a third qualification is added (e.g. UEC), the view will need refactoring.

**Revisit if:** A third qualification pathway is added, or if the unified view becomes too complex to maintain.

## Map STPM → EligibleCourse client-side — STPM Sprint 8, 2026-03-13

**Decision:** Map `StpmRankedProgramme` to `EligibleCourse` type in the dashboard component, reusing the existing `CourseCard` component without modifications.

**Alternatives considered:** (1) Create a new `StpmCourseCard` component with STPM-specific fields. (2) Extend `CourseCard` to accept a union type of SPM and STPM data.

**Rationale:** The existing `CourseCard` already handles images (via field), badges (via source_type/level), merit bars (via merit_cutoff/student_merit), and bookmarks. STPM data maps cleanly to these fields. Zero changes to CourseCard means zero risk of breaking SPM rendering.

**Trade-offs:** Some STPM-specific data (university name, CGPA) is lost in the mapping or displayed as generic fields. The mapping logic lives in the dashboard component rather than a shared utility.

**Revisit if:** STPM cards need to show data that doesn't fit the EligibleCourse shape (e.g. CGPA requirements, MUET band).

## merit_type field for pre-U merit branching — Pre-U Sprint, 2026-03-13

**Decision:** Added `merit_type` CharField on `CourseRequirement` with three choices (`standard`, `matric`, `stpm_mata_gred`). Views.py branches merit calculation by this field, calling `pathways.py` formulas for matric/stpm.

**Alternatives considered:** (1) Modify `engine.py` to handle merit calculation internally. (2) Add a separate `PreUMeritCalculator` class. (3) Keep synthetic entries and add merit to them.

**Rationale:** `engine.py` is the golden master and must not be modified. `pathways.py` already has the correct formulas with 32 tests. A simple field + if/elif in views.py is the minimal change. Pre-U courses go through the same eligibility loop as all other courses — engine checks basic requirements, then views.py applies the track-specific formula as a second pass.

**Trade-offs:** Views.py gains ~50 lines of merit branching. The second-pass eligibility check (engine says eligible, then pathways says not eligible → skip) is slightly unintuitive. But it avoids touching the golden master.

**Revisit if:** A fourth merit formula is needed, or if engine.py is refactored to support pluggable merit calculators.

## Frontend JSON over DB for pre-U institution rendering — UI Polish Sprint, 2026-03-14

**Decision:** STPM and matric course detail pages use the frontend JSON data files (`stpm-schools.json`, `matric-colleges.ts`) to render institution cards, bypassing the DB Institution records.

**Alternatives considered:** (1) Enrich the DB Institution records with PPD, subjects, phone fields. (2) Have the API merge DB and frontend data. (3) Redirect pre-U course detail pages to the pathway pages.

**Rationale:** The frontend JSON has rich data (584 STPM schools with PPD, subjects, phone; 15 matric colleges with tracks, phone, website) that the DB records lack. Adding these fields to the DB would require schema changes, data migration, and ongoing sync with the source data. The frontend data is the authoritative source for this information.

**Trade-offs:** Two data paths for institution rendering: DB for regular courses, frontend JSON for pre-U. If pre-U institution data changes, both the JSON files and DB need updating. The course detail page has more code to handle the branching.

**Revisit if:** The Institution model gains PPD/subjects fields as part of a broader data enrichment effort, or if a unified institution data source is built.

## Real column rename over db_column workaround — Data Integrity Sprint, 2026-03-14

**Decision:** Renamed actual Supabase columns (`program_id` → `course_id`, `program_name` → `course_name`) and removed Django `db_column` parameters, rather than keeping the cosmetic ORM-level rename.

**Alternatives considered:** (1) Keep `db_column` workaround — zero Supabase changes needed. (2) Create a new table with the correct column names and migrate data.

**Rationale:** `db_column` creates a hidden mismatch between what Django code says and what the database actually stores. Anyone querying Supabase directly (RLS policies, dashboards, SQL scripts) would still see the old `program_*` names. A real rename eliminates this confusion layer entirely.

**Trade-offs:** Required coordinating a Supabase ALTER TABLE with a Django migration in the same deploy window. Brief risk of column-not-found errors if deploy order was wrong.

**Revisit if:** Never — this is a one-way improvement.

## TD-001: STPM SPM prerequisite fields — scope finding and user impact — Tech Debt Sprint 4, 2026-03-14

**Decision:** Fix applied (add `spm_pass_bi` and `spm_pass_math` to `SIMPLE_CHECKS` in `stpm_engine.py`). No user notification sent.

**Scope finding:** Queried Supabase production database. All 1,113 STPM requirement rows have `spm_pass_bi = false` and `spm_pass_math = false`. Zero programmes currently require a "pass" (as opposed to "credit") in BI or Math at SPM level. The 12 student profiles in the database have no STPM-specific data stored server-side (STPM eligibility uses client-side localStorage data).

**Alternatives considered:** (1) Fix the code and proactively alert users that results may have been incorrect. (2) Fix the code and do nothing. (3) Remove the unused model fields entirely.

**Rationale:** Since zero programmes set these flags to `true`, the missing check has never produced an incorrect result for any student. Alerting users about a bug that had no effect would cause unnecessary confusion. The fields exist in the model and CSV data for completeness — future programme data may set them. Removing them would lose that forward compatibility.

**Trade-offs:** If future CSV data sets these flags to `true`, the check will now correctly enforce them. Before this fix, such data would have been silently ignored.

**Revisit if:** New STPM programme data is loaded that sets `spm_pass_bi` or `spm_pass_math` to `true` — at that point, verify the STPM golden master baseline changes as expected.

## Backend-only calculations, delete frontend files — TD-002 Sprint, 2026-03-14

**Decision:** All eligibility formulas (merit, CGPA, pathway eligibility, fit scoring) live exclusively in the backend. Frontend deleted `merit.ts`, `stpm.ts`, and `pathways.ts` (596 lines) and now calls three new stateless API endpoints.

**Alternatives considered:** (1) Shared test vectors — keep both implementations, test against same fixtures. (2) Code generation — generate frontend functions from backend source. (3) Backend-only with API calls (chosen).

**Rationale:** User asked "If you were the developer, what would you wish your predecessors had done?" The answer is clear: one implementation, one place to change when requirements change. Shared test vectors still require maintaining two implementations. Code generation adds build complexity. API calls are simple, the app already requires network connectivity, and the ~200ms latency is acceptable for submit-time/page-load calculations.

**Trade-offs:** Grade pages now need network for merit/CGPA display (previously instant). Mitigated with 400ms debounce. Dashboard CGPA-to-percent was inlined as a trivial one-liner (no API call needed).

**Revisit if:** Offline support becomes a requirement, or if API latency degrades user experience on grade entry pages.

## Auth test mock fix over test infrastructure — TD-010 Sprint, 2026-03-14

**Decision:** Fixed 13 failing auth tests by adding a `jwt.get_unverified_header` mock alongside the existing `jwt.decode` mock in all test setUp methods. Did NOT build a reusable auth test infrastructure or JWT signing helper.

**Root cause:** The Supabase auth middleware calls `jwt.get_unverified_header(token)` before `jwt.decode()`. Tests were mocking only `jwt.decode`, but `get_unverified_header('fake-but-patched')` raised `InvalidTokenError` before `jwt.decode` was ever reached.

**Alternatives considered:** (1) Build a proper auth test infrastructure — a `TestAuthMixin` with real JWT signing using a test secret, role-based token generation (student, admin, anonymous), and shared helpers. (2) Simple mock fix (chosen).

**Rationale:** The proper infrastructure (option 1) is the right long-term answer, but it should be built when the admin layer is designed — not now. We don't yet know what roles, permissions, or auth flows the admin layer will need. Building test auth infrastructure now risks designing for requirements that don't exist yet (YAGNI). The mock fix is correct, minimal, and makes all 357 tests pass with 0 failures.

**What a future developer should do:** When building the admin/login tracking layer:
1. Design the role-based permission model first (student, counsellor, admin, etc.)
2. Build a `TestAuthMixin` or fixture that generates real signed JWTs with configurable roles
3. Replace the mock-based approach in `test_auth.py`, `test_saved_courses.py`, and `test_views.py` (reports) with the new mixin
4. Add tests for role-based access (e.g., admin can see all reports, student can only see own)
5. The middleware at `halatuju/middleware/supabase_auth.py` will also need updating for role extraction

**Trade-offs:** Three test files have near-identical mock boilerplate (header patcher + decode patcher). This is a code smell, but extracting a shared helper for 3 files would be premature — wait until the auth model is designed.

**Revisit if:** Admin layer work begins, or if a fourth test file needs the same auth mocking pattern.

## DB fixtures over CSV files for tests — Test Health Sprint, 2026-03-14

**Decision:** Created JSON fixtures (`courses.json`, `requirements.json`) dumped from production Supabase and use Django's `loaddata` in tests. Deleted all CSV-dependent test logic.

**Alternatives considered:** (1) Regenerate the old CSV files from Supabase. (2) Mock the DataFrame directly in each test. (3) DB fixtures via Django's `loaddata` (chosen).

**Rationale:** CSV files were deleted months ago and the data was subsequently modified across multiple sprints. Regenerating CSVs would create a second source of truth. Mocking DataFrames is fragile and wouldn't test the DB→DataFrame pipeline. Django fixtures are the standard approach, load into the test DB, and the shared `conftest.py` helper converts them to a DataFrame — replicating the production startup flow exactly.

**Trade-offs:** Fixture files are large (~33K lines combined). They must be regenerated when production data changes materially. But they're authoritative and testable.

**Revisit if:** Production data changes significantly (new courses, schema changes) — regenerate fixtures from Supabase.

## Golden master rebaseline: 8283 → 5319 — Test Health Sprint, 2026-03-14

**Decision:** Accepted 5319 as the correct SPM golden master baseline, replacing the stale 8283.

**Alternatives considered:** (1) Investigate and reverse the data changes that caused the drop. (2) Accept the new baseline after verification (chosen).

**Rationale:** The 8283 baseline was from CSV data that was migrated to Supabase and then modified across 3+ sprints (data integrity, MOHE audit, field corrections). The golden master test was silently skipping during all of these changes. Verified by comparing per-student eligibility counts between production DataFrame and fixture DataFrame — identical results. The data changes were intentional improvements, not regressions.

**Trade-offs:** None — this is a correction. The old baseline was never validated against the current data.

**Revisit if:** Never — forward baselines should be set against the current DB state.

## SupabaseAuthentication class for 401 responses — API Consistency Sprint, 2026-03-14

**Decision:** Added a lightweight `SupabaseAuthentication` DRF authentication class that returns `None` from `authenticate()` and `'Bearer'` from `authenticate_header()`. Registered as `DEFAULT_AUTHENTICATION_CLASSES`.

**Alternatives considered:** (1) Custom DRF exception handler to map `NotAuthenticated` → 401. (2) Override `APIView.permission_denied()` in a base view class. (3) DRF authentication class (chosen).

**Rationale:** DRF only returns 401 when at least one authenticator provides a `WWW-Authenticate` header. Our auth runs in Django middleware, not DRF's auth pipeline. Rather than fighting the framework (custom exception handlers, view overrides), the authentication class is the canonical mechanism. It's how DRF's own `TokenAuthentication` works.

**Trade-offs:** The class doesn't perform actual authentication (that's the middleware's job). This separation is slightly unintuitive — the "authenticator" is just a header provider. But it follows DRF conventions exactly.

**Revisit if:** The auth architecture changes to move JWT verification into DRF's authentication pipeline (e.g., replacing middleware with a proper DRF authenticator that also verifies tokens).

## Service module extraction for EligibilityCheckView — Refactoring Sprint, 2026-03-14

**Decision:** Extracted business logic from `EligibilityCheckView.post()` into a standalone `eligibility_service.py` module with 5 pure functions, reducing the view from ~310 lines to ~100 lines.

**Alternatives considered:** (1) Private methods on the view class (`_compute_merit()`, `_sort_results()`). (2) A service class with state (`EligibilityService(data, grades)`). (3) Pure module-level functions (chosen).

**Rationale:** Pure functions are the simplest option — no instantiation, no state, no DRF dependencies. Each function takes explicit parameters and returns plain dicts. This makes testing trivial (no request objects, no setUp) and the functions are reusable outside the view if needed. The view becomes a thin orchestrator that handles HTTP concerns only.

**Trade-offs:** The view must pass several parameters to each service function rather than relying on `self`. This is intentional — explicit parameters make data flow visible.

**Revisit if:** A second view needs the same eligibility logic (e.g., batch eligibility API), at which point the service module pays for itself immediately.

## Selenium-based URL validation for MOHE — External Links Sprint, 2026-03-14

**Decision:** Use Selenium with headless Chrome to validate MOHE ePanduan URLs by checking rendered page content, not HTTP status codes.

**Alternatives considered:** (1) httpx/requests HTTP status check. (2) Playwright MCP browser automation. (3) Selenium headless Chrome (chosen).

**Rationale:** MOHE's ePanduan portal always returns HTTP 302→200 regardless of whether the course exists. The rendered page shows "daripada 0 carian" for dead links and "1 daripada 1 carian" for valid links. HTTP clients cannot detect dead links. Playwright MCP failed because Chrome was already running. Selenium with headless Chrome works as a CLI tool without conflicts.

**Trade-offs:** Selenium is slower (~2-3 sec per URL with render wait) and requires Chrome + chromedriver installed locally. But it's a local admin tool, not deployed code.

**Revisit if:** MOHE changes their page structure (rendering detection would break), or if a public API becomes available.

## Course-level vs institution-level external links — External Links Sprint, 2026-03-14

**Decision:** Course detail pages have two distinct link types: (1) "More Info" pill in About section links to the external course portal (MOHE, MOE, polycc), (2) "More Info" button on institution cards links to the institution's own website.

**Alternatives considered:** (1) Single link per institution card combining both. (2) Link everything to MOHE. (3) Separate course-level and institution-level links (chosen).

**Rationale:** Course-level portals (MOHE ePanduan, MOE matric page, PISMP portal) describe the programme itself. Institution websites describe the institution — facilities, contact, admission. These serve different user needs. The separation also handles TVET correctly: TVET courses have per-institution hyperlinks (course-level), while the institution URL is the institution's general website.

**Trade-offs:** More complex frontend logic to determine which URL to show in the About pill (different logic per source_type). But the pattern is consistent once established.

**Revisit if:** A unified course information portal emerges that covers all institution types, or if polycc/MOE links become course-specific rather than portal-level.

## Engine keys as canonical subject format — Subject Key Unification Sprint, 2026-03-15

**Decision:** All SPM subject keys use lowercase engine format (`bm`, `eng`, `math`, `phy`) everywhere — frontend, backend, localStorage, API payloads. `subjects.ts` is the single source of truth with structured category metadata.

**Alternatives considered:** (1) Keep uppercase frontend keys with serializer mapping. (2) Use display names as keys. (3) Unify on engine keys (chosen).

**Rationale:** Engine keys were already used by 90% of the codebase (subjects.ts SUBJECT_NAMES, engine.py, pathways.py, eligibility_service.py, SPM prereqs). Only the grades page used uppercase. Aligning to the majority eliminates the serializer mapping layer entirely — one fewer place to maintain when subjects change.

**Trade-offs:** Beta testers must re-enter SPM grades (localStorage keys changed). Acceptable given small beta user base.

**Revisit if:** A new data source (e.g. MOE API) provides grades in a different key format — would need a mapping layer at the ingestion boundary, not the serializer.

## Default-deny permissions (SupabaseIsAuthenticated) — Security Sprint, 2026-03-14

**Decision:** Changed `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` from `AllowAny` to `SupabaseIsAuthenticated`. All 16 public endpoints explicitly marked with `permission_classes = [AllowAny]`.

**Alternatives considered:** (1) Keep AllowAny default and rely on developers remembering to add auth. (2) Use Django's built-in `IsAuthenticated` instead of custom class.

**Rationale:** Default-deny is a security best practice. A forgotten `permission_classes` line now results in 403 (safe) instead of public access (dangerous). Custom `SupabaseIsAuthenticated` is used because auth flows through Supabase JWT middleware, not Django's session auth.

**Trade-offs:** Every new public endpoint requires an explicit `permission_classes = [AllowAny]` line. This is intentional friction — forces the developer to consciously decide that an endpoint should be public.

**Revisit if:** Django's auth backend is changed from Supabase JWT to something else, or if a more granular RBAC system is introduced.

## i18n message files for course descriptions — Tech Debt Quick Wins 2, 2026-03-15

**Decision:** Pre-U course descriptions and headlines are stored in i18n message files (`en.json`, `ms.json`, `ta.json`) under a `courses.{course_id}` key, not in DB fields.

**Alternatives considered:** (1) Add `description_ta` and `headline_ta` fields to the Course model — requires migration, only solves Tamil. (2) Populate existing `description`/`description_en` DB fields — quick but excludes Tamil. (3) i18n message files (chosen).

**Rationale:** The project has a trilingual i18n system (EN/MS/TA) but the Course model only has 2 description fields (MS/EN). For a fixed set of 6 courses, i18n keys are the correct approach — all 3 languages, versioned with the codebase, no migration needed. The detail page checks i18n keys first, falls back to DB fields for the 390+ other courses.

**Trade-offs:** Two rendering paths for descriptions (i18n → DB → fallback template). But this is explicit and the fallback template itself is now an i18n key too.

**Revisit if:** All course descriptions need trilingual support — at that point, either add `description_ta`/`headline_ta` to the model, or build a course content CMS.

## IC gate replaces school input in auth flow — IC Gate Sprint, 2026-03-15

**Decision:** Replaced the optional school name input in AuthGateModal with a compulsory IC number (NRIC) step. IC is validated (DOB age 15–23, valid state code), stored in `StudentProfile.nric`, and displayed masked (`****-**-1234`) on the profile page. IC is immutable after initial entry.

**Alternatives considered:** (1) Keep school input and add IC as an additional field on profile page. (2) Collect IC later when needed (e.g., at application time). (3) Replace school with IC at auth time (chosen).

**Rationale:** User identified that school name was collected but unused, while IC provides verifiable student identity needed for tracking students through graduation. Making it compulsory at auth time ensures all authenticated users have an IC on record. Simple validation (DOB range + state code) catches typos without over-validating.

**Trade-offs:** Students must enter their IC to proceed — some may abandon. Mitigated by privacy reassurance message. IC is not editable after entry, preventing students from gaming eligibility. School field remains in the model but is not collected during auth.

**Revisit if:** User testing shows significant drop-off at the IC step, or if a less intrusive verification method becomes available.

## Profile view/edit per-section pattern — IC Gate Sprint, 2026-03-15

**Decision:** Profile page defaults to read-only view mode. Each section (Identity, Contact, Family) has an Edit button. Only one section can be in edit mode at a time, with Save/Cancel buttons.

**Alternatives considered:** (1) Keep all fields always editable with a single save button. (2) Inline edit on individual fields (click to edit each field). (3) Per-section view/edit (chosen).

**Rationale:** Always-editable forms invite accidental changes. Inline edit adds complexity for mobile. Per-section grouping matches the existing visual sections and gives users clear intent signals — "I want to change my contact info" vs accidental keystrokes.

**Trade-offs:** More state management (editingSection, snapshot for cancel). Slightly more code in the profile page. But UX is cleaner and prevents accidental data loss.

**Revisit if:** User testing reveals the Edit button is too many clicks, or if a more complex profile structure (e.g., education history, multiple addresses) requires a different pattern.

## Course content in BM database columns, not i18n — STPM Headlines Sprint, 2026-03-15

**Decision:** STPM headlines (and all course content: names, descriptions) are stored in BM in the database. The i18n system (`en.json`, `ms.json`, `ta.json`) is used only for static UI strings. If EN/TA course translations are needed later, they will be added as additional DB columns (`headline_en`, `headline_ta`), not i18n keys.

**Alternatives considered:** (1) Store headlines as i18n message keys (`courses.{course_id}.headline`) — trilingual from day one. (2) Store in DB with BM only (chosen). (3) Store in DB with BM + EN columns immediately.

**Rationale:** There are 1341 visible courses (390 SPM + 951 STPM). Maintaining i18n keys for this many courses creates a massive, hard-to-manage JSON file. Course content is dynamic (changes with annual data refreshes) while i18n files are static and versioned with code. DB columns allow content updates via management commands or admin tools without code deploys. BM is sufficient for now — 90%+ of users are BM-literate.

**Trade-offs:** No English or Tamil headlines until DB columns are added. The earlier decision (Tech Debt Quick Wins 2) to use i18n for pre-U descriptions is now inconsistent — those 6 descriptions should eventually migrate to DB columns too.

**Revisit if:** Multi-language course content becomes a priority, or if a course content CMS is built.

## Dual nullable FKs for SavedCourse — Saved Courses Sprint 1, 2026-03-15

**Decision:** SavedCourse has two nullable FKs (`course` → Course, `stpm_course` → StpmCourse) with a DB check constraint ensuring exactly one is set. Partial unique indexes enforce uniqueness per type.

**Alternatives considered:** (1) Generic string field (`course_id` + `course_type` varchar) — simpler model but no referential integrity. (2) Single polymorphic FK with content type — Django's ContentType framework adds complexity. (3) Dual nullable FKs (chosen).

**Rationale:** Referential integrity is non-negotiable for analytics (which courses are popular, applied, offered). Cascading deletes prevent orphan rows. Direct JOINs work without intermediary tables. The tabbed saved page (SPM/STPM) maps naturally to `WHERE course IS NOT NULL` / `WHERE stpm_course IS NOT NULL`. Pattern extends cleanly for a third qualification type (add another nullable FK + update check constraint).

**Trade-offs:** Check constraint makes bulk inserts slightly more complex (must ensure exactly one FK). Two partial unique indexes instead of one simple unique_together. But both are handled transparently by Django ORM.

**Revisit if:** A third qualification pathway (e.g. UEC) is added — at that point, consider whether the pattern still scales or if a polymorphic approach is warranted.

## Deterministic STPM classifier over Gemini AI — Field Taxonomy Sprint 2, 2026-03-16

**Decision:** Used deterministic keyword matching (`classify_stpm_course()`) instead of Gemini AI to classify 1,113 STPM courses into taxonomy keys.

**Alternatives considered:** (1) Gemini classification with structured output (original plan). (2) Manual classification spreadsheet. (3) Deterministic keyword matching on `category` column (chosen).

**Rationale:** STPM `category` values are consistent BM labels (~170 unique values) unlike the messy Gemini-generated `field` values (207 mixed-language). The category data is clean enough for deterministic matching. Benefits: $0 cost, reproducible, testable without API mocking, no rate limits, instant execution.

**Trade-offs:** New STPM categories added in future data refreshes require manual additions to the classifier. But this is a small maintenance cost vs. ongoing API costs and non-determinism.

**Revisit if:** A new data source with thousands of unpredictable category values is added, where keyword matching becomes impractical.

## Separate admin auth with isolated Supabase clients — Admin Auth Sprint, 2026-03-16

**Decision:** Built a completely separate admin authentication system: PartnerAdmin model (not a role on StudentProfile), isolated Supabase client with separate localStorage key (`halatuju_admin_session`), AdminAuthProvider that wraps only `/admin/*` routes. Admin and student sessions are fully independent.

**Alternatives considered:** (1) Add `is_admin` + `admin_org` fields to StudentProfile — simpler model but conflates identities. (2) Shared Supabase client with role-based routing — risk of session confusion. (3) Separate everything (chosen).

**Rationale:** Admin identity is fundamentally different from student identity. Different fields (org FK, is_super_admin, name), different auth flows (invite-based vs self-signup), different lifecycles. A role flag on StudentProfile would require every admin to also have a student profile — wrong semantically and creates confusing data. Isolated Supabase clients prevent any possibility of a student session granting admin access, even if the same person holds both roles.

**Trade-offs:** More code to maintain (two auth providers, two Supabase clients, two sets of session management). Admin must log in separately even if they're also a student. But the security guarantee is worth the duplication.

**Revisit if:** A unified identity system is needed (e.g., single sign-on across student and admin), or if the number of role types grows beyond two and a proper RBAC system becomes warranted.

## PartnerAdmin UID backfill pattern — Admin Auth Sprint, 2026-03-16

**Decision:** PartnerAdminMixin uses UID lookup first, falls back to email lookup, then backfills the UID on the PartnerAdmin row. This handles the invite flow where the admin row is created (with email only) before the user has authenticated with Supabase.

**Alternatives considered:** (1) Require UID at invite time — impossible since the user hasn't signed up yet. (2) Two-step invite: create Supabase user first, then create PartnerAdmin with UID — requires service role key and more complex flow. (3) Email fallback + UID backfill (chosen).

**Rationale:** The invite creates a PartnerAdmin row with email. When the invited user signs up and first hits an admin endpoint, the mixin finds them by email and stores their UID for fast subsequent lookups. This is simple, handles the temporal gap between invite and first login, and requires no service role key for the lookup path.

**Trade-offs:** First admin request after signup is slightly slower (email lookup + UID write). Negligible in practice.

**Revisit if:** Never — this is a standard pattern for invite-based systems.

## List-of-dicts for multi-tier STPM subject groups — STPM Pipeline Sprint 2, 2026-03-16

**Decision:** `stpm_subject_group` and `spm_subject_group` JSONFields store a **list of dicts** instead of a single dict. Each dict has `{subjects, min_grade, min_count, exclude}`. Engine uses AND semantics — student must satisfy all groups.

**Alternatives considered:** (1) Nested dict with numbered tiers (`{"tier_1": {...}, "tier_2": {...}}`). (2) Single dict with comma-separated grades. (3) List of dicts (chosen).

**Rationale:** Many MOHE courses require "A in 2 AND A- in 1" — two distinct grade thresholds. A single dict can only represent one threshold. A list naturally represents N thresholds with AND semantics. Backward compatibility achieved with `isinstance(group, list)` check — old single-dict data still works.

**Trade-offs:** Engine code needs the isinstance check for backward compatibility until all data is migrated. List format is slightly more verbose in JSON.

**Revisit if:** MOHE introduces OR-semantics between tiers (unlikely given how university admission works — requirements are cumulative).

## Single ranked list from ranking API — Post-Launch Hardening Sprint, 2026-03-17

**Decision:** Ranking API returns `{ranked: [...]}` (single sorted list) instead of `{top_5: [...], rest: [...]}`.

**Alternatives considered:** (1) Keep top_5/rest split but increase top_5 to 10. (2) Add a `top_n` parameter. (3) Return single list (chosen).

**Rationale:** The backend was pre-splitting courses for a specific UI layout (6 top + rest). When the frontend filtered by pathway type after the split, most top slots belonged to other categories — causing fewer than 3 cards in TOP MATCHES. The backend's job is to rank, not to decide display groupings.

**Trade-offs:** Frontend must now slice the list itself (`filtered.slice(0, 3)` for top, rest for overflow). This is trivial and gives the frontend full control.

**Revisit if:** Multiple frontends need different split sizes — but even then, a `top_n` query parameter is cleaner than hardcoding in the backend.

## Three-stream SPM prereq UI (excluding vocational and Islamic) — SPM Prereq UI Sprint, 2026-03-18

**Decision:** STPM SPM prerequisite section shows 3 stream buttons (Science, Arts, Technical) with vocational and Islamic school subjects excluded from the frontend.

**Alternatives considered:** (1) Show all 5 streams including Vocational and Agama. (2) Show 4 streams (add Vocational as a button). (3) Flat list of all 100+ SPM subjects with search.

**Rationale:** Islamic school (Agama) subjects are out of scope for the initial release — the target audience is mainstream SPM students. Vocational subjects are niche and adding a 4th button increases UI complexity. Vocational subjects remain accessible via elective dropdowns if needed. The backend maps all subjects correctly (121 SPM_CODE_MAP entries) regardless of frontend scope.

**Trade-offs:** Students from vocational or Islamic school streams cannot fully specify their SPM subjects in the STPM prereq section. This may cause false negatives for a small number of courses. The backend eligibility engine still handles these subjects correctly if the data were provided.

**Revisit if:** User research shows significant demand from vocational/Islamic school students, or if the STPM prereq check produces too many false negatives for these streams.

## is_active soft delete over hard delete for STPM courses — Pipeline Completion Sprint, 2026-03-18

**Decision:** Added `is_active` BooleanField to StpmCourse (default True). Removed courses are deactivated, not deleted. Detail view and saved courses remain accessible for inactive courses.

**Alternatives considered:** (1) Hard delete removed courses from DB. (2) Add `status` CharField with multiple states (active/inactive/archived/draft). (3) Soft delete with `deleted_at` timestamp.

**Rationale:** Hard delete loses historical data and breaks saved course references. Multiple status states add complexity for a binary need. `is_active` boolean is the simplest model that works — courses are either shown to users or not. Detail view stays unfiltered so saved courses and shared links continue working.

**Trade-offs:** No "archived" or "draft" distinction. If MOHE temporarily removes a course and we deactivate it, then it reappears, we automatically reactivate — but any manual data changes made while inactive are preserved.

**Revisit if:** A third state is needed (e.g. "pending review" for new courses that haven't been parsed yet), or if the admin portal needs to manage course lifecycle states.

## NRIC as hard identity gate via middleware — NRIC Hard Gate Sprint, 2026-03-20

**Decision:** Enforce NRIC verification via Django middleware (`NricGateMiddleware`) rather than per-endpoint checks. No Supabase account or Django profile created until NRIC is verified. Students browse with Supabase anonymous sign-in (`is_anonymous=true` JWT).

**Alternatives considered:** (1) Check NRIC at each protected endpoint (rejected by user — "you are proposing a workaround, we want a hard gate"). (2) Create Supabase account at Google sign-in, check NRIC before profile creation — still creates orphan accounts if student changes login method. (3) Middleware-based gate with anonymous sign-in (chosen).

**Rationale:** A middleware gate means every new endpoint is automatically protected — no developer can accidentally forget the NRIC check. Anonymous sign-in provides a valid JWT for API calls without creating a permanent account, solving the orphan user problem. The whitelist (`/profile/`, `/profile/claim-nric/`, `/profile/sync/`, `/admin/`) covers only the endpoints needed to establish identity.

**Trade-offs:** Additional DB query per request (profile lookup). Mitigated with `.only('nric')` to fetch a single column. Anonymous sessions create lightweight Supabase auth entries that need periodic cleanup (30-day cron). `isAuthenticated` meaning changed from "has session" to "has NRIC" — existing code works because auth gates already check `!isAuthenticated`.

**Revisit if:** Performance profiling shows the per-request profile lookup is a bottleneck (could cache in middleware), or if a more granular permission system is needed beyond binary NRIC/no-NRIC.

## AuthProvider as single routing authority — Auth Flow Canonical Refactor, 2026-03-20

**Decision:** AuthProvider holds `status: AuthStatus` and `profile: StudentProfile | null` in React context. All routing decisions (callback, AuthGateModal, onboarding guard, IC page, dashboard, saved, profile) read from context. localStorage is a write-only cache — AuthProvider writes it as a side effect after fetching from API, but no component reads it for routing.

**Alternatives considered:** (1) Keep localStorage reads but add a "freshness" timestamp to detect stale data. (2) Add a global event bus that components subscribe to for profile changes. (3) Centralise in AuthProvider context (chosen).

**Rationale:** The root cause of multiple bugs (stale cache after BooleanField migration, profile not available after login, inconsistent state across components) was that each component independently read localStorage. A single context provider eliminates the entire class of stale-cache routing bugs. React context is the standard mechanism for shared state — no custom event bus needed.

**Trade-offs:** AuthProvider re-renders all consumers when status or profile changes. Acceptable because auth state changes are infrequent (login, logout, profile update). If performance becomes an issue, can split into separate StatusContext and ProfileContext.

**Revisit if:** Offline-first (PWA) support is needed — at that point localStorage would need to become a read source with a versioned schema and migration strategy.

## localStorage as disposable cache, not source of truth — i18n & Bug Fixes Sprint, 2026-03-19

**Decision:** `restoreProfileToLocalStorage()` always overwrites localStorage from Supabase API on login. No conditional writes. `clearAll()` wipes all `halatuju_*` keys on logout. Supabase is authoritative; localStorage is a performance cache only.

**Alternatives considered:** (1) Conditional restore — only write to localStorage when empty (the previous approach). (2) Field-specific migration shims (e.g. `migrateProfile()` to convert legacy "Ya"/"Tidak" strings to booleans). (3) Versioned localStorage schema with migration on read.

**Rationale:** Conditional writes create stale-cache bugs that only affect returning users — when the backend data format changes, localStorage retains the old format indefinitely. Field-specific migrations are workarounds that must be written for every future schema change. Always-overwrite eliminates the entire class of stale-cache bugs with a single architectural rule.

**Trade-offs:** An extra API call on every login (getProfile). Negligible cost — the call is fast and happens once per session.

**Revisit if:** localStorage needs to function as an offline-first store (Progressive Web App), in which case a versioned schema with migrations would be needed.

## Separate `apps/scholarship/` app for the B40 financing extension — B40 Sprint 1, 2026-05-21

**Decision:** Build the B40 Assistance Programme as a new `apps/scholarship/` Django app rather than adding models/views to `apps/courses/`.

**Alternatives considered:** (1) Add scholarship models + endpoints to `apps/courses/`. (2) A separate app.

**Rationale:** `apps/courses/` is the eligibility engine — its `apps.py` loads the whole course DataFrame at startup and it holds the golden-master logic. The financing domain (applications, sponsors, disbursements) is orthogonal: different lifecycle, different RLS posture, different reviewers. A separate app keeps the sacred engine untouched and lets the financing schema evolve independently. It reuses `StudentProfile` by FK across the app boundary (label `courses`).

**Trade-offs:** A cross-app FK (`'courses.StudentProfile'`) and a second migration history to track. Negligible vs. the isolation benefit.

**Revisit if:** The financing flow ever needs to run inside the eligibility request path (it doesn't — it's a separate funnel).

## Application model: explicit shortlisting fields + `form_data` JSON blob — B40 Sprint 1, 2026-05-21

**Decision:** `ScholarshipApplication` stores the shortlisting-relevant inputs as explicit typed columns (qualification, spm_a_count, stpm_pngk, household_income/size, receives_str/jkm, intended_pathway, intends_tertiary_2026, consent_to_contact) AND a `form_data` JSONField for the rest of the native form.

**Alternatives considered:** (1) Everything in one JSON blob. (2) Every form field as a column. (3) Hybrid (chosen).

**Rationale:** The shortlisting rules engine (Sprint 3) must filter/score on the criteria fields — those need to be queryable, typed, and indexable, so they are real columns. The remaining free-form intake (aspirations, narrative, etc.) is display-only and still firming up while the native form is designed (Sprint 2), so a JSON blob avoids premature schema churn.

**Trade-offs:** Two homes for intake data; a field that graduates from "display-only" to "scored" later needs a migration to promote it from `form_data` to a column.

**Revisit if:** A `form_data` key becomes load-bearing for shortlisting — promote it to a typed column at that point.

## RLS deny-by-default (no policies) for scholarship tables — B40 Sprint 1, 2026-05-21

**Decision:** Enable RLS on `scholarship_cohorts` and `scholarship_applications` with **no** permissive policies.

**Alternatives considered:** (1) RLS + per-row `authenticated` policies (as some Supabase-direct tables use). (2) RLS off. (3) RLS on, no policies (chosen).

**Rationale:** These tables are served exclusively by the Django API, which connects as the table-owner (service) role and bypasses RLS. The frontend never reaches them via PostgREST. Enabling RLS with no policy therefore denies all direct anon/authenticated access (defense in depth) while the API works normally. Application rows hold sensitive financial/family data, so deny-by-default is correct. Also satisfies the Security Advisor "RLS disabled" check.

**Trade-offs:** If a future sprint wants a direct, public, non-sensitive read (e.g. an open cohort listing via PostgREST), a narrowly-scoped SELECT policy must be added for that one table.

**Revisit if:** A frontend feature needs to read these tables directly from Supabase rather than through the Django API.

## New `'apply'` AuthGateReason extends the shared auth flow — B40 Sprint 2, 2026-05-21

**Decision:** Added `'apply'` to `AuthGateReason` and a branch in `AuthGateModal.finishAndClose` that `router.push('/scholarship/apply')`, rather than building a separate auth path for the apply page.

**Alternatives considered:** (1) Reuse the existing `'profile'` reason (but it redirects to dashboard/onboarding, not back to apply). (2) A bespoke inline auth flow on the apply page. (3) Extend the shared flow with one new reason (chosen).

**Rationale:** The auth flow (anonymous sign-in → Google → NRIC claim → resume pending action) is delicate and has been the subject of multiple bug-fix sprints. Reproducing it would be risky and duplicative. A single new reason reuses the entire `KEY_PENDING_AUTH_ACTION` resume machinery and the IC-gate, and returns the user to the apply page — the correct UX with a minimal, contained change.

**Trade-offs:** Touches two shared auth files. Mitigated by mirroring the existing `'quiz'` reason exactly (direct `router.push`) and gating on `next build`.

**Revisit if:** The auth flow is refactored, or apply needs a different post-auth destination.

## Lightweight self-reported academics in the apply form — B40 Sprint 2, 2026-05-21

**Decision:** The apply form captures academics as a single self-reported number (SPM A-count, or STPM PNGK), pre-filled from the profile when grades exist, rather than embedding the full grades-onboarding UI or forcing the student through it first.

**Alternatives considered:** (1) Reuse/embed the full per-subject grades onboarding. (2) Require grades onboarding before the apply page opens. (3) Lightweight self-reported number (chosen).

**Rationale:** The shortlist only needs the A-count / PNGK. Self-reporting keeps "apply-first" smooth (the agreed principle — don't front-load the quiz/onboarding), and documents verify the real figures later. The backend still snapshots the A-count from `profile.grades` when no explicit value is sent, so returning students with grades are covered automatically. Full grades + quiz arrive at STEP 1A (Sprint 4).

**Trade-offs:** Self-reported numbers can be wrong; shortlisting on them is provisional until document verification (Sprint 5). Acceptable — the alternative front-loads friction onto exactly the B40 audience we want to reach.

**Revisit if:** Self-reporting proves unreliable enough to distort shortlisting before documents are collected.

## Synchronous shortlist on submit; pass email immediate, fail email deferred — B40 Sprint 3, 2026-05-21

**Decision:** The intake view runs `shortlist_application()` synchronously right after creating the application. A qualifying applicant gets the acknowledgement email *and* an immediate congratulations email; a rejected applicant gets only the acknowledgement, with the courteous "not this round" email deferred to the `send_pending_decision_emails` command (after `fail_email_delay_days`). The applicant's `locale` and resolved `notify_email` are stored on the application at submit so the deferred command needs no request context.

**Alternatives considered:** (1) Shortlist asynchronously via a queue/cron after submit. (2) Send the fail email immediately too. (3) Synchronous shortlist + deferred fail email (chosen).

**Rationale:** Instant mechanical shortlisting matches the PRD funnel and the near-zero-touch goal, and the synchronous send is consistent with the existing synchronous acknowledgement send. Deferring the fail email avoids a rejection landing seconds after applying (a deliberate kindness in the spec). Storing locale + notify_email avoids needing the request (or a live JWT) when the scheduled command runs days later.

**Trade-offs:** The submit request does up to two SMTP sends (acknowledgement + pass), adding latency; both are best-effort (failures are swallowed). A future move to async sending would remove the latency. The fail email depends on a scheduler being wired at deploy.

**Revisit if:** SMTP latency degrades the submit UX (move sends to a queue), or the two-email pass flow proves redundant (merge acknowledgement + pass into one email).

## FundingNeed as a separate OneToOne model with a computed total — B40 Sprint 4a, 2026-05-21

**Decision:** Store the funding-need breakdown as its own `FundingNeed` model (OneToOne → application) with typed integer line items and a computed `total` property, rather than a JSON blob on the application.

**Alternatives considered:** (1) A JSON field on the application. (2) Columns directly on the application. (3) Separate OneToOne model (chosen).

**Rationale:** The breakdown will be displayed, summed, shown to sponsors, and eventually used in disbursement maths — typed columns + a computed total are queryable and validatable, and a separate model keeps the already-large application row uncluttered and the funding concern cohesive. Upsert via `update_or_create`.

**Trade-offs:** A second table and a reverse relation to handle (accessed via `try/except DoesNotExist`). Negligible.

**Revisit if:** The breakdown needs free-form, highly variable line items that don't fit fixed columns.

## Signed-URL direct-to-Supabase document storage (no bytes through Django) — B40 Sprint 5a, 2026-05-22

**Decision:** Documents upload straight from the browser to a private Supabase Storage bucket using a signed upload URL the backend mints (service key, stdlib `urllib`); Django stores only the path + metadata and serves time-limited signed download URLs on demand.

**Alternatives considered:** (1) Proxy file bytes through Django to Storage. (2) `supabase-py` client. (3) Signed URLs via stdlib `urllib` (chosen).

**Rationale:** Cloud Run has request-size/memory limits; keeping bytes off Django avoids them and is the standard private-storage pattern. stdlib `urllib` avoids a new dependency and keeps the module importable so tests mock the two functions cleanly. The service key stays server-side; the browser only ever receives short-lived signed URLs.

**Trade-offs:** Can't integration-test against real Storage locally (mocked + a 503 fallback when unavailable); the private bucket is a deploy carry-forward. Generating a download URL per document during list serialization makes one HTTP call per doc — fine at N≤7.

**Revisit if:** Per-applicant document volume grows large (sign lazily), or a richer storage SDK becomes warranted.

## Versioned, guardian-gated consent keyed on NRIC age — B40 Sprint 5a, 2026-05-22

**Decision:** `Consent` rows are versioned (`CONSENT_VERSION`), withdrawable (`is_active`), and superseding (a new consent of a type deactivates prior ones). A minor (<18, age derived from the NRIC DOB) must have consent granted by a guardian (name + relationship) or it is rejected.

**Alternatives considered:** (1) A single boolean consent flag on the application. (2) Verbal/implicit consent (what the B40 analysis flagged as insufficient). (3) Versioned consent records with a guardian gate (chosen).

**Rationale:** PDPA needs an auditable, purpose- and version-specific record, and Malaysian minors need guardian consent before their data is shared with sponsors. Deriving age from the already-verified NRIC avoids collecting DOB twice. Superseding keeps an audit trail while making "current consent" unambiguous.

**Trade-offs:** Consent text is DRAFT until lawyer review (the version string swaps then). NRIC-derived age assumes a valid NRIC (already gated at identity).

**Revisit if:** The lawyer requires a different consent structure, or non-NRIC identities are admitted.

## AI-draft → admin-edit → publish profile workflow — B40 Sprint 6a, 2026-05-22

**Decision:** `SponsorProfile` keeps the raw AI `draft_markdown` and the admin's `edited_markdown` separately, with `current_markdown` = edited-wins, and a status flow draft → approved → published. Regenerating a published profile reverts it to draft.

**Alternatives considered:** (1) A single markdown field overwritten by both AI and admin. (2) Auto-publish the AI draft. (3) Separate draft/edited with an explicit publish status (chosen).

**Rationale:** Keeping the AI draft distinct from the admin's edits preserves the original for comparison/regeneration and makes "what sponsors will see" unambiguous (`current_markdown`). The status flow gives an explicit human publish gate before a profile becomes sponsor-visible (Phase 2) — never auto-publish AI output about a real person. Reverting on regenerate prevents a stale published profile silently diverging from a fresh draft.

**Trade-offs:** Two text fields + a status to reason about. Negligible vs. the auditability and the human gate.

**Revisit if:** Profiles need multi-version history (add a revisions table), or sponsors should ever see drafts directly (they shouldn't).

## Profile is the single source of truth for applicant data — B40 Phase 1.5a, 2026-05-22

**Decision:** Academic (grades / exam type / STPM CGPA) and financial (household income/size, STR/JKM) data lives **only** on `courses.StudentProfile`. The `ScholarshipApplication` row keeps per-application fields only (intended pathway, intent, consent, deeper-info, funding need). The apply form **pre-fills** from the profile and **writes back** the financial fields it collects (`services.sync_profile_fields`), the shortlisting engine reads academic + income **live** from `application.profile`, and a frozen `intake_snapshot` JSON captures what was declared at submit time as audit evidence (never the live source).

**Alternatives considered:** (1) Duplicate the shortlisting-relevant fields onto the application and snapshot them at submit (the original Sprint-1–3 design). (2) Profile-only with no snapshot. (3) Profile-canonical + write-back + immutable intake_snapshot (chosen).

**Rationale:** ~600 students already onboarded HalaTuju via Google Sign-In, so much of this data already exists on the profile. Re-asking and storing a second copy on the application created a "clash on the hierarchy of truth" (the user's words) — two divergent values for the same fact, with no defined winner. Making the profile canonical means a student updates their income once and every round sees it; the engine never scores stale duplicated data. The `intake_snapshot` preserves auditability (what they actually declared then) without making the application a competing source.

**Trade-offs:** Shortlisting now depends on the profile being populated — a profile with empty grades scores 0 A's (correctly fails academic). The write-back only overwrites with non-None form values, so a form that omits a field can't blank an existing profile value. Migrations `courses 0047` (add financial fields) + `scholarship 0006` (remove the duplicated fields, add `intake_snapshot`) must both deploy together.

**Revisit if:** A future round needs point-in-time scoring against the snapshot rather than the live profile (then score from `intake_snapshot`), or non-HalaTuju applicants (no profile) are admitted (then the application would need to carry its own data again).

## Soft-NRIC: editable until admin-verified (supersedes "IC immutable") — B40 Redesign Sprint 7, 2026-05-23

**Decision:** NRIC is **soft** — editable by the student until an admin verifies it against the uploaded MyKad, after which it locks. Added `StudentProfile.nric_verified` (default false). Uniqueness is enforced **only when verified** (`unique_verified_nric`, condition `nric_verified AND nric <> ''`), replacing `unique_nric_when_set`. NRIC is **read-only on `PUT /profile/` and `/profile/sync/`** — it changes only via the validated `/profile/claim-nric/` endpoint, which now **blocks a change once the caller's NRIC is verified** (403 `nric_locked`). **This supersedes the IC Gate Sprint (2026-03-15) decision that "IC is immutable after initial entry."**

**Alternatives considered:** (1) Keep IC immutable + add an admin-only override tool. (2) Free self-service edit anytime (no verification gate). (3) Soft until admin verify-&-accept, uniqueness only when verified (chosen).

**Rationale:** "IC immutable after initial entry" left students permanently stuck with a fat-fingered or fake NRIC (no self-service fix) and let a wrong entry block the rightful owner via the unique constraint — both surfaced in the NRIC investigation. For a need-based programme the real guard is the **document check + admin verify-&-accept before award** (Google Vision assists; a human signs off), not an entry-time lock. Relaxing uniqueness to verified-only means a typo of someone else's number can't hard-block a submission; the clash surfaces at verification, where only one NRIC can be verified. Editing routes through the validated claim path, so format/age/state checks still apply and there is a single write point (closing the `PUT`/`sync` gaps).

**Trade-offs:** During the soft phase the DB no longer blocks duplicate NRICs — the document check + admin verification is the only guard before money moves (intended). The minor/guardian-consent gate recomputes from the (now editable) NRIC birth-date on each change. Existing 493 NRICs start unverified (editable) — fine, none are yet document-verified.

**Revisit if:** Fraud pressure requires entry-time identity verification (then add Vision/JPN at claim time), or a non-applicant context needs a locked NRIC without an admin step.

## Deterministic decision rule (per-capita + STR + academic floor) — supersedes the weighted score — B40 Redesign Sprint 8, 2026-05-24

**Decision:** The shortlist decision is a simple deterministic rule, not a 0–100 weighted score: hard gates (consent · intends public study · NOT IPTS-only) → academic floor (SPM ≥4 at A- AND ≥5 at B+ / STPM PNGK ≥2.9) → income (STR recipient passes, bucket A; otherwise per-capita income = household_income / household_size must be < `per_capita_ceiling` RM1,584, bucket B). The verdict is computed **silently at submit** (status stays `submitted`); the scheduler **reveals** it later — +2h for shortlist (invitation email), +48h for decline (warm email). Supersedes the exploratory Sprint-3 Bucket-A/B/marginal engine and the planned weighted score (per-capita bands + factor weights + pass mark + hardship flags).

**Alternatives considered:** (1) Weighted 0–100 score with per-capita bands, dependent/hardship/results weights, and a pass mark (the earlier plan). (2) Household-income bands (B40 < 5,860 / M40 / T20 > 12,679). (3) Simple rule: academic floor + (STR OR per-capita < RM1,584) (chosen).

**Rationale:** Per-capita income already accounts for household size/dependents, so it captures need without a separate hardship score — the grantmaking lead's call ("3 captures this"). RM1,584 = DOSM-2024 B40 ceiling RM5,860 ÷ average household 3.7. Per-capita naturally rejects T20 and is fairer to large families than a flat household ceiling. STR is government-verified low income → a reliable fast-path. With no human in the loop, a transparent reproducible rule is far easier to defend to a rejected applicant than a weighted score. Silent-score + delayed reveal (+2h/+48h) makes an automated verdict feel considered. The public criteria stay at the advertised bar (5 A's / PNGK 3.0, Indian-descent pilot) while the engine is intentionally more lenient (4A-+1B+ / 2.9, open to all) to accommodate near-misses.

**Trade-offs:** No nuanced scoring — a borderline case is decided by hard thresholds (RM1,584, the academic floor) rather than a holistic score. Accepted: simplicity + defensibility + the document/admin verification at award are the real guards. Hardship/clarity become sponsor-profile + mentoring signals, never reject inputs.

**Revisit if:** Outcomes show the per-capita threshold mis-sorts a class of applicants (add back a small scored layer), or a round needs ranking/quotas beyond pass/fail (score within the passing set).

## Commit-on-submit: profile fields via the submit, NRIC via the claim path — B40 Redesign Sprint 9, 2026-05-24

**Decision:** The inline-editable apply form holds edits in React state and persists **nothing** until a successful
submit. On submit, the About-Me/My-Family fields (name, school, home state, phone, parent `guardians`, call
language, referring-org code) ride the application POST and are written to the canonical `StudentProfile` by
`services.sync_profile_fields` (extended from financial-only). The **NRIC is committed separately** through the
validated `/profile/claim-nric/` endpoint — it is never in the application payload and stays read-only on the
serializer. The referring-org is a **fixed dropdown** whose code is stored raw on `profile.referral_source` and
resolved to the `referred_by_org` FK only when a matching active `PartnerOrganisation` exists.

**Alternatives considered:** (1) Persist each field as the user edits (the old "financial writes back while editing"
pattern). (2) Put NRIC in the application payload and let the serializer write it. (3) A live partner-org endpoint
feeding the dropdown.

**Rationale:** A single commit point means a half-finished or failed submit leaves the profile untouched — no
partial writes, no "saved but didn't apply" ambiguity. NRIC must keep its format/age/state validation and the
soft-NRIC verified-lock semantics, all of which live in the claim endpoint — routing it there preserves a single
validated write path and keeps the serializer's `nric` read-only (closing the PUT/sync gap from S7). A fixed
referring-org list matches the legacy Google Form exactly, needs no new endpoint, and `referral_source` already
existed for this; the FK links opportunistically when the org is seeded (TD-056).

**Trade-offs:** The NRIC claim is a second network call on submit, ordered before the application POST; if the claim
succeeds but the POST then fails, the NRIC is updated while no application is created (acceptable — the next submit
attempt succeeds, and the NRIC write is itself valid). The apply form's `guardians` write overwrites the whole list
with one entry (TD-055). Until partner orgs are seeded, attribution persists only as the raw `referral_source` code.

**Revisit if:** Submit latency from the two sequential calls hurts UX (batch into one transactional endpoint), or
guardians/partner-orgs need richer handling.

## My Results edit detour: sessionStorage stash + return-marker — B40 Redesign Sprint 9b, 2026-05-24

**Decision:** Editing/adding results from the apply form sends the student through the **full onboarding** flow
and returns them to the apply page afterwards. Because the apply form only commits on submit, the in-progress
About-Me/My-Family edits are **stashed to sessionStorage** before leaving and **restored on return**; a separate
**boolean return-marker** (also sessionStorage) tells the final onboarding step to route back to `/scholarship/apply`
(button relabelled "Save & return to application") instead of `/dashboard`. The marker is cleared on a legitimate
return and orphan-cleared on any normal apply visit.

**Alternatives considered:** (1) Thread the return intent as a query param (`?return=apply`) through every
onboarding step. (2) Persist apply edits to the backend before the detour. (3) Block results-editing from the apply
form (link to a read-only profile view).

**Rationale:** The onboarding steps `router.push` without preserving query strings, so threading a param would
mean touching every intermediate step — more surface, more risk — for a flow that's inherently single-tab.
sessionStorage is tab-scoped (auto-clears on close) and survives the multi-page detour. Persisting edits to the
backend mid-flow would violate the sprint's commit-on-submit invariant (a half-finished apply must write nothing).

**Trade-offs:** A persistent marker can go stale if the student abandons onboarding mid-flow and then starts a
normal onboarding in the same tab (TD-057) — mitigated (orphan-clear + tab-scoped) but not eliminated. Restoring
the stash requires a `populatedRef` guard so the profile-prefill effect doesn't clobber the restored edits.

**Revisit if:** TD-057's abandon edge bites in practice (switch to query-param threading), or onboarding gains a
step that itself needs to preserve query state (thread a typed nav-state object instead).

## My Plans top-3 sourced from saved courses (not a fresh eligibility recompute) — B40 Redesign Sprint 10, 2026-05-24

**Decision:** The apply form's "top 3 course choices" are picked from the student's **saved courses**
(`getSavedCourses`, exam-type aware), ranked by tap order, capped at 3, with a friendly empty-state when none are
saved. `top_choices` is stored as `[{rank, course_id, course_name, institution}]`. It's optional — the decision
engine never scores it (only `upu_status='ipts'` disqualifies); it feeds the sponsor profile + a seriousness signal.

**Alternatives considered:** (1) Recompute the student's full eligible + ranked list in the apply form (mirror the
dashboard's `checkEligibility` → `getRankedResults` / `rankStpmCourses` two-step, needing the full grades payload +
quiz signals) and pick from that. (2) Free-text course names. (3) Search/autocomplete against the whole catalogue.

**Rationale:** Saved courses are a subset of the student's eligible courses (you can only save what was shown to
you), so they satisfy "from eligible options" while being far lighter — one call, no eligibility recompute, no
signal prep — which kept S10 to a single session. Deliberately-bookmarked courses are also a *stronger* seriousness
signal than a list the form generated. Free text isn't validated; full-catalogue search lets them pick ineligible
courses.

**Trade-offs:** A serious student who hasn't saved anything sees an empty-state and must go bookmark first (top-3
stays optional, so they can still submit). The picker reflects only what's saved at submit time, not a live ranking.

**Revisit if:** Too many applicants reach My Plans with no saved courses (then offer an inline eligible-courses
fetch as a fallback), or sponsors need a ranked-eligibility view rather than the student's self-selected three.

## Admin verify-&-accept is the single NRIC-uniqueness point; new `accepted` status — B40 Redesign Sprint 11a, 2026-05-24

**Decision:** A `shortlisted` application is confirmed by a human via `AdminVerifyAcceptView`: the admin ticks a
checklist (NRIC / name / results / document) against the uploaded MyKad, which sets `profile.nric_verified` (locks
the NRIC), stamps `verified_at` / `verified_by` / `verify_checklist`, and advances the application to a **new
`accepted` status**. NRIC uniqueness is enforced **only here** — if another profile already has that NRIC verified,
the endpoint returns `409 nric_conflict` for the admin to resolve. This is the resolution of TD-054.

**Alternatives considered:** (1) Enforce NRIC uniqueness at entry/claim time (a DB unique constraint or the claim
endpoint) — the pre-soft-NRIC model. (2) No new status — verify just stamps audit fields, application stays
`shortlisted`. (3) A separate `is_verified` boolean instead of a status transition.

**Rationale:** The soft-NRIC decision (S7) deliberately tolerates duplicate *unverified* NRICs (a typo of someone
else's number must not block a poor applicant's submission); the design said the clash should "surface at
verification". Verify-&-accept is exactly that moment, so it's the correct — and only — place to enforce uniqueness.
A distinct `accepted` status cleanly separates "passed the automatic screen" (shortlisted) from "a human verified
the documents and confirmed" (accepted), which the admin list can filter on and the applicant view (S11b) can show.

**Trade-offs:** Uniqueness isn't DB-guaranteed while unverified — two profiles can hold the same NRIC until one is
verified (intended; the document check is the real guard before money moves). `STATUS_CHOICES` now has five values;
migration `0009` re-emits an `AlterField` on both `status` and `verdict` (no-op, choices are validation-only).

**Revisit if:** Fraud pressure requires entry-time identity verification (add JPN/Vision at claim time), or the
programme needs more workflow states beyond submitted/shortlisted/accepted/rejected/withdrawn (e.g. disbursing).

## Drop "Indian descent" from all public copy (supersedes the keep-it-public call) — Landing-copy review, 2026-05-25

**Decision:** The B40 public copy (`docs/halatuju_scholarship_landing_copy.md`, and the live `/scholarship` page once
the copy is applied) makes **no mention of Indian descent / ethnicity anywhere — not even as a pilot framing**. This
**supersedes** the 2026-05-24 decision (item D under "Deterministic decision rule…") to keep advertising the
"Indian descent (pilot)" line publicly.

**Alternatives considered:** (1) Keep the "Indian-descent pilot" framing in the public copy (the earlier call).
(2) Mention it only in the About section.

**Rationale:** Funds are administered by **MyNadi Foundation**, whose **Section 44(6)** tax-exempt status requires the
programme not to discriminate on the basis of race. Even though 44(6) is not yet formally confirmed, it is safer to
omit ethnicity everywhere from the outset than to publish it and have to retract. This also matches the engine, which
has **no descent check** (S8 policy call #1, "we don't want to know"). The community's Indian-organisation origins
remain visible through the partner mentions (CUMIG, Sri Murugan Centre) without ethnicity being a criterion.

**Trade-offs:** The advertised audience reads as all low-income Malaysians, broader than the pilot's community roots;
referrals still flow through the named partner orgs, so reach is unaffected in practice.

**Revisit if:** MyNadi 44(6) status is declined and a different administering body without that constraint is used,
or legal advice changes.

## "Your Plans" step = one progressive-disclosure question, eligible-only, derived destination — plans-redesign P2, 2026-05-26

**Decision:** The apply-form Plans step opens with a single question — *"Do you know which pathway you'll take?"* →
**Decided / Still deciding** — and reveals everything else only after it's answered. The **Decided** branch (SPM
leavers) offers a **single-select dropdown of only the pathways the student's results qualify them for**, each labelled
with its eligible-programme count, sourced live from the existing `/eligibility/check/` engine (`pathway_stats` →
`eligiblePathways()` in a fixed order). The question is **required to submit**, but *"still deciding"* is always a valid
answer. `upu_status` is **derived** from the chosen (public) pathway rather than asked, and `intends_tertiary_2026`
defaults true (the step presupposes continuation).

**Alternatives considered:** (1) The previous flat layout — a multi-select pathway-chips control + a separate UPU
radio + a manual field-of-study select + a top-3 saved-courses picker, all shown at once. (2) Show every pathway
(eligible or not) and let the student pick freely. (3) Leave the step optional (no submission gate).

**Rationale:** The flat layout asked overlapping questions and surfaced controls that generated no usable signal
(the user's "every control must generate signal — for the gate OR the profile" test). Progressive disclosure keeps
the step to one decision at a time; eligible-only prevents a student from "deciding" on something they can't enter
and reuses the engine as the single source of truth; deriving `upu_status` removes a redundant destination question
because every eligible pathway is a public institution (non-IPTS). Requiring the question (with "still deciding" as
an escape hatch) guarantees a signal without ever trapping an unsure student.

**Trade-offs:** Adds a per-step client call to `/eligibility/check/` on the Plans tab (acceptable — same endpoint the
results pages already use). STPM students see a stub in P2 (their degree branch lands in P5). The legacy
field-of-study + top-3 pickers are kept *gated under "Decided"* this sprint and only removed in P3 when the
pathway-filtered course dropdown replaces them — a deliberate one-sprint deferral, not permanent.

**Revisit if:** the eligibility engine can't return `pathway_stats` cheaply enough for an inline call, or a future
cohort funds private (IPTS) pathways (which would reintroduce a real destination question rather than a derived one).

## Uncertain-branch reasons captured, but mentoring stays coordinator-set — plans-redesign P5, 2026-05-27

**Decision:** The "Still deciding" branch collects `uncertainty_reasons` (e.g. *want advice / family / finance*) and
surfaces them on the admin scholarship detail, but does **not** auto-set `mentoring_candidate` at intake. The
coordinator flags mentoring after reviewing the reasons.

**Alternatives considered:** Auto-flag `mentoring_candidate=true` at submit when the reasons include guidance/family/finance.

**Rationale:** `mentoring_candidate` is, by the model's existing design, **coordinator-set, not applicant-collected**
(it's absent from `ApplicationCreateSerializer`; services.py says so explicitly). Auto-setting it would mean adding a
backend write path on a deploy-day ship sprint, for marginal benefit. Capturing the reasons gives the coordinator the
signal to decide; the applicant never directly sets a staff flag. Kept the P5 ship frontend-only.

**Trade-offs:** Mentoring routing is one manual coordinator step rather than automatic. Low cost given volumes.

**Revisit if:** intake volume makes manual mentoring triage a bottleneck — then auto-flag server-side from the reason
keys (a small, safe `services.py` change), keeping the coordinator able to override.

## Typed-name signature is a soft attestation, not an identity gate — Post-launch apply polish (2.3.0), 2026-05-27

**Decision:** The pre-submit truthfulness declaration asks the student to type their full name (as in their IC) as a
"signature" (required). The typed name is checked against the About Me name only as a **soft nudge** — a forgiving,
case/space-insensitive comparison that shows a warning on mismatch but **never blocks submission**. The signed name +
a server timestamp (`declaration_name`, `declared_at`) are stored on the application as an audit record.

**Alternatives considered:** (a) declaration checkbox only, no signature; (b) require a strict/loose name match before
submit; (c) verify the typed name against the official IC name.

**Rationale:** We have **no access to the official JPN name** — the only thing to compare against is the name the
student themselves typed in About Me, so a strict match would only enforce self-consistency while frustrating genuine
students over `bin`/`binti`, spacing, or middle names. The real value of the typed signature is (1) the deliberate act
of assent — friction that a checkbox lacks — and (2) an auditable attestation record (who signed what, when). Both are
delivered without pretending to verify identity. True identity verification is the job of the deferred Vision OCR /
MyKad-upload step (S13), not this field.

**Trade-offs:** The signature does not prove identity and can't catch impersonation; it catches careless
self-inconsistency only. Many applicants are minors, whose signature isn't legally binding anyway — formal guardian
e-consent already happens later in the shortlisted follow-up flow, so this is a good-faith attestation at apply time.

**Revisit if:** S13 Vision OCR lands (then the signed name can be cross-checked against the OCR'd MyKad name and the
nudge can become a real verification signal), or legal counsel requires a binding e-signature flow.

## Documents: 4 new doc types (choices-only) + combined income-proof card + `documents_done` decoupled from `complete` — Step-4 redesign S4, 2026-05-28

**Decision:** Added four `ApplicantDocument` doc types (`salary_slip`, `water_bill`, `electricity_bill`, `offer_letter`)
via a **choices-only migration** (`0014`, no DDL — recorded on prod as a `django_migrations` row via MCP). The Documents
tab is split into **Required** (IC + results slip) vs **Optional**, with proof-of-household-income presented as **one
visual card accepting any one of STR / salary slip / EPF** (a per-file type selector keeps each upload stored under its
true `doc_type`; multi-file allowed). `application_completeness` gained `documents_done` (IC + results slip both
present), but **`complete` was left unchanged** (still `quiz and details and funding`) — the documents/consent gate is
deferred to S5. `reference_letter` was removed from the student UI but **kept in the model choices**.

**Alternatives considered:** (a) three separate income-proof rows (STR / salary / EPF) instead of one combined card;
(b) a single generic "income proof" doc type losing the STR/salary/EPF distinction; (c) fold compulsory documents into
`complete` immediately in S4; (d) drop `reference_letter` from the model entirely.

**Rationale:** Postgres doesn't enforce `choices`, so adding doc types needs no schema change — recording the migration
row keeps Django's state consistent while sidestepping TD-058 (no `manage.py migrate`, no contenttypes failure). The
combined income card lowers perceived burden (one "proof of income" ask, not three) while the per-file type selector
preserves the distinct types verification needs downstream. Decoupling `documents_done` from `complete` keeps each
redesign sprint independently shippable and avoids a half-built completeness rollup; S5 owns the final
`complete = quiz + story + funding + compulsory-docs + consent`. Keeping `reference_letter` as a valid choice avoids a
non-backward-compatible enum change for a near-zero-cost retention (the referee just moved to the admin verify-&-accept
stage).

**Trade-offs:** `complete` is briefly "true" without the compulsory documents present (acceptable — the pipeline is
dormant and a regression test, `test_complete_not_affected_by_documents_done`, makes the interim state explicit). The
income card's type selector is one extra tap per file vs. three fixed rows. `reference_letter` lingers as a model choice
with no UI.

**Revisit if:** S5's completeness finalise changes how `documents_done` feeds `complete`; or income-proof needs to
become compulsory (then it would join the required-set and the gate logic); or `reference_letter` should be formally
retired from the model in a later cleanup.

## Completeness finalised: `complete` = 5-part rollup + `consent_done` (any active consent) — Step-4 redesign S5a, 2026-05-28

**Decision:** `application_completeness.complete` is now `quiz and story and funding and documents and consent` — the
full five-part gate. Added `consent_done = application.consents.filter(is_active=True).exists()`. This **supersedes the
S4 interim decision** that `complete` excluded documents/consent. `notify_email` is exposed read-only on
`ApplicationReadSerializer` (a declared `EmailField(read_only=True)`) so the applicant's "What happens next" panel can
state where decision emails actually go.

**Alternatives considered:** (a) keep `complete` excluding docs/consent and gate the sponsor stage elsewhere; (b)
gate `consent_done` on the specific consent type `share_with_sponsors` rather than "any active consent"; (c) show the
logged-in user's email in the panel instead of the application's `notify_email`.

**Rationale:** Compulsory documents and consent are genuine prerequisites before a profile is sponsor-ready, so they
belong in `complete`; S4 deferred them only to keep each redesign sprint independently shippable. "Any active consent"
is equivalent today (the consent step records a single type) and robust to the type-string. The application's resolved
`notify_email` is the truthful "where updates go" value (and read-only prevents the read serializer accepting a write).

**Trade-offs:** If a second, independent consent type is ever introduced, `consent_done` would wrongly read as done on
the unrelated consent — at that point gate it on the specific required type. `complete` becoming stricter is the intended
direction; the S4 regression test was updated to the new contract (`test_complete_requires_documents_and_consent`).

**Revisit if:** multiple consent types are introduced (make `consent_done` type-specific), or the sponsor stage needs a
completeness definition distinct from the applicant's.

## AI sponsor-profile: language-aware via a prompt parameter (Tamil input understood, output EN/BM) — Step-4 redesign S5c, 2026-05-28

**Decision:** `generate_sponsor_profile(application, language=None)` resolves an output language (default = applicant
`locale`: en→English, ms→Malay; admin override via an EN/BM selector) and the prompt instructs the model to understand
the student's narrative whether written in **Malay, English, or Tamil** and to write the profile in the target language.
Tamil **output** is deferred to Phase 2. Language is a **prompt parameter only** — not stored on `SponsorProfile`
(no migration). `_build_prompt` was also rebuilt to read the current profile-canonical + story + simplified-funding model.

**Alternatives considered:** (a) store the chosen output language on `SponsorProfile` (a new column/migration); (b)
support Tamil output now; (c) always output English; (d) detect input language and echo it as the output language.

**Rationale:** The profile is **sponsor-facing** and sponsors read EN/BM, so Tamil output isn't needed yet — but B40
students may genuinely write their story in Tamil, so understanding Tamil **input** is the real requirement and is
handled now. Keeping language a prompt parameter avoids a migration and makes enabling Tamil output (or per-sponsor
language) a one-line change. Defaulting to the applicant's locale gives a sensible default; the admin override covers
the sponsor-audience case. Echoing the input language (d) is wrong — a Tamil-written story should still yield an EN/BM
sponsor profile.

**Trade-offs:** The generated language isn't persisted, so "what language was this draft?" isn't queryable (the admin
regenerates if they want another language; `model_used` is recorded but not language). Acceptable while Phase 2 isn't live.

**Revisit if:** Phase 2 needs sponsor profiles in Tamil (flip the deferral — add 'ta' to `LANGUAGE_NAMES`), or the
output language needs to be persisted/filterable (add a column then).

## Expand-contract ordering for destructive migrations (deploy-first, DROP-after) — TD-059, 2026-05-28

**Decision:** For **additive** migrations on this live system (ADD COLUMN with default; widen a CharField choices set;
etc.) the order is **migrate-first** — apply the DDL on prod before pushing the code, so old code keeps reading the new
column as inert and new code finds the column already there. For **destructive** migrations (DROP COLUMN; tighten a
column type; remove a choice the data still uses) the order **inverts** to **deploy-first / drop-after** (the classic
expand-contract pattern): ship code that no longer references the column, wait for the new revision to be live on 100%
traffic, then run the DROP via the Supabase MCP + record the `django_migrations` row.

TD-059 dropped 9 `FundingNeed` amount columns using this ordering. The currently-live `FundingNeedSerializer` exposed
those fields via `ModelSerializer`; dropping the columns first would have made every `GET application` 500 until the
new code shipped. With deploy-first, Django simply ignored the (now-redundant) DB columns until they were dropped.

**Alternatives considered:** (a) blue/green or per-route canary deploys (not set up on this single-revision Cloud Run
service); (b) tombstone the columns first (rename to `_dead_*`) then drop later (extra migration, same risk window);
(c) coordinate a single-window outage to drop simultaneously with deploy (manual, fragile, no real benefit at our scale).

**Rationale:** Cloud Run's single-revision serving means there's no "old and new running side-by-side" window where
either DDL order would be safe — one must complete before the other. Deploy-first is safe because Django ignores extra
DB columns; migrate-first is safe for additive because the new column is inert until written. The TD-058 workaround
(MCP `execute_sql` for the DDL + `django_migrations` row in one transaction) sidesteps `manage.py migrate`'s post_migrate
contenttypes failure on this prod DB. **Pre-drop safety hold:** always re-confirm `SELECT COUNT(*)` immediately before
the destructive DDL — don't trust earlier "0 rows" notes.

**Trade-offs:** Two different orderings to remember (additive vs destructive). A destructive migration leaves the prod
schema *behind* code state for the deploy window (a few minutes) — analytics/dashboards reading the DB directly may
briefly see code-orphaned columns. Negligible at our scale.

**Revisit if:** the deploy infrastructure gains true blue/green (then both orderings become trivially safe), or if a
migration is both additive **and** destructive (model rename / column type change) — at that point think in atomic
pairs: add-new-col → backfill → switch code → drop-old-col, each step its own deploy.

## Ship-with-API-disabled-then-flip pattern for billable external APIs — S13, 2026-05-28

**Decision:** For features behind paid external APIs (Cloud Vision, Gemini, etc.) on this cost-conscious project, the
sequence is: **(1)** build the code with the SDK lazily imported and a graceful-degradation path ("AI service not
configured" / "AI module not installed" → soft fallback rendered in the UI); **(2)** apply any additive migration via
Supabase MCP migrate-first; **(3)** ship the code with the API still **disabled**, so production exercises the
fallback for free; **(4)** **as a separate explicit step after user cost sign-off**, enable the API + grant the runtime
SA the relevant role + run one cheap public-sample smoke (a Google-provided sample image) to verify project-level
provisioning; **(5)** ask the user to do one real end-to-end test through the deployed UI. Used for S13 (Cloud Vision
for MyKad OCR).

**Alternatives considered:** (a) enable API up-front and ship code together — couples cost sign-off to a code-ready
deadline; (b) deploy code + API together but behind a feature flag — adds plumbing for a single-purpose case; (c) keep
the code behind a CLI tool only — defeats the UX benefit.

**Rationale:** The user's project has an RM10/month budget alert and the rule "paid API calls or credits need
approval." Decoupling code-shipping from API-enabling (a) lets the code/tests/migration land safely and verifiably,
(b) exercises the fallback path in production for free, surfacing teething early, (c) makes the cost gate a single,
explicit, easy-to-veto step, and (d) means the public-sample smoke separates "is the API alive at all" from "does my
integration work" — much cheaper to diagnose. Production stays cost-neutral until the explicit flip.

**Trade-offs:** A short window where the feature is "live but inert" — the UI shows the neutral fallback chip until
the API flip. Acceptable when the fallback is honestly worded (S13: "we couldn't read the photo automatically — the
team will check it manually"). If the fallback is *not* a graceful UX state (e.g. a 500 instead of a soft signal),
this pattern doesn't apply and you must enable concurrently.

**Revisit if:** Cloud Run gains true blue/green deploys (then enable + flip atomically), or if the API is free / no
cost gate exists (then enable up-front), or if the feature has no acceptable graceful-degradation state.

## Read-time auto-default for `contact_email` (not a DB backfill) — S14, 2026-05-29

**Decision:** When `profile.contact_email` is blank, `ProfileView.get` returns the auth-user email and reports
`contact_email_verified = true`. The DB row stays untouched. Only an *explicit* student-set contact email writes
to the column (and resets the verified flag, which the existing PUT handler already does).

**Alternatives considered:** (a) one-off backfill — `UPDATE … SET contact_email = email, contact_email_verified = true
WHERE contact_email IS NULL OR contact_email = ''` (574 rows would have been mutated); (b) require contact_email
explicitly during onboarding/profile — adds a step + blocks users with no contact email beyond their login email;
(c) drop the `contact_email` column entirely and only use the auth email — loses the future support for "I want
decision emails sent to my parent's address, not mine."

**Rationale:** The intended product behaviour is *"the auth email is your contact email unless you say otherwise"*.
That semantic is computed, not stored — a backfill would have set 574 rows to a value they didn't choose. With the
read-time fallback, if we later change policy (e.g. require explicit consent before treating auth email as contact),
the fix is one line in `ProfileView.get`. With a backfill, we'd have to disambiguate "they actively chose this" vs
"we wrote it for them" — irreversible information loss. The fallback is also cheaper (no migration, no MCP run) and
naturally handles future phone-signup users (no auth email → no fallback → they fill it in explicitly).

**Trade-offs:** A tiny per-request branch in the GET handler. `contact_email_verified` returned as `true` for
fallback users without a row write — clients that re-PUT the same value through the standard flow would see the
verified flag reset by the existing "verified resets on contact_email change" guard, but in practice the UI shows
the fallback as already-verified so there's no re-PUT. The DB row reads as empty in admin SQL — a small cognitive
gap mitigated by the comment in the view.

**Revisit if:** we add policy requiring opt-in for using auth email as contact (e.g. GDPR-style explicit consent),
or if we observe many users complaining that decision emails go to an unintended address (because their fallback
auth-email isn't the one they monitor).

## Story tab Save also persists address to the profile (single transaction, one button) — S14, 2026-05-29

**Decision:** The /application Story tab's address inputs (street + postcode + city) are submitted via the
existing `PATCH /scholarship/applications/<id>/` (i.e. `ApplicationDetailsUpdateSerializer`), and
`save_application_details` writes them to `application.profile` rather than the application itself. One Save
button writes both the application narrative AND the profile address atomically.

**Alternatives considered:** (a) call `updateProfile` from the Story tab in addition to `updateScholarshipDetails`
— two requests, possible partial failures (story saved, address didn't), needs frontend retry/rollback logic;
(b) make address fields on the application a true second source of truth (`ScholarshipApplication.address` columns)
— violates the profile-canonical rule (S5c, TD-060 lesson) and forks the data the admin sees in /profile vs the
application detail page.

**Rationale:** Address fields conceptually belong to the person, not the application — a student's address is
the same across cohort years. Keeping the column on `StudentProfile` matches the profile-canonical pattern (S5c).
Routing the write through `save_application_details` preserves the one-button-save UX without introducing dual-write
semantics in the frontend. The completeness rule (`address_done`) reads the profile, so it naturally reflects either
a /apply submit or a /profile edit or a Story-tab save — three writers, one source of truth.

**Trade-offs:** `ApplicationDetailsUpdateSerializer` now accepts fields that aren't on `ScholarshipApplication`,
which is mildly misleading at the type level. Mitigated by a comment on the serializer + `save_application_details`
docstring explaining the side-effect. If we later add another shared profile field that the Story tab needs to
write, the pattern is established.

**Revisit if:** the Story tab grows enough profile-write fields that the side-effect becomes the majority — at
that point it might be cleaner to split into two endpoints (application vs profile delta) so the contract is
explicit. Today the address is the only such field.

## Single-instance doc types: replace on re-upload (not append) — S15, 2026-05-29

**Decision:** For all `ApplicantDocument` doc types EXCEPT the income-proof bundle
(`str`, `salary_slip`, `epf`), uploading a new file deletes any existing rows of the
same type for the same application + sweeps their Supabase Storage blobs in the same
transaction. The list lives in `views.DocumentListCreateView.MULTI_INSTANCE_DOC_TYPES`.
The three income-proof types stay multi-instance because students legitimately
submit several monthly slips.

**Alternatives considered:** (a) make multi-instance a model attribute / choices
field — adds schema + UI complexity for a small rule; (b) require user to click
Remove before Upload — extra step + same orphan-blob risk on Remove; (c) keep all
uploads, surface them all in the admin with "most recent wins" — leaves the admin
to guess which is authoritative, exactly the problem reported; (d) custom UI
"replace" button — confusing because the "Add more" affordance was already wired
to the same endpoint.

**Rationale:** The bug surfaced from real use: a student uploaded multiple IC photos
during testing, leaving the admin with no way to know which to trust. The view-layer
rule (a `frozenset` in the POST handler) is the simplest place that doesn't require
schema/serializer/UI changes. It also lets us patch the related orphan-Storage bug
on `DocumentDetailView.delete` in the same PR — every doc removal now sweeps Storage.

**Trade-offs:** The decision lives in code, not the model, so a future doc type
needs the dev to remember to classify it. Mitigated by the comment on
`MULTI_INSTANCE_DOC_TYPES` listing what's in it and why. Historical orphan Storage
blobs from pre-fix Remove clicks aren't cleaned up automatically — captured as
TD-062 (low priority; storage is cheap).

**Revisit if:** we add a fourth multi-instance doc type and the list grows hard to
reason about (then promote to a model attribute), or if a doc type's semantics
become "versioned" (where keeping history matters).

## Vision OCR fields: surface as evidence text, no automated matcher for address — S15, 2026-05-29

**Decision:** `vision_address` is surfaced verbatim on the admin verify-&-accept
card alongside `profile.address` for eyeball cross-check. No matcher computed,
no verdict pill (unlike S13's `vision_nric_verdict` / `vision_name_verdict`).
The interviewer flags the mismatch manually if it warrants asking.

**Alternatives considered:** (a) postcode-only match indicator (cheap, useful for
"Selangor postcode vs Sabah IC" outliers); (b) full token-set address matcher
similar to `name_match`; (c) Gemini multimodal pass on the IC for structured
extraction.

**Rationale:** Aligns with the post-shortlist vision (`docs/scholarship/
post-shortlist-vision.md`): surface signal for the interviewer to interpret,
don't automate the judgement. Addresses have too many legitimate-divergence
modes (registered IC address vs current rented room; spelling drift between
JPN's records and student's typing) for a binary matcher to be honest. The
interviewer is the right place to ask "is this still where you live?" once.

**Trade-offs:** Admin still has to read two strings and compare. Acceptable
because the strings sit one above the other in the same card. If volume grows
to where this is genuinely painful, the postcode-only match indicator is the
cheapest enhancement (postcodes are deterministic + low-noise).

**Revisit if:** the admin says they want a soft verdict pill (then add the
postcode-only match), or if Phase A deterministic anomaly engine (per the
post-shortlist vision) wants to flag address mismatches as gaps for the
interview agenda (then derive a flag from the same data without committing
a verdict to the IC document row).

## Anomaly serialisation = code + params; copy lives in i18n bundle, not server — S16 Phase A, 2026-05-29

**Decision:** The anomaly engine returns `[{code: str, params: dict}, …]`. The server-side
module holds NO human copy; the frontend resolves `scholarship.admin.anomaly.{code}.fact`
and `.question` from its i18n bundle, interpolating `params` into the matching template
string. Adding a new rule = one Python function + one i18n entry per locale (`fact` +
`question` under the code's namespace) + one test.

**Alternatives considered:** (a) backend renders the fact + question as English strings,
frontend just displays them — simplest but locks the language at the API surface and means
admin language toggles can't switch the flag wording; (b) backend returns a flat dict with
all i18n strings inlined for every flag — heavy payload + no way to edit copy without a
backend deploy; (c) custom DRF field with locale-aware rendering — adds DRF complexity for
the same outcome.

**Rationale:** The admin already has a language toggle (the same `useT()` hook used across
the app). Letting the FE resolve the copy via i18n keys lets a copy tweak land via a web
deploy alone (no api roll), keeps the engine module purely about logic + facts, and means
the same `{code, params}` shape is naturally consumable later by Phase D (Gemini v2) which
will read flags + interview findings together. The params-as-template approach mirrors
React-Intl / FormatJS conventions without their bundle weight.

**Trade-offs:** Adding a rule requires touching two places (Python + JSON) which is mildly
more friction than a backend-only string return. Mitigated by: the i18n bundle is where
ALL user-facing copy lives anyway; we're consistent with the pattern, not bypassing it.

**Revisit if:** we add anomaly-based logic that needs the rendered text server-side (e.g.
Gemini reads a rendered prompt that mentions the anomalies). Then we'd duplicate the copy
server-side (or call FE-render-time templates from the prompt builder). Today, anomalies
are admin-display only — no server-side consumer needs the text.

## Pragmatic guardianship letter — court order OR parent's authorisation letter — S17, 2026-05-29

**Decision:** For minor applicants where the consenting adult is NOT the father or mother
(legal_guardian / grandparent / older_sibling / other_relative), a `guardianship_letter`
document is required alongside the parent_ic. The doc type accepts **either** a
court-issued guardianship order OR a written authorisation letter from the parent — both
count. The lawyer will advise on the final requirement; the working model accepts both
so the flow is reviewable end-to-end.

**Alternatives considered:** (a) strict — only court-issued guardianship order accepted
(legally tighter); (b) ultra-lenient — typed declaration with no doc upload required
(weak PDPA defensibility); (c) require both docs (court order AND parent letter,
belt-and-braces but exclusive).

**Rationale:** B40 reality is parents are often absent — working abroad, deceased,
separated, or simply unable to navigate official channels. Requiring a court-issued
guardianship order would exclude legitimate applicants from grandparent-headed or
older-sibling-headed households. A parent's written authorisation letter is common
Malaysian practice for school enrolment and similar consent flows; it gives reasonable
PDPA defensibility for a community-supported aid programme without making the bar
impossible. The user explicitly named this trade-off (option b in the discussion).
The lawyer review will confirm or tighten.

**Trade-offs:** Lower legal rigour than option (a); a falsified authorisation letter
won't be caught by the system (Vision OCR can read the IC but can't verify the letter's
authenticity). Mitigated by the admin verify-&-accept step (S11a) — a human reads
the letter before accepting. The anomaly engine surfaces the parent_ic Vision verdict
for the admin to eyeball at the same time.

**Revisit if:** lawyers want stricter (move to court-order-only for non-parent paths),
or if real-use shows widespread fraudulent authorisation letters (then add a verification
step — e.g. callback to the parent on a verified phone number).

## View-time enforcement of doc upload prerequisites (defence-in-depth) — S17, 2026-05-29

**Decision:** The Consent POST view enforces the doc upload requirements directly —
returns 400 `parent_ic_required` if a minor's parent_ic isn't uploaded; 400
`guardianship_letter_required` if non-parent + missing letter. The frontend ALSO
pre-checks and shows amber warnings before submit, so the bad path is rare in normal
use. Both layers exist.

**Alternatives considered:** (a) completeness-only — let the consent record but mark
the application incomplete; (b) FE-only gating — disable the submit button when
prereqs missing; (c) view-only gating — let the FE try, surface backend errors.

**Rationale:** Completeness-only (a) silently accepts a consent that's missing
required evidence — bad for PDPA audit trail (the consent row exists but isn't
backed by the docs it attests to). FE-only (b) is bypassable — a determined or
buggy client can POST anyway. View-only (c) has poor UX — the student finds out
about the missing doc only after clicking submit. The combination (FE warning +
backend enforcement) gives both UX clarity and integrity.

**Trade-offs:** Two places to maintain the same rule. Mitigated by: the rule is
single-source on the backend (frontend just reflects what the backend will accept);
if they diverge, the backend wins and the FE warning becomes "harmless" rather
than wrong.

**Revisit if:** we add async upload (file uploaded after consent click) — then
the FE-side pre-check becomes a non-blocking hint rather than a gate, and the
backend gating becomes the only enforcement. Today both are synchronous so the
combination works.

## No "Other" in the relationship dropdown — S17, 2026-05-29

**Decision:** The 6-option relationship dropdown lists `father / mother /
legal_guardian / grandparent / older_sibling / other_relative`. No "Other" /
"None of the above" catch-all.

**Alternatives considered:** (a) Include "Other" with a required free-text field
to describe — gives flexibility; (b) Add a free-text override on top of the 6
codes; (c) Stay as-is — closed list.

**Rationale:** Per user direction. The closed list is itself a legal safety net —
if no option fits, the right path is to route the applicant through
`legal_guardian` (court-appointed) + a letter, which forces the proper paperwork.
Allowing a free-text "Other" risks consenters claiming relationships that don't
have any legal authority over the minor (e.g., neighbour, family friend, uncle
without court appointment), with no clean way for the admin to flag.

**Trade-offs:** Some legitimate-but-unusual cases (e.g., step-parent without
formal adoption) get routed through legal_guardian + letter, which may feel
overwrought. Accepted trade-off — the bar is higher but defensible.

**Revisit if:** real-use shows a frequent legitimate case the 6 codes don't cover.

## Multi-stream subject model + mirrored backend merit pools — S18, 2026-05-29

**Decision:** Changed `SpmSubject` in `subjects.ts` from a single `category` field to a `streams: StreamKey[]` list, letting a subject appear in more than one stream dropdown (e.g. sciences in both Science and Technical) while staying electable. The backend merit pools in `engine.py` (`SCIENCE_POOL`/`ARTS_POOL`/`TECHNICAL_POOL`) were expanded to mirror the frontend exactly and lifted to module-level constants.

**Alternatives considered:** (1) Keep single `category` and pick one stream per subject — can't express the official grouping where sciences sit under both Science and Technical. (2) A separate `stream → ids` overlap map alongside `category` — two sources of truth for the same fact. (3) Derive the backend pools from the frontend at build time — no shared runtime between TS and Python; not worth a codegen step for two small sets.

**Rationale:** The official SPM elective structure is genuinely many-to-many (a technical student takes Bio/Fizik/Kimia/Add Maths as stream subjects too). A `streams` list models that directly. Keeping the derived export names/shapes meant zero changes to the two consuming pages. The backend keeps its own copy because there is no shared TS↔Python runtime; the risk (silent drift causing a stream subject to score on the 10% weight instead of 30%) is mitigated by a code comment on both definitions plus paired tests asserting the counts (jest: 38 arts / 16 technical; pytest: same).

**Trade-offs:** Two hand-maintained copies of the pools that must move together. Accepted because the alternative (codegen across languages) is heavier than the problem warrants, and tests + the linking comment catch drift.

**Revisit if:** the pools change often, or a third consumer of pool membership appears — at that point extract a single language-neutral source (e.g. a JSON the build emits to both sides).

## Hard-gate (400) vs soft-anomaly-flag for parent_ic identity mismatch — S19, 2026-05-29

**Decision:** When the minor flow's typed parent name OR typed parent NRIC does not match
the `parent_ic` Vision OCR values, block the consent POST with HTTP 400
(`parent_ic_name_mismatch` / `parent_ic_nric_mismatch`). FE pre-checks and disables the
toggle to surface the failure inline; backend re-checks as defence-in-depth.

**Alternatives considered:** (a) keep as soft anomaly flags only (current S17 behaviour —
admin sees them in Pre-interview flags card but applicant can still submit); (b) hard-gate
only on NRIC mismatch (deterministic), keep name mismatch as soft flag (token-set match is
fuzzier); (c) hard-gate both as proposed.

**Rationale:** User asked: "It may not be enough for the parent/guardian to type the name
as it is not their account." Soft flags assume a careful admin reviews every Pre-interview
flag; at scale the admin will skim and trust-but-not-verify. Hard-gating both fields at
consent submit means the legal attestation in the DB matches the IC photo in the record
EVERY time, not just when an admin notices. Token-set name match (with parentage-marker
stripping) gives enough leniency for typos / middle-name omissions that legitimate cases
pass; outright different names / NRICs get blocked. The bar for "fraud" goes from "lie
in a text field" to "upload a fake IC document with matching forged name + NRIC" — a much
higher cost.

**Trade-offs:** A small UX cost — a parent who types their name slightly differently from
their IC has to fix the typo. The FE shows red inline text under the field as soon as
the mismatch is detected, so the failure mode is immediate + actionable, not a confused
form submission. Token-set fuzziness covers the most common typo cases (extra spaces,
case, missing middle name).

**Revisit if:** legitimate-mismatch reports come in (e.g. parent's IC has unusual
characters Vision misreads). Could move to a partial-allowance mode (partial → soft flag,
total mismatch → block) but the S17 verdict already supports `partial`, so this is a
one-line adjustment if needed.

## InfoBox component as the convention enforcement mechanism — S19, 2026-05-29

**Decision:** Extracted `components/InfoBox.tsx` (4 semantic kinds: success / info /
warning / block; locked palette `bg-{color}-50 border-{color}-200 text-{color}-800` +
`rounded-lg p-3 text-sm`). All in-form messaging boxes across `/application` now go
through it. Top-of-card section banners (the "You've been shortlisted!" / "All set!"
intros) keep their distinct `rounded-xl p-5` style — different role.

**Alternatives considered:** (a) Keep inline `className` strings, write a comment
documenting the convention — relies on every dev remembering; (b) Tailwind plugin /
@apply layer — heavier infrastructure; (c) the chosen component approach.

**Rationale:** User explicitly named the convention they want enforced
("if so, let's be consistent across the forms"). When a user names a convention, the
right move is to encode it in code, not docs — a component is the cheapest enforcement
mechanism and self-documents via its prop types. The four `kind` values are also the
natural semantic vocabulary (success/info/warning/block) — useful for screen readers in
the future too.

**Trade-offs:** Slightly more verbose at call sites (`<InfoBox kind="info">…</InfoBox>` vs
`<div className="...">…</div>`). Mitigated by being meaningfully shorter than the inline
class strings it replaces. The component is intentionally minimal — no icons, no
dismissible variant, no inline action button — so it stays one tight artefact. Add
variants only when a real use case shows up.

**Revisit if:** we need a dismissible info box, an inline action button inside the box,
or a different size variant — at that point the component grows props. Don't speculate;
let real use drive shape.

## parent_ic as universal compulsory (admin cross-check, not just minor consent) — S19, 2026-05-29

**Decision:** `parent_ic` document is now required for ALL applicants, not just minors.
`documents_done` rule extended to `{ic, results_slip, parent_ic}`. Documents tab renders
the parent_ic card unconditionally. Help text rewritten to explain universal use:
"A photo of your parent or guardian's IC. We use it to verify supporting documents like
STR or EPF that are usually issued in your parent's name. (If you are under 18, your
parent or guardian also signs the consent below.)"

**Alternatives considered:** (a) Keep parent_ic minor-only (S17 behaviour) and add a
soft-flag anomaly when adult applicants upload STR/EPF without a parent_ic — gentler but
makes the admin's cross-check inconsistent; (b) Make parent_ic compulsory only when an
income-proof doc is uploaded — conditional rules add complexity for marginal benefit;
(c) the chosen path — universal compulsory.

**Rationale:** Per user: even for 18+ applicants, the admin cross-checks STR/EPF (which
are typically issued in a parent's name) against the parent's IC to confirm legitimacy.
Without the parent_ic, the admin has to guess "is the surname on this STR the applicant's
parent?" — a clean cross-check turns the guess into a 2-second eyeball. Universal
compulsory is also the simplest mental model for the student ("upload these 3 documents")
and the simplest completeness rule for the backend.

**Trade-offs:** Self-supporting adults with no living parent or estranged-parent
situations would need to upload a substitute (any household-head IC) and explain via the
admin verify step. The admin verify-&-accept gate (S11a) already handles such
case-by-case judgement, so this is an existing safety valve. The change is forward-
looking — at sprint close 12 applications were `submitted` (pre-decision-reveal, still
seeing the "received" status card not the Documents tab), so the new requirement
naturally applies when they're shortlisted, no retroactive complaint.

**Revisit if:** real-use reports show the no-parent / estranged-parent case is common
(could add an "I don't have a parent's IC — explain" alternative path), or if STR/EPF
get phased out as income proofs (less need for the cross-check). Today the assumption
holds.

## Back-end trusts the student's explicit stream subjects for merit (Sec2) — TD-063, 2026-05-30

**Decision:** The SPM merit engine (`prepare_merit_inputs`) now accepts the subjects the
student explicitly studied in their stream/aliran and uses them for Sec2 (the 30% stream
weight), instead of re-deriving the stream from its own copy of the pools. It falls back to
the legacy count-heuristic only when no explicit list is present.

**Why:** The FE/BE pool duplication (TD-063) existed *solely* because the back-end received a
flat `{subject: grade}` dict with no stream label, so it had to guess the stream by counting
which pool held the most subjects — which required `engine.py` to keep its own mirror of
`subjects.ts`'s pools. The two copies could drift (the S18 bug: a dropdown subject missing
from the back-end pool silently dropped from the 30% stream weight to the 10% elective weight).
The student already *tells* the front-end their stream subjects; we were throwing that away.
Passing it through removes the guess.

**Why we kept the pools (didn't delete the second copy):** two data sources have no stream
label — the golden-master fixtures and every profile saved before this change. For those the
back-end must still classify, so the pools survive as a **fallback-only** classifier. The
duplication isn't fully eliminated, but its blast radius shrinks to old/unlabelled data;
for any labelled student the pools are bypassed and the S18 drift bug is impossible.

**Why Sec2 = best-2 of the *full* designated list (not a hand-picked 2):** the differential
audit showed that storing only a subset can *lower* a student's score (if the subset excludes
a higher-grade in-stream subject). Storing the full aliran list (all subjects studied in the
stream) makes the explicit path identical to the heuristic for single-stream students; it
diverges only for genuine cross-stream students the heuristic was mis-classifying, where the
explicit result is the correct one.

**How we proved it safe:** golden master held at exactly 5319 (the no-label fallback is
byte-identical), plus a differential audit (every grade combo both ways) captured as 6 unit
tests in `test_merit_pools.py`. Rollout is forward-safe: unlabelled existing users keep
scoring via the fallback (unchanged) until they next save grades.

**Revisit if:** the fallback path ever needs to die (e.g. all profiles backfilled with a
stream list) — then the pools could finally be deleted and TD-063 fully closed.

## Phase C: post-shortlist funnel — status + hard gate + non-freeze — 2026-05-30

**Decision:** The post-shortlist handoff uses an explicit student "Confirm & submit"
that flips `shortlisted → profile_complete` (a real status + `profile_completed_at`
timestamp), a **hard** accept-gate (admin cannot accept an incomplete profile — no
override), and completion that is **not** a freeze (a `POST_SHORTLIST_EDITABLE`
status set keeps Step 4 + document upload open after confirming).

**Alternatives considered:** (a) passive completion (computed-on-read, no status,
admin badge only) — rejected because admins can't query/filter it and there's no
"I'm done" signal; (b) soft accept-gate with a `force` override — rejected by the
user ("no point accepting a submission that would likely be rejected"); (c)
freezing the form on confirm — rejected because the admin needs to be able to ask
for more documents and the student must be able to add them.

**Rationale:** A real status makes the funnel queryable/filterable and reuses the
existing `?status=` admin filter with zero new code; the hard gate protects the
imminent batch from accidental accept-of-incomplete; non-freeze supports the
request-more-docs loop. The new status also establishes the slot the interview
statuses (`interviewing`/`interviewed`) extend.

**Trade-offs:** A confirmed app whose student later removes a compulsory doc keeps
`profile_complete` status while the accept-gate (which reads *live* completeness)
would block — a mild status/gate divergence accepted for simplicity (no auto-revert).

**Revisit if:** the status/gate divergence confuses admins in practice (then add
auto-revert in `save_application_details`), or real use shows the hard gate traps a
legitimate exception (then reconsider a logged override).

## PartnerAdmin role categories via expand-contract (keep is_super_admin) — 2026-05-30

**Decision:** Added `PartnerAdmin.role ∈ {super, reviewer, viewer}` *alongside* the
legacy `is_super_admin` boolean (backfilled), with an `is_super` bridge property and
a `has_role()` helper, rather than replacing the boolean outright.

**Alternatives considered:** migrate fully to `role` now (drop `is_super_admin`);
or a unified `account_type` table across student/admin/sponsor.

**Rationale:** Several call sites still read `is_super_admin`; expand-contract keeps
them working while new code reads `role`. A unified account table is a large,
unnecessary refactor — student (StudentProfile) and admin (PartnerAdmin) are
separate tables keyed by `supabase_user_id`, and that pattern extends cleanly to a
future Sponsor table.

**Trade-offs:** Two role sources to keep in sync until `is_super_admin` is dropped
(a future TD).

**Revisit if:** all `is_super_admin` readers are migrated → drop the boolean.

## Auth entry: preserve browse-first; sponsor = register-interest — 2026-05-30

**Decision:** The new branded entry (Log in by type + Sign Up chooser) is an entry
*option*, never a gate. The course guide stays browse-first (anonymous quiz/
eligibility/search; NRIC a deferred soft-claim). "Sponsor" is a public
**register-interest** lead capture (`SponsorInterest`), not a self-serve account.

**Alternatives considered:** the proposed marketplace model (force sign-up + NRIC to
enter, like an SME-financing platform); building real sponsor auth + portal now.

**Rationale:** The student side is a public utility, not a two-sided marketplace —
forcing registration would close the open guide and lose anonymous users. Sponsor
login has no destination yet (no Sponsor model/portal — that's a future Phase E), so
a sponsor "account" would be a door into an empty room; a lead capture delivers value
(admin follow-up) without faking a product.

**Trade-offs:** Sponsors get a form, not a login, until Phase E. The chooser is built
so swapping "register interest" for real onboarding later is localised.

**Revisit if:** Phase E (Sponsor model + Sponsorship M:N + `/sponsor` portal + auth)
is scheduled — then the sponsor entry points at the real flow.

## Doc-assist is automatic-on-upload + student-facing, not admin-on-demand — v2.17.0, 2026-05-31

**Decision:** When a student uploads a weak-OCR supporting doc, Gemini extracts its fields automatically and the **student** immediately sees a soft, specific verdict so they can re-upload the right file. The interview gap-spotter, by contrast, is admin-on-demand.

**Alternatives considered:** admin-on-demand extraction (a "re-extract" button on the admin doc list), mirroring the gap-spotter's trigger since both share the same Gemini plumbing.

**Rationale:** The two features serve different users at different moments. Doc-assist's value is *self-correction at the moment of upload* — an admin-on-demand trigger would re-introduce the admin↔student round-trip the feature exists to eliminate. Gap-spotter's value is *admin interview prep*, which only the admin needs and only when interviewing.

**Trade-offs:** Gemini runs on every supporting-doc upload (~$0.001 each) rather than only when an admin asks. Mitigated by guardrails (size/count/hourly throttle) + a cost knob (`DOC_ASSIST_ONLY_WHEN_UNCERTAIN`) that can restrict it to uploads the free deterministic check couldn't resolve.

**Revisit if:** upload volume makes the per-upload cost material → flip `DOC_ASSIST_ONLY_WHEN_UNCERTAIN` on, or move extraction to a debounced/batched job.

## Gemini extracts, deterministic matchers decide the verdict — v2.17.0, 2026-05-31

**Decision:** In both Gemini features the model only *extracts* structured values; the soft verdict (name match / address match / wrong-doc; gap relevance) is computed by the existing deterministic matchers on the extracted values. The model never emits a verdict.

**Alternatives considered:** let Gemini return the verdict directly (e.g. "this is the wrong document, confidence 0.8").

**Rationale:** A model-emitted verdict can be a confident hallucination that wrongly blocks or misleads a student. Keeping the decision in the deterministic matchers means a misread degrades to a soft, correctable nudge, and the verdict logic stays unit-testable in isolation (no model in the assertion path).

**Trade-offs:** The matchers can only decide on fields the prompt was told to extract; a novel signal needs a schema + matcher change, not just a prompt tweak.

**Revisit if:** the deterministic matchers become the accuracy bottleneck (extraction is good but the match rules are too blunt) — then invest in the matchers, not in trusting the model's verdict.

## Throttle the AI, never block the upload — v2.17.0, 2026-05-31

**Decision:** Cost/abuse guardrails cap the *billable Gemini call*, not the upload. Per-file size (8 MB) and per-application count (40) return 400s, but the hourly AI throttle, when tripped, **skips Gemini** and lets the upload + free Vision/deterministic checks proceed (student sees "we'll review this manually").

**Alternatives considered:** block/queue uploads once a rate limit is hit (simpler to reason about, protects cost harder).

**Rationale:** A genuine student near a deadline must never be locked out by a cost-control mechanism. The expensive thing is the LLM call, so that is what gets throttled; the upload itself is cheap and must always succeed.

**Trade-offs:** A burst of uploads in one hour gets the free checks but not the Gemini nudge until the window resets — acceptable, since the admin still sees the doc and the deterministic verdict.

**Revisit if:** abuse (mass junk uploads) becomes real → add a soft per-application/day upload ceiling with a clear message, still never a hard lockout mid-application.

## A gap carries its own dynamic text; only `code` is stable — v2.17.0, 2026-05-31

**Decision:** Interview gaps are stored as `{code, question, why}` with the Gemini-written `question`/`why` shipped inline; only `code` (slugified, deduped) is stable. Anomalies, by contrast, are `{code, params}` whose human text is resolved from i18n on the frontend.

**Alternatives considered:** i18n the gap text like anomalies; or store only a code and re-generate text on render.

**Rationale:** A gap's question is dynamic (model-authored per applicant), so it can't be a fixed i18n string. But interview findings attach a verdict keyed by `code`, so the code must be stable across renders — hence slugify+dedupe+clamp in the engine. This lets the combined findings list merge anomalies (i18n label) and gaps (carried label) into one capture surface keyed uniformly by `code`, with no backend change to interview capture.

**Revisit if:** gaps need to be translated for a non-admin audience → add a translation pass on the carried text, keyed by the stable `code`.

## Phase D final profile is stored separate from the draft, gated on a submitted interview — v2.18.0, 2026-05-31

**Decision:** The Phase-D refined profile lives in new `SponsorProfile.final_markdown`/`final_model_used`/`finalised_at` columns (not an overwrite of the draft), and `AdminFinaliseProfileView` only runs when a **submitted** `InterviewSession` exists.

**Alternatives considered:** overwrite `draft_markdown` with the refined text (single field); or allow refining off a *draft* (unsubmitted) interview session.

**Rationale:** Keeping draft + final separate means the admin can see what changed after the interview and the draft's existing edit/publish path stays untouched. Requiring a *submitted* interview ensures the findings feeding the v2 are final — a draft session's verdicts can still change, which would make the "final" profile a moving target.

**Trade-offs:** The final profile currently has no edit/publish/reader path (TD-067) — it's an admin-visible artefact whose consumer (the sponsor) arrives in Phase E. We accept building the artefact ahead of its reader because it's cheap and the interview work would otherwise be lost; we do NOT build the reader yet (that would be a door into an empty room — see the sponsor-login decision).

**Revisit if:** Phase E — decide whether the sponsor reads `final_markdown` directly or an admin reviews/edits/publishes it first (likely the latter; mirror the draft's edit+publish).

## The raw prose Gemini call is one shared seam (`_call_gemini_text`) — v2.18.0, 2026-05-31

**Decision:** Both `generate_sponsor_profile` (draft) and `refine_sponsor_profile` (Phase-D v2) route their model call through a single private `_call_gemini_text(prompt, target_language)` in `profile_engine.py`; the draft function was refactored onto it with no behaviour change.

**Alternatives considered:** give the refine function its own inline cascade loop (copy of the draft's), as originally written.

**Rationale:** Mirrors `vision._call_gemini_json` for the JSON engines — every prose AI call now mocks by patching one function, so CI has a single, reliable patch point and the model-cascade/error logic lives in one place. The original duplicate-loop approach also had no clean mock point (the draft imported the SDK locally), which is what surfaced the need.

**Trade-offs:** One more indirection between the engine functions and the SDK — negligible.

**Revisit if:** a future engine needs structured (JSON) prose output — then it belongs on the `_call_gemini_json` seam, not this one.

## Rejections use one status + a rejection_category field, not distinct statuses — v2.19.0, 2026-05-31

**Decision:** All four (well, five — incl. the engine 'ineligible' edge) rejection kinds keep `status='rejected'` and are distinguished by a new `rejection_category` field (merit/need/ineligible/interview/contractual). The category drives the decline email and the Review-&-actions visibility.

**Alternatives considered:** introduce distinct statuses (e.g. `rejected_merit`, `not_selected`, `contractual_breach`); or a separate Rejection model.

**Rationale:** `status` already means "where is this application in the funnel"; the *reason* it was rejected is a separate axis. A category field adds that axis without a funnel rewrite, without migrating existing `rejected` rows, and without every status check across the codebase having to learn five new values. The earlier Review-&-actions guard refined cleanly to "hide only the pre-shortlist categories".

**Trade-offs:** Code that wants "was this a post-review rejection?" must check `status=='rejected' && category in {interview,contractual}` rather than read a single status. Acceptable — that check lives in one or two places.

**Revisit if:** rejection grows its own lifecycle (appeals, reinstatement) that needs distinct states — then promote the categories to statuses or a Rejection model.

## Engine rejection buckets are derived; only the human ones are admin actions — v2.19.0, 2026-05-31

**Decision:** merit/need/ineligible are set automatically by the shortlisting engine (it returns a `category` alongside its verdict, persisted at submit). interview/contractual — genuine human judgements — are the only ones with an admin endpoint (`AdminRejectView`/`admin_reject`).

**Alternatives considered:** make every rejection an explicit admin action; or have the admin pick the category for engine rejections too.

**Rationale:** The engine already computed *why* it rejected (academic floor vs income vs hard gate) — re-deriving or re-entering that by hand would be redundant and error-prone. Reserving admin actions for the two buckets the engine genuinely can't decide (was the reviewed candidate good enough; did they complete post-award steps) keeps the human surface minimal and the automatic path free.

**Trade-offs:** The mapping reason-string → category lives in the engine; a new hard-gate reason must remember to set a category (defaults to 'ineligible' generic email if mis-set).

**Revisit if:** the engine gains rejection reasons that don't fit merit/need/ineligible.

## Decline emails are suggestive of the reason, not blunt — v2.19.0, 2026-05-31

**Decision:** The merit/need decline emails hint at the reason ("competitive on academic results" / "directed to students in the greatest financial need") rather than stating it plainly, and never say "you didn't qualify because X".

**Alternatives considered:** a single generic decline for everyone (no disclosure); or blunt, explicit reason statements.

**Rationale:** The user's call — for vulnerable B40 applicants, a generic non-answer is more frustrating than a gentle, honest hint, but a blunt "you weren't poor/strong enough" is needlessly harsh. Suggestive copy threads that: it tells them something real and points them at a next step (apply again / seminars) without a wounding verdict.

**Trade-offs:** Suggestive copy is harder to translate faithfully (the hint must survive in ms/ta) and is a judgement call the user may want to tune. Tamil is a first draft pending refine.

**Revisit if:** the user wants the reason stated explicitly, or wants to drop disclosure entirely.

## Document-help coach is structurally firewalled from admin data, not prompt-trusted — v2.20.0, 2026-05-31

**Decision:** The "Cikgu Gopal" help engine (`generate_document_help`) accepts only `doc_type`, `verdict`, `first_name`, and `target_language` — never an application/profile/`SponsorProfile`/`InterviewSession`/score object. A unit test asserts the function signature is exactly those four parameters. The verdict is derived separately (`verdict_for_document`, which reads the student's own doc/profile) and passed in as a plain string.

**Alternatives considered:** pass the `ApplicantDocument` (or application) into the engine and rely on a strong system-prompt instruction ("never reveal scores or reviewer notes") to prevent leakage — simpler, fewer moving parts.

**Rationale:** A prompt instruction is defeatable (prompt injection, a clever student question, a future prompt edit). If the admin/reviewer data never enters the function, there is nothing to leak regardless of what the model is asked — the guarantee holds by construction and is cheaply testable (assert the signature). This is the inverse of the admin-only gap-spotter wall.

**Trade-offs:** The engine cannot offer richer, context-aware help (it doesn't know the student's story or history) — by design. Any future "smarter" help that needs more context must re-justify the wall.

**Revisit if:** a future help feature genuinely needs more applicant context — then add only the specific student-owned fields, never the reviewer/score surface, and extend the signature test to lock the new boundary.

## Hybrid AI message + deterministic i18n fallback for the coach — v2.20.0, 2026-05-31

**Decision:** The coach shows a warm Gemini-generated message when available, but degrades to pre-written per-verdict i18n copy (`scholarship.docs.help.fallback.*`) whenever the AI is unconfigured, errored, or hourly-throttled. The endpoint returns `source: 'ai' | 'fallback' | 'none'` and the verdict, so the frontend always has something kind to show.

**Alternatives considered:** (1) AI-only — show nothing when the AI is down. (2) Static-copy-only — no Gemini at all, just pre-written per-verdict text.

**Rationale:** AI-only leaves a student staring at a cold chip exactly when they're stuck (AI outages/throttle happen). Static-only loses the warmth/personalisation that motivated the feature. The hybrid keeps the cost on the free tier (fires only on a mismatch, hourly-capped, throttle skips the billable call), guarantees a kind message with zero AI, and means a total Gemini failure is invisible to the student. Mirrors the v2.17.0 "throttle the AI, never block" stance.

**Trade-offs:** Two copies of the "what to say" intent (the AI prompt's guidance + the static fallback strings) must both stay on-tone; the fallback is less personalised (no first name, generic phrasing).

**Revisit if:** AI availability/cost changes materially — e.g. if calls become reliably free and instant, the static fallback could shrink to a single generic line; if cost becomes a problem, lean harder on the static copy.

## Electives get an explicit field, not derive-on-reload — v2.21.0, 2026-05-31

**Decision:** Persist *which* SPM subjects are electives in an explicit `StudentProfile.elective_subjects` JSONField (synced + re-hydrated on login), rather than deriving electives at load time as `grades − core − stream_subjects`.

**Alternatives considered:** derive-on-reload (no migration; compute electives in the browser from the grades dict minus core minus the aliran picks).

**Rationale:** The user chose the explicit field. It records the student's *intent* — a subject can be flagged elective even before a grade is entered, which derive-on-reload (which keys off grade presence) would miss. With the cap now at 7, an unambiguous stored list is also cleaner than re-deriving a larger set each load. It mirrors `stream_subjects` (TD-063), so the pattern is already established end-to-end.

**Trade-offs:** A migration + a field to keep in sync with the grades dict (electives ⊆ grades keys). Derive-on-reload would have needed neither.

**Revisit if:** the field and grades drift apart in practice (e.g. an elective with no grade lingering) — then reconcile on save, or revisit derive.

## No historical backfill of elective_subjects — v2.21.0, 2026-05-31

**Decision:** Existing profiles are left with `elective_subjects = []`; the fix is forward-only.

**Alternatives considered:** backfill by deriving `grades − core − stream_subjects` for existing rows.

**Rationale:** A dry-run showed 485 of 491 candidate profiles have empty `stream_subjects` (it only arrived in v2.13.0), so the derivation can't separate stream subjects from electives — it would mislabel phy/chem/etc. as electives for ~99% of rows. Mislabeling is worse than an empty field; the grades themselves are untouched in the DB, and labels repopulate correctly on the next onboarding save.

**Trade-offs:** Students who entered electives pre-fix won't see them auto-restored on the grades form (their grades are still in the DB, just not labelled as electives). A per-student manual fix is possible if needed.

**Revisit if:** `stream_subjects` coverage rises enough (e.g. after a season of the updated onboarding) that a clean derivation becomes possible for the remaining unlabelled rows.

## Sponsor sign-in via a dedicated one-shot flag, bypassing the student NRIC modal — Phase E Sprint E1 (v2.22.0), 2026-05-31

**Decision:** A sponsor signs in with a **direct Google OAuth** from `/sponsor`, flagged by a one-shot
`KEY_SPONSOR_SIGNIN` (sessionStorage) that `/auth/callback` reads to route back to `/sponsor`. It does **not** add a
`'sponsor'` value to `AuthGateReason` and does **not** open `AuthGateModal`; it never sets `KEY_PENDING_AUTH_ACTION`.

**Alternatives considered:** (1) Add a `'sponsor'` `AuthGateReason` and teach `AuthGateModal` to do Google sign-in but
skip the NRIC-claim step for sponsors. (2) A full separate sponsor auth provider + isolated Supabase client (like the
admin scope). (3) Direct Google OAuth + dedicated return flag (chosen).

**Rationale:** The student auth flow (anonymous → Google → NRIC claim → resume pending action) is delicate and has
been the subject of multiple bug-fix sprints; the shared `AuthProvider`'s resume effect opens the NRIC modal whenever
`KEY_PENDING_AUTH_ACTION` is present after a non-anonymous login. Option 1 would weave a new branch through exactly
that fragile modal. Option 2 is the right answer if/when sponsors need a fully isolated session (as admins do), but
that's heavyweight for E1's shell. Option 3 reuses the existing single `AuthProvider` (a sponsor is just a
non-anonymous Supabase user with no NRIC), and the isolated flag guarantees the student NRIC gate stays dormant for
sponsors — the NRIC-gate **middleware** already whitelists `/api/v1/sponsor/`, so the backend is consistent.

**Trade-offs:** A sponsor shares the student `AuthProvider`, so if a signed-in sponsor navigates to a *student* page,
that page's own `showAuthGate` could prompt for NRIC — acceptable (they're a sponsor; they don't go there). If
sponsors ever need true session isolation or a role-scoped client, promote to option 2.

**Revisit if:** sponsors need an isolated auth client/session (security or multi-role), or a third login scope
(Phase F mentor) makes a shared, generalised "post-login destination" mechanism worth building once.

## Phase E Sprint E1 ships as a portal *shell* with no student data — Phase E Sprint E1 (v2.22.0), 2026-05-31

**Decision:** E1 delivers only sponsor self-registration, admin vetting, and an approved-sponsor portal **shell**
(an "browsing coming soon" panel). No anonymised student data, cards, or profiles are exposed; that is E2, gated on
lawyer review.

**Alternatives considered:** (1) Build sponsor accounts + a first cut of anonymised browsing together. (2) Defer the
whole sponsor portal until the anonymisation/serializer work is ready. (3) Ship accounts + vetting as a standalone
shell first (chosen).

**Rationale:** The earlier "auth before its product is a door into an empty room" lesson said don't build a login
with no destination. E1 gives the login exactly the minimum real destination — the sponsor's own account state and
the admin's vetting queue — without touching any student data, so it ships freely (no PDPA exposure, no lawyer gate)
while the load-bearing anonymisation work (allowlist card/profile serializers, generated sponsor-safe profile) gets
its own focused, lawyer-gated sprint (E2). Bundling them would have put the safety-critical anonymisation under
schedule pressure from the plumbing.

**Trade-offs:** An approved sponsor briefly sees an empty shell (clearly labelled "coming soon"). The Phase-D
`final_markdown` still has no reader (TD-067) until E2 wires it. Acceptable — the alternative risks rushing the
anonymisation guarantees.

**Revisit if:** never for the split itself; the open question (whether the sponsor reads `final_markdown` directly or
an admin publishes a finalised version first) is settled in E2 per TD-067.

## Sponsor auth = isolated Supabase client (mirrors admin) — supersedes E1's KEY_SPONSOR_SIGNIN — Phase E Sprint E1c (v2.23.0), 2026-05-31

**Decision:** Sponsors authenticate through a dedicated, isolated Supabase client (`lib/sponsor-supabase.ts`, own
`storageKey: 'halatuju_sponsor_session'`) + a `SponsorAuthProvider` + `/sponsor/login` / `/sponsor/register` /
`/sponsor/auth/callback`, exactly mirroring the admin auth stack. **This supersedes the E1 (v2.22.0) decision** to do
a direct Google OAuth on the *student* client flagged by `KEY_SPONSOR_SIGNIN`; that flag + its `/auth/callback` branch
were removed.

**Alternatives considered:** (1) Keep E1's approach (sponsor rides the student client, bypassing NRIC via a flag).
(2) A full separate auth backend. (3) Isolated Supabase client mirroring admin (chosen).

**Rationale:** E1c adds **email/password** sign-up/sign-in (the user wanted a real account, not Google-only). The
student client auto-signs-in anonymously and is wired to the NRIC gate / `AuthGateModal`; layering a sponsor
email/password session onto it is fragile and conceptually wrong. The project already settled this exact problem for
admins ("Separate admin auth with isolated Supabase clients", 2026-03-16) — a distinct user-type gets its own client +
provider + session key. Mirroring it gives email/password + Google + reset for free, keeps the sponsor session fully
separate from student/admin, and made the login/register pages near-copies of the admin ones.

**Trade-offs:** A third Supabase client + provider to maintain (student + admin + sponsor). The student `AuthProvider`
still mounts globally (its anonymous sign-in runs on sponsor pages too) — harmless, different storage key. Worth it
for the isolation.

**Revisit if:** the three auth stacks should be unified behind one role-aware client/provider (only if a fourth scope
arrives and the duplication actually bites).

## Email/password primary + Google-then-complete-details for sponsors — Phase E Sprint E1c (v2.23.0), 2026-05-31

**Decision:** A sponsor registers with the full field set (name, email, password, phone, source, PDPA consent) at
`/sponsor/register`. Google is offered as an alternative but, since OAuth yields only name+email, a Google sponsor is
routed to a **"complete your details"** step on the `/sponsor` portal that collects phone/source/consent before the
account is created/completed. The **same** complete-details step also handles the email-confirmation gap (when Supabase
returns no session at sign-up, the row is created after the user confirms + lands on the portal, pre-filled from a
sessionStorage stash). The register endpoint both *creates* and *completes* (updates an incomplete row).

**Alternatives considered:** (1) Google-only (E1). (2) Email/password only (no Google). (3) Collect everything at
sign-up and block Google unless it can supply phone/source (it can't). (4) Email/password + Google, with one shared
complete-details step (chosen).

**Rationale:** The user explicitly wanted the additional info (phone/source/consent) captured *and* Google as an
option. A Google sign-in physically cannot carry those fields, so a post-auth completion step is unavoidable — and the
same step elegantly covers the "no session at email sign-up" case, so there's one code path for "signed in but details
missing" (driven by `/sponsor/me`'s `profile_complete`).

**Trade-offs:** A Google sponsor does two steps (OAuth, then details) instead of one. The register endpoint is
idempotent-but-completing rather than create-only. Both are acceptable and keep the data-capture requirement intact.

**Revisit if:** Turnstile/email-verification policy changes materially, or sponsors should be allowed in without
phone/source (they shouldn't, per the requirement).

## Shared AuthButtons for the logged-out header cluster — Phase E Sprint E1c (v2.23.0), 2026-05-31

**Decision:** The logged-out `Log in ▾ {Student/Sponsor/Partner} | Sign Up` cluster lives in one component
(`components/AuthButtons.tsx`) used by both `AppHeader` and the landing-page nav, rather than duplicating the dropdown
markup. The landing page keeps its own nav shell (gradient, About link) — only the button cluster is shared.

**Alternatives considered:** (1) Replace the landing nav wholesale with `<AppHeader/>` (loses the landing's bespoke
look + the inline About). (2) Copy the dropdown markup into the landing nav. (3) Extract one shared cluster component
(chosen).

**Rationale:** The user wanted the landing buttons to match the dashboard's *without* changing the rest of the landing
page. A shared component guarantees the two stay identical (no drift) and is a smaller change than swapping the whole
header; copy-pasting the dropdown would have been the drift risk the user's "keep them consistent" ask is about.

**Trade-offs:** `AuthButtons` calls `useAuth` internally (for the Student → auth-gate path), so it must render under
the `AuthProvider` — true everywhere it's used. Negligible.

**Revisit if:** the header and landing need genuinely different logged-out actions (then parameterise or split).

## PKCE flow on all browser Supabase clients (session isolation) — v2.23.1, 2026-05-31

**Decision:** Every browser Supabase client — student `getSupabase`, `getAdminSupabase`, `getSponsorSupabase` — sets
`auth.flowType: 'pkce'`. This is the load-bearing mechanism that keeps the three sessions isolated even though they
share an origin and (often) the same Google identity.

**Alternatives considered:** (1) Rely on the distinct `storageKey` per client for isolation (the prior, broken
assumption). (2) Set `detectSessionInUrl: false` on the student client + handle `/auth/callback` with an explicit
`exchangeCodeForSession`. (3) Scope the student `AuthProvider` so it doesn't mount under `/admin` + `/sponsor`.
(4) PKCE on all clients (chosen).

**Rationale:** A distinct `storageKey` does **not** isolate sessions under the supabase-js default (`implicit`): the
OAuth session returns in the URL hash, which any mounted client reads regardless of storage key, and the student
`AuthProvider` is mounted globally — so admin/sponsor Google logins bled into the student session (confirmed in code +
by user repro). PKCE makes the session come back as a `?code=` that requires the verifier stored under the initiating
client's key, so a non-initiating client physically cannot claim it. It's a one-line, library-standard change with no
migration, no redirect-URL change, and it keeps every existing callback working (each client exchanges only the codes
it initiated). Options 2 and 3 are real hardening but bigger and riskier on the critical student login path; they
remain available as belt-and-suspenders (TD-073) but aren't needed for the security property.

**Trade-offs:** The globally-mounted student client still *attempts* (and harmlessly fails) to read the `?code` on
admin/sponsor callbacks — a benign "code verifier not found" with no session claimed (TD-073). One Gmail remains one
Supabase identity; cross-scope authority is still gated per-endpoint by role rows (`StudentProfile`/`PartnerAdmin`/
`Sponsor`), which is correct.

**Revisit if:** the auth architecture moves to a single role-aware client, or a future client genuinely needs implicit
flow (it shouldn't) — in which case the isolation must be re-proven, not assumed.

**Addendum (v2.23.2) — logout side:** PKCE isolates *login*; isolating *logout* needs two more things, now in place:
(1) all three clients call `signOut({ scope: 'local' })` (the default `'global'` revokes every session for the shared
identity server-side, logging the siblings out); (2) the student `clearAll()` bulk localStorage wipe **excludes** the
sibling session keys (`halatuju_admin_session` / `halatuju_sponsor_session`). Together with PKCE, all three scopes are
isolated in both directions. A new auth client must mirror all three (PKCE + local-scope signOut + not being caught by
a sibling's bulk-clear).

## Anonymised sponsor pool: eligibility, generated-not-scrubbed, allowlist boundary, master flag — Phase E Sprint E2a (v2.24.0), 2026-05-31

**Decision:** The sponsor discovery pool is governed by four choices:
1. **Eligibility = anon profile published AND an active `share_with_sponsors` consent** — the existing consent *is*
   the opt-in (no separate toggle). `pool.is_pool_eligible` / `eligible_pool_queryset`.
2. **The sponsor-safe profile is GENERATED, not scrubbed** — `generate_anonymous_profile` uses a *separate* prompt
   (`_build_anon_prompt`) fed only non-identifying inputs (no name/school/referees placeholder exists in it), not a
   redaction of the named profile. An admin generates → reviews → publishes it (regenerating un-publishes).
3. **The hard safety boundary is an allowlist `Serializer`** (`SponsorPoolCardSerializer`/`SponsorPoolDetailSerializer`)
   — plain `Serializer`, explicit derived fields, **zero model passthrough** — proven by planted-identifier leak tests.
4. **A master flag `SPONSOR_POOL_ENABLED` (default OFF → 404)** gates every browse endpoint; the feature ships dark on
   `main` and tests on synthetic data until the lawyer signs off.

**Alternatives considered:** (1) a separate student opt-in toggle on top of consent (rejected — consent already
captures the share intent; the user chose consent = opt-in). (2) Scrubbing the named profile / `final_markdown` with a
denylist (rejected — a denylist re-includes by default; one missed field leaks a real student's identity). (3) A
`ModelSerializer` with `fields=`/`exclude=` (rejected — same denylist failure mode; a new model field can slip
through). (4) Building E2 on a feature branch until lawyer approval (rejected — branch rot; the flag's off-state is a
safe no-op, so dark-on-main is better). (5) Showing richer quasi-identifiers (gender/age/school) on the card (rejected
by the user for the conservative card — re-identification risk).

**Rationale:** This is the one slice where a single mistake exposes a real (often minor) student's identity to an
outside party, so the safety property must be **structural and tested**, not a review promise. Generated-not-scrubbed
means identifiers are never in the pipeline to begin with for the structured fields; the allowlist serializer means a
sponsor sees only what was deliberately added; the admin publish gate is a human backstop for the one soft surface
(the generated blurb, which is fed semi-structured narrative — TD-074b); and the flag means all of this lands and is
exercised safely while the legal gate is pending. The data model already supported it (`Consent` defaulted to
`share_with_sponsors`; `SponsorProfile` already had a publish lifecycle).

**Trade-offs:** The generated blurb is fed the student's free-text narrative, so its anonymity is model-trust +
human-review, not structural (TD-074b — pre-publish identifier scan is the future hardening). The detail endpoint is
keyed by the raw application id (TD-074a). The anon profile is generated from the application form, so it does not yet
fold in Phase-D interview findings (TD-067 nuance).

**Revisit if:** the lawyer requires a different card content / consent structure (adjust the allowlist + consent
version); or real-pool scale needs filters/ref-keyed detail/a structural blurb guarantee (TD-074).

**Addendum (v2.25.0, E2b frontend):** the frontend pairs with the flag by **degrading to the pre-feature state on the
gated error**. When the flag is off the pool API 404s; `/sponsor` catches that and shows the existing "coming soon"
shell (not an error), and the admin card simply shows no published-to-pool state. So the whole feature (both tiers)
ships to prod dark behind the single env flag, and flipping it lights up backend + frontend together. The browse grid
+ `/sponsor/pool/[id]` detail + admin Generate/Publish-anon controls were built mirroring existing patterns (user
chose this over a Stitch round-trip, since the card grid + the admin card are low-novelty reuses).

## Sponsor wallet = final donations + an internal directed-giving ledger (E3) — Phase E Sprint E3a (v2.26.0), 2026-06-01

**Decision:** A sponsor's money is a **donation to myNADI** (final — never refundable to a bank), recorded as a
`Donation`. Their spendable **balance = total donations − allocations that still hold** (offered/active
`Sponsorship`s) — a ledger, not a mutable balance field. A sponsor funds a student **in full** for the admin-set
`award_amount` (1:1, full-or-nothing for now; the per-sponsor-allocation shape is the many-sponsor plumbing for later).
The student (or guardian for a minor) **accepts** within a deadline → `active`, app `sponsored`. Decline/lapse/cancel →
the allocation stops holding, so the amount is back in the sponsor's balance to **redirect within the platform** — no
money leaves myNADI. **Anonymity holds both ways** (the student never sees the sponsor either). E3a touches **no real
money**: donations are mocked; toyyibPay (in) + disbursement (out) + tranches are a later, lawyer + gateway-gated slice.

**Alternatives considered:** (1) Escrow: hold each sponsor's money and **refund to bank** on a timeout (rejected — that
is third-party fund custody, regulated; the user reframed it away). (2) A mutable `balance` field debited/credited with
refund transactions (rejected — drift + audit pain; a ledger is cleaner). (3) Many-sponsor partial crowdfunding with a
funding deadline now (deferred by the user — avoids the "some-but-not-enough" + time-box complexity). (4) Sponsor
visible to the student (rejected by the user — platform intermediates both sides). (5) Real toyyibPay + disbursement in
this sprint (deferred — needs the lawyer's sign-off on the donation/award terms + a gateway account).

**Rationale:** Framing money as a *final donation* + an *internal ledger* turns the regulated "hold + refund" problem
into bookkeeping: the only real-money events are the inbound donation (later) and the outbound disbursement (later,
human-gated), and "return to balance" is just a status change. The 1:1 full-or-nothing rule removes the time-boxed wait
and partial-funding edge cases while keeping the data shape (per-sponsor allocation amounts summing toward an amount)
open to many-sponsor later. Mocking money lets the whole flow + its anonymity guarantees land and be tested on dummy
data, with the regulated rails as a clean follow-on. Acceptance reuses the existing `is_minor` + `record_consent`
guardian gate.

**Trade-offs:** The donate endpoint is a stub until toyyibPay is wired (TD-075a); there are no tranches yet (one block;
TD-075b); the lapse cron isn't scheduled (TD-075c); award/decline emails aren't sent (TD-075e). The donation's
finality (no bank refund) must be explicit in the donation terms + the lawyer's brief.

**Revisit if:** the lawyer requires a different fund-flow or refund policy; or scale needs partial/multi-sponsor
funding, tranche disbursement, or the 2-year reallocation window (TD-075).

## Verification verdict: a deterministic rollup, not a new AI pass — Verification-verdict S1, 2026-06-01
**Decision:** The officer-facing four-fact verdict (Identity/Academic/Income/Pathway) is computed by a pure,
deterministic engine (`verdict_engine.py`) that *composes signals already produced* (Vision matchers, doc-assist
fields, completeness, the anomaly engine). No new Gemini call in the verdict path.
**Alternatives considered:** a Gemini "summarise this application" pass that writes the verdict prose.
**Rationale:** the verdict drives the coordinator's audit and (later) the income recommendation — it must be
auditable, reproducible, and free; a hallucinated verdict is worse than scattered chips. The AI's role stays
upstream (extraction) where a human-decided matcher converts its output to a verdict. The narrative/synthesis AI
pass belongs later (S5, on the draft profile), cached, never in a GET.
**Trade-offs:** the engine can only assert what the deterministic signals support — richer "judgement" prose waits
for S5; under-claims by design (green is expensive).
**Revisit if:** a fact genuinely needs free-text reasoning the rules can't express — then add a *cached* AI pass
feeding the engine, never replacing it.

## Academic comparison by normalised subject name + STR-gated income green — Verification-verdict S1/S2, 2026-06-02
**Decision:** (a) Academic completeness/accuracy compares the slip against the typed grades by **normalised subject
name**, not by grade key. (b) Income reaches `verified` (green) only on a **verified STR document** (uploaded +
name-matched), never the self-declared `receives_str` flag; otherwise the engine `recommend`s and a human decides.
**Alternatives considered:** (a) mapping OCR'd Malay names to a single canonical grade key — but the subject table
has key collisions (`b_tamil`/`bahasa_tamil`, `eng_draw`/`lukisan_kejuruteraan`) so a reverse map is lossy. (b)
trusting the STR checkbox for green.
**Rationale:** (a) the profile and the slip are two independent readings of the same subjects; matching by
normalised name tolerates which internal key the profile happens to use and pinpoints disagreements per subject.
(b) STR is the gold B40 proof but the checkbox is unverified self-declaration; the document is the evidence.
**Trade-offs:** (a) `_SUBJECT_BM` duplicates `subjects.ts` (TD-078). (b) honest under-claim means a genuinely-poor
family with no STR letter sits at `recommend` until a human rules — by design (the human owns the income verdict).
**Revisit if:** the subject taxonomy moves to a single shared source; or policy lets the AI assert B40 from
triangulated proxies without a human.

## Resolution tickets: idempotent verdict-driven generation + no-re-nag — Verification-verdict S3, 2026-06-02
**Decision:** Each unresolved verdict item becomes a discrete `ResolutionItem`. Generation
(`resolution.sync_resolution_items`) is **idempotent**: at most one `source='system'` item per
`(application, code)` (a partial `UniqueConstraint … WHERE source='system'` + an `IntegrityError` catch for races),
created once and **auto-resolved** when the code leaves `verdict.unresolved`; a resolved item is **never re-created**
even if its gap returns (the "no re-nag" rule). Three codes are deliberately excluded from the student queue
(`ic_service_down`, `grades_unverified`, `str_present_unverified`). Officer-raised items (`add_officer_item`) are the
structured successor to the freeform `info_request_note`.
**Alternatives considered:** (a) generating tickets fresh each time (delete + recreate) — loses the student's
in-progress responses and audit trail; (b) recreating a ticket whenever its gap reappears — re-nags the student about
something they already answered; (c) a separate per-code "is this a student action?" flag on the verdict items — but
the exclusion list is small and lives better next to the mapping.
**Rationale:** the verdict is already the single source of truth (structured `{code, params}`), so generation is a
thin map+reconcile; the unique constraint gives idempotency and the no-re-nag rule for free; sync is therefore safe to
call from any surface (upload, delete, student GET, admin GET). Excluding the three codes keeps the student queue to
things the student can actually act on (the whole point of "one short contact").
**Trade-offs:** (a) `sync` **writes inside a GET** (the admin/student serializers persist tickets on read) — a mild
REST impurity, race-guarded but a smell (TD-079). (b) a deleted compulsory document does **not** resurface its
already-resolved ticket — the officer still sees the gap on the verdict, but the student isn't re-nagged (TD-079).
**Revisit if:** re-opening a resolved ticket on a returning gap becomes necessary (then key dedup on open-status +
add a re-open path); or the GET-side-effect causes trouble (then move sync to an explicit POST / a signal on
upload+delete only).

## Verdict audit as additive fields on the application + record-verdict reuses the finalise engine — Verification-verdict S5, 2026-06-02
**Decision:** (a) The officer's verdict-vs-AI audit is captured as **five additive fields on the existing
`ScholarshipApplication`** (`ai_verdict_snapshot`, `officer_verdict`, `verdict_reason`, `verdict_decided_by`,
`verdict_decided_at`; migration `0037`), NOT a new `VerdictAudit`/`VerdictDecision` table. The override-rate metric
is a query over `verdict_decided_at IS NOT NULL` (pure `audit.py` `override_metrics`). (b) `AdminRecordVerdictView`
records the audit and, when `finalise` is set and a draft profile + a submitted interview exist, calls the existing
Phase-D `refine_sponsor_profile` to produce the final profile in the same request — it does not re-derive that logic.
**Alternatives considered:** (a) a dedicated `VerdictAudit` log table (one row per decision); (b) the FE making two
calls (record-verdict, then the existing finalise-profile) instead of one server action.
**Rationale:** (a) an additive `ALTER` deploys via the simpler MCP `execute_sql` migrate-first path and **avoids a
second new-model contenttypes/auth workaround** (TD-058) stacked on `0036`; one snapshot per application (the *final*
officer decision vs the AI) is all the "how good is the AI" override rate needs, and it matches the
profile-canonical "store the decision where it's queried" posture. (b) reusing `refine_sponsor_profile` keeps a
single source of truth for the final-profile generation (cf. the recurring "don't fork the logic" lessons); the
audit is still recorded even when finalise can't run (no draft / no interview), so the two concerns don't couple.
**Trade-offs:** (a) only the latest decision is retained — no full per-decision history (acceptable for the override
metric; add a log table later if an audit trail of *changes* is needed). (b) `record-verdict` does up to two things
in one request (record + optional refine), but each is independently short-circuited and the refine path is the
existing, tested one.
**Revisit if:** a point-in-time *history* of officer decisions is needed (add a `VerdictAudit` log keyed to the
application), or the override metric needs per-reviewer/per-cohort breakdowns the single snapshot can't express.

## Cost-gated Gemini IC second opinion (escalate-on-low-confidence + conservative merge) — Check-1 Identity, 2026-06-02
**Decision:** The IC (MyKad) read stays deterministic-and-free by default; a Gemini **image** re-read is invoked ONLY when the cheap read is low-confidence — defined as a missing core field, OR a read that disagrees with the NRIC/name the student typed in their profile (`_should_gemini_ic`). When it fires, the Gemini result is merged conservatively (`_merge_ic_reads`): Gemini overwrites a core NRIC/name only when it *matches the profile* and the deterministic read did not; the soft address always prefers the cleaner Gemini value. Behind `IC_GEMINI_FALLBACK_ENABLED` (default ON).
**Alternatives considered:** (a) Always send the IC to Gemini (simplest, best accuracy) — rejected on cost (a billable call on every upload for a cost-conscious project). (b) OCR-text-based Gemini (cheaper than image) — rejected because it can't recover a digit the OCR already misread (the headline blurry-NRIC case, #4), which needs the image. (c) Let Gemini's read win unconditionally on escalation — rejected because it lets a hallucinated second read flip a correct deterministic match.
**Rationale:** The escalation criterion is exactly the case where the student would otherwise see a scary mismatch, so spend lands where it earns its keep; the conservative merge keeps the deterministic matchers as the source of truth for the student-facing verdict (the model only *fills/repairs*, never *overrides a good read*). One change improves names, NRIC, and address together.
**Trade-offs:** (a) A genuine mismatch (real different person) still triggers one Gemini call — acceptable, it's rare and the second opinion confirms the mismatch rather than hiding it. (b) Image tokens cost more per call than text, but the volume is bounded by the low-confidence gate. (c) The merge can't fix a case where BOTH reads are wrong AND the profile is also wrong — out of scope (admin verify-&-accept remains the hard gate).
**Revisit if:** Gemini call volume/cost shows up in the budget alerts (tighten the gate or flip the knob off), or marker-less-name volume is high enough that a cheaper text-pass tier is worth adding before the image escalation.

## Results slip is the authoritative grade record (slip wins → fix profile) — Check-1 Academic, 2026-06-02
**Decision:** When a typed grade disagrees with the results slip, the SLIP is treated as the source of truth: Cikgu Gopal tells the student to update their PROFILE grade to match the slip (or re-upload if the photo is blurry), never to change the slip.
**Alternatives considered:** "Just flag, let the officer resolve" (neutral) — rejected because the slip is an official document and the typed grade is self-entered, so the correct direction is unambiguous and self-service is faster.
**Rationale:** The official document outranks self-entry; making the student fix their own profile keeps the data clean before the officer ever looks.
**Trade-offs:** Assumes the slip read is correct; a misread grade would wrongly nudge a profile edit — mitigated because the student sees both values and a blurry slip can be re-uploaded.
**Revisit if:** OCR grade misreads become common enough that "trust the slip" misfires.

## Deterministic band-strip over prompt-engineering (results slip) — Check-1 Academic, 2026-06-03
**Decision:** Strip the SPM grade-band words (Cemerlang/Kepujian/…) from the extracted subject name with a deterministic regex (`academic_engine._split_band`) at read time, and do NOT instruct Gemini to drop them in the prompt.
**Alternatives considered:** A prompt instruction telling Gemini to exclude band words — tried, then reverted: the one slip extracted under it returned an EMPTY results table, and the deterministic strip already makes the instruction redundant.
**Rationale:** A deterministic post-processor is testable, model-independent, and can't degrade the rest of the extraction; a prompt tweak can.
**Trade-offs:** The band map must track the SPM grade scale (10 bands) — small and stable.
**Revisit if:** the SPM band vocabulary changes, or a non-SPM exam slip needs different handling.

## Offer programme is surfaced, not gated — Check-1 Pathway, 2026-06-03
**Decision:** On the offer letter, only Name + IC are hard identity checks; programme / institution / issuer / date / address are surfaced as soft data points, never matched against the declared pathway as a blocker.
**Alternatives considered:** Cross-check the offer programme against the student's declared field/pathway and flag a mismatch — rejected: a student may legitimately receive (and prefer) a different/better offer than what they declared at apply time.
**Rationale:** The offer is settled by the student's confirmation (below), not by agreement with an earlier declaration; blocking on programme drift would punish a normal, good outcome.
**Trade-offs:** The system can't auto-detect an "off-plan" offer — acceptable; the officer sees the surfaced programme and the interview covers intent.
**Revisit if:** sponsors require the funded programme to match a pre-approved field.

## Final pathway is confirmed by the student, AI-raised, no officer — Check-1 Pathway, 2026-06-03
**Decision:** When an offer's identity matches, the SYSTEM auto-raises a `pathway_confirm` Action-Centre query; the student's Yes writes the offer's programme+institution to `chosen_programme` and stamps `pathway_confirmed_at` (→ Pathway verdict 'verified'). No human officer raises it.
**Alternatives considered:** (a) An officer manually asks at interview — rejected: it's deterministic and self-service, within the existing query window. (b) Auto-set chosen_programme from the offer without asking — rejected: the student must own "this is my final choice" (they may upload a better offer later).
**Rationale:** Rides the existing ResolutionItem rails (system-raised, post-submission gated); confirmation is the student's to give and is cheap to capture.
**Trade-offs:** Needs a confirmed-state column (`pathway_confirmed_at`) so the verdict doesn't depend on resolution items (which depend on the verdict) — one additive migration.
**Revisit if:** a student needs to switch their confirmed pathway (re-confirm refreshes the snapshot; a full "unconfirm" flow is not built).

## Documents organised by the four verification facts — 2026-06-03
**Decision:** Group documents (student tab + officer drawer) and order the verdict by the four facts in one fixed order — Identity, Academic, Pathway, Income — and place the parent/guardian IC under Income (it confirms the earner the income docs are issued to).
**Alternatives considered:** Keep the Required/Optional split (student) and parent-IC-under-Identity (officer) — rejected: a fact-aligned layout makes "what proves what" obvious and matches the verdict the officer audits.
**Rationale:** One invariant — student sections == officer groups == verdict order — is easier to reason about and keeps the two audiences consistent.
**Trade-offs:** "Income (compulsory)" is a section-level summary while a utility bill inside it is optional; the per-card explainer carries the nuance.
**Revisit if:** the fact model changes (e.g. Income splits into income vs. relationship once that engine is built).

## Academic ± grade difference degrades to 'uncertain', never a confident mismatch — Check-1 Academic, 2026-06-03
**Decision:** When the slip's letter and Malay band disagree, OR the typed and read grades differ by only ± (same base letter, e.g. A+ vs A), the academic check reports `uncertain` ("Please check", amber) instead of a confident `mismatch`. Results-slip extraction reads the image (Gemini multimodal), not flat OCR text.
**Alternatives considered:** (a) Trust the OCR'd grade and flag a hard mismatch — rejected: OCR consistently drops the '+'/'Ter-' under watermarks, producing confident-but-wrong "you typed A+, slip says A" feedback. (b) Keep flat-text extraction — rejected: it scrambled A↔A+ across adjacent science rows (the grade SET was right, the row ASSIGNMENT wrong).
**Rationale:** The system must never confidently tell a student they're wrong on a signal it can't trust; an honest "check this by eye" preserves credibility and routes the call to the officer.
**Trade-offs:** A genuine A+/A error now reads amber rather than red, so the officer must eyeball it — accepted; the OCR can't distinguish the two reliably anyway.
**Revisit if:** a higher-fidelity grade OCR (or a structured slip feed) makes the '+' reliable.

## Pathway confirm only on a real offer-vs-declared clash (lenient matcher; editable self-edit deferred) — Check-1 Pathway, 2026-06-03
**Decision:** Replace the always-ask `pathway_confirm` with a lenient matcher (`offer_pathway_match`) comparing the offer's programme+institution against the declared pathway. Match / nothing-to-compare → Pathway verdict 'verified' (no nag). A genuine clash (disjoint distinctive place/field tokens) → the reframed confirm query → the student's Yes realigns the record. The editable "Your chosen study" self-edit surface in Step 3 Funding is deferred to Phase 2.
**Alternatives considered:** (a) Keep asking on every valid offer — rejected: nagging a student whose offer already matches their declaration is pointless (the user's objection). (b) Build the editable self-edit surface now (option b) — deferred: the matric/STPM institution picker in /apply is a stub, so the most common case would be greenfield; the system-driven Check-2 reconciliation handles institution-mismatch + sui-generis without it. (c) Strict string match — rejected: catalogue names and printed offer wording differ in harmless ways ("KM Melaka" vs "Kolej Matrikulasi Melaka").
**Rationale:** Lenient + layered (soft Check-1 nudge, enforced Check-2 confirm) reconciles every case while never blocking and never nagging on a match; the offer is the evidence, the student owns the final choice.
**Trade-offs:** A pure-abbreviation declared institution with no shared place token could false-flag a clash — only a soft nudge + confirm, the student's Yes realigns. The self-edit (let the student fix their declaration directly) waits for Phase 2.
**Revisit if:** real-use shows abbreviation false-flags (add an abbreviation map), or students ask to edit their declared pathway directly (build the Phase-2 editable Funding surface).

## Orientation-robust slip parse via GATED de-rotation — Check-1 live-testing fixes, 2026-06-04
**Decision:** Capture a per-word baseline angle in `_vision_words`; in `academic_engine._group_rows` estimate the slip's
median text angle and, **only when |θ| ≥ 25°**, de-rotate every word centroid before clustering rows. Upright slips
(|θ|<25°) are left exactly as before. Row tolerance is derived from the inter-row gap so it scales to a 4000px photo.
**Alternatives considered:** (a) always de-rotate by the measured angle (tried first — broke upright slips via OCR
angle-noise); (b) snap to ±90° (loses the keystone correction — a tilted slip is ~89°, not exactly 90°); (c) OpenCV
homography pre-processing before Vision (heavy dependency + fragile auto corner-detection); (d) Google Document AI
(per-page cost + new integration).
**Rationale:** The deterministic parser is correct whenever it runs — the only failure was that it *ran* only on
upright slips. Gated de-rotation makes it run on rotated/keystoned photos without touching the upright path, using data
we already had (Vision word boxes). No new dependency, no per-page cost, deterministic.
**Trade-offs:** A mild real tilt (5–20°) is treated as upright (below the gate) and not corrected — acceptable because
no such fixture exists and the gate's job is to protect upright slips from noise. Validated against four real fixtures
(upright ×2, rotated-90°, rotated-90°+keystone-Type2).
**Revisit if:** a real slip arrives tilted within the 25° dead-band and misparses, or a third slip format appears — then
lower/tune the gate against a new fixture, never against the live UI.

## Income evidence — two-track wizard, relationship proof common to both — Income Check-1, 2026-06-04
**Decision:** A guided wizard collects three answers (route: STR|salary, earner: father|mother|guardian, work status)
and `income_engine.income_requirements` turns them into a dynamic compulsory/optional document list. The **earner
identity + family-relationship proof** (father=student-IC patronymic match, mother=Birth Certificate, guardian=letter)
is COMMON to both routes; only the income *evidence* differs (STR doc vs salary slip+EPF / EPF-only / utility bills).
**Alternatives considered:** (a) keep the static income card + a free-form "upload what you have" (the old behaviour —
no identity/relationship check, weakest fact); (b) one giant conditional form; (c) a separate top-level Income tab.
**Rationale:** the wizard shows each family exactly the documents IT needs (no guessing), and a pure FE mirror
(`lib/incomeWizard.ts`) keeps the student's checklist identical to the officer verdict. In-Documents (not a new tab)
keeps the 5-step flow.
**Trade-offs:** more questions up front; the wizard answers must be walked before the verdict can assess (an
un-walked app reads `income_earner_undeclared`).
**Revisit if:** the question count grows unwieldy (then promote to a "5. Income" tab), or multi-earner households need
more than one earner block.

## Income never-block — `recommend` + interview flag, not a hard gate — Income Check-1, 2026-06-04
**Decision:** A genuinely poor family that cannot produce formal proof (non-working/informal earner, no EPF) is NOT
blocked. The verdict returns `recommend` + a soft `income_unverified_needs_interview` signal that flows to the interview
gap-spotter; a human confirms via household size, dependents, lifestyle and the burden signals.
**Alternatives considered:** hard-require an income document for everyone (S23 behaviour) — rejected: it excludes the
exact families the B40 programme exists for.
**Rationale:** informal income is the B40 norm; the deterministic layer surfaces the concern, a human makes the
subjective call.
**Trade-offs:** more interview judgement load; not document-auditable for those cases.
**Revisit if:** abuse appears (then tighten the soft floor, e.g. require both utility bills + a declaration).

## Salary income route = MULTIPLE working members, tagged docs, siblings via shared patronymic — Income Check-1 multi-earner, 2026-06-04

**Decision:** The salary (non-STR) income route is a **multi-select** of working household members
(father/mother/guardian/elder brother/elder sister), each contributing their own IC + (optional) salary slip + EPF.
Documents are tagged with a `household_member` column on `ApplicantDocument` (reusing the existing `parent_ic`/
`salary_slip`/`epf` types); single-instance is per `(doc_type, household_member)`. Relationship proof is parent-grade
for everyone: **father/elder brother/elder sister all verify via the SAME student-IC patronymic** (siblings carry the
same father's name), mother via birth certificate, guardian via letter. Verdict: every IC present + every relationship
confirmed + ≥1 payslip/EPF → `verified` (document DATA verified; the income AMOUNT / per-capita B40 test is a later
sprint, I4); IC present + no financial doc (informal) or an unprovable relationship → `recommend` + interview flag
(never blocks); a missing IC/relationship doc → `gap`. The **forced non-earner-parent EPF was dropped**. STR route
unchanged. Migration `0040` (additive). Migrate-first; `salary_apps=0` on prod so no backfill.
**Alternatives considered:** (a) keep single primary earner + a free-text "who else works" + one shared multi-file
"extra income proof" box (leaner; non-primary docs human-reviewed, not machine-matched) — user chose the full
per-person slots. (b) ~15 new per-member doc types instead of a `household_member` tag — rejected (doubles the OCR +
verdict wiring; the tag reuses all existing machinery). (c) per-member relationship proof for siblings (their own birth
cert) — unnecessary once we saw siblings share the father's patronymic. (d) keep forcing both parents' EPF — dropped
(EPF only exists for formal jobs; near-zero signal for informal B40, confusing for homemakers).
**Rationale:** real B40 households have several earners; the multi-select is honest. The shared-patronymic insight
closed the borrowed-payslip hole for siblings with zero extra documents. "Verified = document data" keeps the human in
charge of the income *amount* call (consistent with the B40 engine) while letting identity/relationship go green.
**Trade-offs:** up to ~17 cards for a 5-earner household; two working elder brothers can't both be represented (one
slot); `earner_work_status`/`household_other_earners` columns + `q2`/`q3`/`q4`/`work` i18n keys now orphaned (kept,
deprecated). **Evolves the 2026-06-02 "human owns the non-STR income verdict" decision (L1787):** the document-data
verdict can now reach `verified`; the income amount judgement still cannot (out of scope here).
**Revisit if:** households routinely have >1 working sibling of the same gender (then model brother_1/brother_2 or move
to a `household_member` free-list), or when I4 lands (then "verified" must also clear the amount test).

## Income "verified" now requires the per-capita AMOUNT test (I4) — read from documents, never auto-rejects — Income Check-1 multi-earner, 2026-06-05
**Decision:** On the salary route, the Income tile reaches `verified` only when the income **amount** also clears the
B40 line, computed *from the documents*: sum each ticked earner's salary-slip **gross** (or, when there's no payslip, an
estimate of ≈24% of the EPF **monthly contribution**) → **per-capita** = sum ÷ `household_size` → compare to the
cohort's `per_capita_ceiling` (RM1,584, the same line the shortlisting engine uses). Below the line *and* the cluster
adds up → `verified`; **at/above** the line → `recommend` + `income_above_b40_line`; unreadable / informal / no
household size → `recommend` + interview. **Never auto-rejected** — a human always places the at/above and the
unprovable cases.
**Alternatives considered:** (a) keep "verified = identities + relationships only" and leave the amount entirely to the
officer (the 2026-06-04 scope); (b) trust the student's *declared* household income instead of reading it from docs;
(c) hard-reject above the line.
**Rationale:** the amount is the actual B40 test — a green tile that ignored it was misleading. Reading it from the
uploaded payslips/EPF (not the declared figure) keeps the verdict evidence-based and consistent with how the slip data
is already extracted. The EPF 24% fallback recovers an income signal when there's no payslip but a contribution exists.
Never-rejecting preserves the standing "income never blocks a genuinely poor family" rule — at/above is a *recommend*,
judged at interview, because per-capita-from-docs is an estimate (informal top-ups, irregular pay, partial months).
**Trade-offs:** the per-capita is only as good as the extracted amounts; a household that under-uploads payslips can
read as *below* the line. Accepted because the direction of error (toward `verified`/`recommend`, never a silent reject)
is safe, and the officer sees the cluster.
**Revisit if:** the cohort ceiling model changes, or extraction confidence on amounts proves too noisy (then widen the
"unreadable → recommend" net, or weight EPF vs payslip differently).

## Income verdict must become document-first, not wizard-route-first (reframe surfaced at close) — Income Check-1 multi-earner, 2026-06-05
**Decision:** Recorded as a **direction for the next sprint (TD-085)**, not yet built: the income verdict should start
from the **documents actually in the drawer** (what income proof exists — STR / salary slip / EPF, tagged or not — and
which parent ICs are present) and use the wizard answers (route / earner / member tags) as **hints, not hard gates**.
**Alternatives considered:** keep the current wizard-route-driven verdict and instead (a) force STR recipients to
re-upload as the right type, or (b) only backfill the route/earner of legacy apps.
**Rationale:** live testing (app #21) showed a confirmed STR recipient who uploaded the father's salary slip getting a
red "no proof of income" because the STR branch only accepts an `str` doc — the verdict trusts the declared route over
observed evidence. The whole pipeline, moreover, submitted *before* the wizard, so 6 apps have no route/tags at all. A
document-first verdict fixes both the STR-with-salary case and the legacy cases uniformly; forcing re-uploads or
route-only backfills fixes neither cleanly.
**Trade-offs:** a document-first verdict is more permissive about what counts as proof and needs careful per-capita /
relationship guards so a stray document can't green a tile. Accepted; that's the next sprint's scope.
**Revisit if:** the document-first rewrite proves to mis-assemble multi-earner clusters (then re-introduce the wizard
tags as a tie-breaker rather than dropping them).

## Consent/submission gate v2 — route-aware + strict; "never-block" only at the verdict — TD-085 S1, 2026-06-05
**Decision:** To give consent (and submit), a student must upload exactly what their income ROUTE requires plus a now-
compulsory offer letter — STR route: STR + earner IC + (mother→BC / guardian→letter); salary route: each selected
member's IC + salary slip (EPF does NOT substitute) + rel doc. The gate is sourced from the wizard's own
`income_requirements` (`services.income_doc_blockers`), not a parallel re-derivation. Already-submitted apps are
grandfathered (strict bar keyed on `profile_completed_at IS NULL`); the rest keep the old looser bar so
`revert_if_profile_incomplete` never rolls them back.
**Alternatives considered:** keep the old "any one of {str, salary_slip, epf}" flat rule; allow EPF to substitute the
salary slip; make the lock/strictness retroactive to the 6 submitted apps; build a document-first verdict that ignores
the route instead of a strict route-aware gate.
**Rationale:** the route is the user's authoritative model (wizard picks it; the student switches routes if they can't
supply a route doc). A strict route-aware gate makes the uploaded documents match the declared route, which is exactly
what a document-first verdict was invented to paper over — so the gate makes document-first unnecessary (it was dropped).
Sourcing from `income_requirements` keeps the gate and the student checklist (and the eventual officer panel) in
lockstep. Grandfathering avoids disrupting already-submitted families (resolved at interview).
**Trade-offs:** "never-block" no longer protects a family that genuinely can't produce a route document at the SUBMISSION
stage — it now lives only at the officer/interview verdict (the user accepted this; informal earners use an official
income-verification letter as their salary slip, whose AMOUNT is then manually verified). Two enforcement bars
(strict / grandfathered) coexist until the 6 submitted apps clear.
**Revisit if:** the informal-no-document family proves common enough to need a deliberate sub-path, or the two-bar
grandfather logic outlives the 6 apps (then collapse to one strict bar).
**Supersedes:** the "Income never-block — recommend + interview, not a hard gate" decision (Income Check-1) AT THE
SUBMISSION LAYER; and reverses the (2026-06-05) "Income verdict must become document-first" reframe.

## Officer document row = coloured fact-labels + a facts-derived badge (movable relationship) — TD-085 S2, 2026-06-05
**Decision:** Each document row in the officer cockpit shows the LABELS of the facts that document provides
(`officerCockpit.documentFacts`), each coloured by its own sub-verdict (🟢 verified / 🟡 partial / 🔴 not), read from the
per-fact `*_check` serializer fields. The row's aggregate badge (`documentPill`) is the ROLL-UP of those fact colours.
The relationship fact is MOVABLE — it sits on a father/elder-sibling IC (shared student-IC patronymic), on the birth
certificate for a mother, on the guardianship letter for a guardian; never on a mother's/guardian's IC. The income
section renders `officerCockpit.incomeDocLayout` — route+selection-aware Required→Optional ordering (reusing
`incomeWizard`) with placeholder rows for missing compulsory docs.
**Alternatives considered:** keep the old single-badge-per-row + grey extracted-values line; compute a fresh per-doc
verdict in the cockpit instead of reading the student-facing `*_check` fields; show the relationship on every earner IC.
**Rationale:** the per-fact checks already arrive on the admin response (documents are serialised by
`ApplicantDocumentSerializer`), so reading them keeps the cockpit and the student checklist in lockstep (no parallel
re-derivation). Deriving the badge from the facts removes the "earner IC always Unread" bug for free. The movable
relationship reflects how the relationship is actually proven (patronymic vs BC vs letter). Reusing `incomeWizard` for
the income layout means the cockpit, the gate, and the student wizard all agree on what's compulsory.
**Trade-offs:** the cockpit now depends on the `*_check` field shapes + the admin serializer surfacing the income wizard
answers (an admin-serializer allowlist add). The fact labels replace the extracted-values summary line (values move
behind "View"). Legacy docs whose checks haven't run show grey/unread facts until re-read.
**Revisit if:** the per-fact check shapes change (the fact map in `documentFacts` must move with them), or a future
document type needs a fact set not yet mapped.

## One Cikgu Gopal per income cluster, anchored to the slot (not the document) — Sprint Gopal-polish, 2026-06-06
**Decision:** For the income fact (the one *cluster* fact), the student-facing coach renders ONCE per earner at the foot
of the cluster (after the relationship-proof card: father→IC, mother→BC, guardian→letter; per ticked member on the
salary route), fed by `income_cluster_advice` via a dedicated `GET scholarship/income/<member>/help/` endpoint. The
per-file coaches for cluster docs (`parent_ic`/`str`/`salary_slip`/`epf`/`birth_certificate`/`guardianship_letter`) are
suppressed; the STR-currency + "add the IC" nudges that used to live on separate rows are folded into the one voice.
**Alternatives considered:** (a) keep the per-document coaches (status quo — up to 3 Gopals in one cluster, jumping
position as files arrive); (b) anchor the coach on the IC document (the old `cluster_status`-on-parent_ic behaviour —
but it can't speak before the IC is uploaded, and competes with the STR/payslip nudges).
**Rationale:** Income is a cluster, unlike the single-document Identity/Academic/Pathway. Anchoring to a POSITION (the
cluster foot, always rendered once the wizard is answered) — not a document — means the coach speaks from the first
uploaded doc and stays put as more arrive, exactly mirroring the officer's per-earner verdict. The per-file coloured
chips stay for instant feedback; only the coach consolidates.
**Trade-offs:** A second help endpoint + an FE component + a client-side cluster-doc grouping (`clusterDocsFor`). The
per-doc `verdict_for_document` still returns income verdicts in isolation (relied on only by suppression), so a future
income doc card rendered WITHOUT `suppressCoach` would double-voice — a small latent coupling.
**Revisit if:** the income wizard's cluster structure changes (the anchor rule + `clusterDocsFor` must move with it), or
a non-cluster income doc (e.g. a standalone utility bill) needs its own coach again.

## "Income too high" is NOT surfaced in the student coach — Sprint Gopal-polish, 2026-06-06
**Decision:** The income cluster coach never tells the student their family income looks too high (the I4 per-capita
ceiling). That signal stays at the officer verdict (`recommend` → interview), never in Gopal.
**Alternatives considered:** Include it in the cluster-coach precedence (it was in the proposed order the user approved).
**Rationale:** It is not a document fix — there is no action the student can take — and a coach that says "your income
looks too high" cuts against the programme's never-block / don't-discourage stance. The officer + interview own the
amount judgement.
**Trade-offs:** The student gets no early signal that their per-capita is over the line; they learn it (gently) at
interview. Accepted — that is the correct, humane place for it.
**Revisit if:** policy changes to make income-amount a student-visible gate (it currently is never-block).

## Utility "Reasonable" needs both bills; high consumption is amber, never red — Sprint Gopal-polish, 2026-06-06
**Decision:** The cockpit utility-bill "Reasonable" fact is a verdict only when BOTH water + electricity are present
(combined per-capita vs RM25/RM40). With one bill it greys out with a "water/electricity only" note. Above the RM40
ceiling it shows AMBER, not red.
**Alternatives considered:** judge "Reasonable" on a single bill; show red for high consumption.
**Rationale:** Water alone is a weak, flat signal (cheap across all households) — judging on it falsely greens almost
everyone. A soft B40 proxy must never scream red (red elsewhere = "not verified / mismatch"); amber = "needs a look".
Greying-with-a-reason on one bill is honest about *why* we can't judge, vs hiding (which reads as "all clear").
**Trade-offs:** Officer must request the second bill to get a "Reasonable" verdict; high consumption is softened to amber.
**Revisit if:** the programme wants utility consumption to be a harder signal, or a single-utility household is common
enough that one bill should suffice.

## reminder_anchor_at as a separate clock knob (not shortlisted_at) — Sprint application-reminders, 2026-06-06
**Decision:** The completion-reminder cadence counts from a dedicated `reminder_anchor_at` field, not directly from
`shortlisted_at`. New shortlists set it to the invitation time (in `release_decision`); the one-time launch backfill set
the in-flight cohort to *today − 2 days*.
**Alternatives considered:** key the cadence directly off `shortlisted_at`.
**Rationale:** Keying off the real shortlist date would have fired a sudden "final warning" (or instant close) at launch
for anyone shortlisted weeks earlier — unfair for a reminder promise that didn't exist when they were shortlisted. A
separate anchor decouples "when reminders count from" from the audit timestamp, makes the launch cutover a one-line
backfill, and gives a re-anchor lever (e.g. an admin grace extension) without touching history.
**Trade-offs:** one extra column; a back-dated anchor must be paired with a burst-proof sender (one stage/run) so it
doesn't fire R1–R4 at once.
**Revisit if:** the programme wants reminders to reflect the literal shortlist date with no cutover grace.

## Partial unique constraint (exclude 'expired') enables restart at the DB layer — Sprint application-reminders, 2026-06-06
**Decision:** The per-(cohort, profile) `unique_application_per_cohort` constraint is now PARTIAL —
`condition = Q(profile__isnull=False) & ~Q(status='expired')` — so an auto-closed application never blocks a fresh one.
**Alternatives considered:** (a) relax only the create-VIEW guard (`.exclude(status='expired')`) — but the DB constraint
still blocks (IntegrityError); (b) reuse/reset the expired row in place — messier (lingering documents/consent, muddies
history).
**Rationale:** "Restart the whole process" means a genuinely new application row; the partial index lets the new row
coexist with the archived `expired` one while still forbidding two LIVE applications per cohort/profile. The view guard +
the DB constraint must agree.
**Trade-offs:** the constraint swap is a real migration op (drop/recreate the partial unique INDEX), not pure ADD COLUMN;
multiple historical rows per (cohort, profile) are now possible (all but one `expired`).
**Revisit if:** a per-(cohort, profile) `.get()` is introduced anywhere that assumes exactly one row.

## Earner IC card asserts proof-match, not relationship — relationship is the birth cert's job — Sprint income-card, 2026-06-06
**Decision:** On the student's income earner-IC checklist, the IC No + Name now show whether they **match the cluster's
income proof** (the STR recipient, or the salary-slip/EPF identity) — green "Matches the STR document" / red on a clash.
The earner-to-student **relationship** is no longer asserted on the IC card; instead a new cluster verdict
`income_rel_doc_needed` makes Cikgu Gopal nudge for the relationship document (birth certificate for a mother,
guardianship letter for a guardian) once the IC is in, then go silent.
**Alternatives considered:** (a) keep showing the relationship status on the IC card (the old behaviour) — but the IC
alone can't prove a mother/child link, so it showed a perpetual "We'll review this"; (b) a separate relationship row on
the card — clutter, and still not the IC's evidence to give.
**Rationale:** the question a student is answering when they upload an earner's IC is "is this the right person for the
income doc?" — so the card should answer exactly that. The *relationship* is evidenced by a different document, so it
belongs to that document's step, voiced once by the cluster coach.
**Trade-offs:** the relationship signal is now a Gopal nudge rather than a row, so a student who ignores Gopal sees less
about the missing birth cert on the card itself (the consent gate still blocks submission, so it can't be skipped).
**Revisit if:** we add an inline per-row relationship indicator, or the birth-cert/guardianship requirement changes.

## The doc-help engine gains a non-sensitive `context` param (member/doc labels, never a model object) — Sprint income-card, 2026-06-06
**Decision:** `help_engine.generate_document_help` now takes an optional `context` dict of **flat, non-sensitive**
strings (member label, income-document label, relationship-document label). It feeds a `_specifics_block` in the prompt
so the income coach names the real earner + document instead of a hardcoded "father's payslip" example. The structural
firewall test was updated to allow exactly this one extra param and assert (in its docstring) that `context` is never a
model object.
**Alternatives considered:** (a) keep the 4-arg firewall and live with generic copy — but the copy was factually wrong
when the earner wasn't the father; (b) pass the `application`/`member` objects in — rejected, that's exactly the leak the
firewall exists to prevent; (c) branch the copy per earner inside the engine — duplicates the member taxonomy the view
already has.
**Rationale:** the coach needs *which member + which document*, which are non-sensitive household-structure labels, not
scores/admin data. A flat string dict carries just that, keeping the firewall's intent (no model object, no score, no
reviewer opinion can reach the engine) while fixing the copy.
**Trade-offs:** the firewall is now "no model objects" rather than "exactly 4 scalar params" — a slightly weaker
structural guarantee, mitigated by the only caller building `context` from member + doc labels alone.
**Revisit if:** any caller is tempted to stuff application/score data into `context`, or the firewall needs to be
re-tightened to scalars only.

## Review as a post‑consent page (not a wizard tab, not an auto‑jump) — Sprint review-submit-flow, 2026-06-07
**Decision:** The read‑only "Review & submit" recap is a distinct screen rendered via a `reviewing` state in
`ScholarshipNextSteps`, reached only by an explicit **"Review & submit"** CTA shown after all 5 wizard steps (incl.
consent) are complete. `NEXT_STEP_ORDER` stays the 5 wizard steps; Review is NOT a member of it. Back returns to the
steps; Submit on the review page is the only commit.
**Alternatives considered:** (a) Review as a 6th navigable tab in `NEXT_STEP_ORDER` — how it was first built; (b) auto‑jump
straight to Review the moment all 5 steps complete (no button); (c) the explicit‑CTA post‑consent page (chosen).
**Rationale:** a freely‑navigable 6th tab let students land on "Review" before they had anything to review, and muddled
"these are steps to do" with "this is the final read‑back". Gating Review behind consent + an explicit CTA makes it a
clear terminal step. The auto‑jump was rejected as jarring — it swaps the whole screen the instant the last toggle flips,
with no beat between "I just consented" and "here's everything, submit now".
**Trade-offs:** one extra click vs an auto‑jump; the submit lives on a screen the student must choose to enter.
`handleConfirm` uses a full reload to flip to the post‑submit screen (TD‑090).
**Revisit if:** testing shows students miss the "Review & submit" CTA, or the user prefers the auto‑jump (left as an
open UX choice at sprint close).

## Anti-spam length caps at the serializer + UI; widen the one mis-typed column — Sprint input-length-guards, 2026-06-07

**Decision:** For student free-text fields, enforce length in two places — the web form (`maxLength`) and the API serializer
(`max_length`) — with a generous shared anti-spam ceiling `STORY_TEXT_MAX = 5000`. Caps on fields backed by a `varchar(N)`
column mirror N exactly (city 100, name/school 255, declaration 200, other-scholarships 300). The one column that was the
wrong *type* for its content — `parents_occupation`, a `varchar(255)` holding a sentence — was widened to `TextField`
(migration `0042`) rather than just capped, since a one-line cap there would still truncate a legitimate answer.
**Alternatives considered:** (a) only a frontend `maxLength` (rejected — paste/older clients/non-UI callers bypass it);
(b) only a serializer cap (rejected — the student gets an error after typing instead of being stopped); (c) widen every
column to `text` and rely solely on the cap (rejected — the existing `varchar` limits are sane DB hygiene; only
`parents_occupation` was genuinely mis-typed); (d) a global request-size limit (rejected — gives a useless generic error,
can't name the field).
**Rationale:** defence in depth — the form stops the common case at the keyboard, the serializer is the authoritative
guard for every code path (incl. the `setattr` writes that bypass model validation), and matching the column avoids both
silent rollbacks and arbitrary truncation. 5000 ≈ ~900 words: above any genuine answer, below a copy-paste flood.
**Trade-offs:** the cap constant is duplicated (a `STORY_TEXT_MAX` in both `serializers.py` and `ScholarshipNextSteps.tsx`)
— a small FE/BE contract to keep in sync, accepted over a shared-config mechanism for one number.
**Revisit if:** a field legitimately needs >5000 chars (raise that field's cap explicitly), or a shared FE/BE constants
source is introduced (then dedupe the ceiling).

## Verdict tiles as a 4-band Kent confidence scale — Sprint verdict-confidence-alignment, 2026-06-07
**Decision:** The officer's four verdict statuses map to a collapsed Sherman-Kent confidence
scale: `verified`→🟢 Certain, `review`→🔵 Probable, `recommend`→🟡 Unsure, `gap`→🔴 Can't verify.
Two refinements: (a) **blue/amber are assigned so colour temperature tracks certainty** —
blue is the higher-confidence "Probable" band, amber the "Unsure" band (amber reads as
caution); (b) **"blue needs a green"** — a `review` fact is blue only if it carries ≥1
genuinely-verified value; backed only by a declaration or a soft signal (`SOFT_EVIDENCE`) or
nothing, it is amber. Tiles show the estimative word + a legend. `factTileTone(fact)`.
**Alternatives considered:** keep the raw status→colour map (the prior 1:1); a 3-band scale
(drops blue); auto-jump amber↔blue by `recommend` alone (ignores whether anything's verified).
**Rationale:** the colours were being read as severity, not confidence; the Kent framing gives
a single coherent axis ("how sure are we the fact is sound") and a principled home for blue
(income's "evidence assembled, a human places it") distinct from amber.
**Trade-offs:** the tile colour is no longer a pure function of status (needs the evidence
array); `recommend` and "review with no verified value" both render amber (acceptable — both
are genuinely "Unsure").
**Revisit if:** a fifth state appears, or officers report the band labels don't match how they
triage.

## Per-fact evidence policy: hard-stop unusable documents; keep income interview-assessable — Sprint verdict-confidence-alignment, 2026-06-07
**Decision:** Weak evidence is bounced back to the applicant for re-upload rather than passed
to an officer for manual vetting — but only where a human genuinely can't recover it:
- **Academic** — a results-slip **name mismatch** is a hard stop (🔴 + fails `documents_done`):
  a slip we can't attribute is unusable. Only a positive mismatch blocks ('pending'/
  'unreadable'/'match' pass).
- **Pathway** — **no offer letter → 🔴** (already a submission blocker): we fund a confirmed
  place; a pathway can't be assessed by interview.
- **Income** — **no income info → 🔴** (consistency with no-IC/slip/offer). BUT income that the
  documents can't prove B40 (informal/no-EPF, unprovable relationship, or salary **above** the
  B40 line) stays **🟡 → interview**: documented salary often understates a poor family, so it
  must not auto-exclude.
- **Identity** — the IC's registered-address **state** is NOT an identity caveat (it's the
  least-current address on file); it's a pre-interview flag only. Identity never auto-fails —
  the gate blocks a NRIC mismatch / unreadable IC for re-upload.
**Alternatives considered:** pass everything to the officer (status quo — but no manpower to
vet); auto-reject above-B40-line income (rejected — interview-recoverable); make every "anchor
mismatch" a hard fail (rejected for identity — OCR misreads a good card's name).
**Rationale:** the team can't manually make sense of poor documents; an applicant re-uploading
beats staff guessing. The one carve-out is income *amount*, which is genuinely interview-
recoverable, so it escalates (amber) rather than blocks.
**Trade-offs:** a legitimate slip whose name OCR misread is bounced (mitigated: the slip
matcher is more reliable than IC-name OCR, and only a positive mismatch blocks).
**Revisit if:** re-upload friction spikes, or a state-restricted cohort makes the IC address
load-bearing.

## Sponsor-facing boundary: widen the allowlist (academic context) but gate institution to TRUSTED sponsors — B40 Phase E/F Sprint 0, 2026-06-07
**Decision:** Keep the sponsor pool's hard boundary an allowlist `Serializer` (fail-closed) but WIDEN it — cross academic
context (results/CGPA/band, field/course) and, gated, the student's **institution**. Institution crosses ONLY to a
**trusted** sponsor, read from `Sponsor.is_trusted` (default True at launch) and passed to the serializer as
`context['is_trusted']`; with no context it is absent. Personal & contact identifiers of the student AND their parents
(name, IC, phone, email, address, photo) stay blocked.
**Alternatives considered:** (1) invert to a denylist — rejected: a denylist leaks new model fields by default; the
allowlist keeps them invisible until consciously approved. (2) expose institution to ALL sponsors — rejected: institution
is a *locator* for a minor, tolerable only for known/vetted launch sponsors. (3) no institution at all — rejected: the
owner decided academic + institution context is the point of the widening for known donors.
**Rationale:** launch sponsors are known, vetted, large donors, so institution-level detail is acceptable; the
trusted-vs-public seam is built now (the `is_trusted` flag + context gate) so institution can be coarsened/switched off
for unvetted public sponsors later with no re-architecture. Results are an *attribute*; institution is a *locator* — so
only the locator is gated.
**Trade-offs:** institution stays dark until a view passes `is_trusted` (view-wiring deferred to go-live / Sprint 7); the
`scan_anon_for_identifiers` blurb scan still blocks school tokens in free text even though the structured institution
field may cross — an intentional asymmetry (structured, gated exposure vs un-gated free-text leak).
**Revisit if:** public (unvetted) sponsor onboarding opens (enforce the gate hard, review academic granularity), or the
lawyer's answer to the bundle §7.4 headline question requires a different boundary.

## Family roster — derive the legacy columns as OUTPUTS — Sprint family-redesign, 2026-06-08
**Decision:** The new structured family roster (father/mother name + coded profession + a brother/sister/guardian
pool) is the sole INPUT. The two legacy columns `first_in_family` and `parents_occupation` are KEPT and
recomputed on every save (`first_in_family` = no sibling in/through tertiary; `parents_occupation` = a human
summary of the roster). They become read-only OUTPUTS.
**Alternatives considered:** (a) drop the legacy columns and update every consumer (profile_engine,
anomaly_engine, submission_review ledger, check2) to read the structured fields; (b) keep both as independent
inputs (status quo).
**Rationale:** Deriving the legacy columns means ZERO consumer changes — a multi-engine refactor collapses to an
additive model + one save-path change. It also makes the `first_in_family_with_siblings_studying` anomaly and the
`sibling_level_unknown` clarify-query *inert by construction* for structured data (first_in_family can no longer
contradict the sibling count), while they stay correct as a safety net for grandfathered free-text rows.
**Trade-offs:** `parents_occupation` carries a terse machine summary ("Father: Driver…") for new apps instead of
the student's prose; the sponsor-profile prompt loses some narrative colour (acceptable — `family_context` keeps
the prose). Two columns now have a hidden invariant (must be derived, never hand-set when a roster exists).
**Revisit if:** a consumer needs per-earner structured occupation (then read the structured fields directly and
retire the summary), or Phase 2 unifies the roster with the income earners.

## Family roster — validate the profession taxonomy against the production DB — Sprint family-redesign, 2026-06-08
**Decision:** Before finalising the 40-option profession list, query every real `parents_occupation` free-text
entry on prod (33 rows) and map each to a code; add options for the genuine gaps the data exposes.
**Alternatives considered:** ship an armchair list and refine later from support tickets.
**Rationale:** The data surfaced four real gaps an a-priori list missed (insurance agent ×2, site engineer,
generic "company worker", foreman ×2) and confirmed the common ones — pushing coverage to ~95% before a single
student sees the dropdown. Cheap, high-signal, repeatable.
**Trade-offs:** a one-off DB read of (mildly sensitive) free text; the list is tuned to the current applicant mix
(B40/lower-M40) and may need extension if the programme's demographic widens.
**Revisit if:** the applicant population shifts, or "Other (specify)" free text starts clustering on a missing code.

## Family roster — make a zero-able stepper compulsory via a null default — Sprint family-redesign, 2026-06-08
**Decision:** The sibling steppers ("in school", "in college/university") start BLANK ("—", null), not 0, and
completeness requires both to be non-null. The student must actively set each, so "0 in school" is a deliberate
answer rather than an un-touched default.
**Alternatives considered:** (a) a preceding "Do you have siblings?" Yes/No gate; (b) leave them defaulting to 0
(can't tell "answered 0" from "skipped").
**Rationale:** A value that can legitimately be zero can't be made compulsory by checking `> 0`; the null-default
is the minimal pattern that distinguishes answered-zero from unanswered, with no extra question.
**Trade-offs:** the student must tap each stepper even to leave it at 0 (one extra interaction); the UI must
render a null state distinctly.
**Revisit if:** drop-off data shows the steppers are a completion bottleneck (then consider the Yes/No gate).

## Sponsor landing gated behind the count endpoint's `enabled` flag — B40 Phase E/F Sprint 1, 2026-06-08

**Decision:** The public sponsor marketing page (`/sponsor` for signed-out visitors) renders **only when the public
count endpoint reports `enabled: true`** (i.e. `SPONSOR_POOL_ENABLED` is on). While the flag is off, signed-out
visitors keep the pre-existing sign-in card; the marketing page is never shown. The backend setting is the single
source of truth — the FE has no separate flag.
**Alternatives considered:** (a) show the marketing page always (gate only the live-counter number); (b) a separate
frontend env flag for the page.
**Rationale:** the whole sponsor programme is lawyer-gated until go-live (Sprint 12), so even recruitment copy waits
for sign-off. Routing the live/dark signal through the count endpoint's `enabled` means one switch flips both the
counter and the page, and the FE can't drift out of sync with the backend.
**Trade-offs:** the marketing page can't be seen on prod until go-live (verify locally with the flag on); an extra
public GET on every `/sponsor` visit.
**Revisit if:** we want to recruit sponsors before the pool/money flow is live (then decouple a "marketing live" flag
from `SPONSOR_POOL_ENABLED`).

## OnboardingResponse as a dedicated model (not JSON on the application) — B40 Phase E/F Sprint 2, 2026-06-08

**Decision:** Store the F8a post-award onboarding questionnaire in a new `OnboardingResponse` model (one row per
application, JSON `answers` + FK to the acknowledgement `Consent` + timestamps) rather than a JSON column on
`ScholarshipApplication`.
**Alternatives considered:** a single `onboarding_response` JSONField on the application (no new table).
**Rationale:** the questionnaire is an audit artifact tied to a specific consent; a dedicated row with its own consent
FK + submitted/updated timestamps gives a clean audit trail and keeps the (already wide) application table from
accreting onboarding-shaped JSON. The answer shape can still evolve without a migration (the payload is JSON).
**Trade-offs:** one more table + a join to read; a new table needs RLS enabled on Supabase at deploy (TD-093).
**Revisit if:** onboarding answers become a fixed, small, queried-by-column set (then promote to typed columns), or if
the OneToOne join proves awkward for the F8b read path.

## Delegate a deep-context FE sprint to a subagent; orchestrator reviews + re-builds — B40 Phase E/F Sprint 3, 2026-06-09

**Decision:** The F8b frontend build (award page + onboarding wizard + i18n + clients) was delegated to a single
fresh-context subagent that left changes uncommitted; the orchestrator then reviewed the diff, independently re-ran
`next build` + jest, and committed.
**Alternatives considered:** building it inline in the main session.
**Rationale:** the main context was deep after Sprints 1–2, and F8b was well-specced (four owner-approved Stitch
screens + fixed backend contracts + an established i18n/`AppHeader` pattern) — exactly the contained, low-ambiguity
shape that delegates cleanly (lesson #73). It keeps the sprint within budget without losing the verify gate.
**Trade-offs:** an extra review pass; the subagent can't commit (by design — deploy/commit stays with the orchestrator).
**Revisit if:** a sprint is exploratory or its spec is still moving — then build inline, since a subagent can't make the
product decisions.

## Real-time sponsor alerts stamp the whole batch regardless of audience — B40 Phase E/F Sprint 4, 2026-06-09

**Decision:** `send_sponsor_realtime` stamps `SponsorProfile.realtime_notified_at` on every newly-published student it
processes, even when there are zero `realtime` sponsors to email. Each student therefore goes through exactly one
real-time cycle.
**Alternatives considered:** stamp only when ≥1 real-time sponsor received the batch (so a future first subscriber gets
a backlog of every earlier student).
**Rationale:** "real-time" means a live alert about what's new *now*; a sponsor who subscribes later shouldn't trigger a
one-off blast of the entire historical pool. Un-alerted students remain fully visible when browsing and are still
covered by the weekly digest.
**Trade-offs:** the very first real-time sponsor won't get a real-time alert for students published before they
subscribed (they see them in the pool / digest instead).
**Revisit if:** sponsors expect a "catch-up" real-time alert on first subscribing (then track notification per
(sponsor, student) instead of a single per-student stamp).

## Pagination is opted in per-view, not a global DRF default — Partner pagination, 2026-06-09

**Decision:** Add `FlexiblePageNumberPagination` (`halatuju/pagination.py`) and apply it explicitly on each list view that needs it (`PartnerStudentListView`, `AdminApplicationListView`), rather than setting `DEFAULT_PAGINATION_CLASS` in `REST_FRAMEWORK`.
**Alternatives considered:** the MySkills approach — a global default pagination class that every viewset inherits.
**Rationale:** MySkills was built that way from day one; HalaTuju has ~30 existing list endpoints that return full lists by contract (dashboards, pickers, exports, the verdict/cockpit serializers). A global default would silently truncate all of them and would have collided with the parallel reviewer track editing the `scholarship` app. Per-view opt-in keeps the blast radius to exactly the two tables converted.
**Trade-offs:** each new table that wants pagination must opt in (one paginator + `.envelope()` call) instead of getting it for free; the `.envelope()` helper exists to keep that boilerplate to ~4 lines and preserve each view's bespoke top-level fields.
**Revisit if:** the API is ever rebuilt around uniform `ListAPIView`/ViewSets with a consistent `{count,next,previous,results}` contract — then a global default becomes safe and removes the per-view calls.

## In-programme progress is DERIVED from the latest SemesterResult, never a stored column — Sprint 9 (F9a), 2026-06-09
**Decision:** The sponsor-facing `progress_state` band is computed live by `pool.derive_progress_state` from the most recent `SemesterResult` row; a new `SemesterResult` model holds the in-programme academic facts, separate from the application-time SPM `results_slip`.
**Alternatives considered:** (a) a `progress_state` column on `ScholarshipApplication` updated whenever a result lands; (b) overloading the existing `results_slip` ApplicantDocument + academic_engine to carry the in-programme CGPA.
**Rationale:** A derived band has a single source of truth, so F2's card can't drift from the results pipeline and needs no backfill; only one helper changes when the bands evolve. A dedicated `SemesterResult` keeps one fact per home (the SPM slip is a different fact from a university semester CGPA — lessons #51/#124) and lets the uploaded slip stay myNADI-only while only the coarse band crosses.
**Trade-offs:** the band is recomputed per read (cheap — one indexed `.first()`); no historical band snapshot is stored (the SemesterResult rows ARE the history). CGPA is student-entered, not OCR-derived (TD-103).
**Revisit if:** progress needs an audited point-in-time band history, or the derivation grows expensive enough to warrant a cached column synced on result write.

## Graduation thank-you relay = three independent anonymity guards, surfaced only by anon ref — Sprint 9 (F9a), 2026-06-09
**Decision:** A student's graduation message passes (1) a submit-time `scan_anon_for_identifiers` structural block, (2) a staff-edit re-scan on approval, and (3) a plain allowlist `GraduationRelaySerializer` exposing only `{ref, text, approved_at}`. The sponsor sees it as "a message from a student you supported" linked to `pool.pool_ref`, never a reply channel. (Owner decision 2026-06-09: scan + staff-approve + anonymous.)
**Alternatives considered:** a direct (DM-style) channel; a single prompt-trust "please don't include your name" instruction; trusting the submit-time scan alone.
**Rationale:** Defence-in-depth — no single miss leaks identity. The scan is the same structural primitive that gates the anon-blurb publish (reuse, not reinvent). Re-scanning the staff `scrubbed_text` closes the "human edit reintroduces an identifier" hole. A plain Serializer (not ModelSerializer) is allowlist-by-construction (lesson #107), proven by a planted-identifier leak test.
**Trade-offs:** a blocked message needs a student edit+resubmit round trip (acceptable — err toward blocking, lesson #108); approval is a manual myNADI step (intended — the human is the final judgement).
**Revisit if:** volume makes per-message human approval impractical (then add an auto-approve path ONLY for messages that pass the scan AND a stronger NER check, never a direct channel).

## promotional_use consent is 18+ only with NO guardian path — Sprint 9 (F9a), 2026-06-09
**Decision:** The `promotional_use` consent (using a student's story/photo for promotion) is a separate versioned consent a student can only grant for themselves as an adult; `grant_promotional_consent` raises `minor_not_allowed` when the NRIC indicates under-18. There is deliberately no guardian-grants-it path (unlike the sponsorship consent).
**Alternatives considered:** a guardian path mirroring the minor sponsorship-consent flow; a single combined consent.
**Rationale:** Owner decision (2026-06-09) — promotional use of a child's identity is the student's own adult choice to make, not a guardian's. Enforcing it structurally (the service refuses) is stronger than a UI checkbox.
**Trade-offs:** a sponsored minor cannot be featured in promotion until they turn 18 — accepted.
**Revisit if:** legal advice at go-live prescribes a different consent model for minors' promotional use.

## Sponsor referral = full SponsorReferral guest-book with a 60-day PDPA purge — Sprint 11 (F4), 2026-06-09
**Decision:** Record each invite as a `SponsorReferral` row (inviter, invitee email/name, note, code, status, registered_sponsor), NOT a lightweight `referred_by` stamp. Unconverted invitee PII (email/name) is scrubbed and the row marked `expired` after 60 days.
**Alternatives considered:** (a) lightweight `referred_by` — no table, send the invite email and don't store the invitee's email, attribute only once they join (least PII, no purge needed, but no "invites sent / conversion" tracking or reminders); (b) the full guest-book with a 30 / 90-day window.
**Rationale:** Owner chose the guest-book (2026-06-09) for the "your invitations" list + conversion stats + future reminder capability. 60 days balances giving a slow invitee time to convert against minimising how long we hold a non-consented person's email. The purge keeps the row (so the inviter's count survives) but removes the PII — auditable without indefinitely retaining strangers' data.
**Trade-offs:** we hold prospective-sponsor emails (PII) until they join or the 60-day purge runs — needs RLS on the table (TD-106) + a daily purge cron (TD-107) that MUST be live before go-live, or unconverted emails linger. The lightweight option would have avoided both but lost the tracking the owner wanted.
**Revisit if:** the programme decides referral analytics/reminders aren't worth the PII custody — then collapse to `referred_by` and drop the table + purge job.

## Go live on draft consent text, refine after the lawyer — Sprint 12 (go-live), 2026-06-09
**Decision:** Flip the B40 sponsor programme live (`SPONSOR_POOL_ENABLED=true`) with the CURRENT draft consent wording (`CONSENT_VERSION = 2026-draft-5`), rather than blocking the go-live on the lawyer's review. The lawyer-vetted text + a `CONSENT_VERSION` bump (which re-attests everyone) land as a follow-up; flow tweaks may follow too.
**Alternatives considered:** hold the entire go-live until the lawyer signs off the consent bundle (the original roadmap gate).
**Rationale:** Owner call (2026-06-09). Day-one real-user exposure is minimal (1 sponsor, 0 anon-published students), so very few people (if any) attest to the draft before the refined text lands. The `draft` version string means a later bump is a clean re-attestation, not a silent change. The programme can be re-darkened instantly with one `--update-env-vars` if the lawyer flags something fundamental. Shipping now unblocks real-world validation of the whole funnel.
**Trade-offs:** any consent captured before the bump is against draft wording (must be superseded by the re-attestation); the team carries an explicit follow-up obligation (consent text + version + Tamil refine) rather than having it done up front.
**Revisit if:** the lawyer's review changes the consent's substance materially (not just wording) — then re-dark the flag, ship the corrected flow, and re-attest before re-enabling.

## Four-role admin model via expand-contract + `has_role` — Admin Roles realignment, 2026-06-09
**Decision:** Replace `super/reviewer/viewer` with `super / admin / partner / reviewer`, keyed on the existing `PartnerAdmin.role` CharField, with the legacy `is_super_admin` flag kept in lockstep (expand-contract). Authorisation flows through `has_role(admin, *roles)`: `super` passes everything; `admin` passes view gates but FAILS execute gates (read-only for now); `partner` is scoped to its own organisation's students; `reviewer` is scoped to its assigned applicants. Organisation is partner-only; super is not an invite type.
**Alternatives considered:** (a) keep the 3-role model and bolt on org/assignment scoping ad hoc; (b) a full per-permission ACL table.
**Rationale:** The four roles mirror the programme's real actors (owner, future ops admin, referring organisations, individual reviewers). Expand-contract on `is_super_admin` let the migration be choices-only (no data lockout risk) while many call sites still gate on the legacy flag. `has_role` makes "admin = read-only" a one-line capability that's trivial to flip to read-write later. A full ACL was overkill for four coarse roles.
**Trade-offs:** two sources of truth (`role` + `is_super_admin`) during the contract phase; `admin` having no one in it yet means its read-only behaviour is only lightly exercised in production.
**Revisit if:** roles need per-page or per-action granularity beyond the four coarse buckets (then move to an ACL), or when `admin` gains execute powers (flip the `has_role` execute gates).

## B40 income gate: gross income primary, per-capita a safety net — B40 income policy, 2026-06-09
**Decision:** A non-STR applicant whose GROSS monthly household income is at or below the cohort `income_ceiling` (DOSM 2024 B40 line, RM5,860) is shortlisted regardless of household size. Per-capita (`per_capita_ceiling`, RM1,584) is demoted to a SAFETY NET that only applies ABOVE the gross ceiling, rescuing large families. STR recipients still pass directly. Existing un-released decisions are re-judged via a `rescore-pending` job.
**Alternatives considered:** (a) the prior rule — per-capita as the sole non-STR gate (no gross test); (b) a gross-only gate with no per-capita rescue.
**Rationale:** DOSM defines B40 as a gross household-income band, so the gross ceiling is the faithful test. The old per-capita-first rule wrongly excluded small B40-income families (a RM5,500 household of 2 was rejected despite being squarely B40). Keeping per-capita as an above-ceiling rescue preserves fairness for large households just over the line. `income_ceiling` already existed on the cohort (previously reference-only), so the change was purely wiring it into the gate + a help-text migration.
**Trade-offs:** two thresholds to maintain per cohort (gross + per-capita); a policy change requires re-scoring pending applicants (handled by the reusable `rescore-pending` job, scoped to un-released decisions so a communicated decision is never disturbed).
**Revisit if:** DOSM updates the B40 line (bump `income_ceiling` + run `rescore-pending`), or the programme wants need-based prioritisation finer than a single gross cut-off.

## Post-submit student surface: a form-locked Action Centre showing only deliberately-raised items — Action Centre, 2026-06-10
**Decision:** Once a student submits (`profile_complete`/`interviewing`/`interviewed`), `/scholarship/application` shows the **Action Centre only** — the 5-step form is locked and never re-openable. The Action Centre surfaces **only items a reviewer (officer) or the AI deliberately raised** (officer items + flag-gated AI `clarify`), plus document re-uploads requested; it does **NOT** surface the system's own verdict gaps (`source='system'`), which stay on the officer cockpit's four cards.
**Alternatives considered:** (a) keep showing the editable form post-submit (the prior `POST_SHORTLIST_EDITABLE` allowed it); (b) surface ALL `system` verdict tickets to the student for self-service (the original Check-2 design).
**Rationale:** Submission is a deliberate, consented, reviewed act — re-editing it silently undermines the audit trail and the consent gate. And live testing showed that auto-surfacing `system` verdict gaps produces **duplicate, noisy queries** (a mismatched upload spawned a "Check the name" system ticket beside the reviewer's task + Gopal's coach); the verdict gaps are the *reviewer's* triage surface, not the student's. The student should only ever respond to what was explicitly asked.
**Trade-offs:** Gave up the "self-serve fix any verdict gap" idea — a missing/mismatched item now reaches the student only when a reviewer (or, when enabled, the AI) raises it. `sync_resolution_items` still *creates* system items (used by nothing student-facing now) — harmless but slightly wasteful (TD logged).
**Revisit if:** we want students to self-serve a specific verdict gap without a reviewer raising it (then selectively surface that one `system` code, not all).

## Action Centre document/answer checks reuse existing engines; Phase 2 nudge is flag-gated + maximally lenient — Action Centre, 2026-06-10
**Decision:** A document upload's accept/keep-open verdict (`resolution.doc_match_verdict`) **mirrors the consent-gate per-doc classification** (`services.document_red_blockers`/`document_unreadable_blockers`): only a confirmed `mismatch` or `unreadable` keeps a task open; uncertain/soft/pending are accepted (the reviewer is the backstop). The Phase 2 typed-answer relevance nudge (`help_engine.judge_answer_relevance`) is **flag-gated** (`CHECK2_ANSWER_RELEVANCE_ENABLED`, default off — one billable Gemini call per answer), **firewalled** to the question+answer text only, **defaults to ACCEPT** on any AI error, and nudges **only when the answer is TOTALLY off-topic**.
**Alternatives considered:** (a) a fresh per-doc "match" rule for the Action Centre (would drift from the gate); (b) a stricter answer check that flags weak/partial answers; (c) no answer check at all.
**Rationale:** Two checks, two judgements that must not contradict the rest of the system — so reuse the *same* classification the gate + Documents tab already use. For answers, the owner's call (D2) is to respect the student's words: only a complete misunderstanding warrants a nudge, and the cost/abuse surface of an AI call is contained behind a default-off flag (the codebase's billable-AI pattern).
**Trade-offs:** `doc_match_verdict` duplicates the gate's per-doc logic rather than sharing one helper (TD logged — refactor when next touched). The lenient answer bar will let some off-topic-ish answers through to the reviewer — deliberate.
**Revisit if:** the gate's per-doc classification changes (keep `doc_match_verdict` in lockstep, or extract a shared helper), or the relevance nudge proves too lenient/strict in real use.

## Relationship/cross-document name matching is transliteration-tolerant; identity stays exact — Verification-accuracy pass, 2026-06-11
**Decision:** Added `vision.relationship_name_match` — a SEPARATE matcher that folds Malaysian-Tamil/Indian romanisation (w↔v, doubled letters, trailing silent h) + a single-character OCR slip on longer tokens — and aliased it into `income_engine` for EVERY name comparison there (relationships, earner-IC↔income-proof, STR-recipient↔IC, BC names). The identity check (student IC vs the typed profile name; the consent NRIC/name gate) keeps the exact `name_match`.
**Alternatives considered:** (a) loosen the global `name_match` (one matcher); (b) a relationship-only function used in just `father_relationship` (the reported case); (c) a phonetic algorithm (Soundex/Metaphone — built for English).
**Rationale:** Every comparison in `income_engine` is the SAME real person across two documents, where romanisation legitimately varies; identity is the student's own typed name vs their own IC, which should match closely. Loosening the global matcher would weaken the identity gate. A separate function that is STRICTLY more lenient (it can only turn a mismatch into a match) cannot weaken identity by construction. English phonetic algorithms mis-handle Tamil names; a small targeted fold + edit-distance is safer and auditable.
**Trade-offs:** Two name matchers to keep in mind. The tolerance could in theory merge two genuinely-different near-identical names — guarded by a differential audit (0 false merges across 16 real prod earners) + permanent over-merge tests.
**Revisit if:** a real false-merge appears (tighten the fold/threshold), or identity ever needs the same tolerance (then prove it doesn't weaken the gate first).

## An approved STR is "current" without a printed year — Verification-accuracy pass, 2026-06-11
**Decision:** `_str_currency` now treats an approval word (`Lulus`/`Diluluskan`/`Layak`/`approve`) as CURRENT even with no readable year; a year only ADDS the ability to mark a prior-year STR `stale`. A document with NO approval status (a SALINAN / application printout) is still `unconfirmed`.
**Alternatives considered:** (a) keep requiring an approval word AND a year (the prior rule); (b) accept any STR-looking doc; (c) require the student to upload a specific year-bearing page/screenshot.
**Rationale:** Confirmed from 6 real uploaded STR screens (viewed via signed URLs): the MySTR "Semakan Status" and Dashboard pages show "Status Permohonan **Semasa**: Lulus" and print NO cohort year — *Semasa* (current) is the currency signal, and the live portal reflects this cycle. The old rule falsely demoted 5 of 14 submitted STR students to `unconfirmed` for a valid Lulus screenshot. Option (c) is major friction on a B40/mobile audience for marginal value (the name/IC cross-check + officer review are the real controls). This REFINES, not reverses, the standing "SALINAN-not-proof" decision — a no-approval-status doc is still unconfirmed.
**Trade-offs:** A genuinely stale Lulus with no readable year would pass as current. Acceptable: a live status-page screenshot is current by construction, and the officer is the backstop. STR extraction also now classifies a closed-set `source_type` + reads Tarikh-Kredit dates to recover the year when present.
**Revisit if:** stale-but-undated STRs become a real problem (require the year again only for that source_type), or MOF changes the portal so the year is printed.

## SARA is not STR — the source_type bucket gates the STR verdict — Verification-accuracy follow-up, 2026-06-11
**Decision:** STR proof must be one of the recognised STR artifacts (the official STR approval letter, the MySTR "Semakan Status" page, or the Dashboard). The Gemini-classified `source_type` now GATES `_str_currency`: a positively-classified `unknown` source returns `unconfirmed` regardless of any status text read off it. SARA's "Layak" is removed from the STR approval words (the STR status is "Lulus"; "Layak" is a SARA status), and the extraction prompt classifies a SARA-only document (e.g. a Perdana Menteri "terpilih untuk menerima bantuan SARA" letter) as `unknown` without inferring an approval status. A blank/legacy `source_type` still falls through to the status check so pre-classification approvals aren't retro-broken.
**Alternatives considered:** (a) accept a SARA letter as B40 proof (SARA recipients are hardcore-poor — arguably needier than STR); (b) keep trusting the AI-inferred status word; (c) require a recognised source_type for ALL STRs (would retro-break the ~11 already-approved STRs whose docs predate classification).
**Rationale:** The owner's policy is that the STR route requires STR proof — SARA (Sumbangan Asas Rahmah) is a distinct programme, and a SARA-only document does not evidence STR approval. Trusting the AI's status word alone let app #63's SARA letter auto-pass as "current" (Gemini inferred "approved" from "terpilih menerima SARA"). Making the classification bucket the gate is deterministic and matches how a human reviewer reads the document type. Falling through on a blank source_type avoids breaking existing valid approvals; those get reclassified on re-extraction.
**Trade-offs:** A genuinely needy SARA family must still produce their STR proof (or be assessed at interview) — the automated path won't accept the SARA letter. Existing docs with a blank source_type are not retro-gated (only re-extracted/new uploads are), so a legacy SARA letter already in the system needs a re-run or a targeted correction (done for #63).
**Revisit if:** policy changes to accept SARA as an independent B40 signal, or once all STR docs carry a classified source_type (then the blank-fallback can be removed and the bucket required for all).

## Deterministic label-anchored capture runs BEFORE Gemini (2026-06-11, capture sprint P0/P1)
**Decision:** For standardised-issuer documents, capture fields by anchoring on FIXED LABELS
(`apps/scholarship/doc_parse.parse_by_labels`) and run it BEFORE Gemini in
`run_field_extraction_for_document`; Gemini is the FALLBACK (when the parser returns `None`).
Each doc's result is tagged `vision_fields['capture']='deterministic'|'ai'`. Parsers are
CONSERVATIVE (return `None` unless the text clearly is that document) so an unrecognised
layout degrades to exactly today's Gemini read. **Why:** the standardised Malaysian docs
(STR/MySTR, TNB, KWSP, JPN BC, govt offers) print fields at fixed labels and many are digital
PDFs with clean text layers we already extract — deterministic capture is more auditable,
free, and removes a class of AI mis-reads. **STR (P1) consequence:** the `source_type` bucket
(letter / semakan_status / dashboard / unknown) is now set DETERMINISTICALLY, which retires
the AI inference behind the SARA→STR false-pass (#63) AND closes the SALINAN-as-proof gap (a
MySTR application copy → `unknown` → `unconfirmed`), both via the existing `_str_currency`
gate. **Validation:** every parser MUST be checked against REAL OCR/text-layer samples before
its path is trusted (L86) — STR was validated against 9 live uploads across all four surfaces.

## An unread document holds its task ('pending' ≠ 'ok') — Upload-race fix, 2026-06-12
**Decision:** `resolution.doc_match_verdict` returns a distinct `'pending'` for a document whose
scan hasn't actually run (results-slip name/subjects not read; an unreadable subject table; an
`ic`/`parent_ic` with no `vision_run_at`). `resolve_doc_items_for_upload` only closes a task on
`'ok'`, so `'pending'` keeps it open. Separately, the interactive upload force-reads the
just-submitted file past the hourly doc-assist cap (`views._maybe_extract_fields(force=True)`).
**Alternatives considered:** (a) keep the original D1 "pending → accept" and rely only on the
force-read to make pending rare — rejected: leaves the greenlight hole whenever a read genuinely
fails; (b) hard-block on pending with an error coach — rejected: misrepresents a transient
"still reading" as "your document is wrong"; (c) add a vision_fields pre-check at the top of
`doc_match_verdict` — rejected: the existing tests mock the per-type check functions (not
`vision_fields`), and a true OCR-service outage on an IC must still accept so we don't trap a
student behind our own broken scanner.
**Rationale:** A verification gate must treat "not yet read" as unknown, not as a pass. The
force-read makes 'pending' rare at upload; when it does persist (real read failure) holding the
task is safer than greenlighting an unverified doc, and the reviewer remains the backstop.
**Trade-offs:** The force-read removes the hourly doc-assist cap for the interactive upload path
(one Gemini read per upload); abuse stays bounded by `UploadRateThrottle` + `MAX_DOCS_PER_APPLICATION`.
A rare genuine 'pending' shows a calm "still checking" note and asks the student to refresh.
**Revisit if:** doc-assist cost becomes material at scale (then cap forced reads at a high
per-application ceiling), or a background re-read job is added (then 'pending' could auto-resolve
without the refresh).

## Post-submit income route switch is a dedicated endpoint, not the details PATCH — Income route switch, 2026-06-12
**Decision:** The student self-serve income route switch is its own endpoint (`POST .../applications/<id>/income-route/`
→ `services.switch_income_route`), not a reuse of the broad `ApplicationDetailsView` PATCH (which already accepts
`income_route`). The dedicated path writes only the income fields, audits, and calls `sync_resolution_items`; it does
NOT call `revert_if_profile_incomplete`.
**Alternatives considered:** (a) reuse the details PATCH (it accepts `income_route` and `POST_SHORTLIST_EDITABLE` already
includes the post-submit statuses) — rejected: the PATCH calls `revert_if_profile_incomplete`, so a switch that creates
a new requirement (e.g. STR→salary needing salary slips) would flip `profile_complete` → `shortlisted` and silently
un-submit the student; (b) relax the PATCH to skip the revert for income-only payloads — rejected: brittle special-casing
of a broad mutator.
**Rationale:** A submitted student is never re-blocked (consent-gate-v2): post-submit gaps are Check-2 Action-Centre
tasks, not submission blocks. A narrow, audited endpoint makes this eligibility-touching change deterministic and keeps
the no-revert guarantee explicit and tested.
**Trade-offs:** A second endpoint covering the same field; mitigated by sharing the serializer choices + the wizard's
completeness rule. The salary-slip absence remains a soft interview signal (no hard task) on the new route — unchanged
post-submit income policy.
**Revisit if:** the post-submit income policy changes to hard-block missing salary slips (then the switch's recompute
would surface them as tasks), or an in-app audit view of route changes is wanted (then promote the log to a model).

## Income route-switch audit is a structured log line, not a DB model — Income route switch, 2026-06-12
**Decision:** `switch_income_route` records the change (`from`/`to` route, earner/members, by) via a structured Cloud
Logging line, not a new `IncomeRouteSwitchEvent` model.
**Alternatives considered:** a dedicated audit model (mirror `AssignmentEvent`) — rejected for this sprint: it needs a
migration (migrate-first via MCP + RLS) and the owner chose "audit-only, no officer-facing surface", so nothing queries
it in-app.
**Rationale:** Cloud Logging is a durable, queryable trail; with no in-app consumer, a model would be cost (a migration +
RLS) for no read path. Keeps the sprint no-migration.
**Trade-offs:** Not queryable via the ORM/cockpit; retention is bounded by log retention, not forever.
**Revisit if:** an officer/admin needs to see route-change history in-app, or compliance wants permanent retention — then
add the model.

## Genuineness is a soft confidence that lowers the prediction — never auto-fails, never blocks — IC genuineness, 2026-06-12
**Decision:** The document-genuineness fingerprint is a SOFT signal. On the IC it caps the Identity verdict at
`review`/Unsure (and raises an officer pre-interview flag + a student amber note), but NEVER moves it to `gap`/fail and
NEVER blocks submission. The reviewer is the authority; the AI lowers confidence, it does not accuse.
**Alternatives considered:** (a) hard-fail / block on a suspect document — rejected: a high-performing student pool with
a genuine card photographed badly would be wrongly stopped, and OCR/AI can't prove forgery anyway; (b) leave it purely a
pre-interview flag (don't touch the verdict) — rejected: the owner wants the AI to make a real *prediction*, so a suspect
card must lower the Identity confidence, not just sit in a side panel.
**Rationale:** Matches the threat model (casual/wrong-doc, not forgers) and the standard of proof ("highly probable",
human-scored). Capping at Unsure is the honest middle: the per-row name/IC "Match" stays accurate (it did match the
entry), while the tile + flag + student note carry the genuineness caveat. Never penalises a student for our AI outage
(no signal then).
**Trade-offs:** A determined forger still passes the automated layer (accepted — the interview + declaration are the
real controls). The signal only bites when the flag is on.
**Revisit if:** the programme moves to less human review at scale (then genuineness may warrant more weight), or a
verify-before-disbursement gate is added (the deferred money-gate layer).

## Genuineness stored in vision_fields JSON; the IC's extra Gemini call is flag-gated — IC genuineness, 2026-06-12
**Decision:** The genuineness result is written into the existing `ApplicantDocument.vision_fields` JSON column
(`['authenticity']`), not new columns — so Sprint 1 needs NO migration. The IC's one extra multimodal call is gated by
`DOC_GENUINENESS_CHECK_ENABLED` (default OFF; the supporting docs in Sprint 2 fold into reads they already make, ~zero
extra cost).
**Alternatives considered:** dedicated `vision_authenticity_*` columns — rejected for Sprint 1 (a migration + RLS for a
soft, flag-gated signal that nothing queries relationally); the JSON read path is sufficient.
**Rationale:** Ships dark with zero schema risk; the flag lets us validate on prod before relying on it; cost stays
bounded (one call per IC, only when on).
**Revisit if:** the authenticity signal ever needs relational querying/reporting (then promote to columns).

## Genuineness verdict cap is a uniform soft post-step in build_verdict — Doc genuineness Sprint 2, 2026-06-12
**Decision:** Rather than threading a genuineness check into each fact's verdict function (many exit points),
`build_verdict` applies `_apply_genuineness_caps` as a single post-step: a per-fact doc map
(`academic→[results_slip]`, `income→[str,epf,birth_certificate]`) is checked for a suspect/wrong-type
`vision_fields['authenticity']`; if found, the fact is downgraded verified→review and a `document_not_genuine`
caveat appended. Downgrade-only (never gap/fail, never upgrade). The IC keeps its cap inside `_verdict_identity`
(Sprint 1) — not re-applied here.
**Alternatives considered:** (a) wire genuineness into each `_verdict_*` at every return — rejected: many exit
points, easy to miss one, and the genuineness logic would be duplicated; (b) make it only an officer flag / student
note (no verdict change) — rejected: the owner wants the AI to *predict* per fact, so a suspect document must lower
the fact's confidence, not just sit in a side panel.
**Rationale:** One place, one rule, applied uniformly; the per-fact doc map is the single source of which documents
feed which fact's genuineness; downgrade-only keeps it strictly soft. Salary slip + offer letter are excluded (too
varied to fingerprint; the engine doesn't check them, so they can't trigger a cap).
**Trade-offs:** A coarser cap than bespoke per-fact logic (it can't, say, distinguish which of several income docs is
suspect in the verdict status — the officer flag + the document drawer carry that detail).
**Revisit if:** a fact needs finer-grained genuineness handling than a single downgrade (then move that fact's cap
back into its verdict function).

## Reliability surfaced as four-fact agreement, not an explicit overall-stance toggle — Verdict scorekeeper (Sprint 3), 2026-06-12
**Decision:** The AI-reliability card reports agreement (= 1 − override rate) per fact (Identity / Academic /
Pathway / Income) + an overall, derived from the four per-fact Pass/Fail decisions the reviewer already records.
We did NOT add the `officer_verdict.overall` ('accept'|'decline'|'hold') UI toggle that TD-083 also contemplated;
`overall` stays inferred (sent as `''`).
**Alternatives considered:** (a) add an explicit overall accept/decline/hold control to the Decision panel and
score reliability on that single stance — rejected for now; (b) score per-fact only with no overall line — rejected
(the overall figure is the headline a sponsor asks for).
**Rationale:** The four per-fact decisions are already captured at verdict-save and already feed `override_metrics`;
deriving agreement from them needs zero reviewer-workflow change and zero new field. An explicit overall toggle is a
separate UX with its own ambiguity (how does it reconcile with the four facts?) and wasn't needed to answer "can you
rely on the AI per fact?". The card is a read-only aggregate (no flag) and hides itself on any data error so it can
never break the applications list.
**Trade-offs:** No single deliberate "officer's overall stance" signal — the overall agreement is computed from the
facts, not stated by the officer. Fine while the four facts are the unit of review; insufficient if a coordinator
dashboard later needs an explicit accept/decline rate.
**Revisit if:** a coordinator dashboard wants an explicit overall stance (then build just the toggle — the unbuilt
half of TD-083).

## Slot model — tolerant-then-tighten rollout; route controls display, not storage — TD-115 Sprint 1, 2026-06-13
**Decision:** Move income documents to fixed `(doc_type × person)` slots via a tolerant-then-tighten rollout: deploy
readers that accept BOTH the legacy blank tag and the new person tag (blank-as-earner fallback on the STR route), THEN
backfill the data, so there is never a window where prod code can't find a doc. The upload endpoint is authoritative for
income-doc tagging (STR route tags `income_earner` regardless of client input — also slotting Action-Centre/Check-2
uploads), and the income ROUTE governs which slots are required vs optional (display), never WHERE a doc is stored.
**Alternatives considered:** (a) big-bang — flip readers to by-person + migrate in one deploy: rejected (a broken window
either side of the migration where STR verdicts can't find docs); (b) keep the route-dependent storage convention
(STR=blank, salary=tagged): rejected — it is the root cause of the "one IC under every earner" + duplicate bugs.
**Rationale:** tolerant readers make deploy and backfill each independently safe; the verdict engine already reads STR by
doc-type and salary by member tag, so the migration is provably verdict-invariant; backend-authoritative tagging fixes the
wizard AND the Action-Centre path in one place.
**Trade-offs:** the readers stay permanently lenient on the STR route (accept a blank as the earner's) — a small forever-cost
for never breaking on a stray blank. The DB uniqueness constraint (the hard guarantee) is deferred; duplicate prevention
rests on the app layer until it lands.
**Revisit if:** the STR route ever gains multiple earners (the single-earner assumption behind blank-as-earner breaks), or
the DB constraint is added (then the lenient readers can tighten to member-only).

## Check-2 vs Interview-Stage: one querying channel, not two — Check-2/Check-3 redesign Sprint 1, 2026-06-13
**Decision:** The officer↔student querying activity (raise query / request document) is a SINGLE mechanism
that lives only in the "Check 2 — Outstanding" box. The "Interview Stage" box does not raise new async
queries; it consumes any still-unanswered Outstanding query as an agenda item to ask verbally, captures
findings, and on Submit ends querying. Outstanding stays open until the interview is concluded, then becomes
a read-only record.
**Alternatives considered:** (a) duplicate raise-query/request-doc controls in both boxes (stage-tagged); (b)
collapse everything into one undifferentiated list.
**Rationale:** The real-world flow has one querying window (assignment → interview); after the interview it's
decision time, no more asks. Mechanically both controls would be the identical ResolutionItem channel, and
the student sees one Action Centre regardless — so two entry points are duplication, and merging loses the
officer's stage view. One channel in Outstanding + carry-over into the agenda matches the lifecycle exactly.
**Trade-offs:** Sprint 1 only splits display (interview content out of Outstanding); the lock-after-interview
and carry-over feed are deferred to Sprint 4. Until then the "interview concluded → no more queries" rule is
not yet enforced in code.
**Revisit if:** the programme ever needs post-interview document collection (e.g. a conditional offer awaiting
one more doc) — then Interview Stage would need its own scoped request channel after all.

## Answered queries auto-accepted; unanswered get Delete; lock at interview conclusion — Check-2/Check-3 S4, 2026-06-14
**Decision:** A student's answer to a Check-2 query is auto-accepted — the question+answer simply display as the record,
no officer Accept/Ask-again. Unanswered items offer a single **Delete** (waive) so the reviewer can drop an irrelevant or
poorly-worded query and raise a better one. All querying (raise / Delete / reopen / student resolve) **locks** once the
interview is concluded (`querying_locked`: status ≥ interviewed OR a submitted interview session); Outstanding becomes a
read-only record. Submit also auto-finalises the polished profile, and the reviewer handoff auto-drafts it — both gated
behind the OFF `CHECK2_AUTO_GENERATE` flag.
**Alternatives considered:** the S2 "officer explicitly Accepts/Ask-again each answer" model (the owner found it unnecessary
ceremony — the apply/application stage already accepted these answers); a hard DB-level lock; auto-gen on by default.
**Rationale:** mirrors the real reviewer flow (query window runs up to the interview, then it's decision time); keeps the
officer surface minimal; ship-dark gating means no billable Gemini calls until the owner flips one env var.
**Trade-offs:** auto-accept means a wrong/poor answer isn't formally re-queried after the interview (the reviewer asks
verbally instead); Delete waives rather than hard-deletes (keeps the audit row, hidden from both sides).
**Revisit if:** the programme needs post-interview document collection, or an explicit officer sign-off per answer for audit.

## Weighted, house-anchored utility-bill address matcher — Cockpit live-review, 2026-06-14
**Decision:** Replace the postcode-AND-city `address_present` boolean with a tiered `vision.address_match`
(found/unconfirmed/mismatch) scored on three components — **house number (the anchor) + street name + locality
(postcode OR city)** — with abbreviations normalised on both sides. Any 2 of 3 → found; 1 → unconfirmed (amber,
"couldn't confirm"); 0 + a different printed postcode → mismatch (red).
**Alternatives considered:** (a) keep postcode-authoritative (an exact postcode alone confirms) — rejected: a postcode
covers a whole locality (thousands of homes), so a relative's bill in the same town would falsely pass; (b) require the
city word (the old rule) — rejected: it fails on bilingual town names (Port↔Pelabuhan Klang, Skudai↔JB, Georgetown↔
P.Pinang), abbreviations (SG/Sungai), and postcode-absent bills.
**Rationale:** Validated against 7 real flagged bills — house# + street matched in 7/7; only the locality WORD tripped
the old matcher. The house number is the true identity; postcode/city disambiguate the town and kill cross-town
street-name collisions.
**Trade-offs:** A genuinely-different home in the same town with a coincidentally-overlapping street could read
'unconfirmed' rather than 'mismatch' — acceptable (soft, officer eyeballs; only `mismatch` is red / raises the flag).
**Revisit if:** false "found"s appear (two distinct homes scoring ≥2) — tighten the street-overlap threshold or require
the house number for 'found'.

## Income genuineness cap is route-aware — only REQUIRED docs can cap the verdict — Cockpit live-review, 2026-06-14
**Decision:** The income fact's genuineness cap (`verdict_engine`) considers only the documents REQUIRED to prove income
on the application's route (STR route → the STR, + birth cert when the earner is the mother), not the static
`[str, epf, birth_certificate]`. A suspect OPTIONAL doc (e.g. a future-dated EPF on the STR route) no longer downgrades
the verdict; it still raises the officer `document_not_genuine` pre-interview flag.
**Alternatives considered:** keep the static list (any of STR/EPF/BC caps income) — rejected: it let an optional doc the
verdict doesn't rely on pull a green INCOME to blue (#72: STR ✓ + IC ✓ but a dodgy optional EPF capped it).
**Rationale:** The verdict should reflect the route's actual proof; optional corroboration belongs in Check-2/interview,
not the headline verdict. Nothing is lost — the officer flag still surfaces the suspicion.
**Trade-offs:** a fabricated optional doc won't move the verdict (by design); the officer flag carries it instead.
**Revisit if:** policy makes an optional income doc verdict-bearing on some route.

## Gemini 2.5 Pro for the FINAL sponsor profile only — Cockpit live-review, 2026-06-14
**Decision:** The conclusive, sponsor-facing final profile (the refine pass) runs on `gemini-2.5-pro` (PRO_CASCADE,
falling back to the Flash cascade); the high-volume draft + anonymous profiles stay on Flash.
**Alternatives considered:** all profile prose on Pro (costlier per call, no quality need for the throwaway draft); keep
everything on Flash (slightly less polished final doc).
**Rationale:** The final profile is generated rarely (once per accepted student) and is the document a sponsor reads —
quality matters and volume is tiny, so the cost delta is negligible.
**Trade-offs:** Pro is slower/costlier per call; mitigated by it being low-volume + a Flash fallback.
**Revisit if:** Pro latency/cost becomes an issue, or a cheaper model matches its prose quality.

## EPF income from the AVERAGE contribution; zero ≠ unreadable — Cockpit live-review, 2026-06-14
**Decision:** The EPF income estimate uses the AVERAGE of all CARUMAN SEMASA months (÷0.24), not the single latest
month, with a fallback to the latest month for older records. A confirmed-zero ("Tiada Transaksi") is a distinct
`contribution_status` ('zero' = a real "no formal salary" signal) from an unreadable table ('unknown').
**Alternatives considered:** keep the latest month only (noisier — a partial/arrears/bonus row skews it); treat any
blank contribution as zero (rejected — conflates a parse miss with genuine no-income, the #72 risk).
**Rationale:** The average is steadier; the zero-vs-unknown split prevents a parse miss being read as "no income" and
turns a genuine zero into a useful B40 signal.
**Trade-offs:** new fields populate only on re-parsed/new EPFs (existing ones use the latest-month fallback until re-run).
**Revisit if:** averaging proves skewed by lump-sum arrears rows — switch to median/trimmed mean.

## Google Meet via Workspace service account + domain-wide delegation — Scheduling, 2026-06-18
**Decision:** Auto-generate interview Meet links by creating Google Calendar events through a **service account with
domain-wide delegation**, impersonating a single Workspace organiser (`admin@halatuju.xyz`); calls are best-effort
(never block a booking) and gated by `INTERVIEW_MEET_ENABLED`.
**Alternatives considered:** per-user OAuth (each reviewer authorises); embedded Jitsi/JaaS; manual paste links.
**Rationale:** every applicant has Gmail (event lands in their calendar with native reminders, one-tap join); 30–45-min
calls sit under the consumer 60-min cap and Workspace removes it; a service account is unattended + needs no per-user
consent screens; DWD impersonates the primary account (aliases can't be impersonated, so the organiser stays `admin@`).
**Trade-offs:** a Workspace seat (~RM15/mo); the SA JSON key is a Cloud Run secret to manage; calendar events live on
the organiser's calendar.
**Revisit if:** volume needs multiple organisers, or keyless DWD (workload identity) becomes simpler than a JSON key.

## Cockpit panel-freeze model (Interview + Decision) — 2026-06-18
**Decision:** Save = persist an editable draft (re-saving overwrites the same record in place); Submit / recording the
verdict = the panel becomes **read-only** (a Check-2-style record); a **superadmin** can reopen to correct. Read-only
interview view shows answered questions only + the open-ended findings; the decision view shows fact badges + amount +
conclusion + "recorded by {name}".
**Alternatives considered:** keep everything editable; fully lock with no reopen (DB-only corrections); per-reviewer reopen.
**Rationale:** an editable-looking committed panel invites accidental change and (with the save-after-submit path)
spawned duplicate sessions; freezing communicates "this is done" and removes the write controls that caused the bug.
Superadmin reopen keeps a correction path without a DB edit.
**Trade-offs:** a small amount of duplicated render (editable vs read-only); reopen is superadmin-only (reviewers can't
self-correct after submit).
**Revisit if:** reviewers frequently need to amend their own submissions — then allow assigned-reviewer reopen.

## Email addresses mapped to halatuju.xyz aliases — 2026-06-18
**Decision:** Global From = `info@halatuju.xyz` (a real mailbox, so replies are deliverable); topical aliases by role —
support/FAQ = `help@`, interview reply-to = `interview@`, sponsor = `sponsor@`, internal notifications = `contact@`,
Meet organiser = `admin@`. All aliases deliver to the one Workspace inbox.
**Alternatives considered:** keep sending from `noreply@`; one address for everything; per-message custom From.
**Rationale:** emails invite replies but `noreply@halatuju.xyz` wasn't a real mailbox, so replies were lost; a real
From fixes that globally, and topical reply-to/landing addresses keep things filterable. Brevo domain auth lets any
`@halatuju.xyz` address send without per-sender registration.
**Trade-offs:** all aliases share one inbox (filtering, not separate mailboxes); reply-to refinement is cosmetic while
single-inbox.
**Revisit if:** the programme grows enough to want separate staffed inboxes per alias.

## Sponsor profile income honesty: documented = certain, self-reported = a claim — 2026-06-18
**Decision:** STR/JKM are asserted in the generated profile ONLY when a (current) welfare document is on file; a documented payslip/EPF income MUST be stated as documented while any other figure (incl. reported household income) is presented as what the family reports. Implemented via `profile_engine._gated_str`/`_gated_jkm` (mirroring `_gated_first_in_family`) + the rewritten INCOME & WELFARE prompt rule; `PROMPT_VERSION` → 2026-06-18.1.
**Alternatives considered:** keep feeding the raw self-declared `receives_str`/`receives_jkm` booleans (status quo — caused #21); or present STR as "reported" rather than omitting it (rejected — the owner's rule is "no proof → assume they don't have it").
**Rationale:** a self-tick is an unverified claim; only an on-file, current document makes a welfare/income fact certain. Consistent with the standing need-signal principle (auditable evidence only). Symmetric: the same standard that suppresses an undocumented STR also forbids hiding a documented salary behind a soft reported figure.
**Trade-offs:** a genuine STR recipient who never uploaded the doc loses the STR mention in their profile; JKM (no document collected anywhere) is effectively never assertable. Existing drafts need the billable `backfill-assigned-profiles` cron to pick up the change.
**Revisit if:** a JKM document type is added to the upload flow, or the owner wants self-declared welfare surfaced as an explicit "reported" line.
