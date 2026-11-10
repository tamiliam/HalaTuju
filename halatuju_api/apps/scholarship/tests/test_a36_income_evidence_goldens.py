"""
Audit sprint A3.6, review follow-up — golden readings of the documented-income line of the AI sponsor
profile (`_income_evidence`, now `profile_inputs.py`).

The first golden file (`test_a36_profile_goldens.py`) has no readable salary slip in any case, so the
"documented income" branch of `_income_evidence` was never reached: a mutation run showed it could be
changed without any golden noticing. These cases give a household a readable slip or EPF statement and
pin the line the model is told, and the prompt line that carries it.

Taken on the pre-split code (5c37b085f), passes unchanged after the split. Gemini is never called: only
`_build_prompt` and `_income_evidence` run, both pure reads, and the API key is blanked as a fence.
"""
import json
from pathlib import Path

from django.test import TestCase, override_settings

from apps.scholarship import profile_engine
from apps.scholarship.tests.factories import create_document, make_application, make_cohort, make_student

GOLDEN_FILE = Path(__file__).resolve().parent / 'fixtures' / 'a36_income_evidence_goldens.json'

_SLIP = {'gross_income': 'RM 2,400.00', 'net_income': 'RM 2,150.00', 'period': '08/2026'}
_EPF = {'employee_contribution_total': 'RM 1,188.00', 'months_counted': '6', 'statement_date': '07/2026'}


def _doc(app, doc_type, member, fields):
    return create_document(application=app, doc_type=doc_type, household_member=member,
                           storage_path=f'fake/{doc_type}/{member}/{app.id}',
                           vision_fields={'fields': dict(fields)})


def read_income(app):
    """What the model is told about documented income, and the prompt line that carries it."""
    line = next(ln for ln in profile_engine._build_prompt(app).splitlines()
                if ln.startswith('Documented income'))
    return {'income_evidence': profile_engine._income_evidence(app), 'prompt_line': line}


@override_settings(GEMINI_API_KEY='')
class TestA36IncomeEvidenceGoldens(TestCase):
    @classmethod
    def setUpTestData(cls):
        cohort = make_cohort(code='a36i', name='B40', year=2026)

        def app(**kw):
            return make_application('submitted', cohort=cohort, student=make_student(), **kw)

        cls.cases = {}
        # No document at all: the model is told to fall back to the reported figure.
        cls.cases['none_on_file'] = app(income_route='salary', income_working_members=['father'])
        # A readable salary slip on the salary route.
        a = app(income_route='salary', income_working_members=['father'])
        _doc(a, 'salary_slip', 'father', _SLIP)
        cls.cases['father_slip'] = a
        # Slip + EPF for two members; the earner is named and not yet in the member list.
        a = app(income_route='salary', income_working_members=['father'], income_earner='mother')
        _doc(a, 'salary_slip', 'father', _SLIP)
        _doc(a, 'epf', 'mother', _EPF)
        cls.cases['father_slip_mother_epf'] = a
        # The STR route: the earner's own slip counts as documented income too.
        a = app(income_route='str', income_working_members=[], income_earner='mother')
        _doc(a, 'salary_slip', 'mother', _SLIP)
        cls.cases['str_route_earner_slip'] = a

    def test_documented_income_lines(self):
        actual = {name: read_income(a) for name, a in self.cases.items()}
        expected = json.loads(GOLDEN_FILE.read_text(encoding='utf-8')) if GOLDEN_FILE.exists() else {}
        assert actual == expected, json.dumps(actual, indent=1, sort_keys=True, ensure_ascii=False)
