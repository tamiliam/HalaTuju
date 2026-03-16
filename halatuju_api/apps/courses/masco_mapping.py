"""
Deterministic mapping from field_key to MASCO 2-digit occupation groups.

Used by map_course_careers command to pre-filter the 4,854-job MASCO list
down to a relevant subset before sending to Gemini.
"""

from django.db.models import Q, QuerySet

FIELD_KEY_TO_MASCO: dict[str, list[str]] = {
    # Engineering
    'mekanikal': ['21', '31', '72', '81'],
    'elektrik': ['21', '31', '74', '81'],
    'sivil': ['21', '31', '71'],
    'kejuruteraan-am': ['21', '31', '72', '81'],
    'mekatronik': ['21', '31', '74', '81'],
    'automotif': ['21', '31', '72', '83'],
    'aero': ['21', '31', '83'],
    'marin': ['21', '31', '83'],
    'minyak-gas': ['21', '31', '81'],
    'kimia-proses': ['21', '31', '81'],
    # IT
    'it-perisian': ['25', '35'],
    'it-rangkaian': ['25', '35'],
    'multimedia': ['25', '35', '28'],
    # Health
    'perubatan': ['22', '32'],
    'farmasi': ['22', '32'],
    # Business
    'perakaunan': ['24', '33', '41'],
    'pengurusan': ['24', '33', '12'],
    'perniagaan': ['24', '33', '52'],
    # Hospitality
    'hospitaliti': ['14', '27', '51'],
    'kulinari': ['27', '51', '75'],
    'kecantikan': ['51', '27'],
    # Education
    'pendidikan': ['23'],
    # Agriculture & Environment
    'pertanian': ['21', '31', '61', '62'],
    'alam-sekitar': ['21', '31'],
    # Design & Architecture
    'senibina': ['21', '31', '71'],
    'senireka': ['28', '36', '73'],
    # Sciences
    'sains-hayat': ['21', '31'],
    # Humanities & Social
    'sains-sosial': ['24', '28', '36'],
    'undang-undang': ['26', '34'],
    'pengajian-islam': ['23', '28'],
    # General catch-all
    'umum': ['24', '33', '28'],
}


def filter_masco_by_field_key(field_key: str) -> QuerySet:
    """
    Return MascoOccupation records matching the MASCO groups for a field_key.
    Only returns specific jobs (codes with '-', i.e. 4+ digit codes).
    """
    from apps.courses.models import MascoOccupation

    groups = FIELD_KEY_TO_MASCO.get(field_key, [])
    if not groups:
        return MascoOccupation.objects.none()

    q = Q()
    for group in groups:
        q |= Q(masco_code__startswith=group)

    return MascoOccupation.objects.filter(q).filter(masco_code__contains='-')
