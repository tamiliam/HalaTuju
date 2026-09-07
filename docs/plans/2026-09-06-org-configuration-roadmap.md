# Organisation Configuration — roadmap (approved 2026-09-06, phased option)

**The ask (owner, 2026-09-06):** the sponsor page removes an awarded student's card after 2 days.
Extend it to 30 days — but NOT by hard-coding it. It must be a configurable value under
**Organisation → Settings → Configuration** (a new tab beside Colours). And that tab should become
the home for the organisation-wide values that are hard-coded today.

**The owner approved the PHASED build**: Sprint A ships the settings engine + the tab + the
funded-card window; later sprints migrate the other groups one at a time.

---

## What exists today (survey, 2026-09-06)

- The 2-day rule is `POOL_FUNDED_GRACE_HOURS` (settings default 48), read in
  `apps/scholarship/pool.py::display_pool_queryset` — a pure query-time filter on `awarded_at`.
- ~30 further values are organisation-scope but hard-coded (module constants or
  `getattr(settings, …)` platform globals). Full survey table is in the sprint-A working notes;
  the groups are listed under the sprints below.
- `PartnerOrganisation` has **no settings store** — flat branding columns plus one side model,
  `OrganisationTheme` (the Colours precedent). There is no generic config model.
- The closest templates to copy:
  - `AdminOrganisationThemeView` (org derived from `owning_organisation`; super passes
    `?org=<code>`; cross-org → **404 never 403**; roles super + org_admin).
  - `AdminProgrammeConfigurationView` + `ProgrammeConfigTab.tsx` (GET/PUT, all-or-nothing save,
    audit line per write).
  - The tab shell at `halatuju-web/src/app/admin/organisation/settings/page.tsx` — its own
    comment says it waits for the second organisation-level setting. This is that setting.

## Binding rules for every sprint in this arc

1. **A setting appears on the tab ONLY when code actually reads it.** No decorative switches —
   an unwired control is the "UI asserts what nothing checks" defect by construction.
2. **Blank = platform default.** The stored row holds only what the organisation changed.
   The registry (code) carries type, default, safe range, group, and label key per setting.
   The catalogue-not-form-builder rule: an org sets a VALUE; it never invents a setting.
3. **The registry defaults DELEGATE to today's Django settings** so behaviour is byte-identical
   for every org with no row. Deploying an engine sprint changes nothing visible by itself.
4. **PUT is all-or-nothing** with range validation server-side; every write gets an
   `AUDIT org_config_set` line carrying key + old → new + actor.
5. **Fence**: org derived from the caller's `owning_organisation`; super names `?org=`;
   cross-org is 404. Roles: super + org_admin only. Classified in `test_org_fence.py`.
6. **Out of scope for this tab, permanently (re-argue only with the owner):**
   - Feature on/off switches (`SPONSOR_POOL_ENABLED`, `WHATSAPP_ENABLED`,
     `BURSARY_AGREEMENT_ENABLED`, …) — go-live levers with operational sequencing; they stay
     platform-controlled (the `module_*` columns are their eventual home).
   - Per-GIFT values (award amounts `ALLOWED_AMOUNTS`, reminder cadence R1–R4, decision
     cool-offs, funding estimates) — they belong to the Programme screen; several already have
     unexposed `ScholarshipCohort` columns.
   - Platform internals (rate limits, PII retention days, FX rate, billing margin).

## Sprints

### Sprint A — the engine, the tab, and the sponsor-page group  *(medium; ONE migration)*
**Goal:** the owner can open Organisation → Settings → Configuration and set the funded-card
window to 30 days, and the sponsor page obeys.
**Scope:**
- `OrganisationConfiguration` model (apps/courses, beside `OrganisationTheme`): OneToOne to
  `PartnerOrganisation`, JSONField `values`, `updated_by_email`, `updated_at`. RLS + one
  `service_role` policy. **Migrate-first via Supabase MCP before the push.**
- `org_config.py` registry + read seam `org_config.value(org, key)` (default ← Django setting).
- First settings, group "Sponsor page":
  - `pool_funded_grace_days` — days a newly funded student's card stays on the sponsor browse
    page (platform default 2; BrightPath to set 30 in the UI after deploy). Stored in DAYS
    (the owner's unit); the pool seam converts. ⚠ `display_pool_queryset` has no org context —
    the sprint must resolve the cutoff per the application's `owning_organisation` (Case/When
    over orgs holding a custom value, default otherwise), and the funded-detail view at
    `views_sponsor.py` must use the same seam.
  - ~~`sponsor_email_max_cards`~~ **DEFERRED to Sprint B (decided in-sprint, 2026-09-07):** its
    two read sites (`emails.py::_sponsor_email_max_cards`, `sponsor_comms.py::MAX_CARDS`) render
    sponsor emails with NO organisation in hand — the senders take an address and a card list.
    Threading the organisation through them is its own task, and rule 1 forbids showing the
    setting before it is wired. Sprint A ships the one setting the owner asked for.
- Endpoint `GET/PUT admin/scholarship/organisation/configuration/` (mirror the programme one).
- FE: `OrganisationConfigurationTab.tsx` + the second tab in the settings shell; i18n en/ms/ta
  (ms/ta first drafts). **Stitch design approved before page code.**
- Tests: registry bounds, fence, blank-=default, audit line, pool cutoff per org, jest for the tab.
**Acceptance:** BrightPath sets 30; a student funded 3 weeks ago still shows; an org with no row
behaves exactly as before; suite green; deployed.

### Sprint B — student communications  *(low-medium; no migration)*
`query_email_delay_hours` (2), `nudge_auto_delay_minutes` (30), `nudge_cooldown_hours` (24),
`max_clarify_open` (3). Registry entries + wiring + rows on the existing tab.

### Sprint C — reviewers & staff  *(medium; no migration)*
`review_sla_days` (10), `review_nudge_soon_days` (2), `review_escalate_grace_days` (4),
`temp_password_ttl_days` (7), `admin_dormant_days` (90).

### Sprint D — interviews  *(medium-high; no migration)*
`interview_duration_min` (30 — also settles the live 30-vs-45 fallback inconsistency in
`emails.py`/`scheduling.py`), booking window start/end/step, `slot_min_lead_hours` (24),
`reschedule_cutoff_hours` (12). ⚠ `interviewSlots.ts` mirrors the window constants in the FE —
this sprint must serve them to the FE instead of the lock-step copy.

### Sprint E — documents  *(low; no migration)*
`max_doc_size_mb` (8), `max_docs_per_application` (40), `max_other_docs` (10),
`doc_stage_max_attempts` (3).

### Sprint F — agreements  *(medium; no migration; legal-adjacent)*
`sign_accept_deadline_days` (30), `sign_reminder_days` (3), foundation signatory
name/title/notify email (tenant identity currently in platform env vars — prints into the
agreement PDF, so owner reviews the rendered output).

Sprints B–F are independent of each other; re-order freely on demand. Each is small because the
engine and the tab already exist — a later sprint is registry entries + wired read sites + rows.

## Status

- [x] Sprint A — SHIPPED + DEPLOYED 2026-09-07 (`main` 85d079a6; retro
      `docs/retrospective-2026-09-07-org-config-sprint-a.md`; BrightPath set 30 days, live)
- [x] Sprint B — SHIPPED 2026-09-07 (worktree `.worktrees/org-config-b`, branch
      `feat/org-config-sprint-b`; the four student-comms settings + the deferred
      `sponsor_email_max_cards`, threaded through the sponsor email senders; retro
      `docs/retrospective-2026-09-07-org-config-sprint-b.md`)
- [x] Sprint C — SHIPPED 2026-09-07 (worktree `.worktrees/org-config-c`, branch
      `feat/org-config-sprint-c`; the five reviewers-&-staff clocks; the temp-password TTL and
      dormancy threshold are now SERVED to the FE — the first exercise of the rule Sprint D's
      `interviewSlots.ts` warning states; retro
      `docs/retrospective-2026-09-07-org-config-sprint-c.md`)
- [ ] D · [ ] E · [ ] F
