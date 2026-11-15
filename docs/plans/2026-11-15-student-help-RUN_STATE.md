# RUN STATE - student help fixes (lead session "Help me")

Not the root RUN_STATE.md (that one belongs to the HalaTuju release-lead session).

## Grant (owner, 2026-11-15)
"Build continuously, and do not wait for me, until all the work is completed. Come to me only when there
are clear forks or potential deviation from accepted plan. You may want to show me the designs once ready
for my approval, and the drawing images, I want to see as well."

Scope: roadmap docs/plans/2026-11-15-student-help-fixes-roadmap.md, sprints H1-H9. Ends when H9 is merged
(or at the owner's word).

## Rules for this run
- Build on side branches, never on main. H1, H2, H3: own branch each (help-h1, help-h2, help-h3), rebased
  onto main and merged ALONE after the freeze (18 Nov). H4-H9: one branch `student-help`, cut at H4 start,
  rebased onto main every working day, one full review + final rebase, then ff into main.
- Worktrees OUTSIDE the workspace folder: C:/Users/tamil/wt/<branch> (VS Code rg pile-ups).
- ONE builder at a time from this session (project max 2; the release-lead session uses the other).
- Every sprint: fresh reviewer on the real diff; H1-H3 (+ H9 doc recognition) also an Opus adversarial review.
- Owner STOPS (send, keep working on other sprints meanwhile):
  - phone check (<=10 lines) before H1, H2, H3 go live;
  - Stitch designs for H5-H8 (one round) and the 8 sample drawings, before UI code that shows them;
  - paid Gemini re-runs (H1: 4 docs; H2: blocked offer letters; H3 dry run is free) - owner's word;
  - publishing: grouped, via the release-lead session, owner's direct yes;
  - any stop in Settings/_workflows/credit-discipline.md "STOP and ask the owner when".
- Coordinate MODEL_VERSION with the release lead: Gemini Option A bumps it (lands 17 Nov earliest); rebase
  after it and bump on top.

## Cursor
| Sprint | Branch | State | Notes |
|---|---|---|---|
| H1 #552 stamp | help-h1 | REVIEW PASS (Opus, 15 Nov); branch pushed; waits rebase + 18 Nov merge | 6874cdb16; suite 22372 pass; MODEL_VERSION 1.28.0. Payslip follow-up b0c1f819c DONE + review PASS, pushed. At rebase add the optional hardening (income_declaration.py ~84-87): "a declaration or village head's form always has an approver's section, even if blank" |
| H2 confirmation letters | help-h2 | ROUND 2 FIXED bcb7256d8 (15 Nov; not pushed; suite 22397 pass; VERDICT .6; 36 polys exact list; TD-630). Opus re-review round 3 RUNNING (h2-review3). Triage change: KMPP doc 1352 -> genuine; POLITEKNIK UNGKU OMAR + "IPOH PERAK" doc 2149 -> suspect (town = unknown word; reviewer asked about allowing state names). Then push help-h2 + owner phone check. Earlier: FIXED 226e71a71 (suite 22390 pass; VERDICT_ENGINE_VERSION 2026-11-15.4; name lists matric 15 / IPG 27 / CC 101; KV+TVET+poly lists not wired = suspect at best). Re-review round 2 FAIL (15 Nov), round-1 fixes hold. Fix round 2 QUEUED after h3a-followup (resume h2-fixer): (M) offer_rulings.py:401 _known_name checks only the word AFTER a known name - "MERCU KOLEJ KOMUNITI KLANG"+KPT and "MERCU BAHAGIAN MATRIKULASI"+KPM read genuine (main: not_offer_letter); also refuse an unknown name in a unit line ("PUSAT ASASI MERCU"); (L) offer_confirmations.py:99 _APPROVAL add DIDAFTAR DENGAN, DILESENKAN OLEH, DI BAWAH SELIAAN, REG NO, "under the purview of"; (H-ish) wire the ~36 polytechnics from the institutions table (closes "POLITEKNIK MERCU"+KPT genuine); add state short forms (P.PINANG, N.SEMBILAN...) + "KM" alias as exact spellings in _KNOWN_PUBLIC_NAMES; log TD: fully English confirmation bodies below CONFIRM_MIN; (L) EN matric offer body college name unchecked - note only. Version: at merge H3 must go above .4 (h3a-followup told .5). Triage: 26 blocked rows (not 13): ~5 move to genuine/suspect, 18 private stay blocked; "KM P.PINANG" short form -> suspect. Round-1 notes below: | REVIEW FAIL (15 Nov) round 1. Fixes: (H) English matric gate = page words only; private uni EN offer mentioning "Matriculation Division" -> genuine 0.71, can autofill a matric pick: require Division/KPM first on letterhead (_named_first/_first_institution) + EN offer title, drop bare-word twins; (M) EN matric results slip -> suspect, must stay not_offer_letter; (M) _PUBLIC_CONFIRMERS name-only lift ("KOLEJ MATRIKULASI MERCU" + KPT mark -> genuine): need clear public proof, KPT not a public mark, BAHAGIAN MATRIKULASI not its own mark; (M) add EN confirmation titles + IIUM EN names; bump VERDICT_ENGINE_VERSION; re-run adversarial review. Read-only triage SQL for the 13 in reviewer hand-back (no original_filename). | suite 22376 pass; 1.28.0 too (one shared bump at merge). Dry run not run (needs DATABASE_URL + corpus); reviewer asked for a read-only route. Open: English-titled confirmations not lifted; only UMS proven no private wing (others = suspect) |
| H3a start-year rule | help-h3 | Follow-up DONE 50f322526 (not pushed; suite 22396 pass, jest 312; VERDICT_ENGINE_VERSION 2026-11-15.5; student note live-offer only; ms/ta first drafts; Degree dry run + sol_tag owed). NOTE: new session-year reading also feeds STPM award sizing + funding estimate (money). Open: bare "Sesi 2024/2025" = first year (today's behaviour). Opus review FAIL (15 Nov). Fix round QUEUED after h2-fixer (FRESH Opus builder; h3a-followup is at 163k): (H) pathway_engine.py:516-522 reporting-date check runs before the Semester 3+ check -> "Semester 3 Sesi 2024/2025"+"3 Mac 2025" reads 2025 = continuing student passes the Degree gift; test _LATER_TERM_RE first + regression test with a date; (L, money) pathway_engine.py:475 session pattern matches a date range "Julai 2025 - 26 Februari 2026" -> 2026 (RM1,000 -> RM3,000 STPM); do not treat "2025 - 26" as a session when a month/date follows; (L) pathway_engine.py:500-506 docstring: '' falls back to stored reporting_date in course_start_year:555 - fix the claim; bare session DECIDED (lead, reviewer rec.): unknown ONLY in start_year.reading when S and S+1 straddle the gift's years (both in = pass, both out = fail), award sizing keeps S; note polytechnic "Sesi II 2024/2025" (Dec 2024 start) reads 2025 - Degree gift unaffected, log it. Version stays .5 (unpushed). H2 fix round 2 running (h2-fixer, VERDICT .6). Earlier: REVIEW PASS (Opus, 15 Nov); branch pushed. Follow-up list was: (LM) pathway_engine.py:344 takes first 20xx, "Sesi 2024/2025 Semester II" = Feb 2025 start read as 2024; (L) stale "0212" refs (models/programmes.py:388, models/applications.py:258, 0211 docstring, technical-debt.md TD-226/TD-084); (L) QC accept endpoint test (400 verdict_gap_floor); (L) verdict_narrative.py:53 wording; + student copy (owner A: student sees the reason, not a block). Note: past-QC cases are not re-checked when years are set later - #782 (the one caught) is shortlisted, not past QC (checked 15 Nov), so OK; re-check at release. | suite 22381 pass; VERDICT_ENGINE_VERSION 2026-11-15.3; migration 0212 is plain SQL, must be applied in Supabase BEFORE the push (release step). Values not pre-filled: admin types "2025, 2026" on bpb-deg-dip-2026 after release. Dry run 162 Degree apps: 1 caught, 48 fine, 0 unreadable, 90 no letter, 23 rejected. Reviewer-only today (no student copy) - asked owner. |
| H3b recent-letter ask | help-h3 | queued (split: check2_queries.py at 674/675, needs moves-only split first) | ~24 live offers older than 3 months (+ up to 28 August) |
| H4 split + stage lock | student-help | queued | Sonnet |
| H5 redesign | student-help | queued | Stitch round (H5-H8) needs owner approval |
| H6 replace | student-help | queued | Sonnet |
| H7 I don't have this | student-help | queued | Sonnet |
| H8 samples | student-help | queued | drawings need owner approval |
| H9 coach + sample check | student-help | queued | Opus review |

## Waiting on the owner
- (DONE 15 Nov) Designs 1-3 approved: Action Centre, "I don't have this", load error.
- (DONE 15 Nov) Picture 4 (sample viewer, mock_4) approved; it will show the v2 samples. ALL design
  approvals for H5-H8 are now in.
- (DONE 15 Nov) "We never take your progress backwards." line: DROPPED. Owner: a wrong document must go
  back. H5: the bar shows the true state; a returned document moves back to "Needs you" with "We need this
  again" + the reason. Builder must leave the line out of mock_1.
- 8 sample drawings: owner REJECTED v1 - "the samples must match the real". Redraw (samples_v2) copies a
  public real sample: same size, layout, standard wording, AND (owner, later) the real colours and images
  (logos, crests). Fake details, big SAMPLE / CONTOH stamp across the crest. v2 SENT to owner 15 Nov
  (designs/samples_v2/*.png; refs in designs/refs.md + refs_b.md). Known gaps: logos blurry (low-res
  crops); TNB page-1 bottom is filler; SPM wording approximated; offer letter = UPNM sample (no public
  UPU/poly letter). Owner 15 Nov: 7 APPROVED; MyKad wrong (drew the 2026 new-gen card; students hold the
  current chip-on-front design). MyKad redrawn + sent 15 Nov (old kept as mykad_newgen.*); owner OK'd the
  approach before seeing it - treat as approved unless the owner objects. All 8 samples settled.
  Owner 15 Nov: cover the other doc types too. Drawing now (samples-c, samples-d): birth_certificate,
  school_leaving_cert, higher_results_stpm, higher_results_matric, bank_statement (passbook),
  income_support_doc (village-head form). 4 DRAWN + sent 15 Nov (birth_certificate, school_leaving_cert,
  bank_statement = Maybank e-statement, income_support_doc = KKDW form); STPM + matric results SKIPPED (no
  public image). Owner 15 Nov: the 4 APPROVED (12 samples approved in all). Cleanup: designs/refd/ left (rm denied) - delete at session end. Free-form types (reference_letter, guardianship_letter,
  semester_result, statement_of_intent, photo) + STPM/matric results: owner 15 Nov chose A = a simple
  typical example each (not a copy of one real one); photo = good/bad photo guide. Drawing (samples-e,
  samples-f); 6 SENT 15 Nov (STPM/matric layouts are typical, not copied - no public slip). Guardianship
  letter being redrawn to match en.json (parent's authorisation letter, not a village-head declaration).
  Needs owner approval. Owner 15 Nov: STPM + matric "a little off", gave real references (PII - layout
  passed to the drawer as words only); redrawn + SENT 15 Nov (gen_v3/hr_make.py; crest + MPM logo are
  simplified drawings). Owner 15 Nov: the last 7 APPROVED (reference_letter, statement_of_intent, photo,
  semester_result, guardianship_letter, STPM, matric). ALL 19 sample types approved (DOC_TYPES minus
  "other"; parent_ic uses the MyKad sample). H8 builds them all. Samples live in scratchpad only - H8
  builder must copy designs/samples_v2/*.svg + generators into the repo FIRST (scratchpad is temporary). This
  overrides the roadmap's "no crests, no logos" for H8.
- (Owner idea 15 Nov) Upload should open the camera. Today the doc cards use accept="image/*,.pdf" with no
  capture attribute (cards.tsx:73-76, ActionCentre.tsx:363). Plan: in H5 add a "Take a photo" button
  (capture="environment") beside the normal Upload (keeps gallery + PDF).
- (DONE 15 Nov) H2 UMS: owner - UMS confirmations = suspect, not a blocker, a reviewer looks. Sent to fixer.
- (DONE 15 Nov) H3a: owner A - the student sees a short reason when the start year is outside the gift's years
  (e.g. "This gift is for students who started in 2025 or 2026"); a reviewer still decides. In H3a follow-up.
- (DONE 15 Nov) H1 phone check: owner OK. Paid Re-run of the 4 #552-pattern docs + 1 known-bad form: owner
  OK - run ONLY after H1 is live (cockpit Re-run), report the 5 outcomes as codes.

## Open risks
- MODEL_VERSION conflict with Gemini Option A (H1, H2, H9).
