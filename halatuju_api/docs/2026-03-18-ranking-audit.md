# Course Ranking Audit — SPM & STPM (Pre-Quiz and Post-Quiz)

**Date:** 2026-03-18
**Scope:** Four ranking modes — SPM pre-quiz, SPM post-quiz, STPM pre-quiz, STPM post-quiz
**Purpose:** Document current behaviour, assess fitness for purpose, propose improvements

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [SPM Pre-Quiz Ranking](#2-spm-pre-quiz-ranking)
3. [SPM Post-Quiz Ranking](#3-spm-post-quiz-ranking)
4. [STPM Pre-Quiz Ranking](#4-stpm-pre-quiz-ranking)
5. [STPM Post-Quiz Ranking](#5-stpm-post-quiz-ranking)
6. [Cross-Cutting Observations](#6-cross-cutting-observations)
7. [Priority Matrix](#7-priority-matrix)

---

## 1. System Overview

HalaTuju ranks courses in two tracks (SPM and STPM), each with two modes:

| Mode | When Used | Signal Source | Key File |
|------|-----------|---------------|----------|
| SPM pre-quiz | Before student takes the quiz | Grades + eligibility only | `ranking_engine.py` |
| SPM post-quiz | After quiz submission | 6 signal categories (36 signals) | `ranking_engine.py` |
| STPM pre-quiz | Before student takes the quiz | CGPA only | `stpm_ranking.py` |
| STPM post-quiz | After quiz submission | 8 signal categories (~60 signals) | `stpm_ranking.py` |

### Data Infrastructure

**SPM ranking** depends on two startup-loaded maps (built in `apps.py`):

- **`course_tags_map`** — Built from `CourseTag` model. Each course has 12+ tag dimensions (work_modality, people_interaction, cognitive_type, learning_style, load, outcome, environment, credential_status, creative_output, service_orientation, interaction_type, career_structure). Enriched with `field_key` from the `Course` model. Structure: `{course_id: {tag_key: tag_value, ..., field_key: taxonomy_key}}`
- **`inst_modifiers_map`** — Built from `Institution.modifiers` (JSONField). Keys: `urban` (boolean), `cultural_safety_net` ('high'/'low'). Structure: `{institution_id: {modifier_key: value}}`

**STPM ranking** uses fields directly on `StpmCourse` model (`field_key`, `riasec_type`, `difficulty_level`, `efficacy_domain`) — no external tag map needed.

---

## 2. SPM Pre-Quiz Ranking

### Current Behaviour

Every eligible course receives a flat `BASE_SCORE = 100` with **zero signal adjustments**. No quiz data exists, so `calculate_fit_score()` is still called but all signal categories are empty, producing no adjustments.

**Exception — Pre-University courses:** Courses with `pathway_type` in `('asasi', 'matric', 'stpm')` use dedicated scoring functions even without quiz signals:

| Pathway | Function | Base | Academic Bonus |
|---------|----------|------|----------------|
| Asasi | `calculate_asasi_fit_score()` | `BASE_SCORE + ASASI_PRESTIGE_BONUS (12)` = 112 | Merit ≥90: +8, ≥84: +4 |
| Matrikulasi | `calculate_matric_stpm_fit_score()` | `BASE_SCORE + MATRIC_PRESTIGE_BONUS (8)` = 108 | Merit ≥94: +8, ≥89: +4 |
| STPM Pathway | `calculate_matric_stpm_fit_score()` | `BASE_SCORE + STPM_PRESTIGE_BONUS (5)` = 105 | Mata Gred ≤4: +8, ≤10: +4 |

After scoring, **merit penalty** is applied:

| Merit Label | Penalty |
|-------------|---------|
| High | 0 |
| Fair | -5 |
| Low | -15 |

### Sort Order (7-Level Tie-Breaking)

Since most non-pre-U courses score identically (100), the sort hierarchy determines the actual ranking:

| Priority | Criterion | Direction | Notes |
|----------|-----------|-----------|-------|
| 1 | Fit score | Descending | Pre-U courses naturally rank higher (112, 108, 105) |
| 2 | Merit chance tier | Descending | High (3) > Fair (2) > Low (1) |
| 3 | Merit delta | Descending | `student_merit - merit_cutoff` (Fair/Low tiers only) |
| 4 | Credential priority | Descending | Asasi/Diploma (5) > Sijil Lanjutan (2) > Sijil (1) |
| 5 | Institution priority | Descending | See institution priority table below |
| 6 | Merit competitiveness | Descending | Higher cutoff = more competitive |
| 7 | Course name | Ascending | Alphabetical fallback |

**Institution Priority Table:**

| Institution Type | Priority |
|------------------|----------|
| Penyelidikan | 14 |
| Komprehensif | 13 |
| Berfokus | 12 |
| Teknikal | 11 |
| Premier | 10 |
| Konvensional | 9 |
| JMTI | 8 |
| METrO | 7 |
| Kolej Komuniti | 6 |
| ADTEC | 5 |
| IKTBN | 4 |
| ILP | 3 |
| IKBN / IKSN | 2 |
| IKBS | 1 |

### Strengths

1. **Deterministic and fair** — no bias from incomplete data; every course starts equal
2. **Merit-driven ordering** — tie-breaker hierarchy surfaces courses with strongest admission chance first
3. **Instant results** — students see meaningful recommendations immediately after entering grades
4. **Pre-U differentiation works** — Asasi, Matric, and STPM pathways naturally float to the top via prestige bonuses

### Weaknesses

| # | Weakness | Impact | Severity |
|---|----------|--------|----------|
| W1 | **Flat scores give false impression of equal fit** — every non-pre-U course shows "100", implying all courses suit the student equally | Students may not understand that ordering is by admission chance, not personal fit | Medium |
| W2 | **No field relevance signal** — a student interested in engineering sees culinary arts ranked equally if merit tiers match | Poor first impression; may erode trust before the quiz adds differentiation | High |
| W3 | **No institution location/preference input** — urban vs rural, state proximity are invisible | Students may see courses at distant institutions ranked highly | Low |

### Proposed Improvements

1. **Display "Admission Chance" instead of fit score pre-quiz (W1).** Hide the fit_score column and show only the merit label (High/Fair/Low) with explanation: *"Ini senarai berdasarkan peluang kemasukan anda. Ambil kuiz untuk cadangan lebih tepat."* Avoids the misleading "100" score.

2. **Add a lightweight field preference selector (W2).** On the eligibility results page, add a dropdown with the 12 field taxonomy categories: *"Bidang minat anda?"* Use the selected field(s) to give a small boost (+5) to matching courses. Gives basic personalisation without the full quiz.

3. **Surface quiz CTA prominently.** After showing pre-quiz results, display a banner: *"Jawab 6 soalan untuk cadangan kursus yang lebih sesuai dengan minat dan personaliti anda."*

---

## 3. SPM Post-Quiz Ranking

### Signal Taxonomy (6 Categories, 36 Signals)

Signals are accumulated by `quiz_engine.py` from 6-8 quiz questions:

**Category 1 — Field Interest (12 signals):**
`field_mechanical`, `field_digital`, `field_business`, `field_health`, `field_creative`, `field_hospitality`, `field_agriculture`, `field_heavy_industry`, `field_electrical`, `field_civil`, `field_aero_marine`, `field_oil_gas`

**Category 2 — Work Preference (4 signals):**
`hands_on`, `problem_solving`, `people_helping`, `creative`

**Category 3 — Learning Tolerance (4 signals):**
`learning_by_doing`, `concept_first`, `rote_tolerant`, `project_based`

**Category 4 — Environment (4 signals):**
`workshop_environment`, `office_environment`, `high_people_environment`, `field_environment`

**Category 5 — Value Trade-offs (8 signals):**
`stability_priority`, `income_risk_tolerant`, `pathway_priority`, `fast_employment_priority`, `proximity_priority`, `allowance_priority`, `employment_guarantee`, `quality_priority`

**Category 6 — Energy Sensitivity (4 signals):**
`low_people_tolerance`, `mental_fatigue_sensitive`, `physical_fatigue_sensitive`, `high_stamina`

**Signal strength:** Score ≥2 = "strong", score 1 = "moderate"

**Multi-select weight splitting:** When a student selects 2+ options in a question, each signal's weight is reduced by 1 (minimum 1). Single selections keep original weight.

### Current Behaviour — Scoring Formula

```
final_score = BASE_SCORE (100) + total_adjustment (capped ±20)
```

Where `total_adjustment` = sum of 6 capped category scores + institution modifier.

### Category 1: Field Interest Matching

**Cap: FIELD_INTEREST_CAP = 8**

Maps quiz signals to taxonomy field_keys via `FIELD_KEY_MAP`:

| Quiz Signal | Maps To Field Keys |
|-------------|-------------------|
| `field_mechanical` | mekanikal, automotif, mekatronik |
| `field_digital` | it-perisian, it-rangkaian, multimedia |
| `field_business` | perniagaan, perakaunan, pengurusan |
| `field_health` | perubatan, farmasi, sains-hayat |
| `field_creative` | senireka, multimedia |
| `field_hospitality` | hospitaliti, kulinari, kecantikan |
| `field_agriculture` | pertanian, alam-sekitar |
| `field_heavy_industry` | mekanikal, automotif, mekatronik, aero, marin, minyak-gas, elektrik, sivil, senibina, kimia-proses |
| `field_electrical` | elektrik |
| `field_civil` | sivil, senibina |
| `field_aero_marine` | aero, marin |
| `field_oil_gas` | minyak-gas |

**Scoring rules:**
- Course `field_key` matches any mapped key from student's strongest field signal → **+8** (primary match)
- Student has multiple field interest signals and course matches a secondary one → **+4** (secondary match)
- No match → **0**

### Category 2: Work Preference

**Cap: WORK_PREFERENCE_CAP = 4**

| Student Signal | Course Tag Match | Points |
|----------------|-----------------|--------|
| `hands_on` | `work_modality = 'hands_on'` | +5 (capped to 4) |
| `hands_on` | `work_modality != 'hands_on'` | -3 (capped to -4) |
| `problem_solving` | `work_modality = 'mixed'` | +3 |
| `people_helping` | `people_interaction = 'high_people'` | +4 |
| `creative` | `learning_style` includes `'project_based'` | +4 |
| `creative` | `cognitive_type = 'abstract'` (no project_based) | +2 |

### Category 3: Environment Fit

**Cap: CATEGORY_CAP = 6**

| Student Signal | Course Tag Match | Points |
|----------------|-----------------|--------|
| `workshop_environment` | `environment = 'workshop'` | +4 |
| `high_people_environment` | `environment = 'office'` | +3 |
| `office_environment` | `environment = 'office'` | +4 |
| `field_environment` | `environment = 'field'` | +4 |

### Category 4: Learning Tolerance

**Cap: CATEGORY_CAP = 6**

| Student Signal | Course Tag Match | Points |
|----------------|-----------------|--------|
| `learning_by_doing` | `work_modality = 'hands_on'` OR `learning_style` includes `'project_based'` | +3 |
| `theory_oriented` | `cognitive_type = 'abstract'` OR `work_modality = 'mixed'` | +3 |
| `concept_first` | `cognitive_type = 'abstract'` OR `work_modality = 'theoretical'` | +3 |
| `project_based` | `learning_style` includes `'project_based'` | +3 |
| `rote_tolerant` | `learning_style` includes `'assessment_heavy'` | +3 |

### Category 5: Energy Sensitivity

**Cap: CATEGORY_CAP = 6**

| Student Signal | Course Tag Match | Points |
|----------------|-----------------|--------|
| `low_people_tolerance` | `people_interaction = 'high_people'` | **-6** (penalty) |
| `physical_fatigue_sensitive` | `load = 'physically_demanding'` | **-6** (penalty) |
| `mental_fatigue_sensitive` | `load = 'mentally_demanding'` | **-6** (penalty) |
| `high_stamina` | `load` is any `'demanding'` type | +2 (boost) |

### Category 6: Values Alignment

**Cap: CATEGORY_CAP = 6**

| Student Signal | Course Tag Match | Points |
|----------------|-----------------|--------|
| `income_risk_tolerant` | `outcome = 'entrepreneurial'` | +3 |
| `stability_priority` | `outcome` in `('regulated_profession', 'employment_first')` | +4 |
| `pathway_priority` | `outcome = 'pathway_friendly'` | +4 |
| `fast_employment_priority` | `outcome = 'employment_first'` | +4 |
| `fast_employment_priority` | `outcome = 'industry_specific'` | +2 |
| `fast_employment_priority` | `career_structure = 'stable'` | +1 |
| `fast_employment_priority` | `career_structure = 'volatile'` | -1 |
| `pathway_priority` + `fast_employment_priority` | (conflict) | -2 |
| `quality_priority` | `outcome` in `('pathway_friendly', 'regulated_profession')` | +1 |
| `stability_priority` | `career_structure = 'stable'` | +3 |
| `income_risk_tolerant` | `career_structure = 'volatile'` | +2 |
| `income_risk_tolerant` | `career_structure = 'portfolio'` | +2 |
| `stability_priority` | `credential_status = 'regulated'` | +2 |
| `creative` | `creative_output = 'expressive'` | +4 |
| `creative` | `creative_output = 'design'` | +3 |

### Institution Modifiers

**Cap: INSTITUTION_CAP = 5**

| Student Signal | Institution Modifier | Points |
|----------------|---------------------|--------|
| `income_risk_tolerant` | `urban = True` | +2 |
| `proximity_priority` | `cultural_safety_net = 'high'` | +4 |
| `proximity_priority` | `cultural_safety_net = 'low'` | -2 |
| `proximity_priority` + `fast_employment_priority` | `cultural_safety_net = 'high'` | +2 additional |

### Final Score Calculation

```
category_scores = {
    field_interest:               capped to ±8
    work_preference_signals:      capped to ±4
    learning_tolerance_signals:   capped to ±6
    environment_signals:          capped to ±6
    value_tradeoff_signals:       capped to ±6
    energy_sensitivity_signals:   capped to ±6
}

fit_adjustment = sum(category_scores)            # theoretical max ±36
inst_adjustment = capped to ±5
total_adjustment = fit + inst, capped to ±20     # GLOBAL_CAP
merit_penalty = {High: 0, Fair: -5, Low: -15}

final_score = 100 + total_adjustment + merit_penalty
```

**Typical score range:** 80–120

### Pre-University Course Scoring (Quiz Active)

Pre-U courses (Asasi, Matric, STPM pathways) use dedicated scoring with quiz signal adjustments:

**Signal Adjustment Table (capped to ±PRE_U_SIGNAL_CAP = 6):**

| Signal | Adjustment | Condition |
|--------|------------|-----------|
| `problem_solving` | +2 | Course is NOT social science |
| `creative` | +1 | Course IS social science |
| `hands_on` | -1 | Always |
| `workshop_environment` | -1 | Always |
| `field_environment` | -1 | Always |
| `concept_first` | +2 | Always |
| `rote_tolerant` | +1 | Always |
| `learning_by_doing` | -1 | Always |
| `pathway_priority` | +3 | Always |
| `fast_employment_priority` | -2 | Always |
| `quality_priority` | +2 | Always |
| `employment_guarantee` | -1 | Always |
| `allowance_priority` | +2 | Matric only |
| `proximity_priority` | +1 | STPM pathway only |
| `mental_fatigue_sensitive` | -2 | Always |
| `high_stamina` | +1 | Always |

**Field preference bonus:** +3 if student's field_interest matches course's field.

### Sort Order

Same 7-level hierarchy as pre-quiz (see Section 2).

### Strengths

1. **Rich signal coverage** — 36 signals across 6 categories capture diverse student preferences
2. **Course-tag matching is granular** — 12+ tag dimensions per course enable fine-grained differentiation
3. **Energy sensitivity penalties are smart** — negative scores for genuine mismatches prevent poor recommendations
4. **Institution modifiers add real-world context** — urban/rural and community support factors
5. **Merit penalty grounds scores in reality** — prevents high-fit but low-admission-chance courses from dominating
6. **Well-tested** — 62 ranking tests cover caps, edge cases, and tie-breaking

### Weaknesses

| # | Weakness | Impact | Severity |
|---|----------|--------|----------|
| W4 | **73 PISMP courses have no course tags** — returns BASE_SCORE (100) with no adjustments, identical to pre-quiz | ~73 teaching courses get no personalisation | High |
| W5 | **Cap asymmetry** — field interest cap is 8, work preference cap is 4, others are 6. Field interest contributes 2x work preference with no documented rationale | May over-weight field match relative to working style fit | Medium |
| W6 | **Multi-select weight splitting dilutes signals** — selecting 2+ options reduces weight by 1 (min 1). Broad-interest students get weaker signals than focused ones | Penalises honestly broad-interest students | Medium |
| W7 | **FIELD_KEY_MAP coverage gaps** — only 12 field_interest signals map to field_keys. Field taxonomy has ~45 keys. Unmapped fields (e.g., `pelancongan`, `alam_sekitar`) get no field interest boost | Courses in niche fields are systematically under-ranked | High |
| W8 | **Institution modifiers sparsely populated** — only institutions with non-empty `modifiers` JSON contribute | Institution-level differentiation available for only a subset | Medium |
| W9 | **No negative field mismatch penalty** — if student prefers engineering but a culinary course has no matching field_key, score is +0 (no boost) rather than a penalty | Mismatched courses aren't pushed down, just not boosted | Low |
| W10 | **Fit reasons are English-only** — `fit_reasons` list generated in English regardless of user language | Inconsistent with bilingual BM/EN approach | Low |

### Proposed Improvements

1. **Backfill 73 PISMP course tags (W4).** Create a `generate_pismp_tags` management command mapping teaching specialisations to course tags (e.g., PISMP Sains → `cognitive_type: abstract`, `environment: lab`). Estimate: 2-3 hours.

2. **Expand FIELD_KEY_MAP coverage (W7).** Map remaining field taxonomy keys to quiz signals. Where no direct quiz signal exists, add a `field_general` fallback or map through parent categories.

3. **Document cap rationale (W5).** Add reasoning comments in `ranking_engine.py` explaining each cap value. Consider equalising to 6 or explicitly justifying the asymmetry.

4. **Auto-populate institution modifiers (W8).** Use institution location data (state, parliament, DUN) already in the Institution model to auto-populate `urban` and `cultural_safety_net` modifiers.

---

## 4. STPM Pre-Quiz Ranking

### Current Behaviour

```
fit_score = BASE_SCORE (50) + CGPA_margin_component
```

**CGPA Margin Calculation:**
```
raw_margin = student_cgpa - course.min_cgpa
clamped_margin = clamp(raw_margin, -CGPA_MARGIN_CAP, +CGPA_MARGIN_CAP)
                                    -1.0              +1.0
cgpa_points = clamped_margin × CGPA_MARGIN_MULTIPLIER (20)
```

So CGPA margin contributes **-20 to +20 points**.

**No other components active:** field match, RIASEC alignment, efficacy, goal alignment, resilience, and interview penalty all require quiz signals and produce 0 without them.

**Sort:** fit_score descending, then course_name ascending. No institution or credential tie-breaking.

**Score range:** 30–70 (unlike SPM's flat 100).

### Strengths

1. **CGPA margin is the strongest single predictor** — academic readiness is the primary admission filter for degree programmes
2. **Meaningful score differentiation** — produces a real range (30–70) unlike SPM pre-quiz's flat 100
3. **Correctly conservative** — doesn't pretend to know student preferences without quiz data

### Weaknesses

| # | Weakness | Impact | Severity |
|---|----------|--------|----------|
| W11 | **No field filtering** — a science-stream student sees arts programmes ranked equally if CGPA margins match. STPM students typically have clearer field direction than SPM (they chose a stream) | Feels especially wrong for this cohort | High |
| W12 | **STPM subject requirements not factored** — a student with Biology sees a Physics-requiring programme ranked the same as a Biology-requiring one | Can surface poorly-suited programmes | Medium |
| W13 | **Interview penalty not applied pre-quiz** — competitive programmes (Medicine, Law) get no score adjustment | May over-rank highly competitive programmes | Low |
| W14 | **Minimal sort tie-breaking** — only score then name. No credential/institution hierarchy | Arbitrary ordering within score tiers | Medium |

### Proposed Improvements

1. **Use STPM stream as a free signal (W11).** Student's STPM subjects are already known from grade input. Map subjects to field taxonomy keys (using `SUBJECT_RIASEC_MAP` already in `stpm_quiz_data.py`) and apply a field_match boost (+4 to +8) for courses whose `field_key` aligns with the student's subject cluster. Requires no quiz.

2. **Factor subject requirements into pre-quiz score (W12).** Check if student has required STPM subjects. All required subjects present → +3 boost; missing a required subject → -5 penalty. Data already in `StpmRequirement`.

3. **Apply interview penalty pre-quiz (W13).** The `req_interview` flag is already on StpmCourse. Apply the same -3 penalty used post-quiz.

4. **Add richer sort tie-breaking (W14).** Mirror SPM: fit_score → university type → min_cgpa competitiveness → course name.

---

## 5. STPM Post-Quiz Ranking

### Signal Taxonomy (8 Categories, ~60 Signals)

Signals are accumulated by `stpm_quiz_engine.py` from branching quiz questions:

**Category 1 — RIASEC Seed (6 signals):**
`riasec_R`, `riasec_I`, `riasec_A`, `riasec_S`, `riasec_E`, `riasec_C`
Pre-seeded from STPM subjects before quiz starts.

**Category 2 — Field Interest (9 signals):**
`field_engineering`, `field_health`, `field_pure_science`, `field_tech`, `field_business`, `field_law`, `field_education`, `field_creative`, `field_finance`

**Category 3 — Field Key (34 signals):**
`field_key_mekanikal`, `field_key_elektrik`, `field_key_sivil`, `field_key_kimia`, `field_key_aero`, `field_key_perubatan`, `field_key_farmasi`, `field_key_allied`, `field_key_health_admin`, `field_key_sains_fizik`, `field_key_sains_kimia`, `field_key_sains_bio`, `field_key_alam`, `field_key_it_sw`, `field_key_it_net`, `field_key_it_data`, `field_key_multimedia`, `field_key_pemasaran`, `field_key_hr`, `field_key_intl`, `field_key_entrepren`, `field_key_law`, `field_key_admin`, `field_key_ir`, `field_key_pendidikan`, `field_key_kaunseling`, `field_key_sosial`, `field_key_media`, `field_key_senireka`, `field_key_digital`, `field_key_pr`, `field_key_perakaunan`, `field_key_kewangan`, `field_key_aktuari`, `field_key_fin_plan`

**Category 4 — Cross-Domain (6 signals):**
`cross_R`, `cross_I`, `cross_A`, `cross_S`, `cross_E`, `cross_C`

**Category 5 — Efficacy (6 signals):**
`efficacy_confirmed`, `efficacy_confident`, `efficacy_open`, `efficacy_redirect`, `efficacy_uncertain`, `efficacy_mismatch`

**Category 6 — Resilience (2 signals):**
`resilience_redirect`, `resilience_supported`

**Category 7 — Career Goal (4 signals):**
`goal_professional`, `goal_postgrad`, `goal_employment`, `goal_entrepreneurial`

**Category 8 — Context (7 signals):**
`crystallisation_high`, `crystallisation_moderate`, `crystallisation_low`, `motivation_intrinsic`, `motivation_extrinsic`, `motivation_mixed`, `family_support_high`, `family_support_low`

### Current Behaviour — Scoring Formula

```
fit_score = BASE_SCORE (50)
           + CGPA margin       (max ±20)
           + field match       (max +12)
           + RIASEC alignment  (max +8)
           + efficacy modifier (+4 to -2)
           + goal alignment    (max +4)
           - interview penalty (-3 or 0)
           - resilience disc.  (0 to -3)
```

**Maximum theoretical score: 50 + 20 + 12 + 8 + 4 + 4 - 0 - 0 = 98**
**Minimum theoretical score: 50 - 20 + 0 + 0 - 2 + 0 - 3 - 3 = 22**

### Component 1: CGPA Margin (max ±20)

```
raw_margin = student_cgpa - course.min_cgpa
clamped = clamp(raw_margin, -1.0, +1.0)
points = clamped × 20
```

| Example | Points |
|---------|--------|
| CGPA 3.8, min 3.0 → margin 0.8 | +16 |
| CGPA 3.0, min 3.0 → margin 0.0 | 0 |
| CGPA 2.5, min 3.0 → margin -0.5 | -10 |
| CGPA 4.0, min 2.5 → margin 1.0+ (capped) | +20 |

### Component 2: Field Match (max +12)

| Source | Match Type | Points |
|--------|-----------|--------|
| Q3 `field_key` signal | Primary: signal maps to course's `field_key` | +8 |
| Q2 `field_interest` signal | Secondary: interest maps to course's `field_key` via lookup | +4 |
| Q5 `cross_domain` signal | Cross-domain: RIASEC cross-type matches course | +2 |

Total capped at FIELD_MATCH_CAP = 12.

### Component 3: RIASEC Alignment (max +8)

| Match Type | Points |
|-----------|--------|
| Course `riasec_type` matches student's primary RIASEC seed | +6 |
| Course `riasec_type` matches student's secondary seed | +3 |
| Course `riasec_type` matches Q5 cross-domain RIASEC | +2 |

Total capped at RIASEC_ALIGNMENT_CAP = 8.

### Component 4: Efficacy Modifier (+4 to -2)

Based on Q4 efficacy signal:

| Signal | Points | Meaning |
|--------|--------|---------|
| `efficacy_confirmed` | +4 | Student feels strong alignment with field demands |
| `efficacy_confident` | +2 | Moderate confidence |
| `efficacy_open` | 0 | Neutral/exploring |
| `efficacy_redirect` | -1 | Considering different direction |
| `efficacy_uncertain` | -1 | Unsure about fit |
| `efficacy_mismatch` | -2 | Feels misaligned with field demands |

### Component 5: Goal Alignment (max +4)

| Student Goal | Required Course Field | Points |
|-------------|----------------------|--------|
| `goal_professional` | `field_key` in professional fields* | +4 |
| `goal_professional` | `field_key` NOT in professional fields | +2 |
| `goal_postgrad` | `field_key` in research fields** | +4 |
| `goal_postgrad` | `field_key` NOT in research fields | +2 |
| `goal_employment` | Any | +3 |
| `goal_entrepreneurial` | `field_key` in business fields*** | +3 |
| `goal_entrepreneurial` | `field_key` NOT in business fields | +2 |

*Professional fields: perubatan, farmasi, undang-undang, mekanikal, elektrik, sivil, mekatronik, kimia-proses, aero, marin, senibina
**Research fields: sains-tulen, bioteknologi, sains-hayat, it-perisian, kimia-proses
***Business fields: perniagaan, pengurusan, pemasaran, perakaunan, kewangan

### Component 6: Interview Penalty

| Condition | Points |
|-----------|--------|
| Course requires interview (`req_interview = True`) | -3 |
| No interview required | 0 |

### Component 7: Resilience Discount (0 to -3)

Cross-references student's resilience signal with course difficulty level:

| Resilience Signal | Difficulty Level | Points |
|------------------|-----------------|--------|
| `resilience_redirect` | `high` | -3 |
| `resilience_redirect` | `moderate` | -1 |
| `resilience_supported` | `high` | -1 |
| All other combinations | — | 0 |

### Result Framing

Based on Q1 crystallisation signal, the frontend receives a framing mode:

| Crystallisation | Mode | Heading | Subtitle |
|-----------------|------|---------|----------|
| `crystallisation_high` | confirmatory | "Your profile aligns with these programmes" | "These match your academic strength and interests" |
| `crystallisation_moderate` | guided | "Based on your interests, consider these programmes" | "Explore options that fit your profile" |
| `crystallisation_low` | discovery | "Here are fields worth exploring" | "Discover programmes across different areas" |

### Sort Order

1. Fit score (descending)
2. Course name (ascending)

No additional tie-breaking levels.

### Strengths

1. **Most sophisticated ranking** — 7 components capture academic readiness, field fit, cognitive style, career direction, and resilience
2. **Efficacy modifier is uniquely insightful** — distinguishes 6 confidence levels, actively penalising poor-fit signals
3. **Result framing is excellent UX** — sets appropriate expectations based on crystallisation level
4. **RIASEC uses both subject seed and quiz data** — cross-validates academic choices with expressed preferences
5. **Goal alignment differentiates career paths** — professional, postgrad, entrepreneurial, and employment goals each boost different programme types
6. **Resilience-difficulty matching prevents burnout** — high-difficulty programmes penalised for students with redirect resilience profile
7. **Well-tested** — 58 ranking tests, comprehensive coverage of each component

### Weaknesses

| # | Weakness | Impact | Severity |
|---|----------|--------|----------|
| W15 | **No course-tag matching (unlike SPM)** — uses `field_key`, `riasec_type`, `difficulty_level` on StpmCourse directly, not granular tags. Two Engineering programmes (one lab-heavy, one office-heavy) score identically | Less personalised for non-academic preferences | Medium |
| W16 | **Enrichment data may be incomplete** — `riasec_type`, `difficulty_level`, `efficacy_domain` added via `enrich_stpm_riasec` command. Courses with unmapped field_keys get defaults (riasec=None, difficulty='moderate', efficacy=None) | Courses with missing enrichment get neutral scores | Medium |
| W17 | **No institution modifiers** — unlike SPM, no urban/rural or community support adjustments | Real-world factors invisible | Low |
| W18 | **Score range narrow in practice** — most students cluster 45–75. Two very different programmes might score 62 vs 64 | Small differences may not reflect meaningful fit differences | Medium |
| W19 | **No merit/admission chance layer** — no High/Fair/Low label or discrete merit penalty beyond CGPA margin | CGPA margin partly addresses this, but no clear admission-chance communication | Low |

### Proposed Improvements

1. **Add lightweight course tags to StpmCourse (W15).** Add 3-4 tag fields: `learning_mode` (research/clinical/studio/lecture), `work_environment` (lab/office/field/studio), `people_intensity` (high/moderate/low). Map quiz signals to these for environment/style matching.

2. **Audit enrichment completeness (W16).** Run `enrich_stpm_riasec --dry-run` and report coverage. Target: 95%+ before deploying quiz-informed ranking.

3. **Add score confidence tiers (W18).** Instead of raw fit_score, show: "Sangat Sesuai" (≥70), "Sesuai" (55–69), "Boleh Dipertimbangkan" (<55).

4. **Add admission confidence indicator (W19).** Calculate from CGPA margin: "Peluang Tinggi" (margin ≥ 0.5), "Peluang Sederhana" (0–0.49), "Peluang Rendah" (< 0).

---

## 6. Cross-Cutting Observations

### SPM vs STPM Architecture Comparison

| Aspect | SPM | STPM |
|--------|-----|------|
| Base score | 100 | 50 |
| Max adjustment | ±20 (GLOBAL_CAP) | +48/-28 (no global cap) |
| Score range | 80–120 | 22–98 |
| Tag system | 12+ dimensions via CourseTag model | 3 fields on StpmCourse directly |
| Field matching | Via FIELD_KEY_MAP (12 signals → field_keys) | Via STPM_FIELD_KEY_MAP (34 signals → field_keys) |
| Merit handling | Discrete penalty (0/-5/-15) | Continuous CGPA margin |
| Institution factors | urban, cultural_safety_net modifiers | None |
| Sort tie-breaking | 7-level hierarchy | 2-level (score, name) |
| Quiz questions | 6-8 (linear) | ~10 (branching by stream) |
| Pre-quiz differentiation | Flat 100 (except pre-U) | 30–70 via CGPA margin |

### Signal Coverage Gap

SPM field taxonomy has ~45 keys but only 12 quiz signals map to them. STPM has 34 `field_key` signals covering much more of the taxonomy. This asymmetry means SPM field matching is significantly less precise than STPM.

### Data Completeness Concerns

| Data Gap | Affected Courses | Impact |
|----------|-----------------|--------|
| PISMP courses without course tags | 73 | No SPM post-quiz differentiation |
| Institutions without modifiers | Unknown (likely many) | No institution-level SPM adjustments |
| StpmCourse without enrichment | Unknown (run audit) | Neutral RIASEC/efficacy scoring |
| Offerings without tuition fees | 87 | No cost-based ranking (not currently a factor) |

---

## 7. Priority Matrix

| # | Fix | Effort | Impact | Priority |
|---|-----|--------|--------|----------|
| W4 | Backfill 73 PISMP course tags | Medium (2-3h) | High | **P1** |
| W7 | Expand SPM FIELD_KEY_MAP coverage | Low (1h) | High | **P1** |
| W11 | Use STPM stream as free pre-quiz signal | Medium (2-3h) | High | **P1** |
| W1 | Show "Admission Chance" not fit_score pre-quiz | Low (1h) | Medium | **P2** |
| W8 | Auto-populate institution modifiers | Medium (2h) | Medium | **P2** |
| W14 | Richer STPM sort tie-breaking | Low (30min) | Medium | **P2** |
| W15 | Lightweight STPM course tags | High (4-5h) | Medium | **P2** |
| W16 | Audit STPM enrichment completeness | Low (30min) | Medium | **P2** |
| W18 | Score confidence tiers for STPM | Low (1h) | Medium | **P2** |
| W5 | Document/review cap rationale | Low (30min) | Medium | **P3** |
| W6 | Review multi-select weight splitting | Low (1h) | Medium | **P3** |
| W12 | Factor subject reqs into STPM pre-quiz | Medium (2h) | Medium | **P3** |
| W19 | STPM admission confidence indicator | Low (1h) | Low | **P3** |
| W10 | Bilingual fit_reasons | Low (1h) | Low | **P4** |
| W13 | Interview penalty pre-quiz | Low (15min) | Low | **P4** |
| W17 | STPM institution modifiers | Medium (2h) | Low | **P4** |
| W3 | Institution location/preference pre-quiz | Medium (2h) | Low | **P4** |
| W9 | Negative field mismatch penalty | Low (1h) | Low | **P4** |

### Recommended First Sprint

The three P1 items would significantly improve ranking quality across all four modes:

1. **Backfill PISMP course tags** — eliminates the largest data gap (73 courses with zero differentiation)
2. **Expand FIELD_KEY_MAP** — improves SPM field matching for niche fields
3. **STPM stream as pre-quiz signal** — transforms STPM pre-quiz from CGPA-only to CGPA + field-aware

---

*End of audit. This document should be updated when any ranking logic changes.*
