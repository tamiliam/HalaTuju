# Code Health Review — 2026-07-03

Full-codebase audit run 2026-07-02/03: seven parallel review passes over the domain
engines, API surface + permissions, document pipeline, models/services/comms, the
Next.js frontend, courses/reports/settings/scripts, and (separately) the 67 newest
commits on `origin/main` (QC gate, income model 2A–2C, STR-proof, signing chain).

**All findings below were checked against `origin/main`** (what production runs).
Items marked ✅ VERIFIED were re-confirmed by direct code read after the review pass.
Nothing has been fixed yet — this is the triage list.

> Housekeeping: at review time the local checkout (`feature/doc-eval-harness`) was
> 67 commits behind `origin/main`. Pull before fixing anything.

---

## P0 — urgent

### 1. Real student PII committed to GitHub ✅ VERIFIED
- **File:** `halatuju_api/docs/backups/student_profiles_legacy_backup_2026-06-01.json`
- 30-row dump of the legacy `student_profiles` table: real names, parent emails
  (rkumaravalu@…, kkvguna@…, etc.), phone numbers, addresses, grades, AI reports and
  `pin_hash` values. Tracked and pushed (commit `dc7a6277`).
- **Impact:** anyone with repo access holds identifiable student/parent contact data +
  PIN hashes. Breaches the workspace Secrets Policy and PDPA posture.
- **Fix:** delete AND rewrite history (`git filter-repo`), force-push, rotate anything
  derivable. Deleting the file alone does not remove it from history.

---

## P1 — high-stakes correctness bugs (small fixes)

### 2. "Cancel decline" doesn't cancel — student silently sees the rejection ✅ VERIFIED
- **File:** `halatuju_api/apps/scholarship/services.py:848` (`cancel_pending_decline`)
- The status-restore branch requires `decision_email_sent_at is None`, but
  `release_decision` (services.py:312) already stamped that field when the **shortlist
  invitation** email went out — true for every normally-processed applicant. So cancel
  clears the embargo markers (mask lifts, student sees `rejected` in-app), status stays
  `rejected`, no decline email is ever sent, admin believes it was undone.
- `test_decision_cooloff.py:69` passes only because its fixture never went through
  `release_decision`.
- **Companion bug (same function, line 849):** when the restore branch *does* run it
  restores to `'interviewed'`, which post-QC-gate means AWAITING QC. A decline made from
  `shortlisted`/`profile_complete`/`interviewing` and then cancelled lands a verdict-less
  case in the QC queue; QC-Accept flips it to `recommended` with **no verdict recorded**,
  and QC-Reopen 400s (`not_decided`). Introduced by the meaning change in `9b8a65b4`.
- **Fix:** give the decline embargo its own email stamp (stop reusing
  `decision_email_sent_at`), and snapshot the pre-decline status at `admin_reject` so
  cancel restores to it.

### 3. YTD÷12 with the monthly cell unread → income understated up to 12× ✅ VERIFIED
- **File:** `halatuju_api/apps/scholarship/income_engine.py:647` (`_salary_monthly_amount`)
- `if month is None or annualised >= month: return annualised` — when OCR reads
  `gross_income_ytd` but misses both monthly cells, a January slip's YTD (≈1 month of
  pay) is divided by 12. RM3,800/mo → RM317/mo → household of 4 → per-capita RM79 →
  salary route can reach **verified green** on the B40 gate.
- No test covers month=None + YTD (only prefer-YTD and no-deflate cases are pinned).
- **Fix:** when `month is None`, treat YTD as unusable (return None → verify at
  interview) or require a months-elapsed denominator.

### 4. ~25 SPM subjects on the web form are unknown to the academic engine ✅ VERIFIED
- **File:** `halatuju_api/apps/scholarship/academic_engine.py:29` (`_SUBJECT_BM`) and
  `:130` (`_KNOWN_SUBJECTS`) vs `halatuju-web/src/lib/subjects.ts`
- Missing: all arts/performance electives (`reka_bentuk_grafik`, `seni_halus_2d/3d`,
  `tarian`, `lakonan`, `alat_muzik`, `aural_teori_muzik`, `koreografi`, `sinografi`,
  `penulisan_skrip`, `produksi_seni`, `multimedia_kreatif`, `muzik_komputer`,
  `apresiasi_tari`, `reka_bentuk_industri/kraf`), all `voc_*` vocational subjects, and
  the Islamic-stream extras (`tasawwur_islam`, `usul_aldin`, `al_syariah`, etc.).
- **Impact:** a student who takes one and enters their grade is told the subject is
  "missing" and to add it on the Profile page — which they already did. Unfixable loop;
  their academic check can never reach `verified`; permanent reviewer amber.
- **Fix:** sync the two lists; add a drift test (backend list ⊇ web list).

### 5. Re-extraction can still destroy good `vision_fields` — no clobber guard ✅ VERIFIED
- **Files:** `halatuju_api/apps/scholarship/vision.py:1666` (unconditional
  `doc.vision_fields = result`), `reextract.py:24-36`,
  `management/commands/reextract_documents.py:74-82`
- The known incident mode (`halatuju_never_reextract_locally` memory): a re-run without
  Storage access reads "no text" and overwrites good extractions. Still purely
  procedural. Aggravators: the bulk command stamps failed docs as done (never revisited);
  cockpit Re-run omits the profile street so an identical bill can flip from `found` to
  `address_mismatch` (raising a false `utility_address_mismatch` query);
  `read_text_document` and `run_vision_match_for_document` have the same wipe-on-failure
  class.
- **Fix:** refuse to replace non-empty fields with an empty/error result; pass `street`
  through `reextract_document`; don't stamp PASS on exception.

---

## P2 — money, awards, comms

### 6. Contractual reject of a funded student strands the sponsorship + ledger
- **File:** `halatuju_api/apps/scholarship/services.py:795` (`admin_reject`)
- `'contractual'` is allowed from `active`/`maintenance` but nothing lapses the funding
  `Sponsorship` (stays HOLDING) or touches the disbursement ledger. Sponsor balance is
  reduced forever; `sponsor_impact`/`sponsor_statement` keep reporting the rejected
  student as supported. Intended path is closure.py, but this path is exposed at
  `views_admin.py` with no guard.
- **Fix:** lapse any HOLDING sponsorship inside `admin_reject` for post-award
  categories, or block contractual reject from funded states and route to closure.

### 7. Failed award-offer email is permanently suppressed
- **File:** `halatuju_api/apps/scholarship/management/commands/send_award_offer_emails.py:49-53`
- Stamps `offer_emailed_at` unconditionally, even when the send failed / notify_email is
  blank; the hourly cron filters `offer_emailed_at__isnull=True`, so the student never
  gets the good-news email. (Same stamp-on-failure pattern, deliberate but silent, in
  `sponsorship.py:175`.)
- **Fix:** stamp only on success; log/record failures somewhere visible.

### 8. Migration 0082 has no backfill → first cron tick can blast historical awards
- **Files:** `0082_sponsorship_offer_emailed_at.py` + `sponsorship.py:155-179`
- Every pre-existing HOLDING sponsorship has NULL `offer_emailed_at` older than 24h and
  qualifies on the first scheduled run — including awards deliberately embargoed under
  the old OFF-gate. Relies on an unenforced manual backfill (the duplicate-blast lesson
  from SJKTConnect applies).
- **Fix:** data-migrate a stamp for pre-existing rows (or gate the cron until backfilled).

### 9. Bank-details save: unmapped field error = dead-end for the student
- **Files:** `halatuju-web/src/components/ActionCentre.tsx:400-408` vs
  `halatuju_api/apps/scholarship/serializers.py` (account_number ≥5 digits)
- FE maps only `bank_holder_mismatch`; a short account number returns a DRF **field**
  error (no top-level code) → generic "couldn't save, try again" with no hint. High-
  stakes field (payout account). FE also has no digit-length check of its own.
- **Fix:** map DRF field errors (or add client-side digit validation to match the API).

### 10. Comprehension quiz contradicts the actual bursary agreement (DARK)
- **Files:** `halatuju-web/src/lib/awardComprehension.ts:116-147` vs
  `halatuju_api/apps/scholarship/bursary.py:95-113`
- Quiz teaches "3.0 CGPA or discontinued", "notify within 7 days", "no upload →
  suspension", "exact programme only"; the agreement says review-not-automatic-
  suspension, "reasonable time", and has no CGPA figure or upload clause.
  `comprehension_passed_at` is recorded "for defensibility" — proving the student
  understood *different* terms is a liability. Nothing forces reconciliation before
  `BURSARY_AGREEMENT_ENABLED` flips.
- **Fix:** rewrite quiz content from bursary.py clauses (its own header says lockstep).

### 11. `send_sign_invitation_emails` not gated by `BURSARY_AGREEMENT_ENABLED`
- **File:** `halatuju_api/apps/scholarship/management/commands/send_sign_invitation_emails.py`
- Unlike `send_bursary_signing_reminders` (no-ops when off), this sends "your agreement
  is ready to sign — open your Action Centre" regardless of the flag → students emailed
  into a dead end while the chain is dark. Also coupled to `AWARD_ACCEPTANCE_ENABLED`.
- **Fix:** mirror the reminder command's flag guard.

### 12. WhatsApp go-live will be opt-OUT, not opt-in (decision needed)
- `StudentProfile.whatsapp_opt_in` defaults **True** (courses/models.py:514) and
  whatsapp.py:12 notes there is no per-recipient consent gate. Channel is correctly dark
  today (flag + creds all required), but the moment `WHATSAPP_ENABLED=1` every applicant
  with a phone is messageable by default. Decide consent model before owner go-live.

---

## P2 — income/STR model consistency (STR-proof commits `8b4686b1`/`97b59918`/`7a7586e7`)

### 13. State rename missed three consumers (`wrong_type`/`unreadable`)
- `income_engine.py:1277,1290` — student cluster coach checks
  `('stale','rejected','unconfirmed')` → **silent** on the two worst failure states
  (officer verdict correctly reds them; student gets no nudge).
- `resolution.py:296` — re-upload state check treats only `('rejected','stale')` as
  mismatch → a SARA letter re-uploaded over a SALINAN **auto-resolves** the
  `str_not_current` ticket while the verdict still fails it.
- `services.py:1617` — submission blocker: `rejected`/`stale` blocks, equally-red
  `wrong_type` doesn't.
- **Fix:** one shared "red STR states" tuple used by all consumers.

### 14. Salary-route B40 test contradicts the STR route's headroom rule
- **File:** `verdict_engine.py:551-560` (I4)
- Tests only `pc < per_capita_ceiling`; ignores the gross ceiling (spec §7: B40 holds
  while gross ≤ RM5,860 OR per-capita ≤ RM1,584). Household of 3, gross RM5,400 →
  salary route says "over the line", STR fall-through says B40 holds. Boundary also off:
  pc exactly RM1,584 → "over" (strict <) vs headroom's breach_room=0 → not over.
- **Fix:** route I4 through `income_headroom` (single source of truth).

### 15. Legacy untagged docs satisfy BOTH parents' evidence check
- **File:** `income_engine.py:1269` (`_parent_has_income_evidence` via `_cluster_docs`)
- A blank-tagged (`household_member=''`) pre-TD-115 salary slip matches
  `household_member__in=[member,'']` for **any** member → suppresses the
  `mother_income_proof_missing` query the S1 feature exists to raise.

### 16. `profile_engine._income_evidence` still uses `working_members()`
- **File:** `profile_engine.py:389`
- Everything else was fixed (#90) to `effective_working_members()`; this call site was
  missed → sponsor/reviewer profile says "Documented income: none on file" when a tagged
  readable payslip exists (the #10 "documented income buried" class resurfacing).

### 17. Verdict engine and student checklist can pick different ICs for the same earner
- **File:** `verdict_engine.py:291` (STR route uses member-agnostic
  `_latest_doc(app,'parent_ic')`) vs `income_engine._member_ic_doc` (member-filtered)
- After a route switch with multiple parent ICs on file, verdict shows
  `birth_cert_mismatch` while the student checklist is all green — breaks the
  "can never disagree" contract, creates a false reviewer flag.

### 18. Wrong-document blame while an IC OCR is pending
- **File:** `income_engine.py:1183` (`income_cluster_advice`)
- IC with `vision_run_at` NULL (known transient state; self-heal cron exists) + processed
  BC → returns `income_rel_doc_unreadable` → Gopal tells the student to re-upload their
  perfectly fine birth certificate, and it becomes an `income_document_unreadable`
  submission blocker.

### 19. STR fall-through headroom counts only the single earner
- **File:** `verdict_engine.py:387` — `income_headroom(application, [earner])` excludes
  other members' payslips/EPF/declared income → gross understated → 'probable' (blue)
  for a genuinely-over household. Low likelihood today (wizard captures one earner).

### 20. `declared_unproven` checked after `if review: return`
- **File:** `verdict_engine.py:534-541` — unproven declared income can hide behind an
  unrelated review state; Check-2 doc request still fires via `declared_income_gaps`,
  so impact is the tile copy only.

---

## P2 — infrastructure & cost

### 21. No `CACHES` configured — all rate limits are per-process in-memory ✅ VERIFIED
- No `CACHES` anywhere in `halatuju/settings/` → Django LocMemCache: per gunicorn
  worker, per Cloud Run instance, wiped on every cold start.
- Affects: `upload: 40/hour` (each upload = billable Vision call), `anon: 1000/min`
  (base.py:105-112), and 3 AI reports/day (reports/views.py:52-57, which also has a
  get-then-set race).
- **Fix:** database cache table (free) or Upstash/Memorystore Redis; point throttles at it.

### 22. Two identical billable Vision calls per slip/BC upload
- **File:** `vision.py:1509+1543` (vs upload path views.py:706)
- Upload runs `ocr_document` (download + `DOCUMENT_TEXT_DETECTION`), then
  `run_field_extraction_for_document` downloads the same blob again and calls
  `_vision_words` — the **same API method**, whose one response contains both
  `full_text_annotation` and `text_annotations`. Offer-letter branch duplicates the
  download; STR genuineness downloads a third copy even when not needed.
- **Fix:** share the single Vision response (and bytes) between the two consumers.

### 23. `validate_course_urls --fix` erases URLs on a transient 5xx
- **File:** `apps/courses/management/commands/validate_course_urls.py:76,259-264`
- Any non-401/403 HTTPError (incl. 500/502/503) is classified 'dead'; 5xx is NOT in the
  retry set; `--fix` blanks `Institution.url`/`CourseInstitution.hyperlink` with no
  backup, dry-run diff, or cap. A MY-gov portal in maintenance = permanent URL loss.
- **Fix:** treat 5xx as retryable/unknown, never as dead; add the mass-change guard the
  sync commands already have.

---

## P3 — smaller items (grouped)

**QC-gate polish** (`9b8a65b4`/`1cf1108f`)
- Cockpit **list** still labels `interviewed` as "Interviewed" (old meaning); the
  "Awaiting QC" relabel landed only on the detail page
  (`halatuju-web/src/app/admin/scholarship/page.tsx:58`).
- Decision panel still active at awaiting-QC — a reviewer can silently amend a verdict
  already in the QC queue (`[id]/page.tsx:2152`; backend accepts verify-accept from
  `interviewed`).
- Self-QC guard keys on **current assignment**, not verdict author
  (`views_admin.py:77`): a super reassignment lets a senior-qc QC their own verdict;
  conversely a newly-assigned qc is wrongly blocked. Key on
  `verified_by`/`verdict_decided_by` instead.
- `AdminPublishAnonProfileView` still sets `anon_published=True` with no status check —
  currently harmless (all read surfaces hard-require `recommended`) but worth a guard.

**Parsers / document pipeline (officer-display severity)**
- `pathway_engine.py:275` `parse_reporting_date`: dash/ampersand ranges resolve to the
  **last** day ("8 - 9 JUN" → 9th; `hingga` form is handled); and the day-extraction
  regex lacks word boundaries, so legacy un-normalised strings ("SESI 2026/2027 JUN")
  can fabricate a day instead of deferring.
- `bc_parse.py:23` / `doc_parse.py:364`: unanchored NRIC regex reads the first 12 digits
  of a longer serial/barcode run as an NRIC → false amber on genuine certs.
- `doc_parse.py:171`: any "salinan" occurrence (e.g. a "Salinan kepada:" CC block on a
  genuine MOF letter) downgrades to `unknown` before letter classification.
- `doc_parse.py:150-162`: `_largest_amount` can report the SARA total as the STR amount.
- `income_engine.py:546-549`: reject-word check runs before the format gate — a non-STR
  containing "tolak/gagal" reads `rejected` (wrong officer copy) instead of `wrong_type`.
- `verdict_engine.py:437-440`: guardian letter/IC clash reported as
  `father_patronymic_mismatch` (wrong cause label).
- `anomaly_engine.py:285-316`: both S17 consent detectors read the single **latest**
  `parent_ic` regardless of `household_member` → false flags in multi-earner households.
- `income_engine.py:1619-1626` (`_member_occupation`): only the first
  `other_family_members` entry per role is read (second working brother invisible).
- `bc_parse.py:85-89`: tokens containing '/' are rejected, so 'A/L'/'A/P' markers are
  dropped from the reconstructed display name (verdict unaffected).
- `views.py:757`: `uncertain` checks `address_match in ('not_found','unreadable')` —
  values it never produces; harmless today (`force=True`), landmine if the env knob flips.

**Misc backend**
- `services.py:1716` `age_from_nric` uses `date.today()` (UTC) not
  `timezone.localdate()` — student is "17" until 08:00 MYT on their 18th birthday
  (conservative direction only).
- `refresh_sponsor_profiles` silently reverts published profiles to draft
  (`services.py:704-705`); cockpit-state impact only, but a fleet-wide prompt roll
  requires manual re-publishing.
- `release_pending_declines` clears markers before sending — a failed decline email is
  dropped permanently (deliberate anti-double-send; consequence worth recording).
- Production settings: no HSTS (`SECURE_HSTS_SECONDS` unset). Everything else clean.
- `apps/courses/views_admin.py:138-145`: partner dashboard loads the entire
  StudentProfile table (all columns) to count one JSON field — use `.only()`/aggregate.
- `scripts/migrate_to_supabase.py:171`: requirements upsert updates only `source_type`
  on conflict (legacy one-shot; only matters if reused).
- `bursary_e2e --keep` against prod DB would commit a live `role='super'` PartnerAdmin.
  Documented local-only; nothing enforces it.
- Inconsistent write-safety defaults: `standardise_stpm_institution` is dry-run by
  default; `align_institution_to_catalogue` / `standardise_pre_u_course` write by default.
- Eval harness `eval_doc_recognition.py:245` passes a `force` kwarg
  `run_field_extraction_for_document` doesn't accept → `--rerun-vision` TypeErrors for
  all supporting-doc fixtures (broken since creation; tooling only).
- Per-request recomputation: `chain_verified_earner` (~3-4 queries) re-run dozens of
  times per application render across the checklist/verdict engines — memoise per
  request if cockpit latency matters.

**Misc frontend**
- `ScholarshipBanner.tsx:29` keys on retired `accepted` status — dead branch; awarded
  students get no dashboard nudge.
- Award slider: fixed-value RM2,000 override can't be selected without dragging away and
  back; every drag step fires a PATCH (`[id]/page.tsx:2036-2064`).
- `api.ts:1900` missing trailing slash on `resolution-items` → 301 on every Action
  Centre fetch (hottest post-submit page).

---

## Verified as already fixed on `origin/main` (no action)

Flagged during review of the stale local checkout; confirmed resolved upstream:
- Five reviewer IDOR endpoints (anon-profile publish, profile edit/publish, resolution
  actions, referee delete) → now routed through `_require_app_write`/`_can_review_app`
  (commit `6aecf04e` and follow-ups).
- Rejected/withdrawn students leaking into the sponsor pool + standing-gift auto-fund →
  `is_pool_eligible`/`eligible_pool_queryset`/`is_fundable` all hard-require
  `status=='recommended'` (`a42e6488`).
- Bank-details task unreachable for awarded/active students → `showsActionCentre` single
  source of truth; blank "Done" card → `bank_details_missing` added to KNOWN_CODES.

## Confirmed clean (checked, no findings)

Student-endpoint ownership scoping (no IDOR), JWT middleware (alg-pinned), sponsor
serializer allowlists, mass-assignment surfaces, CronRunView, migrations 0069-0087,
QC-gate mechanics (no bypass to `recommended` except item 2's edge), reopen two-step
invertibility, student status masking, Check-2 re-notify wiring, signing-chain dark
gating (except item 11), Check-2 LLM summary gating, i18n parity (en/ms/ta, 3,670 keys
each), no console logging of PII, headroom band edges + worked examples, STR chip
matrices vs spec, MODEL_VERSION discipline (1.1→1.2→1.2.1 all properly bumped),
catalogue sync tooling guards, PISMP taxonomy derivation, reports-app scoping.

---

## Approved fix roadmap (owner-approved 2026-07-03; supersedes the draft order of attack)

- **Task A — PII purge: ✅ DONE 2026-07-03.** History rewritten with `git filter-repo`,
  force-pushed, all local checkouts re-pointed, `.gitignore` guard added. Residue: old
  objects unreachable on GitHub (optional support request) + local reflogs (~90-day expiry).
- **Sprint 1 — Decision & needs-gate integrity: ✅ DONE 2026-07-03.** #2 cancel-decline
  (own `decline_email_sent_at` stamp + `pre_decline_status` snapshot restore, migration
  `0090` migrate-first), #3 YTD-alone guard, #4 subject-map sync (64 keys, not ~25) +
  `test_subject_drift.py`. 3,185 backend tests green. Retro
  `docs/retrospective-2026-07-03-code-health-s1.md`.
- **Sprint 2 — Document-pipeline safety:** #5 vision clobber guard + reextract fixes
  (street pass-through, no PASS-stamp on error) + #22 duplicate Vision call.
- **Sprint 3 — Money & comms:** #6 sponsorship lapse on contractual reject, #7 email
  stamp only on success, #8 offer_emailed_at backfill, #9 FE bank field-error mapping,
  #10 quiz↔agreement reconciliation, #11 sign-invitation flag guard.
- **Sprint 4 — Income/STR consistency:** #13–#20 (shared red-states tuple, I4 via
  headroom helper, member-tag fixes, IC-selector alignment, wrong-doc blame).
- **Sprint 5 — Infra & guardrails:** #21 cache backend for rate limits, #23 URL
  validator 5xx handling + mass-change guard, HSTS, quick P3 wins (QC queue label,
  dead banner branch, trailing slash).
- **Backlog:** remaining P3 → small-change lane. **Open decision (owner):** #12
  WhatsApp opt-in default (currently opt-out-shaped).

Detailed task breakdown happens per-sprint at sprint-start (`sprint-start.md`);
re-plan the remaining sprints at each sprint-close if scope shifts.

**Execution authorisation (owner, 2026-07-03):** Sprints 1–2 run fully autonomous
(sprint-start/close approval gates waived; deploy at each close). One checkpoint
report before Sprint 3, then 3–5 autonomous. Pre-taken owner decisions for Sprint 3:
- #8 backfill: stamp ALL historical awarded students as already-emailed (no surprise
  auto-emails; manual command remains for individual sends).
- #6: contractual reject of a funded student AUTO-LAPSES the sponsorship (mirrors
  closure semantics, releases held balance).
- #10 quiz: rewrite strictly from bursary.py clauses (ta per style guide), ship dark,
  owner reviews copy in the final report before the flag ever flips.
