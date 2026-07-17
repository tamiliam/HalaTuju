# Retrospective — Sponsor pool redesign (image-led cards + refined detail) — 2026-07-17

Brief: `docs/plans/2026-07-16-sponsor-pool-redesign-brief.md`. One sprint, one deploy, NO
migration — two allowlist serializer fields + a frontend rebuild of the browse grid and the
student detail page around a strict one-home-per-fact information architecture.

## What Was Built

**Backend (`serializers.py` — the allowlist, unchanged discipline):**
- **`field_image_slug`** on `SponsorPoolCardSerializer` — catalogue-first resolution chain:
  (a) `chosen_programme['course_id']` → `Course.field_key_id` → `FieldTaxonomy.image_slug`;
  (b) else `field_of_study` treated as a taxonomy key → `image_slug`; (c) else `''`
  (frontend falls back to the generic slug). The 37-row taxonomy map + course→field_key
  lookups are memoised on the serializer's per-request context, so a whole list is not N
  queries. Rationale: catalogue artwork shared by hundreds of courses is non-identifying.
- **`reporting_date`** (date-only, null-safe) — drives the "starts in N days" countdown;
  already sponsor-visible via the narrative/pathway text, a coarse date keeps it that way.

**Frontend:**
- **Shared image home** — new `lib/fieldImage.ts` (`FIELD_IMAGE_BASE`, `GENERIC_FIELD_SLUG`,
  `fieldImageUrl(slug)`); `useFieldTaxonomy.ts` now imports it instead of a second copy of
  the bucket URL (the brief's "one shared home" rule).
- **Pure helpers** — `lib/poolCard.ts`: `daysUntil`/`countdown` (hidden when null or past)
  and `inAmountBucket` (browse amount ranges), both node-tested.
- **Browse grid** — image-led cards: field-artwork banner with a soft gradient, a green
  "Verified" shield (every pooled student passed QC by construction), a conditional blue
  "Enrolment verified" badge, a ref-code pill, bold programme + "institution · state",
  academic + funding chips, an amber countdown, an italic blurb, and an amount + "Fully
  fund this student" footer. Filters are field / state / **amount** (client-side).
- **Detail page** — rebuilt to the IA, **no fact renders twice, no facts table**: a header
  card (slim banner strip + ref + state/academic chips + programme title + institution),
  a **verification strip** (Verified by BrightPath + Identity/Academic/Pathway/Financial
  ticks + a conditional Enrolment-confirmed tick), the narrative, and a sidebar action card
  (amount · "over N months" · Covers · amber countdown · CTA · **BrightPath balance** ·
  the exact privacy footer). The old `<dl>` facts grid + the standalone enrolment box are gone.
- **i18n** — 20 new `sponsorPool.*` keys × en/ms/ta (Tamil first-drafts); the sponsor-i18n
  hygiene + parity guardrail stays green.

## Field-image coverage audit (read-only, run against prod)

New `manage.py audit_pool_field_images` (no writes, no image generation) over the current
pool ∪ everyone ever pooled — **63 applications**:
- **(a) course→field_key: 25** · **(b) field_of_study key: 0** · **(c) generic: 38.**
- 10 distinct effective slugs; **all exist in the bucket, zero 404s** — no art gaps.

Findings for the owner:
- **~40% (25/63) get specific catalogue artwork; 38 fall back to the generic
  `umum-kemanusiaan.png`.** That is honest and looks fine (the gradient carries the overlay),
  but there's headroom.
- **Chain (b) never fires** — `field_of_study` values on live applications are free-text
  labels, not `FieldTaxonomy` keys, so the only path to specific art today is a confirmed
  `chosen_programme.course_id`. To lift the specific-art rate, either normalise
  `field_of_study` to taxonomy keys or ensure the confirmed programme carries a catalogue
  `course_id`. **No image generation is warranted this sprint** (nothing is missing — the
  gap is coverage breadth, not broken links).

## What Went Well
- The allowlist discipline made the backend a two-field change with the anonymity suite as
  the guardrail — extended (never weakened) to scan the two new fields.
- The per-request context cache killed the N+1 risk cleanly; DRF's `ListSerializer` shares
  the child's context across every item, so one taxonomy query serves the whole page.
- Pure helpers (`poolCard.ts`) kept the countdown/amount logic node-testable off the DOM.

## What Went Wrong (small)
- Two jest-matcher stumbles caught locally, not in review: `toBeInTheDocument` isn't set up
  in this project (no jest-dom) — use `.toBeTruthy()` / rely on `getByText` throwing; and
  emoji-prefixed labels (🛡️/⏳/✓) break exact `getByText` — match on `{ exact: false }`.
  `Number(null) === 0` also meant a null award had to be guarded explicitly in `inAmountBucket`.

## Numbers
- Backend: **2669 scholarship pytest** (incl. the new resolution-chain + reporting-date +
  new-field-leak tests). Frontend: **583 jest** (+ poolCard + browse-card + detail-IA tests);
  `next build` clean. One deploy (web + api on the same push; api rebuilds because
  `serializers.py` changed). NO migration.

## Carries (owner)
- **Tamil review** of the 20 new `sponsorPool.*` first-drafts.
- **Specific-art coverage** (optional): normalise `field_of_study` → taxonomy keys, or
  ensure confirmed programmes carry a `course_id`, to move students off the generic image.
  Nothing is broken; this is breadth, not a gap.
- Out of scope by the brief and untouched: My Students page + sponsorship cards, the
  fund/confirm flow internals, pool eligibility, partial funding (rejected — full-or-nothing).
