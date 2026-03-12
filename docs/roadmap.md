# HalaTuju — Long-term Roadmap

Last updated: 2026-03-12

## Completed (v1.0–v1.33.0)

- SPM eligibility engine (383 courses, 212+ institutions)
- Quiz-based ranking with fit scores
- Dashboard with merit traffic lights and pathway cards
- Matric/STPM virtual course eligibility (backend)
- PISMP integration with 27 IPG campuses
- AI-powered counselor reports (Gemini)
- Course search and filtering
- Saved courses and admission outcomes tracking
- Student profile with grade storage
- Supabase auth (ES256 + HS256 JWT)
- Multi-language support (EN/BM/TA)

## Planned — STPM Entrance

**Priority:** High
**Scope:** Multi-sprint feature
**Data available:** ~1,680 programmes (1,003 science + 677 arts) with STPM-specific requirements parsed

### What It Is
Currently HalaTuju only accepts SPM grades as input. STPM entrance allows students who have completed Form 6 to input their STPM subjects, grades, CGPA, and MUET band. The engine then recommends degree programmes based on STPM-specific requirements.

### Why It Matters
STPM is the second-largest pathway into Malaysian universities after Matriculation. Without STPM entrance support, Form 6 leavers cannot use HalaTuju at all.

### Key Differences from SPM Flow
- **Input**: STPM subjects + grades (A, A-, B+, B, B-, C+, C, C-, D+, D, F) instead of SPM grades
- **CGPA**: Calculated from STPM grades, used as primary eligibility filter
- **MUET**: Malaysian University English Test band (1-6), required by most programmes
- **Pengajian Am (PA)**: Compulsory STPM subject, required by almost all programmes
- **Subject groups**: Complex JSON-based requirements (min count + min grade from a set of subjects)
- **SPM prerequisites**: Most STPM programmes still require SPM credits in BM, pass Sejarah, and sometimes specific SPM subjects

### Data Source
- `Archived/Random/data/stpm_science_requirements_parsed.csv` — 1,003 science programmes
- `Archived/Random/data/stpm_arts_requirements_parsed.csv` — 677 arts programmes
- Fields: program_id, program_name, university, stream, min_cgpa, stpm requirements, spm prerequisites, min_muet_band, interview/colorblind/fitness flags

### High-Level Tasks
1. **Data modelling** — New models or extend existing for STPM requirements (CGPA, MUET, subject groups)
2. **Data import** — Load ~1,680 programmes into DB, map to existing courses where possible
3. **Eligibility engine** — New STPM eligibility checker (CGPA threshold, subject matching, SPM prerequisites)
4. **Onboarding flow** — STPM-specific grade input UI (subjects, grades, MUET band)
5. **Dashboard integration** — STPM results displayed alongside SPM results (or separate view)
6. **Ranking** — Adapt fit score calculation for degree-level programmes
7. **Testing** — Golden master for STPM pathway

---

## Planned — Admin Dashboard

**Priority:** High
**Scope:** Multi-sprint feature

### What It Is
A protected frontend section within HalaTuju for administrators to view student data, usage analytics, and system health. Not a separate app — a new route group within the existing Next.js frontend.

### Why It Matters
Currently there is no visibility into how students are using HalaTuju, what courses are most popular, or whether the recommendation engine is performing well. Admin access is needed for monitoring, reporting, and data-driven improvements.

### Key Views
1. **Student Overview** — List of registered students, their grades, quiz completion status, report generation history
2. **Analytics Dashboard** — Aggregate stats: registrations over time, grade distributions, most/least eligible courses, pathway popularity breakdown
3. **Eligibility Insights** — Which courses have the most High/Fair/Low matches, merit cutoff distribution, courses with zero eligible students
4. **Report Monitoring** — AI report generation stats, success/failure rates, average generation time
5. **Data Quality** — Courses missing tags, offerings missing fees, institutions missing metadata
6. **System Health** — API response times, error rates, deployment history

### High-Level Tasks
1. **Auth & roles** — Admin role in Supabase (separate from student), route protection
2. **Backend API** — New admin endpoints for aggregated data (student counts, grade distributions, course stats)
3. **Frontend pages** — Dashboard layout, charts (recharts or similar), data tables
4. **Data export** — CSV/PDF export for reporting
5. **Access control** — Only designated admin users can access

### Technical Considerations
- Admin queries may be expensive on large datasets — consider materialised views or periodic aggregation
- Must not affect student-facing API performance
- Consider read-only Supabase connection for admin queries

---

## Backlog (Lower Priority)

- **Phone/OTP login** — Replace current "coming soon" message with actual phone authentication
- **Grade modulation** — 4 rules cross-referencing StudentProfile.grades with quiz signals
- **Course detail page fixes** — Remaining items from `docs/Course Detail Page.pdf`
- **Signal strength sync** — Store `signal_strength` in Supabase (currently only `student_signals` synced)
- **Interview badge** — Parse `#` from course names into proper UI indicator
- **PISMP course-campus mapping** — Refine which courses are taught at which specific IPG campuses
- **Lentera integration** — HalaTuju as Beam 1 (Searchlight) within the broader Lentera programme
