# HalaTuju — SPM Course Recommendation Platform

HalaTuju helps Malaysian SPM leavers find the right post-secondary course. It checks eligibility across 383 courses at 239 institutions, ranks matches by academic fit and personal interests, and generates AI-powered counselor reports — in English, Bahasa Melayu, and Tamil.

## Coverage

| Pathway | Courses | Institutions |
|---------|---------|-------------|
| Polytechnics | Diploma programmes | 36 Politeknik |
| Public Universities (IPTA) | Asasi, Diploma | 20 UA |
| Community Colleges (KKOM) | Sijil, Diploma | 100+ Kolej Komuniti |
| TVET — ILJTM | Sijil, Diploma | 22 ILP/ADTEC |
| TVET — ILKBS | Sijil Lanjutan, Diploma | 30+ ILKBS |
| PISMP (Teacher Training) | Ijazah Sarjana Muda Pendidikan | 27 IPG Campuses |
| Matriculation | 4 tracks (virtual) | Computed from grades |
| STPM (Form 6) | 2 bidangs (virtual) | Computed from grades |

## Architecture

```
Next.js Frontend (Cloud Run)          Django API (Cloud Run)
halatuju-web                          halatuju-api
        |                                    |
        +--- POST /api/v1/eligibility/check/ |
        +--- POST /api/v1/ranking/           |
        +--- GET  /api/v1/courses/search/    |
        +--- POST /api/v1/quiz/submit/       |
                                             |
                                    Supabase PostgreSQL
                                    (Singapore)
```

- **Backend**: Django REST API — eligibility engine loads DB into Pandas DataFrame at startup
- **Frontend**: Next.js 14 — dashboard with merit traffic lights, pathway cards, course search
- **Database**: Supabase (PostgreSQL with RLS)
- **AI Reports**: Google Gemini — bilingual counselor report generation
- **Deployment**: Google Cloud Run (asia-southeast1)

## Quick Start

### Backend

```bash
cd halatuju_api
pip install -r requirements.txt
cp .env.example .env  # Configure DATABASE_URL, SECRET_KEY, etc.
python manage.py runserver
```

### Frontend

```bash
cd halatuju-web
npm install
cp .env.example .env.local  # Configure NEXT_PUBLIC_API_URL
npm run dev
```

### Deploy

```bash
# Backend
gcloud run deploy halatuju-api --source halatuju_api/ \
  --region asia-southeast1 --project gen-lang-client-0871147736 \
  --allow-unauthenticated

# Frontend
gcloud run deploy halatuju-web --source halatuju-web/ \
  --region asia-southeast1 --project gen-lang-client-0871147736 \
  --allow-unauthenticated
```

## Testing

```bash
cd halatuju_api

# Full suite (259 tests, 250 passing)
python -m pytest apps/courses/tests/ -v

# Golden master only (baseline: 8283)
python -m pytest apps/courses/tests/test_golden_master.py -v
```

## Key Features

- **Eligibility Engine** — checks SPM grades against course requirements (general rules, subject groups, distinctions, complex OR-logic)
- **Merit Traffic Lights** — High / Fair / Low chance indicator per course based on merit cutoff
- **Matric/STPM Virtual Courses** — computed at runtime from student grades, not stored in DB
- **Quiz-Based Ranking** — 6-question interest quiz feeds into fit score calculation
- **PISMP Deduplication** — groups 73 PISMP courses by name, merges language variants
- **AI Counselor Reports** — Gemini-generated bilingual reports with career pathway analysis
- **Multi-Language** — full UI in English, Bahasa Melayu, and Tamil

## Documentation

- `halatuju_api/CLAUDE.md` — detailed architecture, deployment, and testing guide
- `docs/roadmap.md` — planned features (STPM entrance, admin dashboard)
- `docs/release-notes-v1.33.0.md` — latest release notes
- `CHANGELOG.md` — full version history

## License

Internal / Proprietary.
