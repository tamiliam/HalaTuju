# HalaTuju Quiz Redesign v2 — Review Document

**Prepared by:** HalaTuju Development Team
**Date:** 10 March 2026
**Status:** Incorporates Advisor 1 feedback; seeking second review
**Feedback to:** tamiliam@gmail.com

---

## Context

HalaTuju is a course recommendation tool for Malaysian SPM students. After entering their SPM results, students take a short quiz to match them with suitable courses from 309 programmes across polytechnics, TVET institutions, community colleges, and universities.

The system works in two stages:
1. **Eligibility** (deterministic) — SPM grades determine which courses a student qualifies for
2. **Ranking** (signal-based) — quiz responses rank those eligible courses by personal fit

The quiz feeds into stage 2 only. It does not affect eligibility — it reorders the list of courses a student already qualifies for.

**The student's full SPM grades are available to the ranking engine at runtime.** This means the quiz only needs to capture what grades cannot tell us: interests, preferences, values, and practical constraints.

---

## Problem with the Current Quiz

The current quiz has 6 text-heavy questions with 5 options each. Each option is a full sentence.

**Key deficiencies:**

1. **No field/subject interest.** A student drawn to healthcare and one drawn to IT get identical rankings if their work style matches. Field interest is the strongest differentiator in course selection, yet it is absent.

2. **Dead signals.** Two options (`rote_tolerant`, `exam_sensitive`) are collected but have no matching rules in the ranking engine. Students select them; the system ignores the response.

3. **Empty signals.** Three questions offer "no preference" options generating zero signal. Students who pick these lose discriminating power from half the quiz.

4. **Weak differentiation.** Most courses cluster around the base score of 100 (range ~93-112). The "top 5" recommendations are not meaningfully different from courses ranked 6-20.

5. **UX friction.** 17-year-old mobile-first users must read, compare, and decide across 5 similar-sounding text options per question.

---

## Proposed Redesign

**8 questions + 1 conditional branch. 4 visual cards per question.**

Each card: icon (48px) + 2-3 word label. Students tap the card that feels right. Auto-advances after a brief pause. Estimated completion time: **~90 seconds**.

Layout: 2×2 card grid on mobile, 4-across on desktop.

---

## The 8+1 Questions

### Q1: "What catches your eye?" — Field Interest (Set 1)

| Card | Icon | Label | Signal | Maps to |
|------|------|-------|--------|---------|
| A | Wrench + gears | Build & Fix | `field_mechanical` | Mekanikal & Automotif (68 courses) |
| B | Laptop + code | Tech & Digital | `field_digital` | Komputer, IT & Multimedia (23 courses) |
| C | Handshake + chart | Business & Money | `field_business` | Perniagaan & Perdagangan (54 courses) |
| D | Heart + stethoscope | Health & Care | `field_health` | Pertanian & Bio-Industri health subset (30 courses) |

### Q2: "And this?" — Field Interest (Set 2)

| Card | Icon | Label | Signal | Maps to |
|------|------|-------|--------|---------|
| A | Paintbrush + ruler | Design & Create | `field_creative` | Seni Reka & Kreatif (20 courses) |
| B | Chef hat + suitcase | Food & Travel | `field_hospitality` | Hospitaliti, Kulinari & Pelancongan (26 courses) |
| C | Leaf + tractor | Nature & Farm | `field_agriculture` | Pertanian & Bio-Industri (30 courses) |
| D | Bolt + ship | Big Machines | `field_heavy_industry` | Triggers Q2.5 (see below) |

**Why two questions?** 9 course field clusters cannot fit in 4 cards. Two questions yield a **primary** and **secondary** interest. This is the single biggest improvement over the current quiz.

### Q2.5: "Which kind?" — Heavy Industry Branch (CONDITIONAL)

**Only shown if student selected Q2D ("Big Machines").** All other students skip this.

| Card | Icon | Label | Signal | Maps to |
|------|------|-------|--------|---------|
| A | Lightning bolt | Electrical | `field_electrical` | Elektrik & Elektronik (38 courses) |
| B | Hard hat + crane | Construction | `field_civil` | Sivil, Seni Bina & Pembinaan (29 courses) |
| C | Airplane + ship | Aero & Marine | `field_aero_marine` | Aero/Marine subset (≈10 courses) |
| D | Oil rig + flame | Oil & Gas | `field_oil_gas` | Oil & Gas subset (≈11 courses) |

**Rationale:** Grouping 88 courses (Electrical + Civil + Aero/Marine/Oil & Gas) under a single card was identified as analytically indefensible in initial review. These disciplines attract distinct cohorts. The conditional branch preserves the primary 4-card UI while cleanly separating sub-fields.

---

### Q3: "Your ideal day at work" — Work Style

| Card | Icon | Label | Signal |
|------|------|-------|--------|
| A | Hands + tools | Hands-On | `hands_on` |
| B | Brain + lightbulb | Problem Solving | `problem_solving` |
| C | People + speech bubbles | With People | `people_helping` |
| D | Pencil + star | Creating Things | `creative` |

*Does the student prefer physical, analytical, social, or creative work?*

### Q4: "Where would you work?" — Environment

| Card | Icon | Label | Signal |
|------|------|-------|--------|
| A | Workshop/garage | Workshop | `workshop_environment` |
| B | Desk + monitor | Office | `office_environment` |
| C | Trees + sun | Outdoors | `field_environment` |
| D | Building + people | With Crowds | `high_people_environment` |

*Boosts courses whose typical work setting matches the student's preference.*

### Q5: "How do you learn best?" — Learning Style

| Card | Icon | Label | Signal |
|------|------|-------|--------|
| A | Hammer + checkmark | Do & Practise | `learning_by_doing` |
| B | Book + magnifying glass | Read & Understand | `concept_first` |
| C | Clipboard + group | Projects & Teamwork | `project_based` |
| D | Repeat/loop arrows | Drill & Memorise | `rote_tolerant` |

*Matches to course teaching/assessment style: project-based, theory-heavy, continuous assessment, etc.*

### Q6: "After SPM, what matters most?" — Values

| Card | Icon | Label | Signal |
|------|------|-------|--------|
| A | Shield + checkmark | Stable Job | `stability_priority` |
| B | Money + rocket | Good Pay | `income_risk_tolerant` |
| C | Graduation cap + arrow | Continue Degree | `pathway_priority` |
| D | Lightning + briefcase | Work Fast | `fast_employment_priority` |

*What drives the student: stability, income, pathway to higher education, or fast employment?*

### Q7: "What tires you out?" — Energy (Caution Filter)

| Card | Icon | Label | Signal |
|------|------|-------|--------|
| A | People crowd + sweat | Too Many People | `low_people_tolerance` |
| B | Brain + weight | Heavy Thinking | `mental_fatigue_sensitive` |
| C | Arm + weight | Physical Work | `physical_fatigue_sensitive` |
| D | Flexed arm + star | **I Can Handle Anything** | `high_stamina` |

*Options A-C apply caution penalties to mismatched courses. Option D ("I Can Handle Anything") generates a positive `high_stamina` signal that slightly boosts demanding courses. This replaces a previous "Nothing Much" option that generated zero signal.*

### Q8: "What would help you keep studying?" — Practical Needs

| Card | Icon | Label | Signal |
|------|------|-------|--------|
| A | Wallet + coins | Pocket Money | `allowance_priority` |
| B | House + heart | Near Home | `proximity_priority` |
| C | Handshake + door | Job Guarantee | `employment_guarantee` |
| D | Trophy + star | Best Programme | *(no signal — intentional)* |

*Socio-economic realities (proximity, allowance) dictate tertiary choices for much of the Malaysian demographic. "Best Programme" captures students without financial/distance constraints.*

---

## Scoring Engine

### Category Caps

| Category | Cap | Rationale |
|----------|-----|-----------|
| **Field Interest** | **±8** | Primary differentiator — a student who wants culinary arts should not see automotive ranked highly because environmental variables align |
| **Work Preference** | **±4** | Secondary — reduced from ±6 to prevent work style from overriding field interest |
| Environment | ±6 | Tie-breaker level |
| Learning | ±6 | Tie-breaker level |
| Values | ±6 | Moderate — drives outcome matching |
| Energy | ±6 | Negative filter + stamina boost |
| Institution | ±5 | Tie-breaker (allowance, proximity) |
| Merit penalty | -15 to 0 | Reality check based on grade-derived merit score |

**Global cap: ±20. Score range: 80-120.**

### Field Interest Scoring

Students answer Q1 and Q2 (and optionally Q2.5), producing two field signals. When matching against a course:

- **Primary field match** (either Q1 or Q2 selection): **+8 points** (up to category cap)
- **Secondary field match** (the other selection): **+4 points**
- **No field match**: 0 (no penalty — field interest is additive only)

The "primary" is whichever Q1/Q2 answer matches the course's field. Both answers are checked against each course; the stronger match gets the higher score.

### Key Matching Rules (Summary)

| Signal | Course condition | Points | Category |
|--------|-----------------|--------|----------|
| `field_*` matches course `frontend_label` | Direct field match | +8 (primary) / +4 (secondary) | field_interest |
| `hands_on` | `work_modality` = "hands_on" | +4 | work_preference |
| `people_helping` | `people_interaction` = "high_people" | +4 | work_preference |
| `creative` | `creative_output` = "expressive" | +4 | work_preference |
| `workshop_environment` | `environment` = "workshop" | +4 | environment |
| `learning_by_doing` | `work_modality` = "hands_on" | +3 | learning |
| `rote_tolerant` | `learning_style` includes "assessment_heavy" | +3 | learning |
| `stability_priority` | `outcome` = "employment_first" | +4 | values |
| `pathway_priority` | `outcome` = "pathway_friendly" | +4 | values |
| `low_people_tolerance` | `people_interaction` = "high_people" | **-6** | energy |
| `mental_fatigue_sensitive` | `load` = "mentally_demanding" | **-6** (or -2, see below) | energy |
| `physical_fatigue_sensitive` | `load` = "physically_demanding" | **-6** | energy |
| `high_stamina` | `load` in ["physically_demanding", "mentally_demanding"] | **+2** | energy |

---

## Grade Modulation Layer (New)

The ranking engine currently treats quiz signals in isolation from SPM grade data. This layer cross-references the two to contextualise subjective responses with objective performance.

### Rule 1: Imposter Syndrome Dampening

**If** a student says "Heavy Thinking tires me" (Q7B)
**But** their merit score is in the top 25% of the cohort
**Then** reduce the penalty for mentally demanding courses from -6 to **-2**

**Rationale:** A student with A/A- in Add Maths and Physics who says "heavy thinking tires me" is likely expressing anxiety, not incapacity. Their grades are the stronger evidence. Full penalty suppresses high-yield pathways based on subjective self-doubt.

### Rule 2: Academic Anxiety Routing

**If** a student selects "Drill & Memorise" (Q5D)
**And** their average SPM grade is D or below
**Then** apply a **1.5× multiplier** to the rote_tolerant match score

**Rationale:** Academically struggling students who are comfortable with structured repetition should be steered toward competency-based TVET programmes (continuous assessment, skills certification) rather than exam-heavy academic diplomas. The multiplier makes this routing stronger for students who need it most.

### Rule 3: Stream-Field Cross-Reference

**If** a student took Science stream (has Physics, Chemistry, Add Maths)
**And** selects a non-Science field interest (e.g., Food & Travel, Business)
**Then** respect the pivot — no penalty.
**But** add a subtle +1 boost to Science-aligned fields as a "safety net"

**Rationale:** Many Science students want to pivot away from Science. The system respects this but ensures Science-aligned courses still appear in the list. The student has agency; the system provides options.

### Rule 4: Physical Fatigue — No Modulation

Physical fatigue tolerance is **not** modulated by grades. A straight-A student who dislikes physical labour is making a valid preference statement. Unlike mental fatigue (where grades can counter-signal), physical preference is independent of academic performance.

---

## Worked Example

**Student:** 4A 3B 2C in SPM (qualifies for 67 courses). Merit score: 72nd percentile.

**Quiz answers:**
- Q1: Build & Fix → `field_mechanical`
- Q2: Big Machines → triggers Q2.5
- Q2.5: Electrical → `field_electrical`
- Q3: Hands-On → `hands_on`
- Q4: Workshop → `workshop_environment`
- Q5: Do & Practise → `learning_by_doing`
- Q6: Stable Job → `stability_priority`
- Q7: I Can Handle Anything → `high_stamina`
- Q8: Pocket Money → `allowance_priority`

**Course A: Diploma Kejuruteraan Elektrik (Polytechnic)**

| Rule | Points | Reason |
|------|--------|--------|
| Field: `field_electrical` matches Elektrik & Elektronik | +8 | Primary field interest |
| Work: `hands_on` matches `work_modality: hands_on` | +4 | Hands-on preference (capped at 4) |
| Environment: `workshop_environment` matches `environment: workshop` | +4 | Workshop preference |
| Learning: `learning_by_doing` matches hands-on | +3 | Learning by doing |
| Values: `stability_priority` matches `outcome: employment_first` | +4 | Stable career |
| Energy: `high_stamina` + `load: physically_demanding` | +2 | Can handle demands |
| Category capping applied | | Field capped at 8, values capped at 6 |
| Global cap | | Total capped at +20 |
| **Final score** | **120** | **Strong match** |

**Course B: Diploma Perakaunan (Polytechnic)**

| Rule | Points | Reason |
|------|--------|--------|
| Field: no match (not electrical or mechanical) | 0 | |
| Work: `hands_on` but `work_modality: cognitive` | -3 | Mismatch |
| Environment: `workshop_environment` but `environment: office` | 0 | No match |
| Learning: no match | 0 | |
| Values: `stability_priority` matches `credential_status: regulated` | +2 | Accounting is regulated |
| Energy: `high_stamina` + `load: mentally_demanding` | +2 | Can handle demands |
| **Final score** | **101** | **Weak match** |

**Separation: 19 points.** The electrical engineering diploma clearly outranks accounting for this student. Under the current quiz (no field interest), both would be within 5 points of each other.

---

## Current vs Proposed — Summary

| Metric | Current | Proposed (v2) |
|--------|---------|---------------|
| Questions | 6 | 8 + 1 conditional |
| Options per question | 4-5 text sentences | 4 visual icon cards |
| Field interest | Absent | 2 questions + 1 branch (11 field signals) |
| Dead signals | 2 | 0 |
| Empty signal options | 3 | 1 (Q8D, intentional) |
| Grade cross-referencing | None | 4 modulation rules |
| Effective discriminating Qs | 3-4 of 6 | 8-9 of 8+1 |
| Courses within 3 pts of top | ~40% | ~10% |
| Completion time | ~3 min | ~90 sec |
| Primary differentiator cap | ±6 (work pref) | ±8 (field interest) |

---

## Course Tag Distribution (Reference)

Each course is tagged across 12 dimensions. These tags are what quiz signals match against.

| Tag | Values (count) | Matched by |
|-----|---------------|------------|
| `frontend_label` (field) | 9 clusters (see appendix) | **Q1, Q2, Q2.5** |
| `work_modality` | hands_on (136), mixed (99), cognitive (49), theoretical (25) | Q3 |
| `environment` | workshop (125), office (75), lecture (32), lab (31), field (29) | Q4 |
| `people_interaction` | moderate (155), low (109), high (45) | Q3, Q7 |
| `learning_style` | continuous_assessment (158), project_based (107), assessment_heavy (95) | Q5 |
| `load` | mentally_demanding (169), physically_demanding (118), balanced (12) | Q7 |
| `outcome` | pathway_friendly (95), employment_first (74), industry_specific (64), entrepreneurial (34) | Q6 |
| `career_structure` | volatile (151), stable (134), portfolio (24) | Q6 |
| `cognitive_type` | procedural (127), problem_solving (103), abstract (79) | Q3 |
| `credential_status` | unregulated (261), regulated (48) | Q6 |
| `creative_output` | none (236), functional (33), expressive (27), design (13) | Q3 |
| `service_orientation` | neutral (267), service (37), care (5) | Q3 |

---

## Questions for Reviewer

1. **Are these the right 8+1 questions?** Is there a dimension missing that matters for Malaysian SPM students choosing post-secondary courses?

2. **Field interest (Q1 + Q2 + Q2.5):** Do the field clusters cover the landscape? Is the branching approach for heavy industry appropriate, or would a different split work better?

3. **Grade Modulation Layer:** Are the 4 cross-referencing rules sound? Specifically:
   - Is dampening the "heavy thinking" penalty for top-25% students defensible, or does it risk overriding a legitimate preference?
   - Is the 1.5× rote_tolerant multiplier for academically weak students appropriate, or could it inadvertently limit options?
   - Is the Science stream "safety net" (+1 to Science fields) patronising, or helpful?

4. **Scoring hierarchy:** Field interest at ±8, work preference at ±4, everything else at ±6. Does this weighting reflect the actual decision-making priorities of SPM students?

5. **Q7 reframing:** "I Can Handle Anything" replaces "Nothing Much" and generates a `high_stamina` signal (+2 for demanding courses). Is this a meaningful improvement, or does it introduce bias toward demanding programmes for students who are simply indifferent?

6. **Visual card format:** 4 cards per question, icon + 2-3 word label, no descriptive text. Is this sufficient for the target demographic, or do some questions need a one-line subtitle for clarity?

7. **What are we missing?**

---

## Appendix: Course Field Distribution

| Field Cluster | Quiz Card | Courses | % | Examples |
|---------------|-----------|---------|---|----------|
| Mekanikal & Automotif | Q1A | 68 | 22% | Diploma Kejuruteraan Mekanikal, Sijil Teknologi Automotif |
| Perniagaan & Perdagangan | Q1C | 54 | 17% | Diploma Perakaunan, Diploma Pengurusan Perniagaan |
| Elektrik & Elektronik | Q2.5A | 38 | 12% | Diploma Kejuruteraan Elektrik, Sijil Elektronik |
| Pertanian & Bio-Industri | Q1D / Q2C | 30 | 10% | Diploma Agroteknologi, Diploma Akuakultur |
| Sivil, Seni Bina & Pembinaan | Q2.5B | 29 | 9% | Diploma Kejuruteraan Awam, Diploma Seni Bina |
| Hospitaliti, Kulinari & Pelancongan | Q2B | 26 | 8% | Diploma Seni Kulinari, Diploma Pengurusan Hotel |
| Komputer, IT & Multimedia | Q1B | 23 | 7% | Diploma Teknologi Maklumat, Diploma Animasi 3D |
| Aero, Marin, Minyak & Gas | Q2.5C/D | 21 | 7% | Diploma Kejuruteraan Penyenggaraan Pesawat |
| Seni Reka & Kreatif | Q2A | 20 | 6% | Diploma Rekabentuk Grafik, Diploma Fesyen |
| **Total** | | **309** | **100%** | |
