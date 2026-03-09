# HalaTuju Quiz Redesign — Review Document

**Prepared by:** HalaTuju Development Team
**Date:** 10 March 2026
**Purpose:** Critical review of proposed quiz redesign before implementation
**Feedback to:** tamiliam@gmail.com

---

## What is HalaTuju?

HalaTuju is a course recommendation tool for Malaysian SPM students. After entering their SPM results, students take a short quiz to help match them with suitable courses from 309 programmes across polytechnics, TVET institutions, community colleges, and universities.

The system works in two stages:
1. **Eligibility** (deterministic) — SPM grades determine which courses a student qualifies for
2. **Ranking** (signal-based) — quiz responses rank those eligible courses by personal fit

The quiz feeds into stage 2 only. It cannot make a student eligible or ineligible — it only reorders the list.

---

## Problem with the Current Quiz

The current quiz has 6 text-heavy questions with 5 options each. Each option is a full sentence the student must read and compare.

### Current Questions

| # | Question | Signal Category | Options |
|---|----------|----------------|---------|
| Q1 | "Which type of work sounds least tiring to you?" | Work preference | 5 text options |
| Q2 | "On most days, you'd rather be working in:" | Environment | 5 text options |
| Q3 | "Which describes you better as a student?" | Learning style | 5 text options |
| Q4 | "Right now, which matters more to you?" | Values | 5 text options |
| Q5 | "After a full day, what usually drains you more?" | Energy sensitivity | 5 text options |
| Q6 | "Which would make it easiest to continue studies?" | Practical needs | 4 text options |

### Issues Identified

**1. No field/subject interest dimension.**
The quiz asks *how* a student likes to work but never *what area* they are interested in. A student drawn to healthcare and a student drawn to IT receive identical rankings if their work style preferences match. This is the single largest gap — field interest is the strongest differentiator in course selection, yet it is entirely absent.

**2. Dead signals — collected but never used.**
Two options generate signals that have no matching rules in the ranking engine:
- `rote_tolerant` (Q3: "I'm okay memorising if expectations are clear") — no course tag matches this
- `exam_sensitive` (Q3: "I struggle with exams under time pressure") — no course tag matches this

These options are traps: a student selects them, but the system ignores the response entirely.

**3. Empty signals — "no preference" options.**
Three questions include "no preference" or "nothing in particular" options that generate `{}` (zero signals). A student who picks these loses discriminating power from 50% of the quiz.

| Question | Empty option | Signal generated |
|----------|-------------|-----------------|
| Q2 | "No strong preference" | `{}` |
| Q5 | "Nothing in particular" | `{}` |
| Q6 | "No strong preference" | `{}` |

**4. Weak score differentiation.**
With only 6 questions producing at most 6 signals, most courses cluster around the base score of 100 (range: ~90-115). The "top 5" recommendations are not meaningfully different from courses ranked 6-20. The quiz lacks the signal density to create meaningful separation.

**5. UX friction for target audience.**
SPM students are 17, mobile-first. The current text-wall format requires reading, comparing, and deciding across 5 similar-sounding options. This is a survey form, not an engaging experience.

---

## Proposed Redesign

### Format Change

| Aspect | Current | Proposed |
|--------|---------|----------|
| Questions | 6 | 8 |
| Options per question | 4-5 (text sentences) | 4 (visual icon cards) |
| Layout | Vertical list of text | 2×2 card grid |
| Card format | Full sentence | Icon (48px) + 2-3 word label |
| Interaction | Click radio button | Tap card, auto-advance |
| Completion time | ~3 minutes | ~90 seconds |
| Field interest coverage | None | 2 questions (8 field clusters) |
| Dead signals | 2 | 0 |
| Empty signal options | 3 | 0 (neutral options reframed positively) |

### Design Principles

1. **Icons carry meaning, labels confirm.** If a student needs to read a paragraph to understand an option, the option is poorly designed.
2. **Every tap produces a usable signal.** No dead-end options.
3. **Field interest is the primary differentiator.** Two of eight questions are dedicated to it.
4. **Grades tell us strengths; the quiz tells us preferences.** No overlap with data we already have.

---

## The 8 Questions

### Q1: "What catches your eye?" — Field Interest (Set 1)

| Card | Icon | Label | Signal | Weight | Maps to Course Field |
|------|------|-------|--------|--------|---------------------|
| A | Wrench + gears | Build & Fix | `field_mechanical` | 3 | Mekanikal & Automotif (68 courses) |
| B | Laptop + code | Tech & Digital | `field_digital` | 3 | Komputer, IT & Multimedia (23 courses) |
| C | Handshake + chart | Business & Money | `field_business` | 3 | Perniagaan & Perdagangan (54 courses) |
| D | Heart + stethoscope | Health & Care | `field_health` | 3 | Pertanian & Bio-Industri — health subset (30 courses) |

### Q2: "And this?" — Field Interest (Set 2)

| Card | Icon | Label | Signal | Weight | Maps to Course Field |
|------|------|-------|--------|--------|---------------------|
| A | Paintbrush + ruler | Design & Create | `field_creative` | 3 | Seni Reka & Kreatif (20 courses) |
| B | Chef hat + suitcase | Food & Travel | `field_hospitality` | 3 | Hospitaliti, Kulinari & Pelancongan (26 courses) |
| C | Leaf + tractor | Nature & Farm | `field_agriculture` | 3 | Pertanian & Bio-Industri (30 courses) |
| D | Bolt + ship | Energy & Machines | `field_heavy_industry` | 3 | Aero/Marin/Minyak & Gas (21) + Elektrik & Elektronik (38) + Sivil/Seni Bina/Pembinaan (29) |

**Rationale:** 9 course field clusters cannot fit in 4 cards. Two questions with 4 cards each = 8 fields covered (the 9th, "Sivil, Seni Bina & Pembinaan", is grouped with heavy industry as both involve construction/infrastructure). Students pick one from each set, yielding a **primary** and **secondary** interest.

**Scoring:** Primary field match = **+6 points**. Secondary field match = **+3 points**. No match = 0 (no penalty). This creates up to 6 points of separation between a field-matched course and an unmatched one — more than any other single signal.

---

### Q3: "Your ideal day at work" — Work Preference

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Hands + tools | Hands-On | `hands_on` | 2 |
| B | Brain + lightbulb | Problem Solving | `problem_solving` | 2 |
| C | People + speech bubbles | With People | `people_helping` | 2 |
| D | Pencil + star | Creating Things | `creative` | 2 |

**Change from current:** Dropped "organising" (weak signal — `organising` mapped to no distinctive course tag pattern; courses tagged `moderate_people` span all fields). Reduced from 5 to 4 options.

**Matching rules (existing, unchanged):**
- `hands_on` > 0 AND course `work_modality` = "hands_on" → +5
- `problem_solving` > 0 AND course `work_modality` = "mixed" → +3
- `people_helping` > 0 AND course `people_interaction` = "high_people" → +4
- `creative` > 0 AND course `learning_style` includes "project_based" → +4
- `creative` > 0 AND course `creative_output` = "expressive" → +4

---

### Q4: "Where would you work?" — Environment

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Workshop/garage | Workshop | `workshop_environment` | 1 |
| B | Desk + monitor | Office | `office_environment` | 1 |
| C | Trees + sun | Outdoors | `field_environment` | 1 |
| D | Building + people | With Crowds | `high_people_environment` | 1 |

**Change from current:** Dropped "no preference" (empty signal). Reduced from 5 to 4 options.

**Matching rules (existing, unchanged):**
- `workshop_environment` > 0 AND course `environment` = "workshop" → +4
- `office_environment` > 0 AND course `environment` = "office" → +4
- `field_environment` > 0 AND course `environment` = "field" → +4
- `high_people_environment` > 0 AND course `people_interaction` = "high_people" → +3

---

### Q5: "How do you learn best?" — Learning Tolerance

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Hammer + checkmark | Do & Practise | `learning_by_doing` | 1 |
| B | Book + magnifying glass | Read & Understand | `concept_first` | 1 |
| C | Clipboard + group | Projects & Teamwork | `project_based` | 1 |
| D | Repeat/loop arrows | Drill & Memorise | `rote_tolerant` | 1 |

**Change from current:** Dropped `exam_sensitive` (dead signal — no matching rule, no course tag). Replaced with `rote_tolerant` which was previously dead but now gets a matching rule (see below). Reduced from 5 to 4 options.

**Matching rules:**
- `learning_by_doing` > 0 AND course `work_modality` = "hands_on" → +3 *(existing)*
- `concept_first` > 0 AND course `cognitive_type` = "abstract" → +3 *(existing)*
- `project_based` > 0 AND course `learning_style` includes "project_based" → +3 *(existing)*
- `rote_tolerant` > 0 AND course `learning_style` includes "assessment_heavy" → +3 **(NEW — was dead signal, now matches 95 courses)**

---

### Q6: "After SPM, what matters most?" — Values

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Shield + checkmark | Stable Job | `stability_priority` | 2 |
| B | Money + rocket | Good Pay | `income_risk_tolerant` | 2 |
| C | Graduation cap + arrow | Continue Degree | `pathway_priority` | 2 |
| D | Lightning + briefcase | Work Fast | `fast_employment_priority` | 2 |

**Change from current:** Dropped "meaningful work" (`meaning_priority`). This concept is too abstract for the target age group and is captured indirectly through field interest (Q1/Q2) and people preference (Q3). Reduced from 5 to 4 options.

**Matching rules (existing, unchanged):**
- `stability_priority` > 0 AND course `outcome` in ["regulated_profession", "employment_first"] → +4
- `stability_priority` > 0 AND course `career_structure` = "stable" → +3
- `income_risk_tolerant` > 0 AND course `outcome` = "entrepreneurial" → +3
- `pathway_priority` > 0 AND course `outcome` = "pathway_friendly" → +4
- `fast_employment_priority` > 0 AND course `outcome` = "employment_first" → +4

---

### Q7: "What tires you out?" — Energy Sensitivity (Negative Filter)

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | People crowd + sweat | Too Many People | `low_people_tolerance` | 1 |
| B | Brain + weight | Heavy Thinking | `mental_fatigue_sensitive` | 1 |
| C | Arm + weight | Physical Work | `physical_fatigue_sensitive` | 1 |
| D | Smiley + thumbs up | Nothing Much | *(empty)* | 0 |

**Change from current:** Dropped `time_pressure_sensitive` (no matching course tag — no course is tagged with time pressure characteristics). "Nothing Much" is an intentional neutral option — it generates no signal, but unlike "no preference" it is positively framed. Reduced from 5 to 4 options.

**Matching rules (existing, negative only):**
- `low_people_tolerance` > 0 AND course `people_interaction` = "high_people" → **-6**
- `mental_fatigue_sensitive` > 0 AND course `load` = "mentally_demanding" → **-6**
- `physical_fatigue_sensitive` > 0 AND course `load` = "physically_demanding" → **-6**

These are caution flags, not exclusions. Penalised courses still appear but rank lower, with a caution note explaining the mismatch.

---

### Q8: "What would help you keep studying?" — Practical Needs

| Card | Icon | Label | Signal | Weight |
|------|------|-------|--------|--------|
| A | Wallet + coins | Pocket Money | `allowance_priority` | 3 |
| B | House + heart | Near Home | `proximity_priority` | 3 |
| C | Handshake + door | Job Guarantee | `employment_guarantee` | 2 |
| D | Trophy + star | Best Programme | *(empty)* | 0 |

**Change from current:** "No strong preference" reframed as "Best Programme" — captures students without financial/distance constraints while feeling like a positive choice. Reduced from 4 to 4 options (same count, better framing).

**Matching rules (existing, institution-level):**
- `allowance_priority` > 0 → boosts courses/institutions offering monthly allowance
- `proximity_priority` > 0 AND institution `cultural_safety_net` = "high" → +4
- `proximity_priority` > 0 AND institution `cultural_safety_net` = "low" → -2
- `employment_guarantee` > 0 → boosts TVET courses with work-based learning

---

## Signal Taxonomy (Complete)

### Current: 5 Categories, 22 Signals

```
work_preference_signals:     hands_on, problem_solving, people_helping, creative, organising
learning_tolerance_signals:  learning_by_doing, concept_first, rote_tolerant, project_based, exam_sensitive
environment_signals:         workshop_environment, office_environment, high_people_environment, field_environment, no_preference
value_tradeoff_signals:      stability_priority, income_risk_tolerant, pathway_priority, meaning_priority,
                             fast_employment_priority, proximity_priority, allowance_priority, employment_guarantee
energy_sensitivity_signals:  low_people_tolerance, mental_fatigue_sensitive, physical_fatigue_sensitive, time_pressure_sensitive
```

- Dead (collected, never matched): `rote_tolerant`, `exam_sensitive`
- Dead (empty signal): `no_preference`
- Weak (no distinctive course tag): `organising`, `time_pressure_sensitive`
- Absent: any field/subject interest

### Proposed: 6 Categories, 20 Signals

```
field_interest:              field_mechanical, field_digital, field_business, field_health,       ← NEW
                             field_creative, field_hospitality, field_agriculture, field_heavy_industry
work_preference_signals:     hands_on, problem_solving, people_helping, creative
learning_tolerance_signals:  learning_by_doing, concept_first, project_based, rote_tolerant      ← rote_tolerant now active
environment_signals:         workshop_environment, office_environment, high_people_environment, field_environment
value_tradeoff_signals:      stability_priority, income_risk_tolerant, pathway_priority,
                             fast_employment_priority, allowance_priority, proximity_priority, employment_guarantee
energy_sensitivity_signals:  low_people_tolerance, mental_fatigue_sensitive, physical_fatigue_sensitive
```

- Dead signals: **0**
- Removed: `organising`, `meaning_priority`, `exam_sensitive`, `time_pressure_sensitive`, `no_preference`
- Added: 8 field interest signals (new category)

---

## Scoring Mechanics

### How Fit Scores Work

```
Final Score = BASE_SCORE (100)
            + Field Interest Match    (0 to +6, capped per category at 6)
            + Work Preference Match   (-6 to +6)
            + Environment Match       (-6 to +6)
            + Learning Match          (-6 to +6)
            + Values Match            (-6 to +6)
            + Energy Sensitivity      (-6 to 0, negative only)
            + Institution Modifier    (-5 to +5)
            + Merit Penalty           (-15 to 0)

Global cap: ±20 from base (range: 80-120)
```

### Score Distribution — Before vs After (Estimated)

| Metric | Current Quiz | Proposed Quiz |
|--------|-------------|---------------|
| Typical score range | 93-112 | 86-118 |
| Max theoretical separation between best and worst match | 20 pts | 20 pts (same global cap) |
| Courses within 3 pts of top score (indistinguishable) | ~40% | ~15% |
| Field interest contribution | 0 pts | up to 6 pts |
| Effective discriminating questions | 3-4 of 6 | 7-8 of 8 |

The key improvement is not wider range but **fewer ties**. Field interest alone creates 6 points of separation that previously did not exist, cutting the percentage of near-identical scores roughly in half.

---

## Worked Example

**Student profile:**
- SPM: 4A 3B 2C (qualifies for 67 courses)
- Q1: "Build & Fix" → `field_mechanical: 3`
- Q2: "Energy & Machines" → `field_heavy_industry: 3`
- Q3: "Hands-On" → `hands_on: 2`
- Q4: "Workshop" → `workshop_environment: 1`
- Q5: "Do & Practise" → `learning_by_doing: 1`
- Q6: "Stable Job" → `stability_priority: 2`
- Q7: "Nothing Much" → *(no signal)*
- Q8: "Pocket Money" → `allowance_priority: 3`

**Scoring for Diploma Kejuruteraan Mekanikal (Polytechnic):**

| Rule | Points | Reason |
|------|--------|--------|
| Field: `field_mechanical` matches "Mekanikal & Automotif" | +6 | Primary field interest |
| Work: `hands_on` matches `work_modality: hands_on` | +5 | Hands-on work preference |
| Environment: `workshop_environment` matches `environment: workshop` | +4 | Workshop environment |
| Learning: `learning_by_doing` matches `work_modality: hands_on` | +3 | Learning by doing |
| Values: `stability_priority` matches `outcome: employment_first` | +4 | Stable career |
| Values: `stability_priority` matches `career_structure: stable` | +3 | Stable structure |
| **Category capping** (6 per category) | | Values capped at 6, work capped at 6 |
| **Global cap** | | Capped at +20 |
| **Final score** | **120** | Strong match |

**Scoring for Diploma Perakaunan (Polytechnic):**

| Rule | Points | Reason |
|------|--------|--------|
| Field: no field match | 0 | Not in mechanical or heavy industry |
| Work: `hands_on` but `work_modality: cognitive` | -3 | Mismatch |
| Environment: `workshop_environment` but `environment: office` | 0 | No match |
| Learning: no match | 0 | |
| Values: `stability_priority` matches `outcome: regulated_profession` | +4 | Stable career (accounting is regulated) |
| **Final score** | **101** | Weak match |

**Separation: 19 points.** The mechanical engineering diploma clearly ranks above accounting for this student. Under the current quiz (no field interest), both would score within 5 points of each other.

---

## Course Tag Distribution

Each of the 309 courses is tagged across 12 dimensions. These tags are what quiz signals match against.

| Tag Dimension | Values (count) | Matched by Question |
|---------------|---------------|-------------------|
| `work_modality` | hands_on (136), mixed (99), cognitive (49), theoretical (25) | Q3 |
| `environment` | workshop (125), office (75), lecture (32), lab (31), field (29), mixed (17) | Q4 |
| `people_interaction` | moderate (155), low (109), high (45) | Q3, Q4, Q7 |
| `cognitive_type` | procedural (127), problem_solving (103), abstract (79) | Q3 |
| `learning_style` | continuous_assessment (158), project_based (107), assessment_heavy (95) | Q5 |
| `load` | mentally_demanding (169), physically_demanding (118), balanced (12), social (10) | Q7 |
| `outcome` | pathway_friendly (95), employment_first (74), industry_specific (64), entrepreneurial (34), regulated (25) | Q6 |
| `career_structure` | volatile (151), stable (134), portfolio (24) | Q6 |
| `credential_status` | unregulated (261), regulated (48) | Q6 |
| `service_orientation` | neutral (267), service (37), care (5) | Q3 |
| `creative_output` | none (236), functional (33), expressive (27), design (13) | Q3 |
| `interaction_type` | mixed (215), transactional (79), relational (15) | Q3, Q7 |
| `frontend_label` *(field)* | 9 field clusters (see Appendix) | **Q1, Q2 (NEW)** |

Note: `frontend_label` is not currently used by the ranking engine. The redesign adds it as the primary matching dimension for the new field interest signals.

---

## Risks and Limitations

| Risk | Severity | Mitigation |
|------|----------|------------|
| 4 cards may force false choices (student's true interest not listed) | Medium | Two field questions cover 8 of 9 clusters; Q2 "Energy & Machines" groups 3 clusters |
| Single-select limits signal richness (student likes both "hands-on" AND "people") | Low | More questions compensate; multi-select is a future enhancement |
| Icon interpretation may vary across cultures | Low | Labels confirm meaning; tested in 3 languages (EN, BM, TA) |
| Students may game the quiz after seeing results | Low | No "right answers" — all options lead to valid recommendations |
| Field interest may dominate other signals | Medium | Capped at +6 per category (same as all other categories) |
| "Nothing Much" / "Best Programme" are disguised empty signals | Low | Acceptable — these students genuinely have no constraint to capture |

---

## Questions for Reviewer

1. **Are these the right 8 questions?** Is there a dimension we're missing that matters for Malaysian SPM students choosing post-secondary courses?

2. **Are the 4 options per question balanced?** Would a 17-year-old understand what each card means from the icon and 2-3 word label alone?

3. **Field interest (Q1 + Q2):** Do the 8 field clusters cover the landscape adequately? Is the grouping of Elektrik/Sivil/Aero under "Energy & Machines" (Q2D) defensible, or should these be split differently?

4. **Dropped signals:** We removed `organising`, `meaning_priority`, `exam_sensitive`, and `time_pressure_sensitive`. Are any of these important enough to bring back (which would mean dropping something else)?

5. **Q7 (Energy) and Q8 (Practical):** These produce weaker signals than Q1-Q6. Are they worth the extra questions, or would 6 tighter questions with no dead weight be better?

6. **Scoring weights:** Field interest at +6, work preference at +5, environment at +4 — is this hierarchy correct? Should field interest be weighted even more heavily?

7. **Is 8 questions the right number?** Too few = weak signals. Too many = drop-off. For a 17-year-old on a phone, where is the sweet spot?

8. **Anything we haven't thought of?**

---

## Appendix: Course Field Distribution

| Field Cluster | Quiz Card | Courses | % of Total | Example Programmes |
|---------------|-----------|---------|-----------|-------------------|
| Mekanikal & Automotif | Q1A | 68 | 22% | Diploma Kejuruteraan Mekanikal, Sijil Teknologi Automotif |
| Perniagaan & Perdagangan | Q1C | 54 | 17% | Diploma Perakaunan, Diploma Pengurusan Perniagaan |
| Elektrik & Elektronik | Q2D | 38 | 12% | Diploma Kejuruteraan Elektrik, Sijil Elektronik |
| Pertanian & Bio-Industri | Q1D / Q2C | 30 | 10% | Diploma Agroteknologi, Diploma Akuakultur |
| Sivil, Seni Bina & Pembinaan | Q2D | 29 | 9% | Diploma Kejuruteraan Awam, Diploma Seni Bina |
| Hospitaliti, Kulinari & Pelancongan | Q2B | 26 | 8% | Diploma Seni Kulinari, Diploma Pengurusan Hotel |
| Komputer, IT & Multimedia | Q1B | 23 | 7% | Diploma Teknologi Maklumat, Diploma Animasi 3D |
| Aero, Marin, Minyak & Gas | Q2D | 21 | 7% | Diploma Kejuruteraan Penyenggaraan Pesawat |
| Seni Reka & Kreatif | Q2A | 20 | 6% | Diploma Rekabentuk Grafik, Diploma Fesyen |
| **Total** | | **309** | **100%** | |
