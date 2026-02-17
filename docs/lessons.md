# Cross-Cutting Lessons

Lessons that apply to any future sprint, regardless of feature area.

- When testing one subsystem in a multi-rule scoring engine, provide explicit inputs for ALL subsystems — don't assume "empty" means "neutral". Default values in tag lookups (e.g. `c_tags.get('career_structure', 'volatile')`) can trigger unrelated scoring rules. (Sprint 4)
- When reusing legacy functions (e.g. Streamlit-era engine code) from a new context (e.g. Django serializer), verify the key/field naming conventions match. The serializer may produce different keys than the original caller expected. (Sprint 6)
