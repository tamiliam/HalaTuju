"""
Management command to load CSV data into Django database.

Usage:
    python manage.py load_csv_data

This command loads data from the Streamlit version's CSVs into the Django models:
- courses.csv → Course
- requirements.csv + tvet_requirements.csv + university_requirements.csv → CourseRequirement
- institutions.csv → Institution
- links.csv → CourseInstitution
- course_tags.json → CourseTag
"""
import os
import json
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.courses.models import (
    Course, CourseRequirement, CourseTag, Institution, CourseInstitution
)


class Command(BaseCommand):
    help = 'Load course data from CSV files into database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            type=str,
            default=os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'data'),
            help='Path to data directory containing CSV files'
        )

    def handle(self, *args, **options):
        data_dir = os.path.abspath(options['data_dir'])
        self.stdout.write(f'Loading data from: {data_dir}')

        with transaction.atomic():
            self.load_courses(data_dir)
            self.load_requirements(data_dir)
            self.load_institutions(data_dir)
            self.load_course_institutions(data_dir)
            self.load_course_tags(data_dir)

        self.stdout.write(self.style.SUCCESS('Data loaded successfully!'))

    def load_courses(self, data_dir):
        """Load courses.csv into Course model."""
        csv_path = os.path.join(data_dir, 'courses.csv')
        df = pd.read_csv(csv_path, dtype=str)
        df = df.fillna('')

        count = 0
        for _, row in df.iterrows():
            Course.objects.update_or_create(
                course_id=row['course_id'],
                defaults={
                    'course': row.get('course', ''),
                    'wbl': row.get('wbl', '').lower() == 'true',
                    'level': row.get('level', ''),
                    'department': row.get('department', ''),
                    'field': row.get('field', ''),
                    'frontend_label': row.get('frontend_label', ''),
                    'semesters': int(row['semesters']) if row.get('semesters') else None,
                    'description': row.get('description', ''),
                }
            )
            count += 1

        self.stdout.write(f'  Loaded {count} courses')

    def load_requirements(self, data_dir):
        """Load requirements CSVs into CourseRequirement model."""
        # Boolean fields in requirements
        bool_fields = [
            'req_malaysian', 'req_male', 'req_female', 'no_colorblind', 'no_disability',
            'pass_bm', 'pass_history', 'pass_eng', 'pass_math',
            'credit_bm', 'credit_english', 'credit_math', 'credit_addmath',
            'pass_stv', 'credit_stv', 'credit_sf', 'credit_sfmt', 'credit_bmbi',
            'pass_math_addmath', 'pass_science_tech', 'pass_math_science',
            'credit_math_sci', 'credit_math_sci_tech', '3m_only', 'single',
            'credit_bm_b', 'credit_eng_b', 'credit_math_b', 'credit_addmath_b',
            'distinction_bm', 'distinction_eng', 'distinction_math', 'distinction_addmath',
            'distinction_phy', 'distinction_chem', 'distinction_bio', 'distinction_sci',
            'pass_sci', 'credit_sci', 'credit_science_group', 'credit_math_or_addmath',
            'pass_islam', 'credit_islam', 'pass_moral', 'credit_moral',
            'req_interview',
        ]

        # Field mapping for 3m_only
        field_map = {'3m_only': 'three_m_only'}

        files = [
            ('requirements.csv', 'poly'),
            ('tvet_requirements.csv', 'tvet'),
            ('university_requirements.csv', 'ua'),
            ('pismp_requirements.csv', 'pismp'),
        ]

        total = 0
        for filename, source_type in files:
            csv_path = os.path.join(data_dir, filename)
            if not os.path.exists(csv_path):
                self.stdout.write(f'  Skipping {filename} (not found)')
                continue

            df = pd.read_csv(csv_path, dtype=str)
            df = df.fillna('')

            count = 0
            for _, row in df.iterrows():
                course_id = row.get('course_id')
                if not course_id:
                    continue

                # Check if course exists
                try:
                    course = Course.objects.get(course_id=course_id)
                except Course.DoesNotExist:
                    # Create minimal course if not exists
                    course = Course.objects.create(
                        course_id=course_id,
                        course=row.get('course', course_id),
                    )

                defaults = {'source_type': source_type}

                # Integer fields
                for field in ['min_credits', 'min_pass', 'max_aggregate_units']:
                    if row.get(field):
                        try:
                            defaults[field] = int(row[field])
                        except (ValueError, TypeError):
                            pass

                # Float fields
                if row.get('merit_cutoff'):
                    try:
                        defaults['merit_cutoff'] = float(row['merit_cutoff'])
                    except (ValueError, TypeError):
                        pass

                # Boolean fields
                for field in bool_fields:
                    model_field = field_map.get(field, field)
                    if field in row:
                        val = str(row[field]).lower()
                        defaults[model_field] = val in ('true', '1', 'yes', 't')

                # JSON fields
                for json_field in ['subject_group_req', 'complex_requirements']:
                    if row.get(json_field):
                        try:
                            defaults[json_field] = json.loads(row[json_field])
                        except (json.JSONDecodeError, TypeError):
                            pass

                # Text fields
                if row.get('remarks'):
                    defaults['remarks'] = row['remarks']

                CourseRequirement.objects.update_or_create(
                    course=course,
                    defaults=defaults
                )
                count += 1

            self.stdout.write(f'  Loaded {count} requirements from {filename}')
            total += count

        self.stdout.write(f'  Total requirements: {total}')

    def load_institutions(self, data_dir):
        """Load institutions.csv into Institution model."""
        csv_path = os.path.join(data_dir, 'institutions.csv')
        if not os.path.exists(csv_path):
            self.stdout.write('  Skipping institutions.csv (not found)')
            return

        df = pd.read_csv(csv_path, dtype=str)
        df = df.fillna('')

        count = 0
        for _, row in df.iterrows():
            inst_id = row.get('institution_id')
            if not inst_id:
                continue

            defaults = {
                'institution_name': row.get('institution_name', ''),
                'acronym': row.get('acronym', ''),
                'type': row.get('type', ''),
                'category': row.get('category', ''),
                'subcategory': row.get('subcategory', ''),
                'state': row.get('state', ''),
                'address': row.get('address', ''),
                'phone': row.get('phone', ''),
                'url': row.get('url', ''),
                'dun': row.get('dun', ''),
                'parliament': row.get('parliament', ''),
            }

            # Float fields
            for field in ['latitude', 'longitude', 'indian_population', 'indian_percentage', 'average_income']:
                col = 'lat' if field == 'latitude' else ('lng' if field == 'longitude' else field)
                if row.get(col):
                    try:
                        defaults[field] = float(row[col])
                    except (ValueError, TypeError):
                        pass

            Institution.objects.update_or_create(
                institution_id=inst_id,
                defaults=defaults
            )
            count += 1

        self.stdout.write(f'  Loaded {count} institutions')

    def load_course_institutions(self, data_dir):
        """Load links.csv into CourseInstitution model."""
        csv_path = os.path.join(data_dir, 'links.csv')
        if not os.path.exists(csv_path):
            self.stdout.write('  Skipping links.csv (not found)')
            return

        df = pd.read_csv(csv_path, dtype=str)
        df = df.fillna('')

        count = 0
        for _, row in df.iterrows():
            course_id = row.get('course_id')
            inst_id = row.get('institution_id')

            if not course_id or not inst_id:
                continue

            try:
                course = Course.objects.get(course_id=course_id)
                institution = Institution.objects.get(institution_id=inst_id)
            except (Course.DoesNotExist, Institution.DoesNotExist):
                continue

            CourseInstitution.objects.update_or_create(
                course=course,
                institution=institution,
                defaults={
                    'hyperlink': row.get('hyperlink', ''),
                }
            )
            count += 1

        self.stdout.write(f'  Loaded {count} course-institution links')

    def load_course_tags(self, data_dir):
        """Load course_tags.json into CourseTag model."""
        json_path = os.path.join(data_dir, 'course_tags.json')
        if not os.path.exists(json_path):
            self.stdout.write('  Skipping course_tags.json (not found)')
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            tags_data = json.load(f)

        count = 0
        # Handle both list format and dict format
        if isinstance(tags_data, list):
            # List of objects with course_id field
            for item in tags_data:
                course_id = item.get('course_id')
                tags = item.get('tags', item)  # tags might be nested or at root

                if not course_id:
                    continue

                try:
                    course = Course.objects.get(course_id=course_id)
                except Course.DoesNotExist:
                    continue

                CourseTag.objects.update_or_create(
                    course=course,
                    defaults={
                        'work_modality': tags.get('work_modality', ''),
                        'people_interaction': tags.get('people_interaction', ''),
                        'cognitive_type': tags.get('cognitive_type', ''),
                        'learning_style': tags.get('learning_style', []),
                        'load': tags.get('load', ''),
                        'outcome': tags.get('outcome', ''),
                        'environment': tags.get('environment', ''),
                        'credential_status': tags.get('credential_status', 'unregulated'),
                        'creative_output': tags.get('creative_output', 'none'),
                        'service_orientation': tags.get('service_orientation', 'neutral'),
                        'interaction_type': tags.get('interaction_type', 'mixed'),
                        'career_structure': tags.get('career_structure', 'volatile'),
                    }
                )
                count += 1
        else:
            # Dict format: course_id -> tags
            for course_id, tags in tags_data.items():
                try:
                    course = Course.objects.get(course_id=course_id)
                except Course.DoesNotExist:
                    continue

                CourseTag.objects.update_or_create(
                    course=course,
                    defaults={
                        'work_modality': tags.get('work_modality', ''),
                        'people_interaction': tags.get('people_interaction', ''),
                        'cognitive_type': tags.get('cognitive_type', ''),
                        'learning_style': tags.get('learning_style', []),
                        'load': tags.get('load', ''),
                        'outcome': tags.get('outcome', ''),
                        'environment': tags.get('environment', ''),
                        'credential_status': tags.get('credential_status', 'unregulated'),
                        'creative_output': tags.get('creative_output', 'none'),
                        'service_orientation': tags.get('service_orientation', 'neutral'),
                        'interaction_type': tags.get('interaction_type', 'mixed'),
                        'career_structure': tags.get('career_structure', 'volatile'),
                    }
                )
                count += 1

        self.stdout.write(f'  Loaded {count} course tags')
