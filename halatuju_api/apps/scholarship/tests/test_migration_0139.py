"""Migration 0139 — the live clarification threads move into comments, losing nothing.

⚠ This is an ADOPTED path, not a new one. The standing lesson on this project is that routing LIVE
behaviour through new machinery switches it off silently: nothing errors, the suite stays green, and
the loss surfaces weeks later when somebody asks where their conversation went. The threads here are
real exchanges on real requests, so the transform is exercised against the SHAPES actually on
production rather than one happy path — answered, unanswered, owner-asked, absent `asked_by`
(pre-2026-07-30 rows, which meant the AI), and the `history` entries `modify` used to write.

The function is imported from the migration module itself, so this tests the code that will run
rather than a copy of it.
"""
import importlib

from django.test import TestCase

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import org_requests
from apps.scholarship.models import OrgRequest, OrgRequestComment

_mig = importlib.import_module(
    'apps.scholarship.migrations.0139_clarifications_to_comments')


class _FakeApps:
    """`RunPython` receives a historical model registry. The real models are shape-compatible for
    this transform, so the migration's own `forwards` can run against them."""

    _MODELS = {
        ('scholarship', 'OrgRequest'): OrgRequest,
        ('scholarship', 'OrgRequestComment'): OrgRequestComment,
    }

    def get_model(self, app_label, model_name):
        return self._MODELS[(app_label, model_name)]


class TestMigration0139(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='mg', name='Mig Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='mg-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='d@mg.test')

    def _req(self, clarifications):
        return OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='feature',
            title='t', description='d', clarifications=clarifications)

    def _run(self):
        _mig.forwards(_FakeApps(), None)

    def test_an_answered_ai_question_becomes_two_comments_in_order(self):
        req = self._req([{'question': 'Which page?', 'answer': 'The dashboard',
                          'asked_by': 'ai', 'asked_at': 't', 'answered_at': 't2'}])
        self._run()
        q, a = list(req.comments.all())
        self.assertEqual((q.body, q.author_kind), ('Which page?', org_requests.AUTHOR_AI))
        self.assertEqual((a.body, a.author_kind), ('The dashboard', org_requests.AUTHOR_ORG))
        self.assertFalse(q.awaiting_reply)
        self.assertTrue(q.replied_at, 'an answered question is stamped replied')

    def test_an_unanswered_question_still_awaits_a_reply(self):
        # The one that matters for the badge: if this lost `awaiting_reply` the requester would
        # never be told anything was outstanding.
        req = self._req([{'question': 'Which report?', 'answer': None, 'asked_by': 'ai'}])
        self._run()
        c = req.comments.get()
        self.assertTrue(c.awaiting_reply)
        self.assertEqual(len(org_requests.open_questions(req)), 1)

    def test_an_owner_question_keeps_its_author(self):
        req = self._req([{'question': 'Would an invite do?', 'answer': None,
                          'asked_by': 'owner'}])
        self._run()
        self.assertEqual(req.comments.get().author_kind, org_requests.AUTHOR_OWNER)

    def test_a_pre_2026_07_30_row_with_NO_asked_by_is_the_AI(self):
        # `asked_by` only exists from 2026-07-30; before that every question was the reviewer's.
        # Reading these as 'owner' would misattribute the whole of the module's history.
        req = self._req([{'question': 'Old one', 'answer': None}])
        self._run()
        self.assertEqual(req.comments.get().author_kind, org_requests.AUTHOR_AI)

    def test_a_history_entry_carries_no_question_and_is_skipped(self):
        # `modify` used to append {history, previous_description} with no `question` key. It must
        # not become an empty comment — `body` is NOT NULL and a blank one renders as a gap.
        req = self._req([{'history': 'description_modified', 'previous_description': 'old',
                          'at': 't'}])
        self._run()
        self.assertEqual(req.comments.count(), 0)

    def test_every_request_is_covered_and_counted_PER_REQUEST(self):
        # In aggregate a dropped thread hides behind another request's rows.
        a = self._req([{'question': 'q1', 'answer': 'a1'}, {'question': 'q2', 'answer': None}])
        b = self._req([{'question': 'only', 'answer': None}])
        c = self._req([])
        self._run()
        self.assertEqual(a.comments.count(), 3)   # q1 + a1 + q2
        self.assertEqual(b.comments.count(), 1)
        self.assertEqual(c.comments.count(), 0)

    def test_the_source_is_NOT_cleared(self):
        """`clarifications` survives this migration on purpose — dropping the source in the same
        change that copies it out removes any way to verify the copy against the original on
        production. Nothing READS it; the drop is its own follow-up."""
        req = self._req([{'question': 'q', 'answer': 'a'}])
        self._run()
        req.refresh_from_db()
        self.assertEqual(len(req.clarifications), 1)

    def test_backwards_removes_only_what_forwards_created(self):
        req = self._req([{'question': 'q', 'answer': 'a'}])
        self._run()
        typed_after = org_requests.post_comment(
            req, None, 'typed by a person afterwards', author_kind=org_requests.AUTHOR_OWNER)
        _mig.backwards(_FakeApps(), None)
        remaining = [c.id for c in req.comments.all()]
        self.assertEqual(remaining, [typed_after.id],
                         'a rollback must not eat a comment somebody typed later')
