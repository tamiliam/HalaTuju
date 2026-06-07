"""
Check 2 — deterministic per-pathway funding-need ESTIMATE for a B40 student.

Pre-college students can't reliably self-report what they'll need, so we estimate the
realistic monthly + one-off **gap a scholarship would fill, AFTER the government's own
coverage**, keyed on the student's pathway. The student's funding checkboxes stay a
*signal*; this estimate is the baseline for award sizing + the officer cockpit.

Figures (RM ranges) are owner-validated and live in
``docs/scholarship/funding-estimate-basis.md`` — keep the two in sync. Pure + no LLM.
"""
from __future__ import annotations

# pathway value (chosen_pathway / intended_pathway / pathways_considered) → category.
_PATHWAY_MAP = {
    'matric': 'matrik', 'matrik': 'matrik', 'matrikulasi': 'matrik',
    'asasi': 'asasi', 'foundation': 'asasi',
    'stpm': 'stpm',
    'poly': 'poly_diploma', 'politeknik': 'poly_diploma', 'diploma': 'poly_diploma',
    'kkom': 'poly_diploma', 'kolej_komuniti': 'poly_diploma',
    'iljtm': 'poly_diploma', 'ilkbs': 'poly_diploma', 'tvet': 'poly_diploma',
    'pismp': 'pismp', 'ipg': 'pismp',
    'university': 'degree', 'degree': 'degree',
}

# category → estimate. Amounts are (low, high) RM. 'monthly' recurs; 'one_off' is one-time.
# 'review' flags categories whose estimate is too variable to trust without an officer.
PATHWAY_ESTIMATES = {
    'matrik': {
        'monthly': {'meals_personal': (100, 150)},
        'one_off': {'device': (1800, 2500), 'registration': (546, 599)},
        'covered': ['hostel', 'teaching', 'BSHP living allowance (~RM1,250/sem)'],
        'review': False,
    },
    'asasi': {
        'monthly': {'meals': (150, 250), 'transport': (0, 50)},
        'one_off': {'device': (1800, 2500), 'registration_tuition': (0, 1000)},
        'covered': ['hostel (usually)', 'heavy tuition subsidy', 'allowance (some programmes)'],
        'review': False,
    },
    'stpm': {
        'monthly': {'transport': (100, 300), 'tuition': (200, 400), 'books': (25, 50)},
        'one_off': {'device': (1800, 2500)},
        'covered': ['school fees', 'STPM exam fees'],
        'review': False,
    },
    'poly_diploma': {
        'monthly': {'meals': (150, 300), 'misc': (20, 50)},
        'one_off': {'device': (1800, 2500), 'registration': (600, 900)},
        'covered': ['low tuition (~RM200/sem)', 'hostel (cheap, provided)'],
        'review': False,
    },
    'pismp': {
        'monthly': {'top_up': (50, 150)},
        'one_off': {'device': (1800, 2500)},
        'covered': ['IPG allowance', 'hostel'],
        'review': False,
    },
    'degree': {
        'monthly': {'living': (300, 600)},
        'one_off': {'device': (1800, 2500)},
        'covered': ['varies (PTPTN / faculty)'],
        'review': True,   # too variable to trust without an officer
    },
}

_DEFAULT_MONTHS = 12  # when programme length is unknown, annualise on 12 months


def _norm(value) -> str:
    return (value or '').strip().lower()


def classify_pathway(application) -> str:
    """The student's pathway category, or 'unknown'. Priority: a SURE chosen_pathway,
    then intended_pathway, then a single pathways_considered entry."""
    if _norm(getattr(application, 'pathway_certainty', '')) == 'sure':
        cat = _PATHWAY_MAP.get(_norm(application.chosen_pathway))
        if cat:
            return cat
    # chosen_pathway even without the 'sure' flag (older rows), then intended_pathway.
    for raw in (getattr(application, 'chosen_pathway', ''), getattr(application, 'intended_pathway', '')):
        cat = _PATHWAY_MAP.get(_norm(raw))
        if cat:
            return cat
    considered = application.pathways_considered
    if isinstance(considered, list) and len(considered) == 1:
        cat = _PATHWAY_MAP.get(_norm(considered[0]))
        if cat:
            return cat
    return 'unknown'


def _programme_months(application) -> int | None:
    fn = getattr(application, 'funding_need', None)
    months = getattr(fn, 'programme_months', None) if fn else None
    return months if months else None


def _sum_range(d: dict) -> tuple[int, int]:
    lo = sum(v[0] for v in d.values())
    hi = sum(v[1] for v in d.values())
    return lo, hi


def estimate_funding(application) -> dict:
    """The funding-need estimate for an application. Returns a dict with the pathway,
    whether it's known/estimatable, the monthly + one-off breakdowns and totals (RM
    low–high), and the programme-length total for award sizing. For an unknown pathway,
    ``known=False`` and no figures — fall back to the student's self-report."""
    pathway = classify_pathway(application)
    spec = PATHWAY_ESTIMATES.get(pathway)
    if spec is None:
        return {'pathway': pathway, 'known': False, 'review': False,
                'monthly': {}, 'monthly_total': (0, 0),
                'one_off': {}, 'one_off_total': (0, 0),
                'programme_months': _programme_months(application),
                'total': (0, 0), 'covered': []}

    monthly, one_off = spec['monthly'], spec['one_off']
    m_lo, m_hi = _sum_range(monthly)
    o_lo, o_hi = _sum_range(one_off)
    months = _programme_months(application)
    span = months or _DEFAULT_MONTHS
    total = (m_lo * span + o_lo, m_hi * span + o_hi)
    return {
        'pathway': pathway,
        'known': True,
        'review': spec['review'],
        'monthly': {k: list(v) for k, v in monthly.items()},
        'monthly_total': (m_lo, m_hi),
        'one_off': {k: list(v) for k, v in one_off.items()},
        'one_off_total': (o_lo, o_hi),
        'programme_months': months,
        'total': total,
        'covered': spec['covered'],
    }
