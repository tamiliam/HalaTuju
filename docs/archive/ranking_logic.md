# Ranking Logic & Taxonomy (v1.5)

**Version:** 1.5
**Last Updated:** 2026-02-04
**Status:** Live Implementation

**Changelog v1.5:**
- Added Section 7: Comprehensive tie-breaking hierarchy documentation
- Established 5-level cascade for equal-score sorting
- Clarified credential priority with ASASI/Foundation as highest (4)
- Documented clear university institution hierarchy (14/13/12/11)
- Added merit cutoff as competitiveness-based tie-breaker (Level 4)

This document serves as the definitive source of truth for the adversarial testing of the ranking engine. It describes the data taxonomy, input signals, and the exact scoring logic used in `src/ranking_engine.py`.

---

## Section 1: The Course Tagging Taxonomy
**Source:** `data/course_tags.json`

Every course is assigned a set of tags defining its nature.

### 1. Work Modality
*Describes the primary way work is performed.*
*   `hands_on`: Requires physical manipulation of tools, machinery, or materials.
*   `mixed`: A balance of practical tasks and theoretical work.
*   `theoretical`: Focuses on abstract concepts, calculations, or writing.

### 2. People Interaction
*Describes the frequency and intensity of social interaction.*
*   `high_people`: Constant interaction (clients, customers, patients).
*   `moderate_people`: Regular but structured interaction (teams, colleagues).
*   `low_people`: Minimal interaction; solitary work focus.

### 3. Cognitive Type
*Describes the primary mode of thinking required.*
*   `abstract`: Conceptual, strategic, or design-oriented thinking.
*   `problem_solving`: Diagnostic, analytical, or troubleshooting focus.
*   `procedural`: Following set rules, protocols, or standard operating procedures.

### 4. Learning Style
*Describes how the course is assessed and taught (Array: can have multiple).*
*   `assessment_heavy`: Graded primarily through exams and written tests.
*   `continuous_assessment`: Graded through ongoing coursework and quizzes.
*   `project_based`: Graded through major projects or portfolios.

### 5. Load (Fatigue Type)
*Describes the type of exhaustion expected.*
*   `physically_demanding`: Requires physical stamina; risk of physical fatigue.
*   `mentally_demanding`: Requires intense concentration; risk of cognitive burn-out.
*   `balanced_load`: Standard mix of physical and mental effort.

### 6. Outcome
*Describes the typical career trajectory.*
*   `employment_first`: Aimed at immediate entry into the workforce.
*   `entrepreneurial`: skills suited for self-employment or business creation.
*   `industry_specific`: Niche skills for a specific sector (e.g., Oil & Gas).
*   `pathway_friendly`: Designed to easily credit transfer to a university degree.
*   `private_sector_dominant`: High demand in corporate/private companies.
*   `public_sector_friendly`: Aligns well with government/civil service roles.
*   `regulated_profession`: Leads to professional licensure (e.g., Engineers, Architects).

### 7. Environment
*Describes the physical setting of the work.*
*   `field`: Outdoors, construction sites, or nature.
*   `lab`: Controlled scientific or technical environments.
*   `office`: Indoor, desk-based corporate environments.
*   `workshop`: Industrial floors, garages, or studios.
*   `mixed_environment`: Variable settings.

### 8. Service Orientation (New in v1.1)
*   `care`: Helping, healing, teaching, or supporting people.
*   `service`: Transactional support or sales.
*   `neutral`: Roles where people-pleasing is not primary.

### 9. Interaction Type (New in v1.1)
*   `relational`: Long-term, trust-based bonds.
*   `transactional`: Short-term, task-based interactions.
*   `mixed`: A balance of both.

### 10. Career Structure (New in v1.1)
*   `stable`: Predictable income, clear hierarchy.
*   `volatile`: High risk/reward, sales-based.
*   `portfolio`: Project-based or freelance heavy.

### 11. Credential Status (New in v1.1)
*   `regulated`: Requires a license/cert to practice.
*   `unregulated`: Skills-based, no legal barrier.

### 12. Creative Output (New in v1.1)
*   `expressive`: Artistic, aesthetic, or emotive.
*   `design`: Functional problem-solving.
*   `none`: Execution-focused.

---

## Section 2: The Institution Tagging Taxonomy
**Source:** `data/institutions.json`

Modifiers that affect scoring based on user preferences.

*   `urban` (Boolean): `True` if located in a city/town center; `False` if rural.
*   `cultural_safety_net` (String): Level of existing community support. (`high`, `moderate`, `low`)
*   `subsistence_support` (Boolean): `True` if financial aid/food included. *(Not currently used in ranking)*
*   `strong_hostel` (Boolean): `True` if on-campus housing is guaranteed. *(Not currently used in ranking)*

---

## Section 3: Quiz Logic (Input Layer)
**Source:** `src/quiz_data.py`

| Question | Answer Option | Mapped Signal | Strength |
| :--- | :--- | :--- | :--- |
| **Q1: Work Style** | Working with tools, machines... | `hands_on` | +2 |
| | Solving problems, calculations... | `problem_solving` | +2 |
| | Helping, teaching, or assisting... | `people_helping` | +2 |
| | Creating or designing things | `creative` | +2 |
| | Organising, coordinating... | `organising` | +2 |
| **Q2: Environment** | Workshop, lab, technical space | `workshop_environment` | +1 |
| | Office or computer-based | `office_environment` | +1 |
| | Many people interaction | `high_people_environment` | +1 |
| | Field work, site visits | `field_environment` | +1 |
| **Q3: Learning** | Learn best by doing... | `learning_by_doing` | +1 |
| | Understanding concepts first | `concept_first` | +1 |
| | Okay memorising... | `rote_tolerant` | +1 |
| | Better with projects... | `project_based` | +1 |
| | Struggle with exams... | `exam_sensitive` | +1 |
| **Q4: Values** | Job stability | `stability_priority` | +2 |
| | Income potential (risk) | `income_risk_tolerant` | +2 |
| | Continue to degree | `pathway_priority` | +2 |
| | Meaningful work | `meaning_priority` | +2 |
| | Finishing quickly | `fast_employment_priority` | +2 |
| **Q5: Fatigue** | Dealing with many people | `low_people_tolerance` | +1 |
| | Technical/detailed work | `mental_fatigue_sensitive` | +1 |
| | Physical/hands-on work | `physical_fatigue_sensitive` | +1 |
| | Time pressure | `time_pressure_sensitive` | +1 |
| **Q6: Survival** | Monthly allowance | `allowance_priority` | +3 |
| | Staying close to home | `proximity_priority` | +3 |
| | Guaranteed job interview | `employment_guarantee` | +2 |

---

## Section 4: Signal Aggregation (Transformation Layer)
**Source:** `src/quiz_manager.py`

Raw signals are grouped into 5 semantic categories for the ranking engine.
*Ref: `QuizManager.get_final_results()`*
*(Note: Signal group names correspond to internal category groupings used for cap enforcement.)*

1.  **Work Preference**: `hands_on`, `problem_solving`, `people_helping`, `creative`, `organising`
2.  **Environment**: `workshop`, `office`, `high_people`, `field`
3.  **Learning Tolerance**: `learning_by_doing`, `concept_first`, `rote_tolerant`, `project_based`, `exam_sensitive`
4.  **Values**: `stability`, `income_risk`, `pathway`, `meaning`, `fast_employment`, `proximity`, `allowance`
5.  **Energy Sensitivity**: `low_people_tolerance`, `mental_fatigue`, `physical_fatigue`, `time_pressure`

---

## Section 5: The Ranking Engine (The Math)
**Source:** `src/ranking_engine.py`

**Base Score:** `100`

### 1. Scoring Truth Table (Interactions)

| Row | Student Signal (Input) | Course Tag (Target) | Score Change | Reason / Note |
| :-- | :--- | :--- | :--- | :--- |
| **Work** | `hands_on` | `work_modality` == 'hands_on' | **+5** | Perfect modality match |
| | `hands_on` (Missing) | `work_modality` == 'hands_on' | **-3** | Mismatch penalty |
| | `problem_solving` | `work_modality` == 'mixed' | **+3** | Good fit |
| | `people_helping` | `people_interaction` == 'high_people' | **+4** | Desire to help meets opportunity |
| | `creative` | `learning_style` contains 'project_based' | **+4** | Creative + Projects = Win |
| | `creative` (Fallback) | `cognitive_type` == 'abstract' | **+2** | If not project-based, still fits abstract |
| | `creative` | `creative_output` == 'expressive' | **+4** | **v1.2: Art/Music match** |
| | `creative` | `creative_output` == 'design' | **+3** | **v1.2: Design match** |
| **Env** | `workshop_environment` | `environment` == 'workshop' | **+4** | Direct match |
| | `high_people_environment` | `environment` == 'office' OR `high_people` | **+3** | Social preference match |
| | `office_environment` | `environment` == 'office' | **+4** | Direct match |
| | `field_environment` | `environment` == 'field' | **+4** | Direct match |
| **Learning** | `learning_by_doing` | `modality`=='hands_on' OR `project_based` | **+3** | Active learning match |
| | `theory_oriented` | `modality` IN ['theory', 'mixed'] | **+3** | Theory tolerant |
| | `concept_first` | `modality`=='theoretical' OR `abstract` | **+3** | Conceptual match |
| | `project_based` | `learning_style` contains 'project_based' | **+3** | Assessment style match |
| **Energy** **(Safety)** | `low_people_tolerance` | `people_interaction` == 'high_people' | **-6** | **Introvert Burnout Protection** |
| | `low_people_tolerance` | `interaction_type` == 'transactional' | **-2** | **v1.2: Burnout (Transactional)** |
| | `low_people_tolerance` | `service_orientation` == 'service' | **-2** | **v1.2: Burnout (Service)** |
| | `physical_fatigue_sensitive` | `load` == 'physically_demanding' | **-6** | **Physical Safety Rail** |
| | `mental_fatigue_sensitive` | `load` == 'mentally_demanding' | **-6** | **Cognitive Safety Rail** |
| **Values** | `income_risk_tolerant` | `outcome` == 'entrepreneurial' | **+3** | Risk appetite match |
| | `income_risk_tolerant` | `career_structure` == 'volatile' | **+2** | **v1.2: Volatility Match** |
| | `income_risk_tolerant` | `career_structure` == 'portfolio' | **+2** | **v1.2: Portfolio Match** |
| | `stability_priority` | `outcome` IN ['regulated', 'employment'] | **+4** | Safety match |
| | `stability_priority` | `career_structure` == 'stable' | **+3** | **v1.2: Structure Match** |
| | `stability_priority` | `credential_status` == 'regulated' | **+2** | **v1.2: Confidence Boost** |
| | `pathway_priority` | `outcome` == 'pathway_friendly' | **+4** | Degree route match |
| | `pathway_priority` | `outcome` == 'pathway_friendly' AND `fast_emp` conflict | **-2** | **v1.3: Balancing Penalty** |
| | `fast_employment_priority`| `outcome` == 'employment_first' | **+4** | **v1.3: Fast Track Match** |
| | `fast_employment_priority`| `outcome` == 'industry_specific' | **+2** | **v1.3: Niche Skill Match** |
| | `fast_employment_priority`| `career_structure` == 'stable' | **+1** | **v1.3: Safe fast money** |
| | `fast_employment_priority`| `career_structure` == 'volatile' | **-1** | **v1.3: Risky fast money** |
| | `meaning_priority` | `high_people` OR `regulated_profession` | **+3** | Service/Meaning match |
| | `meaning_priority` | `service_orientation` == 'care' | **+4** | **v1.2: Deep Meaning (Care)** |
| | `meaning_priority` | `interaction_type` == 'relational' | **+3** | **v1.2: Relational Meaning** |
| | `meaning_priority` | `service_orientation` == 'service' | **+1** | **v1.2: Service Meaning** |

### 2. Institution Modifiers (Tie-Breakers)

| Student Signal | Institution Modifier | Score Change |
| :--- | :--- | :--- |
| `income_risk_tolerant` | `urban` == True | **+2** (Urban center opportunity) |
| `proximity_priority` | `cultural_safety_net` == 'high' | **+4** (Strong community support) |
| `proximity_priority` | `cultural_safety_net` == 'low' | **-2** (Isolation penalty) |
| `fast_employment` + `proximity` | `cultural_safety_net` == 'high' | **+2** (v1.3: Local job network) |


### 3. Merit Penalty (v1.4 - "Reality Check")

Applied **after** fit score calculation. Only affects courses with `merit_cutoff` data (Poly/KK/UA).

| Merit Status | Condition | Penalty |
| :--- | :--- | :--- |
| **High Chance** | `student_merit >= cutoff` | **0** (no penalty) |
| **Fair Chance** | `student_merit >= cutoff - 5` | **-5** |
| **Low Chance** | `student_merit < cutoff - 5` | **-15** |

*   **Rationale:** A course may be a great "fit" based on preferences, but if admission probability is low, it should rank lower than equally-fitting courses with better admission chances.
*   **No Merit Data:** Courses without `merit_cutoff` (e.g., TVET, PISMP) receive no penalty.

### 4. Caps & Limits
*   **Institution Cap:** Max **+/- 5** points from institution modifiers logic.
*   **Category Cap:** Max **+/- 6** points per signal category (e.g., you can't get +20 just from Work Preference matches).
*   **Global Cap:** Total adjustment is clamped to **+/- 20** points from Base Score.
*   **Merit Penalty:** Applied after global cap, can push score below 80.
    *   *Min Score (without merit penalty):* 80
    *   *Max Score:* 120
    *   *Theoretical Min (with Low Chance penalty):* 65

### 5. Edge Cases & Limits
*   **Non-Additive Semantics:** Multiple rules within the same category may fire, but their combined effect is constrained by category caps (±6) to prevent over-amplification.

---

## Section 6: Interpretive Notes for Adversarial Testing
*Specific guidance for interpreting engine behavior.*

### 1. Terminology Drift
*   **Note:** Quiz signals (e.g., `high_people`) are mapped internally to taxonomy fields (e.g., `people_interaction`) via explicit condition checks in `ranking_engine.py`. These are NOT always string-identical fields.

### 2. Intentional Redundancy (Outcome vs. Credential)
*   **Context:** Scoring rules reference both `outcome: regulated` and `credential_status: regulated`.
*   **Design Intent:** This is intentional. One represents career trajectory, the other represents credential confidence. Category caps (`±6`) prevent double-counting from inflating scores beyond intent.

### 3. Meaning Priority Saturation
*   **Context:** High meaning scores (Care + Relational + Service) can theoretically reach +11.
*   **Expectation:** These categories will saturate the **Values** cap (+6). Differentiation for these professions is expected to occur via **Energy** and **Load** penalties (Safety Rails), not Value scores.

### 4. Energy Safety Asymmetry
*   **Principle:** Energy sensitivity operates as a **safety rail**, not a preference booster. The absence of penalties is the "reward". Do not expect positive boosts for low-interaction roles, only penalties for high-interaction ones.

### 5. Rule-to-Cap Mapping (v1.2)
*Clarifying which category cap applies to multi-axis rules.*

| Rule Trigger | Category Cap Used |
| :--- | :--- |
| `creative` + `creative_output` | **Work Preference** |
| `meaning_priority` + `service_orientation` | **Values** |
| `meaning_priority` + `interaction_type` | **Values** |
| `low_people_tolerance` + `interaction_type` | **Energy Sensitivity** |
| `low_people_tolerance` + `service_orientation` | **Energy Sensitivity** |
| `income_risk` + `career_structure` | **Values** |
| `stability` + `career_structure` | **Values** |
| `stability` + `credential_status` | **Values** |

---

## Section 7: Tie-Breaking Hierarchy (v1.5)
**Source:** `src/ranking_engine.py` (lines 462-485)

When multiple courses have the **same fit score**, they are sorted using a comprehensive 5-level cascade to ensure consistent, predictable ranking order.

### The 5-Level Cascade

```
Level 1: Fit Score (Descending)           ← Primary ranking signal
    ↓
Level 2: Credential Priority (Descending)  ← Program type hierarchy
    ↓
Level 3: Institution Priority (Descending) ← Institution reputation/type
    ↓
Level 4: Merit Cutoff (Descending)        ← Admission competitiveness
    ↓
Level 5: Course Name (Ascending)          ← Alphabetical (final tie-breaker)
```

### Level 1: Fit Score (Primary)

The **fit score** (80-120 range) is calculated as documented in Section 5. This is the primary ranking signal representing how well a course matches the student's profile.

**Example:**
- Course A: Score 105
- Course B: Score 105
- Course C: Score 98

**Result:** A and B tie at 105, both rank above C. Proceed to Level 2 to break A vs B tie.

---

### Level 2: Credential Priority

Foundation/ASASI programs are prioritized highest because they provide the **clearest pathway to degree programs**, which is highly valued by students.

**Credential Priority Table:**

| Priority | Credential Type | Examples | Rationale |
| :---: | :--- | :--- | :--- |
| **4** | ASASI / Foundation | "ASASI Kejuruteraan", "Foundation in Science" | Gateway to degree, articulation agreements with universities |
| **3** | Diploma | "Diploma Kejuruteraan Mekanikal" | 2-3 year programs, industry-ready + degree pathway option |
| **2** | Sijil Lanjutan | "Sijil Lanjutan Teknologi" | Advanced certificates |
| **1** | Sijil | "Sijil Teknologi Automotif" | Entry-level certificates |
| **0** | Other / Unknown | Courses without credential keywords | Default priority |

**Detection Logic:**
```python
def get_credential_priority(course_name):
    name_lower = course_name.lower().strip()
    if name_lower.startswith("asasi") or "foundation" in name_lower:
        return 4
    elif name_lower.startswith("diploma"):
        return 3
    elif "sijil lanjutan" in name_lower:
        return 2
    elif name_lower.startswith("sijil"):
        return 1
    return 0
```

**Example:**
- Course A: Score 105, **ASASI** (Priority 4)
- Course B: Score 105, **Diploma** (Priority 3)

**Result:** A ranks above B (ASASI > Diploma). If both were ASASI, proceed to Level 3.

---

### Level 3: Institution Priority

Institutions are hierarchically ordered by **type and reputation**. Research universities rank highest, followed by polytechnics, community colleges, and TVET institutions.

**Institution Priority Table:**

| Priority | Institution Type | Subcategory | Examples | Count |
| :---: | :--- | :--- | :--- | ---: |
| **14** | **University (IPTA)** | Penyelidihan (Research) | UM, USM, UPM, UKM, UiTM | 5 |
| **13** | **University (IPTA)** | Komprehensif (Comprehensive) | UPNM, UIAM, UMS, UNIMAS, etc. | ~8 |
| **12** | **University (IPTA)** | Berfokus (Focused) | UTeM, UTHM, UMPSA, UMK, etc. | ~5 |
| **11** | **University (IPTA)** | Teknikal (Technical) | USIM, UniMAP, UMT, UniSZA, etc. | ~5 |
| **10** | **Polytechnic** | Premier | Politeknik Premier (4 institutions) | 4 |
| **9** | **Polytechnic** | Konvensional | Standard polytechnics | ~30 |
| **8** | **Polytechnic** | JMTI | Jabatan-specific institutions | ~10 |
| **7** | **Polytechnic** | METrO | Metropolitan polytechnics | ~5 |
| **6** | **Community College** | Kolej Komuniti | All KK institutions | ~90 |
| **5** | **TVET** | ADTEC | Advanced Technology Training Centers | ~10 |
| **4** | **TVET** | IKTBN | National Youth Skills Institutes | ~8 |
| **3** | **TVET** | ILP | Industrial Training Institutes | ~22 |
| **2** | **TVET** | IKBN/IKSN | Vocational training centers | ~10 |
| **1** | **TVET** | IKBS | Agricultural skills institutes | ~5 |

**Rationale:**
- **Universities (14-11):** Four-tier system reflects Malaysia's official university classification (Research > Comprehensive > Focused > Technical). ASASI programs at research universities provide strongest degree pathway.
- **Polytechnics (10-7):** Premier institutions have enhanced facilities and industry links. Konvensional are well-established. JMTI/METrO are specialized.
- **Community Colleges (6):** Strong local presence, affordable, but less research-intensive than polytechnics.
- **TVET (5-1):** Specialized skills training, less academic emphasis, ranked by institutional maturity and industry recognition.

**Example:**
- Course A: Score 105, ASASI, **UM (Priority 14)**
- Course B: Score 105, ASASI, **USIM (Priority 11)**

**Result:** A ranks above B (Penyelidihan > Teknikal). If both were at UM, proceed to Level 4.

---

### Level 4: Merit Cutoff (Competitiveness)

When fit score, credential, and institution are all equal, **more competitive courses** (higher merit cutoffs) rank above less competitive ones.

**Rationale:**
- Higher merit cutoff = **More selective** = Higher perceived value
- Students gravitate toward "prestigious" programs even within same institution
- Reflects real-world application behavior (students prefer competitive courses)

**Sorting:** Descending (higher merit = better)

**Example:**
- Course A: Score 105, ASASI, UM, **Merit 90**
- Course B: Score 105, ASASI, UM, **Merit 75**

**Result:** A ranks above B (90 > 75). Higher merit indicates stronger program.

**Special Cases:**
- Courses **without merit data** (TVET, PISMP) get merit = 0
- These rank below equivalent courses with merit data
- Alphabetical name becomes tie-breaker for zero-merit courses

---

### Level 5: Course Name (Alphabetical)

Final tie-breaker ensures **deterministic, stable sorting** even when all other factors are identical.

**Sorting:** Ascending (A → Z)

**Example:**
- Course A: Score 105, ASASI, UM, Merit 85, **"ASASI Kejuruteraan"**
- Course B: Score 105, ASASI, UM, Merit 85, **"ASASI Sains"**

**Result:** A ranks above B ("Kejuruteraan" < "Sains" alphabetically).

---

### Complete Example: Tie-Breaking Cascade

**Scenario:** 8 courses all have **Score 105** (tied). How are they ranked?

| Rank | Course | Credential | Institution | Merit | Name | Breaking Point |
| :---: | :--- | :---: | :--- | :---: | :--- | :--- |
| **1** | ASASI Kejuruteraan | 4 | UM (14) | 92 | ASASI Kejuruteraan | - |
| **2** | ASASI Sains | 4 | UM (14) | 88 | ASASI Sains | Level 4 (Merit 92 > 88) |
| **3** | ASASI Teknologi | 4 | USIM (11) | 85 | ASASI Teknologi | Level 3 (UM > USIM) |
| **4** | Diploma Mekanikal | 3 | Politeknik Premier (10) | 78 | Diploma Mekanikal | Level 2 (ASASI > Diploma) |
| **5** | Diploma Elektrik | 3 | Politeknik Premier (10) | 78 | Diploma Elektrik | Level 5 (Mekanikal < Elektrik) |
| **6** | Diploma Awam | 3 | Politeknik Konvensional (9) | 75 | Diploma Awam | Level 3 (Premier > Konvensional) |
| **7** | Sijil Automotif | 1 | ILP (3) | 0 | Sijil Automotif | Level 2 (Diploma > Sijil) |
| **8** | Sijil Binaan | 1 | ILP (3) | 0 | Sijil Binaan | Level 5 (Automotif < Binaan) |

**Cascade Explanation:**
1. **All tied at Score 105** → Check Credential
2. **Ranks 1-3:** ASASI (4) beats Diploma (3) and Sijil (1)
3. **Within ASASI:** UM (14) beats USIM (11)
4. **Within UM ASASI:** Merit 92 > 88
5. **Ranks 4-6:** Diploma (3) beats Sijil (1)
6. **Within Diploma:** Premier (10) > Konvensional (9)
7. **Within Premier Diploma:** Merit 78 tie → Alphabetical (Elektrik < Mekanikal)
8. **Ranks 7-8:** Both Sijil at ILP → Alphabetical (Automotif < Binaan)

---

### Implementation Reference

**Function:** `sort_courses()` in `src/ranking_engine.py` (lines 462-485)

**Sort Tuple:**
```python
def sort_key(item):
    score = int(item.get('fit_score', 0))
    inst_id = str(item.get('institution_id', '')).strip()
    subcat = INST_SUBCATEGORIES.get(inst_id, '')
    inst_priority = INST_PRIORITY_MAP.get(subcat, 0)

    c_name = str(item.get('course_name') or '')
    cred_priority = get_credential_priority(c_name)

    merit = float(item.get('merit_cutoff', 0) or 0)

    # Return tuple: negative values for descending sort, positive for ascending
    return (-score, -cred_priority, -inst_priority, -merit, c_name)
```

**Why Negative Values?**
- Python's `sorted()` sorts in ascending order by default
- Using negative values for score/priority/merit reverses the order → descending sort
- Course name remains positive → ascending alphabetical order

---

### Design Principles

1. **Determinism:** Same inputs always produce same ranking order
2. **Transparency:** Each tie-breaking level has clear rationale
3. **Fairness:** Merit-based (not arbitrary) at every level
4. **Stability:** Alphabetical ensures no random shuffling
5. **User Expectations:** Aligns with student preferences (degree pathway > diploma, research uni > technical uni)
