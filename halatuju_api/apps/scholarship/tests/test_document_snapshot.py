"""TD-282 — THE PROOF THAT THE DOCUMENT SNAPSHOT CHANGED NOTHING BUT THE COST.

**What is being proved.** ``document_snapshot`` makes the officer's applicant-detail GET read
``applicant_documents`` ONCE instead of 283 times, by having a few dozen engine helpers filter
a list in memory instead of each building its own queryset. Everything about that is a
behaviour risk: a Python filter is not an SQL filter, a stable Python sort is not an
``ORDER BY``, and a snapshot that outlives its scope is a stale read.

So the safety argument is not "the suite still passes". It is the matrix below: for a grid of
fixtures, the endpoint's **response bytes with the snapshot ON are identical to the bytes with
it OFF**. The snapshot is switched off by replacing the one context manager the view opens with
a no-op, which is exactly the pre-TD-282 code path — every helper then falls through to the
query it ran before, because each reader consults the active snapshot and finds none.

⚠ **THIS FILE IS WHAT LETS THE NEXT ENGINEER CHANGE THE SNAPSHOT.** Widen it, add a reader,
change a filter — and if any of it moves an answer, the matrix says so, per fixture, in bytes.
Do not narrow it to make a change easier. If a case here cannot be made green, the change is
wrong; that was the stop condition this work was written under.

**The axes, and why each is there.**
  * **stage** — the stage decides which engines run at all. A `submitted` case never reaches
    the interview agenda; an `awarded` one does not run the submission review the same way.
  * **income route** — `str` and `salary` are two different bodies of code
    (`verdict_income_salary` vs the STR arm), and the document cluster rules differ between
    them (the STR route accepts a legacy-blank tag as the single earner's; the salary route
    does not).
  * **document set** — the snapshot's own subject. The seven below are the shapes that can make
    an in-memory filter differ from an SQL one:
      - ``none`` — the floor, and the case H18 measured at 315.
      - ``one-each`` — one document of several types, so every type branch has something.
      - ``several-same-type`` — three salary slips: "the latest" now has to CHOOSE.
      - ``superseded`` — a live row and a replaced one of the same type. A Python filter that
        forgets ``superseded_at`` returns the replaced document and a verdict moves.
      - ``tagged-and-untagged`` — ``household_member='father'`` beside ``household_member=''``.
        The cluster rules turn on exactly this and they differ by route.
      - ``identical-timestamps`` — two documents with the SAME ``uploaded_at``. See the note
        below; this is the case the ordering argument stands or falls on.
      - ``garbage-vision-fields`` — ``vision_fields`` holding a list, a bare string, a number
        and a nested non-dict where the engines expect a dict. Nothing here should change with
        the snapshot, but a crash would, and a payload that 500s is not identical to one that
        does not.

⚠ **TWO SHAPES OF GARBAGE CRASH THE ENDPOINT, AND THEY DID BEFORE THIS SPRINT.** Building the
matrix found that a stored ``vision_fields`` of ``{'authenticity': 'a string'}`` or
``{'authenticity': {'status': 12345}}`` makes the officer's detail GET raise
``AttributeError`` — a 500 on an officer's screen from one bad JSON value. It is **not** TD-282's
doing: the same exception is raised with the snapshot switched off, which
``TheGarbageThatCrashesTheEndpointCrashedItBefore`` below asserts in both directions rather than
leaving the discovery in a commit message. Fixing it would turn a 500 into a 200, which is a
behaviour change and out of this sprint's scope. It is TD-293.

⚠ **IDENTICAL TIMESTAMPS — READ THIS BEFORE CHANGING THE ORDERING.** Every one of these reads
is ``ORDER BY uploaded_at DESC`` with **no tie-breaker**, so when two documents share a
timestamp neither SQLite nor PostgreSQL promises which comes first — and that was true before
the snapshot existed. The snapshot loads the rows with that same clause once and filters
without re-sorting, so a subset keeps the order the database gave; that is why the
``identical-timestamps`` fixture comes out byte-identical here. It is a FINDING, not a fix:
production PostgreSQL can still change its mind about a tie after an unrelated ``UPDATE``
rewrites a heap row. TD-292 records it, with the reason a ``, '-id'`` tie-breaker was NOT added
in this sprint (it would change which document is chosen TODAY, which is a behaviour change).
"""
import json
from unittest import mock

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship import document_snapshot as snap
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import (
    OUTCOME_STAGES, STAGES, TEST_JWT_SECRET, authed_client, make_admin, make_application,
    make_cohort, make_org, make_programme, make_shortlistable_student,
)
from apps.scholarship.views_admin import applications as applications_view


def _null_snapshot(_application):
    """The OFF switch: what the view does when there is no snapshot — nothing at all."""
    class _Null:
        def __enter__(self):
            return None

        def __exit__(self, *exc):
            return False
    return _Null()


#: Every factory stage as a ``(stage, outcome)`` pair. The two stages with two roads contribute
#: one case each way, because `recommend` and `decline` leave genuinely different rows.
STAGE_CASES = tuple(
    (stage, outcome)
    for stage in STAGES
    for outcome in (('recommend', 'decline') if stage in OUTCOME_STAGES else (None,))
)

#: ``name -> [(doc_type, household_member, vision_fields), ...]``. ``superseded`` and
#: ``identical-timestamps`` need more than a tuple can say and are handled in ``_documents``.
DOCUMENT_SETS = (
    'none',
    'one-each',
    'several-same-type',
    'superseded',
    'tagged-and-untagged',
    'identical-timestamps',
    'garbage-vision-fields',
)

_OK = {'student_verdict': 'ok', 'fields': {'name': 'Test Student', 'nric': '050101-01-1234'}}
_STR_FIELDS = {'student_verdict': 'ok',
               'fields': {'status': 'Lulus', 'year': '2025',
                          'recipient_name': 'Test Student', 'recipient_nric': '050101-01-1234'}}


def _add(application, doc_type, member='', fields=None, i=0, **columns):
    return ApplicantDocument.objects.create(
        application=application, doc_type=doc_type, household_member=member,
        storage_path=f'test/{application.id}/{doc_type}-{member}-{i}.pdf',
        original_filename=f'{doc_type}-{i}.pdf',
        vision_fields=fields if fields is not None else {}, **columns)


def _documents(application, which):
    """Build the named document set on *application*."""
    if which == 'none':
        return
    if which == 'one-each':
        for i, dt in enumerate(('ic', 'results_slip', 'str', 'parent_ic', 'offer_letter',
                                'birth_certificate', 'water_bill', 'electricity_bill',
                                'salary_slip', 'epf', 'income_support_doc',
                                'statement_of_intent')):
            _add(application, dt, fields=_STR_FIELDS if dt == 'str' else _OK, i=i)
        return
    if which == 'several-same-type':
        for i in range(3):
            _add(application, 'salary_slip', fields=_OK, i=i)
        for i in range(2):
            _add(application, 'str', fields=_STR_FIELDS, i=i)
        return
    if which == 'superseded':
        # ⚠ EVERY REPLACED ROW HERE IS MATERIALLY WORSE THAN THE ROW THAT REPLACED IT, and that
        # is the whole design of this fixture. The first version of it re-uploaded IDENTICAL
        # documents, which is what a student does almost never; a snapshot that forgot
        # `superseded_at` altogether then returned the same answers and the bite-check came back
        # SILENT. A student re-uploads BECAUSE the first one was rejected, unreadable or the
        # wrong address — so a dead row leaking into a live read has to move an answer, and now
        # it does: the STR was refused, the bill's address mismatched, the payslip was not a
        # payslip, the results slip's name was someone else's.
        pairs = [
            ('str', {**_STR_FIELDS, 'student_verdict': 'unreadable',
                     'fields': {'status': 'Tidak Lulus', 'year': '2024'}}, _STR_FIELDS, {}, {}),
            ('water_bill', _OK, _OK,
             {'vision_address_match': 'mismatch'}, {'vision_address_match': 'found'}),
            ('salary_slip', {'student_verdict': 'wrong_doc',
                             'authenticity': {'status': 'not_salary'}}, _OK, {}, {}),
            ('results_slip', {'student_verdict': 'name_mismatch',
                              'fields': {'name': 'SOMEBODY ELSE ENTIRELY'}}, _OK, {}, {}),
            ('ic', _OK, _OK, {'vision_error': 'blurry'}, {}),
        ]
        for doc_type, dead_fields, live_fields, dead_columns, live_columns in pairs:
            dead = _add(application, doc_type, fields=dead_fields, i=0, **dead_columns)
            live = _add(application, doc_type, fields=live_fields, i=1, **live_columns)
            # Stamped exactly as a re-upload stamps them (views.py's supersede path).
            ApplicantDocument.objects.filter(id=dead.id).update(
                superseded_at=timezone.now(), superseded_by=live)
        return
    if which == 'tagged-and-untagged':
        _add(application, 'parent_ic', member='father', fields=_OK, i=0)
        _add(application, 'parent_ic', member='', fields=_OK, i=1)
        _add(application, 'salary_slip', member='mother', fields=_OK, i=0)
        _add(application, 'salary_slip', member='', fields=_OK, i=1)
        _add(application, 'income_support_doc', member='father', fields=_OK, i=0)
        _add(application, 'income_support_doc', member='', fields=_OK, i=1)
        return
    if which == 'identical-timestamps':
        a = _add(application, 'str', fields=_STR_FIELDS, i=0)
        b = _add(application, 'str', fields={**_STR_FIELDS, 'student_verdict': 'unreadable'}, i=1)
        c = _add(application, 'salary_slip', fields=_OK, i=0)
        d = _add(application, 'salary_slip', fields={'student_verdict': 'unreadable'}, i=1)
        # ⚠ THE WHOLE POINT: one instant, four rows, no tie-breaker anywhere in the ORDER BY.
        stamp = timezone.now()
        ApplicantDocument.objects.filter(id__in=[a.id, b.id, c.id, d.id]).update(
            uploaded_at=stamp)
        return
    if which == 'garbage-vision-fields':
        # Every shape here is garbage the payload SURVIVES. The two that crash it are in
        # CRASHING_GARBAGE below, with their own test and their own TD, because a fixture
        # quietly trimmed to what passes is how a defect stops being recorded.
        _add(application, 'ic', fields=['not', 'a', 'dict'], i=0)
        _add(application, 'str', fields='a bare string', i=1)
        _add(application, 'results_slip', fields=42, i=2)
        _add(application, 'epf', fields={'fields': {'nested': {'deep': None}}}, i=3)
        _add(application, 'water_bill', fields={'fields': [], 'authenticity': {}}, i=4)
        return
    raise AssertionError(f'unknown document set {which!r}')


#: ``name -> (vision_fields, doc_type, routes)`` — the stored JSON shapes that make the officer's
#: detail GET raise, with the snapshot open OR closed. TD-293. Not "known failures to skip": the
#: test below asserts the two paths raise the SAME exception, which is the identity claim this
#: file makes everywhere else, applied to a case whose answer happens to be an error.
CRASHING_GARBAGE = (
    # `(vf.get('authenticity') or {}).get('status', '')` — the idiom guards `vision_fields`
    # against not being a dict and then assumes `authenticity` IS one.
    ('authenticity-is-a-string', {'authenticity': 'not a dict'}, 'ic', ('str', 'salary')),
    # `canonical_status` does `(raw or '').strip()` — a non-string status walks straight in.
    ('authenticity-status-is-a-number', {'authenticity': {'status': 12345}}, 'water_bill',
     ('str', 'salary')),
)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TheSnapshotChangesNoResponseByte(TestCase):
    """THE ON==OFF MATRIX. One fixture per (stage, route, document set); two reads each."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cohort = make_cohort(programme=make_programme(organisation=cls.org),
                                 owning_organisation=cls.org)
        cls.admin = make_admin('org_admin', owning_org=cls.org)

    def _case(self, stage, outcome, route, documents):
        app = make_application(
            stage, outcome=outcome, cohort=self.cohort,
            student=make_shortlistable_student(),
            income_route=route,
            income_earner='father' if route == 'str' else '',
            income_working_members=['father', 'mother'] if route == 'salary' else [])
        _documents(app, documents)
        return authed_client(self.admin), f'/api/v1/admin/scholarship/applications/{app.id}/'

    def _read(self, client, url, *, snapshot):
        """One GET, with the snapshot on or off, returning (status, bytes, query count)."""
        patcher = (mock.patch.object(applications_view, 'document_snapshot', _null_snapshot)
                   if not snapshot else None)
        if patcher:
            patcher.start()
        try:
            with CaptureQueriesContext(connection) as captured:
                response = client.get(url)
            return response.status_code, response.content, len(captured.captured_queries)
        finally:
            if patcher:
                patcher.stop()

    def _assert_identical(self, stage, outcome, route, documents):
        client, url = self._case(stage, outcome, route, documents)
        # A warm-up read first. The detail GET synchronises Check-2 resolution items on its way
        # through, so the FIRST read of a new application can differ from the second for reasons
        # that have nothing to do with the snapshot. Both reads below are therefore steady-state.
        self.assertEqual(client.get(url).status_code, 200)
        off_status, off_body, off_queries = self._read(client, url, snapshot=False)
        on_status, on_body, on_queries = self._read(client, url, snapshot=True)
        label = f'{stage}/{outcome or "-"} · {route} · {documents}'
        self.assertEqual(off_status, 200, f'{label}: the OFF read did not answer 200')
        self.assertEqual(on_status, 200, f'{label}: the ON read did not answer 200')
        if off_body != on_body:
            self.fail(
                f'{label}: THE SNAPSHOT CHANGED THE ANSWER.\n'
                f'The officer\'s payload differs with the document snapshot open. This is the '
                f'failure this whole file exists to catch — a reader in `document_snapshot` is '
                f'filtering or ordering differently from the query it replaced.\n'
                f'First difference:\n{_first_difference(off_body, on_body)}')
        # ⚠ A POSITIVE ASSERTION THAT THE SNAPSHOT IS ACTUALLY ON. Without this the whole matrix
        # would pass unchanged the day the view stops opening one — identical bytes are exactly
        # what you get when nothing happens. The saving is large (315 -> 38 on the bare case), so
        # a plain "fewer" is a safe and stable claim.
        self.assertLess(
            on_queries, off_queries,
            f'{label}: the snapshot saved NO queries ({on_queries} vs {off_queries}). Either '
            f'the view stopped opening one, or the helpers stopped consulting it — in which '
            f'case every other assertion in this file is passing vacuously.')

    def _sweep(self, documents):
        """Every stage x both routes, for one document set."""
        self.assertIn(documents, DOCUMENT_SETS)
        for stage, outcome in STAGE_CASES:
            for route in ('str', 'salary'):
                with self.subTest(stage=stage, outcome=outcome, route=route,
                                  documents=documents):
                    self._assert_identical(stage, outcome, route, documents)

    # One method per document set, deliberately — a single method holding all 238 cases runs on
    # one xdist worker and becomes the slowest thing in the suite; seven spread out.
    def test_no_documents(self):
        self._sweep('none')

    def test_one_document_of_each_type(self):
        self._sweep('one-each')

    def test_several_documents_of_the_same_type(self):
        self._sweep('several-same-type')

    def test_a_superseded_row_beside_its_replacement(self):
        self._sweep('superseded')

    def test_tagged_and_untagged_income_documents(self):
        self._sweep('tagged-and-untagged')

    def test_two_documents_with_the_identical_uploaded_at(self):
        self._sweep('identical-timestamps')

    def test_garbage_vision_fields(self):
        self._sweep('garbage-vision-fields')

    # ── THE FIRST OPEN — what the read PERSISTS, not just what it draws ──────────────────────
    #
    # Added by the adversarial review of 2026-09-21. `_assert_identical` warms the application up
    # first, and it has to: the first detail GET synchronises Check-2 resolution items, so a cold
    # read and a warm one differ for reasons that are nothing to do with the snapshot. But the
    # warm-up ran with the snapshot ON in both arms, so the one read that WRITES — that creates
    # and resolves ResolutionItem rows off verdict facts, and can email the student — was never
    # compared ON against OFF at all. A wrong row there is persisted and sent, not just drawn.
    #
    # Two byte-for-byte twin applications, one opened cold with the snapshot OFF and one cold with
    # it ON. Their ids and timestamps differ, so payload bytes cannot be compared; what each read
    # LEFT BEHIND can: the resolution items it created, and the mail it sent.
    #
    # ⚠ WHAT THIS CAN AND CANNOT SEE — bitten both ways on the day it was written. A fault that
    # changes what the verdict reads as THE LATEST document of a type turns it red (a typed read
    # that finds nothing under the snapshot: 4 of 5 red). A fault that only adds rows to a LIST
    # read does NOT: serving superseded rows as live left it green, because a superseded row is
    # older than its replacement, so "the latest" — which is what a chase is raised from — does
    # not move. That fault is the byte matrix's to catch, and it does (36 cases). The two tests
    # cover different halves; neither is a substitute for the other.

    def _first_open_leaves(self, stage, outcome, route, documents, *, snapshot):
        from django.core import mail
        from apps.scholarship.models import ResolutionItem
        client, url = self._case(stage, outcome, route, documents)
        app_id = int(url.rstrip('/').rsplit('/', 1)[-1])
        before = len(mail.outbox)
        status, _body, _n = self._read(client, url, snapshot=snapshot)
        self.assertEqual(status, 200)
        items = sorted(
            (i.fact, i.code, i.kind, i.doc_type, i.status, i.source,
             json.dumps(i.params, sort_keys=True))
            for i in ResolutionItem.objects.filter(application_id=app_id))
        sent = sorted((m.subject, tuple(m.to)) for m in mail.outbox[before:])
        return items, [subject for subject, _to in sent]

    def _sweep_first_open(self, documents):
        self.assertIn(documents, DOCUMENT_SETS)
        raised = 0
        for stage, outcome in STAGE_CASES:
            for route in ('str', 'salary'):
                with self.subTest(stage=stage, outcome=outcome, route=route,
                                  documents=documents):
                    off_items, off_mail = self._first_open_leaves(
                        stage, outcome, route, documents, snapshot=False)
                    on_items, on_mail = self._first_open_leaves(
                        stage, outcome, route, documents, snapshot=True)
                    label = f'{stage}/{outcome or "-"} · {route} · {documents}'
                    self.assertEqual(
                        off_items, on_items,
                        f'{label}: THE FIRST OPEN PERSISTED DIFFERENT RESOLUTION ITEMS with the '
                        f'snapshot open. These rows are what the student is asked for; a '
                        f'difference here is a wrong chase, written to the database.')
                    self.assertEqual(
                        off_mail, on_mail,
                        f'{label}: the first open SENT DIFFERENT MAIL with the snapshot open.')
                    raised += len(off_items)
        return raised

    # THREE document sets, not all seven, and that is a measured choice (2026-09-21). Each sweep
    # builds 68 applications and costs about a minute of a deploy gate that runs on few cores.
    # `superseded` is left out on evidence, not taste: the bite above showed this comparison
    # CANNOT see the superseded-as-live fault, so that sweep bought a minute of nothing, and the
    # byte matrix already covers it. The three kept are the ones that change what the verdict
    # READS: nothing on file, one of everything, and the member-tag filter the income facts use.

    def test_the_first_open_persists_the_same_items__no_documents(self):
        """Also the NOT-VACUOUS check. If no first open ever raised an item, every sweep here
        compares empty with empty and is green for ever — and a household with nothing on file
        is the one that MUST be asked for something."""
        raised = self._sweep_first_open('none')
        self.assertGreater(raised, 0, 'no first open created a single ResolutionItem — the '
                                      'first-open comparison is passing vacuously')

    def test_the_first_open_persists_the_same_items__one_of_each(self):
        self._sweep_first_open('one-each')

    def test_the_first_open_persists_the_same_items__tagged_and_untagged(self):
        self._sweep_first_open('tagged-and-untagged')

    def test_the_matrix_is_the_size_it_claims(self):
        """A floor (TD-276). A matrix that silently shrinks to one case asserts almost nothing,
        and a loop over an empty list is green for ever."""
        self.assertEqual(len(STAGES), 15, 'the factory gained or lost a stage — extend the '
                                          'matrix deliberately rather than letting it drift')
        self.assertEqual(len(STAGE_CASES), 17,
                         'STAGE_CASES should be the 13 single-road stages plus two roads each '
                         'for verdict_recorded and awaiting_qc')
        self.assertEqual(len(DOCUMENT_SETS), 7)
        self.assertEqual(len(STAGE_CASES) * 2 * len(DOCUMENT_SETS), 238,
                         'the matrix is stage-cases x 2 routes x document sets')
        swept = {name.split('test_', 1)[1] for name in dir(self) if name.startswith('test_')}
        self.assertGreaterEqual(
            len(swept), 8, 'the per-document-set methods have gone; the matrix now covers less '
                           'than it claims and nothing would say so')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TheGarbageThatCrashesTheEndpointCrashedItBefore(TestCase):
    """TD-293 — two stored ``vision_fields`` shapes 500 the officer's detail GET.

    Found while building the ON==OFF matrix. The point of THIS test is narrow and it is the
    same point the matrix makes everywhere else: **the snapshot did not cause it, and did not
    change it.** The same exception, of the same type, is raised with the snapshot open and
    with it closed.

    ⚠ It is NOT a licence to leave the defect. Fixing it turns a 500 into a 200, which is a
    behaviour change, so it belongs to the sprint that decides what the officer should see for a
    document whose stored extraction is malformed — not to a performance refactor. When that
    lands, this test is the thing that has to be rewritten, deliberately, and the matrix above
    gains the two shapes.
    """

    def _case(self, fields, doc_type, route):
        org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=org),
                             owning_organisation=org)
        app = make_application(
            'interviewing', cohort=cohort, student=make_shortlistable_student(),
            income_route=route, income_earner='father' if route == 'str' else '',
            income_working_members=['father'] if route == 'salary' else [])
        ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, storage_path=f'test/{app.id}/{doc_type}.pdf',
            original_filename='x.pdf', vision_fields=fields)
        return (authed_client(make_admin('org_admin', owning_org=org)),
                f'/api/v1/admin/scholarship/applications/{app.id}/')

    def _raised(self, client, url, *, snapshot):
        patcher = (mock.patch.object(applications_view, 'document_snapshot', _null_snapshot)
                   if not snapshot else None)
        if patcher:
            patcher.start()
        try:
            client.get(url)
            return None
        except Exception as exc:                      # noqa: BLE001 - characterising a defect
            return f'{type(exc).__name__}: {exc}'
        finally:
            if patcher:
                patcher.stop()

    def test_the_two_shapes_fail_identically_with_and_without_the_snapshot(self):
        for name, fields, doc_type, routes in CRASHING_GARBAGE:
            for route in routes:
                with self.subTest(shape=name, route=route):
                    client, url = self._case(fields, doc_type, route)
                    off = self._raised(client, url, snapshot=False)
                    on = self._raised(client, url, snapshot=True)
                    self.assertIsNotNone(
                        off,
                        f'{name}/{route} no longer crashes the endpoint WITHOUT the snapshot. '
                        f'TD-293 has been fixed — good: move this shape into DOCUMENT_SETS '
                        f'`garbage-vision-fields` so the ON==OFF matrix covers it, and delete '
                        f'it from CRASHING_GARBAGE.')
                    self.assertEqual(
                        off, on,
                        f'{name}/{route}: the snapshot CHANGED how this fails. That makes it '
                        f'TD-282\'s defect and not TD-293\'s.')


def _first_difference(a: bytes, b: bytes) -> str:
    """The first JSON key whose value differs, so a failure names a FIELD and not an offset."""
    try:
        left, right = json.loads(a), json.loads(b)
    except ValueError:
        return f'off[:300]={a[:300]!r}\non[:300]={b[:300]!r}'
    lines = []
    for key in sorted(set(left) | set(right)):
        if left.get(key) != right.get(key):
            lines.append(f'  {key}:\n    off = {left.get(key)!r}\n    on  = {right.get(key)!r}')
    return '\n'.join(lines) or '(the parsed JSON matches; the bytes differ in key ORDER)'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ASnapshotCannotGoStale(TestCase):
    """The other half of the argument: the snapshot cannot be read where it should not be.

    Byte-identity proves the rows are filtered correctly. These prove the rows are only ever
    served to the applicant they belong to, and only for as long as the block that loaded them.
    """

    def _application(self):
        org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=org),
                             owning_organisation=org)
        return make_application('interviewing', cohort=cohort,
                                student=make_shortlistable_student())

    def test_a_write_is_visible_to_a_read_taken_outside_the_scope(self):
        """The staleness test. A snapshot is a photograph, and the photograph must be thrown
        away at the end of the block — otherwise a write made during a request is invisible to
        everything after it, which is the failure mode a cache has and this must not."""
        app = self._application()
        with snap.document_snapshot(app):
            self.assertEqual(snap.present_doc_types(app), set())
            _add(app, 'ic', fields=_OK)
            # Inside the block the photograph is deliberately unchanged — it was taken before
            # the write. This is WHY no write path may open one.
            self.assertEqual(snap.present_doc_types(app), set())
        self.assertEqual(snap.present_doc_types(app), {'ic'},
                         'a read taken AFTER the block still saw the stale snapshot — the '
                         'ContextVar was not reset, and every later read in this thread is now '
                         'answering from a photograph')
        self.assertFalse(snap.is_open_for(app))

    def test_a_second_application_is_never_served_from_the_first(self):
        """A snapshot answers for ONE applicant. Several engines walk from a document back to
        `doc.application`, so a reader handed a different application must fall through to its
        query rather than hand back the wrong family's documents."""
        first, second = self._application(), self._application()
        _add(first, 'str', fields=_STR_FIELDS)
        _add(second, 'results_slip', fields=_OK)
        with snap.document_snapshot(first):
            self.assertTrue(snap.is_open_for(first))
            self.assertFalse(snap.is_open_for(second))
            self.assertEqual(snap.present_doc_types(first), {'str'})
            self.assertEqual(snap.present_doc_types(second), {'results_slip'},
                             "the second application was served the FIRST one's documents")

    def test_the_same_pk_on_another_model_is_never_served(self):
        """The key is (model, pk), not pk. The adversarial review of 2026-09-21 proved the first
        version keyed on pk alone: ANY object whose pk equalled the applicant's was served that
        applicant's documents — a different model, or a stand-in with no documents at all."""
        app = self._application()
        _add(app, 'str', fields=_STR_FIELDS)

        class Impostor:                       # a stand-in: right pk, no model behind it
            pk = app.pk

        other_model_same_pk = app.cohort.__class__(pk=app.pk)   # a real model, the same number

        with snap.document_snapshot(app):
            self.assertTrue(snap.is_open_for(app))
            self.assertEqual(snap.present_doc_types(app), {'str'})
            for stranger in (Impostor(), other_model_same_pk):
                self.assertFalse(snap.is_open_for(stranger),
                                 f'{type(stranger).__name__} shares the pk and was treated as '
                                 f'the applicant')
            # A stand-in with no `documents` answers EMPTY, as it always has — not the applicant's.
            self.assertEqual(snap.present_doc_types(Impostor()), set(),
                             "a stand-in with the applicant's pk was served the applicant's "
                             "documents")

    def test_a_nested_snapshot_restores_the_outer_one(self):
        """`reset(token)` in the `finally`, not `set(None)`. An inner block for another
        applicant must leave the outer block exactly as it found it."""
        outer, inner = self._application(), self._application()
        _add(outer, 'str', fields=_STR_FIELDS)
        _add(inner, 'results_slip', fields=_OK)
        with snap.document_snapshot(outer):
            with snap.document_snapshot(inner):
                self.assertEqual(snap.present_doc_types(inner), {'results_slip'})
                self.assertFalse(snap.is_open_for(outer))
            self.assertTrue(snap.is_open_for(outer),
                            'the outer snapshot did not come back after the inner one closed')
            self.assertEqual(snap.present_doc_types(outer), {'str'})
        self.assertFalse(snap.is_open_for(outer))

    def test_the_scope_closes_even_when_the_body_raises(self):
        app = self._application()
        with self.assertRaises(ValueError):
            with snap.document_snapshot(app):
                raise ValueError('boom')
        self.assertFalse(snap.is_open_for(app),
                         'an exception left the snapshot open, so every later read in this '
                         'thread answers from it')

    def test_the_officer_detail_get_writes_no_document(self):
        """The precondition for opening a snapshot there at all: the handler is read-only with
        respect to `applicant_documents`. If that ever stops being true, the snapshot is a stale
        read and this test is the thing that says so."""
        app = self._application()
        _add(app, 'ic', fields=_OK)
        org = app.owning_organisation or app.cohort.owning_organisation
        client = authed_client(make_admin('org_admin', owning_org=org))
        url = f'/api/v1/admin/scholarship/applications/{app.id}/'
        self.assertEqual(client.get(url).status_code, 200)
        with CaptureQueriesContext(connection) as captured:
            self.assertEqual(client.get(url).status_code, 200)
        writes = [q['sql'] for q in captured.captured_queries
                  if 'applicant_documents' in (q['sql'] or '')
                  and not (q['sql'] or '').lstrip().upper().startswith('SELECT')]
        self.assertEqual(writes, [],
                         'the officer detail GET now WRITES to applicant_documents. A snapshot '
                         'must not be open over a write path — either move the write out of the '
                         'read, or stop opening the snapshot in this handler.')


class TheReadersAnswerTheSameWithAndWithoutASnapshot(TestCase):
    """The unit-level half: each reader, both paths, against one fixture with every awkward row.

    The matrix above proves the ENDPOINT is unchanged. This proves each reader is unchanged,
    which is what makes a failure in the matrix findable.
    """

    def setUp(self):
        org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=org),
                             owning_organisation=org)
        self.app = make_application('interviewing', cohort=cohort,
                                    student=make_shortlistable_student(),
                                    income_route='salary',
                                    income_working_members=['father', 'mother'])
        _add(self.app, 'parent_ic', member='father', fields=_OK, i=0)
        _add(self.app, 'parent_ic', member='', fields=_OK, i=1)
        _add(self.app, 'salary_slip', member='father', fields=_OK, i=0)
        _add(self.app, 'salary_slip', member='father', fields=_OK, i=1)
        _add(self.app, 'income_support_doc', member='mother', fields=_OK, i=0)
        dead = _add(self.app, 'str', fields=_STR_FIELDS, i=0)
        _add(self.app, 'str', fields=_STR_FIELDS, i=1)
        ApplicantDocument.objects.filter(id=dead.id).update(superseded_at=timezone.now())

    def _both(self, call):
        off = call()
        with snap.document_snapshot(self.app):
            on = call()
        return off, on

    def test_every_reader_agrees(self):
        app = self.app
        cases = {
            'live_docs/all': lambda: [d.id for d in snap.live_docs(app)],
            'live_docs/type': lambda: [d.id for d in snap.live_docs(app, 'salary_slip')],
            'live_docs/types': lambda: [d.id for d in snap.live_docs(
                app, doc_types=('parent_ic', 'epf'))],
            'live_docs/member': lambda: [d.id for d in snap.live_docs(
                app, 'parent_ic', member='father')],
            'live_docs/blank-member': lambda: [d.id for d in snap.live_docs(
                app, 'parent_ic', member='')],
            'live_docs/members': lambda: [d.id for d in snap.live_docs(
                app, 'parent_ic', members=['father', ''])],
            'latest_doc': lambda: getattr(snap.latest_doc(app, 'str'), 'id', None),
            'latest_doc/member': lambda: getattr(
                snap.latest_doc(app, 'salary_slip', member='father'), 'id', None),
            'latest_doc/absent': lambda: getattr(snap.latest_doc(app, 'epf'), 'id', None),
            'has_live_doc/yes': lambda: snap.has_live_doc(app, 'str'),
            'has_live_doc/no': lambda: snap.has_live_doc(app, 'epf'),
            'present_doc_types': lambda: sorted(snap.present_doc_types(app)),
            'tagged_members': lambda: sorted(snap.tagged_members(
                app, ('parent_ic', 'salary_slip', 'epf'))),
        }
        for name, call in cases.items():
            with self.subTest(reader=name):
                off, on = self._both(call)
                self.assertEqual(off, on, f'{name} answers differently under a snapshot')

    def test_the_superseded_row_is_on_the_application_and_in_no_live_read(self):
        """A positive AND a negative, because a reader that returned nothing at all would
        satisfy the negative on its own (the arc's rule 1). The positive half asks the DATABASE,
        not the module — the claim is that a row the application really has is excluded, which a
        reader cannot be trusted to confirm about itself."""
        dead = ApplicantDocument.objects.filter(
            application=self.app, superseded_at__isnull=False).first()
        self.assertIsNotNone(dead, 'the fixture stopped carrying a superseded row')
        self.assertIn(dead.id, list(self.app.documents.values_list('id', flat=True)))
        with snap.document_snapshot(self.app):
            self.assertNotIn(dead.id, [d.id for d in snap.live_docs(self.app)])
            self.assertGreater(len(snap.live_docs(self.app)), 1,
                               'the live read found almost nothing, so the assertion above '
                               'proves nothing')

    def test_live_docs_refuses_member_and_members_together(self):
        with self.assertRaises(TypeError):
            snap.live_docs(self.app, 'parent_ic', member='father', members=['father', ''])

    def test_a_stand_in_without_documents_answers_empty_rather_than_raising(self):
        """Several engine tests pass an object with no `.documents` at all. Every reader has to
        survive that, exactly as the helpers it replaced did."""
        from types import SimpleNamespace
        double = SimpleNamespace(pk=None)
        self.assertEqual(list(snap.live_docs(double, 'ic')), [])
        self.assertIsNone(snap.latest_doc(double, 'ic'))
        self.assertFalse(snap.has_live_doc(double, 'ic'))
        self.assertEqual(snap.present_doc_types(double), set())
        self.assertEqual(snap.tagged_members(double, ('ic',)), [])
        with snap.document_snapshot(double):
            self.assertFalse(snap.is_open_for(double))
