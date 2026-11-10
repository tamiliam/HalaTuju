"""
Backfill field_key for all SPM courses.

Uses deterministic mapping from frontend_label + field + course name
to one of 37 taxonomy keys. Ported from CourseCard.tsx getImageSlug().

Usage:
    python manage.py backfill_spm_field_key          # dry-run
    python manage.py backfill_spm_field_key --save    # persist to DB
"""
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.courses.models import Course, FieldTaxonomy


def match_any(text: str, keywords: list[str]) -> bool:
    """Check if text contains any keyword (case-insensitive)."""
    return any(kw in text for kw in keywords)


def _education_and_name_overrides(f: str, c: str, fl: str):
    """Education is never reclassified; then course-name overrides (name trumps frontend_label)."""
    # ── PENDIDIKAN protection: education courses never reclassified ──
    if fl == 'pendidikan' or f == 'pendidikan':
        return 'pendidikan'

    # ── COURSE NAME OVERRIDES (name trumps frontend_label) ──
    # Kejuruteraan Kimia in wrong category
    if 'kejuruteraan kimia' in c and 'bioteknologi' not in c and 'makanan' not in c:
        return 'kimia-proses'
    # UA (UPSI) course-name overrides — must be before frontend_label checks
    if match_any(c, ['diploma muzik', 'diploma tari', 'diploma teater']):
        return 'senireka'
    if 'pendidikan awal kanak-kanak' in c:
        return 'pendidikan'
    if match_any(c, ['diploma bahasa etnik', 'diploma bahasa inggeris']):
        return 'bahasa'
    if 'turath islami' in c:
        return 'pengajian-islam'
    if 'teknologi makmal' in c and 'perubatan' not in c:
        return 'sains-hayat'
    if c == 'diploma sains':
        return 'sains-hayat'
    if 'sains (matematik)' in c:
        return 'sains-fizikal'
    if 'sains sukan' in c or 'kejurulatihan' in c:
        return 'sains-sosial'
    return None


# ── frontend_label rules: each takes (field, course_name) and ALWAYS answers ──

def _label_mekanikal(f: str, c: str) -> str:
    if match_any(f, ['automotif', 'kenderaan', 'motosikal']):
        return 'automotif'
    if match_any(f, ['mekatronik']) or match_any(c, ['mekatronik']):
        return 'mekatronik'
    if match_any(f, ['minyak', 'gas', 'petrokimia']):
        return 'minyak-gas'
    return 'mekanikal'


def _label_teknologi_maklumat(f: str, c: str) -> str:
    if match_any(c, ['networking', 'security', 'data', 'rangkaian']):
        return 'it-rangkaian'
    return 'it-perisian'


def _label_komputer(f: str, c: str) -> str:
    if match_any(f, ['ict', 'multimedia']):
        return 'multimedia'
    if match_any(c, ['networking', 'security', 'data', 'rangkaian']):
        return 'it-rangkaian'
    if match_any(f, ['animasi', 'teknologi kreatif digital']):
        return 'multimedia'
    return 'it-perisian'


def _label_aero(f: str, c: str) -> str:
    if match_any(f, ['minyak', 'gas', 'petrokimia']):
        return 'minyak-gas'
    if match_any(c, ['penerbangan', 'pesawat', 'aviation']) or match_any(f, ['aero', 'penerbangan', 'pesawat']):
        return 'aero'
    if match_any(f, ['marin', 'perkapalan', 'kapal']) or match_any(c, ['marin', 'kapal', 'perkapalan']):
        return 'marin'
    return 'aero'


def _label_hospitaliti(f: str, c: str) -> str:
    if match_any(f, ['fesyen']) or match_any(c, ['fesyen', 'pakaian', 'jahitan']):
        return 'senireka'
    if match_any(f, ['kulinari', 'culinary', 'patisserie', 'pastri', 'food', 'makanan']):
        return 'kulinari'
    if match_any(c, ['kulinari', 'culinary', 'pastri', 'patisserie', 'makanan', 'food', 'roti']):
        return 'kulinari'
    if match_any(f, ['dandanan', 'kecantikan', 'terapi', 'spa', 'kecergasan']):
        return 'kecantikan'
    if match_any(c, ['dandanan', 'kecantikan', 'terapi', 'spa', 'kosmetologi', 'rambut']):
        return 'kecantikan'
    return 'hospitaliti'


def _label_perniagaan(f: str, c: str) -> str:
    if match_any(f, ['perakaunan', 'kewangan', 'insurans']):
        return 'perakaunan'
    if match_any(f, ['pengurusan', 'logistik', 'peruncitan', 'retail']):
        return 'pengurusan'
    return 'perniagaan'


def _label_pertanian(f: str, c: str) -> str:
    if match_any(f, ['alam sekitar']):
        return 'alam-sekitar'
    return 'pertanian'


def _label_sivil(f: str, c: str) -> str:
    if 'senibina kapal' in f:
        return 'marin'
    if match_any(f, ['seni bina', 'senibina', 'architectural', 'landskap', 'hortikultur', 'rekabentuk dalaman', 'perancangan bandar', 'geomatik']):
        return 'senibina'
    return 'sivil'


def _label_seni_reka(f: str, c: str) -> str:
    if match_any(f, ['animasi', '3d animation', 'games art', 'teknologi kreatif digital', 'multimedia']):
        return 'multimedia'
    return 'senireka'


def _label_sains_teknologi(f: str, c: str) -> str:
    if match_any(f, ['sains sosial']):
        return 'sains-sosial'
    return 'sains-hayat'


def _const(key: str):
    return lambda f, c: key


_LABEL_RULES = {
    'mekanikal & pembuatan': _label_mekanikal,
    'mekanikal & automotif': _label_mekanikal,
    'elektrik & elektronik': _const('elektrik'),
    'teknologi maklumat': _label_teknologi_maklumat,
    'komputer, it & multimedia': _label_komputer,
    'ict & multimedia': _const('multimedia'),
    'aero & marin': _label_aero,
    'aero, marin, minyak & gas': _label_aero,
    'hospitaliti & gaya hidup': _label_hospitaliti,
    'hospitaliti, kulinari & pelancongan': _label_hospitaliti,
    'perniagaan & perdagangan': _label_perniagaan,
    'pertanian & bio-industri': _label_pertanian,
    'sivil, seni bina & pembinaan': _label_sivil,
    'seni reka & kreatif': _label_seni_reka,
    'sains & teknologi': _label_sains_teknologi,
    'perakaunan & kewangan': _const('perakaunan'),
    'sains sosial': _const('sains-sosial'),
    'kejuruteraan': _const('mekanikal'),
    'kejuruteraan & pembuatan': _const('mekanikal'),
}


def _by_label(f: str, c: str, fl: str):
    rule = _LABEL_RULES.get(fl)
    return rule(f, c) if rule else None


# ── FIELD KEYWORD MATCHING (first match wins, in this order) ──

def _field_engineering(f: str):
    # Automotif
    if match_any(f, ['automotif', 'kenderaan', 'motosikal']):
        return 'automotif'

    # Mekanikal sub-fields
    if match_any(f, ['kimpalan']):
        return 'mekanikal'
    if match_any(f, ['mekatronik']):
        return 'mekatronik'
    if f.startswith('kejuruteraan mekanikal'):
        if match_any(f, ['automasi']):
            return 'mekatronik'
        if match_any(f, ['automotif']):
            return 'automotif'
        if match_any(f, ['petrokimia']):
            return 'minyak-gas'
        return 'mekanikal'
    if match_any(f, ['mekanikal & pembuatan', 'kejuruteraan pembuatan', 'teknologi pembuatan', 'mechanical design']):
        return 'mekanikal'
    if match_any(f, ['penyejukan', 'penyamanan udara', 'kejuruteraan bahan', 'berasaskan kayu', 'penyenggaraan industri', 'perabot']):
        return 'mekanikal'

    # Elektrik sub-fields
    if f.startswith('kejuruteraan elektrik') or f.startswith('kejuruteraan elektronik'):
        return 'elektrik'
    if match_any(f, ['elektrik & elektronik', 'teknologi elektrik', 'solar fotovoltan']):
        return 'elektrik'
    if match_any(f, ['telekomunikasi', 'telecommunication', 'rail signalling', 'electronics instrumentation']):
        return 'elektrik'

    # IT
    if match_any(f, ['teknologi maklumat', 'kejuruteraan komputer', 'sistem maklumat', 'mobile technology', 'peranti mudah alih']):
        return 'it-perisian'
    if match_any(f, ['ict & multimedia']):
        return 'multimedia'

    # Sivil
    if match_any(f, ['sivil', 'kejuruteraan awam', 'penyeliaan tapak']):
        return 'sivil'
    if match_any(f, ['penyelenggaraan bangunan', 'perkhidmatan bangunan', 'teknologi pembinaan', 'ukur bahan']):
        return 'sivil'

    # Architecture & Landscape (but NOT 'senibina kapal')
    if 'senibina kapal' in f:
        return 'marin'
    if match_any(f, ['seni bina', 'senibina', 'architectural', 'landskap', 'hortikultur', 'rekabentuk dalaman', 'perancangan bandar', 'geomatik']):
        return 'senibina'

    # Chemical engineering
    if match_any(f, ['kejuruteraan kimia', 'teknologi kimia', 'kejuruteraan alam sekitar', 'kejuruteraan proses']):
        return 'kimia-proses'
    return None


def _field_services(f: str):
    # Fitness / Sports (before Oil & Gas — 'gas' false-matches 'kecergasan')
    if 'kecergasan' in f:
        return 'sains-sosial'

    # Oil & Gas
    if match_any(f, ['minyak', 'gas']):
        return 'minyak-gas'

    # Physiotherapy (before Hospitality — 'terapi' false-matches 'fisioterapi')
    if 'fisioterapi' in f:
        return 'perubatan'

    # Hospitality cluster
    if match_any(f, ['hospitaliti', 'hotel', 'pelancongan', 'resort', 'pengurusan acara', 'pengendalian acara', 'recreational tourism']):
        return 'hospitaliti'
    if match_any(f, ['kulinari', 'culinary', 'patisserie', 'pastri', 'food', 'makanan', 'seni kulinari']):
        return 'kulinari'
    if match_any(f, ['dandanan', 'kecantikan', 'terapi', 'spa', 'kecergasan']):
        return 'kecantikan'

    # Business cluster
    if match_any(f, ['perniagaan', 'keusahawanan', 'pemasaran', 'e-commerce', 'pengoperasian', 'kesetiausahaan']):
        return 'perniagaan'
    if match_any(f, ['perakaunan', 'kewangan', 'insurans']):
        return 'perakaunan'
    if match_any(f, ['pengurusan', 'logistik', 'peruncitan', 'retail']):
        return 'pengurusan'

    # Agriculture & Agro
    if match_any(f, ['pertanian', 'agroteknologi', 'akuakultur', 'kesihatan haiwan', 'bioteknologi', 'teknologi pertanian']):
        return 'pertanian'
    return None


def _field_sciences_and_arts(f: str):
    # Science & Health
    if match_any(f, ['perubatan', 'kesihatan', 'fisioterapi']):
        return 'perubatan'
    if match_any(f, ['sains', 'stem']):
        return 'sains-hayat'

    # Design & Fashion
    if match_any(f, ['seni reka', 'rekabentuk grafik', 'rekabentuk industri', 'fesyen', 'seni visual', 'media cetak', 'reka bentuk kraf', 'sound & lighting']):
        return 'senireka'

    # Multimedia & Animation
    if match_any(f, ['animasi', '3d animation', 'games art', 'teknologi kreatif digital', 'multimedia kreatif']):
        return 'multimedia'

    # Aero & Marine
    if match_any(f, ['aero', 'penerbangan', 'pesawat']):
        return 'aero'
    if match_any(f, ['marin', 'perkapalan', 'kapal']):
        return 'marin'

    # General Engineering
    if match_any(f, ['kejuruteraan']):
        return 'kejuruteraan-am'

    # Law & Pharmacy
    if match_any(f, ['undang-undang', 'law']):
        return 'undang-undang'
    if match_any(f, ['farmasi', 'pharmacy']):
        return 'farmasi'

    # Humanities
    if match_any(f, ['pengajian islam']):
        return 'pengajian-islam'
    if match_any(f, ['bahasa']):
        return 'bahasa'
    if match_any(f, ['sains sosial']):
        return 'sains-sosial'
    return None


def _umum_by_course_name(f: str, c: str, fl: str):
    """The 'Umum' catch-all: a generic field is read from the course name."""
    if not (fl == 'umum' or f == 'umum'):
        return None
    if match_any(c, ['perikanan', 'perhutanan', 'pertanian']):
        return 'pertanian'
    if match_any(c, ['bank', 'insurans']):
        return 'perakaunan'
    if match_any(c, ['radiografi']):
        return 'perubatan'
    if match_any(c, ['makmal']):
        return 'sains-hayat'
    if match_any(c, ['animasi', 'tari', 'teater', 'muzik']):
        return 'multimedia'
    if match_any(c, ['pembuatan']):
        return 'mekanikal'
    if match_any(c, ['rekabentuk']):
        return 'senireka'
    if match_any(c, ['kanak-kanak']):
        return 'pendidikan'
    if match_any(c, ['tahfiz']):
        return 'pengajian-islam'
    return 'umum'


def classify_course(frontend_label: str, field: str, course_name: str) -> str:
    """
    Map a course to a taxonomy key using frontend_label, field, and course name.

    Returns the taxonomy key (e.g. 'mekanikal', 'it-perisian').
    Logic ported from CourseCard.tsx getImageSlug(), then mapped to
    taxonomy keys (image_slug -> key). The rules run in a fixed order and the
    first one that answers wins: education + name overrides, then the
    frontend_label, then field keywords, then the 'Umum' catch-all.
    """
    f = field.lower()
    c = course_name.lower()
    fl = frontend_label.lower()

    for rule in (_education_and_name_overrides, _by_label):
        key = rule(f, c, fl)
        if key is not None:
            return key
    for rule in (_field_engineering, _field_services, _field_sciences_and_arts):
        key = rule(f)
        if key is not None:
            return key
    key = _umum_by_course_name(f, c, fl)
    return key if key is not None else 'umum'


class Command(BaseCommand):
    help = 'Backfill field_key for all SPM courses from frontend_label + field'

    def add_arguments(self, parser):
        parser.add_argument(
            '--save', action='store_true',
            help='Persist changes to database (default is dry-run)',
        )

    def handle(self, *args, **options):
        # Safety: print DB host
        db_config = settings.DATABASES['default']
        db_host = db_config.get('HOST', 'unknown')
        self.stdout.write(f"Database: {db_host}")

        if 'sqlite' in db_config.get('ENGINE', ''):
            self.stderr.write(self.style.ERROR('Aborting: SQLite detected. This command targets PostgreSQL.'))
            return

        save = options['save']

        # Load taxonomy keys
        valid_keys = set(FieldTaxonomy.objects.values_list('key', flat=True))
        taxonomy_map = {ft.key: ft for ft in FieldTaxonomy.objects.all()}

        courses = Course.objects.all()
        total = courses.count()
        classified = 0
        unmapped = []

        for course in courses:
            # frontend_label removed in Sprint 5; use field as fallback
            fl = getattr(course, 'frontend_label', course.field)
            key = classify_course(
                fl,
                course.field,
                course.course,
            )

            if key not in valid_keys:
                unmapped.append((course.course_id, fl, course.field, key))
                continue

            classified += 1

            if save:
                course.field_key = taxonomy_map[key]
                course.save(update_fields=['field_key'])

        mode = 'SAVED' if save else 'DRY-RUN'
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] {classified}/{total} courses classified"
        ))

        if unmapped:
            self.stderr.write(self.style.WARNING(f"{len(unmapped)} courses had invalid keys:"))
            for cid, fl, field, key in unmapped:
                self.stderr.write(f"  {cid}: field={fl}/{field} → {key}")
