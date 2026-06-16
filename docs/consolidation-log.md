# Small-Change Consolidation Log

Tracks one-off small-lane changes between full sprints. Every ~10 pending entries triggers a
Consolidation Review (see `Settings/_workflows/small-change-lane.md` Part B).

## Pending
- 2026-06-16 fix(web): fold the two interview-question buttons into one (append-only, adaptive label; drops the destructive replace) (halatuju-web: admin/scholarship/[id]/page.tsx)
- 2026-06-16 copy(web): profile card heading "Sponsor profile (draft)" → "Student profile (draft)" (halatuju-web: messages/{en,ms,ta}.json)
- 2026-06-16 feat(web): reviewer Guide + FAQ pages + nav items (English content, redacted screenshots; BM/Tamil content to follow) (halatuju-web: app/admin/guide, app/admin/faq, layout.tsx, messages/* nav labels, public/reviewer-guide/*; docs/reviewer-guide-content.md)
- 2026-06-17 feat: reviewer language fluency (EN/BM/Tamil, None/Conversational/Fluent) + assignment matching (annotate + sort by student call_language) — migration scholarship/0059 migrate-first (halatuju_api: models, serializers_admin, views_admin, migration + tests; halatuju-web: admin/profile, admin/scholarship/page.tsx, admin-api.ts, messages/*)

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
