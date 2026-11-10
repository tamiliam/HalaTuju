"""The tuning knobs of the ranking engine: base score, caps, the field-interest map, the merit
penalty.

Moved verbatim out of `ranking_engine.py` (audit sprint A3.6, a moves-only split), so the pre-U
scorers in `ranking_pre_u.py` can read `BASE_SCORE` without an import cycle. `ranking_engine.py`
re-exports every name, so every `from apps.courses.ranking_engine import ...` is unchanged.
Nothing here changed.
"""

# --- Constants & Tuning Knobs ---
BASE_SCORE = 100
GLOBAL_CAP = 20
INSTITUTION_CAP = 5
CATEGORY_CAP = 6  # Normalised cap per category

# Category-specific caps (override CATEGORY_CAP for these)
FIELD_INTEREST_CAP = 8
WORK_PREFERENCE_CAP = 4

# Field interest → taxonomy field_key mapping
# Maps quiz signal names to the canonical taxonomy keys they match.
# Used by both SPM and STPM ranking for field interest scoring.
FIELD_KEY_MAP = {
    'field_mechanical': ['mekanikal', 'automotif', 'mekatronik', 'kejuruteraan-am'],
    'field_digital': ['it-perisian', 'it-rangkaian', 'multimedia', 'sains-data'],
    'field_business': ['perniagaan', 'perakaunan', 'pengurusan'],
    'field_health': [
        'perubatan', 'farmasi', 'sains-hayat',
        'kejururawatan', 'pergigian',
    ],
    'field_creative': ['senireka', 'multimedia', 'komunikasi'],
    'field_hospitality': ['hospitaliti', 'kulinari', 'kecantikan'],
    'field_agriculture': ['pertanian', 'alam-sekitar', 'sains-fizikal'],
    'field_heavy_industry': [
        'mekanikal', 'automotif', 'mekatronik',
        'aero', 'marin', 'minyak-gas',
        'elektrik', 'sivil', 'senibina',
        'kimia-proses', 'kejuruteraan-am',
    ],
    'field_electrical': ['elektrik'],
    'field_civil': ['sivil', 'senibina'],
    'field_aero_marine': ['aero', 'marin'],
    'field_oil_gas': ['minyak-gas'],
}

# Merit-based ranking penalty (v1.4)
MERIT_PENALTY = {
    "High": 0,     # Meets/exceeds cutoff — no penalty
    "Fair": -5,    # Within 5 points of cutoff
    "Low": -15,    # Significantly below cutoff
}
