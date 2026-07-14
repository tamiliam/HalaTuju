# Plan — one status vocabulary: shared labels + semantic stage colours

## Context

The officer-facing admin surface describes a `ScholarshipApplication`'s stage in **four
independent, drifting places**, and colours it in **two contradictory ones**. Nothing is broken
functionally — this is a comprehension bug, and it has already cost us: the owner reports that
"Completed" is regularly misunderstood.

The two faults:

1. **Colour means two different things depending on the screen.** The applications *list*
   ([page.tsx:24-37](halatuju-web/src/app/admin/scholarship/page.tsx#L24-L37)) uses hue as
   *identity* — a different colour per stage (shortlisted blue, profile_complete emerald,
   interviewing violet, interviewed indigo) — but then collapses `recommended`/`awarded`/`active`/
   `maintenance` into one identical green, so four distinct stages are indistinguishable while two
   adjacent ones shout at each other. The *cockpit*
   ([[id]/page.tsx:148-165](halatuju-web/src/app/admin/scholarship/[id]/page.tsx#L148-L165)) uses
   hue as *meaning* (amber = in progress, green = decided, grey = ended, red = rejected). The same
   student is therefore a violet "Interviewing" pill in the list and an amber one in the cockpit.
   Worse, both maps spend green/amber/red — the exact vocabulary the officer surface already uses
   for **verdict confidence** (`docs/scholarship/verdict-confidence-bands.md`: green Certain / blue
   Probable / amber Unsure / red Can't verify) and for document fact chips. A green "Awarded" pill
   above amber verdict tiles reads as a judgement when it is only a stage.

2. **`profile_complete` has four names.** "Completed" in the list
   ([page.tsx:58](halatuju-web/src/app/admin/scholarship/page.tsx#L58), hardcoded English),
   "Profile complete" in the cockpit + timeline (i18n `admin.scholarship.statuses.*`,
   [en.json:2995](halatuju-web/src/messages/en.json#L2995)), "Completed" again in the admin FAQ
   prose ([faq/page.tsx:57-63](halatuju-web/src/app/admin/faq/page.tsx#L57-L63) — which *also*
   calls `rejected` "Declined", a name that exists nowhere else), and "Profile complete" in the
   backend `STATUS_CHOICES` ([models.py:108-130](halatuju_api/apps/scholarship/models.py#L108-L130),
   Django-admin only). "Completed" implies *the case is finished* — the opposite of the truth: the
   student has finished **their** part and the case is now sitting with us, unreviewed.

Two more facts that shape the fix:

- The list's labels are **hardcoded English**, so in a trilingual admin the status column never
  translates. The cockpit does it correctly via i18n.
- The i18n orphan guardrail
  ([admin-scholarship-i18n.test.ts:86-91](halatuju-web/src/messages/__tests__/admin-scholarship-i18n.test.ts#L86-L91))
  is **blind to this class of drift**: because `[id]/page.tsx` contains the literal
  `` t(`admin.scholarship.statuses.${s}`) ``, the whole `statuses.` prefix is treated as dynamic, so
  every key under it counts as "used" whether or not anything reads it. Nothing stops a second
  hardcoded map from regrowing.

**Outcome wanted:** one source of truth for the status vocabulary — one label per status (in i18n,
in all three languages), one tone per status — imported by every surface, with a test that fails if
a screen invents its own again.

## Decisions taken (owner)

- `profile_complete` is renamed **"Awaiting review"**. Chosen over the single word "Ready" for
  parallelism with its sibling stage `interviewed` = "Awaiting QC": the pair then reads as what it
  actually is, a queue — *awaiting review* → *awaiting QC*.
- Colour is **semantic, with a depth ramp**: colour carries the stage's *meaning* (the label already
  carries its identity), and within the "in progress" and "committed" families the shade deepens
  along the funnel so an officer can read progress from the list at a glance. Amber is **reserved**
  for "needs attention" (`reopened`) — matching what amber means everywhere else in the product —
  and is no longer spent on ordinary in-progress stages.

## The vocabulary (single source of truth)

| status | label (en) | tone |
|---|---|---|
| `submitted` | Submitted | `bg-blue-50 text-blue-700` |
| `shortlisted` | Shortlisted | `bg-blue-100 text-blue-700` |
| `profile_complete` | **Awaiting review** | `bg-blue-200 text-blue-800` |
| `interviewing` | Interviewing | `bg-blue-300 text-blue-900` |
| `interviewed` | Awaiting QC | `bg-blue-400 text-blue-900` |
| `recommended` | Recommended | `bg-green-100 text-green-800` |
| `awarded` | Awarded | `bg-green-200 text-green-900` |
| `active` | Active | `bg-green-300 text-green-900` |
| `maintenance` | Maintenance | `bg-green-400 text-green-900` |
| `closed` | Closed | `bg-gray-100 text-gray-600` |
| `withdrawn` | Withdrawn | `bg-gray-100 text-gray-600` |
| `expired` | Expired | `bg-gray-100 text-gray-600` |
| `rejected` | Rejected | `bg-red-100 text-red-700` |
| `reopened` (synthetic) | Reopened | `bg-amber-100 text-amber-700` |

Tone strings must be **complete literal class names** in the map — Tailwind's JIT scanner cannot see
a class assembled at runtime, so `` `bg-blue-${n}` `` would silently ship unstyled.

## Implementation

### 1. New shared module — `halatuju-web/src/lib/applicationStatus.ts`

The one place the vocabulary lives. Exports:

- `APPLICATION_STATUSES: readonly string[]` — the 13 real statuses in funnel order (mirrors
  `models.py` `STATUS_CHOICES`). This also becomes the source for the list's filter dropdown, which
  today silently omits `withdrawn` and `expired`.
- `SYNTHETIC_STATUSES = ['reopened']` — rendered when `decision_reopened_at` is set; not a DB value.
- `statusLabelKey(s): string` → `admin.scholarship.statuses.${s}` (so callers can't misspell the
  prefix — `officerCockpit.headerTimeline` already emits bare `labelKey` suffixes, which stay as
  they are).
- `statusTone(s): string` → the Tailwind classes above, with a safe grey default for an unknown
  status.
- `displayStatus(app): string` — the `decision_reopened_at ? 'reopened' : app.status` rule, which is
  currently duplicated in both pages ([page.tsx:308](halatuju-web/src/app/admin/scholarship/page.tsx#L308)
  and [[id]/page.tsx:824](halatuju-web/src/app/admin/scholarship/[id]/page.tsx#L824)).

Pure module, no React, no i18n import — it returns *keys*, and the caller does `t(...)`. This
matches how `officerCockpit.ts` is built and keeps it jest-testable in the node env.

### 2. Rewire the two screens

- **`src/app/admin/scholarship/page.tsx`** — delete `STATUS_LABELS`, `statusLabel`, `statusBadge`,
  `STATUS_OPTIONS` (L24-65). Import from the shared module; render the pill with
  `t(statusLabelKey(s))` + `statusTone(s)`, and build the filter `<option>` list from
  `APPLICATION_STATUSES`. **This is also what finally translates the status column** — it is
  English-only today.
- **`src/app/admin/scholarship/[id]/page.tsx`** — delete `STATUS_TONE` + `statusTone` (L148-165),
  import the shared ones. The header pill and the lifecycle timeline chips already read
  `admin.scholarship.statuses.*`, so their markup barely changes.

### 3. i18n — `src/messages/{en,ms,ta}.json`, `admin.scholarship.statuses` block (L2992-3007 in all three)

Only one key changes value; the key set is untouched (so the parity test stays green):

- en: `"profile_complete": "Awaiting review"`
- ms: `"profile_complete": "Menunggu semakan"`
- ta: `"profile_complete": "மதிப்பாய்வுக்குக் காத்திருக்கிறது"` — **first draft, flag for the
  owner's Tamil review** (house convention).

### 4. Admin FAQ prose — `src/app/admin/faq/page.tsx` (L57-63)

Reword the stage glossary to the canonical labels: "Completed" → "Awaiting review", and
"Declined" → "Rejected" (that third name for `rejected` should not exist). Add a one-line gloss for
"Awaiting review" that states the thing the old name got wrong: *the student has confirmed their
details; the case is now with us and not yet reviewed.*

### 5. Backend `STATUS_CHOICES` — `halatuju_api/apps/scholarship/models.py` (L108-130)

Sync the Django-admin display label: `('profile_complete', 'Awaiting review')`. This is the fourth
wording variant and is the only one we don't control from the frontend.

**Cost:** Django will want a migration. It is **choices-only — no DDL** (same class as `0088`/`0091`
in this repo). Generate it, and at deploy record the `django_migrations` row via Supabase MCP rather
than running any ALTER (the established migrate-first convention in `CLAUDE.md`). Do **not** skip
this: leaving `models.py` edited without the migration breaks `makemigrations scholarship --check`,
which was deliberately made clean in TD-147.

### 6. Close the guardrail hole — `src/lib/__tests__/applicationStatus.test.ts` (new)

The existing i18n orphan test cannot catch label drift (dynamic prefix). Add tests that can:

- Every status in `APPLICATION_STATUSES` + `SYNTHETIC_STATUSES` has a key under
  `admin.scholarship.statuses` in **en, ms and ta** — and, conversely, that block has **no key that
  isn't a known status**. This is the assertion that would have caught the original drift.
- `statusTone` returns a non-default tone for every known status (a new status added to the enum
  without a colour fails loudly instead of shipping grey).
- Guard against regrowth: assert that neither `admin/scholarship/page.tsx` nor
  `admin/scholarship/[id]/page.tsx` contains a local status→label or status→colour map — a cheap
  source-scan for `STATUS_LABELS` / `STATUS_TONE` / `statusBadge`, in the same spirit as the existing
  `no-icu-messageformat.test.ts` source-scanning guardrail.

## Verification

1. `cd halatuju-web && npx jest src/lib/__tests__/applicationStatus.test.ts src/lib/__tests__/officerCockpit.test.ts src/messages/__tests__` — the new tests plus the two suites most likely to be disturbed. `headerTimeline`'s existing tests assert on bare `labelKey` strings (`'submitted'`, `'recommended'`, `'awarded'`, `'active'`, `'maintenance'`); those keys are unchanged, so they must stay green — if they go red, the shared module has changed the key shape and that's a bug.
2. `npx jest` (full) + `npm run build`. **Do not pipe the build through `grep`** — a past incident let two type errors through because the pipeline's exit code was grep's, not npm's (recorded in `docs/lessons.md`).
3. `cd halatuju_api && .venv/bin/python -m pytest apps/scholarship/tests/ -q` (2337 currently pass) and `.venv/bin/python manage.py makemigrations scholarship --check` — must be clean after step 5.
4. **Eyeball both surfaces on real data.** The list at `/admin/scholarship` should show the blue ramp deepening down the funnel, the four post-decision stages now distinguishable as separate greens, and — the point of the exercise — the same pill colour and the same word when you click into that student's cockpit. Test account #16 (`admin@tamilfoundation.org`) is currently `shortlisted` and is the one to move stage-to-stage; note the earlier data op means it has a `profile_completed_at` stamp but a `shortlisted` status, so it will read "Shortlisted".
5. Switch the admin UI to BM and confirm the list's status column now translates (it never has).

## Notes / risks

- **Scope guard:** three *other* `statusBadge`-style maps exist and are **different enums** — sponsor
  vetting status (`admin/sponsors/page.tsx`), course-interest status (`profile/page.tsx`), and the
  maintenance sub-state (`admin.maintenance.substate.*` in the cockpit). Leave them alone.
- No student- or sponsor-facing surface renders an application status as a label or coloured chip
  (they only branch on `app.status`), so this change is officer-facing only. The student-masking rule
  in `serializers.py:571-588` (a masked `recommended`/embargoed `rejected` is reported to the student
  as `interviewed`) is untouched and must stay untouched.
- Frontend-only apart from step 5; **no DDL**, no data migration, nothing to backfill.
- This plan is independent of the uncommitted `cancel_offer` work on `feat/partner-onboarding-durable`
  (sponsor award-withdrawal cool-off) — that lives in the backend and does not touch these files.
