# Small-Change Consolidation Log

Tracks one-off small-lane changes between full sprints. Every ~10 pending entries triggers a
Consolidation Review (see `Settings/_workflows/small-change-lane.md` Part B).

## Pending
- 2026-06-16 chore(web): remove dead profile api-client fns + 29 orphaned i18n keys (TD-118) (halatuju-web: admin-api.ts, messages/{en,ms,ta}.json)
- 2026-06-16 chore(web): cockpit Decision+profile copy tweaks, "Rate AI verification" heading, restore finalProfile.title (halatuju-web: admin/scholarship/[id]/page.tsx, messages/{en,ms,ta}.json)
- 2026-06-16 fix(web): hide redundant assignee filter for reviewers on B40 Applications list (halatuju-web: admin/scholarship/page.tsx)
- 2026-06-16 chore(web): TD-120 — remove 77 orphaned admin.scholarship i18n keys (en/ms/ta) + add dynamic-aware orphan/parity guardrail test (halatuju-web: messages/{en,ms,ta}.json, messages/__tests__/admin-scholarship-i18n.test.ts)
- 2026-06-16 feat(api): AI profile distils ALL student inputs (justification, fears, anything_else, top_choices, other_scholarships, help_wanted, uncertainty) — were collected but ignored (halatuju_api: scholarship/profile_engine.py + tests)
- 2026-06-16 feat(api): use the interest quiz — accretive interest context in the profile (Idea 1) + quiz-vs-pathway exploratory interview question (Idea 2) (halatuju_api: scholarship/profile_engine.py, gap_engine.py + tests)
- 2026-06-16 feat(api): feed the OCR'd Statement of Intent letter text into the profile draft (was extracted but only used by Check-2) (halatuju_api: scholarship/profile_engine.py + tests)
- 2026-06-16 feat(web): set-password page for admins/reviewers (invite + reset links → /admin/set-password → choose password) — unblocks non-Google invitees (halatuju-web: app/admin/set-password, admin-supabase.ts, messages/*; halatuju_api: courses/views_admin.py invite redirect)
- 2026-06-16 feat(api): profile academics summarised by group + ethnicity-safe (no vernacular subject names) + PROMPT_VERSION tagging (migration 0058) + version-aware backfill (halatuju_api: scholarship/profile_engine.py, services.py, views_admin.py, models.py+migration, backfill cmd + tests)

## Reviews
