# HalaTuju v2.0 Release Candidate — Release Notes

**Date**: 2026-03-20
**Tag**: `v2.0-rc`
**Domain**: [halatuju.xyz](https://halatuju.xyz)

---

## Overview

HalaTuju v2.0-rc is a complete course recommendation platform for Malaysian SPM and STPM students. This release represents a full rebuild from the original Streamlit prototype into a production Django + Next.js application deployed on Cloud Run.

---

## Features Delivered

### Core Eligibility
- **SPM eligibility engine**: 390 courses across polytechnics, TVET centres, ILJTM, ILKBS, IPG (PISMP), and pre-university pathways
- **STPM eligibility engine**: 1,113 degree programmes across Malaysian universities
- **Matric/STPM virtual pathway eligibility**: 4 matric tracks + 2 STPM bidangs as real DB entries
- **PISMP integration**: 73 courses across 27 IPG campuses with subject-tag ranking
- **Golden masters**: SPM=5319, STPM=2026 (regression-protected)

### Quiz & Ranking
- **SPM quiz**: 6-question personality quiz mapping to 36 signal labels across work style, environment, learning, and career preferences
- **STPM branching quiz**: ~35 questions with subject-seeded RIASEC branching (Science/Arts/Mixed), grade-adaptive confidence check, cross-domain stream filtering
- **Fit score ranking**: Multi-component scoring (field match, signal alignment, merit penalty, credential priority, institution modifiers)
- **STPM ranking**: 7-component formula (CGPA margin, field match, RIASEC alignment, efficacy modifier, goal alignment, resilience discount, interview penalty)
- **Result framing**: 3 modes (confirmatory/guided/discovery) based on quiz crystallisation

### AI Reports
- **Gemini-powered counsellor reports**: Personalised narrative reports in BM and EN
- **Model cascade**: gemini-2.5-flash -> gemini-2.5-flash-lite -> gemini-2.0-flash -> gpt-4o-mini (OpenAI fallback)
- **Two-track prompts**: SPM and STPM-specific prompt templates with human-readable signal formatting
- **Rate limiting**: 3 reports per user per day

### Data & Taxonomy
- **Field taxonomy**: 37 canonical fields with trilingual labels (EN/MS/TA), image slugs, RIASEC primary types
- **MASCO career mappings**: 4,854 occupations linked to courses via AI-assisted pipeline
- **STPM data enrichment**: RIASEC type, difficulty level, efficacy domain on all 1,113 courses
- **Institution modifiers**: Urban classification and cultural safety net scores for 838 institutions

### Identity & Auth
- **NRIC hard gate**: Anonymous browsing with verified identity required for protected features
- **Supabase auth**: Google OAuth + anonymous sign-in + linkIdentity upgrade flow
- **Email verification**: Trilingual verification emails (EN/MS/TA)
- **Admin auth**: Separate PartnerAdmin system with invite flow and org-scoped access

### User Features
- **Dashboard**: Card grid with merit traffic lights, pathway stats, quiz-informed framing
- **Course search**: Unified SPM+STPM search with text, level, field, source type, state filters
- **Course detail**: Offerings (fees, allowances, hyperlinks), career pathways, SPM prerequisites
- **Saved courses**: Dual-FK model (SPM + STPM), interest status tracking, tabbed saved page
- **Admission outcomes**: CRUD with institution tracking
- **Profile**: Grade storage, quiz signals, NRIC, contact info, school
- **Referral system**: `/r/[code]` shortlinks with OG meta tags, referral tracking in admin

### Internationalisation
- **3 languages**: English, Bahasa Melayu, Tamil
- **Full coverage**: All user-facing pages, admin pages, emails, error messages
- **OG meta tags**: WhatsApp/social media link previews with student photo

### Infrastructure
- **CI/CD**: Cloud Build continuous deployment from GitHub (push to main triggers deploy)
- **Custom domain**: halatuju.xyz with Cloud Run domain mapping
- **GCP cost monitoring**: RM50/month budget alert, BigQuery billing export
- **Security**: RLS on all Supabase tables, 0 security advisor errors, JWT auth (ES256 + HS256)

---

## Test Coverage

| Suite | Count |
|-------|-------|
| Backend (pytest) | 992 |
| Frontend (Jest) | 17 |
| Pipeline tools | 278 |
| **Total** | **1,287** |

Golden masters: SPM=5319, STPM=2026

---

## Known Issues

See `docs/roadmap.md` for the full list (8 known issues, categorised future work).

Key items:
1. Phone/OTP login not yet available (Google-only)
2. Report generation has no loading indicator (10-15 sec delay)
3. 87 offerings missing tuition fee data

---

## Breaking Changes

None. This is the first production release on the new stack.

---

## Migration from v1.33.0

v1.33.0 was the last Streamlit-era tag. v2.0-rc is a complete rebuild:
- Backend: Streamlit -> Django REST on Cloud Run
- Frontend: Streamlit -> Next.js 14 on Cloud Run
- Database: CSV files -> Supabase PostgreSQL
- Auth: None -> Supabase (Google OAuth + NRIC gate)
- STPM: Not supported -> 1,113 degree programmes
