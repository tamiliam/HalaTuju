"""TD-287 (2026-10-03): the utility bills are read ONCE per income verdict, and the answer is the
answer it always was.

`verdict_engine._verdict_income` reads `_utility_context` (the soft bill / household signals) at its
head; every fall-through into the salary reading — the salary route itself, the absent-STR §6
rule 2 path, and `_stronger_income_fact` — used to read it AGAIN inside `verdict_income_salary`.
Two identical readings, four queries each outside a document snapshot. The caller now hands its
reading down (`utility=`), and the salary reading takes a deep copy of it. Review F5 (same day):
STR PRECEDENCE read them a second time as well, and now takes the same reading.

Two things are pinned, on four household shapes that each reach a different path:

1. **The count** — `_utility_context` runs exactly once per `_verdict_income`.
2. **The answer** — the fact is IDENTICAL to the one the old code gave, which is reproduced by
   forcing `utility=None` (the salary reading reads the bills itself, as before TD-287).

⚠ Every household carries a soft line BOTH readings emit (`household_size_confirm`, five people
described against a stated size of two). Without one, "identical" would compare two empty
contexts and prove nothing — the silent bite that raised TD-287 in the first place.
"""
from unittest import mock

from apps.scholarship import income_engine, verdict_engine
from apps.scholarship import verdict_income_salary as vis_module
from apps.scholarship.tests.test_income_evidence_homes import (
    FATHER_NAME, FATHER_NRIC, IncomeHomesBase, _doc, _str_doc)

MOTHER_NAME = 'Kamala A/P Suppiah'
MOTHER_NRIC = '750808-14-5002'
_SLIP = {'gross_income': 'RM 1,800.00', 'net_income': 'RM 1,800.00', 'period': '08/2026'}
#: Five people described against a stated household size of two → `household_size_confirm`.
_CROWD = [{'relationship': 'grandmother'}, {'relationship': 'uncle'}, {'relationship': 'cousin'}]


class TestTheBillsAreReadOnce(IncomeHomesBase):

    def _crowded(self, app):
        app.profile.household_size = 2
        app.profile.save(update_fields=['household_size'])
        return app

    def salary_route(self):
        app = self._crowded(self._app(route='salary', members=('father',),
                                      other_family_members=_CROWD))
        self._ic(app)
        _doc(app, 'salary_slip', 'father', fields=_SLIP)
        return app

    def absent_str(self):
        """Declared STR, no STR letter, a complete salary cluster → §6 rule 2 (`any_route=True`)."""
        app = self._crowded(self._app(route='str', members=(), earner='father',
                                      other_family_members=_CROWD))
        self._ic(app)
        _doc(app, 'salary_slip', 'father', fields=_SLIP)
        return app

    def raised(self):
        """The mother's STR cluster is incomplete (no birth certificate) → `_stronger_income_fact`,
        and the father's payslip raises it."""
        app = self._crowded(self._app(route='str', members=(), earner='mother',
                                      other_family_members=_CROWD))
        _doc(app, 'parent_ic', '', name=MOTHER_NAME, nric=MOTHER_NRIC)
        self._ic(app)
        _doc(app, 'salary_slip', 'father', fields=_SLIP)
        _str_doc(app, status='Lulus', year='2026',
                 recipient_name=MOTHER_NAME, recipient_nric=MOTHER_NRIC)
        return app

    def str_settled(self):
        """A current, genuine STR in the linked father's name → STR PRECEDENCE settles it before any
        route (review F5: this path read the bills twice too)."""
        app = self._crowded(self._app(route='str', members=(), earner='father',
                                      other_family_members=_CROWD))
        self._ic(app)
        _str_doc(app, status='Lulus', year='2026',
                 recipient_name=FATHER_NAME, recipient_nric=FATHER_NRIC)
        return app

    SHAPES = ('salary_route', 'absent_str', 'raised', 'str_settled')
    #: The evidence code that proves each shape reached the path it is named for.
    REACHED = {'salary_route': 'income_proof_present', 'absent_str': 'income_proof_present',
               'raised': 'income_proof_present', 'str_settled': 'str_verified'}

    def _counted(self, app):
        """`_verdict_income(app)` with every call to `_utility_context` counted, through BOTH
        names it is bound under (the salary module imports it at load time)."""
        real = verdict_engine._utility_context
        counter = mock.Mock(side_effect=real)
        with mock.patch.object(verdict_engine, '_utility_context', counter), \
                mock.patch.object(vis_module, '_utility_context', counter):
            fact = verdict_engine._verdict_income(app)
        return fact, counter.call_count

    def _as_before_td287(self, app):
        """The old behaviour: the salary reading and STR precedence ignore the caller's reading."""
        real = vis_module.verdict_income_salary

        def reads_its_own(*args, **kwargs):
            if len(args) > 4:                    # `utility` passed positionally
                args = args[:4]
            kwargs['utility'] = None
            return real(*args, **kwargs)
        real_settle = verdict_engine._str_precedence_verdict

        def settles_on_its_own(application, utility=None):
            return real_settle(application, None)
        with mock.patch.object(vis_module, 'verdict_income_salary', reads_its_own),                 mock.patch.object(verdict_engine, '_str_precedence_verdict', settles_on_its_own):
            return verdict_engine._verdict_income(app)

    def test_each_shape_reaches_the_salary_reading_and_carries_a_shared_line(self):
        """The control: every shape really falls through, and really has something to share."""
        for shape in self.SHAPES:
            with self.subTest(shape=shape):
                app = getattr(self, shape)()
                fact = verdict_engine._verdict_income(app)
                codes = [i['code'] for i in fact['evidence']]
                self.assertIn(self.REACHED[shape], codes, 'never reached the path it is named for')
                self.assertIn('household_size_confirm', codes, 'nothing for the two to share')

    def test_the_bills_are_read_once_per_verdict(self):
        for shape in self.SHAPES:
            with self.subTest(shape=shape):
                _fact, calls = self._counted(getattr(self, shape)())
                self.assertEqual(calls, 1, f'{shape}: `_utility_context` ran {calls} times')

    def test_the_answer_is_the_one_the_old_code_gave(self):
        for shape in self.SHAPES:
            with self.subTest(shape=shape):
                app = getattr(self, shape)()
                self.assertEqual(verdict_engine._verdict_income(app), self._as_before_td287(app))

    def test_the_salary_fact_never_shares_an_item_with_the_callers_reading(self):
        """The deep copy: a later edit to one fact's item must not reach the other's."""
        app = self.salary_route()
        utility = verdict_engine._utility_context(app)
        present = set(app.documents.values_list('doc_type', flat=True))
        fact = vis_module.verdict_income_salary(
            app, income_engine.student_name_for_link(app), present, utility=utility)
        shared = [i for i in fact['evidence'] for u in utility if i is u]
        self.assertEqual(shared, [])
        self.assertIn(utility[0], fact['evidence'])         # ...but equal, item for item
