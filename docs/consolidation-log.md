# Small-Change Consolidation Log

Tracks one-off small-lane changes between full sprints. Every ~10 pending entries triggers a
Consolidation Review (see `Settings/_workflows/small-change-lane.md` Part B).

## Pending
- 2026-06-16 fix(web): fold the two interview-question buttons into one (append-only, adaptive label; drops the destructive replace) (halatuju-web: admin/scholarship/[id]/page.tsx)
- 2026-06-16 copy(web): profile card heading "Sponsor profile (draft)" → "Student profile (draft)" (halatuju-web: messages/{en,ms,ta}.json)
- 2026-06-16 feat(web): reviewer Guide + FAQ pages + nav items (English content, redacted screenshots; BM/Tamil content to follow) (halatuju-web: app/admin/guide, app/admin/faq, layout.tsx, messages/* nav labels, public/reviewer-guide/*; docs/reviewer-guide-content.md)
- 2026-06-17 feat: reviewer language fluency (EN/BM/Tamil, None/Conversational/Fluent) + assignment matching (annotate + sort by student call_language) — migration scholarship/0059 migrate-first (halatuju_api: models, serializers_admin, views_admin, migration + tests; halatuju-web: admin/profile, admin/scholarship/page.tsx, admin-api.ts, messages/*)
- 2026-06-17 feat: advance-notice email to student on reviewer assignment (bilingual EN+BM; flag STUDENT_ASSIGNMENT_EMAIL_ENABLED off by default; reviewer phone opt-out share_phone_with_students default on; migration scholarship/0060 migrate-first) (halatuju_api: emails.py, services.py assign_reviewer, models, serializers_admin, settings/base.py, migration + tests; halatuju-web: admin/profile toggle, admin-api.ts, messages/*)
- 2026-06-21 fix(check2): reviewer-raised Action-Centre requests now notify the student (reset query_raised_notified_at on raise; send_due_query_emails counts source='officer' items; no per-item email) (halatuju_api: views_admin.py, services.py + tests)
- 2026-06-21 fix(income): salary-route earner shown Optional/undeclared when pre-ticked-but-not-toggled (#90+4); effective_working_members fallback (tagged docs→roster) wired into income_requirements+verdict; FE persists roster seed on mount; backfilled 5 apps (halatuju_api: income_engine.py, verdict_engine.py + tests; halatuju-web: ScholarshipDocuments.tsx)
- 2026-06-21 fix(income): document_unreadable_blockers passed a list (not the app) to working_members → always [] on salary route → unreadable salary-route earner IC/rel doc skipped the submission gate; now effective_working_members(application) + a regression test (halatuju_api: services.py, tests/test_family.py)
- 2026-06-23 fix(scheduling): advance profile_complete->interviewing when interview times are proposed (status was stuck at Complete through booked/concluded interviews); propose_slots flip + 6-app backfill (halatuju_api: scheduling.py + tests)
- 2026-06-23 fix(check2): surface system 'couldn't read your doc' upload requests to the form-locked student (unreadable/no-identity/stale-STR added to STUDENT_DOC_REQUEST_CODES; name-mismatch class stays reviewer-mediated); un-hides 5 live requests (halatuju_api: resolution.py + tests)
- 2026-06-23 fix(vision): self-heal IC/parent_ic stuck unprocessed (vision_run_at NULL from silent upload OCR failures) → false 'ic_service_down' consent block; reprocess_unread_ic command + cron job + sweep fn (halatuju_api: services.py, views.py JOBS, mgmt command + tests)
- 2026-06-27 fix(scholarship): SPM slip parser bounces 2-column under-reads to Gemini — reads declared JUMLAH MATA PELAJARAN total, returns None when it recovers fewer (was dropping 6/10 subjects + mis-grading 3 of 4 as 'ok'); #66 (halatuju_api: academic_engine.py + tests + PII-scrubbed slip fixture)
- 2026-06-27 fix(scholarship): read hand-written salary-voucher ringgit|sen columns as a decimal (was concatenating RM326.00→32600 → false per-capita RM8150 over B40 line); +net>gross backstop in income_engine; #66 (halatuju_api: vision.py prompt, income_engine.py + tests)
- 2026-06-29 fix(scholarship): ALL-CAPS offer programme leaked to sponsor pool via confirm_pathway (raw offer text, bypassing the cased catalogue); title_case_programme rescues shouty names (acronym/connector/punctuation-safe, idempotent); #107 backfilled (halatuju_api: offer_pathway.py, services.py + tests)

_(previous batch cleared at the 2026-06-16 review below)_

## Reviews

### 2026-06-16 — Live-review round (9 small changes)
**Reflect.** The 9 changes touched three surfaces: the **AI profile generator** (5: distil-all-inputs,
interest-quiz, statement-of-intent, grades-grouping/ethnicity, prompt-versioning), **web i18n hygiene**
(3: TD-118, TD-120, cockpit copy tweaks), and **reviewer access** (2: hide assignee filter, set-password page).
Most were genuine fixes; the profile ones were additive improvements, not symptom-patching.

**Cohere — clusters promoted:**
- **Profile completeness & safety (5).** Not five fixes — one coherent body of work: "make the AI profile use ALL
  the data the student gave us (typed fields, quiz, statement-of-intent), summarised well, and without leaking PII or
  ethnicity." Recognised as a mini-feature; the prompt is now **versioned** so it can evolve safely. Captured in
  `decisions.md` (prompt versioning; grades-by-group; generalise-ethnicity).
- **i18n drift after redesigns (3).** Recurring class: cockpit redesigns leave orphaned `admin.scholarship` keys.
- **Reviewer onboarding (2).** Non-Google invitees couldn't onboard; the set-password page closes the systemic gap.

**Anticipate — guardrails (recurring fix → prevention):**
- i18n orphans → **guardrail test added** (`messages/__tests__/admin-scholarship-i18n.test.ts`, dynamic-aware) — the
  class can no longer silently regrow. ✅
- Stale AI drafts after a prompt change (the #18 trap) → **PROMPT_VERSION + version-aware backfill added** — staleness
  is now detectable by version, and re-running the backfill only refreshes stale drafts. ✅
- **Candidate (not built):** schedule the version-aware backfill (or trigger it on a `PROMPT_VERSION` bump) so drafts
  self-heal without a manual cron call. Logged for a future pass.

**Close out.** Pending cleared (counter reset). Guardrails landed in the same round. Folded into the 2026-06-16
sprint-close (retrospective `docs/retrospective-2026-06-16-livereview-round.md`).
- 2026-06-17 docs(web): add FAQ entries for reviewer languages + phone-sharing toggle (keep reviewer FAQ current with recent features) (halatuju-web: app/admin/faq/page.tsx)
