"""
One-time Gemini batch job to classify STPM courses.

Usage:
    python manage.py enrich_stpm_metadata          # Dry run (print, don't save)
    python manage.py enrich_stpm_metadata --save    # Save to DB
    python manage.py enrich_stpm_metadata --save --batch-size 20
    python manage.py enrich_stpm_metadata --only-empty --save
"""
import json
import os
import time

from django.core.management.base import BaseCommand
from apps.courses.models import Course, StpmCourse

import google.generativeai as genai


class Command(BaseCommand):
    help = 'Classify STPM courses with field/category/description using Gemini'

    def add_arguments(self, parser):
        parser.add_argument('--save', action='store_true', help='Save results to DB')
        parser.add_argument('--batch-size', type=int, default=25, help='Courses per Gemini call')
        parser.add_argument('--only-empty', action='store_true', help='Skip courses with existing field')

    def handle(self, *args, **options):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            self.stderr.write('GEMINI_API_KEY not set')
            return

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Get existing SPM field taxonomy
        spm_fields = sorted(set(
            Course.objects.exclude(frontend_label='')
            .values_list('frontend_label', flat=True)
        ))
        self.stdout.write(f'SPM field taxonomy ({len(spm_fields)} categories): {spm_fields}')

        # Get STPM courses to classify
        qs = StpmCourse.objects.all().order_by('program_id')
        if options['only_empty']:
            qs = qs.filter(field='')
        courses = list(qs.values_list('program_id', 'program_name', 'university', 'stream'))
        self.stdout.write(f'Courses to classify: {len(courses)}')

        batch_size = options['batch_size']
        updated = 0

        for i in range(0, len(courses), batch_size):
            batch = courses[i:i + batch_size]
            batch_num = i // batch_size + 1
            self.stdout.write(f'Batch {batch_num} ({len(batch)} courses)...')

            course_list = '\n'.join(
                f'- {pid}: {name} ({uni}, {stream})'
                for pid, name, uni, stream in batch
            )

            prompt = f"""You are classifying Malaysian university degree programmes.

Existing field categories (use these first, add new ones only if no existing category fits):
{json.dumps(spm_fields, ensure_ascii=False)}

For each programme below, return a JSON array with one object per programme:
- "program_id": the ID exactly as given
- "field": best matching field from the list above, or a new category if none fits (in English)
- "category": the field name in Malay
- "description": 1-2 sentence description of what the programme covers (in English)

Programmes:
{course_list}

Return ONLY valid JSON array, no markdown fences."""

            try:
                response = model.generate_content(prompt)
                text = response.text.strip()
                if text.startswith('```'):
                    text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
                results = json.loads(text)

                for item in results:
                    pid = item.get('program_id', '')
                    if options['save']:
                        StpmCourse.objects.filter(program_id=pid).update(
                            field=item.get('field', ''),
                            category=item.get('category', ''),
                            description=item.get('description', ''),
                        )
                    else:
                        self.stdout.write(f"  {pid}: field={item.get('field')}")
                    updated += 1

            except Exception as e:
                self.stderr.write(f'Batch {batch_num} failed: {e}')

            if i + batch_size < len(courses):
                time.sleep(2)

        self.stdout.write(f'Done. {updated} courses {"saved" if options["save"] else "previewed"}.')
