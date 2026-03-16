"""
Classify STPM courses into field_key taxonomy keys.

Uses deterministic mapping from category + field + course_name
to one of 37 taxonomy keys. Category is the primary signal (cleaner
than field for STPM), with field and course_name as fallbacks.

The top 10 STPM categories (702/1113 courses) match SPM production
frontend_labels exactly and are delegated to classify_course().

Usage:
    python manage.py classify_stpm_fields          # dry-run
    python manage.py classify_stpm_fields --save    # persist to DB
"""
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.courses.models import StpmCourse, FieldTaxonomy
from apps.courses.management.commands.backfill_spm_field_key import (
    classify_course, match_any,
)

# Categories that match SPM production frontend_labels exactly.
# These are delegated to the SPM classify_course() function.
SPM_MATCHING_CATEGORIES = {
    'perniagaan & perdagangan',
    'komputer, it & multimedia',
    'pendidikan',
    'pertanian & bio-industri',
    'seni reka & kreatif',
    'sivil, seni bina & pembinaan',
    'elektrik & elektronik',
    'mekanikal & automotif',
    'aero, marin, minyak & gas',
    'hospitaliti, kulinari & pelancongan',
}


def _classify_spm_matching(category_lower: str, name_lower: str) -> str:
    """
    Classify STPM courses whose category matches an SPM frontend_label.

    Uses course_name for sub-classification since STPM field == category
    (aggregate value, not specific sub-discipline).
    """
    c = category_lower
    n = name_lower

    if c == 'pendidikan':
        return 'pendidikan'

    if c == 'elektrik & elektronik':
        return 'elektrik'

    if c == 'mekanikal & automotif':
        if match_any(n, ['automotif', 'kenderaan']):
            return 'automotif'
        if 'mekatronik' in n:
            return 'mekatronik'
        return 'mekanikal'

    if c == 'komputer, it & multimedia':
        if match_any(n, ['rangkaian', 'networking', 'keselamatan komputer',
                          'security', 'pangkalan data', 'data']):
            return 'it-rangkaian'
        if match_any(n, ['multimedia', 'animasi', 'permainan digital',
                          'media interaktif', 'games']):
            return 'multimedia'
        return 'it-perisian'

    if c == 'perniagaan & perdagangan':
        if match_any(n, ['perakaunan', 'kewangan', 'insurans', 'aktuari']):
            return 'perakaunan'
        if match_any(n, ['pengurusan', 'logistik']):
            return 'pengurusan'
        return 'perniagaan'

    if c == 'pertanian & bio-industri':
        if 'alam sekitar' in n:
            return 'alam-sekitar'
        return 'pertanian'

    if c == 'sivil, seni bina & pembinaan':
        if match_any(n, ['seni bina', 'senibina', 'landskap', 'perancangan',
                          'rekabentuk dalaman']):
            return 'senibina'
        return 'sivil'

    if c == 'seni reka & kreatif':
        if match_any(n, ['animasi', 'multimedia', 'permainan', 'games']):
            return 'multimedia'
        return 'senireka'

    if c == 'aero, marin, minyak & gas':
        if match_any(n, ['minyak', 'petro']):
            return 'minyak-gas'
        if match_any(n, ['marin', 'kapal', 'perkapalan', 'maritim']):
            return 'marin'
        return 'aero'

    if c == 'hospitaliti, kulinari & pelancongan':
        if match_any(n, ['kulinari', 'culinary', 'makanan', 'pastri',
                          'food']):
            return 'kulinari'
        if match_any(n, ['kecantikan', 'spa', 'dandanan']):
            return 'kecantikan'
        return 'hospitaliti'

    # Fallback (shouldn't reach here)
    return 'umum'


def classify_stpm_course(category: str, field: str, course_name: str) -> str:
    """
    Map an STPM course to a taxonomy key using category, field, and course name.

    Returns the taxonomy key (e.g. 'perubatan', 'kimia-proses').

    NOTE: STPM's field column is often identical to category (an aggregate
    value like "Komputer, IT & Multimedia"), unlike SPM where field is a
    specific sub-discipline. We use course_name for sub-classification.
    """
    c = category.lower()
    f = field.lower()
    n = course_name.lower()

    # ── SPM-matching categories (702/1113 courses) ──
    # Handle directly instead of delegating to classify_course(),
    # because STPM field == category (aggregate), not a specific sub-field.
    if c in SPM_MATCHING_CATEGORIES:
        return _classify_spm_matching(c, n)

    # ── Sains Sosial (direct match) ──
    if c == 'sains sosial':
        return 'sains-sosial'

    # ── Environment (before health, to catch compound categories) ──
    if match_any(c, ['alam sekitar', 'teknologi persekitaran',
                      'teknologi alam sekitar']):
        return 'alam-sekitar'

    # ── Health & Medical ──
    if match_any(c, ['perubatan', 'kejururawatan', 'pergigian', 'pengimejan',
                      'dietetik', 'nutrisi', 'optometri', 'audiologi',
                      'patologi', 'kesihatan', 'bioperubatan',
                      'pemakanan', 'fisioterapi', 'pemulihan cara kerja',
                      'teknologi makmal perubatan', 'biomolekul']):
        return 'perubatan'

    # ── Pharmacy ──
    if 'farmasi' in c:
        return 'farmasi'

    # ── Law ──
    if c == 'undang-undang':
        return 'undang-undang'

    # ── Islamic Studies ──
    if match_any(c, ['pengajian islam', 'pengajian agama',
                      'undang-undang islam', 'muamalat']):
        return 'pengajian-islam'

    # ── Social Sciences ──
    if match_any(c, ['sains kemasyarakatan', 'psikologi',
                      'sains politik', 'sosiologi', 'antropologi',
                      'kriminologi', 'kajian pembangunan', 'kerja sosial',
                      'hubungan industri', 'kaunseling', 'pengajian pengguna',
                      'pengajian antarabangsa']):
        return 'sains-sosial'

    # ── Chemical Engineering (before general chemistry) ──
    if match_any(c, ['kejuruteraan kimia', 'kejuruteraan nuklear',
                      'kejuruteraan pemprosesan', 'bio-proses']):
        return 'kimia-proses'

    # ── Chemistry ──
    if 'kimia' in c:
        return 'kimia-proses'

    # ── Language & Humanities (before Communication, to catch 'Bahasa & Komunikasi') ──
    if match_any(c, ['bahasa', 'linguistik', 'kesusasteraan', 'kemanusiaan',
                      'persuratan', 'sejarah', 'tamadun', 'warisan',
                      'pengajian melayu', 'pengajian cina', 'pengajian india',
                      'pengajian asia']):
        return 'umum'

    # ── Communication & Media ──
    if match_any(c, ['komunikasi', 'media']):
        return 'multimedia'

    # ── Mathematics & Statistics ──
    if match_any(c, ['matematik', 'statistik', 'aktuari']):
        if 'kewangan' in c:
            return 'perakaunan'
        return 'sains-hayat'

    # ── Physics ──
    if 'fizik' in c:
        if 'perubatan' in c:
            return 'perubatan'
        return 'sains-hayat'

    # ── Biology & Life Sciences ──
    if match_any(c, ['biologi', 'bioteknologi', 'bio-teknologi',
                      'mikrobiologi', 'biokimia', 'sains gunaan',
                      'sains kognitif']):
        return 'sains-hayat'

    # ── Geosciences ──
    if match_any(c, ['geologi', 'geosains', 'sains bumi']):
        return 'sains-hayat'

    # ── Materials Science ──
    if 'sains bahan' in c:
        return 'sains-hayat'

    # ── Data Science / Analytics ──
    if match_any(c, ['data', 'analitik']):
        return 'it-rangkaian'

    # ── Economics ──
    if 'ekonomi' in c:
        return 'perniagaan'

    # ── Finance & Accounting ──
    if match_any(c, ['kewangan', 'perakaunan']):
        return 'perakaunan'

    # ── Management & HR ──
    if match_any(c, ['sumber manusia', 'pengurusan sumber']):
        return 'pengurusan'
    if match_any(c, ['hartanah', 'harta tanah']):
        return 'pengurusan'

    # ── Maritime ──
    if match_any(c, ['maritim', 'marin']):
        return 'marin'

    # ── Food Science ──
    if match_any(c, ['sains makanan', 'teknologi makanan']):
        return 'kulinari'

    # ── Mechanical Engineering & Manufacturing ──
    if match_any(c, ['kejuruteraan bahan', 'kejuruteraan polimer',
                      'kejuruteraan pembuatan', 'kejuruteraan perlombongan',
                      'teknologi mineral', 'teknologi higiene', 'pembuatan']):
        return 'mekanikal'

    # ── Energy / Electrical ──
    if match_any(c, ['teknologi tenaga', 'kejuruteraan bioperubatan']):
        return 'elektrik'

    # ── Sports & Recreation ──
    if match_any(c, ['sains sukan', 'sukan', 'rekreasi',
                      'pengurusan sukan']):
        return 'sains-sosial'

    # ── Agriculture & Biodiversity ──
    if match_any(c, ['perikanan', 'akuakultur', 'biodiversiti', 'veterinar',
                      'pengurusan taman']):
        return 'pertanian'

    # ── Fashion & Design ──
    if match_any(c, ['tekstil', 'fesyen']):
        return 'senireka'

    # ── Performing Arts ──
    if 'seni persembahan' in c:
        return 'multimedia'

    # ── Oil & Gas ──
    if 'minyak' in c:
        return 'minyak-gas'

    # ── Landscape ──
    if 'landskap' in c:
        return 'senibina'

    # ── Surveying ──
    if 'ukur bahan' in c:
        return 'sivil'

    # ── Business / Entrepreneurship ──
    if match_any(c, ['halal', 'keusahawanan', 'perniagaan']):
        return 'perniagaan'

    # ── Lain-lain catch-all ──
    # "Lain-lain" (16 courses) and any unmapped "Lain-lain (X)" that
    # weren't caught by keyword matching above
    return 'umum'


class Command(BaseCommand):
    help = 'Classify STPM courses into field_key taxonomy keys'

    def add_arguments(self, parser):
        parser.add_argument(
            '--save', action='store_true',
            help='Persist changes to database (default is dry-run)',
        )

    def handle(self, *args, **options):
        db_config = settings.DATABASES['default']
        db_host = db_config.get('HOST', 'unknown')
        self.stdout.write(f"Database: {db_host}")

        if 'sqlite' in db_config.get('ENGINE', ''):
            self.stderr.write(self.style.ERROR(
                'Aborting: SQLite detected. This command targets PostgreSQL.'
            ))
            return

        save = options['save']

        valid_keys = set(FieldTaxonomy.objects.values_list('key', flat=True))
        taxonomy_map = {ft.key: ft for ft in FieldTaxonomy.objects.all()}

        courses = StpmCourse.objects.all()
        total = courses.count()
        classified = 0
        unmapped = []
        key_counts = {}

        for course in courses:
            # category column removed in Sprint 5; use field as fallback
            cat = getattr(course, 'category', course.field)
            key = classify_stpm_course(
                cat,
                course.field,
                course.course_name,
            )

            key_counts[key] = key_counts.get(key, 0) + 1

            if key not in valid_keys:
                unmapped.append((
                    course.course_id, cat,
                    course.field, key,
                ))
                continue

            classified += 1

            if save:
                course.field_key = taxonomy_map[key]
                course.save(update_fields=['field_key'])

        mode = 'SAVED' if save else 'DRY-RUN'
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] {classified}/{total} courses classified"
        ))

        # Distribution summary
        self.stdout.write("\nDistribution:")
        for key, count in sorted(key_counts.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {key}: {count}")

        if unmapped:
            self.stderr.write(self.style.WARNING(
                f"\n{len(unmapped)} courses had invalid keys:"
            ))
            for cid, cat, field, key in unmapped:
                self.stderr.write(
                    f"  {cid}: category={cat}, field={field} → {key}"
                )
