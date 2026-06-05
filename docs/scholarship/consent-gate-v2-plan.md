# Consent / Submission Gate v2 — route-aware document gate (TD-085)

**Status:** **✅ TD-085 COMPLETE — both sprints SHIPPED + DEPLOYED 2026-06-05** (no migrations). S1 (consent gate v2,
retro `docs/retrospective-consent-gate-v2-s1.md`) + S2 (officer Documents-panel redesign, retro
`docs/retrospective-td085-cockpit-s2.md`). The document-first verdict + re-extraction backfill were intentionally
dropped (route stays authoritative). PARKED for later: the post-consent summary page + lock-at-Continue (section below).
**Part of:** TD-085.
**FINAL SCOPE (2026-06-05): TWO sprints only — (S1) Consent gate v2, (S2) Documents-panel redesign (officer cockpit).**
**DROPPED:** (a) the *document-first verdict* — it would make the route NON-authoritative, but the strict route-aware
gate (S1) + the manual slotting already prevent the route/doc mismatch it was meant to fix; the route stays
authoritative. (b) the *re-extraction backfill* — the user re-runs legacy docs by hand in the cockpit (the "Re-run"
button, as done for Divashini/Yeswindran/Theepicaa). No verdict-logic change, no new migration in either sprint.

## Objective
The consent/submission gate (`consent_blockers`) currently treats income proof as the old S23 rule —
`ic + results_slip + parent_ic + any one of {str, salary_slip, epf}` — with no awareness of the wizard route, the
earner, or the relationship docs. Realign the gate so it demands exactly the documents the student's **income route**
requires, plus a now-compulsory **offer letter**. Reuse the wizard's `income_requirements` so the gate and the
student's checklist can never drift.

## The gate (v2)

**Always compulsory (every applicant):**
| Item | doc_type | Status |
|---|---|---|
| IC | `ic` | already gated (`ic_missing`) |
| Results slip | `results_slip` | already gated (`results_slip_missing`) |
| **Offer letter** | `offer_letter` | **NEW — `offer_letter_missing`** |
| Earner's IC | `parent_ic` | already gated (`parent_ic_missing`) |
| NRIC/name match on the IC | — | already live (`_ic_identity_blockers`) |

**If STR route** (`income_route='str'`, single `income_earner`):
- `str` — **NEW** `str_missing`
- earner IC (`parent_ic`) — existing
- earner = **mother** → `birth_certificate` (**NEW** `birth_certificate_missing`)
- earner = **guardian** → `guardianship_letter` (**NEW** `guardianship_letter_missing`)
- earner = **father** → nothing extra (patronymic)

**If salary route** (`income_route='salary'`, `income_working_members` multi-select):
- For **each** ticked member: their IC (`parent_ic` tagged `household_member=member`) + their **salary slip**
  (`salary_slip` tagged member). **EPF does NOT substitute.**
- member = **mother** → + `birth_certificate`; member = **guardian** → + `guardianship_letter`;
  father / elder brother / elder sister → patronymic, nothing extra.
- Per-member blockers carry the member label (reuse the verdict's `members`-list + `localiseParams` pattern so the
  student sees "Salary slip for Mother", "IC for Elder brother", localised en/ms/ta).

## Decisions (user, 2026-06-05)
1. **Hard-block to submit.** Missing route-required income docs block submission. **"Never-block" now lives ONLY at
   the officer/interview verdict, not at submission.** — *Supersedes the "income never blocks a genuinely poor family"
   decision (decisions.md, Income Check-1) at the SUBMISSION layer; the principle still holds at the verdict layer.*
2. **Salary slip only** — EPF does not satisfy a member's income proof (EPF = accumulated savings, not current income).
3. **Offer letter compulsory for everyone** — `offer_letter_missing` blocks all applicants.
4. **Grandfather already-submitted apps.** The strict checks apply ONLY to apps not yet submitted
   (`profile_completed_at IS NULL`). The 6 already-`profile_complete` apps (incl. KISHANTAN, STR w/ no STR doc) keep
   their status and are handled at Check 2 / interview — never retroactively reverted on the new rules.

## Informal earner — the path (resolved 2026-06-05)
The earlier "sharp edge" (informal earner can't submit) is largely **resolved by how families actually document
informal income**: a hawker / lorry driver / tuition teacher obtains an **official government income-verification
letter** stating a salary, which the system already accepts as `salary_slip`. So an informal earner *can* clear the
gate — they're not document-less.

**Reliability distinction (drives the VERDICT, not the gate):**
- **STR document** = authoritative (the government already means-tested the family) → can **auto-clear**.
- **Income-verification letter** = official but the **amount is unverified** ("a letter claiming RM1,800"). The
  salary-slip reader already flags it (`warning: "this is an income-verification letter"`). Treatment: it **passes the
  submission gate** (family isn't stopped at the door) but its amount → **`recommend` + manual verification at
  interview**, NOT an auto-green tile. A clean payslip or an STR auto-greens; a bare income letter does not.
- Implication for the verdict half of TD-085: when the only salary proof for a member is an income-verification letter
  (detected via the extraction warning / no employer), the per-capita result is advisory → `recommend`, never
  auto-`verified`.

Residual edge: a household with literally **no document of any kind** (not even an income letter) still can't submit.
Rare; accepted. A deliberate "informal, no letter" sub-path could be added later if needed.

## Implementation touch-points
- `services.consent_blockers` — replace the flat `income_proof_missing` with route-aware blockers sourced from
  `income_requirements(application)['compulsory']` (+ the per-member salary expansion); add `offer_letter_missing`.
  Gate the new strict income/offer checks on `profile_completed_at IS NULL` (grandfathering).
- `services.application_completeness` — `documents_done` must mirror the same route-aware logic (single source: read it
  off `consent_blockers`/`income_requirements`, don't re-derive).
- `income_engine.income_requirements` / `salary_member_blocks` — promote the per-member **salary slip from optional to
  compulsory** so the wizard checklist and the gate agree. (Today it's optional, to honour never-block — that moves to
  the verdict layer per decision 1.)
- `services.revert_if_profile_incomplete` — must NOT apply the new strict checks to already-`profile_complete` apps
  (grandfather), or it would roll back the 6.
- Frontend i18n — new blocker labels with the correct terms: `offer_letter_missing`, `str_missing`,
  `birth_certificate_missing`, `guardianship_letter_missing`, `salary_slip_missing` (+ member-qualified variants),
  en/ms/ta parity.

## Knock-on effects
- The four students we hand-slotted on 2026-06-05 get correct blockers: Harish & Sharmila → STR doc or switch to
  salary; Divashini & Janani → birth certificate.
- Existing `income_proof_missing` becomes an orphan code once replaced (remove from i18n/codepaths).
- Interaction with the **document-first verdict** (the other half of TD-085): the gate decides *what must be uploaded*;
  the verdict decides *whether what's uploaded verifies*. Build them as one sprint so they stay consistent.

## Documents-panel redesign — officer cockpit (agreed 2026-06-05)
**Scope:** the officer cockpit Documents drawer ONLY (not the student `/application` view). Grouped by the 4 facts
(Identity · Academic · Pathway · Income).

**Per-document display (two lines):**
- Line 1: file name + aggregate badge (the roll-up of the fact colours below).
- Line 2: the **labels** of the facts *that document can provide* — never the values, never a fact it can't supply —
  each coloured: 🟢 fully verified · 🟡 partial (until cured) · 🔴 not verified. *Yellow example:* a results slip
  showing 9 subjects but only 8 keyed → **Subjects 🟡** until the 9th is entered, then 🟢.

**Fact map (what each doc yields):**
| Doc | Facts |
|---|---|
| IC (identity) | Name · IC No |
| Earner IC — **father / brother / sister** | Name · IC No · **Relationship** (patronymic match vs the student IC; cross-doc → 🟢 match / 🔴 mismatch / 🟡 either IC unread) |
| Earner IC — **mother / guardian** | Name · IC No (relationship NOT here) |
| Birth certificate | Child · Mother · Father (carries the **mother** relationship) |
| Guardianship letter | Guardian · Ward (carries the **guardian** relationship) |
| STR | Recipient · IC No · Current (status + year) |
| Salary slip | Name · Amount · Period |
| Utility bill | Address |
| Results slip | Name · Subjects · Results |
| Offer letter | Name · IC No · Pathway |

**Relationship is movable** — it attaches to whichever doc can prove it: father/sibling IC (patronymic) · mother → BC ·
guardian → guardianship letter. Never shown on a mother's/guardian's IC.

**Income section = a visual render of `income_requirements` (route + selection aware):**
- **Order:** compulsory on top, optional at the bottom, fixed/predictable.
  - STR route: STR doc → earner IC → BC *(if mother)* / guardianship *(if guardian)* ‖ optional: salary slip → utility bills → EPF.
  - Salary route: per **selected** working member, a grouped cluster (earner IC → salary slip → BC if that member is the mother) ‖ then shared optional: utility bills → EPF.
- **Selection-aware:** clusters/placeholders appear ONLY for selected earners (`income_earner` STR / `income_working_members`
  salary). An unselected member shows nothing; a doc isn't compulsory unless route+selection makes it so (e.g. no mother
  selected → no BC requirement → no BC placeholder).
- **Missing compulsory docs → placeholder rows** ("Birth certificate — Missing 🔴"), but ONLY for docs that route+selection
  make compulsory. This is how an unmet requirement surfaces without misrepresenting the docs that ARE present.

**Fixes the `documentPill` bug** (earner IC always "Unread"): the earner IC now shows Name · IC No (+ Relationship for a
father/sibling) instead of "Unread". Build: extend `lib/officerCockpit.ts` (per-doc fact list + colours, sourced from the
serializer check fields + `income_requirements`), + jest.

## Manual slottings already applied to prod (2026-06-05) — the backfill must NOT undo these
Hand-set via Supabase MCP while triaging the shortlisted pipeline. A future backfill script should treat an app whose
`income_route` is already non-blank as DONE (skip it), not re-derive it.

| App | Student | Set | Notes |
|---|---|---|---|
| 18 | Divashini | `income_route='str'`, `income_earner='mother'` | STR verified (recipient = mother); still owes birth certificate |
| 5 | Janani | `income_route='salary'`, `income_working_members=['mother']`; tagged `parent_ic`+`salary_slip` → `mother` | mother gross RM6,655 (above B40 → recommend+interview); owes birth certificate |
| 6 | Harish | `income_route='str'`, `income_earner='father'` | no STR doc yet; father confirmed via patronymic; income letter RM1,800 |
| 14 | Sharmila | `income_route='str'`, `income_earner='father'` | sibling of #6, same father; no STR doc yet |

Self-served (not hand-edited, listed for completeness): **#20 Sharvani** — salary / father, docs correctly tagged.
Untouched (no income docs to slot): #12, #13, #17, #19.

**Grandfathered already-submitted (profile_complete) — slotted 2026-06-05 so the officer/Check-2 verdict assembles
("as if they'd walked the wizard"). They are NOT re-gated; income resolved at interview.**
| App | Student | Set | Open item |
|---|---|---|---|
| 4 | Theepicaa | `str` / earner `mother` | STR manually validated by user; system copy unread (re-read for cockpit); mother owes BC |
| 9 | Theresa | `str` / earner `mother` | STR is in mother's name (user); owes: STR doc + mother's IC (uploaded one is father's) + BC |
| 8 | Yeswindran | `salary` / `['father']`; parent_ic→father | user: **STR invalid → salary**; has NO salary slip — owes one |
| 21 | Kishanthan | `salary` / `['father']`; parent_ic+salary_slip→father | re-routed from str (old auto-set); fixes the original app#21 "no proof" bug |
| 15 | Pavalaharasi | `salary` / `['father']`; docs tagged father | clean (father gross RM2,400) |
| 10 | Taanusiya | `salary` / `['mother']`; docs tagged mother | mother owes BC (gross RM3,048) |
| 11 | Nesha | `salary` / `['mother']`; docs tagged mother | salary slip unread; mother owes BC |

STR validity (user manual check 2026-06-05): Theepicaa = valid → STR; Yeswindran = invalid → salary. System copies
still unread until the TD-085 re-extraction backfill (cosmetic for the cockpit, not the routing).

## Parked / FYI — post-consent summary page (NOT in TD-085 scope; future, do not build yet)
Flow: `Application pages → Consent → [Summary page, NEW] → Continue → "Thank you, you'll hear from us"`; **Back** →
Consent → student edits the Application pages.
- **Summary** = a one-glance recap of EVERYTHING the student submitted (name, IC, story, funding, documents, income
  route/earner, etc.) — "one final look at what they're submitting." Read-only recap; some fields reachable for edit via
  Back (e.g. story), some not (e.g. IC). Likely reuses the student-facing fact-summary concept (cousin of the officer
  fact display).
- **Continue = the real submit** (stamps `profile_complete`, notifies admin). **Until this is built, Consent remains the
  submit** (current behaviour).
- **Back** keeps the student un-submitted and fully editable.
- **After Continue → "Thank you" → LOCKED.** Edits only via officer queries (which may edit the locked response).
- **Current lock (corrected 2026-06-05 — verified in code + a real screenshot; supersedes the earlier "lock is new"
  note):** the student-facing lock ALREADY EXISTS. `app/scholarship/application/page.tsx` renders the editable form ONLY
  when `status === 'shortlisted'`; once consent flips the status to `profile_complete`, the page shows the **"Application
  received"** thank-you screen (`pendingApplication.receivedTitle/receivedBody`) — the student CANNOT edit the
  application or upload documents themselves. They can still edit some PROFILE fields (name, address, results) on the
  separate profile surface. The backend `POST_SHORTLIST_EDITABLE` stays open only so OFFICER QUERIES can reopen specific
  items (the "queries edit a locked response" path), NOT student self-edit.
- **So the feature is small:** the lock is NOT new. What's new = (1) the summary page between consent and the commit,
  and (2) moving the commit/lock trigger from Consent to **Continue** (Back keeps the app at `shortlisted` = editable).

## ✅ DONE (2026-06-05) — utility-bill facts enhancement
**Built + tested; both open questions confirmed YES + the `?` dropped from labels.** The officer cockpit utility-bill
row now shows **Address · Current · Reasonable** (+ **Outstanding** only when arrears > charge), plus an **orange note**
when the account holder is neither the student nor any uploaded parent IC. **Reasonable = combined water+electricity
per-capita** (one bill → grey + "water/electricity bill only" note, never a faked verdict); **Current = within ~3 months
of the review date**; high consumption stays amber (soft proxy, never red). Backend `income_engine.utility_check` (+
`utility_reasonable` + `_parse_billing_month`/`_utility_currency` + `_utility_name_unrelated`); `officerCockpit.
documentFacts` extended; FE `UtilityCheck` type; cockpit `docRow` notes; i18n `docsDrawer.fact.reasonable`/`outstanding`
\+ `docsDrawer.utilityNote.{unrelated,water_only,electricity_only}` (en/ms/ta). No migration. Gates: 723 scholarship
pytest + 258 jest + next build clean + i18n parity 2019. The original spec follows for the record.

## (BUILT — see above) utility-bill facts enhancement
Live-testing follow-up (2026-06-05): the officer cockpit utility-bill row currently shows only **Address**. The user
wants it to tell the officer whether the bill is recent, reasonable, and whether there are arrears, plus flag an
unrelated account holder. The extraction already captures `billing_period`, `amount` (current charge), `unpaid_balance`,
`name` — so no new extraction, no migration.

Proposed utility-bill fact labels (in `officerCockpit.documentFacts` + backend `income_engine.utility_check`):
- **Address** — (existing) bill address vs home address → 🟢 / 🔴 / grey.
- **Current** — `billing_period` within ~3 months of the review date → 🟢 current / 🟡 older / grey if no date.
- **Reasonable** — the COMBINED household utility per-capita (water+electricity ÷ household size) vs the existing
  `utility_per_capita` thresholds (RM25 / RM40 per capita) → 🟢 B40-consistent / 🟡 high / grey. (Both bills show the
  same household verdict; reuses existing logic.)
- **Outstanding** — shown ONLY when arrears > current charge (a genuine hardship signal); 🟢 when shown, hidden otherwise.
- **Orange note** (like the salary-slip warning) when the bill is in someone else's name — account holder doesn't match
  the student or any uploaded parent IC. (e.g. Theepicaa's water bill is in "Rajeswari A/P Ramolingom".)

Scope: `income_engine.utility_check` (+ a billing_period date parser) · `documentFacts` utility facts + conditional
Outstanding · the orange name note in the cockpit `docRow` · i18n (Current/Reasonable/Outstanding labels + the note) ·
jest/pytest. **2 OPEN QUESTIONS awaiting the user's nod before building:** (1) "Reasonable" = the *combined* household
utility per-capita (vs each bill on its own)? (2) "Current" = within 3 months of *now* (review time), not the
application date? — both proposed YES.

## Test plan (before any deploy)
- STR route: father (no extra) / mother (BC) / guardian (letter) — each missing doc blocks; complete set passes.
- Salary route: single father; mother+brother both working (each needs IC + slip); mother needs BC.
- EPF-only member → blocked (salary slip required).
- Offer letter missing → blocked for everyone.
- Grandfathering: a `profile_complete` app failing v2 is NOT reverted; a `shortlisted` app is gated on v2.
- Identity/NRIC mismatch still blocks (unchanged).
