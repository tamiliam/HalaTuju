# HalaTuju — Roadmap

Last updated: 2026-03-20

## Status: v2.0 Released

HalaTuju is feature-complete and live at [halatuju.xyz](https://halatuju.xyz).

---

## What Shipped (v1.0–v2.0)

- SPM eligibility engine (390 courses, 838 institutions)
- STPM eligibility engine (1,113 degree programmes)
- Quiz-based ranking with fit scores (SPM + STPM branching quiz)
- Dashboard with merit traffic lights and pathway cards
- Matric/STPM virtual course eligibility
- PISMP integration with 27 IPG campuses
- AI-powered counsellor reports (Gemini)
- Course search and filtering (unified SPM + STPM)
- Saved courses and admission outcomes tracking
- Student profile with grade storage
- NRIC identity gate (anonymous browsing → verified identity)
- Supabase auth (Google OAuth, anonymous sign-in, linkIdentity)
- Multi-language support (EN/BM/TA)
- Field taxonomy (37 canonical fields, trilingual labels)
- MASCO career mappings (4,854 occupations)
- Admin portal (student list, detail, CSV export)
- Custom domain: halatuju.xyz
- CI/CD: Cloud Build continuous deployment from GitHub

---

## Known Issues

| # | Issue | Impact | Notes |
|---|-------|--------|-------|
| 1 | Phone/OTP login shows "coming soon" | Students without Google accounts cannot register | WhatsApp OTP plan exists (`docs/plans/2026-03-09-whatsapp-otp-plan.md`). Requires Twilio (~RM12/month) |
| 2 | Settings page is a stub | Only has language selector and "Reset All Data" | Low impact — functional but sparse |
| 3 | Report generation has no loading indicator | 10-15 sec Gemini delay feels like a hang | Quick UI fix needed |
| 4 | 87 offerings missing tuition fee data | Fee info not available in source CSVs | Data limitation, not a bug |
| 5 | Course `#` marker not rendered as badge | `#` in course name means "typically has interview" — still shown as raw text | Strip `#` and show interview badge |
| 6 | `course` field named `course` not `name` (TD-024) | `course.course` reads oddly | Low risk, cosmetic. Migration + multi-file update needed |
| 7 | StudentProfile table uses `api_` prefix (TD-025) | Legacy naming from Streamlit coexistence | Low risk. Requires migration + RLS policy update |
| 8 | Startup data load is all-or-nothing (TD-047) | If DB connection fails at startup, first request returns 503 | Cloud Run restarts handle this naturally |

---

## Future Work

### High Priority
- **Phone/OTP login** — Unblocks non-Google users. Twilio/WhatsApp integration needed
- **User testing** — Real students through the full auth + eligibility + report flow
- **Report loading UX** — Progress indicator during Gemini generation

### Medium Priority
- **W8: Institution proximity scoring** — Populate institution modifiers (urban, cultural safety net), capture student location, calculate real distance for proximity-based ranking
- **Grade modulation** — 4 rules cross-referencing grades with quiz signals
- **Report enhancements** — MASCO career data in prompt, institution/location context, EN language selector
- **STPM pipeline maintenance** — Test scrapers against live MOHE annually before UPU season
- **Efficacy domain consumption** — `efficacy_domain` is stored on StpmCourse but not used in ranking formula

### Low Priority / Cosmetic
- **TD-024**: Rename `course` field to `name` on Course model
- **TD-025**: Rename `api_student_profiles` table to `student_profiles`
- **Interview badge** — Parse `#` from course names into proper UI indicator
- **PISMP course-campus mapping** — Refine which courses are taught at which IPG campuses
- **Course detail page** — Remaining items from `docs/Course Detail Page.pdf`
- **Settings page** — Account management, notification preferences, data export
- **Remaining FIELD_KEY_MAP expansions** — pendidikan, bahasa, pengajian-islam, undang-undang, sains-sosial, umum need new quiz questions

### Deferred / Parked
- **Lentera integration** — HalaTuju as Beam 1 (Searchlight) within the broader Lentera programme
- **Signal strength sync** — Store `signal_strength` in Supabase (currently localStorage only)
- **Admin analytics** — Usage stats, grade distributions, course popularity, system health dashboard
