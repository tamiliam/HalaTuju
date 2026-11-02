"""Which exam YEAR is the expected one for each results document of an application — route-aware.

Owner rule, approved 2026-11-01 (decisions.md). The cohort year is C. The route is the results the
student HOLDS (`results_route.held` — the one route source; nothing here re-derives it):

    route (held)                      expected — anything else is amber ('off')
    none / SPM only                   SPM C−1
    STPM                              STPM C−1; SPM C−3
    Matriculation                     Matriculation C; SPM C−2
    Asasi (as matriculation)          Asasi C; SPM C−2
    Diploma (polytechnic / diploma)   Diploma C−1 or C; SPM C−4

An unknown route keeps the rule this replaced (SPM C−1). A document kind the route lists no year for
gets no colour at all ('' — "we cannot say"), never amber.

DISPLAY ONLY. `exam_year_status` is read by the cockpit's year chips (the Documents drawer and the
Academic card's merit line) and by nothing that decides, queries or pays: the Check-2 "exam year
unknown" question reads `exam_year` (is there a year?), never its status.
"""

#: The route → {document kind: years before the cohort year that are expected}. 0 = the cohort year.
_EXPECTED = {
    'spm': {'spm': (1,)},
    'stpm': {'stpm': (1,), 'spm': (3,)},
    'matric': {'matric': (0,), 'spm': (2,)},
    'asasi': {'asasi': (0,), 'spm': (2,)},
    'diploma': {'diploma': (1, 0), 'spm': (4,)},
}


def expected_years(application) -> dict:
    """``{document kind: {year strings}}`` expected for this application, or ``{}`` with no cohort."""
    from .results_route import held
    cohort = getattr(getattr(application, 'cohort', None), 'year', None)
    if not cohort:
        return {}
    route = held(application) if application is not None else ''
    rows = _EXPECTED.get(route or 'spm', _EXPECTED['spm'])     # unknown route → the old SPM C−1 rule
    return {kind: {str(cohort - back) for back in backs} for kind, backs in rows.items()}


def year_status(application, kind, year) -> str:
    """``'current'`` when ``year`` is an expected year for a ``kind`` document of this application,
    ``'off'`` when the route expects another year, ``''`` when there is no year, no cohort, or the
    route names no year for that kind."""
    year = str(year or '').strip()
    if not year:
        return ''
    expected = expected_years(application).get(kind)
    if not expected:
        return ''
    return 'current' if year in expected else 'off'
