# Retrospective — per-gift referral sources, Sprints 1 + 2: each gift chooses its own "Who referred you?" list (2026-10-09)

Decisions: `docs/decisions.md` 2026-10-08 ("A gift chooses its referral sources" and "The referral
codes: three fixed choices always…"). Cutover notes: `docs/scholarship/gift-sources-s1-cutover-sql.md`,
`docs/scholarship/gift-sources-s2-cutover-sql.md`. Design of record: the owner-approved Artifact mock
(https://claude.ai/artifact/BCyUgeaeARKXRnrMCrhTCY). Commits `38495b34` (S1), `9ae08a66` (S2),
`505ab0f8` (TD-230 closed, TD-379 raised), `ffa0983a` (review fixes; TD-380, TD-381 raised) — shipped
as ONE push of `ffa0983a`: api `halatuju-api-01117-4m6`, web `halatuju-web-00968-28w`.

## What Was Built

- **A gift chooses its sources (S1).** New table `programme_referral_sources` (`ProgrammeReferralSource`,
  scholarship 0172) and a "Who referred you?" card on Programme → Configuration: one toggle per active
  source (the owner asked for toggles, not tick boxes), "N of M on this form", a read-only footer for the
  three choices that are always there, and the tab's own Save / Discard. No row means "not on this form":
  a source newly switched on joins no gift, and a new gift starts with none.
- **The Sources page** lost its one-gift picker; each row says "On N of M gifts" (one query for the
  list), and after a switch-ON it says "Now switch it on in each gift's Configuration." The old
  `PartnerOrganisation.programme` column is deprecated (expand-contract; TD-379 drops it).
- **The student form follows the gift (S2).** The public intake serves the gift's sources as
  `{code, name}` only; the apply form lists them, then Halatuju.xyz, Facebook / WhatsApp and Other,
  always. The hard-coded `REFERRING_ORG_OPTIONS` is gone. The submit refuses a code the gift does not
  offer (400 `referral_source_not_offered`, nothing written) and the form asks her to choose again,
  keeping everything else.
- **Legacy codes retired.** `pushparani` and `govind` left every form; the one saved profile carrying
  `pushparani` moved to `other` (courses 0077).
- **Review fixes before the push:** a saved choice is cleared only when the list is known; a new source
  reads by its name, not "Other", on the admin screens; the fixed codes and the house organisation's code
  are reserved; a source switched off while a Configuration tab is open no longer jams the save.
- Admin: the Applications Source filter lists every source by name plus the fixed three; tooltips and
  the cockpit pill never show a raw code.

## What Went Well

- **The pre-flight read paid for itself before a line was written.** It caught the stale "next
  migration 0171" note (request #31 had taken 0171), four places where the plan contradicted recorded
  decisions (one gift per person not a list, NULL-means-everything, expand-contract, the data migration
  keeping the source), the size budgets on `scholarship/views.py` and `courses/models.py`, and the
  four-query budget on the Applications list. Each was settled in the plan, not discovered in review.
- **Stitch failed, and the fallback lesson (`docs/lessons.md`, "When Stitch stalls…") worked as
  written:** an Artifact mock got owner approval and a concrete change (toggles) the same day.
- **The adversarial review found real harm before the push** — 0 blockers, 4 should-fix, all fixed in
  `ffa0983a` — and the two it could not fix in scope became register entries, not silence.
- **One push, one deploy per service, migrate-first with both ledger rows recorded**, and a live check
  that read the intake's actual payload (codes and names only) rather than a status code.
- **The rebase onto two other-session commits** conflicted only in the append-only CHANGELOG and
  decisions files; both sides were kept.
- **The owner was told about the seed difference** the moment it was seen, with the cause.

## What Went Wrong

1. **Stitch generate failed twice.** Symptom: both `generate_screen_from_text` calls timed out and the
   screen never appeared in the project, so no Stitch design exists for this card. Root cause: Stitch's
   generate is unreliable (the known "times out" behaviour, but this time it had not succeeded behind the
   timeout). System change: none new — the existing lesson (fall back to an owner-approved Artifact mock
   after Stitch stalls) was followed, and the mock is named here as the design of record so the next
   change to this card starts from it.
2. **The seed's result differed from the plan.** Symptom: the plan and the S1 cutover note expected
   7 + 7 rows; production got `brightpath-flagship` 7, `bpb-sabah-2026` 3. Root cause: the expected rows
   came from a production read on 2026-10-08; before the cutover the next morning somebody used the OLD
   single-gift picker on `cumig`, `hss`, `hyo` and `mhm` (→ flagship), and the seed honoured it as
   designed. The inputs were live, owner-editable settings and were read once, a day early. System
   change: lesson added (`docs/lessons.md` 2026-10-09) — re-run a data migration's pre-check
   immediately before applying, write the expected rows from that read, and tell the owner of any
   difference BEFORE applying. The cutover note and decisions.md now record the actual result.
3. **The builder deleted i18n keys outside the brief.** Symptom: to pay for S1's new strings under the
   bundle line it removed eight keys "nothing reads" (`outcomes.*`, `dashboard.reportDesc`) that the
   brief never mentioned. The keys were dead and the cut was sound, but it was a scope decision the
   builder took alone.
   Root cause: the brief gave the builder a hard budget (the en.json bundle line, TD-360) without saying
   what it may remove to meet it, so it chose for itself. System change: a builder brief that carries a
   budget also says what may be removed to meet it, and otherwise "stop and report" — to be added to
   the lead's builder brief (memory `feedback_build_with_opus_agents.md`) at close.
4. **The jest "before" figure was inferred, not measured.** Symptom: S1's "jest 4181 → 4192" took 4181
   from the previous sprint's record (a sprint with no web change) instead of running the suite on the
   base commit. It happened to be right, but nothing proved it. Root cause: the standing lesson "take the
   baseline reading yourself, before you touch anything, even when the brief states it" (Code health H13)
   was not in the builder's brief. System change: the builder brief asks for both suites to be run on the
   base commit and quoted before the first edit (same memory file as item 3).
5. **The reserved-code hole was found only by the review.** Symptom: an admin could create a source
   coded `other`, `halatuju`, `social` or the house organisation's code, and the apply path would then
   link every student who picked that fixed choice to it — and to the partner emails a referral sends.
   Root cause: the design treated the fixed three and the registry as separate lists, but the submit
   looked BOTH up in one place by code; nobody asked "can a user mint a fixed code?". System change:
   fixed (`code_reserved` on the Sources POST, no organisation lookup for a fixed choice, tests);
   lesson added (`docs/lessons.md` 2026-10-09).
6. **The rebase left a stray line.** Symptom: one "is built." line from the conflict survived in an
   append-only doc and was removed by hand. Root cause: a hand-resolved conflict in a long prose file
   was not re-read as a whole. System change: none new — after resolving any doc conflict, read the
   resolved region top to bottom before continuing, not only the conflict markers.

## Design Decisions

- **Owner's rulings:** each gift chooses its sources in Configuration (toggles); a new source joins no
  gift; a new gift starts with none; Halatuju.xyz / Facebook-WhatsApp / Other are always on every form
  and are not toggles; Pushparani and Govind are legacy → `other`; the server refuses an unoffered code.
- **Empty means NOT listed** for sources — the opposite of the S-ASSIGN "NULL means everything" rule,
  which still governs reviewer and invitation scoping.
- **Expand-contract:** the old one-gift column stays, read by nothing, until TD-379's contract migration.
- **The seed honours the old column** where set (that gift only), otherwise every active gift gets every
  active source.
- **The fixed three are held on both sides** (server and web) with a drift test, because the form must
  still show them when the intake fails.
- **Strict on the APPLY path only:** `referred_by_org` is linked only through the gift's active sources
  there; the course-selector profile endpoints stay loose (TD-380).
- **A saved code is cleared only when the list is known** (review fix); otherwise kept and shown, with
  the server refusal as the safety net.

## Review findings and how each was answered

- Should-fix 1 (a saved code wiped when the list is unknown) — fixed in `ffa0983a`.
- Should-fix 2 (a new source shown as "Other" on the admin screens) — fixed.
- Should-fix 3 (a source could take a reserved code and collect every "Other" student) — fixed.
- Should-fix 4 (a source switched off meanwhile blocks the Configuration save) — fixed.
- 8 notes — two raised as **TD-380** (loose `referred_by_org` links outside the apply path; a stale link
  never cleared) and **TD-381** (Sources shared across tenants; a thinner filter for reviewer / QC); the
  documentation points (deploy-before-migrate 500s, the accepted deploy window, the S1 source-code
  pre-check, "strict on the apply path only") were written into the cutover docs and decisions.md in
  `ffa0983a`.
- Bite-checks: S1 — removing the seed's tenant exclusion, the card's tenant exclusion or the count's
  scope filter each turned its tests red. S2 — removing the submit refusal, the gift filter, the
  code-and-name-only payload or the sync's `active_sources()` lookup each turned red; one bite found the
  submit tests blind to the sync half, and a direct `sync_profile_fields` test was added.

## Numbers

| | Before | After |
|---|---|---|
| pytest (`-n auto`, the deploy gate's line) | 8207 passed / 3 skipped | 8260 passed / 3 skipped (on main incl. TD-376/377) |
| jest | 4181 / 255 suites (inferred — see item 4) | 4221 / 259 suites |
| tsc / lint | 0 / 0 | 0 / 0 |
| i18n keys per locale | 5449 | 5437 |
| Bundle median | 228.781 kB (line 229) | 228.568 kB |
| `/scholarship/application` | 273.797 kB (line 274) | 273.546 kB |
| Migrations | scholarship 0171, courses 0076 | scholarship 0172, courses 0077 (migrate-first, ledger rows recorded) |
| Seed rows (production) | planned 14 | 10 (flagship 7, Sabah 3, testing 0) |
| Register open | 118 | 120 (TD-230 closed; TD-379, TD-380, TD-381 raised) |
| Sprint diff (`b991fbf4..ffa0983a`) | | 57 files, +2,568 / −396 |
| Adversarial review | | 0 blockers, 4 should-fix (all fixed), 8 notes |
| Stitch attempts | | 2, both failed → Artifact mock |
| Deploys | | 1 per service (api `0aced23b`, web `4a13c71a`) |
| Sol | | 22 entries tagged `per-gift-sources` |
