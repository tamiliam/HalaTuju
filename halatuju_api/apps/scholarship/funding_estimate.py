"""
Check 2 — deterministic per-pathway funding-need ESTIMATE for a B40 student.

Pre-college students can't reliably self-report what they'll need, so we estimate the
realistic **monthly shortfall a top-up assistance would fill, AFTER government coverage
(allowance) and any PTPTN loan**, keyed on the student's pathway, times the typical
programme length. The student's funding checkboxes stay a *signal*; this estimate is the
baseline for award sizing + the officer cockpit.

Figures (RM) are owner-validated and live in ``docs/scholarship/funding-estimate-basis.md``
— keep the two in sync. Pure + no LLM.

Post-SPM scope: students can't enter a bachelor's degree directly (the one exception,
PISMP, is a 5-year degree-level teacher-training programme and has its own category). So
the pathway "university" means a **public-university (Universiti Awam) DIPLOMA**, not a
degree. kkom / iljtm / ilkbs have a different, institution-specific cost structure and
are deliberately left un-estimated (assess at interview).
"""
from __future__ import annotations

# pathway value (chosen_pathway / intended_pathway / pathways_considered) → estimate
# category. The category IS the pathway key for the six pathways we estimate; aliases
# fold in. kkom / iljtm / ilkbs / tvet are intentionally absent → no estimate.
_PATHWAY_MAP = {
    'matric': 'matric', 'matrik': 'matric', 'matrikulasi': 'matric',
    'stpm': 'stpm',
    'asasi': 'asasi', 'foundation': 'asasi',
    'university': 'university', 'degree': 'university',  # post-SPM "university" = UA diploma
    'poly': 'poly', 'politeknik': 'poly',
    'pismp': 'pismp', 'ipg': 'pismp',
}

# category → estimate. 'monthly' = est. RM monthly SHORTFALL a top-up would fill (living
# costs − government allowance − PTPTN loan), rounded. 'months' = typical programme
# length. 'variable' = cost varies a lot by institution/field → show a caveat.
# 'practical' = has an internship/practical term that may add travel.
PATHWAY_ESTIMATES = {
    'stpm':       {'monthly': 500, 'months': 18, 'variable': False, 'practical': False},
    'matric':     {'monthly': 200, 'months': 10, 'variable': False, 'practical': False},
    'asasi':      {'monthly': 700, 'months': 10, 'variable': True,  'practical': False},
    'poly':       {'monthly': 120, 'months': 36, 'variable': False, 'practical': True},
    'university': {'monthly': 220, 'months': 30, 'variable': True,  'practical': True},
    'pismp':      {'monthly': 180, 'months': 60, 'variable': False, 'practical': True},
}

# course_id prefixes with a different, un-estimated cost structure → no estimate.
_NO_ESTIMATE_ID_PREFIXES = ('kkom', 'ijtm', 'iljtm', 'ikbn', 'iktbn', 'ilkbs', 'tvet')
# course_id prefixes that pin an estimate category.
_PROGRAMME_ID_PREFIXES = (
    ('poly', 'poly'),
    ('pismp', 'pismp'), ('ipg', 'pismp'),
)
# Ordered course_name keyword scan (first match wins). Specific pathways are checked
# before the generic 'diploma' (a non-Politeknik diploma = a public-university diploma).
_PROGRAMME_NAME_KEYWORDS = (
    ('matrikulasi', 'matric'),
    ('asasi', 'asasi'), ('foundation', 'asasi'),
    ('tingkatan enam', 'stpm'), ('stpm', 'stpm'),
    ('pismp', 'pismp'), ('perguruan', 'pismp'),
    ('politeknik', 'poly'),
    ('diploma', 'university'),
)


def _norm(value) -> str:
    return (value or '').strip().lower()


def _classify_programme(programme) -> str | None:
    """Infer the estimate category from a chosen programme (the actual course the student
    picked, e.g. auto-filled from their offer letter), or None if it can't be read or has
    an un-estimated cost structure. course_id prefix first, then a course_name scan."""
    if not isinstance(programme, dict):
        return None
    cid = _norm(programme.get('course_id'))
    if any(cid.startswith(p) for p in _NO_ESTIMATE_ID_PREFIXES):
        return None
    for prefix, cat in _PROGRAMME_ID_PREFIXES:
        if cid.startswith(prefix):
            return cat
    name = _norm(programme.get('course_name'))
    if 'kolej komuniti' in name:
        return None
    for kw, cat in _PROGRAMME_NAME_KEYWORDS:
        if kw in name:
            return cat
    return None


def classify_pathway(application) -> str:
    """The student's pathway category, or 'unknown'. Priority: a SURE chosen_pathway,
    then chosen_pathway/intended_pathway (older rows), then the chosen PROGRAMME (the
    concrete course — e.g. auto-filled from the offer letter — which pins the pathway
    type even when the pathway-type fields are blank), then a single pathways_considered
    entry."""
    if _norm(getattr(application, 'pathway_certainty', '')) == 'sure':
        cat = _PATHWAY_MAP.get(_norm(application.chosen_pathway))
        if cat:
            return cat
    # chosen_pathway even without the 'sure' flag (older rows), then intended_pathway.
    for raw in (getattr(application, 'chosen_pathway', ''), getattr(application, 'intended_pathway', '')):
        cat = _PATHWAY_MAP.get(_norm(raw))
        if cat:
            return cat
    # A concrete chosen programme beats a list of merely-considered pathways.
    cat = _classify_programme(getattr(application, 'chosen_programme', None))
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


def _round100(n) -> int:
    """Round to the nearest RM100 — these are ballpark estimates, not invoices."""
    return int(round(n / 100.0)) * 100


def estimate_funding(application) -> dict:
    """The funding-need estimate for an application: the monthly shortfall, the typical
    (or student-stated) programme length in months, and the rounded whole-programme total
    for award sizing, plus 'variable' (cost swings by institution) and 'practical' (an
    internship term may add travel) flags. For an un-estimated/unknown pathway,
    ``known=False`` and no figures — fall back to the student's self-report."""
    pathway = classify_pathway(application)
    spec = PATHWAY_ESTIMATES.get(pathway)
    if spec is None:
        return {'pathway': pathway, 'known': False, 'monthly': 0,
                'months': _programme_months(application), 'total': 0,
                'variable': False, 'practical': False}
    months = _programme_months(application) or spec['months']
    monthly = spec['monthly']
    return {
        'pathway': pathway,
        'known': True,
        'monthly': monthly,
        'months': months,
        'total': _round100(monthly * months),
        'variable': spec['variable'],
        'practical': spec['practical'],
    }
