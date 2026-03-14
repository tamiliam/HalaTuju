# Retrospective — Security Hardening Sprint (2026-03-14)

## What Was Built

Four security-related tech debt items resolved in a single focused sprint:

1. **TD-012 — Default permission flipped**: `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` changed from `AllowAny` to `SupabaseIsAuthenticated`. 16 public endpoints explicitly marked with `permission_classes = [AllowAny]`. New endpoints are now auth-required by default.

2. **TD-008 — Profile validation**: Created `ProfileUpdateSerializer` (ModelSerializer, 19 fields, partial update). Both `ProfileView.put()` and `ProfileSyncView.post()` now validate input through DRF — malformed requests return 400 instead of crashing with 500.

3. **TD-036 — SECRET_KEY guard**: `production.py` raises `ValueError` if SECRET_KEY equals the insecure dev default. Dev/test environments unaffected.

4. **TD-038 — CORS wildcard guard**: `production.py` raises `ValueError` if `CORS_ALLOWED_ORIGINS=*`. Must use explicit origin list.

## What Went Well

- **Clean, focused changes**: 4 files changed, 57 insertions, 35 deletions. No cascading breakage.
- **Zero test failures**: All 382 tests passed immediately after changes. The `AllowAny` → `SupabaseIsAuthenticated` flip didn't break any tests because all auth-protected endpoints already had explicit `permission_classes`, and public endpoint tests don't send auth headers.
- **Audit was straightforward**: 25 view classes total, 9 already had `SupabaseIsAuthenticated`, 16 needed `AllowAny`.

## What Went Wrong

Nothing significant. This was a well-scoped sprint with clear, mechanical changes.

## Design Decisions

- **Kept insecure fallback in base.py**: The `django-insecure-dev-key-change-in-production` string remains as the fallback for local dev. The guard is in `production.py` only — checking if the inherited value equals the known insecure string. This avoids breaking `manage.py test` and local `runserver`.
- **ModelSerializer over manual Serializer**: Used `ModelSerializer` for `ProfileUpdateSerializer` because all fields map directly to `StudentProfile` model fields. DRF handles type coercion (int for siblings, float for stpm_cgpa) automatically.

## Numbers

| Metric | Value |
|--------|-------|
| Files changed | 4 |
| Tests | 382 pass, 0 fail, 0 skip |
| Tech debt resolved | TD-008, TD-012, TD-036, TD-038 |
| Remaining tech debt | 39 items (13 resolved of 52 total) |
| Views audited | 25 (9 already protected, 16 marked AllowAny) |
