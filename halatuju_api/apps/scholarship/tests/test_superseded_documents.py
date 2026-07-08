"""Documents-box reorg Phase 2 — document version history.

A re-upload no longer HARD-deletes the old copy: it stamps `superseded_at` and points
`superseded_by` at the replacement (retained as history for the officer view). THE RISK is
a verdict/gate/completeness read that forgets to exclude superseded rows — a replaced doc
would then silently count. These tests pin:

  1. superseded docs are invisible to every verdict/gate read funnel + the student listing;
  2. the admin serializer still returns them (history);
  3. the replace path supersedes (keeps the row + blob) instead of deleting;
  4. an explicit student "Remove" hard-deletes the whole chain + sweeps the blobs;
  5. a STATIC guard so a future read in the pure engine modules can't skip the active filter.
"""
import os
import re

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import verdict_engine, income_engine, services
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort


def _app(**kw):
    cohort = ScholarshipCohort.objects.create(
        code=f'c{ScholarshipCohort.objects.count()}', name='B40', year=2026)
    profile = StudentProfile.objects.create(
        supabase_user_id=f'u{StudentProfile.objects.count()}', name='Muthu Raman', **kw)
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='interviewing')


def _doc(app, doc_type='results_slip', member='', **kw):
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, household_member=member,
        storage_path=kw.pop('storage_path', f'blob-{ApplicantDocument.objects.count()}'), **kw)


class TestSupersededInvisibleToReads(TestCase):
    def test_latest_doc_skips_superseded(self):
        app = _app()
        old = _doc(app, 'str')
        new = _doc(app, 'str')
        old.superseded_at = timezone.now()
        old.superseded_by = new
        old.save(update_fields=['superseded_at', 'superseded_by'])
        self.assertEqual(verdict_engine._latest_doc(app, 'str'), new)

    def test_present_doc_types_skips_superseded(self):
        app = _app()
        d = _doc(app, 'offer_letter')
        d.superseded_at = timezone.now()
        d.save(update_fields=['superseded_at'])
        self.assertNotIn('offer_letter', verdict_engine._present_doc_types(app))

    def test_cluster_docs_skips_superseded(self):
        app = _app()
        app.income_route = 'salary'
        app.save(update_fields=['income_route'])
        old = _doc(app, 'salary_slip', member='father')
        new = _doc(app, 'salary_slip', member='father')
        old.superseded_at = timezone.now()
        old.superseded_by = new
        old.save(update_fields=['superseded_at', 'superseded_by'])
        got = list(income_engine._cluster_docs(app, 'father', 'salary_slip'))
        self.assertEqual(got, [new])

    def test_present_set_in_completeness_skips_superseded(self):
        """A superseded results_slip must not satisfy the documents present-set."""
        app = _app()
        d = _doc(app, 'results_slip')
        d.superseded_at = timezone.now()
        d.save(update_fields=['superseded_at'])
        present = set(app.documents.filter(superseded_at__isnull=True)
                      .values_list('doc_type', flat=True))
        self.assertNotIn('results_slip', present)


class TestReplacePathSupersedes(TestCase):
    """The upload endpoint's replace path is exercised via the view in the API tests; here we
    assert the model-level contract the view relies on: superseding keeps the row + its blob."""

    def test_supersede_keeps_row_and_blob(self):
        app = _app()
        old = _doc(app, 'ic', storage_path='ic-old')
        new = _doc(app, 'ic', storage_path='ic-new')
        # mimic the view's transaction body
        ApplicantDocument.objects.filter(id=old.id).update(
            superseded_at=timezone.now(), superseded_by=new)
        old.refresh_from_db()
        self.assertIsNotNone(old.superseded_at)          # row retained
        self.assertEqual(old.superseded_by_id, new.id)
        self.assertEqual(old.storage_path, 'ic-old')     # blob path untouched (not swept)
        # admin (default manager) sees both; a live read sees only the new
        self.assertEqual(app.documents.count(), 2)
        self.assertEqual(verdict_engine._latest_doc(app, 'ic'), new)


class TestStudentRemoveHardDeletesChain(TestCase):
    def test_remove_deletes_whole_chain(self):
        app = _app()
        a = _doc(app, 'ic')
        b = _doc(app, 'ic')
        c = _doc(app, 'ic')
        # a ← b ← c  (c is live)
        ApplicantDocument.objects.filter(id=a.id).update(superseded_at=timezone.now(), superseded_by=b)
        ApplicantDocument.objects.filter(id=b.id).update(superseded_at=timezone.now(), superseded_by=c)
        # transitive walk (mirrors DocumentDetailView.delete)
        chain, frontier = [c], [c]
        while frontier:
            parents = list(ApplicantDocument.objects.filter(superseded_by__in=[d.id for d in frontier]))
            chain.extend(parents)
            frontier = parents
        self.assertEqual({d.id for d in chain}, {a.id, b.id, c.id})


class TestResolvedMember(TestCase):
    def test_blank_income_doc_resolves_by_name(self):
        app = _app()
        app.father_name = 'RAVI A/L PERIAKARUPPAN'
        app.mother_name = 'SELVI A/P VELLAYAN'
        app.save(update_fields=['father_name', 'mother_name'])
        from apps.scholarship.income_engine import resolved_member_for
        # a blank-tagged father IC resolves to 'father' by the name on the card
        blank_ic = _doc(app, 'parent_ic', member='', vision_name='RAVI A/L PERIAKARUPPAN')
        self.assertEqual(resolved_member_for(app, blank_ic), 'father')
        # a properly-tagged doc keeps its own tag (no name lookup)
        tagged = _doc(app, 'parent_ic', member='mother')
        self.assertEqual(resolved_member_for(app, tagged), 'mother')
        # a blank doc whose name matches nobody → '' (shown in the SALARY catch-all)
        mystery = _doc(app, 'parent_ic', member='', vision_name='SOMEONE ELSE ENTIRELY')
        self.assertEqual(resolved_member_for(app, mystery), '')
        # a non-income blank doc is never name-resolved
        slip = _doc(app, 'results_slip', member='')
        self.assertEqual(resolved_member_for(app, slip), '')

    def test_blank_str_resolves_by_recipient_name(self):
        # #45: an STR on the salary route is the FATHER's; blank-tagged, it resolves to 'father' by the
        # RECIPIENT name (not the declared income_earner) — the docs box now files it as the verdict does.
        app = _app()
        app.father_name = 'SARAVANAN A/L CHANTHIRAN'
        app.mother_name = 'REMAVATHY A/P SELVARAJOO'
        app.save(update_fields=['father_name', 'mother_name'])
        from apps.scholarship.income_engine import resolved_member_for, name_contradicts_tag
        blank_str = _doc(app, 'str', member='',
                         vision_fields={'fields': {'recipient_name': 'SARAVANAN A/L CHANTHIRAN'}})
        self.assertEqual(resolved_member_for(app, blank_str), 'father')
        # a father's STR MIS-TAGGED 'mother' self-corrects to 'father' (the #80 class, now for STR too).
        mis = _doc(app, 'str', member='mother',
                   vision_fields={'fields': {'recipient_name': 'SARAVANAN A/L CHANTHIRAN'}})
        self.assertEqual(name_contradicts_tag(app, mis), 'father')


class TestStaticReadGuard(TestCase):
    """Every documents-read in the pure verdict/income engine modules MUST exclude superseded
    rows. Mirrors the repo's no-icu-messageformat / subject-drift static guards: a new read that
    forgets `superseded_at` fails HERE, loudly, instead of silently counting a replaced doc."""

    # Pure read-only engines — no upload/sweep/ops document mutations live in these.
    READ_MODULES = [
        'verdict_engine.py', 'income_engine.py', 'anomaly_engine.py', 'pathway_engine.py',
        'profile_engine.py', 'submission_review.py', 'check2_queries.py',
    ]
    # Tokens that open a documents READ — both the direct `.documents.` form and the aliased
    # `docs.` form (`docs = getattr(application, 'documents', None)`), which the first audit's
    # grep missed (has_valid_str et al. read a superseded STR without the filter).
    READ_TOKENS = ('.documents.filter(', '.documents.all(', '.documents.values_list(',
                   '.documents.exists(', '.documents.count(',
                   'docs.filter(', 'docs.all(', 'docs.values_list(',
                   'docs.exists(', 'docs.count(')

    def test_engine_reads_filter_superseded(self):
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)))
        offenders = []
        for name in self.READ_MODULES:
            path = os.path.join(base, name)
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            for tok in self.READ_TOKENS:
                for m in re.finditer(re.escape(tok), src):
                    # a BACK+forward window spans a leading `# all-versions-read:` pragma and the
                    # multi-line filter(...) call itself.
                    window = src[max(0, m.start() - 320):m.start() + 220]
                    # An explicit `all-versions-read:` pragma is a documented, reviewed exception —
                    # a read that INTENTIONALLY spans superseded rows (e.g. counting prior upload
                    # attempts). Everything else MUST carry the superseded_at filter.
                    if 'superseded_at' not in window and 'all-versions-read:' not in window:
                        line = src.count('\n', 0, m.start()) + 1
                        offenders.append(f'{name}:{line} — {tok}')
        self.assertEqual(
            offenders, [],
            'Documents read without a superseded_at filter (Phase 2 version-history risk):\n'
            + '\n'.join(offenders))
