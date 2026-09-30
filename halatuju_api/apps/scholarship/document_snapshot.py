"""ONE READ OF AN APPLICANT'S DOCUMENTS, SHARED BY THE ENGINES THAT ASK ABOUT THEM (TD-282).

**The problem this exists for.** Opening one applicant on the officer cockpit cost **315
database queries** with no documents on file and **385** with three, and 283 of the 315 were
reads of the same small table. The engines behind that screen — ``verdict_engine``, the
``income_engine`` package, ``anomaly_engine``, ``submission_review``, the blockers — each ask
*"what is the latest live STR?"*, *"is there a parent IC?"*, *"which document types are
present?"* dozens of times, and each question used to build a **fresh queryset**. That is why
``prefetch_related('documents')`` on the view's queryset did nothing: a ``.filter(...)`` on a
related manager ignores a prefetch cache (code health H18 checked before saying so).

**What this module is.** A *snapshot*: one ``SELECT`` of an application's documents, held for
the length of ONE read-only computation, that the readers below filter in Python instead of
asking the database again. It is deliberately NOT a cache — there is no expiry, no
invalidation and nothing to go stale, because it cannot outlive the ``with`` block that opened
it.

**How a helper uses it.** It calls a reader here instead of writing its own queryset. Each
reader asks whether a snapshot is open **for that application's id**; if one is, it answers
from the rows in memory, and if not it runs exactly the query the helper ran before. So every
caller that is NOT inside a snapshot — the submission gate, Check 2, the management commands,
the student's own payload, every test — behaves precisely as it did, unchanged.

**Where it is opened — THE ONE PLACE.** ``views_admin/applications.py``,
``AdminApplicationDetailView.get``, around the serializer build. Nothing else opens one today.
Read **"Widening it safely"** below before adding a second.

⚠ **NO WRITE PATH MAY OPEN OR READ A SNAPSHOT.** The rows are a photograph taken when the
block opened; a function that writes a document and then reads one back must see its own
write. That is why the scope is explicit and narrow rather than a request-wide middleware, and
``test_document_snapshot.py`` holds the test that proves a write is visible to a read taken
outside the block.

**Why a ContextVar and not a module global.** Django serves requests on threads (and may serve
them on coroutines). A module-level dict would be shared between two officers opening two
applicants at the same instant, and the second read would answer with the first's documents.
A :mod:`contextvars` variable is per-thread AND per-task, and ``reset(token)`` in a ``finally``
restores whatever was there before, so nesting is safe too.

**Why the snapshot is keyed on the application id.** A snapshot answers for exactly one
applicant. A helper handed a *different* application while a block is open falls straight
through to its query — see ``test_a_second_application_is_never_served_from_the_first``. This
matters because several engines walk from a document back to ``doc.application``.

── ORDERING, AND THE ONE THING TO KNOW ABOUT IT ────────────────────────────────────────────

Every one of these reads is ``ORDER BY uploaded_at DESC, id DESC`` — ``SNAPSHOT_ORDER`` below,
the ONE home of that clause: ``ApplicantDocument.Meta.ordering`` is built from it and every
explicit document ``.order_by(...)`` in the codebase unpacks it (``test_document_order`` scans
for a site that does not). The snapshot is loaded with that same clause ONCE, and every reader
below filters the loaded list **without re-sorting it**, so a subset keeps the order the
database gave — an in-memory answer is identical to the query's, by construction, ties included.

⚠ **"LATEST" = NEWEST ``uploaded_at``, THEN HIGHEST ``id``** (TD-292, 2026-09-30; decisions.md).
Until then the clause had no tie-breaker, so with two documents sharing an ``uploaded_at`` the
row the database picked was arbitrary — PostgreSQL may even change its mind after an unrelated
``UPDATE`` moves a row in the heap — and the snapshot's one unfiltered read could choose a
different row than a helper's own filtered query (the adversarial review of 2026-09-21). ``id``
is the auto-increment key, so the tie goes to the row written LAST, which is what every helper
means by "latest". It changes which document is chosen only on an exact tie, so it bumped
``VERDICT_ENGINE_VERSION``; production held 1,356 documents and ZERO such ties when it shipped
(the lead's read-only count, 2026-09-21 and again 2026-09-30), so no band moved.

── WIDENING IT SAFELY ──────────────────────────────────────────────────────────────────────

1. The computation you wrap must be **read-only with respect to ``applicant_documents``**. If
   it writes a document, do not wrap it.
2. Wrap at the **outermost** point of that computation, so every helper underneath shares one
   snapshot rather than opening several.
3. Add the surface to the ON==OFF matrix in ``test_document_snapshot.py`` before you ship it.
   That test is the whole safety argument: it asserts the endpoint's JSON is **byte-identical**
   with the snapshot on and off, across a matrix of document shapes. A widening that is not in
   the matrix is not proven.
4. Lower the query budget in ``code-standards.json`` afterwards. The budget is the instrument
   that notices if the saving is later undone.
"""
import contextlib
import contextvars

#: ``(application_id, rows)`` while a snapshot is open, else ``None``. Per-thread and per-task,
#: so two concurrent requests can never see each other's rows.
_ACTIVE: contextvars.ContextVar = contextvars.ContextVar(
    'applicant_document_snapshot', default=None)

#: The clause every document read in this codebase uses, written ONCE: newest ``uploaded_at``,
#: then highest ``id`` (TD-292). Unpack it — ``.order_by(*SNAPSHOT_ORDER)``; ``Meta.ordering``
#: and every explicit site read it from here, so an in-memory answer can never differ from a query.
SNAPSHOT_ORDER = ('-uploaded_at', '-id')

#: Sentinel for "this reader does not filter on ``household_member`` at all", distinct from the
#: real tag value ``''`` (an untagged, household-level document), which IS a filter.
ANY_MEMBER = object()


class DocRows(list):
    """A plain list of documents with the two queryset verbs its callers already use.

    ``_cluster_docs`` and friends hand back a queryset, and their callers say ``.first()`` and
    ``.exists()`` as well as iterating and calling ``list()``. Returning a list subclass that
    answers those two keeps every call site unchanged, which is what makes this refactor
    reviewable — and it is deliberately only two verbs. This is not a queryset and must never
    grow into one: a reader that needs a third verb wants a function in this module, not a
    method here.

    ⚠ **THIS IS RETURNED ONLY WHEN A SNAPSHOT IS OPEN.** With no snapshot the readers below
    return the QUERYSET they always returned — lazily, in the same shape, built by one
    ``.filter(**kwargs)`` call — so nothing about the un-snapshotted path changes, down to the
    stand-in objects some engine tests pass in place of a related manager.
    """

    def first(self):
        return self[0] if self else None

    def exists(self) -> bool:
        return bool(self)


def _manager(application):
    """The related manager, or ``None`` for a test double that has no documents at all.

    Several engines are written to tolerate a stand-in object; they check this themselves and
    return their own answer for it, so the readers below simply answer empty.
    """
    return getattr(application, 'documents', None)


def _identity(application):
    """``(concrete model, pk)`` — what a snapshot is keyed on — or ``None`` for anything that is
    not a saved model instance.

    ⚠ THE MODEL IS PART OF THE KEY, NOT JUST THE PK. The first version keyed on ``pk`` alone, and
    the adversarial review of 2026-09-21 proved the hole with a probe: ANY object whose ``pk``
    happened to equal the applicant's — a different model, or a stand-in with no ``documents``
    attribute at all — was served that applicant's documents. No reader is called with such an
    object today; the "Widening it safely" steps in CLAUDE.md are exactly where one would be.
    """
    meta = getattr(application, '_meta', None)
    model = getattr(meta, 'concrete_model', None)
    pk = getattr(application, 'pk', None)
    if model is None or pk is None:
        return None
    return (model, pk)


def _rows(application):
    """The snapshot's rows if one is open FOR THIS APPLICATION, else ``None``.

    ``None`` is the signal to fall through to the database, and it is returned for anything
    that is not the very application the snapshot was opened for — same model AND same pk —
    so a reader can never be handed another applicant's documents, or another model's.
    """
    active = _ACTIVE.get()
    if active is None:
        return None
    key, rows = active
    identity = _identity(application)
    if identity is None or identity != key:
        return None
    return rows


def is_open_for(application) -> bool:
    """Whether a snapshot is currently serving *application*. For tests and for a helper that
    wants to say in a log line which path it took; no engine needs to ask."""
    return _rows(application) is not None


@contextlib.contextmanager
def document_snapshot(application):
    """Read this application's documents once and serve every reader below from that read.

    Read-only computations only — see the module docstring. Nesting is safe: the previous value
    is restored by ``reset`` in the ``finally``, so an inner block for a different application
    does not leak out of itself, and an outer block resumes intact.
    """
    manager = _manager(application)
    key = _identity(application)
    if manager is None or key is None:
        # Nothing to snapshot (a test double, or an unsaved application). Every reader then
        # takes its ordinary path, which is exactly today's behaviour.
        yield
        return
    # ⚠ THE LOAD IS UNFILTERED — superseded rows included — and every reader below applies
    # `superseded_at IS NULL` itself. Filtering here instead would move that rule out of the
    # readers and into the load, so a future reader wanting version history would silently be
    # handed a list that cannot contain it. One query either way.
    rows = list(manager.all().order_by(*SNAPSHOT_ORDER))
    token = _ACTIVE.set((key, rows))
    try:
        yield
    finally:
        _ACTIVE.reset(token)


# ── the readers ─────────────────────────────────────────────────────────────────────────────
# Each one is the same shape: answer from the snapshot's rows if there is one, else run the
# query the caller used to run. The in-memory branch filters WITHOUT re-sorting, so it keeps
# the order the load's ORDER BY gave it.

def _live(rows):
    return [d for d in rows if getattr(d, 'superseded_at', None) is None]


def _filter_kwargs(doc_type, doc_types, member, members):
    """The ORM keyword arguments for one ``.filter()`` call — never a chain of them.

    A chain (`.filter(a).filter(b)`) produces the same rows, but several engine tests pass a
    stand-in whose ``documents.filter(**kw)`` returns a fixed object with no ``.filter`` of its
    own. Building the kwargs first and calling ``.filter`` ONCE is what keeps those doubles
    working, and it is the same single call each helper made before TD-282.
    """
    kwargs = {'superseded_at__isnull': True}
    if doc_type is not None:
        kwargs['doc_type'] = doc_type
    if doc_types is not None:
        kwargs['doc_type__in'] = doc_types
    if member is not ANY_MEMBER:
        kwargs['household_member'] = member
    if members is not None:
        kwargs['household_member__in'] = members
    return kwargs


def live_docs(application, doc_type=None, *, doc_types=None, member=ANY_MEMBER, members=None):
    """The LIVE (not superseded) documents matching the filter, latest first.

    * ``doc_type`` / ``doc_types`` — one type, or a tuple of them. Give neither for every type.
    * ``member`` — an exact ``household_member`` value (``''`` is a real value: untagged).
    * ``members`` — a list of acceptable ``household_member`` values (the ``__in`` form the
      income cluster uses to accept a member's own tag OR a legacy blank).

    ``member`` and ``members`` are alternatives; passing both is a programming error.

    Returns a ``DocRows`` under a snapshot and the ordinary lazy queryset otherwise.
    """
    if member is not ANY_MEMBER and members is not None:
        raise TypeError('live_docs takes member OR members, not both')
    rows = _rows(application)
    if rows is not None:
        out = _live(rows)
        if doc_type is not None:
            out = [d for d in out if d.doc_type == doc_type]
        if doc_types is not None:
            out = [d for d in out if d.doc_type in doc_types]
        if member is not ANY_MEMBER:
            out = [d for d in out if (d.household_member or '') == member]
        if members is not None:
            allowed = set(members)
            out = [d for d in out if (d.household_member or '') in allowed]
        return DocRows(out)
    manager = _manager(application)
    if manager is None:
        return DocRows()
    return manager.filter(
        **_filter_kwargs(doc_type, doc_types, member, members)).order_by(*SNAPSHOT_ORDER)


def latest_doc(application, doc_type, *, member=ANY_MEMBER, members=None):
    """The latest LIVE document of *doc_type*, or ``None``.

    The single most-called read in the codebase: ``_latest_doc`` in ``verdict_engine`` and in
    ``income_engine.utilities`` both delegate here, as do a dozen one-off copies of the same
    three lines. "Latest" is ``SNAPSHOT_ORDER``: newest ``uploaded_at``, and on an exact tie the
    highest ``id`` (TD-292).
    """
    return live_docs(application, doc_type, member=member, members=members).first()


def has_live_doc(application, doc_type) -> bool:
    """Whether any LIVE document of *doc_type* is on file (the ``.exists()`` form)."""
    return live_docs(application, doc_type).exists()


def present_doc_types(application) -> set:
    """The set of doc types with at least one LIVE document — the completeness reads' question."""
    rows = _rows(application)
    if rows is not None:
        return {d.doc_type for d in _live(rows)}
    manager = _manager(application)
    if manager is None:
        return set()
    return set(manager.filter(superseded_at__isnull=True)
               .values_list('doc_type', flat=True))


# (``tagged_members`` below is the only reader with an ``.exclude()`` in its query form.)


def tagged_members(application, doc_types) -> list:
    """The ``household_member`` tags carried by LIVE documents of *doc_types*, blanks excluded.

    The ``.exclude(household_member='').values_list('household_member', flat=True)`` form, which
    two callers use to ask *"which people did the student actually upload documents for?"*. The
    result is a list and may repeat, exactly as the ``values_list`` did — both callers put it
    through a ``set``.
    """
    rows = _rows(application)
    if rows is not None:
        return [d.household_member for d in _live(rows)
                if d.doc_type in doc_types and (d.household_member or '') != '']
    manager = _manager(application)
    if manager is None:
        return []
    return list(manager.filter(doc_type__in=doc_types, superseded_at__isnull=True)
                .exclude(household_member='')
                .values_list('household_member', flat=True))
