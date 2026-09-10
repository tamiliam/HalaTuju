# Plan — the officer screens say "B40" about gifts that are not B40

**Status:** ✅ **BUILT 2026-09-10** on `feat/officer-income-vocabulary`. Owner approved logging it
as its own sprint, 2026-09-09. Shape (b) taken, as recommended in §4. Twelve strings, not eleven —
`utility_percapita_high` ("M40/T20") carried the identical fault in the other direction and was
missing from §3's list. See §7 below for what the build found that this plan did not know.
**Size:** one sprint, small. ~8 files. **Probably NO migration** — see §4.
**Trigger:** BrightPath **Sabah**, expected live ~2 weeks from 2026-09-09. Owner, 2026-09-09:
*"each gift would have its own text and preferences. And they need not be B40 focused."*

---

## 1. ⚠ THE OWNER'S FIRST FRAMING WAS WRONG, AND THE CORRECTION IS THE POINT

The owner asked (2026-09-09): *"If these are programme specific — i.e. not at org level — then they
should be linked to the gift's name, which is set in the Configuration page."*

**They must not be linked to the gift's name.** In every one of these strings **B40 is Malaysia's
national income band — the bottom 40% — not the name of a gift.** Substituting the gift's name
produces nonsense:

| Today | With the gift's name substituted |
|---|---|
| `Income (B40)` | `Income (BrightPath Sabah)` |
| `Per-capita income RM4,200 is over the B40 line (RM1,584)` | `…is over the BrightPath Sabah line` |
| `STR document verified — B40 status confirmed.` | `…BrightPath Sabah status confirmed` |

The owner accepted this correction on 2026-09-09 (*"2. OK"*). **Do not re-propose the name
substitution.**

## 2. The real defect, which the owner was correctly pointing at

**A gift may run no B40 means test at all, and the officer screen says B40 anyway.**

The rules already support this. Sabah S2a (2026-09-02) made every threshold nullable, where
**NULL means the test is not applied**. `income_ceiling` and `per_capita_ceiling` are among them,
and it is not hypothetical — measured on production 2026-09-09:

| Round | `income_ceiling` | `per_capita_ceiling` |
|---|---|---|
| `b40-2026` (BrightPath) | 5860 | 1584 |
| `test` (Test Programme) | **NULL** | **NULL** |

So a gift with no income ceiling already exists, and its officer verdict card still reads
"Income (B40)" and reasons about "the B40 line".

## 3. The eleven strings

Measured 2026-09-09 (`en.json`, ×3 locales):

```
admin.scholarship.verdict.fact.income                      "Income (B40)"
admin.scholarship.verdict.item.income_above_b40_line
admin.scholarship.verdict.item.income_per_capita_ok
admin.scholarship.verdict.item.income_salary_probable
admin.scholarship.verdict.item.income_salary_unsure
admin.scholarship.verdict.item.income_declared_accepted_str
admin.scholarship.verdict.item.str_verified
admin.scholarship.verdict.item.str_not_current_rejected
admin.scholarship.verdict.item.utility_percapita_b40
admin.scholarship.agenda.needsInterview.income_above_b40_line
admin.scholarship.anomaly.household_size_one.fact
```

**They split into two kinds, and the split is the whole design:**

- **Threshold language** — "the B40 line", "over the B40 line", "Income (B40)". These describe a
  ceiling the gift may not have. **These are the sprint.**
- **STR language** — `str_verified`, `str_not_current_rejected`. **STR is a real, named Malaysian
  government programme.** Saying "STR document verified" is correct wherever STR is used, whatever
  the gift is called. **Do not rename these** — only the trailing *"— B40 status confirmed"* clause
  is in scope.

## 4. Shape (to be confirmed at sprint-start, not decided here)

Two candidates, and the second is probably right:

**(a) Let an organisation NAME its income band** — a new setting, so a gift can say "M40" or
"low-income". Cost: another tenant-editable string, another translation surface, and a name that
can drift from the ceiling it describes.

**(b) Say what the numbers actually say, and drop the band label.** *"Per-capita income RM4,200 is
over the line (RM1,584)"*; the fact tile reads **"Income"**. When a gift sets **no** ceiling, the
income fact should not claim a threshold at all — it should read as un-means-tested rather than as
passing a B40 test it never ran.

**Recommendation: (b).** It needs **no new stored field and probably no migration**, it cannot
drift from the ceiling, and it is honest for a gift with NULL ceilings — which is the case that
actually breaks. (a) can follow later if a tenant asks for it by name.

⚠ **The number must keep coming from the round's own `income_ceiling` / `per_capita_ceiling`.** It
already does. This sprint changes wording and the no-ceiling branch, **not** the means test.

## 5. What must not be tidied

- **Never derive this from the gift's name.** §1.
- **STR keeps its name.** It is a government programme, not our vocabulary.
- **The engine is not in scope.** `income_engine` / `verdict_engine` maths, the ceilings, the bands
  and `MODEL_VERSION` are untouched. **This is a wording and empty-state sprint.** If a verdict band
  moves, something is wrong.
- **BrightPath must read as it does today** wherever it has ceilings set. Its officers have been
  reading these lines for months; the only visible change for them should be dropping the "B40"
  label, and even that is worth showing the owner before it ships.

## 6. Out of scope

- The **student-facing** B40 copy on the apply page — that is the separate, already-planned sprint
  `2026-09-09-apply-page-copy-per-gift.md`.
- The landing page and the sign-in prompt (`scholarship.landing.req.item2`, `authGate.applyReason`)
  — same class, different pages, still unlogged as work.
- The two **sponsor-facing** B40 strings on the sponsor landing.

---

## 7. What the build found that this plan did not know (2026-09-10)

**§2 understated the defect.** The plan says a NULL-ceiling gift "still reads Income (B40)". It
does — and it also tells the officer something false about the documents:

```python
# income_engine.income_headroom, line ~1411
if pc is None or not size or not pc_ceiling:
    return 'unknown', {'all_known': all_known}
```

`not pc_ceiling` is **the gift having no income test**. It returns the SAME band as *"we could not
read the documents"*, and 'unknown' prints:

> "Income can't be document-verified (informal / no payslip) — confirm during the interview…"

On the Test round (both ceilings NULL) the payslips may read perfectly. **The engine conflated a
property of the GIFT with a defect in the EVIDENCE**, and the screen renders them identically.

**Built as a predicate, not a new band.** `income_engine.income_test_configured(application)` asks
the cohort directly. `income_headroom`'s return set is untouched, so no caller of it is dragged
into a wording sprint. New item code `income_not_means_tested`; **the verdict status does not
move** — amber before, amber after, a test pins it.

**Both codes are written as literals.** `test_verdict_item_i18n` walks the AST for `_item('...')`
and caught the first version, which chose the code with a conditional inside the call. A dynamic
code escapes the guard that stops a raw key path rendering in the cockpit.

**`profile_engine.py` is LOGGED, NOT BUILT.** It holds a second, larger B40 vocabulary — the
sponsor-facing profile prompt, `_BELOW_LINE_AFFIRM`, `_ABOVE_LINE_CAUTION`, and
`_OFFICER_FACT_LABELS['income'] = 'Household income (B40 need)'`. It is deliberately untouched:
every edit there requires a `PROMPT_VERSION` bump, which re-dates every existing profile draft on
production — a data and cost consequence well outside "wording and empty state". ⚠ The label is
now the twin that can go stale; treat it as owed work, not as a settled state.
