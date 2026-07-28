"""What a programme asks its applicants for — the ONE place that question is answered.

Layer 0 of the configuration roadmap (`docs/plans/2026-07-28-configuration-layers-roadmap.md`).

⚠ **THIS SPRINT IS DELIBERATELY INERT.** Nothing calls these functions to make a decision yet.
The literals they will eventually replace are still in `services.py`, untouched, and the proof
that this seam is correct is `test_requirements.py` asserting the two agree — plus the entire
existing test suite passing UNMODIFIED. Sprint 3 (documents) and Sprint 4 (questions) move the
gates over one at a time. Landing the seam and the switchover together would mean the sprint
that introduces the abstraction is also the sprint that changes behaviour, with nothing to diff
against.

**The seam rule, from the branding extraction that did this well in July:** this module is the
only place the catalogue tables are read for a decision. No per-call-site queries. When Sprint 3
rewires `application_completeness`, it asks here — it does not learn to query
`ProgrammeApplicationItem` itself.

**Resolution order**, and why a missing row is not the same as `off`:

    an explicit ProgrammeApplicationItem row  →  its state
    no row, item is core                      →  'required'   (a floor an org cannot lower)
    no row                                    →  the item's default_on
    no programme at all                       →  PLATFORM_DEFAULTS

The last line matters more than it looks. An application can reach here with no programme —
legacy rows predating the programme layer, and test fixtures built without one. Returning "asks
for nothing" would silently unblock every gate for exactly those applications, which is the
worst possible failure: it looks like everything passing. So an unresolvable programme falls
back to today's behaviour, not to an empty set.
"""
from __future__ import annotations

from .models import ApplicationItem, ProgrammeApplicationItem

# ── The one exception to "a document code names a real DOC_TYPE" ─────────────
#
# `income_proof` is a SWITCH OVER AN ENGINE, not a document type. Household income is proved by
# a route — STR or salary — with per-member evidence, resolved by `services.income_doc_blockers`,
# and the documents it may involve are several (`str`, `salary_slip`, `epf`, `income_support_doc`,
# per-member `ic`). Modelling those individually would let an organisation take the route engine
# apart one document at a time, which breaks "engine logic stays programme-agnostic" and is
# precisely where BrightPath would get broken. So the catalogue offers ONE item covering the whole
# route: on, and the engine runs exactly as today; off, and it does not run at all.
#
# `test_requirements.py` asserts every other document code IS a real `ApplicantDocument.DOC_TYPES`
# value, so this set is the complete list of aggregates and cannot grow silently.
DOCUMENT_AGGREGATES = frozenset({'income_proof'})

# ── The floor, when there is no programme to ask ─────────────────────────────
#
# These mirror what `services.py` hard-codes TODAY for BrightPath. They are not a second source
# of truth to be maintained: `test_requirements.py` asserts them against the live literals, so
# the two cannot drift without a test failing. They exist so that an application with no
# programme keeps behaving exactly as it does now.
PLATFORM_REQUIRED_DOCUMENTS = ('ic', 'results_slip', 'offer_letter', 'income_proof')
PLATFORM_OPTIONAL_DOCUMENTS = ('water_bill', 'electricity_bill', 'statement_of_intent', 'photo')
PLATFORM_REQUIRED_QUESTIONS = (
    'aspirations', 'plans', 'daily_life', 'fears',
    'family_roster', 'funding', 'address',
    # `consent_done` in `application_completeness`. Omitted from the first draft of this tuple and
    # caught by the test comparing this fallback against the seeded catalogue — the two describe
    # the same thing and must not be written independently. Kept because a legacy application with
    # no programme must still be gated on consent, which is a legal requirement rather than a
    # programme preference.
    'consent',
)
PLATFORM_OPTIONAL_QUESTIONS = ('justification', 'anything_else')


def _programme_of(application):
    """The programme an application belongs to, or None.

    Read defensively: `programme` is denormalised onto the application and set once in `save()`,
    but legacy rows predate the column. `getattr` rather than a bare attribute so a caller may
    pass a lightweight stub — which the gates in `services.py` are full of.
    """
    if application is None:
        return None
    return getattr(application, 'programme', None)


def _selected(programme) -> dict[tuple[str, str], str]:
    """Every explicit selection this programme has made, keyed by (kind, code).

    One query. The gates that will call this run per-application inside list endpoints, so a
    per-item query here would become an N+1 the moment Sprint 3 wires it in.
    """
    if programme is None:
        return {}
    rows = (ProgrammeApplicationItem.objects
            .filter(programme_id=programme.pk)
            .select_related('item'))
    return {(r.item.kind, r.item.code): r.state for r in rows}


def _catalogue(kind: str) -> list[ApplicationItem]:
    return list(ApplicationItem.objects.filter(kind=kind, is_active=True))


def resolve(application, kind: str) -> dict[str, str]:
    """`{code: state}` for every active catalogue item of `kind`, for this application.

    The single entry point. `state` is one of 'off' | 'optional' | 'required'.
    """
    programme = _programme_of(application)
    if programme is None:
        return _platform_defaults(kind)

    selected = _selected(programme)
    out: dict[str, str] = {}
    for item in _catalogue(kind):
        explicit = selected.get((kind, item.code))
        if explicit is not None:
            # ⚠ A core item cannot be switched off even by an explicit row. The UI refuses it and
            # the API will refuse it, but the FLOOR belongs here too — a row written by a
            # migration, a fixture or a future bulk edit never passes through either of those.
            out[item.code] = 'required' if (item.is_core and explicit == 'off') else explicit
        elif item.is_core:
            out[item.code] = 'required'
        else:
            out[item.code] = item.default_state
    return out


def _platform_defaults(kind: str) -> dict[str, str]:
    if kind == 'document':
        req, opt = PLATFORM_REQUIRED_DOCUMENTS, PLATFORM_OPTIONAL_DOCUMENTS
    else:
        req, opt = PLATFORM_REQUIRED_QUESTIONS, PLATFORM_OPTIONAL_QUESTIONS
    return {**{c: 'required' for c in req}, **{c: 'optional' for c in opt}}


def required_documents(application) -> set[str]:
    """Document codes this application MUST provide."""
    return {c for c, s in resolve(application, 'document').items() if s == 'required'}


def optional_documents(application) -> set[str]:
    """Document codes offered but never blocking."""
    return {c for c, s in resolve(application, 'document').items() if s == 'optional'}


def required_questions(application) -> set[str]:
    return {c for c, s in resolve(application, 'question').items() if s == 'required'}


def optional_questions(application) -> set[str]:
    return {c for c, s in resolve(application, 'question').items() if s == 'optional'}


def asks_for(application, kind: str, code: str) -> bool:
    """Does this programme ask for `code` at all (required OR optional)?

    The question Sprint 3's gates need most: a document that is not asked for must not be
    chased, must not appear as outstanding, and must not produce a verdict fact.
    """
    return resolve(application, kind).get(code, 'off') != 'off'
