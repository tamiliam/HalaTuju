"""Generate quirky BM headlines for STPM courses using Gemini."""

import json
import time
from google import genai
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

        client = genai.Client(api_key=api_key)

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
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[SYSTEM_PROMPT, user_prompt],
                    config={'temperature': 0.9, 'max_output_tokens': 4096},
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
