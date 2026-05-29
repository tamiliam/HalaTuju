# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.12.0] — S23: income proof now required (2026-05-29)

- **Proof of household income is now a required document.** Previously the income-proof card (STR / salary slip / EPF) sat in the Optional section; an applicant could mark Documents as complete without uploading any income evidence. Any one of `{str, salary_slip, epf}` satisfies the gate — STR families are encouraged in the card explainer to ALSO upload a salary slip and/or EPF statement for every working household member, but one upload is enough to pass completeness.
- **Card explainer rewritten for B40 directness:** *"If your family is an STR recipient, please upload a screenshot of your STR portal showing your parent's name and NRIC. We strongly encourage you to also upload the latest salary slip and/or EPF statement for every working member of the household."* The previous "Any one is fine…" wording understated how much admin uses the extra documents to cross-check the household income figure typed at /apply.
- **`documents_done` rule (backend `services.application_completeness` + frontend `documentsComplete`)** extended: `ic + results_slip + parent_ic + (str ∨ salary_slip ∨ epf)`. The IncomeProofCard moved from the Optional section to the Required section on the Documents tab. `requiredNote` copy dropped "two" (now four cards in Required).
- **Tests:** backend `+4` (`test_documents_done_false_when_income_proof_missing` + three positive cases per income-proof type) — scholarship test_details suite 38/38 pass. Frontend jest `+4` (one negative + three positive variants + multi-upload case) — 156/156 pass. `_make_complete` helper extended to include an STR doc so the existing `test_complete_when_all_present` still asserts a 7-part green.
- **No migration.** Choices were already on `ApplicantDocument.DOC_TYPES` since S4; only the completeness rule changed. **No backfill.** Live applications already shortlisted (just Elanjelian on prod) get the new requirement at next page load — they re-open the Documents tab and upload one income proof.

## [2.11.1] — Name-mismatch chip directs to /profile (2026-05-29)

- **Vision OCR name-soft chip on the Documents tab now tells the student where to fix it.** When Vision reads the name on the IC slightly differently from the typed name, the most likely cause is a typo at /apply, not a problem with the IC. New copy: *"Your NRIC matches but the name on your IC reads slightly differently. The name on your IC is the official one — please update your profile to match it exactly."* + a *"Edit your name in your profile"* link below the chip pointing to `/profile`. Applies only to the `name-soft` variant (NRIC mismatch left unchanged; NRIC is locked once admin-verified anyway). i18n parity 1370 × en/ms/ta (+1 new `name-soft-action` key; Tamil first-draft queued). Frontend-only; tests 154/154 pass; web-only deploy.

## [2.10.1] — Stream dropdowns sorted alphabetically (2026-05-29)

- **Stream-subject dropdowns now list options alphabetically by display name** (locale-aware), matching the elective dropdown. Applies to both the SPM grades page (`onboarding/grades`) and the STPM SPM-prerequisite page (`onboarding/stpm-grades`). With the Arts pool now at 38 subjects (S18), a sorted list is much easier to scan. Pre-filled default stream subjects are unaffected — they still read the canonical pool order. Frontend-only; no test or backend change.

## [2.11.0] — S19: minor consent flow hardening + UX iteration round (2026-05-29)

Composite sprint after S18 ship. Six commits, one headline (minor consent v2) plus four
copy/UX iterations the user drove through live, plus a follow-up policy change on
`parent_ic` requirement. All shipped to prod incrementally.

- **Minor consent v2** (`7a9e8cb`). Pre-S19 the minor branch trusted typed values
  unconditionally; this iteration closes the gap. Added: parent NRIC field (masked
  `XXXXXX-XX-XXXX`, stored in new `Consent.guardian_nric` column via migration
  `scholarship/0021`); structured 7-option relationship dropdown (father, mother,
  legal_guardian, grandparent, brother, sister, relative — "older_sibling" split into
  brother+sister; "other_relative" shortened to relative; no "Other" per user); consent
  text body interpolates `{student_name}`, `{student_nric}`, and pronouns derived from
  the student's NRIC last digit (`gender_from_nric` helper); **hard-gate** name + NRIC
  match against `parent_ic` Vision OCR (was a soft anomaly flag in S17 — now blocks
  consent POST with 400 `parent_ic_nric_mismatch` / `parent_ic_name_mismatch`); FE
  pre-checks live and disables the toggle on mismatch; OCR-disclosure paragraph removed
  from consent body (stays in Documents step where OCR actually happens). `CONSENT_VERSION`
  bumped `2026-draft-2` → `2026-draft-3` (0 pre-existing consents on prod, forward-only).
- **Layout iteration** (`abdfab5`). User feedback after seeing S19 in the browser: simpler
  parent-voice body in B40 language (two short paragraphs); moved the subtitle into a
  student-directed blue info-box ("As you are under 18, please ask your parent or guardian
  to read the following section…"); removed the redundant guardianNotice line; moved the
  `needParentIc` warning UP into that slot, conditional on `!hasParentIc` (hide when
  uploaded). DRAFT label removed from both adult and minor branches (still a working
  model, but the DRAFT banner no longer fits).
- **InfoBox + bold consent body** (`cf9b1d4`). New `components/InfoBox.tsx` locks the
  box-colour convention across `/application`: green=success, blue=info, amber=warning,
  red=block; fixed `rounded-lg p-3 text-sm` + `text-{color}-800` body. Applied to consent
  warnings + funding intro + save-error block. Adult subtitle dropped (consent body is
  self-explanatory). Consent body renders `**bold**` markers (markdown style) as
  `<strong>` — used for student name, NRIC, and the programme name. Tiny `renderRich`
  helper, 5 lines.
- **Box-ify all tab intros** (`d6c0505`). Every `/application` step now opens with one
  instruction-led blue InfoBox where applicable (Story langNote, Funding intro merged
  from two stacked paragraphs, Documents step4Body rewritten as instruction). step6Body
  intro on Consent tab removed (redundant). minorInfoNotice trimmed (dropped "As you are
  under 18 years of age," prefix — the consent body itself states the under-18 fact).
- **parent_ic universal compulsory** (`35d61b3`). Per user direction: even adult applicants
  need to upload parent's IC, because the admin cross-checks supporting docs like STR or
  EPF (typically issued in a parent's name) against the parent's IC. `documents_done` now
  requires `{ic, results_slip, parent_ic}` universally; `guardian_docs_done` simplified
  (parent_ic moved out; minor branch only checks the conditional `guardianship_letter`).
  Help text rewritten universal × en/ms/ta. Forward-looking, not retroactive — 12 currently
  submitted apps are all pre-decision-reveal so they see the "received" status card not
  the Documents tab; only Elanjelian (test) is at /application today.

**Tests** — backend **1236 / 1236 pass** (+12 from 1224 at S17 close: 4 TestGuardianDocsDone
restructure, 4 new TestConsentApi for NRIC-mismatch/name-mismatch/missing-nric/hyphen-strip
+ 3 minor relationship test updates + 1 new TestGuardianDocsDone case for parent_ic moved
out). Frontend **jest 154 / 154** (documentsComplete suite rewritten in-place to drop the
isMinor flag tests).
**Migration applied via Supabase MCP** (TD-058 workaround): `scholarship/0021` — additive
`ADD COLUMN guardian_nric` + choices-only `AlterField` for new GUARDIAN_RELATIONSHIPS list.
**i18n** parity 1369 × en/ms/ta. Tamil first-draft mirrors queued (queue now 10 batches).
**Deploys**: 6 (one per commit). All small; total under-budget.

## [2.10.0] — S18: SPM stream subject coverage — full Arts & Technical lists (2026-05-29)

A user reported that the SPM apply-form stream dropdowns offered far fewer subjects than the official SPM list. Root cause: the Arts pool listed only 9 subjects and Technical only 8, while `SUBJECT_NAMES` already had labels for ~26 of the missing Arts subjects — they were simply never added to the selectable pool. Worse, the backend merit engine kept its **own** hardcoded copy of these pools, so any subject in the dropdown but absent from the backend pool would silently score on the 10% elective weight instead of the 30% stream weight. This sprint brings both into line with the official source (Islamic-stream subjects excluded per the product's mainstream scope) and keeps frontend and backend pools in lockstep.

### Changed
- **Subject model (`subjects.ts`): single `category` → `streams` list.** A subject can now belong to more than one stream pool (e.g. the sciences appear under both Science and Technical, matching the official SPM elective grouping) while remaining electable. Derived exports (`SPM_CORE_SUBJECTS`, `SPM_STREAM_POOLS`, `SPM_ALL_ELECTIVE_SUBJECTS`, `SPM_PREREQ_STREAM_POOLS`) keep their names and shapes — **no consuming page changed.**
- **Arts stream pool: 9 → 38 subjects.** Adds the full non-Islamic official list — languages (Arabic, Iban, Kadazandusun, Punjabi, Semai), literatures (English, Chinese, Tamil, Communicative Malay), performing & visual arts (Dance, Choreography, Acting, Scenography, Music subjects, 2D/3D Fine Art, Graphic/Industrial/Craft Design, Creative Multimedia, Script Writing, Performing Arts Production, Art History & Management), and Bible Knowledge.
- **Technical stream pool: 8 → 16 subjects.** Now matches the official Science-Technology-Vocational grouping: the four engineering studies, Engineering Drawing, Technical Graphics, Computer Science, Inventions, plus Asas Kelestarian, Pertanian, Sains Rumah Tangga, Sains Sukan, Sains Tambahan, and the sciences (Bio/Fizik/Kimia/Add Maths). `Multimedia` moved out of Technical to elective-only (it maps to the Arts group in the source).
- **Backend merit pools (`engine.py`) expanded to mirror the frontend** and lifted to module-level constants (`SCIENCE_POOL`, `ARTS_POOL`, `TECHNICAL_POOL`) so the 30% stream weight (Sec2) recognises every selectable stream subject. A code comment ties the two definitions together.

### Added
- Two new subject keys with labels: `bahasa_punjabi` (Punjabi Language) and `bible_knowledge` (Bible Knowledge).
- `subjects.test.ts` (12 tests): pool composition counts, Islamic-exclusion, sciences-in-both-pools, the "selected-as-stream-subject disappears-from-electives" dedup invariant, and label coverage for every selectable subject.
- `test_merit_pools.py` (7 tests): pool membership mirrors the frontend, and arts/technical stream subjects land in Sec2 (30%) not Sec3 (10%).

### Notes
- **No migration, no data backfill** — subject keys are not persisted as enums; grades are stored by key. Existing saved grades are unaffected.
- Golden master unchanged (SPM 5319): the new keys aren't held by the baseline students, and the science/technical pool overlap resolves the stream tie to Science by ordering, so pure-science merit is identical. Verified, not assumed.

## [2.9.0] — S17: minor consent flow — re-voiced text, parent IC + guardianship letter, structured relationship (2026-05-29)

The pre-S17 minor branch was a half-measure: it captured guardian name + free-text relationship + flipped the toggle label, but the consent body still read "I consent…" (student voice) and we trusted the typed guardian name with no identity verification. Lawyer review needs a defensible end-to-end flow. This sprint delivers that working model — single push, one migration, ready for legal sign-off.

- **Re-voiced consent text for minors.** New `scholarship.consent.textMinor` i18n block — full parent-voice paragraph: *"I am the parent or legal guardian of the named applicant, who is under 18 years of age. On their behalf, I consent to… I confirm that I have legal authority to give this consent for the applicant."* Replaces the prior toggle-label-only minor cue.
- **Structured `guardian_relationship` dropdown** (6 codes, no free-text): `father`, `mother`, `legal_guardian` (court-appointed), `grandparent`, `older_sibling`, `other_relative`. "Other" intentionally excluded per user direction — if no fit, the right path is a court-appointed `legal_guardian` with a letter. Backend rejects any value not in the structured list (`ConsentCreateSerializer.validate_guardian_relationship` → 400).
- **Parent/guardian IC upload required for minors.** New doc type `parent_ic` on `ApplicantDocument.DOC_TYPES`. Auto-Vision-OCR'd on upload (reuses the S13 pipeline). Compulsory in the Documents tab when applicant is a minor; backend blocks consent POST with 400 `parent_ic_required` if missing.
- **Guardianship letter required for non-parent guardians.** New doc type `guardianship_letter`. Pragmatic acceptance (per user direction): a court-issued guardianship order OR a parent's written authorisation letter — both count. Backend blocks consent POST with 400 `guardianship_letter_required` when `needs_guardianship_letter(relationship)` is true and the doc isn't uploaded. Shown in the Optional section of the Documents tab when minor (the relationship is picked only at consent time).
- **Completeness rule now 7-part.** `application_completeness` gains `guardian_docs_done`: trivially true for adults; for minors requires `parent_ic` uploaded, AND if the latest active consent's relationship is non-parent also `guardianship_letter`. `complete = quiz + story + funding + docs + consent + address + guardian_docs`.
- **2 new anomaly rules** (S16 Phase A engine):
  - `parent_ic_name_mismatch` — Vision-OCR name on `parent_ic` differs from the typed guardian name on the consent (token-set via the existing `name_match`).
  - `parent_ic_underage` — Vision-OCR NRIC on `parent_ic` indicates age < 18. The "guardian" is themselves a minor — hard signal for the admin.
- **CONSENT_VERSION bumped** `2026-draft-1` → `2026-draft-2`. Existing active `2026-draft-1` consents become outdated; student/guardian re-attests with the new flow on next visit. Honest re-consent for a substantive identity change. **Prod check at sprint close: zero existing consent rows** (the live programme is still dormant), so the bump is purely forward-looking — no real applicants need to re-attest.
- **Migration `scholarship/0020`** — choices-only (no DDL); applied as a direct `django_migrations` insert via Supabase MCP per the TD-058 workaround. `Consent.guardian_relationship` keeps its `CharField(100)` storage; choices enforced at the serializer + admin level. Pre-S17 free-text consent rows (none on prod) would stay readable.
- **Admin verify-&-accept card** gains a "Parent/guardian IC (Vision OCR)" row when present — surfaces extracted NRIC + name + address + Re-run link. No automated verdict on this card; the new anomaly rules surface the verdicts in the Pre-interview flags card above.
- **i18n** parity 1356 × en/ms/ta (+20 keys: consent textMinor + 6 relationship labels + relationshipPlaceholder + needParentIc/Letter + 2 doc-type labels + 2 doc-help + 1 admin parentIcTitle + 2 anomaly pairs). Tamil first-draft mirrors queued — **batch is now 9 deep**.
- **Tests** — backend **1224 / 1224 pass** (+13 new: 4 TestGuardianDocsDone; 4 TestConsentApi for parent_ic_required + guardianship_letter_required + non-parent-with-letter OK + invalid-relationship rejected; 3 minor-relationship test updates; 4 anomaly tests for the two new rules). Frontend **jest 112 / 112** (+2: documentsComplete minor signature; DOC_TYPES length bump 11 → 13).
- **1 deploy**; under budget.

## [2.8.0] — S16 Phase A: deterministic anomaly engine for pre-interview flags (2026-05-29)

First slice of the post-shortlist vision (`docs/scholarship/post-shortlist-vision.md`). Single focused sprint.

- **Engine** (`apps/scholarship/anomaly_engine.py`). Pure module: 10 `_detect_*` functions registered in a `_DETECTORS` tuple, plus one `detect_anomalies(application) → list[dict]` aggregator returning JSON-ready `{code, params}` dicts. Each rule null-safe over missing profile / docs / funding_need. No LLM calls, no model writes — all deterministic. The 10 rules (per the user-calibrated taxonomy):
  - `vision_nric_mismatch`, `vision_name_mismatch` — built on S13's OCR verdicts.
  - `address_state_mismatch` — Vision-OCR'd state ≠ `profile.preferred_state`, with W.P. prefix normalisation.
  - `jkm_high_income` — `receives_jkm=true` AND `household_income > RM3000`; question reframed to acknowledge disability/caregiving (JKM is family-applied, not student-applied — the user corrected my first framing).
  - `household_size_one`, `first_in_family_with_siblings_studying` (question preempts the school-vs-university distinction).
  - `funding_other_without_note`, `declaration_name_mismatch` (token-set via `vision.name_match`).
  - `str_claimed_no_doc` — `receives_str=true` AND no `doc_type='str'` upload. New rule per user suggestion.
  - `device_in_funding` — laptop won't fit in the RM 3,000 cap alone. New rule per user suggestion.
- **Three suggestions deferred to Phase B** (need Gemini multimodal): utility-bill amount vs household size; SOI content-derived questions; "wrong" supporting doc detection. Honest scope.
- **Admin UI** (`admin/scholarship/[id]/page.tsx`). New "Pre-interview flags" card above verify-&-accept; amber-tinted list, one entry per flag, each renders the observed fact + the suggested question via i18n with the engine's `params` interpolated. Empty-state: *"No automated flags. Use your judgement during the interview."* — the engine is honest about silence. Flag count chip in the card header.
- **Backend wiring**: `AdminApplicationDetailSerializer` adds `anomalies = SerializerMethodField`, called per GET (no cache; the function is cheap and pure). Read-only.
- **Frontend type**: new `AdminAnomaly { code, params }` interface in `admin-api.ts`; `AdminScholarshipDetail.anomalies: AdminAnomaly[]`.
- **i18n**: 26 new keys per locale (5 UI scaffolding + 10 facts + 10 questions + 1 askLabel). Parity 1336 × en/ms/ta. Tamil first-draft mirrors queued for batch refine — **queue is now 8 batches / ~85+ strings**.
- **Tests**: 23 new in `test_anomaly_engine.py` (one positive + one negative per rule + integration shape tests for empty input, dict shape, ordering stability). 193/193 scholarship pytest. Next build EXIT=0.
- **Live preview for app #3** (Elanjelian, shortlisted): expected 2 flags on first load — `address_state_mismatch` (IC: KEDAH vs profile: Putrajaya) + `str_claimed_no_doc` (`receives_str=true`, no STR doc uploaded). First real-data validation of the engine.
- **No migration**. No backfill needed.

## [2.7.0] — S15: Story tab polish + Vision MyKad address + single-instance docs (2026-05-29)

Composite sprint after S14 ship. Four discrete pieces, all deployed; see retrospective for the journey.

- **Story tab polish on /application** (`53afbad`). Live-testing feedback converted to four UX/UX-data items:
  - **Tick boxes → slide toggles** on `firstInFamily` + the Consent agreement, matching /apply's `Toggle` (STR/JKM). `FieldLabel` extracted from /apply to `src/components/FieldLabel.tsx` so /application reuses the same `*` convention.
  - **Siblings: boolean → numeric.** "One or more of my siblings are also studying" replaced by "How many of your siblings are also studying?" — useful proxy for family education burden. Backend: migration `scholarship/0019` adds `siblings_studying_count: PositiveSmallIntegerField(null=True, blank=True)`; legacy `siblings_studying` boolean kept for back-compat (joins TD-061 contract). `profile_engine._build_prompt` prefers the count over the boolean.
  - **Placeholder ghost text + collapsible "Need ideas?" tips** on all 6 open textareas (parentsOccupation, familyContext, aspirations, plans, dailyLife, fears). Native `<details>` panels with 3 short bullets each. Tone deliberately first-person + slightly imperfect — student should think *"I can write better than that"*.
  - **Asterisk convention.** Required Story-tab fields (aspirations, plans, street, postal, city) gain `*` via `FieldLabel required`; optional fields drop the "(Optional)" suffix. Matches /apply.
- **Vision OCR for MyKad address surface** (`69cb1d0`, `0fb08a3`, `4baae5f`). Building on S13's MyKad name+NRIC OCR: now also extract the home address from the IC photo. Migration `scholarship/0018` adds `vision_address: CharField(max_length=500)`; new `_extract_address` helper in `vision.py` uses a postcode-anchor heuristic to walk up the OCR text, drops the NRIC + name lines, strips "Alamat" labels, and now also picks up the state line below the postcode + the taman/kampung line above. Soft signal only — no matcher, no verdict; admin verify-&-accept card surfaces the extracted address alongside the student-entered `profile.address` for eyeball cross-check at interview time. The heuristic-tuning journey took 3 deploys against the real MyKad — first miss (state below postcode), second miss (TAMAN SEMANGAT dropped as "looks like a name"), final pass captures all 4 lines.
- **Single-instance doc-type replace on re-upload** (`2ee7d5d`). Previously, a student could upload multiple IC photos and the system kept all of them — leaving the admin to guess which was authoritative. Now: `DocumentListCreateView.POST` sweeps any existing rows of the same single-instance doc type (DB + Supabase Storage blob) before creating the new one. The three income-proof types (STR / salary_slip / EPF) intentionally stay multi-instance for monthly slip stacking. Explicit `DELETE` also sweeps the Storage blob (was leaking blobs on every Remove click). UI label flips from "Add more" → "Replace" for single-instance types. TD-062 logged for the orphan Storage blobs that pre-fix Remove clicks left behind (sweep when convenient).
- **Post-shortlist vision doc** (`87404e1`). Direction-setting `docs/scholarship/post-shortlist-vision.md` — four user types (student done; admin needs role categories; sponsor + mentor to do), funnel through interview/sponsorship/in-programme, three-engine gap model (deterministic rules + Vision OCR + Gemini), two-stage profile (draft → interview findings → final), standardisation north star. Recommended Phase A = deterministic anomaly engine as the first slice.

**Tests** — backend 1188 (+19: 5 vision address extraction, 3 docs single-instance, 6 details siblings count, 2 profile_engine count fallback, +3 from related); frontend jest 110 (+4: siblings count round-trip + prefill behaviour).
**i18n** parity 1310 × en/ms/ta (+34 keys; Tamil first-draft mirrors queued for batch refine — pending queue is now 7 batches).
**Migrations applied via Supabase MCP** (migrate-first per TD-058 workaround): `scholarship/0018_applicantdocument_vision_address`, `scholarship/0019_scholarshipapplication_siblings_studying_count`. Both additive, 0 rows touched.
**Deploys**: 5 over the sprint (3 Vision address tuning + 1 single-instance docs + 1 S15 polish). The 3 Vision deploys were a heuristic-tuning loop against real-data feedback — captured as a lesson (test fixtures alone can't validate OCR heuristics; user-driven verification is essential).

## [2.6.0] — S14: /profile schema consolidation + required address on /application (2026-05-29)

Backend + frontend (no migration; data backfilled via Supabase MCP under the expand-contract pattern). Closes
four /profile gaps surfaced during live user-testing: redundant income/siblings/phone fields that didn't sync with
/apply, plus the missing physical address capture for shortlisted applicants.

- **/profile family card.** Replaced the `family_income` range dropdown with an open RM input bound to
  `household_income` (same column /apply already writes) and re-labelled "Number of Siblings" → "Household size"
  on `household_size` (also shared with /apply). One source of truth for income + household composition.
- **/profile Contact & Location.** Dropped the dead `phone` input (the visible Contact Phone in Contact Details
  is the synced one). No behaviour change for users; the deprecated input is just gone.
- **Contact Email auto-default.** `ProfileView.get` now falls back to the auth-user email when
  `profile.contact_email` is blank, and reports it as verified (Google/Supabase already verified that mailbox).
  Read-time fallback only — the DB row stays empty; a user-set contact email still wins and uses its real
  verification flag.
- **/application Story tab — new "Where you live" card.** Street + postcode + city inputs under the Family card.
  State stays read-only ("from your application" — sourced from `profile.preferred_state`). One Save button
  writes everything; `save_application_details` persists the address sub-fields to the profile (alongside the
  narrative on the application). Pre-fills from `profile.address`/`postal_code`/`city` on next read.
- **Completeness rule now 6-part.** `application_completeness` gains `address_done` (street + postcode + city
  all non-blank); `complete = quiz + story + funding + docs + consent + address`. Story tab tick requires both
  the narrative AND the address. Existing shortlisted applicants must add their address to reach "complete".
- **Conflict policy doc'd** on `buildApplicationPayload`: last-write-wins on shared profile fields.
- **TD-061 logged** (drop the three dead columns next session under expand-contract).
- **Backfills run on prod via Supabase MCP** (before push): `household_income` populated from `family_income`
  range midpoints (41 rows), `household_size = siblings + 2` (42 rows), phone-promotion no-op (all 6 dead-phone
  rows already had `contact_phone`), contact_email auto-default is read-time so no DB write needed.
- **i18n** parity 1276 keys × en/ms/ta — Tamil first-drafts for the new keys (`profile.householdIncome*`,
  `householdSize*`, `scholarship.nextSteps.story.cardAddress.*`) **pending user refine**.
- **Tests** — backend +3 (address_done, address PATCH writes to profile, contact_email auto-default ×2);
  frontend +4 (buildDetailsPayload address, applicationToDetailsForm address pre-fill + defaults).
  151/151 scholarship pytest + 106/106 jest, build green (EXIT=0).

## [2.5.0] — S13: Vision OCR for MyKad — soft signal at upload + verify-&-accept (2026-05-28)

Backend + frontend + admin (additive migration `scholarship 0016`, migrate-first via Supabase MCP). When a student
uploads their **IC**, Google Cloud Vision is auto-triggered server-side; the student sees an instant chip below the
file row ("looks good" / "name slightly different" / "NRIC doesn't match" / "couldn't read"), and the admin sees the
same signal as a row inside the verify-&-accept card. **Vision is a soft hint only — never a hard block.** The admin
verify-&-accept (S11a) remains the real identity gate. Resolves the post-launch fast-follow flagged at S12 split.
- **Backend (`apps/scholarship/vision.py` + `views`):** new `vision.py` with pure matchers (`nric_match`,
  `name_match` returns match/partial/mismatch) + a graceful-degradation entry point (`run_vision_for_document`)
  that fetches the image from Supabase Storage, calls Cloud Vision `document_text_detection`, extracts NRIC + name,
  and writes 4 new `ApplicantDocument` fields (`vision_nric`, `vision_name`, `vision_run_at`, `vision_error`). The
  IC `record-document` POST auto-triggers it; a new admin endpoint `POST .../documents/<id>/re-run-vision/` lets the
  coordinator retry. **All Vision calls are mocked in tests** (8 pure-matcher tests + 3 IC auto-trigger tests + 4
  admin re-run tests); **no paid calls** during build. The serializer also exposes server-computed
  `vision_nric_verdict` / `vision_name_verdict` so the frontend doesn't reimplement the matchers (S5c-lesson).
- **Migration `scholarship 0016`** — additive 4 columns; applied migrate-first via Supabase MCP (per the TD-058
  workaround) before the push.
- **Frontend (student):** the IC card helper now reads *"…we'll check it automatically to help you spot typos —
  your photo isn't kept at Google."* A `VisionChip` renders below the IC file row in one of four variants (green
  ✓ match · amber ⚠ name-soft · amber ⚠ NRIC-bad · neutral ⓘ unreadable), driven by the server verdicts.
- **Frontend (admin):** a new "Vision OCR (soft signal)" row inside the verify-&-accept card — two coloured pills,
  the raw extracted NRIC + name, a `Re-run Vision` link, and the declaration name shown for cross-check. Stitch was
  skipped on the admin side (S5b precedent — internal admin UI doesn't go through Stitch).
- **Consent text bump** — appended one sentence honestly disclosing automated OCR processing on uploaded documents
  (still PDPA-aligned: data already collected; transient processing). Inline privacy hint in the IC card too.
- **API key path deferred to post-deploy.** The Cloud Vision API isn't enabled yet — the new code degrades to
  `vision_error="AI service not configured"` and the student sees the neutral "couldn't read" chip. **One real
  end-to-end check is admin-triggered (billable) and waits for the user's explicit greenlight.**
- Gates: backend **1162 pytest** (+21), `next build` **EXIT=0** (explicit exit-code check, TD-059 lesson), i18n
  parity **1257** ×3. Tamil first-draft pending user refine (consistent with S4/S5a).

## [2.4.7] — TD-059 cleanup: drop dead `FundingNeed` amount columns (2026-05-28)

Backend + frontend cleanup, **destructive migration** (`scholarship 0015`). The S3 funding reframe (v2.4.2) left
9 line-item amount columns on `FundingNeed` orphaned (no readers, no writers, no UI). This drops them.
- **Backend:** `FundingNeed` loses `tuition_gap`, `laptop`, `hostel`, `transport`, `books`, `monthly_allowance`,
  `allowance_months`, `other`, `other_desc` and the `total` property (and the `__str__` line that used it).
  `FundingNeedSerializer.fields` shrinks to `categories`/`funding_note`/`programme_months` only. Stale model + payload
  tests dropped or rewritten to use `categories`.
- **Frontend:** `FundingNeed` interface, `DetailsFormState` (8 form fields removed) and the `fundingTotal` helper +
  its jest tests; payload/form mappings in `applicationToDetailsForm`/`buildDetailsPayload` shrunk to the 3 kept
  fields. `/admin/scholarship/[id]` no longer shows `RM${funding_need.total}` — shows the **ticked categories** list.
- **Migration ordering — expand-contract (deploy-first, drop-after).** For a destructive change, dropping columns
  before the deploy would 500 the currently-live `FundingNeedSerializer`. So: code shipped first (Django ignores
  extra DB columns), then `DROP COLUMN ×9` applied on prod via Supabase MCP + `django_migrations` row recorded
  (per the TD-058 workaround). 0 prod rows in `funding_needs` confirmed before the drop.
- Build clean; backend 1141 pytest; jest 123; i18n unchanged (parity 1246). **Resolves TD-059.**

## [2.4.6] — AI sponsor-profile generator rebuilt + Tamil/BM-aware (Step-4 redesign, S5c) (2026-05-28)

Backend + admin frontend, **no migration**. **Resolves TD-060.** `profile_engine.py` was building its Gemini prompt from
fields the profile-canonical refactor removed (`qualification`/`spm_a_count`/`household_income`/`stpm_pngk`) plus
legacy/dead ones — it would have 500'd if an admin clicked "Generate". Rebuilt against the current data model **and**
made language-aware.
- **`_build_prompt` rewritten** to read profile-canonical academic/financial data (`profile.exam_type`,
  `count_spm_a_grades(profile.grades)`, `profile.stpm_cgpa`, `household_income/size`, `receives_str/jkm`), the "Your
  story" narrative (`aspirations`, `plans`, `first_in_family`, `parents_occupation`, `siblings_studying`,
  `family_context`, `daily_life`), the pathway (`field_of_study` + `pathways_considered`), and the simplified funding
  (`categories` + `funding_note` + `programme_months` — **not** the dead `total`/TD-059) + referees.
- **Language-aware:** the prompt tells the model the student's own words may be in **Malay, English, or Tamil**
  (understand all three) and to write the profile in a **target language**. `generate_sponsor_profile(application,
  language=None)` defaults output to the applicant's locale (en→English, ms→Malay); the admin can override via a small
  **EN / BM** selector on `/admin/scholarship/[id]`. (Tamil *output* deferred to Phase 2 — sponsors read EN/BM — but
  it's now a one-line prompt-parameter change.)
- **Tests:** new `test_profile_engine.py` (8) exercises the pure prompt builder — current fields present, multilingual
  + target-language instructions present, no dead `total`, language resolution, and the **TD-060 regression** (no
  `AttributeError` on a current-model application). Gemini stays mocked; **no live/paid calls** were made.
- Build clean; backend 1143 pytest; i18n parity 1246. **Note:** a true end-to-end generation check is an
  admin-triggered live (billable) Gemini call — run it when ready; the programme is still dormant.

## [2.4.5] — Admin records the referee at verify-&-accept (Step-4 redesign, S5b) (2026-05-28)

Backend + admin frontend, **no migration** (the `Referee` model already exists). The Step-4 redesign moved the referee
out of the student flow; this lets the **coordinator record it at the verify-&-accept stage**, which previously had no UI.
- **Backend:** new PartnerAdmin-scoped endpoints — `GET/POST /api/v1/admin/scholarship/applications/<pk>/referees/`
  (list/add) and `DELETE …/referees/<ref_id>/` (remove, scoped to the application). Reuses `RefereeSerializer`. Tests
  for add/list/delete, name-required, wrong-application 404, and admin-only access.
- **Admin frontend:** the Referee section on `/admin/scholarship/[id]` is now interactive — lists referees with a
  remove action and an add form (name, role, relationship, phone, email). New `addReferee`/`deleteReferee` admin-API
  helpers. i18n ×3 (parity 1245).
- Build clean; backend 1135 pytest. **Finding logged as TD-060:** the AI sponsor-profile generator (`profile_engine.py`)
  references fields the profile-canonical refactor removed (`qualification`/`spm_a_count`/`household_income`/`stpm_pngk`)
  plus legacy/dead ones — it would error if invoked. Its rebuild + Tamil/BM-awareness is **S5c** (next).

## [2.4.4] — Completeness finalise + "What happens next" (Step-4 redesign, S5a) (2026-05-28)

Backend + frontend, **no migration**. Closes the completeness loop and gives the student a reassuring finish.
- **Backend:** `application_completeness` gains **`consent_done`** (an active `Consent` row exists) and **`complete`
  now = quiz + story + funding + compulsory-docs + consent** (the full 5-part rollup; supersedes S4's interim
  "complete excludes docs/consent"). The read serializer now exposes **`notify_email`** (read-only — the address
  decision/comms emails are actually sent to). Tests updated to the new contract + `consent_done` cases.
- **Frontend:** `ScholarshipNextSteps` now wires the **real Documents + Consent step ticks** (S4 added
  `documents_done` to the backend but the UI still hardcoded them to false). Once all five steps are done, the intro
  banner switches to a green **"You're all set!"** state and a new **"What happens next"** panel appears — a 3-step
  plain-language timeline (we review → we may call you in your preferred language → decision by email) plus a note
  stating the exact email updates go to. i18n ×3 (parity 1235; Tamil copy first-draft pending user refine).
- Progress bar, "Step X of 5", per-step ticks and the desktop 2-column rail were already delivered in S1 — this
  sprint only wired the remaining signals and added the finish panel. Build clean; backend 1128 pytest.
- **Deferred to S5b:** admin referee-at-verify-&-accept + Tamil-aware AI sponsor-profile. **TD-059** (drop dead
  `FundingNeed` amount columns) still queued.

## [2.4.3] — Documents — compulsory vs optional, with explainers (Step-4 redesign, S4) (2026-05-28)

Backend + frontend (migrate-first: `scholarship 0014`, choices-only — no DDL, row recorded on prod before deploy).
Reworks the Documents tab so the **two compulsory documents are clearly separated from the optional ones**, each with
a one-line "what to upload / why" explainer, so B40 students aren't discouraged by an onerous-looking list.
- **Required** (amber pill): Identity card (IC) + SPM/STPM results slip — *"We need these two to process your application."*
- **Optional** (muted pill): a single **"Proof of household income"** card accepting **any one of** STR letter /
  salary slip / EPF statement (multi-file — several earners welcome); plus latest water bill, latest electricity bill
  (kept as a prosperity proxy), statement of intent, offer letter, photo. `reference_letter` dropped from the student
  UI (referee moved to the admin verify-&-accept stage; kept in model choices for back-compat).
- Backend: 4 new `ApplicantDocument` doc types (`salary_slip`, `water_bill`, `electricity_bill`, `offer_letter`) —
  additive choices-only migration `0014`. `application_completeness` gains **`documents_done`** = IC **and** results
  slip both present. `complete` is **deliberately unchanged** (still quiz + story + funding) — the documents/consent
  gate lands in S5's completeness finalise. Serializers derive their choice list from the model, so the new types
  validate automatically.
- Frontend: `ScholarshipDocuments` reworked into Required/Optional sections + a combined income-proof card (STR /
  salary slip / EPF selector, each file stored under its own type); `scholarship.ts` doc-type groups +
  `documentsComplete()` helper (+jest); i18n ×3 (parity 1227) — Tamil copy is a first draft pending the user's review.
- Build clean; backend 112 pytest; UI matches the Stitch-approved prototype.

## [2.4.2] — "How you'd use the support" — reframed funding (Step-4 redesign, S3) (2026-05-27)

Backend + frontend (migrate-first: `scholarship 0013`). Reframes the funding tab away from itemised RM amounts.
Since assistance is **capped at RM3,000 (a contribution)**, asking a total or "how you'd cover the balance" only
manufactured a discouraging gap — so both are gone. The tab now: states **"Our assistance is up to RM3,000 — the
actual amount may be lower…"**; asks **programme length**; offers a **tick-only** checklist of what the support would
help with (living, transport, accommodation, books, device, tuition *with "often covered" helper*, something-else);
and an **optional open box** ("how you're planning to fund your studies, or how you'd manage if this doesn't come
through"). No totals, no per-category amounts.
- Backend: `FundingNeed` gains `categories` (JSON), `funding_note` (text), `programme_months` (int) — additive
  migration `0013`, migrate-first (0 existing rows); serializer + details-PATCH + tests. **Funding-complete** now =
  at least one category ticked (was total > 0).
- Frontend: funding tab rewritten (tick categories + length + open box); `DetailsFormState`/payload mapping; i18n ×3
  (parity 1209). Legacy amount fields kept as dead columns (unused).
- Build clean; backend 106 / jest 93; UI screenshot-verified.

## [2.4.1] — "Your story" guided section (Step-4 redesign, S2) (2026-05-27)

Backend + frontend (migrate-first: `scholarship 0012`, applied to prod before deploy). Replaces the "story" tab's
4 generic textareas with a **guided two-card section** — *About your family* + *About you* — that together form the
basis of the student's statement of intent. Trimmed to high-signal, mostly-optional prompts (per the signal-vs-burden
review): family = first-in-family tick, parents'/guardians' occupation, "siblings also studying" (optional), and an
optional family-situation box; you = aspirations + plan (the keepers) + optional daily-life/responsibilities +
optional "what worries you / what support would help". A visible note invites answers in **BM / English / Tamil**,
and points to the Statement-of-Intent upload for "more to say". No profile data is re-asked (sibling count, income,
etc. stay on the canonical profile).
- Backend: 5 additive narrative fields on `ScholarshipApplication` (`first_in_family`, `parents_occupation`,
  `siblings_studying`, `family_context`, `daily_life`; migration `0012`); details-PATCH + read serializers + tests.
  **Story-complete** now = `aspirations` + `plans` filled (was aspirations + justification); everything else optional.
- Frontend: the guided form in the Story tab; `DetailsFormState` + payload mapping; i18n ×3 (parity 1190).
- Build clean; backend 101 / jest 88; UI screenshot-verified (mobile + desktop). No total/photo/funding change here
  (those are S3/S4).

## [2.4.0] — Application follow-up → 5-tab shell (Step-4 redesign, S1) (2026-05-27)

Frontend-only (web deploy). First sprint of the `/scholarship/application` (post-shortlist "complete your profile")
redesign — see `docs/scholarship/application-redesign-plan.md`. The shortlisted view changes from one long scroll to
a **5-tab sectioned shell** mirroring `/apply`: desktop left step-rail + active section card, mobile bottom tab bar,
a progress bar + "Step N of 5" indicator. Tabs: **Quiz · Your story · Funding · Documents · Consent** — the Referee
step is **dropped from the student flow** (it moves to the coordinator's verify-&-accept stage in a later sprint).
Section *content* is ported in **unchanged** this sprint (the single details form is split across the Story + Funding
tabs but still PATCHes the same payload via one shared form state — a Save button on each tab persists everything);
Your story / Funding / Documents get their actual rework in S2–S4. New pure helpers `NEXT_STEP_ORDER` +
`defaultNextTab` (opens on the first incomplete step) with 9 unit tests. Build clean; jest 86; i18n parity 1177.
No backend/model change.

## [2.3.1] — Shortlist email links straight to "complete your profile" (2026-05-27)

Backend-only (api deploy). Live testing showed the shortlist **invitation email** said *"we'll be in touch shortly
with what to do next"* with **no link** — leaving the student stuck at Step 4 with nowhere to go. The email now
includes a direct **call-to-action link** to `{FRONTEND_URL}/scholarship/application` (the complete-your-profile
page), with the documents note (IC, results slip, proof of household income) matching the "How it works" Step 4, in
all three locales. The link is built in `emails._send` from `settings.FRONTEND_URL` (so the ack/decline bodies are
unaffected). Separately, `FRONTEND_URL` now defaults to the **branded `https://halatuju.xyz`** (was the raw Cloud Run
URL) and the live Cloud Run env var was updated to match — so both the shortlist link **and** the existing
verify-email link are now branded. +1 test (shortlist body contains the link). The +48h decline email is unchanged
(no link by design — it's a warm "not this round").

## [2.3.0] — Truthfulness declaration + typed-name signature before submit (2026-05-27)

Backend + frontend (migrate-first: scholarship `0011`, applied to prod before deploy). Adds a final
attestation step to the B40 apply form, on the "Support" tab just above Submit:
- **Declaration** (plain language, no legalese): "I declare that everything I've shared in this application
  is true and complete… I understand the team may ask me for documents to confirm it, and that giving false or
  misleading information can lead to my application being rejected — or any assistance being withdrawn later."
- **Typed-name signature** (required): the student types their full name (as in their IC) to sign. Its value is
  the deliberate act of assent + an audit record — **not** identity verification, since we only hold the name they
  typed in About Me to compare against, never the official JPN record. So the match is a **soft nudge**: if the
  signature doesn't loosely match (case/space-insensitive) the About Me name, we show a gentle warning but never
  block submission.
- **Audit trail:** new `declaration_name` (the signed name) + `declared_at` (server timestamp, stamped at submit)
  on `ScholarshipApplication`. Accepted by the create serializer, exposed by the read serializer. `declared_at` is
  only set when a signature is present (no signature → null).

Backend: model + migration `0011` (additive) + `_APP_FIELDS` + `create_application` stamp; 97 scholarship tests
(2 new). Frontend: `declarationName` in the form state/payload, required in `applyFormError`, soft
`declarationNameMismatch` helper; declaration block on the Support tab (3 locales); 79 lib tests (4 new); i18n
parity 1171. Build clean; declaration block + soft nudge verified locally (Playwright).

## [2.2.7] — Apply-flow polish: NRIC prefill, clearer "no results" prompt, real ending page (2026-05-27)

Frontend-only (one `halatuju-web` deploy). Three issues from live new-user testing:
- **NRIC now pre-fills the apply form.** The NRIC the student gives at the sign-up gate was saved to the
  profile but showed up blank on the apply form. Root cause: the form's profile-prefill locked itself on the
  *first* profile snapshot, which for a brand-new user has no NRIC yet (it's claimed at the gate moments later).
  The prefill now waits until the profile actually carries its NRIC before seeding, so the field arrives
  pre-filled (and still editable, since it's unverified). Verified in prod DB that the NRIC was being persisted —
  this was purely a frontend timing bug.
- **Clearer prompt when results are missing.** A student who reaches "Your Plans" without exam results saw a
  vague "add them in the previous step". Rewritten to name the step explicitly and urge action: "We can't show
  your pathways yet — we don't have your exam results. Please go to the 'Your SPM / STPM Results' step and add
  your results first…" (`plan.noPathways`, ×3 locales, step named per-language).
- **The post-submission page is no longer a dead end.** `/scholarship/application` rendered a bare card with no
  site chrome. It now uses the standard `AppHeader` + `AppFooter` (full nav + footer), states **which email** we'll
  write to ("We'll send any updates… to {email}. Please check that inbox, including spam."), and offers "Browse
  courses while you wait" + "Back to home" CTAs. Email falls back to the Google sign-in address when no separate
  contact email is set. Applies to the received / accepted / none states alike.

Verified locally (Playwright) that the application page renders with header, card, email note, CTAs, and footer.
Build clean; i18n parity 1164; 75 lib tests pass.

## [2.2.6] — Stop Chrome address-autofill hijacking the course / institution comboboxes (2026-05-27)

Frontend-only (one `halatuju-web` deploy). Reported on the live STPM top-3 picker: Chrome's saved-address
autofill (postcodes / localities) popped up **over** the course list, covering it. Both `ProgrammePicker`
and `InstitutionPicker` already set `autoComplete="off"`, but Chrome **ignores `off`** for fields it
heuristically classifies as address/contact. Switched both to `autoComplete="new-password"` — Chrome won't
autofill saved addresses into a new-password field, and since the inputs are `type="text"` no password UI
fires. Added `data-1p-ignore` + `data-lpignore="true"` so the new-password hint doesn't attract 1Password /
LastPass icons. Affects every course picker (decided + top-3 branches) and the matric-college / Form-6-school
pickers. Build clean.

## [2.2.5] — STPM "still deciding" top-3 degree picker + PISMP in SPM leaning pills (2026-05-27)

Frontend-only (one `halatuju-web` deploy, no api change):
- **STPM students who are "still deciding" now rank their top 3 degrees.** Previously the uncertain branch offered
  STPM students only the SPM-style pathway pills, which don't fit them — an STPM student weighs *specific degrees*,
  not pathways. They now get **3 ranked boxes (1st / 2nd / 3rd)**, each a type-to-search picker over the degrees their
  STPM results qualify them for (same `ProgrammePicker` as the decided branch). Selections dedupe across boxes and
  store as `top_choices` (rank + course + institution); empty slots are dropped and ranks re-sequenced on submit.
  Every box generates decision/profile signal — consistent with "no control without signal".
- **SPM leaning pills now show all 9 pathways, including PISMP.** The pills previously listed only *eligible*
  pathways, which silently dropped PISMP (Teaching / IPG). Leanings are exploratory, not a commitment, so the full
  menu (`PATHWAY_ORDER`) is shown — a student can lean towards a pathway even before qualifying.

Verified locally (Playwright): all 9 pills incl. PISMP render; the 3 STPM boxes select, dedupe, and persist
`top_choices` with institution + null gaps. Build clean; i18n parity 1161; 75 lib tests pass (+1 for null-slot filtering).

## [2.2.4] — STPM eligibility fix (0 for all STPM students) + scholarship list + decided-branch note (2026-05-27)

- **STPM eligibility bug (critical):** the apply form's degree picker showed "no eligible courses" for **every** STPM
  student. Root cause: the STPM eligibility view (`/stpm/eligibility/check/`) passed **raw** profile demographics
  (`male`/`malaysian`) to the engine, which compares against the Malay forms (`Lelaki`/`Warganegara`). All 1112 STPM
  courses require Malaysian citizenship, so `malaysian` ≠ `Warganegara` excluded every course → 0. (The SPM path
  normalises in its serializer; the STPM view didn't.) Fix: shared `normalize_gender`/`normalize_nationality` helpers
  (extracted from the SPM serializer, now used by both) applied in the STPM view. Verified live: a real STPM student
  goes from 0 → **601** eligible degrees. +1 regression test; 47 STPM/serializer/golden-master tests pass. (api)
- **Other-scholarships list updated** to JPA, Khazanah, PETRONAS, Bank Negara Malaysia, Program Dermasiswa B40,
  Maybank, Maxis, Sime Darby, Others (replaces MARA / Yayasan / Bank-corporate). (web, ×3 locales)
- **"Anything you'd like to add?"** free-text now shows for the **Decided** branch too (not just "still deciding"),
  so a decided student who can't find their exact course in the filtered list can tell us. (web)

Build clean; i18n parity 1159; 74 FE + 47 STPM backend tests pass.

## [2.2.3] — `coq` round-trip fix + STPM names canonicalised + "Public University" copy (2026-05-27)

Three frontend fixes, one `halatuju-web` deploy (no api change):
- **`coq` now round-trips to the edit form.** 2.2.2 persisted `coq` to the DB, but the auth context's
  profile-cache effect *overwrote* `KEY_PROFILE` on every refresh — dropping the camelCase `coqScore` and never
  mapping the backend's snake_case `coq_score` back. So the grades/edit form re-read `0`. The cache now **merges**
  (instead of overwriting) and maps `coq_score → coqScore`, so a stored co-curricular score shows on re-edit.
- **STPM centre names canonicalised to the MOE secondary list (by code).** All 584 STPM centres matched a secondary
  school by code (clean subset, zero gaps), but every name had drifted from the canonical MOE record (Title-Case copy
  with casing/bracket/apostrophe inconsistencies + truncations, e.g. `Datin Onn → DATIN ONN JAFFAR`, `Munsyi → MUNSHI`).
  Names now come from the canonical secondary list, so the STPM stream→school picker shows **identical** names to the
  About Me School field (ALL-CAPS, as About Me already displays).
- **"Public university degree" → "Public university"** in the Plans pathway dropdown (en/ms/ta).

Build clean; i18n parity 1156; 74 lib tests pass. Forward-only for `coq` (existing profiles fill in on next sync).

## [2.2.2] — Persist `coq_score` to the profile (co-curricular score now stored, not just local) (2026-05-27)

Follow-up to 2.2.1, fixing the *root* gap rather than just tolerating it. `coq_score` was collected at onboarding
but only kept in `localStorage` and **never synced**, so it was `null` for 100% of DB profiles (2.2.1 just defaulted
the null). The profile-sync payload now includes `coq_score` (both the onboarding sync and the auth-gate sync read it
from the saved profile); the backend already persisted it via `ProfileUpdateSerializer`. +1 sync regression test
(`test_sync_persists_coq_score`). A localStorage↔sync parity audit confirmed `coq` was the *only* un-synced field.
**Forward-only** — existing profiles persist `coq` on their next onboarding/sync (no backfill; nothing server-side
reads `coq`, so no decision impact). Merit stays a computed-on-the-fly derivative (correctly **not** stored).
Frontend (`halatuju-web`) + a backend test.

## [2.2.1] — Hotfix: eligibility 400 on null `coq_score` blanked the Plans pathway dropdown (2026-05-27)

Hotfix for the 2.2.0 Plans redesign. The apply page posts the **full** student profile to `/eligibility/check/`;
`coq_score` is `null` for **100% of prod profiles (601/601)**, and `EligibilityRequestSerializer` rejected null
`coq_score` with HTTP 400 — so the call failed and the Plans-step pathway dropdown showed the empty *"once your
results are in…"* state for **every SPM applicant** (476 with grades), even though their results were fine.
Fix: `EligibilityRequestSerializer.to_internal_value` now **strips nulls** so optional fields fall back to their
declared defaults (`coq_score`→5.0, `colorblind`→False, …) instead of erroring — one place, covers the whole class.
Backend-only, no migration. +1 regression test (full profile with null optionals → 200 + pathways); 100 courses +
serializer tests pass. **Root cause was missed in 2.2.0 because previews used mocked `pathway_stats` and the
post-deploy check sent a minimal payload, never the real full-profile call.** Deployed to `halatuju-api`.

## [2.2.0] — B40 apply-form "Your Plans" redesign — DEPLOYED TO PROD (2026-05-27)

Context-aware, progressive-disclosure rebuild of the apply-form Plans step (P1–P5), built on
`feature/plans-redesign` and shipped in one coordinated deploy. **Merged `acdb2a4` → `main`; both Cloud Run
services deployed (`halatuju-api-00156`, `halatuju-web-00205`, builds SUCCESS); live + verified on halatuju.xyz**
(served bundle carries the new strings; `/eligibility/check/` + `/fields/` 200). Migration `0010` (7 optional
fields) was applied **migrate-first** to prod and verified (7/7 columns on `scholarship_applications`, correct
`jsonb`/`text`/`varchar` types) before the push — additive, zero-downtime. 97 frontend + 1105 backend tests green.
The step now opens with one question (Decided / Still deciding) and reveals only eligible options; every control
generates a decision or profile signal. (The wider B40 programme remains **not promoted** — separate launch task:
wire Cloud Scheduler → `send_pending_decision_emails`.) Per-sprint detail below.

### P1 — storage foundation (backend, 2026-05-26)
- **7 new optional fields** on `ScholarshipApplication` (migration `0010_plans_redesign_fields`):
  `pathway_certainty`, `chosen_pathway`, `pre_u_track`, `pre_u_institution`, `chosen_programme` (json),
  `uncertainty_reasons` (json), `uncertainty_note`. All blank/default → backward-compatible.
- Wired through the intake (`ApplicationCreateSerializer`), read (`ApplicationReadSerializer`), and admin
  serializers, plus `services._APP_FIELDS` + `build_intake_snapshot` (persisted + frozen in the audit snapshot).
- **Engine unchanged**: shortlisting still gates on `intends_tertiary_2026` + `upu_status=='ipts'`; the new
  fields don't touch the decision or the `courses` eligibility engine (reused read-only by later sprints).
- Tests: +2 (sure + uncertain branch round-trip, snapshot, read serializer). Scholarship suite **95 passed**;
  migration applies cleanly on SQLite.

### P2 — Plans-step shell + eligible-pathway dropdown (frontend, 2026-05-26)
- The "Your Plans" step now opens with **one question — "Do you know which pathway you'll take?"** →
  *Yes, I've decided* / *I'm still deciding*. Nothing else shows until it's answered (progressive disclosure).
- **Decided (SPM leavers)** reveals a single-select **eligible-only pathway dropdown** — each option shows
  its eligible-programme count (e.g. *"Polytechnic — 85 eligible"*), fed live by the eligibility engine
  (`/eligibility/check/` → `pathway_stats` → `eligiblePathways()` in fixed order). New `<PathwaySelect>` component.
  STPM students see a degree-branch stub; *Still deciding* shows an exploration stub (both built in P5).
- **State + validation**: `ApplyFormState` gains `pathwayCertainty` + `chosenPathway`; payload adds
  `pathway_certainty` + `chosen_pathway` (P1 fields). `applyFormError` is now exam-type-aware — the pathway
  question is required (but *"still deciding"* is always a valid answer), and a decided SPM leaver must pick a
  pathway; STPM students are exempted (degree picker lands in P5). `upu_status` is **derived** from the chosen
  public pathway (no separate UPU question); `intends_tertiary_2026` stays true by default.
- **Replaced** the multi-select pathway chips, the UPU radio, and the "I intend to continue" checkbox + their
  i18n keys (×3 locales). Field-of-study + top-3 course pickers stay gated under "decided" pending P3 (which
  collapses them into one pathway-filtered course dropdown); "other scholarships" kept as an independent signal.
- Tests: +6 (eligible-pathways helper from P2a + certainty/chosen-pathway validation + payload mapping).
  Frontend suite **76 passed**; `next build` clean; i18n parity 1126 keys. Branch only — not deployed.

### P3 — Decided-course picker for programme pathways (frontend, 2026-05-26)
- When a student picks a **programme pathway** (Foundation / Public university / Polytechnic / Community
  college / Teaching-PISMP / ILJTM / ILKBS), the "decided" branch now reveals a **single-select, type-to-search
  course combobox** showing **only the courses that pathway makes them eligible for** (A–Z, with institution
  counts). New `<ProgrammePicker>` component (School-field UX, but constrained to the eligible list — no free text).
- Courses come from the **same `/eligibility/check/` call** P2 already makes — the page now also keeps
  `eligible_courses` and filters by `pathway_type` (`programmesForPathway()` helper). No new endpoint/fetch.
- **Matriculation & STPM** pathways show a short institution stub (their stream→school / track→college flow is P4).
- Picking a course stores `chosen_programme` (the P1 JSON field) and **derives `field_of_study`** from the
  course — no separate field question. `applyFormError` now requires the course on a decided programme pathway
  (matric/STPM exempt — P4; STPM students exempt — P5).
- **Removed** (delete-as-you-replace): the field-of-study `<select>` + the top-3 saved-courses picker that P2
  parked under "decided", their data fetches (`getSavedCourses` / `fetchFieldTaxonomy`), and 8 now-dead i18n keys
  (×3 locales). The one course dropdown replaces both.
- Tests: +8 (`programmesForPathway` filter/sort, `isProgrammePathway`, course requirement + matric/STPM exemptions,
  `chosen_programme` mapping). Frontend suite **84 passed**; `next build` clean (`/scholarship/apply` 36.1 kB);
  i18n parity 1125 keys. Branch only — not deployed.

### P4 — Institution pathways: Matriculation track→college + STPM stream→school (frontend, 2026-05-26)
- The two non-programme pathways now have their decided sub-flows (replacing the P3 institution stub):
  - **Matriculation** → **track** chips (only the tracks the student qualifies for, from `/calculate/pathways/`
    via `eligibleMatricTracks()`) → **college** picker (`MATRIC_COLLEGES` filtered to that track by `collegesForTrack()`).
  - **STPM / Form 6** → **stream** chips (Sains / Sains Sosial / *Not sure*) → **school** picker (the 584 Form 6
    centres in `stpm-schools.json`, filtered to that stream by `stpmSchoolsForStream()`).
- New generic `<InstitutionPicker>` (type-to-search name combobox, capped list + "keep typing" hint) — reused for
  both the college list and the 584-school list. Matric track eligibility comes from an extra `/calculate/pathways/`
  call fired alongside the existing eligibility call (SPM leavers only).
- Storage: track/stream → `pre_u_track`, college/school → `pre_u_institution` (P1 fields). `applyFormError` requires
  both on a decided matric/STPM pathway (STPM students still exempt — their degree picker is P5). `field_of_study`
  is intentionally left empty for pre-U pathways (no degree chosen yet; the track/stream is the signal).
- Tests: +9 (`isInstitutionPathway`, `eligibleMatricTracks`, `collegesForTrack`, `stpmSchoolsForStream`, the
  track/stream + institution validation, payload mapping). Frontend suite **93 passed**; `next build` clean
  (`/scholarship/apply` 37.2 kB); i18n parity 1144 keys. Branch only — not deployed.

### P5 — STPM-student degree picker + Uncertain branch (frontend, 2026-05-26)
- **Post-STPM students** (`exam_type === 'stpm'`) now get a real **degree picker** instead of the stub — their
  decided branch skips the SPM pathway step and reuses `<ProgrammePicker>` over the degrees from
  `/stpm/eligibility/check/` (mapped + sorted A–Z by `stpmDegreesToCourses()`, university shown as the institution).
  Stores `chosen_programme` + derives field. New validation: a decided STPM student must pick a degree.
- **"Still deciding" branch** is now built out (was a stub): optional **leaning chips** (eligible pathways →
  `pathways_considered`, SPM leavers only), **"Where are you right now?" reason chips** (→ `uncertainty_reasons`:
  exploring / waiting for results / want advice / family / finance), and a free-text line (→ `uncertainty_note`).
  All optional — "uncertain" never blocks the application.
- **Mentoring stays coordinator-set** (per the model's design): the reasons are captured + surfaced on the admin
  detail, and the coordinator flags `mentoring_candidate` from them (not auto-set at intake).
- Tests: +6 (`stpmDegreesToCourses`, `UNCERTAINTY_REASONS`, STPM degree requirement, uncertain-never-blocks,
  reasons/note payload). Frontend suite **97 passed**; `next build` clean (`/scholarship/apply` 37.5 kB); i18n
  parity 1156 keys. **Branch complete — ready for the gated ship (migrate-first → merge → deploy).**

## [2.1.5] — Apply-form: My Family ordering + required household size (2026-05-25)

### Changed
- **Field order in My Family** — "Number of people in your household" now comes *before* "Combined monthly household
  income", so the student counts the household first and then totals that group's income (the old order asked them to
  "add up the income of everyone you counted" before they'd counted anyone).
- **Tips work in concert** — the household tip now ends "Next, you'll total this group's monthly income"; the income
  tip now reads "everyone you counted **above**". (en/ms/ta)

### Added
- **Household size is now required** (`min 1`) — it's needed for the per-capita income calculation. New `householdSize`
  validation + error message (en/ms/ta), surfaced on the My Family step. (+1 test)

## [2.1.4] — Apply-form: one tooltip, phone mask, per-step validation (2026-05-25)

### Fixed
- **Duplicate tooltip** — the `i` bubble dropped its native `title` attribute, which had been showing a second, drab
  browser tooltip on hover. Hover (desktop) and click/tap (mobile) now open the same custom popover.

### Added
- **Phone auto-mask** — phone and parent-phone fields format to `0XX-XXX XXXX` as digits are typed (`formatPhone`),
  matching the NRIC mask; pre-filled profile values are masked on load too.
- **Validation on Continue** — each step is validated when the student clicks Continue (not only at final submit):
  advancing is blocked while the current/earlier step has an error, which is surfaced there. Phone is now
  format-validated (9–11 digits, leading 0); parent phone is optional but validated when present (`parentPhone` error).

### Tests
- +8 unit tests (`formatPhone`, `isValidPhone`, phone/parent-phone validation). i18n parity **1121 → 1122** keys.

### Follow-ups (same day)
- **Landline-aware phone mask** — `formatPhone` now detects the Malaysian area-code length by prefix (mobile 01X and
  Sabah/Sarawak 08X = 3 digits; 03/04/05/06/07/09 = 2) and groups accordingly: `03-1234 5678`, `04-123 4567`,
  `088-123 456`, `012-345 6789`. (+1 test)
- **Consent control is now a toggle** — the consent on the Support step matches the STR/JKM toggle switches in My
  Family (label left, switch right) instead of a lone checkbox. `Toggle` extracted to `components/Toggle.tsx`.

## [2.1.3] — Apply-form: friendlier help bubble (2026-05-25)

### Changed
- The field help `i` bubble is restyled on-brand and extracted to `components/InfoTip.tsx`: a primary-tinted `i` with a
  ring, and a white rounded popover card with a soft primary border, shadow, caret and a lightbulb icon — replacing the
  flat grey `i` + hard dark-grey tooltip. Adds an optional `defaultOpen` prop. Applies to every apply-form field tooltip.

## [2.1.2] — Apply-form: home link, IC mask, searchable school field (2026-05-25)

Three usability fixes on `/scholarship/apply` (raised from the live form). All `halatuju-web`; deployed via push
to `main` (`9aa5d9e`).

### Added
- **Searchable School field** — the free-text School input is now a search-as-you-type field over all **2,480
  Malaysian secondary schools** (`PERINGKAT = Menengah`: SMK, SBP, SMKA, KV, KT6, SM SABK, etc.), each shown with its
  state, sourced from the MOE directory `SenaraiSekolahWeb_April2026.xlsx` (kept in `/docs` for provenance). Includes a
  **"can't find your school? just type it"** free-text fallback so a missing/misspelled school never blocks an
  applicant. New `src/data/secondary-schools.{json,ts}` (+ `searchSchools` helper) and `components/SchoolSelect.tsx`.
  The field still stores the school **name** (no backend/schema change).
- **Home link on desktop** — the apply form's desktop step-rail now has a Home link back to `/scholarship` (the mobile
  bottom bar already had one; desktop had no way back).

### Changed
- **IC number auto-masks** to `XXXXXX-XX-XXXX` as digits are typed (`formatNric`). Previously a student could type 12
  bare digits that silently failed the `NRIC_RE` check on submit; the mask produces exactly the format the validator
  and the claim endpoint require.

### Follow-ups (same day)
- School field tip now reads "where you sat for SPM **or STPM**" (was SPM only); the search placeholder shows a
  sample name — "Start typing, e.g. SMK Vivekananda" (a real entry) — so the SMK abbreviation/format is clear. (en/ms/ta)

### Tests
- +6 unit tests (`formatNric`, `searchSchools`, school-data integrity). i18n parity **1118 → 1121** keys
  (`schoolSearchPlaceholder` / `schoolNotListed` / `schoolNoMatch`, en/ms/ta). Production build clean
  (`/scholarship/apply` 8 kB → 37.6 kB from the route-split school list).

## [2.1.1] — Post-deploy: /scholarship copy + layout fixes (2026-05-25)

Small production follow-ups after the B40 redesign went live. All `halatuju-web` only; deployed to halatuju.xyz via
push to `main` (3 commits: `6706837`, `9d7224d`, plus the earlier OG/hero fixes).

### Changed
- **"Can I apply?" section restructured** — a single shared heading now spans two columns: the requirements
  checklist (left) and the "Please note" callout kept as-is (right). Heading reworded to first-person **"Can I apply?"**
  to match the copy doc (en/ms/ta).
- **Landing copy aligned with `docs/halatuju_scholarship_landing_copy.md`** across **en/ms/ta** — the page had still
  been running the older pre-doc wording. Reworked hero sub, lead paragraphs (dropped the "our community / self-help"
  framing), value cards; **Please note 5 → 7 bullets** (added Limited places, Trust w/ light verification, Under 18);
  **Can I apply 5 → 6 requirements** (added 20-min interview + quarterly-progress lines, DOSM citation, "Solid academic
  record"); How-it-works timing ("same day", "within 48 hours", MyNadi named, "up to two months"); FAQ replaced with
  the approved 9-question set.

### Added
- **"Want to support a student?"** donor section — **Get in touch** → `mailto:info@halatuju.xyz?subject=Sponsor enquiry`;
  "Funds are administered by MyNadi Foundation" with a link to yayasanmynadi.org. **Section 44(6) tax line omitted**
  until MyNadi's status is confirmed.
- **"About this programme"** section — partners credited; the partner whose registered name contains "Indian" is shown
  as the **acronym "CUMIG" only**, to keep the word off the public page (MyNadi 44(6) non-discrimination).

### Verified
- i18n parity 1118 keys across en/ms/ta (0 warnings); production build clean.

## [2.1.0] — B40 Redesign · Sprint 12b: DEPLOYED to production (2026-05-25)

The B40 redesign (S7–S12a) is **live in production**. `feature/b40-redesign` merged to `main` (release merge
`55c2c36`); both Cloud Run services rebuilt + deployed; health checks 200.

### Deployment
- **Migrations applied to prod first** (zero-downtime, additive): courses `0048` + scholarship `0007`, `0008`, `0009`.
  Confirmed via `showmigrations` + an information_schema column check. **Note:** the Cloud Run deploy triggers do
  **not** run migrations (build → push → deploy only), so migrations were applied manually *before* pushing `main`,
  keeping the existing live site healthy throughout.
- **Cohort `b40-2026`** verified live and **thresholds corrected to the settled S8 values**: a pre-existing row from
  Phase 1 still had the advertised cut-offs (`min_spm_a_count=5`, `min_stpm_pngk=3.0`); set to the engine's lenient
  `4` / `2.9` (B+ count 5, per-capita 1584, 2h/48h delays were already correct). Added an idempotent
  `seed_b40_2026_cohort` management command (+ 3 tests) for reproducible cohort creation.
- Post-deploy security advisors: 0 errors (scholarship tables' "RLS enabled, no policy" are the intended
  deny-by-default design; all WARNs pre-existing).

### Deferred (must do before promoting)
- **Cloud Scheduler → `send_pending_decision_emails`** — not wired (no applicants while the site is unpromoted).
  Required before the programme is promoted, or shortlist/decline reveal emails won't fire.
- **Vision OCR** → post-launch S13 (new Google Vision key + cost sign-off).

### Tests
- Backend **1100 → 1103** (cohort seed command). Migrations verified on prod. No frontend change.

## [Unreleased] — B40 Redesign · Sprint 12a: apply-form desktop responsiveness (2026-05-24)

The desktop layout for the apply form (the item deferred from S9). Frontend only; on `feature/b40-redesign`, not deployed.

### Changed
- `/scholarship/apply` is now responsive on desktop: on `lg` it becomes a **two-column layout** — a left vertical
  **step-nav rail** (the five sections, active highlighted, completed ticked) beside the active section card +
  Back/Continue — using the horizontal space the mobile single column left empty. The mobile **bottom tab bar is
  now `lg:hidden`** (the rail replaces it on desktop), and the container widens (`max-w-2xl` → `lg:max-w-4xl`).
- Mobile is unchanged (single column, progress, section card, bottom tab bar). The change is contained to the
  page's layout shell — section content and the mobile flow are untouched.

### Notes
- The `/scholarship/application` cards (received/accepted) already read fine centred at `max-w-2xl` — left as-is.
  `ScholarshipNextSteps` (post-shortlist follow-up) wasn't touched; can get a desktop pass later if needed.

### Tests
- `next build` clean. Frontend jest unchanged (49 — layout only). Backend unchanged (1100). No i18n change, no migration.

## [Unreleased] — B40 Redesign · Sprint 11b: applicant application states + login banner (2026-05-24)

The applicant-facing half of S11. Frontend only; on `feature/b40-redesign`, not deployed.

### Added
- `/scholarship/application` gains the **accepted** state — a distinct "confirmed" card (congratulations + "our team
  will be in touch about your award"), separate from the neutral received card. Full status map now: submitted →
  received · shortlisted → follow-up · **accepted → confirmed** · rejected/withdrawn → neutral.
- **`ScholarshipBanner`** — a self-contained dashboard banner that fetches the caller's application and renders only
  when it's **shortlisted** ("complete your application") or **accepted** ("confirmed"), linking to
  `/scholarship/application`; renders nothing otherwise (margin lives on the banner so there's no empty gap). EN/MS/TA i18n.

### Tests
- Frontend jest unchanged (49 — display + one fetch, no new pure logic). Backend unchanged (1100). `next build`
  clean; i18n 1107-key parity.

## [Unreleased] — B40 Redesign · Sprint 11a: admin verify-&-accept + NRIC lock + mentoring (2026-05-24)

The human verification gate for MyNadi admins. Backend + admin frontend; on `feature/b40-redesign`, not deployed.
(Applicant application-page states + login banner split to S11b.)

### Added
- **`AdminVerifyAcceptView`** (`POST /admin/scholarship/applications/<id>/verify-accept/`): admin confirms a
  checklist (NRIC / name / results / document) against the uploaded MyKad → sets `profile.nric_verified` (**locks**
  the NRIC), stamps `verified_at` / `verified_by` / `verify_checklist`, and advances the application
  **shortlisted → accepted**. Only a shortlisted application can be accepted.
- New **`accepted`** application status (passed the auto-screen = shortlisted; human-verified & confirmed = accepted).
- Mentoring-candidate toggle via **PATCH** on the admin detail endpoint.
- Admin detail page (`/admin/scholarship/[id]`): a **Verify-&-accept checklist card** (Accept enabled only when all
  four are ticked; shows the locked/accepted + verified-by state) + a mentoring-candidate toggle. EN/MS/TA i18n.
- `verified_at` / `verified_by` / `verify_checklist` audit fields; serializer exposes `nric` (full, for comparison),
  `nric_verified`, the audit fields, `mentoring_candidate`, and the S10 plans/support intake. Migration `0009`.

### Fixed
- **TD-054 resolved**: NRIC uniqueness is now enforced at the single verify-&-accept point — if another profile
  already has that NRIC *verified*, the endpoint returns `409 nric_conflict` for the admin to resolve (the soft-NRIC
  "clash surfaces at verification" design), instead of the old claim transfer-path PK collision.

### Tests
- Backend **1095 → 1100** (verify-accept happy path, TD-054 conflict, only-shortlisted guard, mentoring toggle,
  non-admin 403). Migration `0009` + golden masters intact. Frontend jest unchanged (49).

## [Unreleased] — B40 Redesign · Sprint 10: apply form ② — My Plans + Support + "received" (2026-05-24)

The second half of the apply form. Frontend only (every field was already accepted by `ApplicationCreateSerializer`
since S7); on `feature/b40-redesign`, not deployed.

### Added
- **My Plans**: "intend to continue tertiary study" gate checkbox; **pathways considering** multi-select chips;
  **UPU / destination** radio (with an inline amber note when "private (IPTS)" is picked — IPTS-only is out of
  scope and the S8 engine declines it); **field of study** dropdown (from the field taxonomy); **top-3 course
  choices** picked from the student's **saved courses** (ranked by tap order, max 3, friendly empty-state);
  **other scholarships** multi-select chips + free text → funding-overlap signal.
- **My Support**: help-with-university + help-with-scholarship radios (optional, Yes/No/Not sure), "anything else"
  free text, required consent.
- `scholarship.ts`: plans/support form state + payload mapping (`top_choices` ranked by order) + constants
  (`UPU_OPTIONS`, `HELP_OPTIONS`, `OTHER_SCHOLARSHIP_OPTIONS`, `TopChoice`); apply page fetches saved courses
  (exam-type aware) + field taxonomy on mount. EN/MS/TA i18n.

### Changed
- The apply form's single `intended_pathway` select is replaced by the `pathways_considered` multi-select; the
  `notes` free-text is replaced by `anything_else`. `intends_tertiary_2026` kept (engine hard gate) as a checkbox.

### Notes
- The post-submit **"Application received"** screen already works (S8's silent-score keeps status `submitted`, so the
  application page shows the neutral "received — we'll be in touch" card; the follow-up only appears once shortlisted).
  No auto-advance.

### Tests
- Frontend jest **49** (top_choices builder + plans/support payload; replaces the dropped notes test). Backend unchanged (1095).

## [Unreleased] — B40 Redesign · Sprint 9b: My Results edit → onboarding round-trip (2026-05-24)

Wires the apply form's My Results "edit/add results" into the full onboarding flow and brings the student back
without losing in-progress edits. Frontend only; on `feature/b40-redesign`, not deployed.

### Changed
- **My Results "edit / add results"** now routes through the **full onboarding** (`/onboarding/exam-type` → grades
  → … → "a few more details") instead of `/profile` or `/quiz`, so the profile ends up complete for course
  recommendations too.
- The **final onboarding step** is context-aware: entered from the apply form, its button reads **"Save & return
  to application"** and routes back to `/scholarship/apply` (otherwise unchanged → dashboard).

### Added
- **Stash & restore** of in-progress About-Me/My-Family edits across the onboarding detour (sessionStorage): the
  form only commits on submit, so edits are stashed before leaving and restored on return (landing on the Results
  tab). Helpers `stashApplyForm` / `popApplyStash` / `hasApplyReturn` / `clearApplyReturn` (storage-injectable,
  SSR-safe); orphan return-marker cleared on a normal apply visit.
- i18n `onboarding.saveReturnToApplication`; Results CTA copy updated (edit/add → onboarding).

### Tests
- Frontend jest **44 → 49** (stash/restore round-trip, marker set/clear, SSR no-op). Backend unchanged (1095).

## [Unreleased] — B40 Redesign · Sprint 9: apply form ① — About Me + My Family (2026-05-24)

Apply-form rebuild, first half. Inline-editable **About Me** + **My Family**, commit-on-submit. Frontend +
small backend write-back; on `feature/b40-redesign`, not deployed. Mobile-first (desktop layout is S12).

### Changed
- **About Me** (was read-only "About You") is now **inline-editable**, pre-filled from the profile: full name,
  school, **NRIC** (editable until verified, read-only + "Verified" badge once locked), referring organisation,
  home state, phone. **Contact email is locked** (already verified). The old "Edit → /profile" bounce is gone.
- **Commit-on-submit** — edits live in form state; on a successful submit the About Me + My Family fields sync to
  the canonical profile (`sync_profile_fields`), and the **NRIC commits via the validated claim path** (never the
  application payload). A failed submit persists nothing.
- Section headings are first-person (**About Me**, **My Family**); tab labels stay short (About / Family / …).
- Validation now enforces the required About-Me fields (name, school, NRIC format, referring org, home state,
  phone) + household income, and **jumps the user to the offending tab**; the error banner moved out of the
  Support tab so it shows on whichever tab the error is on.

### Added
- **My Family**: parent/guardian **name + phone** (stored in `profile.guardians`) and **preferred call language**
  (en/ms/ta/mixed → `profile.preferred_call_language`); `i` tooltips on income, household, STR, JKM.
- Required `*` + `i` info-bubble tooltips across About Me + My Family (`InfoTip` + `FieldLabel` components).
- Referring-organisation **fixed dropdown** (9 legacy options) → stored as `referral_source`, resolved to the
  `referred_by_org` FK server-side when a matching active `PartnerOrganisation` exists.
- `scholarship.ts`: new form fields + `nricChanged`, `REFERRING_ORG_OPTIONS`, `CALL_LANGUAGE_OPTIONS`,
  `MALAYSIAN_STATES`; `ApplicationCreateSerializer` accepts the new write-only profile fields; profile GET returns
  `referral_source` + `guardians`. EN/MS/TA i18n (labels, tooltips, headings, validation).

### Tests
- Backend **1093 → 1095** (About-Me/Family write-back + referring-org FK resolution). Frontend jest **37 → 44**.

## [Unreleased] — B40 Redesign · Sprint 8: decision engine + silent-score + delayed reveal (2026-05-24)

The deterministic decision engine (final policy calls settled). Backend only; on `feature/b40-redesign`, not deployed.

### Changed
- **`shortlisting.py` rewritten** to the settled rule (no score/weights/hardship): hard gates (consent · intends
  public study · not IPTS-only) → academic floor (SPM ≥4 at A- AND ≥5 at B+ / STPM PNGK ≥2.9) → income (STR →
  pass, bucket A; else per-capita income < `per_capita_ceiling` RM1,584 → pass, bucket B). `evaluate()` returns
  `verdict` (shortlisted/rejected) + bucket + reason.
- **Submit no longer decides instantly** — it scores **silently** (`score_application`): stores verdict +
  `decision_due_at`, status stays `submitted`, only the acknowledgement email is sent.
- **Delayed reveal** via `send_pending_decision_emails` (now release-due-decisions): flips status + sends the
  email at `decision_due_at` — **+2h** shortlist (invitation), **+48h** decline (warm).
- **Decline email** rewritten warm (EN/MS/TA): "not successful this round, all the best, you're welcome at our
  higher-education seminars — we'll send invites."

### Added
- Cohort: `per_capita_ceiling` (1584), `min_spm_bplus_count` (5), `success_delay_hours` (2), `decline_delay_hours`
  (48); defaults `min_spm_a_count` 5→4, `min_stpm_pngk` 3.0→2.9.
- Application: `verdict`, `decision_due_at`, `decision_released_at`. Migration scholarship `0008`.

### Tests
- Backend **1093 pass** (golden masters intact). Rewrote engine tests (per-capita + academic-floor + IPTS + STR),
  scheduler tests (release-due / idempotent / dry-run), submit tests (silent score), cohort-defaults; added a
  per-verdict-delay scoring test.

## [Unreleased] — B40 Redesign · Sprint 7: backend foundation (soft-NRIC + intake fields) (2026-05-23)

Foundation for the decision-engine redesign + apply-form rebuild (6-sprint roadmap in
`docs/scholarship/b40-decision-redesign-plan.md`). Backend only; on `feature/b40-redesign`, not deployed.

### Added
- **`StudentProfile.nric_verified`** (Bool), **`coq_score`** (Float — co-curricular score now persisted,
  was transient), **`preferred_call_language`**. Profile GET returns all three.
- **`ScholarshipApplication`** new intake fields (all optional): `field_of_study`, `pathways_considered`,
  `top_choices`, `upu_status` (incl. an IPTS option), `other_scholarships` (+ free text), `help_university`,
  `help_scholarship`, `anything_else`, `mentoring_candidate`. Carried through the create serializer,
  `_APP_FIELDS`, the audit `intake_snapshot`, and the read serializer.
- Migrations: courses `0048`, scholarship `0007`.

### Changed
- **Soft-NRIC (supersedes "IC immutable"):** uniqueness now enforced **only when verified**
  (`unique_verified_nric` replaces `unique_nric_when_set`); NRIC is **read-only on PUT/sync** (claim path
  only); the claim endpoint **blocks a change once verified** (403 `nric_locked`). See `docs/decisions.md`.

### Tests
- Backend **1091 pass** (was 1086; +4 soft-NRIC, +1 intake round-trip), golden masters intact (SPM 5319,
  STPM 2026). Updated `test_profile_fields` (PUT no longer sets NRIC; uniqueness only when verified).

## [Unreleased] — B40 Assistance Programme · Phase 1.5c public landing + follow-up route (2026-05-22)

Added the public marketing landing and gave the post-submission follow-up its own page.

### Added
- **`/scholarship/` landing** (public, no sign-in) — Stitch-designed, community self-help framing:
  hero + AI imagery, overview + value cards, a "Please note (pilot)" callout, a "Can you apply?"
  checklist (Indian-descent pilot, B40 < RM5,860, 5 A's / PNGK 3.0, public post-secondary), an
  8-step "How it works" timeline, a 10-item FAQ accordion, and a closing CTA. Renders with
  `AppHeader`/`AppFooter` like other content pages.
- **`/scholarship/application`** — the post-submission home: shortlisted students complete their
  follow-up (`ScholarshipNextSteps`) here; everyone else sees a neutral "received" status; visitors
  with no application are sent to apply. The apply page now redirects returning applicants here and
  routes here after submit (no more inline status branch).
- **AI imagery** (Gemini, via Stitch) saved as real assets: `public/scholarship/hero.jpg`,
  `community.jpg`. Hero is `priority`; the CTA image lazy-loads.
- **i18n**: `scholarship.landing.*` + `scholarship.application.*` in EN/MS/TA (1002 keys, parity
  verified). Gate button copy and all landing copy use the approved British-English wording.

### Tests / verification
- Jest **37 pass**; `next build` green (`/scholarship`, `/scholarship/application`, `/scholarship/apply`
  all compile). Live render check on `next dev` confirmed the landing renders (hero image, value cards,
  pilot callout, requirements, timeline, FAQ, CTA, footer). Not deployed.

## [Unreleased] — B40 Assistance Programme · Phase 1.5b apply-form frontend rebuild (2026-05-22)

Rebuilt the student apply flow to the profile-canonical API and the Stitch-approved design
(landing soft sign-in gate + tabbed 5-section form).

### Added / Changed
- **Soft sign-in gate** — anonymous visitors read the eligibility criteria freely and apply via a
  one-tap "Continue with Google" (the same button registers new students), with a "we'll use your
  profile so you never retype" reassurance. Replaces the old plain sign-in prompt.
- **Tabbed 5-section apply form** (Form A) — About You · Your Family · Your SPM/STPM Results ·
  Your Plans · Support, with a step progress bar + sticky bottom tab bar.
  - Sections 1 & 3 are **read-only, pre-filled from the profile** with "From your HalaTuju profile"
    badges and Edit links; results show A-count / A+ / STPM CGPA, or a "finish your quiz" prompt when
    the profile has no academic data yet.
  - Section 2 (Family) **writes financial fields back to the profile** (income, household size, STR/JKM
    toggles) with a "this also updates your HalaTuju profile" caption.
  - Academic data is **never posted** — the backend reads it from the profile.
- **`scholarship.ts`** — `ApplyFormState` slimmed to the financial + application fields;
  `profileToApplyDefaults` pre-fills financial from the profile; new `profileAcademicSummary` helper;
  `buildApplicationPayload`/`applyFormError` drop the academic fields.
- **API types** — `StudentProfile` gains the financial fields; student `ScholarshipApplication` uses
  `exam_type` (was `qualification`) and exposes `intake_snapshot`. (Admin types/serializer unchanged.)
- **i18n** — new `scholarship.apply.*` keys (gate, tabs, sections, read-only field labels, write-back
  note, results summary, empty states) in EN/MS/TA; 925 keys, parity verified.

### Tests
- `scholarship.test.ts` updated to the new shape (20 pass); full Jest **37 pass**; `next build` green
  (`/scholarship/apply` compiles). Not deployed.

## [Unreleased] — B40 Assistance Programme · Phase 1.5a source-of-truth refactor (2026-05-22)

Made the HalaTuju profile the single source of truth for applicant data, plus de-Gmailed email.

### Changed
- **Profile is canonical.** Moved academic (read from existing `grades`/`exam_type`/`stpm_cgpa`) and
  financial data to `courses.StudentProfile`: added `household_income`, `household_size`,
  `receives_str`, `receives_jkm`, `guardians` (migration `courses 0047`).
- **`ScholarshipApplication` slimmed** (migration `scholarship 0006`) — removed the duplicated
  `qualification`/`spm_a_count`/`stpm_pngk`/`household_income`/`household_size`/`receives_str`/
  `receives_jkm`; added `intake_snapshot` (immutable record of what was declared at submit time).
- **Shortlisting reads the profile live** — `shortlisting.evaluate()` scores academic + income from
  `application.profile`; intent + consent stay per-application. `count_spm_a_grades` now lives in
  `shortlisting.py`.
- **Apply flow writes back** — `services.sync_profile_fields` syncs the form's financial fields to the
  profile (non-None only, never blanks an existing value); `build_intake_snapshot` freezes the audit copy.
- **Serializers** — create accepts the financial write-back fields (write-only); read + admin serializers
  derive academic/financial from the profile and expose `intake_snapshot`.
- **Email de-Gmailed** — `production.py` email is now fully env-driven (Brevo SMTP relay default);
  no personal address in code. Deploy sets `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` + verifies the sender domain.

### Tests
- Full backend suite **1086 pass**. Updated `test_shortlisting`/`test_api`/`test_models`/
  `test_admin_scholarship` for the profile-canonical shape; removed the obsolete
  "explicit a-count override" test; added write-back + snapshot coverage.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 6b (2026-05-22) — Phase 1 build complete

MyNadi admin console UI (frontend) — completes Sprint 6 and the Phase 1 build.

### Added
- **`/admin/scholarship`** — applications list with status + bucket filters.
- **`/admin/scholarship/[id]`** — full applicant detail (intake, funding, documents, referees,
  consent) + AI sponsor-profile panel: Generate → edit Markdown → Save → Publish, with status badge.
- Admin API client (`getScholarshipApplications`, `getScholarshipApplication`,
  `generateSponsorProfile`, `saveSponsorProfile`, `publishSponsorProfile`); "B40 Applications" nav link.
- i18n: `admin.scholarship.*` in EN/MS/TA (894 keys, parity verified).

### Tests
- Frontend suite **37 pass**; check-i18n PASS; `next build` — both admin pages compile.

### Phase 1 status
- **All 6 sprints complete.** Backend 1086 tests, frontend 37, golden masters intact, on
  `feature/b40-assistance` (not deployed). Remaining: the single Phase-1 deploy (carry-forwards) and
  Phase 0 legal/entity sign-off before public launch.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 6a (2026-05-22)

AI sponsor-profile drafting + MyNadi admin API (backend; the admin console UI is 6b).

### Added
- **`SponsorProfile` model** (OneToOne application; `draft_markdown`/`edited_markdown`, status
  draft→approved→published, `model_used`, timestamps; migration 0005, RLS).
- **`profile_engine.py`** — `generate_sponsor_profile()` drafts a sponsor-ready Markdown profile
  from intake + deeper-info + funding + grades + referee via the Gemini cascade (graceful error).
- **Admin API** (reuses `PartnerAdminMixin`, super-admin sees all): list applications (status/bucket
  filter), full detail (intake/funding/docs/referees/consents/profile), generate-profile, edit
  profile, publish — under `/api/v1/admin/scholarship/`.

### Tests
- 9 new (`test_admin_scholarship.py`, Gemini mocked). Full backend suite **1086 pass, 0 fail**;
  golden masters unchanged.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 5b (2026-05-22)

Document upload + referee + consent UI (frontend) — completes Sprint 5.

### Added
- **`ScholarshipDocuments`** — per-doc-type upload (sign → PUT straight to Supabase Storage →
  record), list with signed-URL view links + delete.
- **`ScholarshipReferee`** — add/list referees.
- **`ScholarshipConsent`** — DRAFT consent text + checkbox; guardian name/relationship fields when
  the applicant is a minor; "consent given" once recorded.
- Wired as steps 4–6 of the next-steps checklist.
- API client: sign-upload, direct PUT, record/list/delete docs, referee CRUD, consent get/record;
  `DOC_TYPES` + `formatFileSize` helpers.
- i18n: `scholarship.docs/referee/consent` + step 4–6 labels in EN/MS/TA (856 keys, parity verified).

### Tests
- 2 new helper tests (frontend suite **37 pass**); check-i18n PASS; `next build` success.

### Notes
- UI + network glue; the upload PUT-to-Storage and consent round-trip need the live `b40-documents`
  bucket — folded into the browser smoke-test carry-forward.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 5a (2026-05-22)

Document vault + referee + e-consent (backend; frontend is 5b).

### Added
- **`ApplicantDocument`, `Referee`, `Consent` models** (migration 0004; all RLS deny-by-default).
- **`storage.py`** — signed upload/download URLs for a private Supabase Storage bucket
  (`b40-documents`) via stdlib `urllib` + the service key; file bytes go browser↔Storage, never
  through Django. Best-effort (returns None on failure).
- **Endpoints** (scoped to the caller's shortlisted application): `documents/sign-upload/`,
  `documents/` (list/record), `documents/<id>/` (delete), `referees/`, `consent/`.
- **Consent + guardian gate** — versioned (`CONSENT_VERSION`), withdrawable, supersedes prior; a
  **minor (<18, age from NRIC DOB) requires a guardian** (name + relationship) or consent is rejected.
- `age_from_nric` / `is_minor` / `record_consent` services.

### Tests
- 18 new (`test_consent.py` 9, `test_documents.py` 9). Full backend suite **1077 pass, 0 fail**;
  golden masters unchanged.

### Notes
- Two deploy carry-forwards: create the `b40-documents` private bucket; replace the DRAFT consent
  text (`CONSENT_VERSION = '2026-draft-1'`) with the lawyer-reviewed version.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 4b (2026-05-21)

Post-shortlist next-steps flow (frontend) — completes Sprint 4.

### Added
- **`ScholarshipNextSteps` component** — a 3-step checklist driven by the `completeness` block:
  course quiz (links to the existing `/quiz`), about-you textareas, and a funding-need line-item
  form with a live RM total. PATCHes to the Sprint 4a details endpoint; "all done" banner on completion.
- Shortlisted applications on `/scholarship/apply` now render this flow (rejected/submitted keep
  the status card).
- `scholarship.ts` helpers: `fundingTotal`, `buildDetailsPayload`, `applicationToDetailsForm`,
  `emptyDetailsForm`.
- API: extended `ScholarshipApplication` type (`funding_need`, `completeness`, deeper-info) +
  `updateScholarshipDetails()` PATCH.
- i18n: `scholarship.nextSteps.*` in EN/MS/TA (819 keys, parity verified).

### Tests
- 5 new helper tests (frontend suite **35 pass**); check-i18n PASS; `next build` success.

### Notes
- Verified at compile + unit + i18n level; the PATCH round-trip + quiz-then-return flow need a
  browser smoke test against a live backend before Phase 1 ships (existing carry-forward).

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 4a (2026-05-21)

Post-shortlist data layer: funding need + deeper info + completeness (backend; frontend is 4b).

### Added
- **`FundingNeed` model** (OneToOne → application, `funding_needs`) — line items (tuition_gap,
  laptop, hostel, transport, books, monthly_allowance × allowance_months, other, other_desc) + a
  computed `total`. Quantifies the funding ask (the B40 analysis flagged its absence).
- **Deeper-info fields** on `ScholarshipApplication`: `aspirations`, `plans`, `fears`, `justification`.
- **`PATCH /api/v1/scholarship/applications/<id>/`** — saves deeper-info + funding need for the
  caller's own **shortlisted** application; read serializer now returns `funding_need` + a
  `completeness` block (`quiz_done` / `details_done` / `funding_done` / `complete`).
- `application_completeness()` + `save_application_details()` services. Migration 0003.
- `funding_needs` added to the deny-by-default RLS SQL.

### Tests
- 11 new (`test_details.py`). Full backend suite **1059 pass, 0 fail**; golden masters unchanged.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 3 (2026-05-21)

Mechanical shortlisting engine + Bucket A/B + pass/fail decision emails.

### Added
- **`apps/scholarship/shortlisting.py`** — pure `evaluate(app, cohort)` → status/bucket/reason.
  Per-criterion OK/marginal/fail across academic (A-count or PNGK), income (STR anchor + ceiling
  × 1.15 marginal band), intent and consent. All-OK → Bucket A; exactly one marginal → Bucket B;
  otherwise rejected. All thresholds read from `ScholarshipCohort`.
- **`shortlist_application()`** wired into the intake view — runs synchronously on submit, persists
  status/bucket/reason/shortlisted_at, sends the pass email immediately.
- **Trilingual pass + fail emails** (refactored `emails.py` onto a shared `_send` helper).
- **`send_pending_decision_emails` management command** — sends the courteous "not this round"
  email after `fail_email_delay_days`; `--dry-run`, prints the DB host, reads config from settings.
- Model fields `shortlisted_at`, `decision_email_sent_at`, `locale`, `notify_email` (migration 0002).

### Changed
- Submitting now triggers an instant shortlist: a qualifying applicant receives the acknowledgement
  *and* a congratulations email; a rejected applicant receives only the acknowledgement, with the
  fail email deferred to the command after the cohort delay.

### Tests
- 25 new (`test_shortlisting.py` 19, `test_decision_emails.py` 6) + updated intake tests. Full
  backend suite **1048 pass, 0 fail**; SPM/STPM golden masters unchanged.

### Notes
- The fail-email command's scheduler (e.g. Cloud Scheduler) is not yet wired — deploy work,
  deferred with the Supabase migration/RLS to the end of Phase 1.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 2 (2026-05-21)

Native application form + single front door (frontend), wired to the Sprint 1 intake API.

### Added
- **`/scholarship/apply` page** — trilingual application form with a requirements intro and
  status-gated rendering (loading / sign-in gate / form / success / already-applied), pre-filled
  from the AuthProvider profile. Lightweight academic capture (SPM A-count or STPM PNGK); full
  grades + quiz stay deferred to STEP 1A.
- **`src/lib/scholarship.ts`** — pure, node-testable helpers (`countAGrades`,
  `profileToApplyDefaults`, `buildApplicationPayload`, `applyFormError`).
- **API client** — `submitScholarshipApplication` + `getMyScholarshipApplications`.
- **`'apply'` auth-gate reason** — new branch in `auth-context` + `AuthGateModal` that reuses the
  existing Google sign-in + NRIC-claim flow and returns the user to `/scholarship/apply`.
- **"B40 Aid" header nav link.**
- **i18n** — `scholarship.*` block + `authGate.applyReason` in EN/MS/TA (793 keys, parity verified).

### Tests
- 13 new (`src/lib/__tests__/scholarship.test.ts`); full frontend suite **30 pass** (17 + 13).
- check-i18n PASS; `next build` success (`/scholarship/apply` compiles + prerenders).

### Notes
- Verified at compile + unit + i18n level. The OAuth round-trip (sign-in → return to apply) has
  not been browser-smoke-tested against a live backend — do so before Phase 1 ships.

## [Unreleased] — B40 Assistance Programme · Phase 1 Sprint 1 (2026-05-21)

New `apps/scholarship/` app — the financing extension's intake backbone. Phase 1 carries
no sponsor or money flow (those are Phases 2-3). See `docs/scholarship/b40-assistance-prd.md`
and `docs/scholarship/b40-phase1-roadmap.md`.

### Added
- **`ScholarshipCohort` model** (`scholarship_cohorts`) — per-round config holding the
  configurable shortlisting thresholds (`min_spm_a_count`, `min_stpm_pngk`, `income_ceiling`,
  `bucket_b_margin`) and funding/workflow parameters (`funding_envelope`, `fail_email_delay_days`)
  that the Sprint 3 rules engine will read.
- **`ScholarshipApplication` model** (`scholarship_applications`) — one application per student
  per cohort (partial unique constraint), with explicit shortlisting inputs (qualification,
  spm_a_count, stpm_pngk, household_income/size, receives_str/jkm, intended_pathway,
  intends_tertiary_2026, consent_to_contact), workflow fields (status, bucket, shortlist_reason,
  acknowledged_at) and a free-form `form_data` blob.
- **Intake API** — `GET/POST /api/v1/scholarship/applications/` (list own + submit) and
  `GET /api/v1/scholarship/applications/<id>/` (own detail). Submit resolves the active open
  cohort, snapshots the SPM A-count from the linked `StudentProfile` (A+/A/A- all count), sends
  a trilingual acknowledgement email, and stamps `acknowledged_at`. Default-deny auth; anonymous
  users and the duplicate/closed-round cases are rejected (403/409).
- **Trilingual acknowledgement email** (EN/MS/TA) via the existing Gmail SMTP infra; best-effort
  send that never blocks recording the application.
- **RLS policy SQL** (`apps/scholarship/sql/rls_policies.sql`) — enables RLS deny-by-default on
  both new tables (Django service role bypasses; direct PostgREST access denied). Apply before
  first deploy, then confirm Security Advisor 0 errors.

### Tests
- 17 new tests (`apps/scholarship/tests/`): models + defaults + partial-unique constraint +
  A-count helper (test_models.py, 4); intake create/ack-email/snapshot/consent/duplicate/
  closed-round/anonymous/no-profile/list-own/detail/cross-user-404/auth (test_api.py, 13).
- Full backend suite: **1023 passed, 0 failures** (1006 existing + 17 new); SPM/STPM golden
  masters unchanged.

### Notes
- Backend only — the native application form (frontend) is Sprint 2.
- Comms via email + in-app for Phase 1; WhatsApp deferred to Phase 2.

## [Unreleased] — Admin CSV Full Field Set (2026-05-02)

### Changed
- **Partner admin CSV export expanded from 7 columns to 27** (`/api/v1/admin/students/export/`). Now carries every field admins see in the dashboard detail view: identity (Name, IC, Angka Giliran, Email, Phone, School), demographics (Gender, Nationality), address (Address, Postal Code, City, State), eligibility context (Family Income, Siblings, Colorblind, Disability), academic (Exam Type, SPM Grades, STPM Grades, STPM CGPA, MUET Band), preferences (Financial Pressure, Travel Willingness), attribution (Referral Source, Referred By Org), and timestamps (Date Joined, Last Sign-In).
- `_fetch_auth_emails` → `_fetch_auth_data`: now fetches `last_sign_in_at` alongside `email` from `auth.users` in the same query.
- Export queryset now uses `select_related('referred_by_org')` to avoid N+1 lookups for the org-name column.

### Added
- **`Email` and `Last Sign-In` columns** joined from Supabase Auth's `auth.users` by `supabase_user_id`. Anonymous-only users (no email or phone) appear as blank in those columns; everyone else has them populated.
- JSON fields (SPM Grades, STPM Grades) are compactly stringified; empty `{}` renders as blank.
- Booleans render as `Yes`/`No` for human readability.

### Tests
- 5 tests in `apps/courses/tests/test_admin_export.py`: full 27-column header, full SPM profile rendering, STPM-specific columns, ghost-row blank rendering, auth-query-failure fallback.

---

## [2.0-rc] — 2026-03-20

### Added
- **OpenAI GPT-4o Mini fallback** for AI report generation when all Gemini models fail.
- **GCP cost monitoring**: RM50/month budget alert, BigQuery billing export.

---

## [Unreleased] — Auth Flow Canonical Refactor (2026-03-20)

### Changed
- **AuthProvider is single routing authority**: `status` + `profile` live in React context. Routing reads AuthProvider, never localStorage directly.
- **localStorage is write-only cache**: AuthProvider fetches from API, writes to localStorage as cache. `profile-restore.ts` deleted.
- **Callback page simplified**: Just establishes session, delegates all routing to AuthProvider status machine.
- **AuthGateModal reads context**: No more standalone `getProfile()` calls — reads `status`/`profile` from AuthProvider.
- **useOnboardingGuard reads AuthProvider**: Guards use AuthProvider state with loading support, not localStorage.
- **IC page guard reads status from AuthProvider**: Redirects if anonymous or already has NRIC.
- **STPM fields added to StudentProfile TS type**: Cached in AuthProvider alongside SPM fields.
- **Dashboard ranked results flattened to single list**: Removed dual-list display.

### Fixed
- **Rules of Hooks crash**: Moved `pendingProfileRedirect` useEffect before early return.
- **Onboarding redirect loop**: Resolved empty profile creation causing infinite redirects.
- **OAuth amnesia**: Stopped premature profile creation; fixed `signInWithGoogle` vs `linkIdentity` for login.
- **IC format**: Hyphens inserted before API call; loading race condition fixed.

### Removed
- `profile-restore.ts` — AuthProvider handles caching.
- TD-003 — auth flow refactored, localStorage no longer routing authority.

### Docs
- Comprehensive auth/onboarding flow documentation (`docs/auth-onboarding-flow.md`).
- Sprint retrospective, decisions, lessons.

### Tests
- 966 backend tests, 17 frontend, 0 failures.

---

## [Unreleased] — W14+W21 Ranking Sprint (2026-03-20)

### Added
- **W14**: 5-level STPM sort tiebreaking — score → uni tier → min_cgpa → difficulty → name.
- **W21**: `TRACK_FIELD_MAP` — matric:sains + stpm:sains → health + agriculture.
- 8 new tests.

---

## [Unreleased] — NRIC Hard Gate Sprint (2026-03-20)

### Added
- **Anonymous sign-in**: Auto-sign-in anonymously on first visit via Supabase; `isAnonymous` flag in AuthProvider.
- **linkIdentity helpers**: For upgrading anonymous sessions to Google-linked accounts.
- **NRIC hard gate middleware**: Blocks protected endpoints without NRIC — returns 403 `nric_required`.
- **Auth gate rewrite**: NRIC-first identity flow with `linkIdentity()`, replaces login page with redirect.
- **403 handler**: Frontend auto-shows auth gate on `nric_required` response.
- **Header updates**: Different UI for anonymous vs identified users.
- **IC page guard**: Redirect if anonymous or already has NRIC.
- 18 new integration tests for NRIC hard gate flow.

### Changed
- `isAuthenticated` now means has-NRIC; `hasSession` added as separate flag.
- Removed `get_or_create` from protected views — profiles must exist via NRIC claim.
- `is_anonymous` extracted from JWT in auth middleware.
- Course display limit unified to 9; explore filters sorted alphabetically.

---

## [Unreleased] — W7 FIELD_KEY_MAP Sprint (2026-03-20)

### Added
- 7 new `field_key` → signal mappings in `FIELD_KEY_MAP`.
- Search filter alphabetical sort.
- 8 new tests.

---

## [Unreleased] — Ranking Improvements Sprint (2026-03-19)

### Changed
- **W4**: 73 PISMP course tags backfilled for ranking accuracy.
- **W11**: STPM pre-quiz RIASEC signal derived from subjects (no quiz needed).
- Ranking audit doc added.
- W16 resolved.

### Fixed
- localStorage restoration from Supabase on login.
- Frontend boolean conversion — stopped converting booleans to Ya/Tidak before API calls.
- localStorage migration for legacy Ya/Tidak strings.

### Tests
- 40 new tests.

---

## [Unreleased] — i18n Sprint 2: Admin Pages (2026-03-19)

### Changed
- **All 7 admin pages internationalised**: 118 keys × 3 languages (EN/MS/TA).
- Zero hardcoded admin strings remaining.

---

## [Unreleased] — i18n & Bug Fixes Sprint (2026-03-19)

### Changed
- **BooleanField conversion**: `colorblind`/`disability` CharField → BooleanField (fixes dashboard 400 bug). Migration 0046.
- **Error mapping layer**: `ERROR_MAP` + `PATTERN_MAP` for i18n error translation.
- **Trilingual email verification**: EN/MS/TA templates.
- **Dynamic HTML lang attribute**: Set from locale.
- **Translated aria-labels**: Accessibility i18n.

### Fixed
- Dashboard 400 error from boolean field type mismatch.
- Hardcoded strings in auth callback, quiz, report, and IC onboarding pages replaced with `t()` calls.
- Stats display, login button, and incomplete badge UI fixes.

### Tests
- 4 new tests.

---

## [Unreleased] — STPM Quiz Sprint 5: Deploy & Validate (2026-03-18)

### Changed
- **Migrations 0042-0045 applied to Supabase**: MUET float type, postal_code/city/address profile fields, RIASEC/difficulty/efficacy enrichment fields, is_active flag — all applied via raw SQL (bypassing InconsistentMigrationHistory blocker).
- **RIASEC enrichment applied to production**: 867 STPM courses + 28 field taxonomy entries enriched with riasec_type, difficulty_level, efficacy_domain via `enrich_stpm_riasec --apply`.
- **Backend deployed**: `halatuju-api-00131-p7l` on Cloud Run asia-southeast1.
- **Frontend deployed**: `halatuju-web-00160-rql` on Cloud Run asia-southeast1.

### Verified
- Supabase Security Advisor: 0 new issues after schema changes.
- Smoke tests: STPM quiz questions (branch routing), quiz submit (signal accumulation), eligibility check (545 courses for strong science student), all passing on production.

## [Unreleased] — STPM Quiz Engine Sprint 4: Frontend (2026-03-18)

### Added
- **STPM quiz page** (`halatuju-web/src/app/stpm/quiz/page.tsx`): Branching card-based quiz UI with dynamic Q3/Q4 resolution after Q2. Reads subjects from localStorage, routes Science/Arts/Mixed branches via backend API, auto-advances between questions.
- **STPM quiz API client** (`halatuju-web/src/lib/api.ts`): 3 functions — `getStpmQuizQuestions`, `resolveStpmQuizQ3Q4`, `submitStpmQuiz` — plus `StpmResultFraming` type for ranking response framing.
- **Subject-to-API key mapping** (`halatuju-web/src/lib/subjects.ts`): `STPM_SUBJECT_TO_API_KEY` maps 20 frontend subject IDs (e.g. `PHYSICS`) to backend keys (e.g. `physics`).
- **STPM quiz storage keys** (`halatuju-web/src/lib/storage.ts`): `KEY_STPM_QUIZ_SIGNALS`, `KEY_STPM_QUIZ_BRANCH` for persisting quiz results across sessions.
- **Trilingual STPM quiz strings** (`messages/en.json`, `ms.json`, `ta.json`): Loading, error, skip, take/retake quiz labels.

### Changed
- **Dashboard shows quiz-informed framing** (`halatuju-web/src/app/dashboard/page.tsx`): When STPM quiz signals exist, dashboard header shows result framing (confirmatory/guided/discovery heading + subtitle). Quiz CTA routes to `/stpm/quiz`. Retake button shown after quiz completion.
- **Dashboard reads STPM quiz signals** (`dashboard/page.tsx`): STPM ranking now uses `KEY_STPM_QUIZ_SIGNALS` (falling back to `KEY_QUIZ_SIGNALS`), and displays framing from ranking API response.

## [Unreleased] — STPM Quiz Engine Sprint 3: Ranking Integration (2026-03-18)

### Changed
- **STPM ranking formula rewritten** (`stpm_ranking.py`): 7-component scoring — BASE(50) + CGPA_MARGIN(+20) + FIELD_MATCH(+12) + RIASEC_ALIGNMENT(+8) + EFFICACY_MODIFIER(+4/-2) + GOAL_ALIGNMENT(+4) - INTERVIEW(-3) - RESILIENCE_DISCOUNT(0/-3). Max score 98.
- **Eligibility output enriched** (`stpm_engine.py`): Eligible course dicts now include `riasec_type`, `difficulty_level`, `efficacy_domain` for ranking engine consumption
- **Ranking API returns framing** (`views.py`): `POST /stpm/ranking/` now includes `framing` object with mode (confirmatory/guided/discovery), heading, and subtitle from Q1 crystallisation signal

### Added
- **Result framing logic**: 3 modes based on Q1 — confirmatory ("Your profile aligns with..."), guided ("Based on your interests..."), discovery ("Here are fields worth exploring")
- **STPM field_key → field_interest reverse mapping** (`_FK_TO_INTEREST`): Maps Q3 sub-field signals back to Q2 broad interest for secondary field matching

### Tests
- 58 ranking tests (was 11): CGPA margin (5), field match (9), RIASEC alignment (8), efficacy modifier (6), goal alignment (7), resilience discount (7), interview (2), full integration (4), framing (5), ranked results (5)
- 881 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Quiz Engine Sprint 2: Data Enrichment (2026-03-18)

### Added
- **3 new fields on StpmCourse**: `riasec_type` (R/I/A/S/E/C), `difficulty_level` (low/moderate/high), `efficacy_domain` (quantitative/scientific/verbal/practical) — for quiz-informed ranking in Sprint 3
- **`riasec_primary` field on FieldTaxonomy**: maps each field to its primary Holland RIASEC type
- **`enrich_stpm_riasec` management command**: deterministic classifier using field_key → RIASEC/difficulty/efficacy mappings from the design doc. Covers 37 field_keys (all except `umum` catch-all). Dry-run by default, `--apply` to save.
- **Migration 0044**: `add_riasec_difficulty_efficacy_fields`

### Tests
- 40 new enrichment tests (mapping completeness, correctness, consistency, DB fields, management command)
- 829 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Quiz Engine Sprint 1: Foundation (2026-03-18)

### Added
- **STPM quiz data** (`stpm_quiz_data.py`): ~35 questions × 3 languages (EN/BM/TA) with subject-seeded branching design grounded in Holland's RIASEC, SCCT, SDT, and Super's Career Development Theory
- **STPM quiz engine** (`stpm_quiz_engine.py`): RIASEC seed calculation from STPM subjects, branch routing (Science/Arts/Mixed), grade-adaptive Q4 resolution, cross-domain Q5 stream filtering, signal accumulation into 9-category taxonomy
- **3 new API endpoints**: `GET /stpm/quiz/questions/` (returns branch-specific questions), `POST /stpm/quiz/resolve/` (resolves Q3+Q4 after Q2 answer), `POST /stpm/quiz/submit/` (processes answers → signals)
- **STPM signal taxonomy**: 9 categories (riasec_seed, field_interest, field_key, cross_domain, efficacy, resilience, motivation, career_goal, context)
- **Cross-domain asymmetry enforcement**: Science students see 6 Q5 options; arts students see only achievable options (no science-prerequisite programmes)
- **Grade-adaptive confidence check**: Q4 uses actual STPM grades — weak grades (≤B-) trigger honest framing, strong grades trigger confirmatory framing

### Tests
- 102 new STPM quiz tests (56 engine + 22 data + 24 API)
- 775 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 3: Validator + Workflow (2026-03-17)

### Added
- **Validator tool** (`Settings/_tools/stpm_requirements/validate_stpm_requirements.py`): 6 automated quality checks — completeness, subject key validity (validates against canonical key sets), grade validity, count sanity, cross-reference with source CSV, sample audit against raw HTML
- **Reusable workflow** (`Settings/_workflows/stpm-requirements-update.md`): Annual STPM requirements refresh SOP covering all 5 pipeline stages with checkpoints and failure modes

### Fixed
- Validator subject key check now catches invalid keys beyond `UNKNOWN:` prefix (validates against `VALID_STPM_KEYS`/`VALID_SPM_KEYS` sets)
- Validator handles `stpm_named_subjects` as list of dicts (real data format), not just list of strings
- Validator CSV cross-reference gracefully handles missing files instead of crashing
- Validator sample audit uses isolated PRNG (`random.Random(42)`) instead of global seed

### Tests
- 49 new validator tests (248 total pipeline tool tests)
- 590 backend tests, 17 frontend tests, 0 failures
- Golden masters: SPM=5319, STPM=2103

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 2: Backend Integration (2026-03-16)

### Added
- **Fixture converter** (`Settings/_tools/stpm_requirements/stpm_json_to_fixture.py`): Converts structured JSON → Django fixture format with null-safety for non-nullable model fields
- **4 new StpmRequirement boolean fields**: `req_male`, `req_female`, `single`, `no_disability` (migration 0031)
- **List-aware subject group engine**: `check_stpm_subject_group()` and `check_spm_prerequisites()` now handle both single dict (legacy) and list of dicts (new pipeline) formats with AND semantics
- **Exclusion list support**: SPM prerequisites engine checks `exclude` lists — student needs min_count subjects at min_grade from any subject NOT in the exclude list
- **Demographic eligibility checks**: `check_stpm_eligibility()` now enforces `req_male`, `req_female`, `no_disability`
- **API fields**: STPM course detail response includes `req_male`, `req_female`, `single`, `no_disability`
- **SpecialConditions component**: Renders gender, marital, disability conditions with colour-coded indicators
- **i18n keys**: `maleOnly`, `femaleOnly`, `unmarriedOnly`, `noDisability` in EN/MS/TA
- **Search page fix**: SPM grades merged from `KEY_GRADES` into profile for eligibility checks
- **Dashboard fix**: Report existence synced with DB on fresh devices

### Changed
- **STPM golden master**: 1811 → 2103 (richer requirement data = more eligible matches)
- **stpm_requirements.json fixture**: Regenerated from new pipeline (1,113 courses)

### Tests
- 32 new fixture converter tests (199 total pipeline tool tests)
- 590 backend tests, 17 frontend tests, 0 failures
- Golden masters: SPM=5319, STPM=2103

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 1: Parser Rewrite (2026-03-16)

### Added
- **Subject key registry** (`Settings/_tools/stpm_requirements/subject_keys.py`): 135+ subject mappings (25 STPM + 110 SPM), slash-combo handling, `UNKNOWN:` fallback
- **HTML→JSON parser** (`Settings/_tools/stpm_requirements/parse_stpm_html.py`): Per-`<li>` block parsing via BeautifulSoup, 11 block types, multi-tier STPM groups, exclusion lists
- **Pipeline test suite**: 167 tests (subject keys + parser + integration)
- Parsed 1,680 courses (1,003 science + 677 arts): 1.4% warning rate, 0 unknown subjects

## [Unreleased] — MASCO Career Mappings Sprint B: AI Mapping Pipeline (2026-03-16)

### Added
- **FIELD_KEY_TO_MASCO mapping**: Deterministic mapping from 31 field_keys to MASCO 2-digit occupation groups for pre-filtering
- **filter_masco_by_field_key**: Filters 4,854 MASCO jobs to ~200-400 relevant jobs per field
- **map_course_careers command**: AI-assisted career mapping pipeline
  - Generate mode (`--output`): iterates unmapped courses, calls Gemini, outputs review CSV
  - Apply mode (`--apply`): reads reviewed CSV, writes M2M links to DB
  - Supports both SPM (`--source-type`) and STPM (`--stpm`) courses
  - Rate limiting (`--delay`), batch size (`--limit`), Gemini model cascade

### Tests
- 12 new tests (5 mapping, 3 filter, 2 generate, 2 apply)
- Total: 568 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged)

## [Unreleased] — MASCO Career Mappings Sprint A: Backend Foundation (2026-03-16)

### Added
- **Full MASCO 2020 dataset**: `load_masco_full` management command loads 4,854 occupations from CSV with auto-generated eMASCO URLs (`https://emasco.mohr.gov.my/masco/{code}`)
- **StpmCourse.career_occupations**: New M2M field mirrors SPM `Course` model — STPM degree courses can now link to MASCO job codes
- **STPM detail API**: Now returns `career_occupations` array (same shape as SPM detail)
- **CareerPathways component**: Extracted from SPM detail page into shared component used by both SPM and STPM course detail pages; jobs with `emasco_url` are clickable, without are plain tags; hidden when empty

### Tests
- 10 new tests (4 data loading, 3 model, 3 API)
- Total: 556 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged — no eligibility/ranking changes)

## [Unreleased] — Field Taxonomy Sprint 5: Cleanup & Legacy Removal (2026-03-16)

### Changed
- **`field_key` non-nullable** — both `Course` and `StpmCourse` now require `field_key` (was nullable); all 1,503 courses already populated
- **Frontend field fallbacks** — all `course.field` references replaced with `getFieldName(course.field_key)` from taxonomy hook (detail pages, saved page, CourseCard)
- **Search API** — removed `?field=` fallback from frontend; only `field_key` sent

### Removed
- `frontend_label` column from `Course` model (migration 0028)
- `category` column from `StpmCourse` model (migration 0029)
- `frontend_label` from `CourseSerializer` output and TypeScript `Course` type
- `field` from `SearchParams` TypeScript type

### Tests
- Total: 530 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged)

## [Unreleased] — Field Taxonomy Sprint 4: Frontend Integration (2026-03-16)

### Changed
- **CourseCard images** — replaced 150-line `getImageSlug()` keyword matcher with taxonomy-driven lookup via `field_key` → `image_slug`; images now resolve from `FieldTaxonomy.image_slug` instead of hardcoded keyword rules
- **Search field filter** — dropdown now uses `/api/v1/fields/` taxonomy API with trilingual labels (EN/MS/TA) and filters by `field_key` instead of raw `frontend_label`/`field` strings
- **Search API** — `?field_key=` parameter now preferred over `?field=` for filtering; `field_keys` list added to search filter response
- **Dashboard** — STPM course cards now pass `field_key` through to CourseCard for correct image resolution

### Added
- `useFieldTaxonomy` hook — fetches taxonomy once, caches module-level, provides `getImageUrl(fieldKey)` and `getFieldName(fieldKey)` for trilingual field labels
- `fetchFieldTaxonomy()` API client function for `/api/v1/fields/`
- `field_key` added to `EligibleCourse`, `SearchCourse`, `StpmEligibleCourse` TypeScript types
- 2 new backend tests: `field_key` filter, `field_keys` in search filters

### Tests
- Total: 546 backend + 17 frontend, 0 failures

## [Unreleased] — Field Taxonomy Sprint 3: Ranking Engine field_key Integration (2026-03-16)

### Changed
- **SPM ranking** — field interest matching now uses `field_key` (taxonomy key) instead of `frontend_label` strings; `FIELD_LABEL_MAP` replaced by `FIELD_KEY_MAP`
- **STPM ranking** — keyword-based `_match_field_interest()` replaced with `field_key` lookup against shared `FIELD_KEY_MAP` (DRY); removed 48-line `COURSE_FIELD_MAP`
- **`field_health` signal** — now correctly maps to health fields (`perubatan`, `farmasi`, `sains-hayat`) instead of agriculture (was a bug)
- **`field_key` in eligibility results** — added to both SPM and STPM eligibility response dicts so ranking engines can use it

### Tests
- Updated 7 field interest tests (5 SPM, 2 STPM) from `frontend_label`/keyword to `field_key`
- Added 3 new tests: double-match bonus, no-field_key edge case (SPM + STPM)
- Total: 544 tests, 0 failures

---

## [Unreleased] — Field Taxonomy Sprint 2: STPM Classification + API Integration (2026-03-16)

### Added
- **STPM deterministic classifier** — `classify_stpm_course()` maps `category + field + course_name` to taxonomy key; handles ~170 category values across 29 taxonomy keys
- **`_classify_spm_matching()` helper** — sub-classifies 10 SPM-matching STPM categories using `course_name` (STPM field == category aggregate, not specific sub-discipline)
- **`FieldTaxonomySerializer`** — recursive serializer with `children` field for nested group→leaf structure
- **`GET /api/v1/fields/`** — returns 10 field groups with nested children (37 leaf fields)
- **`?field_key=` filter** — backwards-compatible query parameter on search endpoints (alongside existing `?field=`)
- **`field_key` in API responses** — added to SPM search, STPM search, and STPM course detail
- **`classify_stpm_fields` management command** — dry-run/save modes, distribution summary, safety checks
- **57 new STPM classifier tests** + 4 API endpoint tests (total 118 in test_field_taxonomy.py)
- **SQL reference script** — `scripts/stpm_backfill_field_key.sql` for documentation

### Database
- Backfilled all 1,113/1,113 STPM courses with `field_key_id` (0 unclassified)
- Distribution: 29 of 37 taxonomy keys used (top: pertanian=100, pendidikan=97, umum=77, sains-hayat=65, it-perisian=65)

---

## [Unreleased] — Field Taxonomy Sprint 1: Model + Migration + SPM Backfill (2026-03-16)

### Added
- **FieldTaxonomy model** — canonical table with 37 leaf fields + 10 parent groups, trilingual names (EN/MS/TA), image slugs, parent-child hierarchy
- **field_key FK** on `Course` and `StpmCourse` — nullable foreign key to FieldTaxonomy (will become non-nullable in Sprint 5)
- **Data migration** — populates all 47 taxonomy entries with trilingual names and sort orders
- **Deterministic classifier** — `classify_course()` maps `frontend_label + field + course_name` to taxonomy key; handles 16 production frontend_label variants
- **Backfill management command** — `backfill_spm_field_key` with `--save` flag (dry-run by default), safety check for PostgreSQL
- **Admin registration** — FieldTaxonomyAdmin with list/filter/search; CourseAdmin updated with field_key display/filter
- **55 new tests** — 7 model integrity tests + 48 classifier tests (including 24 production frontend_label tests)

### Database
- Created `field_taxonomy` table (47 entries) with RLS enabled (public read)
- Added `field_key_id` column to `courses` and `stpm_courses`
- Backfilled all 390 SPM courses (0 unmapped)
- Recorded Django migrations 0025 + 0026

---

## [Unreleased] — Special Conditions, Report Guard & Search Fix (2026-03-15)

### Added
- **Special Conditions expansion** — SpecialConditions component now shows gender restrictions (male/female only), unmarried requirement, and no-disability condition with colour-coded dots (blue/pink/purple/red)
- **i18n keys** — `maleOnly`, `femaleOnly`, `unmarriedOnly`, `noDisability` in EN/MS/TA
- **Contact form** — Supabase-backed contact form replaces raw email on contact page (name, email/phone, category, message)
- **Onboarding guard** — `useOnboardingGuard` hook protects dashboard/saved/profile/outcomes from users without grades
- **IC gate** — post-login IC + name collection page for users without NRIC
- **Smart auth routing** — Google OAuth and OTP login check NRIC → grades → route appropriately
- **Profile redesign** — two-column layout, amber incomplete indicators, email/phone/angka giliran fields, Yes/No toggles

### Fixed
- **Search "Eligible only" broken** — grades stored in `KEY_GRADES` but search page only read `KEY_PROFILE`; now merges both (root cause of 0 results)
- **"Generate Report" shown alongside "Read Report"** — syncs `reportGenerated` state from DB when localStorage flag missing (cross-device/cache clear)
- **Profile i18n bug** — `onboarding.name` key replaced with `profile.name` in all 3 languages
- **Mobile nav auth gate** — uses `link.authReason` instead of hardcoded `'profile'`

### Database
- Set `single = true` for 4 courses (IKBN-CET-005, UZ0520001, UZ0345001, UZ0721001) — recovered from deleted `details.csv`
- Created `contact_submissions` table with RLS (anon insert, service_role manage)

---

## [Unreleased] — Tech Debt Quick Wins 2 (2026-03-15)

### Added
- **Trilingual pre-U descriptions** — i18n keys (EN/MS/TA) for all 6 pre-U course headlines and descriptions in message files, replacing empty DB fields
- **Gemini API rate limiting** — max 3 reports per user per 24 hours via Django cache, returns 429 when exceeded (TD-009)
- **CourseListView pagination** — optional `?page=1&page_size=50` query params, backwards-compatible (TD-046)
- **Fallback description template** — `courses.descriptionFallback` i18n key replaces hardcoded fallback strings in course detail page

### Fixed
- **Engine field naming** — `three_m_only` used directly instead of runtime column rename hack in `apps.py` (TD-023)
- **Bug 4** — reclassified as "not a bug" (pre-U entry requirements are genuinely broad, not generic)
- **Bug 5** — pre-U description content added via i18n system (proper trilingual approach)

### Changed
- **Dependency pins relaxed** — `sentry-sdk>=1.39,<3.0` (was `<2.0`), `numpy>=1.24,<3.0` (was `<2.0`) (TD-039, TD-040)
- **Tech debt doc** — updated 10 items to reflect resolved status (5 from earlier sprints not marked, 5 new). Now 48/52 resolved.

---

## [Unreleased] — Bug Fixes & Auth Gating (2026-03-15)

### Added
- **Centralised localStorage keys** — `storage.ts` with 19 key constants + `clearAll()` helper, all 15 pages updated (TD-014 resolved)
- **Auth gating** — My Profile nav link, Load More buttons (dashboard SPM/STPM/ranked + search), and profile page now show sign-up modal for anon users
- **Saved courses UX** — institution name + course ID on saved cards, unified status toggle with correct state transitions (un-toggle "Got Offer" falls back to "Applied")
- **Error boundary pages** — `error.tsx`, `loading.tsx`, `not-found.tsx` for graceful error handling
- **Backend** — `institution_name` returned for both SPM and STPM saved courses
- **i18n** — `profileReason`, `loadmoreReason` auth gate messages in EN/MS/TA; error/loading/not-found page keys

### Changed
- About page tagline: removed "No sign-ups" (all 3 languages) since sign-up is now required for key features

---

## [Unreleased] — Saved Courses Sprint 2 (2026-03-15)

### Added
- **`useSavedCourses()` shared hook** — single source of truth for save state, auth gating, optimistic updates, toast feedback, and resume-after-login across all pages
- **Toast notification system** — `ToastProvider` + `useToast()` hook with success/error variants, auto-dismiss after 3s, slide-in animation
- **Search page save** — bookmark icon on search results now reflects actual saved state and toggles correctly
- **Detail page visual states** — save button shows green "Saved" when saved, red "Remove from Saved" on hover, blue "Save This Course" when not saved (both SPM and STPM detail pages)
- **Saved page SPM/STPM tabs** — tabbed interface with counts, correct detail page links per type (`/course/` for SPM, `/stpm/` for STPM)
- **Translation keys** — `courseDetail.saved`, `saved.noSpm`, `saved.noStpm` in EN/MS/TA

### Changed
- **Dashboard** — replaced ~50 lines of inline save logic with `useSavedCourses()` hook call
- **SPM detail page** — replaced broken `handleSave` (no auth, no token) with hook
- **STPM detail page** — same fix as SPM detail page

### Removed
- Inline `savedIds` state, `handleToggleSave`, `handleSaveOrGate` from dashboard (moved to hook)
- Direct `saveCourse`/`unsaveCourse` imports from detail pages (now via hook)

---

## [Unreleased] — Saved Courses Sprint 1 (2026-03-15)

### Added
- **STPM course saving** — SavedCourse model supports both SPM and STPM courses via dual nullable FKs with DB check constraint
- **Qualification filter** — `GET /saved-courses/?qualification=SPM|STPM` filters saved courses by type
- **Auto-detect STPM** — POST with `stpm-*` prefix or explicit `course_type` saves to correct FK
- **`course_type` in response** — GET /saved-courses/ returns `course_type: 'spm' | 'stpm'` per entry
- **Frontend types** — `SavedCourseWithStatus.course_type`, `saveCourse` accepts optional `courseType`, `getSavedCourses` accepts optional `qualification` filter

### Changed
- **SavedCourse model** — `course` FK now nullable, `stpm_course` FK added, `unique_together` replaced with partial unique indexes
- **SavedCourseDetailView** — DELETE/PATCH check both FKs when looking up saved course

### Database
- Supabase migration: `stpm_course_id` column, nullable `course_id`, check constraint, partial unique indexes

### Tests
- Saved courses tests expanded from 3 to 17 (SPM CRUD, STPM CRUD, qualification filter, idempotent save, check constraint enforcement)
- Full suite: 425 pass, 0 fail, 0 skip

---

## [Unreleased] — External Links & MOHE Sprint (2026-03-14)

### Added
- **MOHE ePanduan integration** — `mohe_url` field on StpmCourse, auto-generated URL pattern for 1,113 STPM courses, validated with Selenium-based page content checker
- **MOHE scraper + sync** — `scrape_mohe_courses` and `sync_stpm_mohe` management commands for auditing MOHE catalogue against DB
- **STPM URL validator** — Selenium-based validator (not HTTP status — MOHE always returns 200). Checks rendered page content for "daripada 0 carian" to detect dead links
- **Course-level "More Info" pill** — About section on course detail pages now shows a contextual "More Info" link: MOHE ePanduan for UA/poly/kkom, polycc for poly (TBD), MOE sites for matric/form 6/PISMP, institution hyperlink for TVET
- **Institution website links** — Institution cards now link to the institution's own website URL instead of the course-level hyperlink
- **STPM institution cards** — Rich institution card on STPM detail page with acronym, type, category, state, and website link (looked up from Institution table)
- **ILJTM/ILKBS filter split** — Search API resolves `tvet` source_type into `iljtm`/`ilkbs` using `course_pathway_map`; filter dropdown shows them separately
- **IPG campus URLs** — 27 IPG campuses populated with correct website URLs
- **Annual STPM data refresh procedure** — Documented in `docs/stpm-annual-refresh.md`

### Changed
- **Search limit** — Backend limit bumped from 100 to 10000 for full result sets
- **Merit colour logic** — STPM mata gred courses use inverted colours (low = green/good); arts stream ≤12 green, science ≤18 green
- **Pre-U course detail** — Department and WBL fields hidden for pre-U courses (not meaningful)
- **"More Info" pill style** — STPM detail page changed from "View on ePanduan (MOHE)" text link to compact pill button

### Fixed
- **1 dead MOHE URL** — UJ6521004 cleared after Selenium validation confirmed "daripada 0 carian"
- **Kolej Komuniti URL** — 1 missing institution URL fixed
- **Search pathway_type** — Search results now include `pathway_type` and `qualification` fields for correct badge rendering

---

## [Unreleased] — Security, API Consistency & Refactoring Sprints (2026-03-14)

### Changed
- **Default permissions flipped** — `DEFAULT_PERMISSION_CLASSES` changed from `AllowAny` to `SupabaseIsAuthenticated` (TD-012). 16 public views explicitly marked.
- **401 for unauthenticated** — Added `SupabaseAuthentication` DRF class; unauthenticated requests now return 401 with `WWW-Authenticate: Bearer` instead of 403 (TD-011)
- **DRF status constants** — All raw integer status codes replaced with DRF constants (TD-004)
- **EligibilityCheckView refactored** — Extracted 5 pure functions into `eligibility_service.py`, view reduced from 310 → 100 lines (TD-045)
- **Double DataFrame iteration eliminated** — `_apply_pismp_dedup()` no longer iterates twice (TD-044)

### Fixed
- **ProfileUpdateSerializer** — PUT/PATCH profile now validates via serializer instead of accepting arbitrary fields (TD-008)
- **SECRET_KEY guard** — Production raises ValueError if SECRET_KEY equals insecure dev default (TD-036)
- **CORS wildcard guard** — Production raises ValueError if CORS_ALLOWED_ORIGINS=* (TD-038)

---

## [Unreleased] — Tech Debt Sprint 4 (2026-03-14)

### Fixed
- **TD-001: STPM SPM prerequisite check** — Added `spm_pass_bi` and `spm_pass_math` to `SIMPLE_CHECKS` in `stpm_engine.py`. Zero programmes currently set these flags, so no eligibility results changed. STPM golden master baseline unchanged at 1,811.
- **TD-050: Quiz language bug** — Quiz page now reads locale from i18n context (`useT()`) instead of non-existent `halatuju_lang` localStorage key. Quiz loads in the user's selected language (EN/BM/TA).
- **TD-007: Bare except in engine.py** — `check_merit_probability()` now catches `(ValueError, TypeError)` instead of bare `except:`.
- **TD-020: Duplicate serializer key** — Removed duplicate `credit_stv` entry in `SPECIAL_FIELDS` dict.
- **TD-018: Duplicate import** — Removed redundant `from django.db.models import Count, Subquery, OuterRef` inside `EligibilityCheckView.post()`.
- **TD-019: Inline imports** — Moved `json` and `defaultdict` imports from inline method bodies to top of `views.py`.

---

## [Unreleased] — Hotfix Sprint (2026-03-14)

### Added
- **STPM programme institution enrichment** — Detail API now looks up university in `institutions` table, returning acronym, type, category, state, URL; frontend renders rich institution card matching SPM style
- **i18n: Max Grade Points** — New key `courseDetail.maxGradePoints` in EN ("Max Grade Points"), BM ("Mata Gred Maksimum"), TA ("அதிகபட்ச தர புள்ளிகள்")

- **STPM sidebar redesign** — Entry Requirements consolidated into unified card matching SPM route: General Requirements (checkmarks), STPM Requirements (key-value table), STPM Subjects (blue pills), SPM Prerequisites (green pills), Special Conditions (separate card with warning icon). STPM Subjects and SPM Prerequisites moved from left column to sidebar.

### Changed
- **Search: ILJTM/ILKBS resolution** — Search API now resolves `tvet` → `iljtm`/`ilkbs` using `course_pathway_map`; filter options show ILJTM and ILKBS separately instead of hidden `tvet`
- **Search: course limit removed** — Backend no longer caps at 100 courses; explore page shows all results
- **Course detail: merit label** — "Avg. Mata Gred" → "Max Grade Points" (i18n) for `stpm_mata_gred` merit type
- **Course detail: merit colour logic** — Arts stream: ≤12 green, 13-18 amber, >18 red; Science stream: ≤18 green, >18 amber

### Fixed
- **ILJTM/ILKBS badges on explore page** — CourseCard now receives `pathway_type` from search API, showing correct ILJTM/ILKBS badges instead of undefined
- **DB: Arts merit cutoff** — `stpm-sains-sosial` cutoff updated from 18 → 12 in Supabase

---

## [Unreleased] — UI Polish & Consistency Sprint

### Added
- **Rich institution cards for pre-U courses** — STPM course detail (`/course/stpm-*`) now shows schools with PPD, subjects (colour-coded badges), phone numbers from frontend JSON data; matric courses show colleges with tracks, phone, website
- **Subject Key legend** — STPM course detail pages include a sidebar legend explaining subject abbreviations (BT, L.ENG, etc.)
- **STPM programme detail redesign** — `/stpm/[id]` now matches SPM course detail format: header with level+stream badges, About section with AI description, Quick Facts sidebar (field, category, merit), institution card, save/actions buttons
- **STPM API enrichment** — Detail endpoint now returns `field`, `category`, `description`, `merit_score`

### Changed
- **Search filter labels standardised to Malay** — Universiti, IPGM, Politeknik, Kolej Komuniti, Kolej Matrikulasi, Tingkatan 6, ILJTM, ILKBS
- **TVET removed from search filter** — ILJTM and ILKBS appear separately; redundant "tvet" option hidden

### Fixed
- **Dashboard pathway pills** — matric/stpm pills now appear; university pill fixed (`'ua'` → `'university'` key)
- **Badge key case** — TYPE_LABELS/TYPE_COLORS changed from uppercase to lowercase keys to match API response
- **University ranking** — Added `'university'` key to PATHWAY_PRIORITY (was only `'ua'`)
- **Pathway priority** — Corrected order: asasi(8) > matric(7) > stpm(6) > university(5) > poly(4) > pismp(3) > kkom(2) > iljtm/ilkbs(1)
- **Institution name on SPM cards** — Dashboard course cards now show institution name, state, and count
- **DB state normalisation** — "Kuala Lumpur" → "WP Kuala Lumpur" (3 IPG campuses), "Labuan" → "WP Labuan" (1 matric college)
- **Level rename** — "Ijazah Sarjana Muda Pendidikan" → "Ijazah Sarjana Muda" (73 rows in Supabase)

## [Unreleased] — STPM Entrance (Sprints 1–5)

### Fixed (Sprint 5)
- **STPM grade scale** — Replaced E with D+(1.33), corrected C- from 2.00→1.67, kept E/G as legacy aliases in GRADE_ORDER for backward compatibility with parsed requirement data
- **Quiz signal localStorage key** — Dashboard STPM path read `halatuju_student_signals` (nonexistent) instead of `halatuju_quiz_signals`; quiz signals now reach STPM ranking correctly
- **STPM ranking field_interest format** — Fixed default value from `[]` to `{}` to match quiz engine's dict format

### Changed (Sprint 5)
- **STPM grade entry page redesign** — Stream selector (Science/Arts) as Section 1; 3 stream-filtered subject slots + 1 open elective; co-curriculum score input (0.00–4.00); overall CGPA = 90% academic + 10% co-curriculum; MUET as plain numbers; SPM prereqs split into 4 compulsory + 2 optional
- **Frontend CGPA points** — `lib/stpm.ts` updated to match backend (C-=1.67, D+=1.33, removed E)
- **SPM prereq constants** — Split `SPM_PREREQ_SUBJECTS` into `SPM_PREREQ_COMPULSORY` (4) + `SPM_PREREQ_OPTIONAL` (2)
- **i18n** — 9 new keys × 3 locales (stream, koko, formula labels)

### Added (Sprint 4)
- **STPM search API** — `GET /api/v1/stpm/search/` with text, university, stream filters + cursor pagination (20/page)
- **STPM programme detail API** — `GET /api/v1/stpm/programmes/<id>/` with human-readable subject labels, SPM prereqs, flags
- **STPM search page** — `/stpm/search` with debounced text input, dropdown filters, responsive card grid, load-more
- **STPM detail page** — `/stpm/[id]` with breadcrumb, stream badge, subject pills, quick facts sidebar, requirement flags
- **i18n** — 33 new `stpm.*` keys in EN/BM/TA for search and detail pages
- **Dashboard link** — "Browse All Programmes" button linking to STPM search

### Added (Sprint 3)
- **Supabase migration** — `stpm_courses` + `stpm_requirements` tables with RLS policies, 2,226 rows loaded
- **STPM ranking engine** — `stpm_ranking.py` (BASE=50, CGPA margin +20, field match +10, interview -3)
- **STPM ranking API** — `POST /api/v1/stpm/ranking/` endpoint
- **Frontend fit scores** — `rankStpmProgrammes()` API client, colour-coded badges (green ≥70, amber ≥55, grey <55)

### Added (Sprint 1)
- **StpmCourse & StpmRequirement models** — Django models for ~1,113 unique STPM degree programmes across ~20 public universities
- **STPM CSV data loader** — `load_stpm_data` management command loads science (1,003) + arts (677) CSVs with idempotent update_or_create
- **STPM eligibility engine** — `stpm_engine.py` with CGPA calculator, grade comparison, SPM prerequisite checks, STPM subject/group requirements, demographic filters
- **STPM eligibility API** — `POST /api/v1/stpm/eligibility/check/` endpoint accepting STPM grades, SPM grades, CGPA, MUET band
- **STPM golden master** — baseline 1811 across 5 test student profiles
- **Implementation plan** — `docs/plans/2026-03-12-stpm-entrance.md` (5 sprints, 22 tasks)

### Added (Sprint 2)
- **STPM subject definitions** — `lib/subjects.ts` constants (20 subjects, grade scale, MUET bands, SPM prereqs) aligned with backend engine keys
- **Frontend CGPA calculator** — `lib/stpm.ts` mirrors backend `stpm_engine.py` grade-point mapping
- **Exam type activation** — `/onboarding/exam-type` page now enables STPM selection (was "Coming Soon"), sets `halatuju_exam_type` in localStorage
- **STPM grade entry page** — `/onboarding/stpm-grades` single combined page with STPM subjects (PA compulsory + 4 optional), MUET band pills, auto-calculated CGPA, SPM prerequisites (6 subjects)
- **STPM API client** — `checkStpmEligibility()` in `lib/api.ts` with typed request/response interfaces
- **Dashboard STPM routing** — `dashboard/page.tsx` conditionally renders STPM programme cards or SPM course cards based on `exam_type`
- **Backend STPM profile fields** — `StudentProfile` gains `exam_type`, `stpm_grades`, `stpm_cgpa`, `muet_band`, `spm_prereq_grades` fields with profile sync + API support
- **i18n support** — 14 new translation keys across EN/MS/TA for STPM onboarding flow

### Stats
- Tests: 320 collected, 287 passing (1 new in Sprint 5, 12 in Sprint 4, 13 in Sprint 3, 6 in Sprint 2) | SPM golden master: 8283 | STPM golden master: 1811
- STPM programmes: 1,113 unique (from 1,680 CSV rows with 567 overlapping)

## [1.33.0] - 2026-03-12 — Unified Pre-U Backend & IPGM Integration

### Added
- **Backend Matric/STPM eligibility** — `pathways.py` port of all frontend eligibility logic (4 Matric tracks, 2 STPM bidangs, 32 tests)
- **Matric/STPM in API response** — eligible tracks returned in `eligible_courses` with merit labels, display fields, mata_gred
- **Unified pre-U ranking** — `calculate_matric_stpm_fit_score()` routes matric/stpm through prestige + academic + field preference + signal scoring (12 tests)
- **27 IPG campuses** — all Institut Pendidikan Guru campuses added as institutions, linked to 73 PISMP courses (1,971 offerings)
- **Pathway-based sort priority** — `PATHWAY_PRIORITY` dict replaces `SOURCE_TYPE_PRIORITY` for correct Asasi > Matric > STPM > UA > Poly > PISMP > KKOM ordering

### Fixed
- **PISMP ranking** — credential priority changed from 4 to 2.5; pathway priority from 5 to 3. Now sorts below Poly High, above KKOM High
- **ILJTM/ILKBS sort placement** — merit fallback 1.5 places them between Fair and Low tiers
- **Matric/STPM credential priority** — was returning 0 (fell through all checks); now returns 5 via source_type and name-based fallback
- **Course name capitalisation** — fixed BAHASA MELAYU → Bahasa Melayu, SAINS PENDIDIKAN → Sains Pendidikan, Ukm → UKM

### Removed
- **Frontend synthetic pre-U entries** — 201 lines removed from `dashboard/page.tsx` (pathwayResults, mergedRankingData, syntheticFlat useMemos)

### Stats
- Tests: 259 collected, 250 passing | Golden master: 8283
- Institutions: 239 (212 existing + 27 IPG)
- Course offerings: +1,971 PISMP-IPG links

## [1.32.2] - 2026-03-11 — Unified Pre-U Scoring & Pathway Fixes

### Added
- **Unified pre-U scoring system** — Asasi, Matric, and STPM all use consistent prestige + academic + field preference + signal adjustment scoring
  - Prestige order: Asasi (+12) > Matric (+8) > STPM (+5)
  - Academic bonus: Matric >=94:+8, >=89:+4; STPM <=4:+8, <=10:+4; Asasi >=90:+8, >=84:+4
  - Field preference bonus (+3) when quiz field interest matches pathway variant
- **Asasi-specific scoring in ranking engine** — replaces generic course-tag matching for pathway_type == 'asasi'
- **Matric/STPM cards for non-authenticated users** — synthetic pathway entries now appear in flat course list (without quiz)
- **Pre-U scoring design document** — `docs/plans/2026-03-11-pre-u-scoring-design.md`

### Changed
- **STPM progress bar scale** — uses full 3-27 mata gred range; shows raw values ("You: 4 | Need: 18") instead of converted 0-100
- **STPM Social Science 13-18 label** — changed from "Low" to "Fair" (appeal zone via Autonomi Pengetua)
- **Pathway card links** — now pass track/stream query params (was defaulting to Science)
- **MeritIndicator component** — accepts `displayStudent`/`displayCutoff` props for raw value display

### Removed
- **"Your Eligible Tracks" section** from Matric detail page (redundant with card grid)

## [1.32.1] - 2026-03-11 — Pathway Chance Indicator

### Added
- **Merit chance bar on Matric/STPM cards** — same High/Fair/Low indicator as regular courses
  - Matric: >= 94 High, 89-93 Fair, < 89 Low
  - STPM Science: always High (guaranteed place if eligible)
  - STPM Social Science: <= 12 High, 13-18 Low

### Changed
- **STPM Social Science eligibility expanded** — maxMataGred raised from 12 to 18; students with 13-18 now appear as Low chance instead of being excluded

## [1.32.0] - 2026-03-11 — Pathway Ranking, Quiz Flow, Data Persistence

### Added
- **Matric/STPM in ranked results** — pre-university pathways now compete in the ranked course list as synthetic entries with prestige + academic + quiz signal scoring (fit score range ~103-122)
- **Prestige scoring system** — `getPathwayFitScore()` in pathways.ts combines base score, prestige bonus (+8), academic bonus (merit/mata gred thresholds), and quiz signal adjustments
- **Supabase profile restore on login** — returning users get grades, demographics, and quiz signals restored from Supabase into localStorage automatically
- **localStorage cleanup on logout** — all `halatuju_*` keys wiped when signing out (multi-user device safety)

### Changed
- **Quiz signal adjustments for pathways** — 8 quiz questions now boost or penalise Matric/STPM scoring (e.g. concept-first learners +2, hands-on preference -1, pathway priority +3)
- **Report generation gated** — report can only be generated once per quiz run; retaking quiz resets the gate
- **Retake quiz navigation** — "Retake Quiz" button now navigates to `/quiz` instead of staying on dashboard

### Fixed
- **STPM subject data** — removed duplicate `pp` from 2 schools, fixed `PK`→`PAKN` mapping, removed redundant `MM/PP` from Kolej T6 Tun Fatimah
- **Missing STPM subjects** — added BT, BC, KMK, ICT, L.ENG to subject key legend with colours and full names

## [1.31.0] - 2026-03-11 — STPM UX Polish, WP Schools, MASCO Backfill

### Added
- **16 WP Kuala Lumpur Form 6 schools** — added to STPM school dataset from MOE SST6 portal
- **MASCO backfill management command** — `backfill_masco` command populates MASCO codes for 62 courses missing them, using Supabase lookup
- **Stream-filtered subjects** — STPM detail page filters school subjects by selected stream (Sains/Sastera)

### Changed
- **Average merit cutoff** — Quick Facts now shows average merit cutoff across all institutions offering the course, instead of student's own merit score
- **Pathway track cards on dashboard** — pills now show track cards inline when selected, with stream badge filtering
- **Card badge vs title** — pathway card badge shows short label (e.g. "Matric") while title keeps the full pathway name
- **STPM school data** — converted to title case at source for consistency
- **Mobile layout** — shorter labels, better spacing for pathway cards and course detail on small screens
- **Subject badges** — coloured by stream, phone number formatting improved, legend added to STPM detail page

### Fixed
- **WP and JPN preserved as uppercase** — title-case conversion no longer lowercases state abbreviations
- **School acronyms preserved** — e.g. "SMK" stays uppercase in school names

## [1.30.0] - 2026-03-10 — Matric/STPM Detail Pages, About Page, UX Fixes

### Added
- **Matriculation detail page** (`/pathway/matric`) — course-detail-style layout with header card, About This Track, Where to Study (15 KPM colleges), Quick Facts, Eligible Tracks sidebar, merit score with traffic light
- **STPM detail page** (`/pathway/stpm`) — same layout with 568 schools, state + PPD filters, stream badges, load-more pagination
- **Pathway track cards** — dashboard shows cards for each eligible matric track and STPM bidang when pills are active, with images, duration, fee, and institution count
- **Static data files** — `matric-colleges.ts` (15 colleges with track assignments from MOE Soalan Lazim Nov 2024) and `stpm-schools.json` (568 schools from MOE SST6 portal)
- **PathwayTrackCard component** — card component for matric tracks and STPM bidang with Supabase field images
- **About page content** — full mission statement: problem, what it does, who's behind it, how to help
- **About page i18n** — all content localised in EN, BM, and Tamil
- **Pathway detail i18n** — 30 keys across EN/BM/TA for matric/STPM detail pages
- **Student merit in Quick Facts** — course detail sidebar now shows student's merit score with colour coding

### Changed
- **Pathway pills** — matric and STPM pills now navigate to detail pages instead of filtering courses
- **Pathway pills as clickable filters** — all other pills toggle dashboard course filter; Clear button resets
- **Pathway pill order** — Asasi, Matric, Form 6 shown first; count shows eligible tracks (not scores)
- **Course detail header** — removed duplicate field name and duration (already in Quick Facts)
- **Institution link** — "Apply" button renamed to "More Info"
- **Phone login** — gracefully blocked with "coming soon" message directing users to Google sign-in

### Removed
- **Filter dropdowns** — removed institution type and course level dropdowns from dashboard (replaced by clickable pills)
- **"Ranked Courses" heading** — removed as redundant with Top Matches section

## [1.29.0] - 2026-03-10 — 9 Post-SPM Pathway Summary

### Added
- **Expanded pathways** — dashboard now shows 9 post-SPM options: Asasi, Matriculation, Form 6, PISMP, Polytechnic, University, Kolej Komuniti, ILJTM, ILKBS
- **Backend pathway_type** — eligibility API returns `pathway_type` field distinguishing Asasi from University (within UA), and ILJTM from ILKBS (within TVET) via institution category lookup
- **Course pathway map** — built at startup from CourseRequirement source_type, Course level, and Institution category
- **Compact badge layout** — PathwayCards redesigned as compact flex-wrap badges with unique SVG icons per pathway type
- **Pathway i18n** — 9 pathway type labels in EN/BM/TA plus "courses" count label

### Changed
- **PathwayCards component** — rewritten from individual track cards to compact summary badges showing eligible pathway types with course counts
- **Dashboard** — merges pathway engine results (Matric/STPM) with API eligibility counts by pathway_type

## [1.28.0] - 2026-03-10 — Matriculation & STPM Pathways

### Added
- **Matriculation eligibility** — 4 tracks (Sains, Kejuruteraan, Sains Komputer, Perakaunan) with subject requirements, minimum grade thresholds, and merit calculation (academic 90% + CoQ 10%)
- **STPM eligibility** — 2 bidang (Sains, Sains Sosial) with mata gred scoring. Best 3 credits from different subject groups, thresholds 18/12
- **Pathway engine** — pure TypeScript module (`lib/pathways.ts`) computing eligibility and scores entirely on the frontend
- **PathwayCards component** — dashboard cards showing eligibility status, merit scores (Matric) or mata gred (STPM), with reasons for ineligibility
- **4 stream subjects** — grades page expanded from 2 to 4 stream subject slots. Best 2 count as stream for UPU merit; weaker 2 compete with electives
- **Pathway i18n** — 14 translation keys across EN/BM/TA for pathway cards and eligibility reasons

### Changed
- **Grades page** — `aliranSubj1`/`aliranSubj2` state replaced with `aliranSubjects` array. Generic `handleAliranChange(index, id)` handler
- **UPU merit calculation** — sorts 4 stream grades, routes best 2 to stream section and weaker 2 to elective competition pool
- **Dashboard** — pathway cards rendered above course list, computed via `useMemo` from localStorage grades

## [1.27.0] - 2026-03-10 — Visual Quiz Redesign

### Added
- **Visual card quiz** — 8+1 questions with 2×2 icon card grids replacing old radio buttons. Each option has an emoji icon and short label
- **Multi-select** — Q1 ("What catches your eye?") and Q2 ("And this?") allow picking up to 2 options with weight splitting (3→2 each)
- **Conditional branching** — Q2.5 ("Which kind?") appears only when "Big Machines" is selected in Q2, splitting heavy industry into Electrical/Civil/Aero-Marine/Oil & Gas
- **"Not Sure Yet" option** — Q1, Q2, Q4 have a 5th option for undecided students. Q1/Q2 distribute +1 evenly across fields; Q4 generates zero signal
- **Field interest category** — new 6th signal category with 11 signals (`field_mechanical`, `field_digital`, `field_business`, `field_health`, `field_creative`, `field_hospitality`, `field_agriculture`, `field_electrical`, `field_civil`, `field_aero_marine`, `field_oil_gas`), capped at ±8
- **Field interest matching** — courses matched against `frontend_label` via `FIELD_LABEL_MAP`. Primary match +8, secondary +4
- **New signal wiring** — `rote_tolerant` (+3 for assessment-heavy courses), `high_stamina` (+2 for demanding courses), `quality_priority` (+1 for pathway-friendly/regulated courses)
- **Quiz i18n** — 12 new translation keys across EN/BM/TA for quiz UI (pickUpTo, notSureYet, becauseYouPicked, etc.)
- **Interpolation in i18n** — `t()` function now supports `{key}` parameter substitution

### Changed
- **Quiz data** — rewritten from 6 to 8+1 questions × 3 languages with `icon`, `select_mode`, `max_select`, `condition`, `not_sure` fields
- **Quiz engine** — handles both `option_index` (single) and `option_indices` (multi), weight splitting, "Not Sure Yet" exclusivity validation
- **Quiz submit API** — accepts either `option_index` or `option_indices` per answer
- **Ranking engine** — work preference cap lowered from ±6 to ±4; field interest cap ±8 (new)
- **Quiz page design** — gradient blue-purple header, progress bar, step dots, auto-advance on selection (no Next button), larger icons (text-5xl), mobile-first max-w-md layout

### Removed
- Dead signals: `organising`, `meaning_priority`, `exam_sensitive`, `time_pressure_sensitive`, `no_preference`
- Next button — auto-advance handles all navigation (300ms single-select, 400ms multi-select)

### Technical Notes
- 24 quiz tests + 16 ranking tests added. Total: 212 collected, 203 pass (9 pre-existing JWT failures). Golden master: 8245
- Stitch mockup: `projects/16660567457727755942` (10 screens)
- Design doc: `docs/quiz-redesign-final.md`
- Implementation plan: `docs/plans/2026-03-10-visual-quiz-redesign.md`
- Deployed as backend rev 41, frontend rev 47

## [1.26.0] - 2026-03-09 — My Profile & Course Interests

### Added
- **My Profile page** (`/profile`) — new page with 4 sections: Personal Details, Contact & Location, Family & Background, My Course Interests
- **Expanded student profile** — NRIC, address, phone number, family monthly income, number of siblings fields added to `StudentProfile` model (migrations 0010, 0011)
- **Course interest status** — saved courses now have a student-set status tag: Interested / Planning to apply / Applied / Got offer. Stored in `SavedCourse.interest_status` field
- **PATCH endpoint** — `PATCH /api/v1/saved-courses/<course_id>/` for updating interest status
- **Nav bar integration** — "My Profile" link added to top nav, dropdown menu, and mobile menu (all point to `/profile`)
- **i18n** — profile page translated in EN, BM, and TA (16 keys per language)
- **Exam-type page redesign** — gradient icon boxes, decorative corners, left-aligned layout, hover effects
- **Course detail page review** — documented 10 issues and prioritised fixes in `docs/Course Detail Page.pdf`

### Changed
- Profile API (`GET/PUT /api/v1/profile/`) returns and accepts new fields
- Profile sync (`POST /api/v1/profile/sync/`) accepts new fields
- Saved courses API (`GET /api/v1/saved-courses/`) returns `interest_status` per course
- "My Profile" links in header dropdown and mobile menu now point to `/profile` (was `/onboarding/grades`)

### Technical Notes
- 13 new backend tests (6 model + 3 SavedCourse + 4 API). Total: 188 collected, 179 pass (9 pre-existing JWT failures). Golden master: 8280
- Frontend build passes clean. `/profile` route: 4.3 kB (169 kB first load)
- Deployed as backend rev 40, frontend rev 44
- Design doc: `docs/plans/2026-03-09-my-profile-design.md`
- Stitch mockup: `projects/13238979537238863747`

## [1.25.1] - 2026-03-09 — Merit Score Fix

### Fixed
- **Merit score mismatch** — grades page showed 68.88 but course cards showed 56.38 for the same student. The backend was recalculating merit using a different subject grouping (5/3/1) instead of the correct UPU formula (4/2/2). Now the frontend sends its pre-computed merit score to the backend, eliminating the duplicate calculation entirely.

### Changed
- **Eligibility endpoint** — accepts optional `student_merit` field. When provided, skips backend recalculation. Falls back to old calculation for backwards compatibility.

### Technical Notes
- Frontend: grades page saves `finalMerit` to localStorage; dashboard includes it in API payload
- Backend: serializer accepts `student_merit`; view uses it directly when present
- 166 tests pass (9 pre-existing JWT failures unchanged). Golden master: 8280
- Deployed as backend rev 33, frontend rev 42

## [1.25.0] - 2026-02-26 — Eligible Toggle Auth Gate + Merit Progress Bar

### Added
- **Eligible toggle prompts login** — clicking the "Eligible Only" toggle on `/search` now opens the auth gate modal if the user is not logged in, encouraging account creation. Previously the toggle was permanently disabled because `halatuju_eligible_courses` was never written to localStorage.
- **`eligible` auth gate reason** — new `AuthGateReason` type, i18n strings (EN, BM, TA), resume action so toggle auto-activates after login
- **Merit progress bar indicator (Variation C)** — replaced simple traffic-light dot with a visual progress bar showing the student's score inside the bar, a dashed cutoff line, and "High/Fair/Low Chance" label with numeric scores (e.g. "You: 72 | Need: 65")
- **`eligibleMap` state** on search page — stores full `EligibleCourse` data (not just IDs), enabling merit scores to flow into CourseCard on the search page

### Changed
- **Eligible toggle** — changed from disabled `<label>` to always-clickable `<button>` element
- **MeritIndicator component** — now accepts `studentMerit` and `meritCutoff` props; falls back to simple dot+label when numeric scores are unavailable

### Technical Notes
- Frontend only — no backend changes, no migrations
- Build passes cleanly
- Deployed as frontend rev 40 (eligible toggle) and rev 41 (merit progress bar)
- Backend rev remains 32

## [1.23.4] - 2026-02-26 — Stitch Design Polish

### Changed
- **Pill labels shortened** — "All Institution Types" → "Institution Type", "All Levels" → "Course Level", etc. (EN, BM, TA)
- **Pill background** — white → gray-100 fill matching Stitch design
- **Search placeholder** — descriptive: "Search for courses, institutions, or fields (e.g. Computer Science, UM)..."
- **Clear Filters always visible** — greyed out when no filters active, blue when filters applied

## [1.23.3] - 2026-02-26 — Filter Pill Dropdown Redesign

### Changed
- **Filter dropdowns restyled as pill/chip buttons** — replaced 4 native HTML `<select>` elements with custom `FilterPill` component matching Stitch design (compact rounded pills, chevron icon, dropdown panels)
- **Active filter state** — selected pills highlight with primary blue border/background
- **Clear Filters button** — now has funnel icon and rounded-full styling to match pills
- **Outside-click dismiss** — dropdown panels close when clicking outside

### Technical Notes
- New component: `src/components/FilterPill.tsx` (~100 lines, uses `clsx`)
- No new dependencies, no backend changes, no i18n changes
- Build passes cleanly

## [1.23.2] - 2026-02-25 — Search Page Stitch Alignment

### Added
- **Institution info on search cards** — each course card now shows the primary institution name, state (pin icon), and "+N more" count when offered at multiple institutions
- **Book icon** on field text in course cards for visual consistency with Stitch design
- **Clear Filters button** — appears in the filter row when any filter is active, resets all filters in one click
- **Eligibility toggle redesign** — replaced plain checkbox with a styled pill toggle, moved into the filter row with descriptive subtitle text
- **Search API: institution fields** — backend now returns `institution_name` and `institution_state` per course via Django Subquery (alphabetically first offering)
- **3 new backend tests** for institution name, state, and empty-offering fallback
- **3 new i18n keys** (`clearFilters`, `eligibleToggleDesc`, `moreInstitutions`) in EN, BM, TA

### Technical Notes
- Backend tests: 173 collected, 164 passing (9 pre-existing JWT failures — not production)
- Golden master: 8280 (unchanged)
- Files changed: 8 (1 backend view, 1 test, 1 API type, 3 i18n, 1 component, 1 page)

## [1.23.1] - 2026-02-25 — Deploy Fix: Suspense Boundary

### Fixed
- **Next.js prerender crash** — `/search` page crashed during Cloud Run build because `useSearchParams()` requires a `<Suspense>` boundary for static generation. Wrapped `SearchPageInner` in `<Suspense>` with a loading spinner fallback.
- **Stale container image** — previous failed deploy pushed a stale image to gcr.io (old Container Registry). Redeployed from source to Artifact Registry (`asia-southeast1-docker.pkg.dev`), restoring correct build. Frontend now on rev 35.

### Technical Notes
- Backend tests: 173 passing (13 pre-existing JWT test failures — not a production issue)
- Golden master: 8280 (unchanged)

## [1.23.0] - 2026-02-25 — Course Search / Explorer

### Added
- **Course search page** (`/search`) — browse the full course catalogue with text search and 4 filters (Institution Type, Course Level, State, Field)
- **Search API** (`GET /api/v1/courses/search/`) — server-side filtering, pagination, dynamic filter options, institution count per course
- **Eligible-only toggle** — if student has eligibility data, toggle to show only courses they qualify for
- **"Explore" nav link** — added to header between Dashboard and Saved
- **i18n** — full search page translations in EN, BM, TA
- **10 backend tests** for the search endpoint (text, level, field, source_type, state, pagination, combined, institution count)

### Changed
- **Institution URLs** — corrected 7 broken/outdated institution website links in `data/institutions.csv`

## [1.22.4] - 2026-02-25 — Profile Page Polish

### Changed
- **Profile icons** — replaced emoji icons (🇲🇾, 🌍, 👨, 👩, 🎨, ♿) with inline SVG icons for nationality, gender, and health condition buttons; icons change colour when selected
- **"Non-Malaysian" label** — renamed to "Foreign" (EN), "Asing" (BM), "வெளிநாட்டவர்" (TA) for clarity

## [1.22.3] - 2026-02-23 — Merit Formula Fix + Supabase Security

### Fixed
- **UPU merit formula** — replaced incorrect engine.py port with correct UPU calculation: `weighted = (core/72×40) + (stream/36×30) + (elective/36×10)`, `academic = weighted × 9/8`, cap 90 + CoQ
- **Stale grades bug** — grades from previously-selected subjects lingered in localStorage, inflating merit score; now only grades for currently-selected subjects (core + aliran + electives) are loaded
- **Dynamic merit on subject switch** — clearing old subject grades when switching stream, aliran, or elective subjects so merit updates immediately
- **14 Supabase RLS initplan warnings** — rewrote all RLS policies using `(select auth.uid())` subselect for performance
- **Supabase `django_migrations` RLS** — enabled Row Level Security on Django migrations table (security advisory)

### Changed
- **Merit score display** — removed green/yellow colour coding; score displays in neutral grey (no judgement)
- **Merit calculation** — grades page now passes categorised grades (core/stream/elective) directly instead of flat map with heuristic splitting

## [1.22.2] - 2026-02-23 — UI Polish: Grades Page

### Changed
- **Subject renames** — "Bahasa Tamil" → "Bahasa Cina/Tamil", "Bahasa Cina" → "Kesusasteraan Cina/Tamil" (combined options to shorten dropdown)
- **Stream pills** — equal-width grid layout, less rounded (rounded-xl), two-tone SVG icons (flask/book/wrench)
- **Shadow/depth treatment** — subtle shadows on core subject cards, stream pills, compact subject rows, merit panel, grade buttons (modern soft style)

### Added
- **Lukisan** — new subject in Arts stream pool and elective list (distinct from PSV)
- **StreamIcon component** — two-tone SVG icons for science/arts/technical streams

## [1.22.1] - 2026-02-23 — Sprint 20: Merit Score & CoQ

### Added
- **Co-curricular (CoQ) score input** — decimal number input (0-10, e.g. 5.50, 7.85) on profile page
- **Live merit score panel** — grades page shows real-time academic merit (/ 90) + CoQ (/ 10) = total (/ 100) as grades are entered
- **Client-side merit calculator** — TypeScript port of `engine.py` formula in `lib/merit.ts` (`prepareMeritInputs` + `calculateMeritScore`)
- New translation keys in EN, BM, TA: coqScore, coqHint, meritScore, academicMerit, coqMerit, meritTotal

### Fixed
- **Stream subject pre-population** — first-time visitors now see default stream subjects (PHY/CHE for science) instead of empty dropdowns

### Changed
- **Backend CoQ passthrough** — `EligibilityRequestSerializer` now accepts `coq_score` (float, 0-10); `views.py` uses it instead of hardcoded 5.0
- Dashboard passes saved CoQ from profile localStorage to eligibility API
- `StudentProfile` interface updated with optional `coq_score` field

## [1.22.0] - 2026-02-23 — Sprint 20: Onboarding Redesign

### Added
- **SPM/STPM exam type selection** — new `/onboarding/exam-type` screen with SPM card (active) and STPM card (coming soon)
- **Progress stepper** — shared `ProgressStepper` component shows "Step 1 of 3" with visual progress bars across all onboarding screens
- **Negeri (state) dropdown** — 16 Malaysian states/territories added to profile page
- **Elective subject add button** — "Tambah Subjek Elektif" dashed button to dynamically add 0-2 elective subjects
- New translation keys in EN, BM, TA for all new UI elements

### Changed
- **Stream + grades merged** — stream selection (compact pill buttons) now lives on the grades page, removing one navigation step
- **Core subjects redesign** — button grid with green checkmark on completion, clear icon, responsive 5+5 mobile layout
- **Stream/elective subjects redesign** — compact dropdown + grade badge dropdown rows replacing full button grids
- **Profile page compact layout** — single card with Negeri, Jantina toggle, Nationality toggle, Keperluan Khas checkboxes with accessibility icons
- **Improved helper text** — contextual subtitles on each screen ("Enter your grades so we can find courses that match your results")
- All `/onboarding/stream` links updated to `/onboarding/exam-type` across landing, dashboard, footer, login pages

### Removed
- `/onboarding/stream` page — stream selection moved into grades page

### Technical Notes
- Next.js build: 20 routes, 0 errors
- Files: 10 modified/created, 1 deleted
- Backend tests: 176 (unchanged — frontend-only sprint)
- Golden master: 8280 (unchanged)

## [1.21.0] - 2026-02-23 — Course Image Classification (37 Categories)

### Added
- **37 AI-generated course images** — replaced 9 generic field images with 37 category-specific images generated via Gemini 2.5 Flash Image, covering all 383 courses
- **Keyword-based image matching** — `CourseCard.tsx` now uses a multi-level matcher (`getImageSlug`) that routes courses to images based on field name and course name keywords
- **Sub-routing for large fields** — Pendidikan (73 courses) splits into 5 teaching-subject images; Mekanikal & Pembuatan (24) into 4; Elektrik & Elektronik (13) into 3; Teknologi Maklumat into 2
- **"Umum" dissolution** — 17 miscategorised "Umum" courses now route to proper categories via course name matching (e.g. perikanan → pertanian, bank → perakaunan)
- **Future STPM images** — pre-created images for Undang-undang and Farmasi categories

### Changed
- **Every course now has an image** — previous system had 97% of courses showing a grey placeholder (only 13/383 matched). Now 383/383 resolve to a relevant image
- **`getFieldImageUrl` signature** — now takes `(field, courseName)` instead of just `(field)`, enabling course-name-based sub-routing
- **Image generation script** — `tools/generate_field_images.py` rewritten with 37 categories, detailed Malaysian-context prompts, and `--skip-existing` flag

### Technical Notes
- 37 images uploaded to Supabase Storage `field-images` bucket (~1.5-2 MB each)
- 15-max rule: no image category covers more than 15 courses
- Next.js build: 20 routes compiled successfully
- Modified files: `CourseCard.tsx`, `generate_field_images.py`, `CHANGELOG.md`

## [1.20.0] - 2026-02-23 — Sprint 18: Header & Footer Redesign

### Added
- **AppHeader component** — shared responsive header with logo (120px), Dashboard/Saved nav links with active indicator, profile dropdown (name, email, My Profile, My Applications, Settings, Log Out), mobile hamburger menu with slide-out drawer
- **AppFooter component** — shared footer with brand column + tagline, Quick Links (Dashboard, Start Here, Saved), Legal links (About, Privacy, Terms, Cookies), copyright bar with Contact Us link
- **Profile dropdown** — shows user initials avatar, full name and email from Supabase session metadata, grouped account actions, red Log Out button with sign-out via Supabase
- **Cookies page** (`/cookies`) — explains essential cookies only, no tracking/analytics, links to Settings for data clearing
- **Contact page** (`/contact`) — Tamil Foundation (MCEF) contact info, email for enquiries and data deletion requests
- **Logout functionality** — first time users can sign out (calls `supabase.auth.signOut()`, redirects to landing)
- **i18n keys** — `header.*` (myProfile, myApplications, logout), `footer.*` (tagline, quickLinks, legal, startHere), `common.cookies`, `common.contact` in all 3 languages (EN, BM, TA)

### Changed
- **Logo optimised** — compressed from 6.2 MB to 27 KB (99.6% reduction), transparent background, 480px wide for retina
- **Logo size increased** — rendered at 120×40px across all pages (was 60×32px), improves brand visibility
- **All pages now use shared header/footer** — dashboard, saved, settings, outcomes, about, privacy, terms, course detail, report. Landing page uses shared footer with its own hero header. Quiz page keeps focused workflow header.
- **About/Privacy/Terms pages** — upgraded from back-arrow mini-headers to full AppHeader + AppFooter
- **Privacy page** — added contact email link

### Technical Notes
- Backend tests: 176 (unchanged) | Golden master: 8280 (unchanged)
- Next.js build: 20 routes compiled successfully
- New files: `AppHeader.tsx`, `AppFooter.tsx`, `/cookies/page.tsx`, `/contact/page.tsx`
- Modified: 15 frontend files, 0 backend files

## [1.19.1] - 2026-02-22 — Post-Sprint 17 Hotfixes

### Fixed
- **ES256 JWT authentication**: Supabase user access tokens use ES256 (JWKS), but middleware only accepted HS256 — all authenticated API calls (saved-courses, reports, outcomes) returned 403. Middleware now checks token `alg` header and routes to HS256 (JWT secret) or ES256 (JWKS public key via `PyJWKClient`).
- **Missing Cloud Run env vars**: Added `SUPABASE_JWT_SECRET`, `GEMINI_API_KEY`, and `SUPABASE_URL` to backend Cloud Run service.
- **Google name pre-fill**: AuthGateModal now pre-fills the user's name from their Google profile on OAuth sign-in.

### Added
- **"Read Report" button**: Dashboard shows "Read Report" (linking to existing report) instead of "Generate Report" when a report already exists. Reverts to "Generate Report" on quiz retake.
- **3 i18n keys**: `dashboard.readReport` in EN ("Read Report"), BM ("Baca Laporan"), TA ("அறிக்கையைப் படி")

### Technical Notes
- Backend tests: 176 (unchanged) | Golden master: 8280 (unchanged)
- Deployed: backend rev 26, frontend rev 20
- Cloud Run env vars added: `SUPABASE_JWT_SECRET`, `GEMINI_API_KEY`, `SUPABASE_URL`
- JWKS client uses `PyJWKClient` from `PyJWT` with automatic key caching

## [1.19.0] - 2026-02-22 — Sprint 17: Outcome Tracking

### Added
- **AdmissionOutcome model** — tracks student application outcomes (applied/offered/accepted/rejected/withdrawn) per course+institution, with intake year, session, notes, and date fields
- **CRUD endpoints** (`/api/v1/outcomes/` and `/api/v1/outcomes/<id>/`) — list, create, update status, delete. All auth-required, filtered to own outcomes.
- **"I Applied!" / "I Got an Offer!" buttons** on saved courses page — inline outcome creation with optimistic UI
- **Outcomes page** (`/outcomes`) — "My Applications" page listing all outcomes with colour-coded status badges, inline status editing, and delete
- **Track Applications CTA** on saved courses page — links to outcomes page
- **20 i18n keys** in `outcomes.*` section across all 3 locales (EN, BM, Tamil)
- 10 new backend tests: CRUD, duplicate (409), auth enforcement (403), cross-user isolation

### Technical Notes
- Backend tests: 176 (+10) | Golden master: 8280 (unchanged)
- Frontend build: passes clean
- Migration 0009 applied: `admission_outcomes` table with RLS + 5 policies
- Supabase security advisor: 0 errors (excluding known `django_migrations`)
- Sprint 16 deployed: backend rev 21, frontend rev 17

## [1.18.0] - 2026-02-22 — Sprint 16: Registration Gate

### Added
- **AuthGateModal** (`components/AuthGateModal.tsx`): Multi-step registration modal with inline Phone OTP + Google OAuth sign-in, reason-specific messaging (quiz/save/report), benefit bullets, and name+school profile completion form
- **AuthContext** (`lib/auth-context.tsx`): `AuthProvider` + `useAuth()` hook wrapping Supabase session state, providing `token`, `isAuthenticated`, `showAuthGate(reason)`, `hideAuthGate()`. Detects pending Google OAuth actions on mount.
- **ProfileSyncView** (`POST /api/v1/profile/sync/`): New backend endpoint that bulk-pushes localStorage data (grades, gender, quiz signals, name, school) to backend after first login — creates or updates profile in one call
- **`name` + `school` fields** on `StudentProfile` model (migration 0008) — for follow-up tracking
- **Profile sync API** (`syncProfile()` in `api.ts`) + `SyncProfileData` type
- **21 i18n keys** in `authGate.*` section across all 3 locales (EN, BM, Tamil)
- 4 new backend tests: sync creates profile, sync updates existing, sync rejects anon, profile PUT accepts name/school

### Changed
- **Dashboard**: Save button always visible (gates on auth if not logged in), Report CTA always visible (was hidden for guests), Quiz CTA triggers auth gate instead of direct navigation. Actions auto-resume after auth completion via localStorage resume action.
- **Quiz page**: Gated behind authentication — shows sign-in prompt with auth gate trigger for unauthenticated visitors
- **Dashboard imports**: Replaced ad-hoc `getSession()` with `useAuth()` hook for consistent auth state

### Technical Notes
- Backend tests: 166 (+4) | Golden master: 8280 (unchanged)
- Frontend build: passes clean
- Google OAuth edge case handled: pending action stored in localStorage before redirect, AuthProvider restores it on mount, modal opens at profile step
- New files: `components/AuthGateModal.tsx`, `lib/auth-context.tsx`
- Modified: `providers.tsx`, `dashboard/page.tsx`, `quiz/page.tsx`, `api.ts`, `views.py`, `models.py`, `urls.py`, `en.json`, `ms.json`, `ta.json`

## [1.17.0] - 2026-02-22 — Sprint 16: Bilingual Descriptions Pipeline

### Added
- `headline_en` and `description_en` fields on Course model (migration 0007)
- `load_course_descriptions()` method in data loader — reads `course_descriptions.json`, populates all 4 description fields
- `data/course_descriptions.json` — 383 bilingual course descriptions extracted from `src/description.py`
- Course detail page now shows locale-appropriate headline and description (BM for `ms`, EN for `en`/`ta`)
- `courseDetail.*` i18n keys added to all 3 locale files (EN, BM, Tamil)
- 6 new tests: bilingual API fields, empty defaults, description loading, TVET overwrite protection

### Fixed
- TVET metadata loader no longer overwrites rich descriptions with thin CSV text (conditional update)

### Technical Notes
- CourseSerializer now exposes `headline_en`, `description_en`
- Frontend `Course` interface updated with new fields
- Supabase migration applied: `ALTER TABLE courses ADD COLUMN headline_en/description_en`
- Backend tests: 162 (was 156) | Golden master: 8280 (unchanged)

## [1.16.1] - 2026-02-21 — Description Sprint: Quality Audit + English Translations

### Added
- English translations (`headline_en`, `synopsis_en`) for all 383 course descriptions in `src/description.py` — enables bilingual course cards
- `headline` field added to all entries (previously only `synopsis` existed)
- English fallback defaults in `get_course_details()` function

### Fixed
- 33 description quality issues across all 6 institution types:
  - 25 "mereka" (third-person) pronoun fixes → "anda" (second-person, direct address)
  - 2 typos: "DANN" → "DAN", "turu padang" → "turun padang"
  - 2 thin descriptions expanded (IJTM-CET-035, IJTM-CET-037)
  - 3 headline fixes ("Suara Untuk Mereka" → "Suara Untuk Semua")
  - 1 "kita" → "anda" fix

### Technical Notes
- `src/description.py`: ~2,400 → ~3,090 lines
- All 383 entries verified via AST parsing — 100% bilingual coverage
- British English spelling throughout translations
- Backend tests: 156 (unchanged) | Golden master: 8280 (unchanged)

## [1.16.0] - 2026-02-20 — Sprint 15: Career Pathways (MASCO Integration)

### Added
- **MascoOccupation model**: New Django model with `masco_code` (PK), `job_title`, `emasco_url` — stores 272 MASCO-classified occupations from Malaysia's official eMASCO portal
- **Course ↔ Occupation M2M**: `Course.career_occupations` ManyToManyField links courses to career outcomes (531 unique links across all TVET and Polytechnic courses)
- **Career Pathways on course detail**: New "Career Pathways" section on `/course/[id]` page shows clickable indigo pill badges linking to eMASCO portal pages for each linked occupation
- **API: career_occupations in course detail**: `GET /api/v1/courses/<id>/` now returns `career_occupations` list with `masco_code`, `job_title`, and `emasco_url`
- **MASCO data loaders**: Two new methods in `load_csv_data.py` — `load_masco_occupations` (from `masco_details.csv`) and `load_course_masco_links` (from `course_masco_link.csv` with deduplication)
- **8 new tests**: 3 API tests (career occupations in detail, field validation, empty list) + 5 model tests (PK, M2M, reverse relation, idempotent update_or_create, __str__)
- Migration `0005_add_masco_occupations`

### Technical Notes
- Backend tests: 156 (+8) | Golden master: 8280 (unchanged)
- Data loaded into Supabase with RLS enabled (public read) on both `masco_occupations` and `courses_course_career_occupations` tables
- MASCO data sourced from existing project files (`data/masco_details.csv`, `data/course_masco_link.csv`) — originally used by legacy Streamlit app
- eMASCO portal pages contain starting salary, annual increment, demand status, and job descriptions

## [1.15.0] - 2026-02-20 — Sprint 14: TVET Data Fix + UX Polish

### Fixed
- **TVET orphaned courses**: All 84 TVET courses had zero institution links because `load_course_details` used `.filter().update()` on non-existent `CourseInstitution` records. Changed to `update_or_create` so TVET rows in `details.csv` create links when none exist.
- **Institution taxonomy**: 55 ILKBS/ILJTM institutions were incorrectly typed as `IPTA`. Changed to `ILKA` in `data/institutions.csv` and Supabase DB (157 IPTA + 55 ILKA).

### Added
- **181 TVET course-institution links** now loaded correctly — IKBN/IKTBN/IKSN courses linked to ILKBS institutions, ILP/ADTEC/JMTI courses linked to ILJTM institutions, with fees, allowances, and application hyperlinks.
- **Settings page redesign** (`settings/page.tsx`): Language selector, clear profile data button, about section — fully localised (EN/BM/TA).
- **Saved page i18n**: Localised with `useT()` hook across all 3 locales.
- **Settings and saved i18n keys**: Added `settings.*` and `saved.*` translation keys to all 3 locale files.

### Changed
- **Gemini SDK migration**: `google-generativeai` (deprecated) replaced with `google-genai` v1.x Client API pattern in `report_engine.py`. Updated mocks in `test_report_engine.py`.
- **`requirements.txt`**: `google-generativeai>=0.3,<1.0` → `google-genai>=1.0,<2.0`

### Technical Notes
- Backend tests: 148 (unchanged) | Golden master: 8280 (unchanged)
- Both `halatuju-api` and `halatuju-web` deployed to Cloud Run
- Data fix applied directly to Supabase DB (55 institution type updates + 181 link inserts)

## [1.14.0] - 2026-02-18 — Sprint 13: Localisation (EN/BM/TA)

### Added
- **i18n infrastructure** (`lib/i18n.tsx`): React context with `useT()` hook, localStorage-persisted locale preference, static JSON imports for zero-latency switching
- **Language selector** (`components/LanguageSelector.tsx`): Dropdown in landing page nav and dashboard header — switches between English, Bahasa Melayu, and Tamil
- **142 translation keys** per locale across 6 sections: common, landing, onboarding, dashboard, login, subjects
- **i18n validation script** (`scripts/check-i18n.js`): Checks JSON parsing, key completeness across all 3 locales, and no empty values

### Changed
- **6 core pages localised**: Landing, stream selection, grades input, profile input, dashboard, and login — all hardcoded strings replaced with `t('key')` calls
- **Landing page** converted from server component to client component to support `useT()` hook
- **Grades page**: Core subject labels now use translated `t('subjects.XX')` keys; stream/elective subjects retain official Malay names
- **Dashboard sub-components** (`InsightsPanel`, `FilterDropdown`, `RankedResults`, `LoadingScreen`) each call `useT()` for their own translated strings
- **Tamil translations** quality-reviewed per style guide: brand name kept as "HalaTuju", compound words joined, sandhi rules applied

### Technical Notes
- Backend tests: 148 (unchanged) | Golden master: 8280 (unchanged)
- Frontend-only sprint — no backend changes, no migrations
- New files: `lib/i18n.tsx`, `components/LanguageSelector.tsx`, `scripts/check-i18n.js`
- Modified: 3 JSON translation files + 6 page files + `providers.tsx`

## [1.13.0] - 2026-02-18 — Sprint 12: Report Frontend + PDF

### Added
- **Report display page** (`/report/[id]`): Renders AI counsellor report as formatted markdown with `react-markdown` and Tailwind Typography prose styling
- **PDF download**: "Download PDF" button using `window.print()` with `@media print` stylesheet (A4, clean layout, hidden nav)
- **Generate Report CTA** on dashboard: Auth-protected button calls `POST /api/v1/reports/generate/`, redirects to report page on success
- **Report API client functions** in `api.ts`: `generateReport()`, `getReport()`, `getReports()` with TypeScript types
- 4 new view tests: report list (own reports only), report detail, cross-user 404 regression, validation

### Fixed
- **FK bug in report views**: `ReportDetailView` and `ReportListView` filtered by `student_id=request.user_id` (comparing integer PK with UUID string — would never match). Fixed to `student__supabase_user_id=request.user_id`

### Dependencies
- Added `react-markdown@10.1.0` for markdown rendering
- Added `@tailwindcss/typography` for prose styling

## [1.12.0] - 2026-02-18 — Sprint 11: AI Report Backend

### Added
- **Report engine** (`apps/reports/report_engine.py`): Gemini-powered narrative counselor report generator with model cascade fallback (gemini-2.5-flash → gemini-2.5-flash-lite → gemini-2.0-flash)
- **Report prompts** (`apps/reports/prompts.py`): BM and EN counselor report templates ported from legacy Streamlit, with counselor personas (Cikgu Venu, Cikgu Gopal, Cikgu Guna)
- **Report API endpoints**: `POST /api/v1/reports/generate/` (generate report), `GET /api/v1/reports/` (list), `GET /api/v1/reports/<id>/` (detail) — all auth-protected
- 12 new tests: format helpers (grades, signals, courses, insights), prompt templates (BM/EN), persona mapping, Gemini mock (success, cascade fallback, missing API key)

### Changed
- Report views wired up (previously stubs returning "coming soon")
- Reports URL config updated with list endpoint

## [1.11.0] - 2026-02-18 — Sprint 10: Deterministic Insights

### Added
- **Insights engine** (`insights_engine.py`): Pure function that generates structured summaries from eligibility results — stream breakdown, top fields, level distribution, merit summary, and Malay summary text
- **Insights in eligibility response**: `POST /api/v1/eligibility/check/` now returns an `insights` key alongside `eligible_courses` and `stats`
- **InsightsPanel component** on dashboard: Three-column layout showing top fields (Bidang Teratas), level distribution (Tahap Pengajian), and merit bar chart (Peluang Kemasukan)
- 8 new tests: empty input, stream breakdown, labels, top fields ranking, merit counts, level distribution, summary text
- **KKOM separation**: Kolej Komuniti requirements split into dedicated `kkom_requirements.csv` with `source_type: 'kkom'`

### Changed
- Eligibility API response now includes `insights` object for frontend consumption
- Dashboard displays insights panel between stats cards and quiz CTA
- API types updated with `Insights`, `InsightsStreamItem`, `InsightsFieldItem`, `InsightsLevelItem` interfaces

## [1.10.0] - 2026-02-18 — Sprint 9: Data Gap Filling

### Added
- **TVET course metadata**: 84 TVET courses enriched with names, levels, departments, descriptions, semesters, and WBL flags from `tvet_courses.csv`
- **PISMP course metadata**: 73 PISMP courses enriched with level (Ijazah Sarjana Muda Pendidikan), department, field, semesters (8), and auto-generated Malay descriptions
- **Institution modifiers in DB**: Added `modifiers` JSONField to Institution model — ranking modifiers (urban, cultural_safety_net, etc.) now stored in PostgreSQL instead of loaded from filesystem JSON
- **`audit_data` management command**: Reports data completeness across courses, requirements, institutions, offerings, and tags
- 5 new tests: TVET enrichment, PISMP enrichment, institution modifiers storage

### Fixed
- **Institution modifiers not working on Cloud Run**: Modifiers were read from `data/institutions.json` at startup, but this file isn't in the Docker image. Now loaded from DB via `load_csv_data`.

### Technical Notes
- Migration 0004: adds `modifiers` JSONField (default={}) to Institution
- All 383 courses now have complete metadata (description, level, department, field, frontend_label, semesters)
- `load_csv_data` now runs 9 loaders in sequence: courses → requirements → tvet_metadata → pismp_metadata → institutions → modifiers → links → details → tags

## [1.9.0] - 2026-02-18 — Sprint 8: Course Detail Enhancement

### Added
- **Course offering details** in `/course/[id]` API response — tuition fees, hostel fees, registration fee, monthly/practical allowances, free hostel/meals flags, application hyperlink
- **"Apply" button** on institution cards linking to official application portals (407 courses with hyperlinks)
- **Fee display** on institution cards — tuition, hostel, and registration fees in a clean grid layout
- **Benefit badges** — "Free Hostel", "Free Meals", and "RM{amount}/month" allowance badges on institution cards
- **`load_course_details`** management command method — loads `details.csv` to enrich CourseInstitution rows (TVET: per-institution, Poly/Univ: per-course)
- 5 new backend tests: offering fees, hyperlink, allowances, free badges, empty field handling

### Technical Notes
- No schema migration needed — CourseInstitution model already had fee fields from initial setup
- `details.csv` (407 rows): TVET rows have institution_id (per-institution fees), Poly/Univ rows don't (shared fees across all institutions)
- Golden master unchanged at 8280 (no engine changes)

## [1.8.0] - 2026-02-18 — Sprint 7: PISMP Integration

### Added
- **73 PISMP (teacher training) courses** integrated into eligibility engine — new `source_type: 'pismp'`
- **PISMP data file** (`data/pismp_requirements.csv`) — cleaned and formatted from draft
- **"Teacher Training" filter** in dashboard dropdown and stat card
- **Amber badge styling** for PISMP courses (`bg-amber-100 text-amber-700`)
- 8 new backend tests: eligibility, exclusion, borderline, subject-specific, Malaysian-only, stats, merit labels, subject requirements
- Django migration `0003_add_pismp_source_type`

### Fixed
- **Empty subjects bug** in `check_subject_group_logic`: rules with `subjects: []` (meaning "any N subjects at grade X") were silently skipped. Now counts from all student grades. Critical for PISMP's "5 Cemerlang from any subjects" requirement.
- **NaN guard** in `check_subject_group_logic` and `check_complex_requirements`: non-string input (NaN from DataFrame concat) no longer crashes the engine

### Technical Notes
- Golden master unchanged at 8280 (PISMP data is additive, no existing courses affected)
- PISMP courses have no `merit_cutoff` — merit labels are `null` (same as TVET)
- `age_limit` field in PISMP data not implemented (not in student profile) — documented as future enhancement

## [1.7.0] - 2026-02-17 — Sprint 6: Dashboard Redesign (Card Grid)

### Added
- **Merit traffic lights** on course cards: Green (High Chance), amber (Fair Chance), red (Low Chance) indicators based on student merit vs course cutoff
- **Student merit calculation** in eligibility endpoint: Computes merit score from SPM grades using UPU-style formula, returns `merit_label`, `merit_color`, `student_merit` per course
- **CourseCard component** (`components/CourseCard.tsx`): Extracted reusable vertical card with field image header, merit indicator, rank badge, and fit reason tags
- 2 new backend tests for merit labels in eligibility response

### Changed
- **Dashboard layout**: Responsive card grid (3 col desktop, 2 tablet, 1 mobile) replaces single-column list
- **Card design**: Vertical layout with field image on top instead of horizontal flex
- Low merit courses (`merit_label === 'Low'`) rendered with reduced opacity
- TVET courses show no merit indicator (no cutoff data)
- Dashboard reduced from ~764 to ~370 lines by extracting CourseCard and FilterDropdown

### Fixed
- **Ranking merit penalty** now works correctly: `student_merit` included in eligibility response flows through to ranking API (previously defaulted to 0)
- Grade key mismatch: `prepare_merit_inputs` expects `'history'`, serializer produces `'hist'` — adapted in eligibility view

### Technical Notes
- Backend tests: 106 (+2) | Golden master: 8280 (unchanged)
- New files: `src/components/CourseCard.tsx` | Modified: `views.py`, `test_api.py`, `api.ts`, `dashboard/page.tsx`
- CoQ (co-curricular quality) score defaults to 5.0 — future enhancement to ask user

## [1.6.0] - 2026-02-17 — Sprint 5: Quiz Frontend

### Added
- **Quiz page** (`/quiz`): Interactive 6-question quiz with step-by-step navigation, progress bar, and auto-advance on selection
- **Quiz API integration** (`lib/api.ts`): `getQuizQuestions()`, `submitQuiz()`, `getRankedResults()` functions with TypeScript types
- **Take Quiz CTA** on dashboard: Prominent gradient banner inviting users to personalise their rankings
- **Ranked results view** on dashboard: Top 5 matches with rank badges and fit reason tags, plus "Other Eligible Courses" section
- **Quiz state management**: Signals stored in localStorage; retake quiz option clears and resets
- **Quiz completed banner**: Green confirmation with retake link when quiz has been completed

### Changed
- Dashboard dynamically switches between flat eligibility list (no quiz) and ranked results (after quiz)
- Dashboard subtitle updates based on whether quiz has been taken

### Technical Notes
- Frontend-only sprint — no backend changes, no migrations
- Backend tests: 104 (unchanged) | Golden master: 8280 (unchanged)
- New files: `src/app/quiz/page.tsx` | Modified: `src/lib/api.ts`, `src/app/dashboard/page.tsx`
- Quiz signals persisted in `halatuju_quiz_signals` localStorage key
- Ranking query uses React Query with eligibility + signals as combined query key

## [1.5.0] - 2026-02-17 — Sprint 4: Ranking Engine Backend

### Added
- **Ranking engine** (`apps/courses/ranking_engine.py`): Ported 551-line Streamlit ranking engine to Django — pure functions, no globals, no file I/O
- **Ranking endpoint** (`POST /api/v1/ranking/`): Accepts eligible courses + student signals, returns top 5 + rest with fit scores and natural language reasons
- **RankingRequestSerializer**: Validates eligible_courses (each must have course_id) and student_signals
- **Institution data loading**: AppConfig now loads course tags map, institution subcategories, and institution modifiers (from JSON) at startup
- **Ranking tests** (`test_ranking.py`): 34 new tests covering score calculation, category/institution/global cap enforcement, merit penalty (High/Fair/Low), sort tie-breaking (5 levels), credential priority, top_5/rest split, API endpoint validation

### Technical Notes
- Test count: 70 → 104 (+34 ranking tests)
- Golden master: 8280 (unchanged)
- No migrations, no deploy (backend only)
- Ranking engine uses dependency injection — course tags and institution data passed as parameters, not loaded from files
- Institution modifiers (urban, cultural_safety_net) loaded from `data/institutions.json` at startup; future sprint will migrate to model fields

## [1.4.0] - 2026-02-16 — Sprint 3: Quiz API Backend

### Added
- **Quiz data module** (`apps/courses/quiz_data.py`): 6 psychometric questions in 3 languages (EN, BM, TA), ported from `src/quiz_data.py`
- **Quiz engine** (`apps/courses/quiz_engine.py`): Stateless signal accumulator — takes answers in, returns categorised signals in 5-bucket taxonomy
- **Quiz questions endpoint** (`GET /api/v1/quiz/questions/?lang=en`): Returns quiz questions in requested language, public (no auth)
- **Quiz submit endpoint** (`POST /api/v1/quiz/submit/`): Accepts 6 answers, returns `student_signals` + `signal_strength`, public (no auth)
- **Quiz tests** (`test_quiz.py`): 14 new tests covering endpoint behaviour, signal accumulation, taxonomy mapping, validation, and language parity

### Technical Notes
- Test count: 56 → 70 (+14 quiz tests)
- Golden master: 8280 (unchanged)
- No migrations, no deploy (backend only)
- `ProfileView.put()` already accepts `student_signals` — no change needed
- Quiz engine is fully stateless: no session, no DB writes. Frontend sends all 6 answers in one POST.

## [1.3.0] - 2026-02-16 — Sprint 2: Saved Courses Fix + Page Shells

### Added
- **Saved courses page** (`/saved`): Lists saved courses from API, remove button, login prompt for guests
- **Settings page** (`/settings`): Links to edit grades, saved courses, about, privacy, terms
- **About page** (`/about`): Project description and mission
- **Privacy policy page** (`/privacy`): Data collection, usage, and storage disclosure
- **Terms of service page** (`/terms`): Disclaimer and liability
- **Auth callback page** (`/auth/callback`): Handles OAuth redirect from Supabase, redirects to dashboard
- **Saved course CRUD tests**: 3 new tests covering save (201), list (appears), and delete (removed) (`test_saved_courses.py`)
- **Bookmark button on dashboard**: Logged-in users see a save/unsave bookmark icon on each course card with optimistic updates

### Fixed
- **`unsaveCourse` API call**: Changed from body-based DELETE (`/api/v1/saved-courses/` + body) to URL-based DELETE (`/api/v1/saved-courses/<course_id>/`) matching the backend route
- **`getSavedCourses` return type**: Updated from `string[]` to `Course[]` to match actual backend response

### Changed
- **Dashboard CourseCard**: Refactored from single `<Link>` wrapper to `<div>` with separate link area and save button, so save/click targets are independent
- **Dashboard saved state**: Now fetches from Supabase API when session exists (was not wired at all)

### Technical Notes
- Test count: 53 → 56 (+3 saved course CRUD tests)
- Golden master: 8280 (unchanged)
- TypeScript: 0 errors
- Frontend deployed: revision `halatuju-web-00007-wd8`

## [1.2.0] - 2026-02-16 — Sprint 1: Git Housekeeping + Auth Enforcement

### Added
- **Sprint roadmap**: 15-sprint migration plan across 4 phases (`docs/roadmap/sprint-roadmap-v1.x.md`)
- **DRF permission class**: `SupabaseIsAuthenticated` for class-based views (`halatuju/middleware/supabase_auth.py`)
- **Auth enforcement**: `SavedCoursesView`, `SavedCourseDetailView`, `ProfileView` now require valid Supabase JWT
- **Auth tests**: 11 new tests covering protected endpoint rejection (403), authenticated access (200), and public endpoint openness (`test_auth.py`)
- **Git tracking**: All project code (`halatuju_api/`, `halatuju-web/`, `tools/`) now under version control
- **`.gitignore`**: Covers Node.js (`node_modules/`, `.next/`), Django (`*.sqlite3`, `staticfiles/`), and temp files (`.tmp/`)

### Changed
- **Protected views**: Replaced manual `if not request.user_id` checks with `permission_classes = [SupabaseIsAuthenticated]`
- **Migration 0002**: Renames `student_profiles` table to `api_student_profiles` (matching model's `db_table`), adds missing fields (`credit_math_or_addmath`, `credit_sci`, `credit_science_group`, `pass_sci`)

### Fixed
- **Table mismatch**: `StudentProfile.Meta.db_table = 'api_student_profiles'` didn't match migration 0001's `student_profiles` — generated migration 0002 to correct this

### Technical Notes
- DRF returns 403 (not 401) for unauthenticated requests when no `WWW-Authenticate` header is configured — this is expected behaviour
- Test count: 42 → 53 (+11 auth tests)
- Golden master: 8280 (unchanged)

## [1.1.0] - 2026-02-04

### 🎓 Major Feature: University Course Integration

Added comprehensive support for 87 Malaysian public university (IPTA) Asasi and Foundation programs across 20 institutions.

### ✨ New Features

#### Data Layer
-   **New Data Files**:
    -   `data/university_requirements.csv` - 87 university course eligibility rules
    -   `data/university_courses.csv` - Course metadata (department, field, frontend_label)
    -   `data/university_institutions.csv` - 20 IPTA universities with constituency data
-   **Course Catalog Expansion**: 727 → 814 courses (+12% growth)

#### Eligibility Engine (`src/engine.py`)
-   **Grade B Requirements**: New tier stricter than Credit C (Grade B or better)
    -   `credit_bm_b`, `credit_eng_b`, `credit_math_b`, `credit_addmath_b`
-   **Distinction Requirements**: Grade A- or better
    -   `distinction_bm`, `distinction_eng`, `distinction_math`, `distinction_addmath`
    -   `distinction_bio`, `distinction_phy`, `distinction_chem`, `distinction_sci`
-   **Complex OR-Group Logic**: JSON-based multi-subject requirements
    -   Example: "Need 2 subjects with Grade B from [Physics, Chemistry, Biology]"
    -   Supports AND logic between groups, OR logic within groups
-   **Pendidikan Islam/Moral Support**: `pass_islam`, `credit_islam`, `pass_moral`, `credit_moral`
-   **Additional Science Requirements**: `pass_sci`, `credit_sci`, `credit_addmath`

#### UI Updates (`main.py`, `src/dashboard.py`, `src/translations.py`)
-   **Institution Filter**: Added "Public University" (Universiti Awam) option
-   **Dashboard Metrics**: Expanded from 4 to 5 columns to include UA course count
-   **Translations**: Added `inst_ua` key in English/Bahasa Melayu/Tamil
-   **Grade Input**: Added "Pendidikan Islam" and "Pendidikan Moral" to Other Subjects dropdown

#### Data Manager (`src/data_manager.py`)
-   **University Data Merging**:
    -   Extracts course name and institution from `notes` column
    -   Merges with institution metadata for state/URL
    -   Maps to consistent type naming: "Universiti Awam"
-   **Type Standardization**: All institution types now use Bahasa Melayu for filter compatibility

### 🧪 Testing

-   **Golden Master Test Expansion** (`tests/test_golden_master.py`):
    -   Added 8 new student profiles (43-50) for UA requirement testing
    -   Grade B testing, Distinction testing, Complex OR-group testing
    -   Updated baseline: 5,318 → 8,280 eligible matches (+2,962)
    -   Test coverage: 50 students × 407 courses = 20,350 checks
-   **University Integration Tests** (`test_university_integration.py`):
    -   Data loading verification
    -   Eligibility engine testing with strong/weak students
    -   Complex requirements JSON parsing

### 🐛 Bug Fixes

-   **NaN Handling**: Fixed AttributeError in `check_complex_requirements()` when pandas passes NaN as float type
-   **Type Consistency**: Changed UA type from 'UA' to 'Universiti Awam' for UI compatibility
-   **Windows Console**: Removed Unicode emojis from test output for cp1252 encoding compatibility

### 📝 Documentation

-   **README.md**: Updated course catalog numbers and feature descriptions
-   **DATA_DICTIONARY.md**: Documented all 20+ new UA requirement columns and complex_requirements JSON format
-   **docs/university_integration_complete.md**: Comprehensive implementation summary

### ⚙️ Technical

-   **Engine Functions**:
    -   `is_credit_b(grade)` - Checks if grade is B or better
    -   `is_distinction(grade)` - Checks if grade is A- or better
    -   `check_complex_requirements(grades, json_str)` - Evaluates OR-group logic
    -   `map_subject_code(code)` - Maps 60+ SPM subjects to internal keys
-   **Performance**: No noticeable impact despite 12% course increase (~140KB additional data)

### 🔄 Backward Compatibility

-   All changes fully backward compatible with existing Poly/KK/TVET courses
-   New requirement columns default to 0 (not required)
-   Existing eligibility logic unchanged

## [1.0.0] - 2026-01-24

### 🚀 Initial Release
First official stable release of **HalaTuju**, the SPM Leaver Course Recommender.

### ✨ Key Features
-   **Eligibility Engine**: 
    -   Exact matching against General and Specific requirements for Polytechnics, Community Colleges, ILKBS, and ILJTM.
    -   Support for gender-specific, physically demanding, and interview-based course rules.
-   **Ranking System**: 
    -   Weighted scoring based on Student Interest (RIASEC), Work Preferences (Hands-on vs Theory), and Learning Styles.
    -   Tie-breaking logic using Credential Priority (Diploma > Certificate) and Institution Tier functionality.
-   **Dashboard**:
    -   Interactive filtering and "Tiered" display (Top 5 Matches vs Rest).
    -   Visual indicators for specific requirements (Medical checks, Interviews).
-   **Reports**:
    -   AI-generated personalized career pathway reports (Gemini Pro + OpenAI Fallback).
    -   PDF export functionality.
-   **Localization**: Full English, Malay, and Tamil language support.

### 🐛 Key Fixes & Stability
-   **Gender Logic**: Fixed regression where engine hardcoded Malay gender terms, causing rejection of eligible students using English/Tamil UI.
-   **Data Integerity**: Implemented a "Golden Master" regression test suite (`tests/test_golden_master.py`) achieving 100% integrity on 13,000+ test cases.
-   **Cleanup**: Removed unused dependency `match_jobs_rag` and unused `InsightGenerator`, consolidated imports, and verified no hardcoded secrets exist.

### ⚙️ Technical
-   **Stack**: Streamlit, Pandas, Supabase (Auth/DB), Google Gemini.
-   **Testing**: Automated Golden Master testing for the engine.
