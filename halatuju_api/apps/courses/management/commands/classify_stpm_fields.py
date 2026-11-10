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
from apps.courses.stpm_field_rules import (
    _by_category_health_to_languages, _by_category_sciences_to_business, _by_course_name,
)

# English → Malay normalization for STPM field values.
# After Sprint 5 removed the category column, the field column holds
# mixed-language values. This map normalizes English values so the
# Malay-based classifier rules can match them.
ENGLISH_FIELD_MAP = {
    # Sciences
    'mathematics': 'matematik',
    'mathematics & statistics': 'matematik & statistik',
    'management mathematics': 'matematik',
    'mathematical modelling and analytics': 'matematik',
    'financial mathematics': 'matematik kewangan',
    'statistics': 'statistik',
    'data analytics': 'analitik data',
    'data analytics statistics': 'statistik',
    'data science': 'sains data',
    'physics': 'fizik',
    'physics & instrumentation': 'fizik',
    'nanophysics': 'fizik',
    'medical physics': 'fizik perubatan',
    'chemistry': 'kimia',
    'chemical sciences': 'kimia',
    'forensic chemistry': 'kimia forensik',
    'analytical & environmental chemistry': 'kimia',
    'biology': 'biologi',
    'biological sciences': 'biologi',
    'marine biology': 'biologi marin',
    'applied microbiology': 'mikrobiologi',
    'cognitive science': 'sains kognitif',
    'bio-technology': 'bioteknologi',
    'biomedical science': 'bioperubatan',
    'biomolecular science': 'biomolekul',
    'forensic science': 'sains forensik',
    'geology': 'geologi',
    'geoscience': 'geosains',
    'geosciences': 'geosains',
    'earth sciences': 'sains bumi',
    'material science': 'sains bahan',
    'material science & technology': 'sains bahan',
    'actuarial science': 'sains aktuari',
    # Engineering
    'chemical engineering': 'kejuruteraan kimia',
    'nuclear engineering': 'kejuruteraan nuklear',
    'biomedical engineering': 'kejuruteraan bioperubatan',
    'manufacturing engineering': 'kejuruteraan pembuatan',
    'manufacturing': 'pembuatan',
    'material engineering': 'kejuruteraan bahan',
    'materials engineering': 'kejuruteraan bahan',
    'material & polymer engineering': 'kejuruteraan polimer',
    'mining & mineral resources engineering': 'kejuruteraan perlombongan',
    'mineral technology': 'teknologi mineral',
    'bio-process engineering technology': 'bio-proses',
    'environmental engineering': 'kejuruteraan alam sekitar',
    'energy technology': 'teknologi tenaga',
    'renewable energy technology': 'teknologi tenaga',
    'food processing engineering': 'teknologi makanan',
    # Health
    'medicine': 'perubatan',
    'medicine & surgery': 'perubatan',
    'medical science': 'perubatan',
    'nursing': 'kejururawatan',
    'dentistry': 'pergigian',
    'pharmacy': 'farmasi',
    'medical imaging': 'pengimejan perubatan',
    'physiotherapy': 'fisioterapi',
    'optometry': 'optometri',
    'audiology': 'audiologi',
    'dietetics': 'dietetik',
    'nutrition & dietetics': 'pemakanan',
    'nutrition science': 'pemakanan',
    'healthcare': 'kesihatan',
    'healthcare technology': 'kesihatan',
    'health sciences': 'kesihatan',
    'health and fitness': 'sains sukan',
    'speech pathology': 'patologi pertuturan',
    'occupational safety & health': 'kesihatan pekerjaan',
    'occupational safety and health': 'kesihatan pekerjaan',
    'environmental health & safety': 'kesihatan pekerjaan',
    'environmental science & occupational health': 'sains alam sekitar',
    # Social Sciences
    'social sciences': 'sains kemasyarakatan',
    'social science': 'sains kemasyarakatan',
    'psychology': 'psikologi',
    'sociology & anthropology': 'sosiologi',
    'political science': 'sains politik',
    'political science & security studies': 'sains politik',
    'counselling': 'kaunseling',
    'social work': 'kerja sosial',
    'criminology': 'kriminologi',
    'development studies': 'kajian pembangunan',
    'history': 'sejarah',
    'history & civilization': 'sejarah',
    'geography': 'geografi',
    'heritage studies': 'warisan',
    'humanities': 'kemanusiaan',
    'sports science': 'sains sukan',
    'sports management': 'pengurusan sukan',
    'international & strategic studies': 'pengajian antarabangsa',
    'southeast asian studies': 'pengajian asia',
    'east asian studies': 'pengajian asia',
    'industrial relations': 'hubungan industri',
    'human resources': 'sumber manusia',
    'human resource management': 'sumber manusia',
    # Law
    'law': 'undang-undang',
    # Business & Finance
    'economics': 'ekonomi',
    'finance': 'kewangan',
    'accounting': 'perakaunan',
    'real estate': 'hartanah',
    'real estate & land management': 'hartanah',
    'social entrepreneurship & community management': 'keusahawanan',
    'wellness entrepreneurship': 'keusahawanan',
    'halal industry management': 'halal',
    'business & halal industry management': 'halal',
    # Languages & Communication
    'languages & linguistics': 'bahasa & linguistik',
    'languages & communication': 'bahasa & komunikasi',
    'languages & entrepreneurship': 'bahasa & keusahawanan',
    'linguistics': 'linguistik',
    'linguistics & media': 'komunikasi & media',
    'literature': 'kesusasteraan',
    'malay literature': 'kesusasteraan melayu',
    'malay literature & culture': 'persuratan & kebudayaan',
    'malay studies': 'pengajian melayu',
    'malay language studies': 'pengajian melayu',
    'english language studies': 'bahasa inggeris',
    'chinese studies': 'pengajian cina',
    'indian studies': 'pengajian india',
    'communications': 'komunikasi',
    'communication': 'komunikasi',
    'media & communication': 'komunikasi & media',
    'media studies': 'komunikasi & media',
    # Islamic Studies
    'islamic studies': 'pengajian islam',
    'religious studies': 'pengajian agama',
    'islamic management': 'pengajian islam',
    # Environment
    'environmental science': 'sains alam sekitar',
    'environmental studies': 'sains alam sekitar',
    'environmental technology': 'teknologi alam sekitar',
    'biodiversity conservation & management': 'biodiversiti',
    'biodiversity management': 'biodiversiti',
    # Marine
    'maritime management': 'maritim',
    'maritime technology': 'maritim',
    'marine science': 'sains laut',
    'aquaculture': 'akuakultur',
    'fisheries': 'perikanan',
    # Food
    'food science': 'sains makanan',
    'food technology': 'teknologi makanan',
    'food science & technology': 'sains makanan',
    # Other
    'others': 'lain-lain',
    'performing arts': 'seni persembahan',
    'quantity surveying': 'ukur bahan',
    'industrial hygiene & safety': 'teknologi higiene',
    # Others (X) inner values
    'applied chemistry': 'kimia gunaan',
    'medical laboratory technology': 'teknologi makmal perubatan',
    'occupational therapy': 'pemulihan cara kerja',
    'park and amenity management': 'pengurusan taman',
    'polymer engineering': 'kejuruteraan polimer',
}

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
        if match_any(n, ['alam sekitar', 'sekitaran', 'persekitaran',
                          'biodiversiti', 'sains laut', 'biologi marin']):
            return 'alam-sekitar'
        if match_any(n, ['sains makanan', 'teknologi makanan', 'jaminan makanan',
                          'produk agro', 'perkhidmatan makanan']):
            return 'kulinari'
        # Pure biology/biotech without agricultural context → sains-hayat
        if match_any(n, ['biologi', 'biokimia', 'mikrobiologi', 'genetik',
                          'bioteknologi', 'bioinformatik']):
            if not match_any(n, ['pertanian', 'agro', 'tumbuhan', 'tanaman',
                                  'perladangan', 'hortikultur', 'penternakan',
                                  'ternakan', 'haiwan']):
                return 'sains-hayat'
        if 'kimia industri' in n:
            return 'kimia-proses'
        return 'pertanian'

    if c == 'sivil, seni bina & pembinaan':
        if match_any(n, ['seni bina', 'senibina', 'landskap', 'perancangan',
                          'rekabentuk dalaman']):
            return 'senibina'
        return 'sivil'

    if c == 'seni reka & kreatif':
        if match_any(n, ['animasi', 'multimedia', 'permainan', 'games',
                          'sinematografi', 'filem']):
            return 'multimedia'
        if 'sejarah' in n:
            return 'sains-sosial'
        if 'kesusasteraan' in n:
            return 'bahasa'
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


def _normalise_category(category_lower: str) -> str:
    """Normalise English field values to Malay equivalents.

    After Sprint 5 removed the category column, field holds mixed-language
    values. The "Others (X)" pattern extracts X for keyword matching.
    """
    c = category_lower
    if c.startswith('others (') and c.endswith(')'):
        inner = c[8:-1].strip()
        return ENGLISH_FIELD_MAP.get(inner.lower(), c)
    return ENGLISH_FIELD_MAP.get(c, c)


def classify_stpm_course(category: str, field: str, course_name: str) -> str:
    """
    Map an STPM course to a taxonomy key using category, field, and course name.

    Returns the taxonomy key (e.g. 'perubatan', 'kimia-proses').

    NOTE: STPM's field column is often identical to category (an aggregate
    value like "Komputer, IT & Multimedia"), unlike SPM where field is a
    specific sub-discipline. We use course_name for sub-classification.
    The rules run in a fixed order and the first that answers wins.
    """
    c = _normalise_category(category.lower())
    n = course_name.lower()

    key = _by_course_name(n)
    if key is not None:
        return key

    # ── PENDIDIKAN protection: never reclassify education degrees ──
    if c == 'pendidikan':
        return 'pendidikan'

    # ── SPM-matching categories (702/1113 courses) ──
    # Handle directly instead of delegating to classify_course(),
    # because STPM field == category (aggregate), not a specific sub-field.
    if c in SPM_MATCHING_CATEGORIES:
        return _classify_spm_matching(c, n)

    # ── Sains Sosial (direct match) ──
    if c == 'sains sosial':
        return 'sains-sosial'

    for rule in (_by_category_health_to_languages, _by_category_sciences_to_business):
        key = rule(c, n)
        if key is not None:
            return key

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
