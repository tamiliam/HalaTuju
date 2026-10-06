# Retrospective — Input length-guard hardening (Story · Funding · Apply)

**Date:** 2026-06-07
**Type:** Reactive bugfix sprint (prod incident → audit → systemic fix)
**Deploys:** 3 (all SUCCESS) · 1 migration (`scholarship/0042`)

## What Was Built

A student (POVIENTHIRAN A/L R MARIMUTU, app #30) reported he could not save the
"Your story" step — only the generic *"Could not save your details. Please try
again."* Diagnosis traced it to the **"What do your parents/guardians do for a
living?"** field (`parents_occupation`): a `varchar(255)` column with **no length
guard on the web form or the API**. His real answer ("My mother is a Grab driver
and the sole breadwinner…") exceeded 255 chars; Postgres raised `value too long
for type character varying(255)`; and because the save is one atomic request, the
**entire Story save rolled back** (narrative + funding + address), surfacing only
as the blanket error.

Fixed in three shipped slices:

1. **The bug (deploy 1).** `parents_occupation` → `TextField` (migration `0042`,
   backward-compatible widening, applied migrate-first via Supabase MCP). Every
   free-text Story field gets a generous anti-spam cap (`STORY_TEXT_MAX = 5000`)
   on both the web form (`maxLength`) and the API serializer (clean 400). Closed
   the same latent trap on the address **city** field (`varchar(100)`).

2. **Actionable message + Funding (deploy 2).** Per user request: instead of
   "could not save", a length error now reads *"Your answer to "{question}" is too
   long. Please shorten it."* naming the field (en/ms/ta). The API client carries
   DRF field-level errors through (`err.fieldErrors`); a pure `firstTooLongField()`
   helper + `STORY_FIELD_LABEL_KEYS` map resolve field → question label. Funding's
   `funding_note` got the same cap, completing the Story/Funding audit.

3. **Apply-form audit (deploy 3).** Same check on `/apply`. Two real risks —
   **name** and **school** (free-text combobox), both `varchar(255)` profile
   columns written by `sync_profile_fields` → `setattr` → `save` with no
   validation. `ApplicationCreateSerializer`'s write-only profile fields gained
   `max_length` matching their columns; the form gained `maxLength`s; the apply
   submit shows the same actionable message. `contact_phone` was already safe
   (`formatPhone` caps to 11 digits); dropdowns can't overflow.

## What Went Well

- **Live Postgres logs nailed it fast.** `get_logs(postgres)` showed the exact
  `value too long for type character varying(255)` error at the student's save
  timestamps — turned a vague "save failed" into a one-line root cause.
- **The fix generalised cleanly.** Once the mechanism was understood
  (unvalidated free text → varchar column → atomic rollback → generic error), the
  same audit found the `city` and `name`/`school` analogues before users hit them.
- **Tests caught the trim gotcha** (DRF `CharField` trims whitespace) before deploy.

## What Went Wrong

- **The trap was invisible because two layers silently disagreed.** The web form
  and the `serializers.Serializer` both imposed no limit, but the DB column did.
  *Root cause:* `ApplicationDetailsUpdateSerializer` is a plain `Serializer` with
  hand-declared `CharField`s (no `max_length`), and `save_application_details` /
  `sync_profile_fields` write via raw `setattr` — neither path inherits the model
  field's length the way a `ModelSerializer` would. *Fix that prevents recurrence:*
  lesson added (below) — any hand-declared serializer field or `setattr` write to a
  length-limited column must carry an explicit `max_length`; mirror the DB column.
- **The error message hid the cause from the user and from triage.** A blanket
  `catch {}` discarded the 400 body. *Root cause:* the client threw away DRF's
  field errors and the component ignored the exception entirely. *Fix:* the API
  client now preserves `fieldErrors` and the forms phrase a specific message.

## Design Decisions

See `decisions.md` — "Anti-spam length caps at the serializer + UI, widen the
mis-typed column" (Sprint 2026-06-07).

## Numbers

- Backend: **1814** pytest (777 scholarship + 1037 courses/reports) — +8 this sprint
- Frontend: **274** jest — +8 this sprint (firstTooLongField ×4 + earlier)
- i18n parity: **2090** × en/ms/ta
- Migrations: scholarship through **`0042`** (the one widening this sprint)
- 3 deploys, all SUCCESS; `next build` clean each time
