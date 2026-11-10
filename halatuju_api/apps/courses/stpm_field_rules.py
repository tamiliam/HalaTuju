"""Name and category rules for classifying an STPM course (split out of classify_stpm_fields, A3.10).

Each rule returns a taxonomy key, or None when it has no answer, and the caller tries them in order.
"""
from apps.courses.management.commands.backfill_spm_field_key import match_any


def _by_course_name(n: str):
    """Course name trumps MOHE category."""
    # ── COURSE NAME OVERRIDES (name trumps MOHE category) ──
    # Kejuruteraan Kimia misclassified under wrong category
    if 'kejuruteraan kimia' in n and 'bioteknologi' not in n and 'makanan' not in n:
        return 'kimia-proses'
    # Veterinary is a medical doctorate, not agriculture
    if 'veterinar' in n:
        return 'perubatan'
    # Pergigian by name
    if 'pergigian' in n:
        return 'pergigian'
    # Farmasi by name
    if 'farmasi' in n or 'farmaseutikal' in n:
        return 'farmasi'
    # Allied health by name → kejururawatan
    if match_any(n, ['kejururawatan', 'fisioterapi', 'optometri', 'audiologi',
                      'dietetik', 'terapi carakerja', 'pemulihan cara kerja',
                      'pengimejan perubatan', 'pengimejan diagnostik',
                      'sinaran perubatan', 'teknologi makmal perubatan']):
        return 'kejururawatan'
    # Nutrition / food science by name → kulinari
    if match_any(n, ['pemakanan', 'sains makanan', 'teknologi makanan',
                      'jaminan makanan', 'makanan halal']):
        return 'kulinari'
    # Ukur Bahan (Quantity Surveying) → sivil
    if 'ukur bahan' in n:
        return 'sivil'
    # Komunikasi by name
    if match_any(n, ['komunikasi massa', 'komunikasi sosial',
                      'pembangunan kandungan', 'periklanan',
                      'kewartawanan', 'perhubungan awam']):
        return 'komunikasi'
    return None


def _by_category_health_to_languages(c: str, n: str):
    """Environment, health, pharmacy, law, Islamic, social, chemistry, languages, humanities."""
    # ── Environment (before health, to catch compound categories) ──
    if match_any(c, ['alam sekitar', 'teknologi persekitaran',
                      'teknologi alam sekitar']):
        return 'alam-sekitar'

    # ── Health & Medical (split into perubatan / kejururawatan / pergigian) ──
    # Pergigian
    if 'pergigian' in c:
        return 'pergigian'
    # Allied health → kejururawatan
    allied_health = [
        'kejururawatan', 'fisioterapi', 'optometri', 'audiologi',
        'dietetik', 'patologi', 'pengimejan', 'pemulihan cara kerja',
        'teknologi makmal perubatan',
    ]
    if match_any(c, allied_health):
        return 'kejururawatan'
    # Nutrition / food science → kulinari (NOT kejururawatan)
    if match_any(c, ['nutrisi', 'pemakanan', 'sains pemakanan']):
        return 'kulinari'
    # Occupational health → sains-sosial (not clinical medicine)
    if 'kesihatan pekerjaan' in c:
        return 'sains-sosial'
    # Remaining medical
    if match_any(c, ['perubatan', 'kesihatan', 'bioperubatan', 'biomolekul',
                      'sains perubatan']):
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

    # ── Bahasa & Kesusasteraan ──
    bahasa_cats = [
        'bahasa', 'linguistik', 'kesusasteraan', 'persuratan',
        'pengajian melayu', 'pengajian cina', 'pengajian india',
    ]
    if match_any(c, bahasa_cats):
        return 'bahasa'

    # ── Sains Sosial: history, heritage, area studies ──
    if match_any(c, ['sejarah', 'tamadun', 'warisan', 'pengajian asia',
                      'kemanusiaan', 'geografi']):
        # But Islamic humanities → pengajian-islam
        if match_any(n, ['islam', 'syariah', 'dakwah']):
            return 'pengajian-islam'
        return 'sains-sosial'

    # ── Komunikasi & Media ──
    if match_any(c, ['komunikasi', 'media']):
        return 'komunikasi'
    return None


def _by_category_sciences_to_business(c: str, n: str):
    """Data, maths, physics, life science, economics, management, engineering, arts, business."""
    # ── Sains Data: statistics, actuarial, data science ──
    if match_any(c, ['statistik', 'sains aktuari', 'sains data', 'analitik']):
        return 'sains-data'

    # ── Mathematics ──
    if 'matematik' in c:
        if 'kewangan' in c:
            return 'perakaunan'
        return 'sains-fizikal'

    # ── Physics ──
    if 'fizik' in c:
        if 'perubatan' in c:
            return 'perubatan'
        return 'sains-fizikal'

    # ── Geosciences & Materials ──
    if match_any(c, ['geologi', 'geosains', 'sains bumi', 'sains bahan']):
        return 'sains-fizikal'

    # ── Biology & Life Sciences ──
    if match_any(c, ['biologi', 'bioteknologi', 'bio-teknologi',
                      'mikrobiologi', 'biokimia', 'sains gunaan',
                      'sains kognitif', 'sains forensik']):
        return 'sains-hayat'

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
    if match_any(c, ['maritim', 'marin', 'sains laut']):
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
    if match_any(c, ['perikanan', 'akuakultur', 'pengurusan taman']):
        return 'pertanian'
    if 'biodiversiti' in c:
        return 'alam-sekitar'

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
    return None
