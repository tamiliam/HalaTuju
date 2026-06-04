# Check‑1 Income — Implementation Plan (item 3: earner identity + relationship)

Status: **DRAFT for refinement** (schema approved 2026‑06‑04). Last of the four facts (TD‑081 residual).

## Objective
Turn the Income fact from a weak "is a document present?" check into a clinical Check‑1 that proves
**who the earner is** and **that they are the student's family**, driven by a guided document wizard that
shows exactly the documents a given family needs (compulsory) plus optional credibility boosters.

## Scope
- **In:** the earner‑identity + relationship verification, the guided wizard, the Birth Certificate doc type,
  the requirement engine, the income‑verdict rewire, officer + student + Gopal copy, the section ordering.
- **Out (hooks left, no schema change needed later):** reading the income **amount** → per‑capita B40 test
  (item 1); the utility‑bill **hardship** signal. Both layer on top of this structure in a later slice.

## Section order (requirement)
Everywhere — student Documents tab, officer verdict tiles, apply/admin groupings:
**Identity → Academic → Pathway (offer letter) → Income**, with the income wizard sitting **under Income**.
Already true in the student tab + officer tiles; audit + align the one inconsistent spot
(`admin-api.ts` fact union) and any apply‑form grouping.

---

## Approved schema (reference)

### Stored wizard answers — `ScholarshipApplication` (additive)
```
income_route        ''|'str'|'salary'                      # Q1 "have an STR document?"  yes→str / no→salary
income_earner       ''|'father'|'mother'|'guardian'         # Q2 main income earner
earner_work_status  ''|'payslip'|'informal'|'not_working'   # Q3 (salary route only)
```
`receives_str` (existing, profile) stays — "family receives STR", distinct from "has the document". v1 = one
primary earner (multi‑earner = a repeatable block, deferred).

### Household context — means‑test integrity + family burden (additive)
Captured in the wizard, surfaced to the officer as Income context (not hard gates).
```
household_other_earners   ''|small int   # Q4 (non‑STR only): other working household members (e.g. a working sibling)
siblings_in_school        small int      # family burden — dependents in school
siblings_in_tertiary      small int      # family burden — dependents in pre‑U / college / degree
```
- **Working sibling (non‑STR):** a sibling earning at home adds to household income → asking guards against an
  under‑declared household figure (STR families are already means‑tested, so skip for them). If "yes", invite (optional)
  their income proof too; always surface to the officer.
- **Burden (school vs tertiary):** more children in education = higher family burden = stronger need; tertiary
  dependents weigh more (fees). Refine the existing `siblings_studying_count` (S15) into school + tertiary
  (expand‑contract; the sum = studying) rather than duplicating.

### Document types
Reused: `str`, `salary_slip`, `epf`, `parent_ic` (= "earner IC", parent **or** guardian), `water_bill`,
`electricity_bill`, `guardianship_letter`.
**New:** `birth_certificate` — OCR fields stored in `vision_fields` (no new columns):
`bc_child_name`, `bc_mother_name`, `bc_father_name`, `bc_number`.

### Requirement matrix — `income_requirements(application) → {compulsory[], optional[]}`
Always compulsory: earner IC (`parent_ic`) + relationship proof —
father → *(none, derived from student‑IC patronymic)* · mother → `birth_certificate` · guardian → `guardianship_letter`.

| route / work‑status | compulsory income docs | optional (credibility) |
|---|---|---|
| STR | `str` | water + electricity bills, salary slip, EPF |
| salary · payslip | `salary_slip` + `epf` | water + electricity bills |
| salary · not_working | `epf` | water + electricity bills |
| salary · informal | `water_bill` + `electricity_bill` (address‑matched) | EPF if any, free‑text note |

### Per‑document deterministic checks
```
parent_ic (earner IC):  NRIC valid + name extracted                         → anchors the earner
relationship:
  father    → student‑IC patronymic father‑name == earner‑IC name
  mother    → BC.mother_name == earner‑IC name  AND  BC.child_name == student name
  guardian  → guardianship_letter name          == earner‑IC name
str:         STR name == earner · STR NRIC == earner NRIC · year recent (currency)
salary_slip: name == earner          (amount → item‑1 layer, later)
epf:         name == earner
water/elec:  vision_address == application address   (balance/usage → hardship, later)
```

### Income verdict roll‑up (reuses verified / review / recommend / gap)
```
earner undeclared (wizard blank)        → review     (income_earner_undeclared)
a compulsory doc missing                → gap        (lists which)
a compulsory check fails                → review     (the specific reason)
STR route, all compulsory pass          → verified
salary route, all compulsory pass       → recommend  (human still places the B40 amount call)
optional docs                           → evidence only, never block
```

### Never‑block, flag‑for‑interview (the soft floor)
A genuinely poor family may be unable to produce formal proof — a non‑working parent/guardian with **no EPF**, an
informal earner with only bills. We **do not block** these. Instead the verdict is `recommend` with a soft
`income_unverified_needs_interview` signal that flows into the **interview gap‑spotter** (existing `gap_engine` /
anomaly engine): "income claim not document‑verified — confirm during the interview via household size, dependents,
lifestyle, and the burden signals." So the deterministic layer surfaces the concern; a **human** makes the
subjective call. The burden signals (siblings in school/tertiary, household earners) feed that judgement.

### Student framing (encouraging, never punitive)
The wizard intro explains in plain language: **the more you can share, the faster we can approve and the less likely
a delay or rejection** — and that nothing here blocks the application; missing items just mean a person reviews it by
hand. Optional docs are framed as "adds credibility / speeds approval", not "you failed to provide X".

### New reason codes (full chain each: verdict_engine → CODE_TO_TICKET → 2 i18n blocks ×3 → actionCentre.KNOWN_CODES)
`income_earner_undeclared` · `earner_ic_missing` / `earner_ic_unreadable` · `father_patronymic_mismatch` ·
`birth_cert_missing` / `birth_cert_mismatch` · `guardianship_letter_missing` (reuse if exists) ·
`str_year_stale` · `salary_epf_missing` · `utility_address_mismatch` ·
`income_unverified_needs_interview` (soft → interview prompt, never a gap).
Reused: `income_proof_missing`, `str_claimed_no_doc`, `str_present_unverified`, `str_verified`.

---

## Phased implementation

### Sprint I1 — Backend foundation: data model + requirement engine + BC reader (no UI)
**Deliverable:** the pure logic + storage that everything else consumes; fully unit‑tested in isolation.
- **Migration (additive, migrate‑first via Supabase MCP):** `income_route`, `income_earner`,
  `earner_work_status` on `ScholarshipApplication`; `birth_certificate` added to `ApplicantDocument.DOC_TYPES`
  (choices‑only — BC OCR fields live in `vision_fields`, no new columns). Confirm `Meta.db_table` before any raw ALTER.
- **`income_engine.py` (NEW, pure):** `income_requirements(application)`; relationship checks
  `father_patronymic_match` / `mother_bc_match` / `guardian_letter_match`; per‑doc check helpers; a
  `father_name_from_ic(name)` patronymic parser (after `A/L`/`A/P`/`bin`/`binti`).
- **BC reader (`vision.py`):** `_DOC_HINTS['birth_certificate']` Gemini prompt → child/mother/father names;
  store in `vision_fields`. Mock the `_call_gemini_json` seam in tests.
- **Tests:** requirement matrix for every (route × earner × work‑status); each relationship check
  (match / mismatch / unreadable); patronymic parser (A/L, bin, mixed, none).
- **Files (~8):** `income_engine.py` (+test), `vision.py`, `models.py` (choices), migration, maybe `serializers.py`
  to surface BC fields. **Backend only.**

### Sprint I2 — Income verdict rewire + reason codes + officer Income tile
**Deliverable:** the officer sees the assembled, per‑earner verdict; the resolution/Action‑Centre chain is whole.
- **`verdict_engine._verdict_income` rewritten** to drive off `income_requirements` + the per‑doc checks →
  verified / recommend / review / gap with the new reason codes (keep `str_verified` fast path).
- **Full reason‑code chain:** `resolution.CODE_TO_TICKET` entries · officer i18n
  (`admin.scholarship.verdict.item.*`) · student ticket i18n (`scholarship.actionCentre.item.*`) ·
  `actionCentre.ts KNOWN_CODES` — all ×3 locales. (Checklist from the Sharvin/`offer_no_identity` lesson.)
- **Officer cockpit:** Income tile lists which compulsory docs are missing/failing + the relationship status.
- **Tests:** verdict roll‑up per scenario (STR‑verified, salary‑recommend, missing‑BC‑review, father‑mismatch,
  informal‑utilities, undeclared); i18n parity; resolution‑ticket mapping.
- **Files (~10):** `verdict_engine.py`, `resolution.py`, 3 message files, `actionCentre.ts`, officer component,
  tests. **Backend + officer FE + i18n.**

### Sprint I3 — Student wizard UI + dynamic checklist (Stitch‑first)
**Deliverable:** the student‑facing guided wizard under the Income section; the feature goes live end‑to‑end.
- **Stitch mockup FIRST** (mandatory): the 3‑question flow + the dynamic compulsory/optional checklist; get
  visual approval before coding templates.
- **Pure `lib/incomeWizard.ts`** (node‑jest): answers → `{compulsory[], optional[]}` (mirrors `income_engine`),
  so the checklist is testable without the DOM.
- **Wizard component** under the Income section of the Documents tab — questions →  POST answers → render the
  tailored checklist reusing the existing card/chip/upload pattern; compulsory `*` + "adds credibility" labels.
  Questions: **Q1** STR document? · **Q2** main earner (father/mother/guardian) · **Q3** (salary) work status
  (payslip / informal / not working) · **Q4** (non‑STR) anyone else in the household earn? (working sibling) ·
  **burden** siblings in school / in pre‑U‑college‑degree. Encouraging intro ("share more → faster, avoid rejection;
  nothing blocks you").
- **Section order:** confirm Identity·Academic·Pathway·Income everywhere; align `admin-api.ts` union + any apply grouping.
- **Gopal copy** for the new income verdicts (firewall‑safe; same pattern as slip/offer): missing‑BC,
  father‑mismatch‑please‑check, utilities‑address, etc., en/ms/ta + fallbacks.
- **Tests:** `incomeWizard` jest (every branch), wizard render via `next build` typing, i18n parity.
- **Files (~12):** `incomeWizard.ts` (+test), wizard component, `ScholarshipDocuments.tsx`, `api.ts`/types,
  3 message files, Gopal `help_engine` verdicts + `documentHelp.ts`. **Frontend + a little backend (help verdicts).**

### Sprint I4 — DEFERRED: amount‑reading (per‑capita B40 test) + utility hardship signal
Hooks already left in I1's per‑doc checks. Separate slice; not part of item 3.

---

## Migration & deploy discipline
- Additive migrations only; **migrate‑first via Supabase MCP** before pushing `main` (deploy does not run `migrate`).
- No new tables → no RLS work; choices‑only changes need the `django_migrations` row recorded via MCP (TD‑058 pattern).
- Each sprint: full suite green + golden masters intact + `next build` clean (true exit code) + i18n parity before deploy.

## Decisions locked (2026‑06‑04)
1. **Placement:** wizard sits inside **4. Documents → Household income** (dynamic, replacing the static card). If it
   grows unwieldy, promote to its own "5. Income" tab later — in‑Documents is fine for now. ✅
2. **Birth Certificate:** standard JPN cert target; old/handwritten/foreign → officer review, never a hard block. ✅
3. **Informal floor:** earner IC + relationship + utility bills, never‑block + interview flag. ✅
4. **STR recency:** recent window OK (target ~12–18 months; surface the year, soft flag if stale). ✅
5. **Guardian + not working:** same EPF‑only fallback. ✅
+ **Never block; flag for interview** when proof is genuinely unavailable (poor‑family reality). ✅
+ **Household completeness + burden** questions added (working sibling for non‑STR; siblings in school / tertiary). ✅
+ **Encouraging framing** throughout (share more → faster approval, fewer rejections; nothing blocks you). ✅

## Next step
Take **I3's wizard into Stitch** (question flow + dynamic checklist + encouraging copy) for visual approval — then
build **I1 → I2 → I3**.
