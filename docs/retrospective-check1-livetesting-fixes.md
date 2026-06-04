# Retrospective — Check-1 live-testing fixes (2026-06-04)

A live-review session on real student records that hardened three of the four verification facts after the
Check-1 arc shipped. All five fixes deployed to prod the same day.

## What Was Built (deployed)
1. **Orientation-robust SPM slip parse** (`c416c2e`). The deterministic positional parser only ran on *upright*
   slips — a sideways/keystoned phone photo clustered into nonsense, fell back to Gemini, and Gemini transposed
   grades (the recurring "Pavalaharasi/Sharmila reads wrong" bug). Fix: capture a per-word baseline angle
   (`_vision_words`) and **de-rotate every centroid by the slip's median angle** before grouping (`_group_rows`),
   **gated** so an upright slip (|θ|<25°) is never perturbed. Verified against **four real slips frozen as fixtures**
   (`tests/fixtures/slips/`): 2 upright (unchanged), 1 rotated-90°, 1 rotated-90°+keystone Type-2. (Diagnostic
   `3ff604b` captured the geometry; full-word capture is now kept only on a fallback slip.)
2. **Pointed, context-aware Gopal slip advice** (`39510ac`). The coach got only a coarse verdict label, so an
   *uncertain* grade (the common "please check") fell through to nothing. Surfaced the photo tilt + the uncertain
   state and added two verdicts: `slip_grade_uncertain` (double-check) and `slip_skewed_unclear` (retake flat) — with
   an **anti-nag rule**: retake advice fires only when skew coincides with a doubtful read (a cleanly-read rotated
   slip gets no coach). Firewall intact.
3. **Officer Academic verdict false "could not be read"** (`d9e683b`). A perfectly-read slip showed both "could not
   be read" *and* "entered 8 of 9 subjects". Fix: stop judging slip readability from `vision_name_match` (the
   supporting-doc/IC column, blank for some slip name spellings) — use the slip's own `_slip_name_status`, the same
   signal the student checklist uses.
4. **Two pathway false flags** (`e80b60c`). (a) A Form-6/STPM offer false-clashed with the declared pathway because
   the offer "programme" reads the enrolment *type* ("Tingkatan Enam Semester 1") not the field — added enrolment-
   structure words to `_GENERIC_TOKENS` so a type-only programme can't clash; institution carries it to a match.
   (b) A general notice with no name/IC was mislabelled `offer_unreadable` ("ask for a clearer copy") — new
   `offer_no_identity` reason for "readable body, no identity on it".
5. **Reason-code chain completeness** (`e3d93c9`). `offer_no_identity` rendered a raw i18n key in the student Action
   Centre because it wasn't added to `actionCentre.KNOWN_CODES` (the 4th wiring point).

## What Went Well
- The **fixture-based** slip fix ended the deploy-and-pray loop: one capture → freeze 4 real slips → fix against all
  four locally → deploy once, correct.
- All verdicts recompute per request, so three of the fixes needed **no re-OCR** — the deploy alone corrected the tiles.
- Every fix shipped with a regression test pinned to the exact real-student case (Sharvani, Divashini, Sharvin).

## What Went Wrong
1. **Slip-parser whack-a-mole before the reset.** *Symptom:* rotation/orphan-gate/split-merge each fixed one slip and
   broke another (incl. upright Theepicaa); reset to `f507c83`. *Root cause:* iterating against the live UI with no
   real-data fixtures — every change was a guess validated only by deploying. *Fix:* the capture-then-fixture
   discipline is now the standing rule (lesson added); a slip-parser change ships only when all four real fixtures pass.
2. **`offer_no_identity` showed a raw key.** *Symptom:* the student Action Centre rendered
   `admin.scholarship.verdict.item.offer_no_identity` verbatim. *Root cause:* a new verdict reason code must be wired
   in **four** places (verdict_engine → `CODE_TO_TICKET` → officer i18n → student `actionCentre` i18n + `KNOWN_CODES`);
   only three were done. *Fix:* the four-link checklist is now in `lessons.md` + `memory`.
3. **Wrong column used as a readability signal.** *Symptom:* a clean slip flagged "could not be read" for one student.
   *Root cause:* `vision_name_match` (a supporting-doc/IC heuristic column) was reused to judge a *results slip*, where
   it isn't reliably populated. *Fix:* use each document's own authoritative status; lesson added.

## Design Decisions
- **Gated de-rotation** (only de-rotate when |median angle| ≥ 25°) — an earlier "always de-rotate by the measured
  angle" perturbed upright slips via OCR angle-noise. See `decisions.md`.
- **Band-authoritative kept on a keystone-truncated band** — a bare "Cemerlang" beside a printed "A" reads A- and
  downstream becomes "please check" (safe), rather than re-trusting the OCR-unreliable +/- letter.

## Numbers
- 5 commits, all deployed (+ 1 capture diagnostic + 1 revert). **~609 scholarship pytest + 231 jest** at sprint end
  (deployed); courses/reports unchanged (1037). 4 real-slip fixtures added. No migration. i18n 1853×3.
- Income Check-1 **I1 backend** (income_engine + requirement matrix + Birth-Certificate reader + migration `0039`) was
  also built this session but is **in-progress next sprint** — not part of this close, migration not yet on prod.
