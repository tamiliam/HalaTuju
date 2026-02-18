# Cross-Cutting Lessons

Lessons that apply to any future sprint, regardless of feature area.

- When testing one subsystem in a multi-rule scoring engine, provide explicit inputs for ALL subsystems — don't assume "empty" means "neutral". Default values in tag lookups (e.g. `c_tags.get('career_structure', 'volatile')`) can trigger unrelated scoring rules. (Sprint 4)
- When reusing legacy functions (e.g. Streamlit-era engine code) from a new context (e.g. Django serializer), verify the key/field naming conventions match. The serializer may produce different keys than the original caller expected. (Sprint 6)
- When `pd.concat` merges DataFrames with different columns, missing values become NaN (which is truthy in Python, not None). Always guard JSON-parsing functions with `isinstance(val, str)` before calling `.strip()` or `json.loads()`. (Sprint 7)
- Empty `subjects: []` in `subject_group_req` JSON doesn't mean "skip this rule" — it means "count from ANY subject". Test your engine logic with the actual data format, not just existing data patterns. (Sprint 7)
- When mocking a lazily-imported module (imported inside a function, not at module top), patch the actual module path (e.g. `google.generativeai.GenerativeModel`) not the local reference (e.g. `mymodule.genai`). The local name doesn't exist as a module attribute until the function runs. (Sprint 11)
- When filtering Django querysets by an external auth ID (e.g. Supabase UUID), use the FK traversal (`student__supabase_user_id=request.user_id`) not the FK column (`student_id=request.user_id`). The FK column is the integer PK, not the UUID — they'll never match. Always write view-level tests for auth-filtered endpoints, not just unit tests for underlying functions. (Sprint 12)
