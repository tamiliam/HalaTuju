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


def classify_course(frontend_label: str, field: str, course_name: str) -> str:
    """
    Map a course to a taxonomy key using frontend_label, field, and course name.

    Returns the taxonomy key (e.g. 'mekanikal', 'it-perisian').
    Logic ported from CourseCard.tsx getImageSlug(), then mapped to
    taxonomy keys (image_slug -> key).
    """
    f = field.lower()
    c = course_name.lower()
    fl = frontend_label.lower()

    # ── PENDIDIKAN ──
    if fl == 'pendidikan':
        return 'pendidikan'

    # ── MEKANIKAL & PEMBUATAN / MEKANIKAL & AUTOMOTIF ──
    if fl in ('mekanikal & pembuatan', 'mekanikal & automotif'):
        if match_any(f, ['automotif', 'kenderaan', 'motosikal']):
            return 'automotif'
        if match_any(f, ['mekatronik']) or match_any(c, ['mekatronik']):
            return 'mekatronik'
        if match_any(f, ['minyak', 'gas', 'petrokimia']):
            return 'minyak-gas'
        return 'mekanikal'

    # ── ELEKTRIK & ELEKTRONIK ──
    if fl == 'elektrik & elektronik':
        return 'elektrik'

    # ── TEKNOLOGI MAKLUMAT ──
    if fl == 'teknologi maklumat':
        if match_any(c, ['networking', 'security', 'data', 'rangkaian']):
            return 'it-rangkaian'
        return 'it-perisian'

    # ── KOMPUTER, IT & MULTIMEDIA ──
    if fl == 'komputer, it & multimedia':
        if match_any(f, ['ict', 'multimedia']):
            return 'multimedia'
        if match_any(c, ['networking', 'security', 'data', 'rangkaian']):
            return 'it-rangkaian'
        if match_any(f, ['animasi', 'teknologi kreatif digital']):
            return 'multimedia'
        return 'it-perisian'

    # ── ICT & MULTIMEDIA ──
    if fl == 'ict & multimedia':
        return 'multimedia'

    # ── AERO & MARIN / AERO, MARIN, MINYAK & GAS ──
    if fl in ('aero & marin', 'aero, marin, minyak & gas'):
        if match_any(f, ['minyak', 'gas', 'petrokimia']):
            return 'minyak-gas'
        if match_any(c, ['penerbangan', 'pesawat', 'aviation']) or match_any(f, ['aero', 'penerbangan', 'pesawat']):
            return 'aero'
        if match_any(f, ['marin', 'perkapalan', 'kapal']) or match_any(c, ['marin', 'kapal', 'perkapalan']):
            return 'marin'
        return 'aero'

    # ── HOSPITALITI & GAYA HIDUP / HOSPITALITI, KULINARI & PELANCONGAN ──
    if fl in ('hospitaliti & gaya hidup', 'hospitaliti, kulinari & pelancongan'):
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

    # ── PERNIAGAAN & PERDAGANGAN ──
    if fl == 'perniagaan & perdagangan':
        if match_any(f, ['perakaunan', 'kewangan', 'insurans']):
            return 'perakaunan'
        if match_any(f, ['pengurusan', 'logistik', 'peruncitan', 'retail']):
            return 'pengurusan'
        return 'perniagaan'

    # ── PERTANIAN & BIO-INDUSTRI ──
    if fl == 'pertanian & bio-industri':
        if match_any(f, ['alam sekitar']):
            return 'alam-sekitar'
        return 'pertanian'

    # ── SIVIL, SENI BINA & PEMBINAAN ──
    if fl == 'sivil, seni bina & pembinaan':
        if 'senibina kapal' in f:
            return 'marin'
        if match_any(f, ['seni bina', 'senibina', 'architectural', 'landskap', 'hortikultur', 'rekabentuk dalaman', 'perancangan bandar', 'geomatik']):
            return 'senibina'
        return 'sivil'

    # ── SENI REKA & KREATIF ──
    if fl == 'seni reka & kreatif':
        if match_any(f, ['animasi', '3d animation', 'games art', 'teknologi kreatif digital', 'multimedia']):
            return 'multimedia'
        return 'senireka'

    # ── SAINS & TEKNOLOGI ──
    if fl == 'sains & teknologi':
        if match_any(f, ['sains sosial']):
            return 'sains-sosial'
        return 'sains-hayat'

    # ── PERAKAUNAN & KEWANGAN ──
    if fl == 'perakaunan & kewangan':
        return 'perakaunan'

    # ── SAINS SOSIAL ──
    if fl == 'sains sosial':
        return 'sains-sosial'

    # ── KEJURUTERAAN / KEJURUTERAAN & PEMBUATAN ──
    if fl in ('kejuruteraan', 'kejuruteraan & pembuatan'):
        return 'mekanikal'

    # ── FIELD KEYWORD MATCHING ──

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

    # Oil & Gas
    if match_any(f, ['minyak', 'gas']):
        return 'minyak-gas'

    # Hospitality cluster
    if match_any(f, ['hospitaliti', 'hotel', 'pelancongan', 'resort', 'pengurusan acara', 'pengendalian acara', 'recreational tourism']):
        return 'hospitaliti'
    if match_any(f, ['kulinari', 'culinary', 'patisserie', 'pastri', 'food', 'makanan', 'seni kulinari']):
        return 'kulinari'
    if match_any(f, ['dandanan', 'kecantikan', 'terapi', 'spa', 'kecergasan']):
        return 'kecantikan'

    # Business cluster
    if match_any(f, ['perniagaan', 'keusahawanan', 'pemasaran', 'e-commerce', 'pengoperasian']):
        return 'perniagaan'
    if match_any(f, ['perakaunan', 'kewangan', 'insurans']):
        return 'perakaunan'
    if match_any(f, ['pengurusan', 'logistik', 'peruncitan', 'retail']):
        return 'pengurusan'

    # Agriculture & Agro
    if match_any(f, ['pertanian', 'agroteknologi', 'akuakultur', 'kesihatan haiwan', 'bioteknologi', 'teknologi pertanian']):
        return 'pertanian'

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
    if match_any(f, ['bahasa', 'pengajian islam', 'sains sosial', 'kesetiausahaan']):
        return 'umum'

    # ── UMUM catch-all ──
    if fl == 'umum' or f == 'umum':
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

    return 'umum'


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
            key = classify_course(
                course.frontend_label,
                course.field,
                course.course,
            )

            if key not in valid_keys:
                unmapped.append((course.course_id, course.frontend_label, course.field, key))
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
                self.stderr.write(f"  {cid}: frontend_label={fl}, field={field} → {key}")
