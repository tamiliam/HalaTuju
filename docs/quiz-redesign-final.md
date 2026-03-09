# HalaTuju Visual Quiz — Final Design

**Date:** 10 March 2026
**Status:** Final — ready for implementation
**Incorporates:** Advisor 1 review (scoring, grade modulation, Q2.5 branching) + Advisor 2 review (multi-select, "Not Sure", B40 considerations)

---

## Design Decisions Log

| # | Source | Decision | Action |
|---|--------|----------|--------|
| 1 | Advisor 1 | Q2D groups 88 courses indefensibly | Added branching Q2.5 |
| 2 | Advisor 1 | Q7D "Nothing Much" is a skip button | Reframed → "I Can Handle Anything" with `high_stamina` |
| 3 | Advisor 1 | Field interest cap too weak | Raised to ±8, work preference lowered to ±4 |
| 4 | Advisor 1 | Engine must cross-reference grades with quiz | Added Grade Modulation Layer (4 rules) |
| 5 | Advisor 2 | Single-select on Q1/Q2 is fragile | **Multi-select (pick up to 2) on Q1 and Q2** |
| 6 | Advisor 2 | No "I'm not sure" is risky for B40 rural students | **Added 5th "Not Sure Yet" card on Q1, Q2, Q4** |
| 7 | Advisor 2 | Q8D "Best Programme" wastes an option | **Tuning item** — give small boost to pathway/accreditation indicators during implementation |
| 8 | Advisor 2 | Financial constraints underweighted for B40 | **Tuning item** — consider raising institution cap to ±7 or promoting to standalone category |
| 9 | Advisor 2 | Merit penalty (-15) can override entire quiz | **Tuning item** — consider compressing to -10 during implementation |
| 10 | Advisor 2 | Label validation with real students | **Post-build** — test BM/TA labels with 5-10 students before launch |

**Build now (Sprint scope):** Items 1-6
**Tune during implementation:** Items 7-9
**Post-build validation:** Item 10

---

## Quiz Structure

**8 questions + 1 conditional branch.**

- Q1, Q2: **5 cards, multi-select (pick up to 2)** — field interest
- Q2.5: **4 cards, single-select** — conditional branch for heavy industry
- Q3: **4 cards, single-select** — work style
- Q4: **5 cards, single-select** — environment (includes "Not Sure Yet")
- Q5-Q8: **4 cards, single-select** — learning, values, energy, practical

**Estimated completion:** ~90-100 seconds.

---

## The Questions

### Q1: "What catches your eye?" — Field Interest Set 1

**Multi-select: pick up to 2.** Weight splits when 2 selected.

| Card | Icon | Label | Signal | Weight (1 pick) | Weight (2 picks) |
|------|------|-------|--------|:---:|:---:|
| A | Wrench + gears | Build & Fix | `field_mechanical` | 3 | 2 each |
| B | Laptop + code | Tech & Digital | `field_digital` | 3 | 2 each |
| C | Handshake + chart | Business & Money | `field_business` | 3 | 2 each |
| D | Heart + stethoscope | Health & Care | `field_health` | 3 | 2 each |
| E | Question mark + sparkle | **Not Sure Yet** | *(distributes +1 to all 4 fields)* | — | — |

**"Not Sure Yet" behaviour:** Gives +1 to `field_mechanical`, `field_digital`, `field_business`, `field_health`. This slightly boosts all fields equally, ensuring undecided students still get reasonable differentiation from other signals (Q3-Q8). It does NOT count toward multi-select — if a student picks "Not Sure Yet", it is the only selection for Q1.

**Multi-select UX:** Cards toggle on/off. After 2 are selected, the remaining grey out. A "Next" button appears (no auto-advance for multi-select — student needs to confirm). If only 1 is selected, auto-advance after 400ms as normal.

---

### Q2: "And this?" — Field Interest Set 2

**Multi-select: pick up to 2.** Same mechanics as Q1.

| Card | Icon | Label | Signal | Weight (1 pick) | Weight (2 picks) |
|------|------|-------|--------|:---:|:---:|
| A | Paintbrush + ruler | Design & Create | `field_creative` | 3 | 2 each |
| B | Chef hat + suitcase | Food & Travel | `field_hospitality` | 3 | 2 each |
| C | Leaf + tractor | Nature & Farm | `field_agriculture` | 3 | 2 each |
| D | Bolt + ship | Big Machines | `field_heavy_industry` | 3 | 2 each |
| E | Question mark + sparkle | **Not Sure Yet** | *(distributes +1 to all 4 fields)* | — | — |

**If Q2D selected (alone or as part of multi-select):** Q2.5 is shown next.

---

### Q2.5: "Which kind?" — Heavy Industry Branch (CONDITIONAL)

**Single-select. Only shown if Q2D was selected.**

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Lightning bolt | Electrical | `field_electrical` | 3 |
| B | Hard hat + crane | Construction | `field_civil` | 3 |
| C | Airplane + ship | Aero & Marine | `field_aero_marine` | 3 |
| D | Oil rig + flame | Oil & Gas | `field_oil_gas` | 3 |

No "Not Sure" here — if a student picked "Big Machines" they have enough intent to differentiate.

---

### Q3: "Your ideal day at work" — Work Preference

**Single-select, 4 cards.**

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Hands + tools | Hands-On | `hands_on` | 2 |
| B | Brain + lightbulb | Problem Solving | `problem_solving` | 2 |
| C | People + speech bubbles | With People | `people_helping` | 2 |
| D | Pencil + star | Creating Things | `creative` | 2 |

---

### Q4: "Where would you work?" — Environment

**Single-select, 5 cards** (includes "Not Sure Yet" — per Advisor 2, environment exposure varies significantly among B40 rural students).

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Workshop/garage | Workshop | `workshop_environment` | 1 |
| B | Desk + monitor | Office | `office_environment` | 1 |
| C | Trees + sun | Outdoors | `field_environment` | 1 |
| D | Building + people | With Crowds | `high_people_environment` | 1 |
| E | Question mark + sparkle | **Not Sure Yet** | *(no signal)* | 0 |

**"Not Sure Yet" here generates zero signal** — environment is a tie-breaker, not a primary differentiator. An honest "I don't know" is better than a random tap that introduces noise.

---

### Q5: "How do you learn best?" — Learning Style

**Single-select, 4 cards.**

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Hammer + checkmark | Do & Practise | `learning_by_doing` | 1 |
| B | Book + magnifying glass | Read & Understand | `concept_first` | 1 |
| C | Clipboard + group | Projects & Teamwork | `project_based` | 1 |
| D | Repeat/loop arrows | Drill & Memorise | `rote_tolerant` | 1 |

---

### Q6: "After SPM, what matters most?" — Values

**Single-select, 4 cards.**

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Shield + checkmark | Stable Job | `stability_priority` | 2 |
| B | Money + rocket | Good Pay | `income_risk_tolerant` | 2 |
| C | Graduation cap + arrow | Continue Degree | `pathway_priority` | 2 |
| D | Lightning + briefcase | Work Fast | `fast_employment_priority` | 2 |

---

### Q7: "What tires you out?" — Energy

**Single-select, 4 cards.**

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | People crowd + sweat | Too Many People | `low_people_tolerance` | 1 |
| B | Brain + weight | Heavy Thinking | `mental_fatigue_sensitive` | 1 |
| C | Arm + weight | Physical Work | `physical_fatigue_sensitive` | 1 |
| D | Flexed arm + star | I Can Handle Anything | `high_stamina` | 1 |

---

### Q8: "What would help you keep studying?" — Practical Needs

**Single-select, 4 cards.**

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Wallet + coins | Pocket Money | `allowance_priority` | 3 |
| B | House + heart | Near Home | `proximity_priority` | 3 |
| C | Handshake + door | Job Guarantee | `employment_guarantee` | 2 |
| D | Trophy + star | Best Programme | `quality_priority` | 1 |

**Q8D change (per Advisor 2):** No longer empty. Generates `quality_priority` signal with weight 1 — gives a small boost to courses with stronger accreditation or pathway-to-degree indicators. Exact matching rule to be defined during implementation.

---

## Signal Taxonomy — Final

### 6 Categories, 22 Signals

```
field_interest:              field_mechanical, field_digital, field_business, field_health,
                             field_creative, field_hospitality, field_agriculture,
                             field_electrical, field_civil, field_aero_marine, field_oil_gas
                             (cap: ±8)

work_preference_signals:     hands_on, problem_solving, people_helping, creative
                             (cap: ±4)

environment_signals:         workshop_environment, office_environment, field_environment,
                             high_people_environment
                             (cap: ±6)

learning_tolerance_signals:  learning_by_doing, concept_first, project_based, rote_tolerant
                             (cap: ±6, grade-modulated)

value_tradeoff_signals:      stability_priority, income_risk_tolerant, pathway_priority,
                             fast_employment_priority, allowance_priority, proximity_priority,
                             employment_guarantee, quality_priority
                             (cap: ±6)

energy_sensitivity_signals:  low_people_tolerance, mental_fatigue_sensitive,
                             physical_fatigue_sensitive, high_stamina
                             (cap: ±6, grade-modulated)
```

---

## Scoring Engine

### Category Caps

| Category | Cap | Rationale |
|----------|-----|-----------|
| **Field Interest** | **±8** | Primary differentiator |
| **Work Preference** | **±4** | Secondary (reduced to prevent overriding field) |
| Environment | ±6 | Tie-breaker |
| Learning | ±6 | Tie-breaker, grade-modulated |
| Values | ±6 | Moderate |
| Energy | ±6 | Negative filter + stamina boost, grade-modulated |
| Institution | ±5 | Practical needs (allowance, proximity) |
| Merit penalty | -15 to 0 | Reality check (**tuning item: consider -10 to 0**) |

**Global cap: ±20. Score range: 80-120.**

### Field Interest Scoring (Multi-Select)

Students pick up to 2 cards on Q1 and up to 2 on Q2. This can produce 1-4 field signals.

**Matching logic per course:**
1. Check all student field signals against the course's `frontend_label`
2. Best match = primary (+8 before cap)
3. Second-best match = secondary (+4 before cap)
4. Additional matches beyond 2 are ignored (diminishing returns)
5. Category cap ±8 applies after summing

**Tiebreaker when multiple signals have equal weight:** Q1 picks outrank Q2 picks (primacy — Q1 is "what catches your eye first"). If both matching signals come from the same question, the one listed first in the student's selection order is primary. This is deterministic and requires no additional user input.

**"Not Sure Yet" (Q1E / Q2E):** Distributes +1 to each field in that set. Effect: mild, undifferentiated boost — other quiz signals (Q3-Q8) become the primary differentiators for this student.

---

## Grade Modulation Layer

Runs in `ranking_engine.py` before category capping. Cross-references `StudentProfile.grades` with quiz signals.

### Rule 1: Imposter Syndrome Dampening

```
IF mental_fatigue_sensitive > 0
AND course load = "mentally_demanding"
AND student merit >= 75th percentile
THEN penalty = -2 (instead of -6)
```

### Rule 2: Academic Anxiety Routing

```
IF rote_tolerant > 0
AND course learning_style includes "assessment_heavy"
AND student average SPM grade <= D
THEN match_score += 3 (additive, before capping)
```

*Note: Earlier draft used a 1.5× multiplier, but the engine architecture is strictly linear/additive. Converted to flat +3 bonus per Advisor 1 review.*

### Rule 3: Stream-Field Safety Net

```
IF student has Science stream subjects (Physics, Chemistry, Add Maths)
AND student selected non-Science field interest
THEN add +1 to Science-aligned fields (field_electrical, field_digital, field_health)
     (no penalty to chosen field — respect the pivot)
```

### Rule 4: Physical Fatigue — No Modulation

Physical fatigue preference is not modulated by grades. Valid regardless of academic performance.

---

## Tuning Items (Resolve During Implementation or With User Data)

| # | Item | Advisor | Options | Default |
|---|------|---------|---------|---------|
| T1 | Institution modifier cap | Advisor 2 | Raise to ±7, or promote allowance/proximity to standalone category | Keep ±5, revisit with user data |
| T2 | Merit penalty range | Advisor 2 | Compress from [-15, 0] to [-10, 0] | Keep -15, document as intentional design choice |
| T3 | Q8D `quality_priority` matching rule | Advisor 2 | Boost pathway-friendly + regulated courses | Define during implementation |
| T4 | 75th percentile threshold | Advisor 1 | Hardcode from 50 test students, or dynamic | Hardcode initially |
| T5 | "Average SPM grade" definition | Advisor 1 | Mean of all subjects, or core subjects only | Core subjects (BM, BI, Maths, Sejarah) |
| T6 | `value_tradeoff_signals` cap saturation | Advisor 2 | Category has 8 signals in ±6 cap — log hit rate during testing | Add logging, revisit if >50% of students hit cap |

---

## Post-Build Validation

**Label testing (Advisor 2, item 10):** Before launch, show card labels in BM and TA to 5-10 students from the existing cohort. Ask them to explain what each card means in their own words. If they can't, rewrite the label. This takes a day, not a sprint.

**A/B testing (Advisor 1):** Post-launch, compare icon interpretation between rural and urban cohorts. Track which "Not Sure Yet" options are most frequently selected — high usage on a specific question suggests the options need rework.

---

## Implementation Scope

| Task | Effort | Notes |
|------|--------|-------|
| Update `quiz_data.py` — 8+1 Qs × 3 langs, multi-select support | Medium | Q1/Q2 have 5 options; Q2.5 conditional; rest have 4 |
| Add `field_interest` category to `quiz_engine.py` | Small | New 6th category with 11 signals |
| Multi-select processing in `quiz_engine.py` | Small | Weight splitting: 1 pick = 3, 2 picks = 2 each |
| "Not Sure Yet" handling in `quiz_engine.py` | Small | Distribute +1 evenly to category fields |
| Branching logic for Q2.5 | Small | Frontend shows Q2.5 if Q2D selected |
| Field matching rules in `ranking_engine.py` | Medium | Match field signals against `frontend_label` |
| Grade Modulation Layer in `ranking_engine.py` | Medium | 4 rules, reads `StudentProfile.grades` |
| Adjust category caps (field ±8, work ±4) | Small | Constants in `ranking_engine.py` |
| Wire `rote_tolerant`, `high_stamina`, `quality_priority` | Small | New matching rules |
| Remove dead signals from `ranking_engine.py` | Small | Clean up `organising`, `meaning_priority`, etc. |
| Redesign quiz page — card grid + multi-select + branching | Medium | 2×2 grid, toggle cards, conditional Q2.5 |
| Create 37 card icons (9 Qs × 4 cards + 3 "Not Sure" icons) | Medium | Gemini Image or icon set |
| Update quiz tests | Medium | Multi-select, branching, "Not Sure" cases |
| Update ranking tests (new caps, grade modulation) | Medium | New signal category, modulation rules |
| Add `field_cluster` to course data | Small | Map `frontend_label` → field signal |

---

## Appendix: Course Field Distribution

| Field Cluster | Quiz Card | Courses | % |
|---------------|-----------|---------|---|
| Mekanikal & Automotif | Q1A | 68 | 22% |
| Perniagaan & Perdagangan | Q1C | 54 | 17% |
| Elektrik & Elektronik | Q2.5A | 38 | 12% |
| Pertanian & Bio-Industri | Q1D / Q2C | 30 | 10% |
| Sivil, Seni Bina & Pembinaan | Q2.5B | 29 | 9% |
| Hospitaliti, Kulinari & Pelancongan | Q2B | 26 | 8% |
| Komputer, IT & Multimedia | Q1B | 23 | 7% |
| Aero, Marin, Minyak & Gas | Q2.5C/D | 21 | 7% |
| Seni Reka & Kreatif | Q2A | 20 | 6% |
| **Total** | | **309** | **100%** |
