# HalaTuju — Long-term Roadmap

Last updated: 2026-03-13

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

## Completed — STPM Entrance (6 Sprints, feature/stpm-entrance branch)

- 1,113 STPM degree programmes loaded into Supabase
- STPM eligibility engine with CGPA calculator, grade comparison, SPM prerequisites
- STPM ranking engine (CGPA margin, field match, interview penalty)
- Frontend: exam type selection, STPM grade entry (stream selector, 3+1 subjects, 90/10 CGPA), dashboard with fit scores
- Search API + programme detail API, frontend search + detail pages
- Grade scale corrected: D+(1.33), C-(1.67), E/G legacy aliases
- Quiz signal localStorage fix + ranking field_interest format fix
- Merit scoring: 1,080 courses with UPU purata markah merit (59.33%–100%), traffic light badges (High/Fair/Low)
- Koko score corrected to 0–10 scale, CGPA formula: (academic × 0.9) + (koko × 0.04)
- Elective add-button UX, zero-courses empty state, ICT stream fix
- Tests: 326 collected, 293 passing | SPM: 8283 | STPM: 1811
- **Deployed** with revision tag for E2E testing — merit traffic lights verified working
- **Next:** Merge to main, full production deploy

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
