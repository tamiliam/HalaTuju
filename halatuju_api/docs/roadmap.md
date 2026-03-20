# HalaTuju — Roadmap & Future Work

## Future Enhancements

### Ranking
- **W8 Part 2: Capture student location** — Add `home_state` to StudentProfile (derive from postcode or state dropdown on onboarding). Prerequisite for distance-based proximity scoring. Parked: most students think in state terms, and Part 1 (institution modifiers) already activates the proximity signal.
- **W8 Part 3: Real proximity scoring** — Replace cultural_safety_net heuristic with state-based distance calculation (same state = boost, adjacent = moderate, distant = no bonus). Depends on Part 2. Parked: Part 1 covers the core user need; revisit if user testing reveals demand.
- **W8: Institution modifiers for STPM ranking** — `stpm_ranking.py` has no institution modifier logic. Would need to add urban/safety_net scoring similar to SPM ranking engine. Low priority since STPM courses link to only 20 IPTA institutions.
- **W5: Document/review cap rationale** — Category caps are asymmetric (field interest=8, work preference=4, others=6) with no documented reasoning.
- **W9: Negative field mismatch penalty** — Mismatched courses aren't pushed down, just not boosted. Low impact.
- **W15: Lightweight STPM course tags** — STPM courses have no course tags (lab, workshop, etc.). Medium effort.
- **W18: Score confidence tiers for STPM** — Show confidence level based on how many signals contributed to the score.

### Quiz & Signals
- **W6: Multi-select weight splitting** — Selecting 2+ options reduces signal weight. Penalises broad-interest students.
- **W7 remaining: New quiz questions** — 7 unmapped field_keys (pendidikan, bahasa, pengajian-islam, undang-undang, sains-sosial, umum, komunikasi-media) need new quiz questions to capture field interest.

### Reports
- MASCO career data in prompt, institution/location context
- EN language selector in frontend

### UI
- Course detail page fixes from `docs/Course Detail Page.pdf`
- Grade modulation layer

### Infrastructure
- STPM Pipeline: test scrapers against live MOHE
- Phone/OTP login (blocked — Twilio ~RM12/mo)

### i18n
- W10: Fit reasons are English-only — should be bilingual BM/EN
