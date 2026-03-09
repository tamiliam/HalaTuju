# My Profile Page — Design Document

**Date:** 2026-03-09
**Status:** Approved
**Stitch:** [Preview](https://stitch.withgoogle.com/preview/13238979537238863747?node-id=8a5b67ac384143b18d5c2a445e8d5df1)

## Context

HalaTuju currently collects minimal student data during onboarding (gender, nationality, state, special needs). For Lentera longitudinal tracking, we need richer student profiles (NRIC, address, family income). Additionally, the existing "My Applications" feature (Saved + Outcomes pages) feels disconnected — it should be reframed as a course interests list within the profile.

## Design Decisions

1. **Onboarding stays minimal** — no new fields added to onboarding. The expanded profile is a separate `/profile` page accessible from the nav bar.
2. **Student self-reports all data** — no counsellor portal needed yet.
3. **PDPA consent deferred** — collect fields now, add formal consent tracking when Lentera formalises.
4. **Course interests, not applications** — HalaTuju provides guidance only. Students can't apply through HalaTuju. The feature tracks interest/intent, not actual applications (UPU/UPTVET handle that).
5. **Status tags are student-set** — Interested / Planning to apply / Applied / Got offer. These are self-reported reference notes, not system-verified states.

## Page Structure

Route: `/profile` (new page, requires authentication)
Accessible from: Navigation bar (new "My Profile" link between Search and Settings)

### Section 1 — Personal Details
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Name | text | Yes | Pre-filled from Google auth |
| NRIC | text | No | Format: XXXXXX-XX-XXXX |
| Gender | toggle (Male/Female) | Yes | Carried from onboarding |
| Nationality | toggle (Malaysian/Foreign) | No | Carried from onboarding |

### Section 2 — Contact & Location
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| State | dropdown | No | 16 Malaysian states, carried from onboarding |
| Address | textarea | No | Free text |
| Phone | text | No | Placeholder: +60 12-345 6789 |

### Section 3 — Family & Background
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Family monthly income | dropdown | No | Ranges: <RM1,000 / RM1,001-3,000 / RM3,001-5,000 / RM5,001-10,000 / >RM10,000 |
| Number of siblings | number | No | |
| Colour blindness | checkbox | No | Carried from onboarding |
| Physical disability | checkbox | No | Carried from onboarding |

### Section 4 — My Course Interests
- Populated from saved courses (existing SavedCourse model)
- Each course shows: name, institution, and a status dropdown
- Status options: Interested (gray) / Planning to apply (blue) / Applied (amber) / Got offer (green)
- Remove button (unsaves the course)
- Empty state: "Save courses from the dashboard to track them here"

### Actions
- "Save Changes" button (full-width, primary blue)
- "Last saved" timestamp

## Data Model Changes

### StudentProfile (existing model — add fields)
```python
# New fields
nric = models.CharField(max_length=14, blank=True, default='')
address = models.TextField(blank=True, default='')
phone = models.CharField(max_length=20, blank=True, default='')
family_income = models.CharField(max_length=30, blank=True, default='')
siblings = models.IntegerField(null=True, blank=True)
```

### SavedCourse (existing model — add field)
```python
# New field
interest_status = models.CharField(
    max_length=20,
    choices=[
        ('interested', 'Interested'),
        ('planning', 'Planning to apply'),
        ('applied', 'Applied'),
        ('got_offer', 'Got offer'),
    ],
    default='interested'
)
```

## API Changes

### Existing endpoints (modify)
- `PUT /api/v1/profile/` — accept new fields (nric, address, phone, family_income, siblings)
- `GET /api/v1/profile/` — return new fields
- `PUT /api/v1/saved-courses/<id>/` — accept `interest_status` field (new endpoint or extend existing)

### No new endpoints needed
- Profile page reads from `GET /api/v1/profile/` + `GET /api/v1/saved-courses/`
- Saves via `PUT /api/v1/profile/` + individual saved course status updates

## Navigation Change
Add "My Profile" link to the header nav, between Search and Settings. Active state when on `/profile`.

## Out of Scope
- Course detail page fixes (separate sprint)
- PDPA consent form
- Counsellor portal
- NRIC encryption (Lentera requirement, future)
- i18n for new fields (Sprint 21 scope)
