# Engineering Lessons — HalaTuju

Cross-cutting lessons from sprint retrospectives. Only items that affect future work regardless of feature area.

- Bulk data loading via MCP tools should always be delegated to subagents to avoid context exhaustion. Each batch consumes significant context; 20+ batches will overflow the main window. (STPM Sprint 3)
- When modifying grade scales or lookup tables, always run golden master tests immediately — parsed data may contain legacy values not visible in the UI-facing code. (STPM Sprint 5)
- Use constants for localStorage keys instead of string literals to prevent key mismatch bugs across pages built in different sprints. (STPM Sprint 5)
- Always check `class Meta: db_table` in Django models before writing raw SQL against Supabase — default naming (`app_model`) doesn't apply when custom table names are set. (STPM Sprint 6)
- For bulk data loads >500 rows into Supabase, generate a SQL file and use `psql` or a management command instead of MCP batches — each batch consumes context and 20+ batches will overflow the window. (STPM Sprint 6)
- Cloud Run `NEXT_PUBLIC_*` env vars are baked at build time — tagged revisions still call the main API URL unless the frontend is rebuilt with the tagged URL. (STPM Sprint 6)
- Django management commands must read config from `django.conf.settings` first, not `os.environ.get()` — Django doesn't auto-load `.env` into the environment. (STPM Sprint 7)
- For AI taxonomy classification, use a closed set of categories (no "add new if none fits") or include a two-pass approach — open-ended prompts produce hyper-specific values that defeat the purpose of a taxonomy. (STPM Sprint 7)
