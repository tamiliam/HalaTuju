# Cross-Cutting Lessons

Lessons that apply to any future sprint, regardless of feature area.

- When testing one subsystem in a multi-rule scoring engine, provide explicit inputs for ALL subsystems — don't assume "empty" means "neutral". Default values in tag lookups (e.g. `c_tags.get('career_structure', 'volatile')`) can trigger unrelated scoring rules. (Sprint 4)
