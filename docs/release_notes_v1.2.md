# Release Notes: Ranking Engine v1.2

**Date:** 2026-01-20
**Module:** `src/ranking_engine.py`

## Overview
This release integrates the enhanced Course Taxonomy (v1.1) into the scoring logic. It introduces finer-grained scoring rules for helping professions, career stability, and burnout protection without altering the base ranking behavior for legacy data.

## New Rules Added

### 1. Helping & Meaning (`value_tradeoff_signals`)
*   **+4 Points:** `meaning_priority` + `service_orientation: care`
    *   *Rationale:* Stronger match for care-giving roles than generic service.
*   **+3 Points:** `meaning_priority` + `interaction_type: relational`
    *   *Rationale:* Rewarding deep human connection.
*   **+1 Point:** `meaning_priority` + `service_orientation: service`
    *   *Rationale:* Slight boost for general service roles.

### 2. Burnout Protection (`energy_sensitivity_signals`)
*   **-2 Points:** `low_people_tolerance` + `interaction_type: transactional`
    *   *Rationale:* Transactional interactions (high volume/low depth) are uniquely draining.
*   **-2 Points:** `low_people_tolerance` + `service_orientation: service`
    *   *Rationale:* General service roles require constant social energy.

### 3. Stability vs Risk (`value_tradeoff_signals`)
*   **+3 Points:** `stability_priority` + `career_structure: stable`
    *   *(Reflects stronger likelihood of predictable early-career pathways)*
*   **+2 Points:** `income_risk_tolerant` + `career_structure: volatile`
*   **+2 Points:** `income_risk_tolerant` + `career_structure: portfolio`

### 4. Credential Confidence (`value_tradeoff_signals`)
*   **+2 Points:** `stability_priority` + `credential_status: regulated`
    *   *Note:* Operates as a confidence signal, not a guarantee of employment.

### 5. Creative Matching (`work_preference_signals`)
*   **+4 Points:** `creative` + `creative_output: expressive`
*   **+3 Points:** `creative` + `creative_output: design`

## Behavioral Changes
*   **Introverts:** Will see slightly lower scores for high-churn retail/service roles compared to previous versions.
*   **Meaning-Seekers:** Will see a clearer separation between "Care" (Nursing) and "Service" (Hospitality).
*   **Creatives:** Expressive arts courses will score higher for creative students than purely abstract courses.

## Edge Cases & Limits
*   **Neutral Fallback:** Courses with `neutral`/`mixed` tags receive 0 adjustment, preserving v1.0 scores.
*   **Category Caps:** All new points are subject to the ±6 point category cap. High-scoring matches (e.g., Creative + Expressive + Abstract) will saturate at +6.
