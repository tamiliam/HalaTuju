"""Advisor action 5: replay real past cases through the v3.1.0 engines and the live-main engines.

Design (owner-approved 2026-11-13): `docs/plans/2026-11-13-a5-replay-design.md`. R1 builds the harness and
its safety layers only; the engine adapters, the normaliser, the ruling catalogue and the report are R2.

The package is copied into the replay image as the top-level package `replay` (see `owner/Dockerfile.replay`),
so it runs beside EITHER tree (old or new). Every import inside it is relative, and nothing here imports
an engine at module level.

The layers, each enough on its own to stop a write (design 3.4):
  1. the `replay_ro` role (SELECT only; owner step, `owner/replay_ro_create.sql`);
  2. every transaction `REPEATABLE READ, READ ONLY`, proved by `SHOW` (`guards.begin_snapshot`);
  3. every transaction and every case savepoint always rolled back (`guards.read_only_session`, `run_case`);
  4. the statement filter (`guards.refuse_non_reads`, which reuses `offer_s4_dry_run.refuse_writes`);
  5. nothing to write with: no key in the environment (`guards.check_environment`), a refusing mail
     backend, Storage / Gemini / the meter shut, and no network but the database (`netguard`).
"""
