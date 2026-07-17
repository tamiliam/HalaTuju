# Implementation Brief — Sponsor Pool Redesign (image-led cards + refined detail)

**For:** the implementing agent (Opus 4.8), in `c:\Users\tamil\Python\Production\HalaTuju`
**Shape:** ONE sprint, one deploy, NO migrations. Backend = two allowlist serializer fields only; everything else frontend.
**Authority — build EXACTLY these, no simplification:**
- Browse grid mock: `stitch.withgoogle.com/preview/10844973747787673276?node-id=da6e43ca92d347b3851e07543a8640cb`
- Detail mock: `stitch.withgoogle.com/preview/10844973747787673276?node-id=594d11501b6b4f51bff8ee8cc0c1d921`
- The information-architecture table in §IA below (owner-settled 2026-07-16). Where a mock and the IA table disagree, the IA table wins.

## Context

The sponsor pool pages (`/sponsor` browse + `/sponsor/students/[id]`) under-use the data the anonymity-allowlisted API already serves and repeat the same facts in multiple places. The redesign (benchmarked against Funding Societies / LinkedFinance): image-led cards reusing the course selector's field artwork, an urgency countdown, a verification trust strip (our differentiator), and a strict one-home-per-fact architecture. Anonymity is inviolate: no student name, photo, contact, address, or school — the existing allowlist discipline continues.

## IA — one home per fact (acceptance criterion, not guidance)

| Fact | Card | Detail |
|---|---|---|
| Ref code | Banner pill | Header only |
| Field artwork | Card banner | Slim header banner strip |
| Programme + institution | Bold body line | Header title only |
| State | Merged into institution line ("· Perak") | Header chip only |
| Academic band | Chip | Header chip only (narrative elaborates in prose) |
| Verified | Shield badge on banner | Verification strip ONLY (no header badge) |
| Enrolment verified | 2nd badge when true | Fifth tick in the strip, conditional |
| Award amount | Footer, large | Sidebar only, large |
| Programme months | NOT on card | Sidebar ("over N months") |
| Funding categories | Chip | Sidebar ("Covers: …") |
| Reporting date countdown | Amber line | Sidebar amber row |
| Blurb (≤20 words) | Card only | NEVER (narrative replaces it) |
| Narrative | — | Body only |
| Sponsor balance | — | Sidebar, under CTA |
**On the detail page no fact may render twice. There is NO facts table anywhere.**

## Backend (`apps/scholarship/serializers.py` — the allowlist)

1. **`field_image_slug`** on `SponsorPoolCardSerializer` — resolution chain, catalogue-first:
   (a) `chosen_programme['course_id']` → `courses.Course.field_key_id` → `FieldTaxonomy.image_slug`;
   (b) else `app.field_of_study` treated as a taxonomy key → `FieldTaxonomy.image_slug` (direct PK lookup, tolerate miss);
   (c) else `''` (frontend falls back to the generic slug). Cache the taxonomy lookup per-request (the list serialises many apps — avoid N queries: prefetch or a module-level `dict` built once per request). Allowlist rationale in the docstring: catalogue artwork shared by hundreds of courses is non-identifying.
2. **`reporting_date`** on the same serializer — `app.reporting_date` as ISO date, null-safe, DATE ONLY (never a time). Docstring: already sponsor-visible today via the narrative/pathway text; date-only keeps it coarse.
3. **Tests (do not skip any):** the sponsor-card anonymity suite — extend the exact-keys/no-PII assertions to the two new fields; resolution-chain unit tests for (a)/(b)/(c) including an unknown key and a missing taxonomy row; `reporting_date` null case. Grep for any test asserting the card's exact field set and update it deliberately.

## Frontend

**Shared plumbing:** reuse the existing field-image URL pattern (`useFieldTaxonomy.ts` — public bucket `field-images`, generic fallback `umum-kemanusiaan.png`). Do NOT hard-code a second copy of the bucket URL — lift the existing constant into one shared home if needed. Countdown = days between today and `reporting_date` (hide the row when null or past; "N days away" wording per mock).

**Browse page** (`app/sponsor/(portal)/students/page.tsx`) per the grid mock:
- Card banner: field image, `object-cover`, soft gradient for overlay legibility; green "Verified" shield top-right; ref-code white pill bottom-left; blue "Enrolment verified" second badge only when true.
- Body: bold programme name; muted "institution · state"; chips (academic band; funding categories); amber countdown line; italic blurb.
- Footer: amount large + primary "Fully fund this student" button.
- Header: live count + the three filter chips (field / state / amount) — wire field+state filters client-side over the loaded list (the API list is small); amount filter = simple ranges.

**Detail page** (`app/sponsor/(portal)/students/[id]/page.tsx`) per the detail mock + IA:
- Header card: slim banner strip (same image system), ref + state chip + academic chip, programme title + institution line. Nothing else.
- Verification strip: "Verified by BrightPath" + four static ticks (Identity, Academic record, Study pathway, Financial need — every pooled student has passed QC by construction) + conditional fifth "Enrolment confirmed" tick from `enrolment_verified`. Caption per mock.
- Narrative card: render `anon_profile` markdown as today (three paragraphs, no headings).
- Sidebar action card: amount (large) · "over N months" · Covers row · amber countdown · CTA · **"Your BrightPath balance: RM X" (the mock omitted it — REQUIRED)** · footer note with EXACTLY this copy: "You'll receive semester progress updates. Personal details are never shared." **Do NOT ship the mock's invented "100% of your contribution…" claim.**

**i18n:** every new string in en/ms/ta under the guarded `sponsorPool.*` namespace (the sponsor-i18n parity test must stay green). Countdown pluralisation handled per locale convention already used elsewhere.

**Out of scope (do not touch):** the My Students page and sponsorship cards (follow-up); the fund/confirm flow; any backend pool eligibility logic; partial-funding mechanics (deliberately rejected — funding is full-or-nothing; no progress bars).

## Field-image coverage audit (required deliverable, not optional)

Before closing: a small script/management-command run (read-only) listing every DISTINCT resolved `field_image_slug` for current pool + recently pooled applications, checking each URL exists in the bucket (HEAD request), and reporting: total fields seen, resolved via (a)/(b)/(c) counts, and any 404 slugs. Findings go in the retro. NO image generation in this sprint — art gaps are reported for an owner-approved follow-up.

## Tests & verification

- Backend: extended anonymity suite + resolution-chain tests; full pytest green.
- Frontend: jest for card rendering (badges conditional, countdown null-safe, no-months-on-card), detail (no facts table renders; balance line present), i18n parity; `next build` clean.
- Review checklist item: walk both pages against the IA table — any fact appearing twice on the detail page fails review.
- After push: match Cloud Build by SHORT_SHA (`gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com`); smoke: pool browse renders with real field images (spot-check 3 cards), detail page for one student, sponsor balance shows, countdown correct vs the student's reporting date.

## Sizing & risks

~12–16 files. Risks: (1) N+1 queries from the image lookup on the list — the per-request cache is mandatory; (2) taxonomy-key drift (`field_of_study` values that aren't keys) — tolerated by chain (b)'s miss-handling + surfaced by the coverage audit; (3) banner crops looking poor on some art — acceptable this sprint (gradient helps); the audit report tells the owner where regeneration is worth it; (4) breaking the existing anonymity tests — they are the guardrail, extend them, never weaken them.
