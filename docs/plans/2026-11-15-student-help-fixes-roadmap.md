# Student help fixes: roadmap (drafted 2026-11-15)

Status: APPROVED by the owner 2026-11-15 (order as written; H7 reason lists as written; per-gift start-year
setting deferred). No sprint starts before the freeze lifts (Wed 18 Nov) and before the post-audit work has its
slots (owner ruling 2026-11-14: post-audit work first). Builder slots are agreed with the HalaTuju release-lead
session. Publishing follows the release train (max 3 windows a day, the owner's direct yes).

## Branch strategy (owner, 2026-11-15, option A)

- **H1 and H2 go to main alone**, each as soon as it is ready (they unblock real students), with the usual
  adversarial review and the owner's phone check.
- **H3-H9 build on one long-lived branch `student-help`** in its own worktree (see
  Settings/_workflows/parallel-work-isolation.md), cut from main when H3 starts.
- Rebase `student-help` onto main **every working day** to keep conflicts small. Run the targeted tests after
  each rebase.
- At the end: one full suite, one fresh review of the whole branch diff, a final rebase, then fast-forward
  into main. Publishing is a separate step on the owner's yes.

Source: the owner's walk through the Help Me emails on 15 Nov (items 1-5). The owner may add items after
reading more emails; new items join at the next sprint close (re-plan).

## Items and owner rulings

1. **"I don't have this" on OPTIONAL Check 2 document asks.** Covers optional documents only, never
   potentially-required ones. Today: per-member EPF (`*_epf_missing`), `water_bill_recheck`,
   `electricity_bill_recheck`, `school_leaving_cert_missing`. Built as an `optional` marker on `DOC_SPECS`
   (check2_queries.py). The card shows Upload + "I don't have this". The reasons show only after that tap.
   Reasons are tap buttons (phone and desktop), a different list per document. "Other" opens a required text
   box. Cancel goes back to Upload. Bill wording gains "(optional)". Once answered, the ask closes and Check 2
   never asks it again. The reviewer sees the reason (OutstandingPanel). This also settles support Fix 3 for
   bills (rulings sheet R2, option A).
2. **Replace an uploaded document + a simpler Action Centre.** Replace is allowed until the interview is done
   (`services/querying.py` `querying_locked`), max 3 replaces per document (server-enforced; every upload is a
   paid read). Approved redesign direction: 3 sections ("Needs you" / "Sent, we are checking" / "Done"); a
   "why we ask" line; file name + Replace; "We need this again" + the reason; a progress bar that never goes
   backwards; a clear bad-file message; a retry message when the page fails to load. Split ActionCentre.tsx
   first. Safety gap found: documents POST/DELETE have NO stage lock (only `/resolve/` checks
   `querying_locked`).
3. **Sample documents.** Drawn SVG samples (no AI photos, no crests, no logos, fake numbers such as
   000000-00-0000), a SAMPLE / CONTOH stamp, arrows on what we check, translatable labels. First 8: MyKad (one
   sample for student + parent IC), results slip, payslip, offer letter, STR, EPF statement, electricity bill,
   water bill. A small "See a sample" link on each document card. The Cikgu Gopal / Guna coach
   (DocumentHelpCoach.tsx) shows a "See a sample" button when the student struggles. Plus a check that spots
   an uploaded sample.
4. **#552: village-head approval stamp not read.** `income_doc_unapproved` because the vision read says
   has_stamp=no (the stamp sits on the Nama/Alamat lines; the empty "Cop Rasmi" box is read as "no stamp").
   Owner: first job after 18 Nov, not a hotfix.
5. **#597: confirmation-of-studies letters.** Owner rulings 15 Nov:
   - A confirmation letter is an alternative to the offer letter for ALL pathways (students lose offers).
     Widen ruling 4 (decisions.md "Default accepted - confirmation-of-studies letters") from UMS / polytechnic
     / Form 6 to every public institution type (matric, IPG, KV, IKBN / IKM, all public universities). Keep:
     private college or a university's private wing = fail; a university with a private wing = `suspect` (a
     person checks, not a block). A confirmation letter never writes a course pick.
   - A student who started earlier (for example a 2025 matric student in the 2-year programme) may apply if
     the GIFT'S RULES allow it. Per gift, not global. The Sabah gift (2026-bpb-s) allows it. What matters is
     current enrolment.
   - An old offer or confirmation letter gets a soft Check 2 ask for a recent confirmation letter (no block).
   - Also: English "Matriculation Division" offers are not fingerprinted (offer_signatures.py is Malay-only),
     and #597's English offer (doc 6062) was staged but never promoted (trace why).

## Sprints

Order: proven bugs that block students first (risk + value), then the Action Centre base the UI items need,
then the UI items, then samples.

### H1 - #552 approval stamp (item 4)
- **Goal:** a stamp anywhere in the approver section counts; an empty "Cop Rasmi" box does not cancel it.
- **Scope:** `income_declaration.py` `APPROVAL_PROMPT` (+ `approval_missing` only if needed), regression test
  from #552's layout (no PII), prompt / MODEL_VERSION bump, decisions.md entry.
- **Acceptance:** regression test passes; a handwritten title with no stamp still fails; adversarial review
  clean; owner phone check. Then a paid re-run of the 4 known docs (2 apps) ONLY on the owner's word.
- **Build:** Opus (income). **Complexity:** low.

### H2 - Confirmation letters for every public institution (item 5, part 1)
- **Goal:** a public institution's confirmation letter clears `offer_not_official`; English matric offers are
  recognised.
- **Scope:** `_NO_PRIVATE_WING` / `confirmation_kind` / `_confirmation_lift` (offer_rulings.py,
  offer_reading.py), English matric fingerprint (offer_signatures.py), trace doc 6062's missed promotion,
  decisions.md ruling 4 widened, MODEL_VERSION bump, tests per institution type + private-wing tests.
- **Acceptance:** dry run over the 13 live blocked `not_offer_letter` apps lists each move (codes only); no
  private letter turns green; adversarial review clean; owner phone check. Paid re-score only on the owner's
  word.
- **Build:** Opus (eligibility). **Complexity:** high.

### H3 - Old letters ask for a recent one (item 5, part 2)
- **Goal:** an offer or confirmation letter older than the window raises a soft Check 2 ask for a recent
  confirmation letter.
- **Scope:** new Check 2 code beside `stale_income_proof` (pathway_engine `is_confirmation_letter` +
  `offer_date`), window as an org tunable (org_config_registry.py, default 3 months), student + reviewer copy
  (en; ms/ta through Sol), tests.
- **Per-gift "earlier starters" rule:** today the start year is display-only, so nothing blocks earlier
  starters and the Sabah gift already works. Owner 2026-11-15: do NOT build the gift setting now; build it
  when a gift needs "2026 starters only".
- **Acceptance:** no student is blocked by the new ask; the ask closes on a recent letter; tests pass.
- **Build:** Opus (eligibility-adjacent), Sonnet review. **Complexity:** medium.

### H4 - Action Centre split + documents stage lock (item 2, base)
- **Goal:** ActionCentre.tsx split into small parts with NO visible change; documents POST/DELETE refuse after
  `querying_locked`.
- **Scope:** ActionCentre.tsx (715 lines; check the size ledger) -> components under 600 lines; documents.py
  POST/DELETE guard + tests; check what the documents tab shows after the interview.
- **Acceptance:** jest + pytest green; same screens before and after; locked case returns a clear error.
- **Build:** Sonnet. **Complexity:** medium.

### H5 - Action Centre redesign (item 2)
- **Goal:** the approved 3-section Action Centre.
- **Stitch first:** ONE Stitch round covering H5, H6 and H7 (sections, Replace, "I don't have this" flow);
  owner approves before any UI code.
- **Scope:** sections, "why we ask" line, sent state for typed answers, progress that never goes backwards,
  bad-file message, load-error retry; en copy (ms/ta through Sol).
- **Acceptance:** mobile check at phone width; jest; owner sees it on a preview before publish.
- **Build:** Sonnet. **Complexity:** medium.

### H6 - Replace a document (item 2)
- **Goal:** a Replace button on each sent / done document until `querying_locked`, max 3 per document.
- **Scope:** the card UI; server cap (count replaces per document, refuse the 4th with a clear message);
  re-upload already supersedes (documents.py:173-254); tests.
- **Acceptance:** 3 replaces work, the 4th is refused; replace closes after the interview; tests pass.
- **Build:** Sonnet. **Complexity:** medium.

### H7 - "I don't have this" (item 1)
- **Goal:** students can decline an optional document with a reason.
- **Scope:** `optional` marker on `DOC_SPECS`; `views/resolution.py` accepts a reason (+ note) on optional
  doc items only; Check 2 auto-reopen never re-asks a declined item; tap-button reason lists (below);
  reviewer sees the reason; bill wording "(optional)"; tests.
- **Acceptance:** a required doc item still refuses text; declined items stay closed after a Check 2 re-run;
  tests pass.
- **Build:** Sonnet. **Complexity:** medium.

### H8 - Sample documents (item 3, part 1)
- **Goal:** 8 drawn samples and a "See a sample" link on each document card.
- **Scope:** 8 SVGs (SAMPLE / CONTOH stamp, fake numbers, arrows, translatable labels), a sample viewer, the
  card link; Stitch for the viewer (can join the H5 round).
- **Acceptance:** no real names, numbers, crests or logos; works at phone width; jest.
- **Build:** Sonnet. **Complexity:** medium.

### H9 - Coach points to samples + spot an uploaded sample (item 3, part 2)
- **Goal:** the coach shows "See a sample" when the student struggles; an uploaded sample is caught.
- **Scope:** DocumentHelpCoach.tsx button by verdict; help_verdict.py; a sample check in document reading
  (MODEL_VERSION bump); tests.
- **Acceptance:** a SAMPLE / CONTOH upload is flagged, never accepted; a real document is not flagged; review.
- **Build:** Sonnet, Opus review (document recognition). **Complexity:** medium.

Total: 9 sprints. H1-H3 change who is blocked, so each has an adversarial review and the owner's phone check.
H4-H9 are student-facing UI and run on Sonnet with a fresh reviewer.

## Reason lists for H7 (approved by the owner 2026-11-15)

Every list ends with "Other" (opens a required text box).

- **EPF statement** (asked per family member): Does not work in a job that pays EPF (for example
  self-employed, farmer, odd jobs) / Works abroad / Has EPF, but cannot get the statement now / Does not live
  with us, or we have no contact / Other
- **Electricity bill:** The landlord pays it, or it is in the rent / We share a meter with another house / We
  have no electricity supply / We lost the bill and cannot get a copy / Other
- **Water bill:** We use a well, river or hill water (no water bill) / The landlord pays it, or it is in the
  rent / We share a meter with another house / We lost the bill and cannot get a copy / Other
- **School-leaving certificate:** The school has not given it to me yet / I lost it and I am asking for a
  copy / I cannot reach the school / Other

## Not in this plan

The other support-email work waits for the owner's rulings R1-R5 and the FAQ facts: Fix 3 for earners, Fix 4b
("Ask a person"), FAQ q10-q14, the support inbox (parked), the Gmail drafts helper.
