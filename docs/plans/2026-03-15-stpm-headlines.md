# STPM Course Headlines Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add quirky BM headlines to all 951 STPM courses (excl UiTM) and surface them as subtitles on the course detail page.

**Architecture:** Add a `headline` column to `stpm_courses`, create a Django management command that generates headlines via Gemini in batches, update the API to return `headline`, and update the frontend `CourseHeader` to display it.

**Tech Stack:** Django (migration + management command), Gemini API (generation), Next.js (frontend display)

---

### Task 1: Add `headline` column to StpmCourse model

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:565` (add field after `description`)
- Create: `halatuju_api/apps/courses/migrations/NNNN_add_stpm_headline.py` (auto-generated)

**Step 1: Add field to model**

In `models.py`, add after the `description` field (line 565):

```python
headline = models.CharField(max_length=200, blank=True, default='', help_text='Quirky BM headline for student-facing subtitle')
```

**Step 2: Generate migration**

Run: `cd halatuju_api && python manage.py makemigrations courses -n add_stpm_headline`
Expected: Migration file created

**Step 3: Apply migration locally**

Run: `cd halatuju_api && python manage.py migrate`
Expected: Migration applied

**Step 4: Run existing tests to confirm no breakage**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_models.py -v`
Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/*_add_stpm_headline.py
git commit -m "feat: add headline column to stpm_courses table"
```

---

### Task 2: Update STPM API to return headline

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:1297-1309` (add headline to response)
- Modify: `halatuju-web/src/lib/api.ts:613-625` (add headline to TypeScript interface)

**Step 1: Add headline to API response**

In `views.py` at line 1297, the `StpmCourseDetailView.get()` method returns a dict. Add `headline`:

```python
return Response({
    'course_id': prog.course_id,
    'course_name': prog.course_name,
    'university': prog.university,
    'stream': prog.stream,
    'field': prog.field,
    'category': prog.category,
    'description': prog.description,
    'headline': prog.headline,          # <-- add this
    'merit_score': prog.merit_score,
    'mohe_url': prog.mohe_url or '',
    'requirements': requirements,
    'institution': institution_data,
})
```

**Step 2: Update TypeScript interface**

In `api.ts`, add `headline` to `StpmCourseDetail`:

```typescript
export interface StpmCourseDetail {
  course_id: string
  course_name: string
  university: string
  stream: string
  field: string
  category: string
  description: string
  headline: string             // <-- add this
  merit_score: number | null
  mohe_url?: string
  requirements: StpmRequirements
  institution: StpmInstitutionDetail | null
}
```

**Step 3: Run API tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_api.py apps/courses/tests/test_stpm_search.py -v`
Expected: All pass (headline is just an extra field, empty string by default)

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/views.py halatuju-web/src/lib/api.ts
git commit -m "feat: return headline in STPM course detail API"
```

---

### Task 3: Update STPM detail page to show headline

**Files:**
- Modify: `halatuju-web/src/app/stpm/[id]/page.tsx` (pass headline as subtitle)

**Step 1: Update CourseHeader subtitle prop**

Change the `CourseHeader` usage from:

```tsx
<CourseHeader
  sourceType="university"
  level="Ijazah Sarjana Muda"
  title={data.course_name}
  subtitle={data.university}
/>
```

To:

```tsx
<CourseHeader
  sourceType="university"
  level="Ijazah Sarjana Muda"
  title={data.course_name}
  subtitle={data.headline || data.university}
/>
```

This falls back to university name if no headline exists yet.

**Step 2: TypeScript check**

Run: `cd halatuju-web && npx tsc --noEmit`
Expected: Clean

**Step 3: Commit**

```bash
git add halatuju-web/src/app/stpm/[id]/page.tsx
git commit -m "feat: show headline as subtitle on STPM detail page"
```

---

### Task 4: Create headline generation management command

**Files:**
- Create: `halatuju_api/apps/courses/management/commands/generate_stpm_headlines.py`

**Context:** The existing SPM headlines follow this pattern — emoji + short catchy BM tagline aimed at 17-20 year olds:
- `👶 Guru Prasekolah: Pembina Asas Kehidupan`
- `🤖 Diploma Mekatronik: Jurutera Serba Boleh`
- `📡 Elektronik (Komunikasi): Dunia Tanpa Wayar`
- `🎵 Diploma Muzik: Dari Teori ke Pentas`

STPM headlines should match this tone.

**Step 1: Write the management command**

```python
"""Generate quirky BM headlines for STPM courses using Gemini."""

import json
import time
import google.generativeai as genai
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.courses.models import StpmCourse


BATCH_SIZE = 50

SYSTEM_PROMPT = """Kamu adalah penulis kreatif untuk laman web pendidikan Malaysia.
Tugas: Cipta headline pendek dan menarik dalam Bahasa Melayu untuk kursus universiti.
Sasaran: Pelajar berumur 17-20 tahun.

Format: emoji + tagline ringkas (maks 60 aksara selepas emoji).
Contoh:
- 🤖 Mekatronik: Jurutera Serba Boleh
- 📡 Elektronik Komunikasi: Dunia Tanpa Wayar
- ⚗️ Teknologi Polimer: Sains Plastik
- 🧠 ASASIPintar: Program Minda Genius
- ⚽ Pendidikan Jasmani: Jurulatih Generasi Sihat

Peraturan:
1. Mula dengan satu emoji yang sesuai
2. Tagline mesti ringkas, catchy, dan relevan
3. Guna Bahasa Melayu sahaja (tiada Inggeris)
4. Jangan ulang nama kursus penuh — ringkaskan
5. Pastikan setiap headline unik

Balas dalam format JSON sahaja:
{"headlines": {"course_id_1": "emoji headline", "course_id_2": "emoji headline"}}"""


class Command(BaseCommand):
    help = 'Generate quirky BM headlines for STPM courses via Gemini'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Print headlines without saving to DB')
        parser.add_argument('--limit', type=int, default=0,
                            help='Max courses to process (0 = all)')
        parser.add_argument('--overwrite', action='store_true',
                            help='Regenerate even if headline already exists')

    def handle(self, *args, **options):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            self.stderr.write('GEMINI_API_KEY not set')
            return

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Select courses needing headlines
        qs = StpmCourse.objects.exclude(
            university__icontains='Teknologi MARA'
        )
        if not options['overwrite']:
            qs = qs.filter(headline='')
        qs = qs.order_by('course_id')

        if options['limit']:
            qs = qs[:options['limit']]

        courses = list(qs.values('course_id', 'course_name', 'university',
                                  'field', 'category', 'stream'))
        total = len(courses)
        self.stdout.write(f'Generating headlines for {total} courses...')

        generated = 0
        failed = 0

        for i in range(0, total, BATCH_SIZE):
            batch = courses[i:i + BATCH_SIZE]
            prompt_lines = []
            for c in batch:
                prompt_lines.append(
                    f"- {c['course_id']}: {c['course_name']} "
                    f"({c['university']}, {c['category'] or c['field']}, "
                    f"{'Sains' if c['stream'] == 'science' else 'Sastera'})"
                )
            user_prompt = (
                f"Cipta headline untuk {len(batch)} kursus berikut:\n\n"
                + "\n".join(prompt_lines)
            )

            try:
                response = model.generate_content(
                    [SYSTEM_PROMPT, user_prompt],
                    generation_config={'temperature': 0.9, 'max_output_tokens': 4096},
                )
                text = response.text.strip()
                # Strip markdown fences if present
                if text.startswith('```'):
                    text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
                data = json.loads(text)
                headlines = data.get('headlines', data)
            except Exception as e:
                self.stderr.write(f'Batch {i // BATCH_SIZE + 1} failed: {e}')
                failed += len(batch)
                time.sleep(5)
                continue

            for c in batch:
                cid = c['course_id']
                headline = headlines.get(cid, '')
                if not headline:
                    failed += 1
                    continue
                # Truncate to 200 chars
                headline = headline[:200]
                if options['dry_run']:
                    self.stdout.write(f'  {cid}: {headline}')
                else:
                    StpmCourse.objects.filter(course_id=cid).update(
                        headline=headline
                    )
                generated += 1

            self.stdout.write(
                f'  Batch {i // BATCH_SIZE + 1}: '
                f'{len(batch)} processed'
            )
            # Rate limit: Gemini free tier = 15 RPM
            time.sleep(5)

        self.stdout.write(
            f'\nDone: {generated} generated, {failed} failed '
            f'(of {total} total)'
        )
```

**Step 2: Test with dry run (small batch)**

Run: `cd halatuju_api && python manage.py generate_stpm_headlines --dry-run --limit 5`
Expected: 5 headlines printed to stdout, nothing saved

**Step 3: Review output quality with user**

Show the 5 sample headlines for tone/style approval before running the full batch.

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/management/commands/generate_stpm_headlines.py
git commit -m "feat: management command to generate STPM headlines via Gemini"
```

---

### Task 5: Generate all headlines

**Prerequisite:** User has approved the tone from Task 4's dry run.

**Step 1: Run full generation**

Run: `cd halatuju_api && python manage.py generate_stpm_headlines`
Expected: ~951 headlines generated (some may fail, re-run for stragglers)

**Step 2: Verify coverage**

```sql
SELECT
  COUNT(*) FILTER (WHERE headline != '') as has_headline,
  COUNT(*) FILTER (WHERE headline = '') as missing,
  COUNT(*) as total
FROM stpm_courses
WHERE university NOT ILIKE '%teknologi mara%';
```

Expected: ~951 has_headline, 0 missing

**Step 3: Re-run for any failures**

Run: `cd halatuju_api && python manage.py generate_stpm_headlines`
(Command auto-skips courses that already have headlines)

**Step 4: Spot-check quality**

```sql
SELECT course_id, course_name, headline
FROM stpm_courses
WHERE headline != ''
ORDER BY random()
LIMIT 20;
```

Review with user for quality.

**Step 5: Run full test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All 424 tests pass

**Step 6: Commit and push**

```bash
git add -A
git commit -m "feat: generate BM headlines for 951 STPM courses"
git push
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Add `headline` column | model + migration |
| 2 | Return headline in API | views.py + api.ts |
| 3 | Show headline in frontend | stpm/[id]/page.tsx |
| 4 | Create generation command | management command |
| 5 | Generate all headlines | run command + verify |

**Total files touched:** 6 (create 2, modify 4)

**Risk:** Gemini API calls cost credits. At ~19 batches of 50, that's ~19 API calls on the free tier. Well within limits.

**Rollback:** If headlines are bad, `UPDATE stpm_courses SET headline = '' WHERE headline != '';` resets everything. Frontend falls back to university name.
