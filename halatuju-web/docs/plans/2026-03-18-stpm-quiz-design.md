# STPM Student Quiz — Design Document

**Date:** 2026-03-18
**Status:** Draft v2 — subject-seeded branching design

---

## 1. Why a Separate Quiz

The current quiz was designed for SPM students choosing between diplomas, certificates, and pre-university pathways. STPM students are a fundamentally different population:

| Dimension | SPM Student | STPM Student |
|-----------|-------------|--------------|
| Age | 17 | 18–19 |
| Decision stage | "What kind of education next?" | "Which degree programme?" |
| Options | Diploma, Certificate, Matric, STPM, TVET | University degree only |
| Maturity | Exploring broadly | Narrowing to a specific field |
| Key concern | "Can I afford to study?" | "Which programme fits me best?" |
| Number of courses | 5,300+ (mixed credential levels) | 1,100+ (degrees only) |

Bolting STPM logic onto the SPM quiz creates awkward compromises (Q6 says "After SPM", allowance signals are irrelevant, field interests are TVET-flavoured). A purpose-built quiz serves STPM students better and produces richer signals for degree-level ranking.

---

## 2. Key Design Insight: Subjects as Signal

When an STPM student reaches the quiz, we already know:

- **Their stream** (Science or Arts) — chosen 2 years ago
- **Their specific subjects** (e.g., Physics + Chemistry + Math T, or Economics + Accounting + Business)
- **Their grades** in each subject
- **Their MUET band**
- **Their SPM prerequisite grades**

This is a powerful implicit signal. Holland's RIASEC theory explicitly links academic subject preferences to personality types. A student who chose Physics and Chemistry has already self-selected into Realistic/Investigative territory. Asking them "Do you prefer building things or analysing data?" is redundant — they answered that question two years ago by choosing their subjects.

### STPM Subject → RIASEC Seed Mapping

| STPM Subject | Primary RIASEC | Secondary |
|-------------|---------------|-----------|
| Mathematics T | I (Investigative) | C (Conventional) |
| Mathematics M | C (Conventional) | I (Investigative) |
| Physics | R (Realistic) | I (Investigative) |
| Chemistry | I (Investigative) | R (Realistic) |
| Biology | I (Investigative) | S (Social) |
| ICT | I (Investigative) | C (Conventional) |
| Economics | E (Enterprising) | C (Conventional) |
| Accounting | C (Conventional) | E (Enterprising) |
| Business Studies | E (Enterprising) | S (Social) |
| Literature in English | A (Artistic) | S (Social) |
| Geography | I (Investigative) | R (Realistic) |
| History | S (Social) | A (Artistic) |
| Visual Arts | A (Artistic) | R (Realistic) |
| STPM Syariah | S (Social) | C (Conventional) |
| Pengajian Am (PA) | *(excluded — all students take this)* | |

**Seed calculation:** Sum RIASEC scores across the student's 3 subjects (primary = 2 points, secondary = 1 point). The highest-scoring RIASEC type becomes the seed. Ties are preserved as a multi-type seed.

**Example:** A student taking Physics (R:2, I:1) + Chemistry (I:2, R:1) + Math T (I:2, C:1) → R:3, I:5, C:1 → **Seed: I (Investigative), secondary R (Realistic)**

This seed determines which branch of the quiz the student enters.

### Stream Crossover Asymmetry

An important asymmetry governs which branches are available to which students:

**Science → Arts: Wide open.** Most arts-side degree programmes (Business, Law, Accounting, Education, Communications) require only a minimum CGPA and MUET — no specific arts subjects. A science student qualifies for these *plus* all science-side programmes. This is a real, common pathway — not a hypothetical curiosity.

**Arts → Science: Essentially closed.** Engineering requires Physics and Math T. Medicine requires Biology and Chemistry. Pure Science programmes require their specific subjects. An arts student simply cannot cross into these without having taken the prerequisite STPM subjects.

**Design implications:**

1. **Science branch Q2 should offer arts-side options directly** — not just in the cross-domain question (Q5). "Business & Management" and "Education" are genuine first-choice options for science students, not afterthoughts.

2. **Arts branch Q5 should only show *achievable* cross-domain options** — e.g., "Health administration" or "IT management" (which may not require science subjects), but NOT "Medicine" or "Engineering" (which are impossible without the prerequisites).

3. **Extra-subject detection:** If a science student took a 4th subject from the arts stream (e.g., Economics as an elective), this is a strong crossover signal. The quiz should detect this and treat it as a hybrid seed — presenting both science and arts options with equal prominence in Q2, rather than defaulting to science-only.

| Student Profile | Branch | Q2 Options |
|----------------|--------|------------|
| Physics + Chemistry + Math T | Science | Engineering, Medicine, Pure Science, Technology, **Business & Management**, **Education** |
| Physics + Chemistry + Math T + *Economics* | Science-Hybrid | Engineering, Medicine, Technology, **Business**, **Accounting & Finance**, **Law** |
| Economics + Accounting + Business | Arts | Business, Law, Education, Creative, Accounting & Finance |
| Economics + Accounting + *Biology* | Arts (limited cross) | Business, Law, Education, Finance, *Allied Health* (if Biology prerequisite met) |

### What Subjects Don't Tell Us

The quiz focuses on what subjects *cannot* reveal:

1. **Within-domain direction** — A Physics student: mechanical engineering, electrical, aerospace, or IT?
2. **Cross-domain interests** — A science student secretly drawn to design, business, or education
3. **Confidence vs interest gap** — Interested in medicine but struggling in biology
4. **Motivation source** — Passion vs family expectation vs career pragmatism
5. **Career horizon** — Professional practice vs research vs entrepreneurship
6. **Decision readiness** — Decided, narrowing, or still exploring

---

## 3. Theoretical Foundation

The quiz draws on four established career psychology frameworks. Each question is grounded in at least one.

### 3.1 Holland's RIASEC Model

The most empirically validated career interest framework. Six personality–environment types form a hexagon:

```
        Realistic (R)
       /             \
Conventional (C)    Investigative (I)
      |                |
Enterprising (E)    Artistic (A)
       \             /
        Social (S)
```

Adjacent types are more similar; opposite types are most different. Research shows RIASEC predicts course satisfaction and persistence in higher education.

**Application in this quiz:** RIASEC is used as the *seed* (derived from STPM subjects), not discovered through generic forced-choice questions. The quiz then *refines* within the seed type, making every question feel relevant.

**Instrument reference:** Modelled on the 18REST (de Fruyt & Wille, 2020) — validated for educational assessment, CFI = .932. Adapted: instead of 3 items per type (18 total), we use the subject seed + targeted refinement (fewer items, higher relevance).

### 3.2 Social Cognitive Career Theory (SCCT)

Lent, Brown & Hackett (1994). Career interests develop from **self-efficacy beliefs** ("Can I succeed at this?") and **outcome expectations** ("Will it lead to good results?"). These are shaped by prior learning experiences.

Critical for Malaysian context: In collectivist cultures, **family approval** moderates the self-efficacy → choice relationship more strongly than in Western samples. Students may choose careers congruent with family expectations even when personal interests differ — and this can still lead to positive outcomes when the family relationship is strong.

**Application:** Self-efficacy items identify domains where the student feels confident (not just interested). Family influence item acknowledges collectivist reality without pathologising it. STPM grades themselves serve as an *objective* efficacy signal — if a student got A in Chemistry, we don't need to ask "are you confident in science?" But we do need to ask about *adjacent* efficacy (e.g., "are you comfortable with the patient-care side of medicine, not just the science?").

### 3.3 Self-Determination Theory (SDT)

Deci & Ryan (2000). Three psychological needs drive intrinsic motivation: **autonomy** (sense of choice), **competence** (feeling capable), **relatedness** (feeling connected). When course choice satisfies these needs, students report higher satisfaction and lower dropout.

**Application:** Motivation-source questions distinguish autonomous from controlled motivation. This doesn't penalise family-influenced choices — it informs how results are framed.

### 3.4 Super's Career Development Theory

Super (1957, 1990). STPM students (18–19) are transitioning from **Crystallisation** (forming tentative preferences) to **Specification** (converting preferences into specific goals).

**Application:** Crystallisation item identifies how decided the student already is. This changes how results are *presented*, not what is recommended.

---

## 4. Quiz Structure — Branching Design

**Each student answers 10 questions. Total question pool: ~35 questions.**

The quiz has a **trunk** (shared questions) and **branches** (stream-specific and interest-specific questions). The branch taken depends on the student's STPM subjects (known before the quiz starts) and their answers to earlier questions.

```
                    ┌─────────────────────────┐
                    │  STPM Subjects Known     │
                    │  → Calculate RIASEC seed │
                    └────────┬────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Q1: Decision    │  ← Shared (Super)
                    │      readiness   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───┐  ┌──────▼─────┐  ┌─────▼──────┐
     │ Science    │  │ Arts       │  │ Mixed/     │
     │ Branch     │  │ Branch     │  │ Unusual    │
     │ Q2s–Q4s   │  │ Q2a–Q4a   │  │ Q2m–Q4m   │
     └────────┬───┘  └──────┬─────┘  └─────┬──────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  Q5: Cross-     │  ← Shared (Holland)
                    │      domain     │
                    │      interest   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Q6: Confidence │  ← Adaptive (SCCT)
                    │  (based on      │
                    │   branch field) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Q7: Challenge  │  ← Shared (SCCT)
                    │      appetite   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Q8: Motivation │  ← Shared (SDT)
                    │      source     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Q9: Career     │  ← Shared (SCCT)
                    │      horizon    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Q10: Family    │  ← Shared (SCCT)
                    │       influence │
                    └────────┬────────┘
                             │
                         [Results]
```

**Student experience:** 10 questions, ~4 minutes. Feels personalised because the field-refinement questions (Q2–Q4) are specific to their actual STPM subjects.

---

## 5. Question Design — Trunk (Shared)

### Q1 — Decision readiness (all students)

**Theory:** Super's Career Development Theory
**Purpose:** Determines result framing AND influences Q2–Q4 branch depth.

> **"Where are you in choosing what to study at university?"**

| Option | Signal | UI Effect |
|--------|--------|-----------|
| I know exactly what I want | `crystallisation_high` | Confirmatory framing; field refinement (Q2–Q4) narrows faster |
| I have a general direction | `crystallisation_moderate` | Exploratory framing with direction |
| I'm still figuring it out | `crystallisation_low` | Discovery framing; Q2–Q4 show broader options |

**Rationale:** Asked first because it sets the tone. A "decided" student's branch questions can be more specific ("Within engineering, which type?"). An "exploring" student's branch questions stay broader ("Which of these areas sounds most appealing?").

---

### Q5 — Cross-domain interest (all students)

**Theory:** Holland's hexagon (adjacent-type exploration)
**Purpose:** Discovers interests *outside* the student's stream. This is where the quiz adds value beyond what subjects tell us.

> **"Is there an area outside your main subjects that also appeals to you?"**

Options are dynamically generated to show RIASEC types the student's subjects did NOT strongly seed. **Critically, only *achievable* cross-domain options are shown** — options the student actually qualifies for based on their subjects.

| If seed is... | Options shown | Why |
|---------------|---------------|-----|
| **I+R** (Science) | Business & entrepreneurship (E), Teaching & counselling (S), Design & creative arts (A), Law & policy (E), Data & systems (C), No — I want to stay in my lane | Science students qualify for most arts-side degrees — all options are achievable |
| **E+C** (Arts-Business) | Health administration (S+I), IT management (C+I), Environmental studies (if Geography taken), Education (S), No — I want to stay in my lane | Arts students **cannot** cross into Engineering, Medicine, or Pure Science — those options are excluded. Only science-adjacent options that don't require science prerequisites are shown |
| **E+C** (Arts-Business + *Biology as 4th subject*) | All of the above + Allied Health, Biomedical Science | The extra science subject opens specific doors — show them |

Signal: Maps to the corresponding RIASEC type(s) with weight 1 (secondary interest, not primary).

**Rationale:** This is the most important question in the quiz. It catches the science student who wants to do medical illustration (I+A), the accounting student drawn to tech (C+I), or the biology student who actually wants to teach (I+S). Holland's research shows that two-letter codes (primary + secondary) predict career satisfaction better than single-letter codes. The "No, stay in my lane" option is valid and produces no cross-domain signal.

**The crossover asymmetry is enforced here:** Science students see a wide menu of cross-domain options (because they genuinely qualify). Arts students see a filtered menu limited to what's actually achievable without science prerequisites. This prevents false hope while still showing real opportunities.

---

### Q7 — Challenge appetite (all students)

**Theory:** SCCT (coping efficacy)

> **"When a subject is really hard, what do you do?"**

| Option | Signal | Weight |
|--------|--------|--------|
| Dig in harder — I like the challenge | `resilience_high: 2` |
| Get help and push through | `resilience_supported: 1` |
| Switch focus to what I'm better at | `resilience_redirect: 1` |
| Depends — if I care about it, I'll fight for it | `resilience_interest: 1` |

**Rationale:** Programmes like Medicine, Engineering, and Law have high attrition. A student with `resilience_redirect` who picks Medicine may benefit from seeing Biomedical Science or Health Sciences as alternatives. Not used to *exclude* — used to offer *complementary* suggestions.

---

### Q8 — Motivation source (all students)

**Theory:** SDT (autonomous vs controlled motivation)

> **"What matters most when choosing what to study?"**

| Option | Signal | Weight |
|--------|--------|--------|
| I want to love what I study | `motivation_autonomous: 2` |
| I want a stable, well-paying career | `motivation_career: 2` |
| I want to make my family proud | `motivation_family: 2` |
| I want a respected qualification | `motivation_prestige: 2` |

---

### Q9 — Career horizon (all students)

**Theory:** SCCT (outcome expectations)

> **"What's your goal after graduating?"**

| Option | Signal | Weight |
|--------|--------|--------|
| Practise a specific profession (doctor, engineer, lawyer, etc.) | `goal_professional: 2` |
| Get a good job in any well-paying field | `goal_employment: 2` |
| Continue to postgraduate study (Masters, PhD) | `goal_postgrad: 2` |
| Start my own business or venture | `goal_entrepreneurial: 2` |

---

### Q10 — Family influence (all students)

**Theory:** SCCT (collectivist cultural adaptation)

> **"How much does your family's opinion influence your course choice?"**

| Option | Signal | Weight |
|--------|--------|--------|
| A lot — their guidance is very important to me | `family_influence_high: 2` |
| Somewhat — I consider their views but decide myself | `family_influence_moderate: 1` |
| Not much — this is fully my decision | `family_influence_low: 0` |

**Rationale:** Not used for ranking. Used for result framing only. Malaysian research shows family influence is a significant and *legitimate* factor in course choice — the quiz respects this rather than treating it as a red flag.

---

## 6. Question Design — Science Branch (Q2s–Q4s)

Shown to students whose STPM subjects are science-stream (Physics, Chemistry, Biology, Math T, ICT, etc.).

### Q2s — Primary field direction

> **"You've studied science — which direction excites you most?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Engineering — designing and building systems | `field_engineering: 3` | `mekanikal`, `elektrik`, `sivil`, `mekatronik` |
| Medicine & Health — caring for people's wellbeing | `field_health: 3` | `perubatan`, `farmasi`, `sains-hayat` |
| Pure & Applied Science — understanding how the world works | `field_pure_science: 3` | `sains-tulen`, `bioteknologi`, `kimia-proses` |
| Technology & Computing — building digital solutions | `field_tech: 3` | `it-perisian`, `it-rangkaian`, `multimedia` |
| Business & Management — I'm more interested in the business side | `field_business: 3` | `perniagaan`, `pengurusan`, `pemasaran` |
| Education — I want to teach or work with people | `field_education: 3` | `pendidikan`, `kaunseling` |

**Rationale:** Science students qualify for arts-side degrees too (Business, Law, Education, etc.) — these are genuine first-choice options, not afterthoughts. Including them here respects the crossover asymmetry: science students have the widest range of options and the quiz should reflect that. If the student picks Business or Education, Q3s branches into the arts sub-field refinement questions (Q3a equivalents) instead of science sub-fields.

**Extra-subject variant:** If the student took a 4th subject from the arts stream (e.g., Economics), the arts-side options are shown with higher prominence — moved up in the list and labelled "Your Economics background opens these options too."

### Q3s — Sub-field refinement (branches from Q2s)

**If Q2s = Engineering:**

> **"What kind of engineering appeals to you?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Mechanical — machines, vehicles, manufacturing | `field_key_mekanikal: 2` | `mekanikal`, `automotif` |
| Electrical & Electronics — circuits, power, telecoms | `field_key_elektrik: 2` | `elektrik`, `mekatronik` |
| Civil & Architecture — buildings, infrastructure, design | `field_key_sivil: 2` | `sivil`, `senibina` |
| Chemical & Process — reactions, materials, energy | `field_key_kimia: 2` | `kimia-proses` |
| Aerospace & Marine — flight, ships, defence | `field_key_aero: 2` | `aero`, `marin` |

**If Q2s = Medicine & Health:**

> **"Which part of healthcare draws you?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Becoming a doctor or dentist | `field_key_perubatan: 2` | `perubatan` |
| Pharmacy or biomedical science | `field_key_farmasi: 2` | `farmasi`, `bioteknologi` |
| Allied health — physiotherapy, dietetics, lab science | `field_key_allied: 2` | `sains-hayat` |
| Health administration or public health | `field_key_health_admin: 2` | `pengurusan`, `sains-hayat` |

**If Q2s = Pure & Applied Science:**

> **"Which science excites you most?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Physics or Mathematics — theory and modelling | `field_key_sains_fizik: 2` | `sains-tulen` |
| Chemistry or Materials — substances and reactions | `field_key_sains_kimia: 2` | `sains-tulen`, `kimia-proses` |
| Biology or Biotechnology — life and living systems | `field_key_sains_bio: 2` | `bioteknologi`, `sains-hayat` |
| Environmental Science or Agriculture | `field_key_alam: 2` | `alam-sekitar`, `pertanian` |

**If Q2s = Technology & Computing:**

> **"What kind of tech work interests you?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Software development — building apps and systems | `field_key_it_sw: 2` | `it-perisian` |
| Networking & cybersecurity — infrastructure and protection | `field_key_it_net: 2` | `it-rangkaian` |
| Data science & AI — making sense of information | `field_key_it_data: 2` | `it-perisian`, `sains-tulen` |
| Creative tech — multimedia, games, digital design | `field_key_multimedia: 2` | `multimedia`, `senireka` |

### Q4s — Confidence check (adaptive)

**Theory:** SCCT (domain-specific self-efficacy)

Based on the student's Q2s choice and their *actual STPM grades*, this question probes the gap between interest and confidence.

**If the student chose Medicine & Health but got B- or lower in Biology:**

> **"You're drawn to healthcare, but your Biology grade is [grade]. How do you feel about that?"**

| Option | Signal |
|--------|--------|
| I'll work harder — I know I can improve | `efficacy_confident: 2` |
| I'd prefer a health field that's less Biology-heavy | `efficacy_redirect: 1` |
| Maybe I should explore other options too | `efficacy_uncertain: 0` |

**If the student's grades strongly match their interest (e.g., chose Engineering, got A in Physics):**

> **"Your Physics results are strong. Are you confident you'd enjoy 4 years of engineering study?"**

| Option | Signal |
|--------|--------|
| Absolutely — this is what I want | `efficacy_confirmed: 2` |
| Mostly, but I'd like to keep my options open | `efficacy_open: 1` |
| Actually, I'm not sure engineering is right for me | `efficacy_mismatch: 0` |

**Rationale:** This is where the quiz becomes genuinely personal. It uses the student's *own grades* to ask a targeted question about the gap (or alignment) between interest and ability. A generic quiz can't do this. The signal adjusts how strongly the field match influences ranking — `efficacy_confirmed` amplifies the field bonus; `efficacy_mismatch` suppresses it and broadens recommendations.

---

## 7. Question Design — Arts Branch (Q2a–Q4a)

Shown to students whose STPM subjects are arts-stream (Economics, Accounting, Business, History, Literature, Geography, etc.).

### Q2a — Primary field direction

> **"You've studied the arts — which direction excites you most?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Business & Management — running organisations | `field_business: 3` | `perniagaan`, `pengurusan` |
| Law & Public Policy — justice and governance | `field_law: 3` | `undang-undang`, `pentadbiran` |
| Education & Social Work — shaping lives | `field_education: 3` | `pendidikan`, `kaunseling` |
| Communications & Creative — media, writing, design | `field_creative: 3` | `multimedia`, `senireka` |
| Accounting & Finance — numbers and analysis | `field_finance: 3` | `perakaunan`, `kewangan`, `sains-aktuari` |

### Q3a — Sub-field refinement (branches from Q2a)

**If Q2a = Business & Management:**

> **"What kind of business work interests you?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Marketing & branding — understanding people and markets | `field_key_pemasaran: 2` | `pemasaran` |
| Human resources — managing and developing talent | `field_key_hr: 2` | `pengurusan` |
| International business — trade, logistics, global markets | `field_key_intl: 2` | `perniagaan` |
| Entrepreneurship — building something of my own | `field_key_entrepren: 2` | `perniagaan`, `pengurusan` |

**If Q2a = Law & Public Policy:**

> **"What draws you to this field?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Practising law — advocacy and litigation | `field_key_law: 2` | `undang-undang` |
| Public administration — government and policy | `field_key_admin: 2` | `pentadbiran` |
| International relations — diplomacy and global affairs | `field_key_ir: 2` | `pentadbiran`, `undang-undang` |

**If Q2a = Education & Social Work:**

> **"How do you want to make a difference?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Teaching — classroom, school, inspiring students | `field_key_pendidikan: 2` | `pendidikan` |
| Counselling & psychology — one-to-one support | `field_key_kaunseling: 2` | `kaunseling` |
| Community development — programmes and social impact | `field_key_sosial: 2` | `kaunseling`, `pendidikan` |

**If Q2a = Communications & Creative:**

> **"What kind of creative work excites you?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Journalism & media — telling stories that matter | `field_key_media: 2` | `multimedia` |
| Graphic design & visual arts — making things look right | `field_key_senireka: 2` | `senireka` |
| Film, animation, or digital content | `field_key_digital: 2` | `multimedia`, `senireka` |
| Advertising & PR — persuading and positioning | `field_key_pr: 2` | `pemasaran`, `multimedia` |

**If Q2a = Accounting & Finance:**

> **"What interests you about this field?"**

| Option | Signal | Field Keys |
|--------|--------|------------|
| Auditing & accounting — accuracy and compliance | `field_key_perakaunan: 2` | `perakaunan` |
| Investment & banking — markets and money | `field_key_kewangan: 2` | `kewangan` |
| Actuarial science — risk and statistics | `field_key_aktuari: 2` | `sains-aktuari` |
| Financial planning — helping people manage money | `field_key_fin_plan: 2` | `kewangan`, `perakaunan` |

### Q4a — Confidence check (adaptive, same logic as Q4s)

Uses the student's actual grades to probe interest–confidence alignment. Same structure as Q4s but with arts-relevant content.

---

## 8. Question Design — Mixed/Unusual Branch (Q2m–Q4m)

For students whose subjects don't cleanly fit Science or Arts (e.g., Biology + Economics + Geography), or whose RIASEC seed is highly balanced.

### Q2m — Broad exploration

> **"Your subjects cross different areas. Which direction appeals to you most?"**

Shows a curated mix of 5–6 options spanning both Science and Arts degree clusters, selected based on which RIASEC types are present in the seed. Uses the same signal/field_key structure as Q2s and Q2a.

### Q3m–Q4m — Follow the same refinement and confidence patterns.

---

## 9. Signal Taxonomy (STPM)

```python
STPM_SIGNAL_TAXONOMY = {
    # Derived from subjects (pre-quiz), refined by Q2–Q4
    'riasec_seed': [
        'riasec_R', 'riasec_I', 'riasec_A',
        'riasec_S', 'riasec_E', 'riasec_C',
    ],

    # From Q2–Q4 branch answers (maps to FieldTaxonomy keys)
    'field_interest': [
        # Dynamically populated based on branch answers
    ],

    # From Q5 (cross-domain interest)
    'cross_domain': [
        'cross_R', 'cross_I', 'cross_A',
        'cross_S', 'cross_E', 'cross_C',
    ],

    # From Q4 (adaptive confidence) + grade analysis
    'efficacy': [
        'efficacy_confirmed', 'efficacy_confident',
        'efficacy_open', 'efficacy_redirect',
        'efficacy_uncertain', 'efficacy_mismatch',
    ],

    # From Q7
    'resilience': [
        'resilience_high', 'resilience_supported',
        'resilience_redirect', 'resilience_interest',
    ],

    # From Q8
    'motivation': [
        'motivation_autonomous', 'motivation_career',
        'motivation_family', 'motivation_prestige',
    ],

    # From Q9
    'career_goal': [
        'goal_professional', 'goal_employment',
        'goal_postgrad', 'goal_entrepreneurial',
    ],

    # From Q1 and Q10 — framing only, not ranking
    'context': [
        'family_influence_high', 'family_influence_moderate',
        'family_influence_low',
        'crystallisation_high', 'crystallisation_moderate',
        'crystallisation_low',
    ],
}
```

---

## 10. RIASEC → FieldTaxonomy Mapping

| RIASEC | FieldTaxonomy Keys |
|--------|-------------------|
| **R** (Realistic) | `mekanikal`, `automotif`, `mekatronik`, `elektrik`, `sivil`, `senibina`, `pertanian`, `alam-sekitar`, `aero`, `marin`, `minyak-gas` |
| **I** (Investigative) | `perubatan`, `farmasi`, `sains-hayat`, `sains-tulen`, `bioteknologi`, `it-perisian`, `it-rangkaian` |
| **A** (Artistic) | `senireka`, `multimedia`, `senibina`, `fesyen` |
| **S** (Social) | `pendidikan`, `kaunseling`, `sains-sukan`, `pengajian-islam` |
| **E** (Enterprising) | `perniagaan`, `pengurusan`, `pemasaran`, `undang-undang` |
| **C** (Conventional) | `perakaunan`, `kewangan`, `pentadbiran`, `sains-aktuari` |

---

## 11. Ranking Engine Integration

### Current STPM scoring (stpm_ranking.py)

```
BASE_SCORE (50) + CGPA_MARGIN (max +20) + FIELD_MATCH (+10) - INTERVIEW (-3)
```

Field match is binary: +10 if course.field_key matches any field_interest signal. Maximum score = 77.

### Proposed STPM scoring (with new quiz)

```
BASE_SCORE (50)
  + CGPA_MARGIN          (max +20, unchanged)
  + FIELD_MATCH           (max +12, from Q2–Q4 field_key match)
  + RIASEC_ALIGNMENT      (max +8, from subject seed + Q5 cross-domain)
  + EFFICACY_MODIFIER     (+4 to -2, from Q4 + grade analysis)
  + GOAL_ALIGNMENT        (max +4, from Q9)
  - INTERVIEW_PENALTY     (-3, unchanged)
  - RESILIENCE_DISCOUNT   (0 to -3, from Q7 vs programme difficulty)
```

Maximum possible: 50 + 20 + 12 + 8 + 4 + 4 - 0 = **98**

### Scoring detail

**FIELD_MATCH (+12 max)**
- Primary field_key match from Q3 sub-field: +8
- Secondary field_key match from Q2 broad direction: +4
- Cross-domain match from Q5: +2 (additive, but capped at +12 total)
- No match: +0

**RIASEC_ALIGNMENT (+8 max)**
- Course's RIASEC type matches student's primary seed: +6
- Matches secondary seed: +3
- Matches cross-domain interest (Q5): +2
- No match: +0
- *Requires `riasec_type` on StpmCourse (one-time data enrichment)*

**EFFICACY_MODIFIER (+4 to -2)**
- `efficacy_confirmed`: +4 (strong alignment — amplify field match)
- `efficacy_confident`: +2 (willing to push through)
- `efficacy_open`: +0 (neutral — keep options broad)
- `efficacy_redirect`: -1 (suggest related alternatives)
- `efficacy_mismatch`: -2 (suppress primary field, boost cross-domain)

**GOAL_ALIGNMENT (+4 max)**
- `goal_professional` + regulated profession course (Medicine, Law, Engineering): +4
- `goal_postgrad` + research-intensive programme: +4
- `goal_employment` + high-employability programme: +3
- `goal_entrepreneurial` + business/management programme: +3

**RESILIENCE_DISCOUNT (0 to -3)**
- `resilience_redirect` + high-difficulty programme: -3
- `resilience_redirect` + moderate-difficulty: -1
- `resilience_supported` + high-difficulty: -1
- All others: 0

### Signals used for result framing only (not scoring)

| Signal | Effect on UI |
|--------|-------------|
| `motivation_family` | "Discuss these options with your family — their experience can help you choose well." |
| `motivation_autonomous` | "You seem to know what excites you. Trust that instinct." |
| `crystallisation_low` | Frame as: "Here are fields worth exploring" (discovery mode) |
| `crystallisation_high` | Frame as: "Your profile aligns with..." (confirmatory mode) |
| `crystallisation_moderate` | Frame as: "Based on your interests, consider these programmes" (guided mode) |
| `family_influence_high` + interest ≠ expected field | "Your interests point toward [X]. Explore it with your family — you might discover a path you both feel good about." |
| `efficacy_mismatch` | "Your interests and current strengths point in different directions. Here are programmes that bridge both." |

---

## 12. Data Enrichment Required

| Field | Model | Type | Purpose | How to populate |
|-------|-------|------|---------|-----------------|
| `riasec_type` | StpmCourse | CharField(1), choices R/I/A/S/E/C | RIASEC matching | AI classification of 1,113 courses (one-time) |
| `difficulty_level` | StpmCourse | CharField, choices low/moderate/high | Resilience matching | Manual classification based on known dropout rates |
| `riasec_primary` | FieldTaxonomy | CharField(1) | Map fields to RIASEC | Manual mapping (~37 entries) |
| `efficacy_domain` | StpmCourse | CharField, choices quantitative/scientific/verbal/practical | Efficacy matching | Derived from field_key mapping (automated) |

---

## 13. UX Design Principles

1. **Visual cards, not Likert scales.** Same card-based UI as SPM quiz, with illustrations. Tap to select, auto-advance.

2. **One question per screen.** Mobile-first. Progress bar shows "3 of 10".

3. **Personalised feel.** Q2 says "You've studied science — which direction excites you most?" (not generic "What field interests you?"). Q4 references the student's actual grade. This makes the quiz feel like a conversation, not a survey.

4. **Branching is invisible.** The student doesn't see "Science Branch". They just see questions that feel relevant to *them*. The branching logic is entirely backend.

5. **Trilingual.** All question text and option labels in EN, BM, and TA.

6. **No wrong answers.** Every option is valid. "Neither" and "stay in my lane" produce useful absence-of-signal data.

7. **Results framing varies.** Three modes based on Q1: Confirmatory (decided), Guided (narrowing), Discovery (exploring).

---

## 14. Question Count Summary

| Path | Q1 | Q2 | Q3 | Q4 | Q5 | Q6* | Q7 | Q8 | Q9 | Q10 | Total |
|------|----|----|----|----|----|----|----|----|----|----|-------|
| Science → Engineering | Shared | Science | Eng sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Science → Medicine | Shared | Science | Health sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Science → Pure Science | Shared | Science | Science sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Science → Technology | Shared | Science | Tech sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Arts → Business | Shared | Arts | Biz sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Arts → Law | Shared | Arts | Law sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Arts → Education | Shared | Arts | Edu sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Arts → Creative | Shared | Arts | Creative sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Arts → Finance | Shared | Arts | Finance sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |
| Mixed | Shared | Mixed | Sub-field | Confidence | Cross-domain | Adaptive | Shared | Shared | Shared | Shared | **10** |

*Q6 is the adaptive confidence question that uses actual grades — this is where the student's STPM results directly shape the quiz experience.

**Total unique questions across all branches:** ~35
**Questions any single student sees:** 10

---

## 15. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Subject → RIASEC mapping is too coarse | Medium | The mapping is a *seed*, not a final answer. Q2–Q5 refine it. Even a wrong seed gets corrected by the branch questions |
| Grade-based Q4 feels judgmental | Medium | Frame positively: "Your [subject] results are [grade]. How do you feel about that?" — not "Your grade is low" |
| Mixed-stream students don't fit neatly | Low | Dedicated mixed branch with broader options |
| Branching logic is complex to build | Medium | Test each branch path independently. Use a decision matrix in the backend, not nested if-statements |
| 35 total questions is a lot to translate (×3 languages) | Low | Structure is repetitive (same patterns per branch). Most options are short phrases |
| AI RIASEC classification of 1,113 courses is inaccurate | Medium | Validate against published university RIASEC mappings. Manual review of edge cases |

---

## 16. Testing Strategy

- **Unit tests:** RIASEC seed calculation from all known STPM subject combinations
- **Branch routing tests:** Verify correct branch selection for Science, Arts, and Mixed students
- **Signal accumulation tests:** End-to-end from quiz answers → signals → ranking adjustment
- **Golden master tests:** Run new ranking on existing STPM student profiles; compare distribution
- **Grade-adaptive Q4 tests:** Verify correct question variant based on grade/interest combinations
- **Edge cases:** All subjects from same type; highly balanced seed; no quiz taken (CGPA-only ranking must still work)
- **User testing:** 5–10 real STPM students per branch. Do the top 5 recommendations feel right?

---

## 17. Implementation Phases

### Phase 1: Foundation (Sprint 1)
- Implement RIASEC seed calculation from STPM subjects
- Design and implement `stpm_quiz_data.py` (all branch questions × 3 languages)
- Implement branching quiz engine with `process_stpm_quiz()`
- Add STPM quiz API endpoints (questions endpoint returns branch-specific questions based on subjects)
- Write unit tests for seed calculation and branch routing

### Phase 2: Data Enrichment (Sprint 2)
- Add `riasec_type`, `difficulty_level`, `efficacy_domain` to StpmCourse model
- AI-classify all 1,113 STPM courses
- Add `riasec_primary` to FieldTaxonomy entries
- Validate classifications
- Write golden master tests

### Phase 3: Ranking Integration (Sprint 3)
- Implement new STPM ranking formula
- Add RIASEC alignment, efficacy modifier, goal alignment, resilience discount
- Implement result framing logic (3 modes)
- Write ranking integration tests

### Phase 4: Frontend (Sprint 4)
- Build STPM quiz page with branching UI
- Implement grade-adaptive Q4 (frontend receives grade context from localStorage)
- Dynamic Q5 cross-domain options
- Update STPM dashboard with quiz-informed framing
- Trilingual content review

### Phase 5: Polish & Validate (Sprint 5)
- User testing with real STPM students (Science + Arts branches)
- Adjust signal weights based on feedback
- Mobile testing across branches
- Documentation and retrospective

---

## References

- Holland, J. L. (1997). *Making Vocational Choices* (3rd ed.). Psychological Assessment Resources.
- de Fruyt, F., & Wille, B. (2020). 18REST: A short RIASEC-interest measure. *Journal of Career Assessment*.
- Lent, R. W., Brown, S. D., & Hackett, G. (1994). Toward a unifying social cognitive theory of career and academic interest, choice, and performance. *Journal of Vocational Behavior*, 45, 79–122.
- Deci, E. L., & Ryan, R. M. (2000). The "what" and "why" of goal pursuits. *Psychological Inquiry*, 11, 227–268.
- Super, D. E. (1990). A life-span, life-space approach to career development. In Brown & Brooks (Eds.), *Career Choice and Development* (2nd ed.). Jossey-Bass.
- Bandura, A. (1997). *Self-efficacy: The exercise of control*. W. H. Freeman.
- O*NET Mini-IP Linking Report. National Center for O*NET Development.
