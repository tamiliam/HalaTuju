"""Contract module Sprint 5 — the render carries all the template's legal content.

The permanent guard left after the constants-removal gate: a deployed template's rendered
agreement contains every clause heading+body, the title/preamble, and the Schedule 1
payment table (with the STPM exam-month gap) — proving nothing legal is lost now that the
render is template-only. (The one-time constants-vs-template equality gate was proven
before the hard-coded bursary.py constants were removed — see the S5 retrospective.)
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship import bursary, contracts
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

from apps.scholarship.tests.contract_helpers import brightpath_org, make_deployable


def _deployed():
    t = make_deployable('2026-parity')
    contracts.submit_for_deployment(t)
    return contracts.deploy(t, is_super=True)


class TestTemplateRenderCarriesContent(TestCase):
    def setUp(self):
        self.tmpl = _deployed()
        self.cohort = ScholarshipCohort.objects.create(
            code='par', name='B40', year=2026, owning_organisation=brightpath_org())
        p = StudentProfile.objects.create(supabase_user_id='par-1', name='Stu', exam_type='spm', grades={})
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='awarded', chosen_pathway='stpm',
            chosen_programme={'course_name': 'Diploma in Nursing', 'institution': 'Politeknik KL'})

    def _render(self):
        p = bursary.particulars_for(self.app, self.tmpl, 'en')
        return bursary.render_agreement_html(
            self.app, p, student={'name': 'Stu', 'nric': ''}, guarantor={'name': 'Guar'},
            foundation={'name': p['foundation_signatory_name'], 'title': '', 'nric': ''},
            witness={'by': ''}, template=self.tmpl)

    def test_render_carries_every_clause_and_schedule(self):
        html = self._render()
        for clause in self.tmpl.clauses.all():
            self.assertIn(clause.heading_en, html)
            self.assertIn(clause.body_en.split('\n\n')[0][:40], html)
        self.assertIn(self.tmpl.title_en, html)
        self.assertIn(self.tmpl.preamble_en[:40], html)
        # Schedule 1 table + the STPM Dec/Jun gap; English-authoritative notice; no DRAFT banner.
        self.assertIn('Schedule 1', html)
        self.assertIn('Exam month', html)
        self.assertIn('authoritative', html)
        self.assertNotIn('DRAFT', html)
