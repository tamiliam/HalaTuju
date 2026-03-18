"""
Management command to enrich StpmCourse with RIASEC type, difficulty level,
and efficacy domain. Also populates FieldTaxonomy.riasec_primary.

Deterministic classification based on field_key mappings from the design doc
(Section 10: RIASEC → FieldTaxonomy Mapping).

Usage:
    python manage.py enrich_stpm_riasec          # Dry run
    python manage.py enrich_stpm_riasec --apply   # Apply changes
"""
from django.core.management.base import BaseCommand
from apps.courses.models import StpmCourse, FieldTaxonomy


# --- field_key → RIASEC type (inverted from design doc Section 10) ---
# When a field_key maps to multiple RIASEC types, the primary type listed
# first in the design doc is used.
FIELD_KEY_TO_RIASEC = {
    # R (Realistic)
    'mekanikal': 'R',
    'automotif': 'R',
    'mekatronik': 'R',
    'elektrik': 'R',
    'sivil': 'R',
    'senibina': 'R',     # Also A — but primary use is R (construction)
    'pertanian': 'R',
    'alam-sekitar': 'R',
    'aero': 'R',
    'marin': 'R',
    'minyak-gas': 'R',
    'kimia-proses': 'R',

    # I (Investigative)
    'perubatan': 'I',
    'farmasi': 'I',
    'sains-hayat': 'I',
    'sains-tulen': 'I',
    'bioteknologi': 'I',
    'it-perisian': 'I',
    'it-rangkaian': 'I',

    # A (Artistic)
    'senireka': 'A',
    'multimedia': 'A',
    'fesyen': 'A',

    # S (Social)
    'pendidikan': 'S',
    'kaunseling': 'S',
    'sains-sukan': 'S',
    'pengajian-islam': 'S',

    # E (Enterprising)
    'perniagaan': 'E',
    'pengurusan': 'E',
    'pemasaran': 'E',
    'undang-undang': 'E',

    # C (Conventional)
    'perakaunan': 'C',
    'kewangan': 'C',
    'pentadbiran': 'C',
    'sains-aktuari': 'C',

    # Mixed / edge cases
    'hospitaliti': 'E',
    'kulinari': 'R',
    'kecantikan': 'A',
}


# --- field_key → difficulty level ---
# Based on known dropout rates and programme demands.
FIELD_KEY_TO_DIFFICULTY = {
    # High: regulated professions, heavy STEM, competitive entry
    'perubatan': 'high',
    'farmasi': 'high',
    'undang-undang': 'high',
    'sains-aktuari': 'high',
    'aero': 'high',
    'mekanikal': 'high',
    'elektrik': 'high',
    'sivil': 'high',
    'mekatronik': 'high',
    'kimia-proses': 'high',
    'marin': 'high',
    'minyak-gas': 'high',
    'sains-tulen': 'high',
    'bioteknologi': 'high',
    'it-perisian': 'moderate',
    'it-rangkaian': 'moderate',

    # Moderate: structured programmes, moderate rigour
    'senibina': 'moderate',
    'pertanian': 'moderate',
    'alam-sekitar': 'moderate',
    'sains-hayat': 'moderate',
    'perakaunan': 'moderate',
    'kewangan': 'moderate',
    'sains-sukan': 'moderate',
    'pendidikan': 'moderate',
    'pengajian-islam': 'moderate',
    'pentadbiran': 'moderate',

    # Low: less technical, broader entry
    'perniagaan': 'low',
    'pengurusan': 'low',
    'pemasaran': 'low',
    'kaunseling': 'low',
    'senireka': 'low',
    'multimedia': 'low',
    'fesyen': 'low',
    'hospitaliti': 'low',
    'kulinari': 'low',
    'kecantikan': 'low',
    'automotif': 'moderate',
}


# --- field_key → efficacy domain ---
FIELD_KEY_TO_EFFICACY = {
    # Quantitative: heavy maths/stats
    'mekanikal': 'quantitative',
    'elektrik': 'quantitative',
    'sivil': 'quantitative',
    'mekatronik': 'quantitative',
    'aero': 'quantitative',
    'marin': 'quantitative',
    'minyak-gas': 'quantitative',
    'kimia-proses': 'quantitative',
    'sains-tulen': 'quantitative',
    'sains-aktuari': 'quantitative',
    'it-perisian': 'quantitative',
    'it-rangkaian': 'quantitative',
    'perakaunan': 'quantitative',
    'kewangan': 'quantitative',

    # Scientific: lab/research/clinical
    'perubatan': 'scientific',
    'farmasi': 'scientific',
    'sains-hayat': 'scientific',
    'bioteknologi': 'scientific',
    'pertanian': 'scientific',
    'alam-sekitar': 'scientific',
    'sains-sukan': 'scientific',

    # Verbal: reading/writing/argumentation
    'undang-undang': 'verbal',
    'pendidikan': 'verbal',
    'kaunseling': 'verbal',
    'pengajian-islam': 'verbal',
    'pentadbiran': 'verbal',
    'perniagaan': 'verbal',
    'pengurusan': 'verbal',
    'pemasaran': 'verbal',

    # Practical: hands-on/creative output
    'senibina': 'practical',
    'senireka': 'practical',
    'multimedia': 'practical',
    'fesyen': 'practical',
    'hospitaliti': 'practical',
    'kulinari': 'practical',
    'kecantikan': 'practical',
    'automotif': 'practical',
}


# --- FieldTaxonomy key → riasec_primary ---
# Same as FIELD_KEY_TO_RIASEC — used for FieldTaxonomy backfill.
FIELD_TAXONOMY_RIASEC = FIELD_KEY_TO_RIASEC


class Command(BaseCommand):
    help = 'Enrich StpmCourse with RIASEC type, difficulty, efficacy domain'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Apply changes (default is dry run)',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        # --- Part 1: Enrich StpmCourse ---
        courses = StpmCourse.objects.all()
        updated = 0
        unmapped_riasec = set()
        unmapped_difficulty = set()
        unmapped_efficacy = set()

        for course in courses:
            fk = course.field_key_id
            changed = False

            riasec = FIELD_KEY_TO_RIASEC.get(fk)
            difficulty = FIELD_KEY_TO_DIFFICULTY.get(fk)
            efficacy = FIELD_KEY_TO_EFFICACY.get(fk)

            if riasec and course.riasec_type != riasec:
                course.riasec_type = riasec
                changed = True
            elif not riasec:
                unmapped_riasec.add(fk)

            if difficulty and course.difficulty_level != difficulty:
                course.difficulty_level = difficulty
                changed = True
            elif not difficulty:
                unmapped_difficulty.add(fk)

            if efficacy and course.efficacy_domain != efficacy:
                course.efficacy_domain = efficacy
                changed = True
            elif not efficacy:
                unmapped_efficacy.add(fk)

            if changed:
                if apply:
                    course.save(update_fields=[
                        'riasec_type', 'difficulty_level', 'efficacy_domain',
                    ])
                updated += 1

        self.stdout.write(f"\nStpmCourse: {updated}/{courses.count()} would be updated")

        if unmapped_riasec:
            self.stdout.write(self.style.WARNING(
                f"  Unmapped RIASEC field_keys: {sorted(unmapped_riasec)}"
            ))
        if unmapped_difficulty:
            self.stdout.write(self.style.WARNING(
                f"  Unmapped difficulty field_keys: {sorted(unmapped_difficulty)}"
            ))
        if unmapped_efficacy:
            self.stdout.write(self.style.WARNING(
                f"  Unmapped efficacy field_keys: {sorted(unmapped_efficacy)}"
            ))

        # --- Part 2: Enrich FieldTaxonomy ---
        taxonomies = FieldTaxonomy.objects.all()
        tax_updated = 0

        for tax in taxonomies:
            riasec = FIELD_TAXONOMY_RIASEC.get(tax.key)
            if riasec and tax.riasec_primary != riasec:
                tax.riasec_primary = riasec
                if apply:
                    tax.save(update_fields=['riasec_primary'])
                tax_updated += 1
            elif not riasec and not tax.parent_key_id:
                # Only warn about leaf nodes without parent (top-level groups)
                self.stdout.write(self.style.WARNING(
                    f"  FieldTaxonomy '{tax.key}' has no RIASEC mapping"
                ))

        self.stdout.write(f"FieldTaxonomy: {tax_updated}/{taxonomies.count()} would be updated")

        if apply:
            self.stdout.write(self.style.SUCCESS(
                f"\nApplied: {updated} courses + {tax_updated} taxonomy entries updated"
            ))
        else:
            self.stdout.write(self.style.NOTICE(
                "\nDry run — use --apply to save changes"
            ))
