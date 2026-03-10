# Matriculation & STPM Detail Pages — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create detail pages for Matriculation and STPM pathways, showing eligible tracks, merit/mata gred with traffic light, and filterable institution tables.

**Architecture:** Two new frontend-only pages (`/pathway/matric` and `/pathway/stpm`). Matriculation college data (15 KPM colleges) and STPM school data (569 schools from scraped CSV) bundled as static JSON in the frontend. Pathway pills on dashboard navigate to these pages instead of filtering courses. Merit thresholds: Matric 94+ High, 89-93 Fair, <89 Low.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, static JSON data files.

---

## Data

### Matriculation Colleges (15 KPM — excludes MARA, JPPro, SES)

Source: MOE Soalan Lazim Program Matrikulasi (Nov 2024), pages 4-8.

| ID | Name | State | Sains | Sains Komputer | Kejuruteraan | Perakaunan | Phone | Website |
|----|------|-------|:-----:|:--------------:|:------------:|:----------:|-------|---------|
| kmp | KM Perlis | Perlis | Y | — | — | Y | 04-9868613 | kmp.matrik.edu.my |
| kmk | KM Kedah | Kedah | Y | — | — | Y | 04-9286100 | kmk.matrik.edu.my |
| kmpp | KM Pulau Pinang | Pulau Pinang | Y | — | — | Y | 04-5756090 | kmpp.matrik.edu.my |
| kmpk | KM Perak | Perak | Y | Y | — | Y | 05-3594449 | kmpk.matrik.edu.my |
| kms | KM Selangor | Selangor | Y | — | — | Y | 03-31201410 | kms.matrik.edu.my |
| kmns | KM Negeri Sembilan | Negeri Sembilan | Y | — | — | Y | 06-4841825 | kmns.matrik.edu.my |
| kmm | KM Melaka | Melaka | Y | — | — | Y | 06-3832000 | kmm.matrik.edu.my |
| kmj | KM Johor | Johor | Y | Y | — | Y | 06-9781613 | kmj.matrik.edu.my |
| kmph | KM Pahang | Pahang | Y | — | — | Y | 09-5495000 | kmph.matrik.edu.my |
| kmkt | KM Kelantan | Kelantan | Y | Y | — | Y | 09-7808000 | kmkt.matrik.edu.my |
| kml | KM Labuan | Labuan | Y | Y | — | Y | 087-465311 | kml.matrik.edu.my |
| kmsw | KM Sarawak | Sarawak | Y | — | — | — | 082-439100 | kmsw.matrik.edu.my |
| kmkk | KMK Kedah | Kedah | — | — | Y | — | 04-4682508 | kmkk.matrik.edu.my |
| kmkph | KMK Pahang | Pahang | — | — | Y | — | 09-4677103 | kmkph.matrik.edu.my |
| kmkj | KMK Johor | Johor | — | — | Y | — | 07-6881629 | kmkj.matrik.edu.my |

### STPM Schools (569)

Source: `C:\Users\tamil\Python\Archived\SchoolScraper\output\schools_list_v2.csv`

Fields: NO, KOD_SEKOLAH, NEGERI, PPD, NAMA_SEKOLAH, PAKEJ_MATA_PELAJARAN, SEMESTER, MATA_PELAJARAN, ALAMAT, NOMBOR_TELEFON

PAKEJ values: "SAINS" (25), "SAINS SOSIAL" (343), "SAINS; SAINS SOSIAL" (200)

---

## Task 1: Create static data files

**Files:**
- Create: `halatuju-web/src/data/matric-colleges.ts`
- Create: `halatuju-web/src/data/stpm-schools.json` (converted from CSV)
- Create: `halatuju-web/src/data/stpm-schools.ts` (typed import)

**Step 1:** Create `halatuju-web/src/data/matric-colleges.ts` with typed array of 15 colleges:

```typescript
export interface MatricCollege {
  id: string
  name: string
  state: string
  tracks: ('sains' | 'sains_komputer' | 'kejuruteraan' | 'perakaunan')[]
  phone: string
  website: string
}

export const MATRIC_COLLEGES: MatricCollege[] = [
  // ... all 15 colleges from table above
]
```

**Step 2:** Convert STPM CSV to JSON. Run:

```bash
cd halatuju-web
python -c "
import csv, json
with open('../../../Archived/SchoolScraper/output/schools_list_v2.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
schools = []
for r in rows:
    if r['NEGERI'] == 'NEGERI': continue  # skip header dupes
    pakej = r['PAKEJ_MATA_PELAJARAN']
    schools.append({
        'code': r['KOD_SEKOLAH'],
        'name': r['NAMA_SEKOLAH'],
        'state': r['NEGERI'],
        'ppd': r['PPD'],
        'streams': [s.strip() for s in pakej.split(';')] if pakej != 'PAKEJ MATA PELAJARAN' else [],
        'subjects': r['MATA_PELAJARAN'],
        'phone': r['NOMBOR_TELEFON'],
    })
with open('src/data/stpm-schools.json', 'w', encoding='utf-8') as f:
    json.dump(schools, f, ensure_ascii=False, indent=2)
print(f'Wrote {len(schools)} schools')
"
```

**Step 3:** Create `halatuju-web/src/data/stpm-schools.ts`:

```typescript
export interface StpmSchool {
  code: string
  name: string
  state: string
  ppd: string
  streams: string[]  // "SAINS" | "SAINS SOSIAL"
  subjects: string
  phone: string
}

import schoolsData from './stpm-schools.json'
export const STPM_SCHOOLS: StpmSchool[] = schoolsData as StpmSchool[]
```

**Step 4:** Commit.

```bash
git add src/data/
git commit -m "feat: add matric college and STPM school static data"
```

---

## Task 2: Create Matriculation detail page

**Files:**
- Create: `halatuju-web/src/app/pathway/matric/page.tsx`

**Step 1:** Create the page component. It should:

1. Read grades + CoQ from localStorage (same as dashboard)
2. Run `checkAllPathways()` to get matric results
3. Show header: "Matriculation" + student's merit score with traffic light
   - Merit 94+ → green "High", 89-93 → amber "Fair", <89 → red "Low"
4. Show eligible tracks as coloured badges
5. State filter dropdown
6. Table of colleges filtered by state, showing which tracks each offers
7. Caveat text at bottom
8. Back link to dashboard

Key details:
- Use `'use client'`
- Read profile from localStorage key `halatuju_profile` (same as dashboard)
- Merit traffic light: `meritLabel(score)` → 'High'/'Fair'/'Low', colours match existing merit system
- College table columns: Name, State, Tracks (coloured badges), Phone, Website (link)
- Filter: only show colleges that offer at least one of the student's eligible tracks
- Caveat: "Track availability is based on MOE Soalan Lazim (Nov 2024) and may change. Students are assigned to colleges by MOE based on merit and availability — you do not choose your college."

**Step 2:** Build and verify. Run: `npx next build`

**Step 3:** Commit.

```bash
git add src/app/pathway/matric/
git commit -m "feat: add matriculation detail page with college table"
```

---

## Task 3: Create STPM detail page

**Files:**
- Create: `halatuju-web/src/app/pathway/stpm/page.tsx`

**Step 1:** Create the page component. It should:

1. Read grades from localStorage
2. Run `checkAllPathways()` to get STPM results
3. Show header: "Form 6 (STPM)" + student's mata gred + eligible bidang badges
4. Two filters: state dropdown + stream dropdown (Sains / Sains Sosial / All)
5. Table of schools with: Name, State, PPD, Streams (badges), Phone
6. Only show schools that offer the student's eligible bidang
7. Back link to dashboard

Key details:
- State filter: populated from unique states in data (16 states)
- Stream filter: if student eligible for Sains only, default to Sains; if both, show all
- School count shown next to heading: "Schools (123)"
- Streams shown as small badges: green for Sains, blue for Sains Sosial

**Step 2:** Build and verify. Run: `npx next build`

**Step 3:** Commit.

```bash
git add src/app/pathway/stpm/
git commit -m "feat: add STPM detail page with school table and filters"
```

---

## Task 4: Make pathway pills navigate to detail pages

**Files:**
- Modify: `halatuju-web/src/components/PathwayCards.tsx`
- Modify: `halatuju-web/src/app/dashboard/page.tsx`

**Step 1:** Update PathwayCards to accept an `onNavigate` callback for matric/stpm pills. When a matric or stpm pill is clicked, navigate to `/pathway/matric` or `/pathway/stpm` instead of filtering.

In `PathwayCards.tsx`, the `onClick` handler should check:
- If `p.type === 'matric'` → `router.push('/pathway/matric')`
- If `p.type === 'stpm'` → `router.push('/pathway/stpm')`
- Otherwise → toggle filter (existing behaviour)

Import `useRouter` from `next/navigation`.

**Step 2:** Build and verify. Run: `npx next build`

**Step 3:** Commit.

```bash
git add src/components/PathwayCards.tsx src/app/dashboard/page.tsx
git commit -m "feat: matric and stpm pills navigate to detail pages"
```

---

## Task 5: Add i18n keys for detail pages

**Files:**
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1:** Add keys under `pathwayDetail` section:

```json
"pathwayDetail": {
  "backToDashboard": "Back to Dashboard",
  "matricTitle": "Matriculation",
  "stpmTitle": "Form 6 (STPM)",
  "meritScore": "Merit Score",
  "mataGred": "Mata Gred",
  "eligibleTracks": "Eligible Tracks",
  "colleges": "Colleges",
  "schools": "Schools",
  "allStates": "All States",
  "allStreams": "All Streams",
  "sains": "Science",
  "sainsSosial": "Social Science",
  "phone": "Phone",
  "website": "Website",
  "tracks": "Tracks",
  "state": "State",
  "name": "Name",
  "stream": "Stream",
  "high": "High",
  "fair": "Fair",
  "low": "Low",
  "matricCaveat": "Track availability is based on MOE Soalan Lazim (Nov 2024) and may change. Students are assigned to colleges by MOE based on merit and availability.",
  "stpmCaveat": "School data is from MOE SST6 portal. Offerings may change each intake."
}
```

**Step 2:** Translate to BM and Tamil in ms.json and ta.json.

**Step 3:** Commit.

```bash
git add src/messages/
git commit -m "feat: add i18n keys for matric and STPM detail pages"
```

---

## Task 6: Build, test, deploy

**Step 1:** Build frontend: `npx next build`

**Step 2:** Run backend tests to verify no regressions: `cd halatuju_api && python -m pytest apps/courses/tests/ -v`

**Step 3:** Deploy frontend:

```bash
cd halatuju-web
gcloud run deploy halatuju-web --source . --region asia-southeast1 --project gen-lang-client-0871147736 --allow-unauthenticated
```

**Step 4:** Deploy backend (only if backend changed):

```bash
cd halatuju_api
gcloud run deploy halatuju-api --source . --region asia-southeast1 --project gen-lang-client-0871147736 --allow-unauthenticated
```

**Step 5:** Verify live: click Matric and STPM pills on dashboard → should navigate to detail pages.

**Step 6:** Commit any remaining changes, update CHANGELOG.md.
