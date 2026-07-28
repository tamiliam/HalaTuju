"""What a programme asks its applicants for — the ONE place that question is answered.

Layer 0 of the configuration roadmap (`docs/plans/2026-07-28-configuration-layers-roadmap.md`).

**Status.** Sprint 2 landed this module inert (nothing called it), Sprint 3a moved the backend
DOCUMENT gates onto it, and Sprint 3b put the resolved document sets on the application payload
so the front end renders what it is told. Questions (Sprint 4) still resolve here but no gate
reads them yet. The staging was deliberate: landing the seam and the switchover together would
mean the sprint that introduces the abstraction is also the sprint that changes behaviour, with
nothing to diff against.

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

from django.db.models import OuterRef, Subquery

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
PLATFORM_OPTIONAL_DOCUMENTS = ('water_bill', 'electricity_bill', 'statement_of_intent', 'photo',
                               # Sprint 3b: rendered by the student Documents tab since long
                               # before Layer 0, and missing from every list that claimed to
                               # describe it. See the seed command for the full account.
                               'school_leaving_cert')
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


def resolve(application, kind: str) -> dict[str, str]:
    """`{code: state}` for every active catalogue item of `kind`, for this application.

    The single entry point. `state` is one of 'off' | 'optional' | 'required'.

    **ONE query, and memoised per application instance.** `application_completeness` calls this,
    and the serializers call THAT once per row — so a careless implementation becomes an N+1 the
    moment Sprint 3 wires it in. The catalogue and the programme's overrides are fetched together
    by a correlated subquery rather than two round trips, and the result is cached on the instance
    for the life of the request.

    The memo is per INSTANCE, deliberately, rather than per programme in a module-level dict. A
    process-wide cache would go stale the moment an org_admin changed a setting on another Cloud
    Run instance, and a wrong answer about what an application requires is far worse than a query.
    """
    memo = getattr(application, '_requirements_memo', None)
    if memo is not None and kind in memo:
        return memo[kind]

    programme = _programme_of(application)
    if programme is None:
        out = _platform_defaults(kind)
    else:
        # ⚠⚠ AN EMPTY CATALOGUE MEANS "NOT CONFIGURED", NEVER "ASKS FOR NOTHING".
        #
        # This guard exists because its absence was nearly shipped. Every one of the 143 live
        # applications carries a programme, and production's catalogue tables were still empty
        # (seeding was deferred to a later sprint on the grounds that nothing read them). Without
        # this line the resolved set came back {} for every one of them, `documents_done` became
        # `set().issubset(present)` — vacuously true — and all 60 students inside the submission
        # gate could have submitted with no documents at all.
        #
        # The full 5018-test suite passed throughout, because no fixture seeds the catalogue: the
        # tests never exercised the dependency they were supposedly covering. Green meant nothing.
        #
        # So: the catalogue is only believed when it has something to say. Falling back costs a
        # cheap COUNT; getting it wrong opens every gate in the system silently.
        if not ApplicationItem.objects.filter(kind=kind, is_active=True).exists():
            return _memoise(application, kind, _platform_defaults(kind))
        chosen = (ProgrammeApplicationItem.objects
                  .filter(item_id=OuterRef('pk'), programme_id=programme.pk)
                  .values('state')[:1])
        items = (ApplicationItem.objects
                 .filter(kind=kind, is_active=True)
                 .annotate(chosen=Subquery(chosen)))
        out = {}
        for item in items:
            if item.chosen is not None:
                # ⚠ A core item cannot be switched off even by an explicit row. The UI refuses it
                # and the API will refuse it, but the FLOOR belongs here too — a row written by a
                # migration, a fixture or a future bulk edit passes through neither.
                out[item.code] = 'required' if (item.is_core and item.chosen == 'off') else item.chosen
            elif item.is_core:
                out[item.code] = 'required'
            else:
                out[item.code] = item.default_state

    return _memoise(application, kind, out)


def _memoise(application, kind: str, out: dict[str, str]) -> dict[str, str]:
    """Cache on the instance for the life of the request; never fail because caching failed."""
    try:
        memo = getattr(application, '_requirements_memo', None)
        if memo is None:
            memo = {}
            application._requirements_memo = memo
        memo[kind] = out
    except AttributeError:
        pass  # a frozen/slotted stub — correctness does not depend on the memo
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


def payload_for(application, kind: str) -> dict[str, list[str]]:
    """The resolved sets, shaped for a serializer: `{'required': [...], 'optional': [...]}`.

    **The front end is sent VALUES, never the rule that produced them** — `docs/lessons.md`
    (2026-07-22): *"before mirroring a rule across the language boundary, ask what the other side
    actually needs — usually a VALUE."* The web app used to carry its own `COMPULSORY_DOC_TYPES`,
    and it disagreed with this module in production: it said `['ic', 'results_slip']` while the
    submission gate required an offer letter and the income route as well. Two descriptions of one
    rule, drifted. This function exists so there is one description.

    Sorted, so a payload diff means a real change rather than a dict-ordering artefact.

    Only `kind='document'` has a caller today (Sprint 3b). Sprint 4 adds the questions block to
    the serializer; this function needs nothing for that, which is why it takes `kind` rather than
    hard-coding one.
    """
    resolved = resolve(application, kind)
    return {
        'required': sorted(c for c, s in resolved.items() if s == 'required'),
        'optional': sorted(c for c, s in resolved.items() if s == 'optional'),
    }
