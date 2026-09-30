"""TD-292 — "the latest document" is newest `uploaded_at`, then HIGHEST `id`. One home.

Every document read ordered by `-uploaded_at` with no tie-breaker, so two documents sharing a
timestamp had no defined "latest": SQLite and PostgreSQL may return either, and PostgreSQL may
change its mind after an unrelated UPDATE. Since 2026-09-30 the clause is
`document_snapshot.SNAPSHOT_ORDER = ('-uploaded_at', '-id')` — the row written LAST wins — and
`ApplicantDocument.Meta.ordering` plus every explicit document `.order_by(...)` read it from there.

Pinned three ways on an identical-timestamps fixture (the snapshot reader, the model's default
ordering, one explicit site), and by a SOURCE SCAN with a floor so a new
`.order_by('-uploaded_at')` cannot quietly reintroduce the undefined tie.
"""
import datetime
import re

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship import document_snapshot, profile_engine
from apps.scholarship.document_snapshot import SNAPSHOT_ORDER, latest_doc
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.source_walk import API_ROOT, floor_count, read_source, walk_sources


class IdenticalTimestampsTest(TestCase):
    """Two live documents of one type, one `uploaded_at`: the higher id is "the latest"."""

    def setUp(self):
        self.app = make_application('profile_complete')
        self.older = ApplicantDocument.objects.create(
            application=self.app, doc_type='statement_of_intent', storage_path='p/soi-1',
            vision_fields={'text': 'FIRST ROW'})
        self.newer = ApplicantDocument.objects.create(
            application=self.app, doc_type='statement_of_intent', storage_path='p/soi-2',
            vision_fields={'text': 'SECOND ROW'})
        self.assertGreater(self.newer.id, self.older.id)
        tie = timezone.now() - datetime.timedelta(minutes=5)
        ApplicantDocument.objects.filter(application=self.app).update(uploaded_at=tie)

    def test_the_verdict_engine_version_records_the_change(self):
        # Review F5a: an exact tie now names a row, which can move a fact — so it bumped.
        from apps.scholarship import verdict_engine
        self.assertGreaterEqual(verdict_engine.VERDICT_ENGINE_VERSION, '2026-09-30.1')

    def test_the_clause_is_the_tie_broken_one(self):
        self.assertEqual(SNAPSHOT_ORDER, ('-uploaded_at', '-id'))
        self.assertEqual(ApplicantDocument._meta.ordering, list(SNAPSHOT_ORDER))

    def test_latest_doc_picks_the_higher_id_off_the_query(self):
        self.assertEqual(latest_doc(self.app, 'statement_of_intent'), self.newer)

    def test_latest_doc_picks_the_higher_id_inside_a_snapshot(self):
        with document_snapshot.document_snapshot(self.app):
            self.assertTrue(document_snapshot.is_open_for(self.app))
            self.assertEqual(latest_doc(self.app, 'statement_of_intent'), self.newer)

    def test_the_models_default_ordering_picks_the_higher_id(self):
        self.assertEqual(self.app.documents.filter(doc_type='statement_of_intent').first(),
                         self.newer)
        self.assertEqual(list(ApplicantDocument.objects.filter(application=self.app)),
                         [self.newer, self.older])

    def test_an_explicit_order_site_picks_the_higher_id(self):
        # profile_engine._statement_of_intent — `.order_by(*SNAPSHOT_ORDER).first()`.
        self.assertEqual(profile_engine._statement_of_intent(self.app), 'SECOND ROW')


#: `.order_by(...)` / `ordering = [...]` argument lists that name `uploaded_at` DESCENDING.
_ORDER_CALL = re.compile(r"(?:order_by\(|ordering\s*=\s*[\[(])([^)\]]*)", re.S)
_DESC = re.compile(r"""['"]-uploaded_at['"]""")
_TIE = re.compile(r"""['"]-(?:id|pk)['"]""")
_UNPACKED = 'order_by(*SNAPSHOT_ORDER)'

#: Another model with an `uploaded_at` of its own may order by it without the document rule.
#: EMPTY on 2026-09-30 — every `-uploaded_at` in the tree was an ApplicantDocument read. Adding a
#: name here is a decision with its reason beside it, never a way to make this pass.
OTHER_MODELS = {}

#: `.latest(`/`.earliest(` on uploaded_at, `Max(`/`max(` whose arguments name it, and a sort key.
_OTHER_PICK = re.compile(
    r"""\.(?:latest|earliest)\(\s*['"]-?uploaded_at['"]"""
    r"""|\b[Mm](?:ax|in)\([^()]*uploaded_at[^()]*\)"""
    r"""|key\s*=\s*lambda[^:]*:[^,)\n]*uploaded_at""")
#: A hit allowed because it returns a TIMESTAMP, not a row, so a tie cannot change the answer.
TIMESTAMP_AGGREGATES = {
    # "When did this applicant last upload anything?" — the partner chase list's activity date.
    'apps/scholarship/partner_comms.py': "Max('uploaded_at')",
}


class NoUntieBrokenDocumentOrderTest(SimpleTestCase):
    """The source scan. Fails on any non-test `order_by('-uploaded_at'…)` without `-id`."""

    WHY = ('TD-292: every "latest document" read must break an uploaded_at tie on the id; the '
           'one home is document_snapshot.SNAPSHOT_ORDER')

    def _sources(self):
        files = walk_sources(API_ROOT / 'apps', '*.py', 400, self.WHY)
        return [p for p in files if 'tests' not in p.relative_to(API_ROOT).parts]

    def test_no_descending_uploaded_at_order_lacks_the_tie_break(self):
        bad = []
        for path in self._sources():
            rel = path.relative_to(API_ROOT).as_posix()
            if rel in OTHER_MODELS:
                continue
            text = read_source(path, self.WHY)
            for m in _ORDER_CALL.finditer(text):
                args = m.group(1)
                if _DESC.search(args) and not _TIE.search(args):
                    line = text.count('\n', 0, m.start()) + 1
                    bad.append(f'{rel}:{line}: {m.group(0).strip()[:80]}')
        self.assertEqual(bad, [], 'A document read orders by -uploaded_at with no tie-break. '
                                  'Use .order_by(*SNAPSHOT_ORDER) (document_snapshot).')

    def test_no_other_latest_pick_reads_uploaded_at_alone(self):
        """Review F5c: `.latest('uploaded_at')`, `Max('uploaded_at')` / `max(… uploaded_at …)` and a
        sort keyed on it pick "the newest" with no tie-break too. A hit is allowed only in
        `TIMESTAMP_AGGREGATES` — an aggregate that returns a TIME, never a row."""
        hits = []
        for path in self._sources():
            rel = path.relative_to(API_ROOT).as_posix()
            text = read_source(path, self.WHY)
            for m in _OTHER_PICK.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                hits.append((rel, m.group(0)))
                if TIMESTAMP_AGGREGATES.get(rel) != m.group(0):
                    self.fail(f'{rel}:{line}: {m.group(0)!r} picks the newest document by '
                              'uploaded_at alone. Order by *SNAPSHOT_ORDER and take .first().')
        # The scan must still SEE the one legitimate aggregate — a floor under the regex.
        floor_count(hits, len(TIMESTAMP_AGGREGATES), 'uploaded_at aggregates', self.WHY)

    def test_the_sites_that_use_the_one_home_are_all_still_found(self):
        # 17 explicit sites + the snapshot's own two reads on 2026-09-30 → floor 19.
        sites = []
        for path in self._sources():
            text = read_source(path, self.WHY)
            sites += [path.name] * text.count(_UNPACKED)
        floor_count(sites, 19, f'{_UNPACKED} sites', self.WHY)

    def test_the_model_reads_its_ordering_from_the_one_home(self):
        text = read_source(API_ROOT / 'apps/scholarship/models/documents.py', self.WHY)
        self.assertIn('ordering = list(SNAPSHOT_ORDER)', text)
