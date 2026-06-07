# Verification verdict — confidence bands & per-fact checks

The officer cockpit's **Verification verdict** tiles read as a confidence scale — Sherman
Kent's *words of estimative probability*, collapsed to four bands. Each tile's colour says
**how sure the engine is that the fact is sound**, and the human effort rises as confidence
falls.

Source of truth: `apps/scholarship/verdict_engine.py` (statuses) and
`halatuju-web/src/lib/officerCockpit.ts` (`factTileTone`, colours/labels).

## The four bands

| Colour | Band (Kent) | Status | Meaning | Officer's job |
|---|---|---|---|---|
| 🟢 Green | **Certain** (~90–100%) | `verified` | Checks passed | Audit |
| 🔵 Blue | **Probable** (~75%) | `review` **with ≥1 verified value** | Likely sound; one thing to confirm | Confirm the flag |
| 🟡 Amber | **Unsure** (~50%) | `recommend`, **or** `review` with no verified value | Even odds / nothing verified yet / a B40 call | Own the decision |
| 🔴 Red | **Can't verify** (≤30%) | `gap` | Missing / unreadable / unusable evidence | Get a usable document first |

Two rules that shape the colours:

1. **Blue requires a green.** A `review` fact is Blue **only if it carries at least one
   genuinely-verified value**. Backed only by a self-declaration (`pathway_declared`) or a
   soft signal (utility per-capita / hardship) — or by nothing — it drops to 🟡 Unsure.
   (`SOFT_EVIDENCE` in `officerCockpit.ts`.)
2. **The gate bounces the hard fails.** Some low-confidence cases never reach an officer:
   the **submission gate** (`services.application_completeness` / `consent_blockers`) blocks
   them and makes the student re-upload — see the per-fact notes. The verdict still shows
   the matching colour for any pre-submission app an officer opens.

## Per-fact checks and how they band

### Identity — the MyKad (`_verdict_identity`)
Anchor = **NRIC** (exact). Secondary = **name** (match / OCR-truncation subset / disjoint).
Identity **never auto-fails** — a mismatch is a confirm, not a fraud verdict.

- 🟢 **Certain** — NRIC ✓ and name ✓ (a pure OCR truncation auto-resolves; the NRIC anchors).
- 🔵 **Probable** — NRIC ✓ but the name reads disjoint/odd (the NRIC carries identity; the
  name is usually an OCR miss on a good card).
- 🟡 **Unsure** — the OCR *service* was down (couldn't check; confirm later).
- 🔴 **Can't verify** — IC missing or unreadable.
- **Gate:** the student **cannot submit** with a **NRIC mismatch** or an **unreadable/missing
  IC** — those bounce for re-upload (so "both wrong" never reaches a submitted verdict). A
  name mismatch with a matching NRIC does **not** block (the NRIC proves identity).

### Academic — the results slip (`_verdict_academic`)
Anchor = the slip's **name** (its ownership key). Content = **completeness** (every subject
entered) + **accuracy** (typed grades = slip grades).

- 🟢 **Certain** — name ✓ + complete + accurate.
- 🔵 **Probable** — name ✓ but a subject is missing / a grade differs / a grade is "check by
  eye" / grades not yet read (the slip is provably theirs; confirm the cell).
- 🟡 **Unsure** — name not yet decided (`pending`) with grades unread (nothing verified).
- 🔴 **Can't verify** — slip **missing**, **or a name MISMATCH**: a slip in someone else's
  name is unusable — matching grades can't be credited to the student.
- **Gate:** a **slip-name mismatch fails the submission bar** — the student must re-upload
  their own slip. ('pending' / 'unreadable' / 'match' pass; only a positive mismatch blocks.)

### Pathway — the offer letter (`_verdict_pathway`)
Anchor = offer **identity** (name + IC). Then the offer is reconciled against the declared
pathway.

- 🟢 **Certain** — offer identity ✓ and it agrees with the declared pathway (or the student
  confirmed it).
- 🔵 **Probable** — offer identity ✓ but the offer/declaration clash → "is this the final
  one?" (record realigns on the student's Yes).
- 🟡 **Unsure** — an offer is present but its identity can't be read (`offer_no_identity` /
  `offer_unreadable` / `offer_name_mismatch`) — nothing verified.
- 🔴 **Can't verify** — **no offer letter.** The programme supports a *confirmed place*;
  without an offer there is nothing to fund (income can be settled at interview, a pathway
  cannot).
- **Gate:** the **offer letter is compulsory** — `offer_letter_missing` is a `consent_blockers`
  code, so a student cannot submit without one.

### Income — the cluster (STR or salary route) (`_verdict_income` / `_verdict_income_salary`)
The only fact that uses **all four bands**, and the only one that can be 🟡 via `recommend`
("evidence assembled, a human places the B40 call"). Checks: wizard walked · earner/member
IC · relationship (father = patronymic, mother = birth cert, guardian = letter) · STR current
+ recipient = earner **or** payslip/EPF · utility bills (soft).

- 🟢 **Certain** — the whole cluster adds up: a current STR to the earner + earner IC +
  relationship confirmed (STR route); or every IC + every relationship + ≥1 payslip/EPF
  (salary route).
- 🔵 **Probable** — a check fails/unconfirmed *and* something is verified (e.g. earner IC in,
  STR not current).
- 🟡 **Unsure** — B40 can't be document-proven (informal/no-EPF, or an unprovable
  relationship) → officer places it at interview (`recommend`); **or** the wizard isn't
  walked / nothing verified yet (`review` with no green).
- 🔴 **Can't verify** — a compulsory income doc is missing (earner/member IC, birth cert,
  guardianship letter, or STR).

### Other — supporting documents
The Documents-panel catch-all for any doc type that isn't one of the four facts. **No band,
no tile** — it contributes nothing to the verdict. (Utility bills *do* matter, but as soft
income evidence folded into the Income tile, never a gate.)

## Which bands each fact can show

| | 🟢 Certain | 🔵 Probable | 🟡 Unsure | 🔴 Can't verify |
|---|:--:|:--:|:--:|:--:|
| Identity | ✓ | ✓ | ✓ (service down) | ✓ |
| Academic | ✓ | ✓ | ✓ | ✓ |
| Pathway | ✓ | ✓ | ✓ | ✓ |
| Income | ✓ | ✓ | ✓ | ✓ |
| Other | — | — | — | — |
