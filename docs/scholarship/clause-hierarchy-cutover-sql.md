# Clause hierarchy — prod cutover SQL (migrate-first)

Migration `scholarship/0105_contractclause_level` applied to prod (Supabase `pbrrlyoyyiftckqvzvvo`)
BEFORE the deploy, per the migrate-first convention. Adds the clause nesting depth. Pre-state
2026-07-19: `level` absent; 16 existing `contract_clauses` rows (the 2026-v1 draft) → all become
level 0 (top-level), which is correct.

```sql
ALTER TABLE contract_clauses
  ADD COLUMN level smallint NOT NULL DEFAULT 0 CHECK (level >= 0);

INSERT INTO django_migrations (app, name, applied)
  VALUES ('scholarship', '0105_contractclause_level', now());
```

The inline CHECK (Django's `PositiveSmallIntegerField` adds `level >= 0`) gets an auto-generated
name that differs from Django's — harmless, same caveat as 0103/0104. `level` is 0/1/2 in practice
(0 clause, 1 sub, 2 sub-sub); numbers are computed, never stored.
