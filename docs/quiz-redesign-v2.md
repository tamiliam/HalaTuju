# HalaTuju Quiz Redesign v2 — Final Design

**Date:** 10 March 2026
**Status:** Incorporates Advisor 1 review feedback
**Previous version:** `docs/quiz-redesign-review.md` (v1, pre-review)

---

## Summary of Changes from v1

| # | Advisor Feedback | Action Taken |
|---|-----------------|--------------|
| 1 | Q2D "Energy & Machines" groups 88 courses indefensibly | Added branching Q2.5 for Q2D selectors |
| 2 | Q7D "Nothing Much" is a disguised skip button | Reframed as "I Can Handle Anything" → `high_stamina` signal |
| 3 | Field Interest +6 cap is disproportionately weak | Raised field interest cap to **+8**, reduced work preference cap to **+4** |
| 4 | Engine must cross-reference grades with quiz signals | Added Grade Modulation Layer in ranking engine |
| 5 | Dropped signals should stay dropped | Confirmed — grades handle academic anxiety |
| 6 | A/B test icons with rural vs urban cohorts | Noted for post-launch iteration |

---

## System Architecture

```
SPM Grades (deterministic)          Quiz (subjective)
        │                                  │
        ▼                                  ▼
┌─────────────────┐              ┌──────────────────┐
│ Eligibility     │              │ Signal Taxonomy   │
│ Engine          │              │ (6 categories,    │
│ → Yes/No per    │              │  21 signals)      │
│   course        │              └────────┬─────────┘
└────────┬────────┘                       │
         │                                │
         ▼                                ▼
┌─────────────────────────────────────────────────┐
│              Ranking Engine                      │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │ Grade Modulation Layer (NEW)            │    │
│  │ • Dampens imposter-syndrome penalties   │    │
│  │ • Boosts rote_tolerant for weak grades  │    │
│  │ • Cross-references stream with field    │    │
│  └─────────────────────┬───────────────────┘    │
│                        ▼                         │
│  ┌─────────────────────────────────────────┐    │
│  │ Signal-Tag Matching                     │    │
│  │ Field Interest (cap ±8)                 │    │
│  │ Work Preference (cap ±4)               │    │
│  │ Environment (cap ±6)                    │    │
│  │ Learning (cap ±6)                       │    │
│  │ Values (cap ±6)                         │    │
│  │ Energy (cap ±6)                         │    │
│  │ Institution Modifier (cap ±5)           │    │
│  │ Merit Penalty (-15 to 0)               │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  Global cap: ±20 → Score range: 80-120          │
└─────────────────────────────────────────────────┘
```

---

## The Quiz: 8 Questions + 1 Conditional Branch

### Q1: "What catches your eye?" — Field Interest (Set 1)

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Wrench + gears | Build & Fix | `field_mechanical` | 3 |
| B | Laptop + code | Tech & Digital | `field_digital` | 3 |
| C | Handshake + chart | Business & Money | `field_business` | 3 |
| D | Heart + stethoscope | Health & Care | `field_health` | 3 |

**Field → Course mapping:**
- `field_mechanical` → Mekanikal & Automotif (68 courses)
- `field_digital` → Komputer, IT & Multimedia (23 courses)
- `field_business` → Perniagaan & Perdagangan (54 courses)
- `field_health` → Pertanian & Bio-Industri health subset (30 courses)

---

### Q2: "And this?" — Field Interest (Set 2)

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Paintbrush + ruler | Design & Create | `field_creative` | 3 |
| B | Chef hat + suitcase | Food & Travel | `field_hospitality` | 3 |
| C | Leaf + tractor | Nature & Farm | `field_agriculture` | 3 |
| D | Bolt + ship | Big Machines | `field_heavy_industry` | 3 |

**Field → Course mapping:**
- `field_creative` → Seni Reka & Kreatif (20 courses)
- `field_hospitality` → Hospitaliti, Kulinari & Pelancongan (26 courses)
- `field_agriculture` → Pertanian & Bio-Industri (30 courses)
- `field_heavy_industry` → triggers Q2.5 (see below)

---

### Q2.5: "Which kind?" — Heavy Industry Branch (CONDITIONAL)

**Only shown if student selected Q2D ("Big Machines").**

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Lightning bolt | Electrical | `field_electrical` | 3 |
| B | Hard hat + crane | Construction | `field_civil` | 3 |
| C | Airplane + ship | Aero & Marine | `field_aero_marine` | 3 |
| D | Oil rig + flame | Oil & Gas | `field_oil_gas` | 3 |

**Field → Course mapping:**
- `field_electrical` → Elektrik & Elektronik (38 courses)
- `field_civil` → Sivil, Seni Bina & Pembinaan (29 courses)
- `field_aero_marine` → Aero, Marin subset of Aero/Marin/Minyak & Gas (≈10 courses)
- `field_oil_gas` → Oil & Gas subset of Aero/Marin/Minyak & Gas (≈11 courses)

**UX:** Same 2×2 card grid, same auto-advance. Adds ~10 seconds for affected users only. Non-Q2D users skip this entirely.

**Implementation:** `field_heavy_industry` is replaced by the specific sub-signal. If Q2D is selected but Q2.5 is somehow skipped (edge case), fall back to boosting all three parent fields equally at reduced weight (+1 each).

---

### Q3: "Your ideal day at work" — Work Preference

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Hands + tools | Hands-On | `hands_on` | 2 |
| B | Brain + lightbulb | Problem Solving | `problem_solving` | 2 |
| C | People + speech bubbles | With People | `people_helping` | 2 |
| D | Pencil + star | Creating Things | `creative` | 2 |

**Matching rules:**
| Condition | Points | Category |
|-----------|--------|----------|
| `hands_on` > 0 AND `work_modality` = "hands_on" | +4 | work_preference |
| `hands_on` = 0 AND `work_modality` = "hands_on" | -3 | work_preference |
| `problem_solving` > 0 AND `work_modality` = "mixed" | +3 | work_preference |
| `people_helping` > 0 AND `people_interaction` = "high_people" | +4 | work_preference |
| `creative` > 0 AND `learning_style` includes "project_based" | +4 | work_preference |
| `creative` > 0 AND `creative_output` = "expressive" | +4 | work_preference |
| `creative` > 0 AND `creative_output` = "design" | +3 | work_preference |

**Category cap: ±4** (reduced from ±6 per advisor recommendation — field interest is primary, work preference is secondary)

---

### Q4: "Where would you work?" — Environment

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Workshop/garage | Workshop | `workshop_environment` | 1 |
| B | Desk + monitor | Office | `office_environment` | 1 |
| C | Trees + sun | Outdoors | `field_environment` | 1 |
| D | Building + people | With Crowds | `high_people_environment` | 1 |

**Matching rules:**
| Condition | Points |
|-----------|--------|
| `workshop_environment` > 0 AND `environment` = "workshop" | +4 |
| `office_environment` > 0 AND `environment` = "office" | +4 |
| `field_environment` > 0 AND `environment` = "field" | +4 |
| `high_people_environment` > 0 AND `people_interaction` = "high_people" | +3 |

**Category cap: ±6**

---

### Q5: "How do you learn best?" — Learning Tolerance

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Hammer + checkmark | Do & Practise | `learning_by_doing` | 1 |
| B | Book + magnifying glass | Read & Understand | `concept_first` | 1 |
| C | Clipboard + group | Projects & Teamwork | `project_based` | 1 |
| D | Repeat/loop arrows | Drill & Memorise | `rote_tolerant` | 1 |

**Matching rules:**
| Condition | Points |
|-----------|--------|
| `learning_by_doing` > 0 AND (`work_modality` = "hands_on" OR `learning_style` includes "project_based") | +3 |
| `concept_first` > 0 AND `cognitive_type` = "abstract" | +3 |
| `project_based` > 0 AND `learning_style` includes "project_based" | +3 |
| `rote_tolerant` > 0 AND `learning_style` includes "assessment_heavy" | +3 |

**Grade modulation (NEW):** If student's average SPM grade is D or below AND `rote_tolerant` is selected, apply **×1.5 multiplier** to the `rote_tolerant` match score before capping. This aggressively routes academically struggling students toward competency-based TVET programmes where continuous assessment reduces exam pressure.

**Category cap: ±6**

---

### Q6: "After SPM, what matters most?" — Values

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Shield + checkmark | Stable Job | `stability_priority` | 2 |
| B | Money + rocket | Good Pay | `income_risk_tolerant` | 2 |
| C | Graduation cap + arrow | Continue Degree | `pathway_priority` | 2 |
| D | Lightning + briefcase | Work Fast | `fast_employment_priority` | 2 |

**Matching rules:**
| Condition | Points |
|-----------|--------|
| `stability_priority` > 0 AND `outcome` in ["regulated_profession", "employment_first"] | +4 |
| `stability_priority` > 0 AND `career_structure` = "stable" | +3 |
| `stability_priority` > 0 AND `credential_status` = "regulated" | +2 |
| `income_risk_tolerant` > 0 AND `outcome` = "entrepreneurial" | +3 |
| `income_risk_tolerant` > 0 AND `career_structure` = "volatile" | +2 |
| `pathway_priority` > 0 AND `outcome` = "pathway_friendly" | +4 |
| `fast_employment_priority` > 0 AND `outcome` = "employment_first" | +4 |
| `fast_employment_priority` > 0 AND `career_structure` = "stable" | +1 |

**Category cap: ±6**

---

### Q7: "What tires you out?" — Energy Sensitivity

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | People crowd + sweat | Too Many People | `low_people_tolerance` | 1 |
| B | Brain + weight | Heavy Thinking | `mental_fatigue_sensitive` | 1 |
| C | Arm + weight | Physical Work | `physical_fatigue_sensitive` | 1 |
| D | Flexed arm + star | **I Can Handle Anything** | `high_stamina` | 1 |

**Q7D change (per advisor):** "Nothing Much" → "I Can Handle Anything". Generates `high_stamina` signal instead of empty `{}`.

**Matching rules:**
| Condition | Points |
|-----------|--------|
| `low_people_tolerance` > 0 AND `people_interaction` = "high_people" | **-6** |
| `mental_fatigue_sensitive` > 0 AND `load` = "mentally_demanding" | **-6** |
| `physical_fatigue_sensitive` > 0 AND `load` = "physically_demanding" | **-6** |
| `high_stamina` > 0 AND `load` in ["physically_demanding", "mentally_demanding"] | **+2** |

**Grade modulation (NEW — imposter syndrome dampening):**
If student selects Q7B ("Heavy Thinking" drains them) BUT their merit score is in the **top 25%** of the student cohort, reduce the -6 penalty to **-2**. Strong SPM results are an objective counter-signal to subjective self-doubt. Do not let imposter syndrome suppress high-yield pathways.

```python
# Pseudocode for grade modulation on Q7B
if mental_fatigue_sensitive > 0 and load == 'mentally_demanding':
    if student_merit >= top_25_percentile_threshold:
        penalty = -2   # dampened — grades say they can handle it
    else:
        penalty = -6   # full penalty — grades confirm the concern
```

**Category cap: ±6**

---

### Q8: "What would help you keep studying?" — Practical Needs

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Wallet + coins | Pocket Money | `allowance_priority` | 3 |
| B | House + heart | Near Home | `proximity_priority` | 3 |
| C | Handshake + door | Job Guarantee | `employment_guarantee` | 2 |
| D | Trophy + star | Best Programme | *(empty)* | 0 |

**Matching rules (institution-level):**
| Condition | Points |
|-----------|--------|
| `allowance_priority` > 0 → boost institutions offering monthly allowance | +3 |
| `proximity_priority` > 0 AND institution `cultural_safety_net` = "high" | +4 |
| `proximity_priority` > 0 AND institution `cultural_safety_net` = "low" | -2 |
| `employment_guarantee` > 0 → boost TVET courses with work-based learning | +2 |

**Category cap: ±5** (institution modifier cap)

---

## Signal Taxonomy — Final (v2)

### 6 Categories, 21 Signals

```
field_interest (NEW):        field_mechanical, field_digital, field_business, field_health,
                             field_creative, field_hospitality, field_agriculture,
                             field_electrical, field_civil, field_aero_marine, field_oil_gas
                             (cap: ±8)

work_preference_signals:     hands_on, problem_solving, people_helping, creative
                             (cap: ±4 — reduced from ±6)

environment_signals:         workshop_environment, office_environment, field_environment,
                             high_people_environment
                             (cap: ±6)

learning_tolerance_signals:  learning_by_doing, concept_first, project_based, rote_tolerant
                             (cap: ±6, with grade modulation on rote_tolerant)

value_tradeoff_signals:      stability_priority, income_risk_tolerant, pathway_priority,
                             fast_employment_priority, allowance_priority, proximity_priority,
                             employment_guarantee
                             (cap: ±6)

energy_sensitivity_signals:  low_people_tolerance, mental_fatigue_sensitive,
                             physical_fatigue_sensitive, high_stamina
                             (cap: ±6, with grade modulation on mental_fatigue_sensitive)
```

**vs v1:** +1 signal (`high_stamina`), +4 field sub-signals (electrical/civil/aero_marine/oil_gas replacing generic `field_heavy_industry`), field interest cap raised to ±8, work preference cap lowered to ±4.

---

## Grade Modulation Layer — Full Specification

This is the new cross-referencing layer between deterministic grade data and subjective quiz signals. It runs **before** category capping in `ranking_engine.py`.

### Rule 1: Imposter Syndrome Dampening

```
IF student selects "Heavy Thinking tires me" (mental_fatigue_sensitive > 0)
AND student merit score >= 75th percentile
THEN reduce mentally_demanding penalty from -6 to -2
```

**Rationale:** A student with A/A- in Add Maths and Physics who says "heavy thinking tires me" is likely expressing anxiety, not incapacity. Their grades are the stronger signal.

### Rule 2: Academic Anxiety Routing

```
IF student selects "Drill & Memorise" (rote_tolerant > 0)
AND student average SPM grade <= D (poor academic performance)
THEN multiply rote_tolerant match score by 1.5× before capping
```

**Rationale:** Academically struggling students who are comfortable with structured repetition should be aggressively routed toward competency-based TVET (continuous assessment, skills certification) rather than exam-heavy academic diplomas.

### Rule 3: Stream-Field Cross-Reference

```
IF student took Science stream (has Physics, Chemistry, Add Maths grades)
AND student selects a non-Science field interest (e.g., field_hospitality, field_business)
THEN no penalty — respect the pivot intent
BUT add a subtle +1 boost to Science-aligned fields as "safety net" recommendations
```

**Rationale:** Many Science stream students want to pivot away from Science (burnout, interest shift). The system should respect this but ensure Science-aligned courses still appear in the list as viable alternatives. Do not gate-keep based on stream.

### Rule 4: Physical Stamina vs Grades

```
IF student selects "Physical Work tires me" (physical_fatigue_sensitive > 0)
AND student merit score >= 75th percentile
THEN no modulation — physical fatigue is a legitimate preference regardless of grades
```

**Rationale:** Unlike mental fatigue (which grades can counter-signal), physical fatigue tolerance is not correlated with academic performance. A straight-A student who dislikes physical labour is making a valid preference statement.

---

## Scoring Summary — Final v2

```
Final Score = BASE (100)
            + Field Interest     (cap ±8)   ← primary differentiator
            + Work Preference    (cap ±4)   ← secondary
            + Environment        (cap ±6)
            + Learning           (cap ±6, grade-modulated)
            + Values             (cap ±6)
            + Energy             (cap ±6, grade-modulated)
            + Institution        (cap ±5)
            + Merit Penalty      (-15 to 0)

Global cap: ±20 → Score range: 80-120
```

### Estimated Score Distribution (v2)

| Metric | Current Quiz | v1 Redesign | v2 Final |
|--------|-------------|-------------|----------|
| Effective discriminating questions | 3-4 of 6 | 7-8 of 8 | 8-9 of 8+1 |
| Field interest contribution | 0 pts | up to +6 | up to **+8** |
| Courses within 3 pts of top score | ~40% | ~15% | ~10% |
| Grade cross-referencing | None | None | **4 rules** |
| Dead signals | 2 | 0 | 0 |
| Empty signal options | 3 | 2 | **1** (Q8D only — intentional) |

---

## Implementation Scope

| Task | Effort | Component |
|------|--------|-----------|
| Update `quiz_data.py` — 8+1 questions × 3 languages, 4 options each | Medium | Backend |
| Add `field_interest` category to `quiz_engine.py` | Small | Backend |
| Add branching logic for Q2.5 in `quiz_engine.py` | Small | Backend |
| Add field matching rules to `ranking_engine.py` | Medium | Backend |
| Implement Grade Modulation Layer in `ranking_engine.py` | Medium | Backend |
| Wire `rote_tolerant` and `high_stamina` in `ranking_engine.py` | Small | Backend |
| Adjust category caps (field ±8, work ±4) | Small | Backend |
| Remove dead signal handling from `ranking_engine.py` | Small | Backend |
| Redesign quiz page — 2×2 icon card grid + branching | Medium | Frontend |
| Create/source 36 card icons (9 questions × 4 cards) | Medium | Frontend |
| Add `field_cluster` attribute to course data (map `frontend_label` → field signal) | Small | Data |
| Update quiz tests | Medium | Tests |
| Update ranking tests (new caps, grade modulation) | Medium | Tests |
| A/B test icons (rural vs urban) | Post-launch | UX |

---

## Open Items for Sprint Planning

1. **75th percentile threshold** — calculate from existing 50 test students or from live user data? (Recommend: hardcode from test data initially, make dynamic later)
2. **"Average SPM grade" definition** — mean of all subjects, or mean of core subjects only?
3. **Icon sourcing** — generate via Gemini Image, use open-source icon set (Lucide/Heroicons), or commission?
4. **i18n** — question prompts in EN/BM/TA (existing pattern), but icons are language-neutral (advantage of visual quiz)
