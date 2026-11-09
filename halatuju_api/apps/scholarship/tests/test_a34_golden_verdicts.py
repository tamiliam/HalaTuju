"""Audit sprint A3.4 — GOLDEN CASES for the verdict and resolution engines, recorded BEFORE the split.

A3.4 splits ``verdict_engine.py`` and breaks up three long functions — ``_verdict_income``,
``resolution.doc_match_verdict`` and ``help_engine.verdict_for_document`` — by MOVING code, never
changing it. These are eligibility and money paths, so "the tests still pass" is not enough: every
branch is driven and its EXACT answer (status, evidence and unresolved items with their params, the
help code, the Action Centre verdict, and what each function handed to its collaborators) is compared
with ``fixtures/a34_golden_verdicts.json``, which was written on the untouched tree. This file holds
the four facts (income, identity, pathway, the genuineness caps) and the whole verdict; the two
per-document verdicts are in ``test_a34_golden_documents.py``.

⚠ NEVER RE-RECORD THIS FILE TO MAKE A REFACTOR GREEN. A difference here is a behaviour change in an
eligibility path, and it stops the sprint. Re-record (``UPDATE_A34_GOLDEN=1``, run serially) only for a
deliberate, owner-approved rule change, and say so in the commit.

How the branches are reached, so the fixture stays valid across the move:
  * collaborators are patched AT THEIR SOURCE (``apps.scholarship.income_engine.*``,
    ``pathway_engine.*``, ``academic_engine.*``, ``offer_pathway.*``, ``verdict_income_salary.*``) —
    every one is looked up at call time by the code under test, before and after the split;
  * everything else (the IC matchers, read-error rules, person-red keys, genuineness bands, the STR
    stranger rule, the ladder) runs for real.

All people here are obviously fake. No real student data, no database dump.
"""
import inspect
import json
import os
import pathlib
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.scholarship import verdict_engine
from apps.scholarship import verdict_income_salary as vis_module
from apps.scholarship.tests.factories import create_document, make_application, make_cohort, make_student

GOLDEN = pathlib.Path(__file__).parent / 'fixtures' / 'a34_golden_verdicts.json'
UPDATE = os.environ.get('UPDATE_A34_GOLDEN') == '1'

STUDENT = 'ANBU A/L DEVARAJ'
STUDENT_NRIC = '080808-14-0808'
FATHER = 'DEVARAJ A/L MUNUSAMY'
MOTHER = 'KAMALA A/P SUPPIAH'
#: 2100-01-01 — an IC second-opinion window that is still open whenever this runs.
_FAR = 4102444800.0
_DEFERRED = {'ic_second_opinion_error': 'gemini 503', 'ic_second_opinion_until': _FAR}

IE = 'apps.scholarship.income_engine'
PE = 'apps.scholarship.pathway_engine'
AE = 'apps.scholarship.academic_engine'
OP = 'apps.scholarship.offer_pathway'
VIS = 'apps.scholarship.verdict_income_salary'


# ── recording helpers ────────────────────────────────────────────────────────────────────────

def _norm(obj):
    """A JSON-stable picture of any value a function returned or was handed."""
    if isinstance(obj, dict):
        return {str(k): _norm(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_norm(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_norm(v) for v in obj)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, 'doc_type'):
        return f'<doc:{obj.doc_type}>'
    if hasattr(obj, 'income_route') or type(obj).__name__ == 'ScholarshipApplication':
        return '<application>'
    return f'<{type(obj).__name__}>'


class _Calls:
    """Fakes that answer a fixed value and remember what they were handed (by parameter name when
    the real signature is known, so a positional-vs-keyword difference is not a false alarm)."""

    def __init__(self):
        self.log = []

    def fake(self, name, answer, real=None, skip_first=True):
        sig = inspect.signature(real) if real is not None else None

        def _f(*args, **kwargs):
            if sig is not None:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                got = dict(bound.arguments)
                got.pop('application', None)
            else:
                got = {'args': list(args[1:] if skip_first else args), 'kwargs': kwargs}
            self.log.append([name, _norm(got)])
            return answer(*args, **kwargs) if callable(answer) else answer
        return _f


def _patched(stack, patches):
    for target, value in patches.items():
        stack.enter_context(mock.patch(target, value))


def _mkdoc(app, doc_type, member='', *, vf=None, name='', nric='', run=True, error=''):
    return create_document(
        application=app, doc_type=doc_type, household_member=member,
        storage_path=f'fake/a34/{doc_type}/{member or "household"}/{app.id}',
        vision_fields=vf or {}, vision_name=name, vision_nric=nric, vision_error=error,
        vision_run_at=timezone.now() if run else None)


def _str_fields(status='Lulus', year=None, name=FATHER, nric='700707-14-5001'):
    return {'fields': {'status': status, 'year': str(timezone.localdate().year) if year is None else year,
                       'source_type': 'semakan_status', 'recipient_name': name,
                       'recipient_nric': nric}}


def _doc(doc_type, *, vf=None, member='', run=True, error='', nric='', name='', name_match='',
         address_match='', app=None):
    """A stand-in document — only the attributes the three functions read."""
    return SimpleNamespace(
        doc_type=doc_type, vision_fields=vf if vf is not None else {}, household_member=member,
        vision_run_at=timezone.now() if run else None, vision_error=error, vision_nric=nric,
        vision_name=name, vision_name_match=name_match, vision_address_match=address_match,
        application=app or _fake_app())


def _fake_app(earner='father', route='str'):
    return SimpleNamespace(profile=SimpleNamespace(name=STUDENT, nric=STUDENT_NRIC),
                           income_earner=earner, income_route=route)


def _load():
    if GOLDEN.exists():
        return json.loads(GOLDEN.read_text(encoding='utf-8'))
    return {}


class _GoldenBase(TestCase):
    SECTION = ''

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(year=2026)

    def app(self, *, route='str', earner='father', **extra):
        student = make_student(name=STUDENT, nric=STUDENT_NRIC)
        return make_application(
            'submitted', cohort=self.cohort, student=student, income_route=route,
            income_earner=earner, income_working_members=[], income_declared={},
            father_name=FATHER, father_occupation='private', mother_name=MOTHER,
            mother_occupation='homemaker', other_family_members=[], siblings_in_school=0,
            siblings_in_tertiary=0, **extra)

    def check(self, results):
        """Compare (or, under UPDATE_A34_GOLDEN=1, record) this section's answers."""
        data = _load()
        if UPDATE:
            data[self.SECTION] = results
            GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + '\n',
                              encoding='utf-8')
            return
        self.assertIn(self.SECTION, data, f'{GOLDEN.name} has no "{self.SECTION}" section')
        golden = data[self.SECTION]
        self.assertEqual(sorted(results), sorted(golden), 'the case list itself changed')
        for case in sorted(golden):
            with self.subTest(case=case):
                self.assertEqual(results[case], golden[case])


# ── 1. The income fact (`verdict_engine._verdict_income`) ─────────────────────────────────────

_IC = SimpleNamespace(doc_type='parent_ic', vision_name=FATHER, vision_fields={})
_IC_DEFERRED_NAMED = SimpleNamespace(doc_type='parent_ic', vision_name=FATHER, vision_fields=_DEFERRED)
_IC_DEFERRED_BLANK = SimpleNamespace(doc_type='parent_ic', vision_name='', vision_fields=_DEFERRED)
_IC_BLANK = SimpleNamespace(doc_type='parent_ic', vision_name='', vision_fields={})


def _sc(current='current', name='match', nric='match'):
    return {'current_status': current, 'name_status': name, 'nric_status': nric}


#: name → (earner, {knob: value}). Knobs: ic, link (father/mother/guardian answer), chain,
#: satisfied, str (a STR letter on file), sc (student_str_check answer), bc / letter
#: ('ok' | 'wrong' | 'unreadable'), stands, salary (status, has-proof), tested.
INCOME_CASES = {
    'i04_salary_route':                 ('father', {'route': 'salary'}),
    'i05_wizard_not_walked':            ('', {}),
    'i06_no_str_salary_satisfied':      ('father', {'satisfied': True}),
    'i07_no_str_no_salary':             ('father', {}),
    'i08_ic_missing_str_stands_no':     ('father', {'ic': None, 'str': True}),
    'i09_ic_missing_salary_raises':     ('father', {'ic': None, 'str': True, 'stands': True,
                                                    'salary': ('review', True)}),
    'i10_ic_missing_salary_no_proof':   ('father', {'ic': None, 'str': True, 'stands': True,
                                                    'salary': ('verified', False)}),
    'i11_ic_missing_salary_not_better': ('father', {'ic': None, 'str': True, 'stands': True,
                                                    'salary': ('gap', True)}),
    'i12_ic_deferred_unnamed':          ('father', {'ic': _IC_DEFERRED_BLANK, 'str': True}),
    'i13_ic_unreadable':                ('father', {'ic': _IC_BLANK, 'str': True}),
    'i14_father_link_mismatch':         ('father', {'str': True, 'link': 'mismatch'}),
    'i15_father_mismatch_deferred_ic':  ('father', {'ic': _IC_DEFERRED_NAMED, 'str': True,
                                                    'link': 'mismatch'}),
    'i16_father_link_unknown':          ('father', {'str': True, 'link': 'unknown'}),
    'i17_unknown_not_means_tested':     ('father', {'str': True, 'link': 'unknown', 'tested': False}),
    'i18_father_chain_upgrade':         ('father', {'str': True, 'link': 'mismatch', 'chain': True}),
    'i18b_father_verified':             ('father', {'str': True}),
    'i19_mother_no_bc':                 ('mother', {'str': True}),
    'i20_mother_bc_unreadable':         ('mother', {'str': True, 'bc': 'unreadable'}),
    'i21_mother_bc_wrong_type':         ('mother', {'str': True, 'bc': 'wrong'}),
    'i22_mother_verified':              ('mother', {'str': True, 'bc': 'ok'}),
    'i23_mother_bc_mismatch':           ('mother', {'str': True, 'bc': 'ok', 'link': 'mismatch'}),
    'i23b_mother_mismatch_deferred':    ('mother', {'ic': _IC_DEFERRED_NAMED, 'str': True, 'bc': 'ok',
                                                    'link': 'mismatch'}),
    'i24_guardian_no_letter':           ('guardian', {'str': True}),
    'i25_guardian_letter_unreadable':   ('guardian', {'str': True, 'letter': 'unreadable'}),
    'i26_guardian_letter_wrong_type':   ('guardian', {'str': True, 'letter': 'wrong'}),
    'i27_guardian_verified':            ('guardian', {'str': True, 'letter': 'ok'}),
    'i28_guardian_link_mismatch':       ('guardian', {'str': True, 'letter': 'ok', 'link': 'mismatch'}),
    'i28b_guardian_chain_ignored':      ('guardian', {'str': True, 'letter': 'ok', 'link': 'mismatch',
                                                      'chain': True}),
    'i29_str_stale':                    ('father', {'str': True, 'sc': _sc('stale')}),
    'i30_str_future':                   ('father', {'str': True, 'sc': _sc('future')}),
    'i31_str_rejected':                 ('father', {'str': True, 'sc': _sc('rejected')}),
    'i32_str_unconfirmed':              ('father', {'str': True, 'sc': _sc('unconfirmed')}),
    'i33_str_wrong_type':               ('father', {'str': True, 'sc': _sc('wrong_type')}),
    'i34_str_unreadable':               ('father', {'str': True, 'sc': _sc('unreadable')}),
    'i35_str_unknown_named':            ('father', {'str': True, 'sc': _sc('unknown')}),
    'i35b_str_unknown_no_ref':          ('father', {'str': True, 'sc': _sc('unknown', 'no_ref', 'no_ref')}),
    'i36_str_recipient_mismatch':       ('father', {'str': True, 'sc': _sc('current', 'mismatch', 'no_ref')}),
    'i37_mismatch_salary_raises':       ('father', {'str': True, 'sc': _sc('current', 'mismatch', 'no_ref'),
                                                    'stands': True, 'salary': ('verified', True)}),
    'i38_str_present_unverified':       ('father', {'str': True, 'sc': _sc('current', 'no_ref', 'no_ref')}),
    'i38b_str_check_none':              ('father', {'str': True, 'sc': None}),
    'i39_stale_salary_raises':          ('father', {'str': True, 'sc': _sc('stale'), 'stands': True,
                                                    'salary': ('review', True)}),
    'i40_stale_and_ic_missing':         ('father', {'ic': None, 'str': True, 'sc': _sc('stale'),
                                                    'stands': True, 'salary': ('recommend', True)}),
    'i41_rejected_and_link_mismatch':   ('father', {'str': True, 'sc': _sc('rejected'), 'link': 'mismatch'}),
}


class TestGoldenIncome(_GoldenBase):
    SECTION = 'income'

    def _income_case(self, earner, knobs):
        route = knobs.get('route', 'str' if earner else '')
        app = self.app(route=route, earner=earner)
        if knobs.get('str'):
            _mkdoc(app, 'str', vf=_str_fields())
        bc = knobs.get('bc')
        if bc:
            _mkdoc(app, 'birth_certificate', vf={
                'fields': {'bc_child_name': STUDENT, 'bc_mother_name': MOTHER, 'bc_father_name': FATHER},
                **({'authenticity': {'status': 'not_birth_certificate'}} if bc == 'wrong' else {})})
        letter = knobs.get('letter')
        if letter:
            _mkdoc(app, 'guardianship_letter', vf={
                'fields': {'guardian_name': FATHER, 'ward_name': STUDENT},
                **({'authenticity': {'status': 'not_guardianship_letter'}} if letter == 'wrong' else {})})
        calls = _Calls()
        status, proof = knobs.get('salary', ('recommend', True))

        def salary_fact(*a, **k):
            return {'fact': 'income', 'status': status,
                    'evidence': [{'code': 'income_proof_present', 'params': {}}] if proof else [],
                    'unresolved': [{'code': 'golden_salary_reading', 'params': {}}]}

        def headroom(application, earner_, evidence, review):
            return {'fact': 'income', 'status': 'recommend', 'evidence': list(evidence),
                    'unresolved': list(review) + [{'code': 'golden_headroom_reading', 'params': {}}]}

        link = knobs.get('link', 'match')
        unreadable = {'bc': bc == 'unreadable', 'letter': letter == 'unreadable'}
        patches = {
            f'{IE}.household_str_status': calls.fake('household_str_status', (None, None)),
            f'{IE}.salary_income_satisfied': calls.fake('salary_income_satisfied',
                                                        knobs.get('satisfied', False)),
            f'{IE}._member_ic_doc': calls.fake('_member_ic_doc', knobs.get('ic', _IC)),
            f'{IE}.father_link': calls.fake('father_link', link, skip_first=False),
            f'{IE}.mother_relationship': calls.fake('mother_relationship', link, skip_first=False),
            f'{IE}.guardian_link': calls.fake('guardian_link', link, skip_first=True),
            f'{IE}.chain_verified_earner': calls.fake('chain_verified_earner', knobs.get('chain', False)),
            f'{IE}.relationship_doc_unreadable': lambda d: unreadable[
                'bc' if d.doc_type == 'birth_certificate' else 'letter'],
            f'{IE}.student_str_check': calls.fake('student_str_check', knobs.get('sc', _sc()),
                                                  skip_first=True),
            f'{IE}.income_test_configured': lambda a: knobs.get('tested', True),
            f'{IE}.utility_per_capita': lambda a: {'signal': 'b40', 'per_capita': 123.4},
            f'{IE}.utility_hardship': lambda a: True,
            f'{IE}.unemployment_corroborated_members': lambda a: [],
            f'{IE}.household_size_shortfall': lambda a: None,
            f'{VIS}.verdict_income_salary': calls.fake(
                'verdict_income_salary', salary_fact, real=vis_module.verdict_income_salary),
            f'{VIS}._failed_str_headroom_fact': calls.fake(
                '_failed_str_headroom_fact', headroom, real=vis_module._failed_str_headroom_fact),
            f'{VIS}.salary_evidence_stands_without_the_str': calls.fake(
                'salary_evidence_stands_without_the_str', knobs.get('stands', False)),
        }
        with ExitStack() as stack:
            _patched(stack, patches)
            fact = verdict_engine._verdict_income(app)
        return {'fact': _norm(fact), 'calls': calls.log}

    def _precedence_cases(self):
        """The STR PRECEDENCE paths, entirely real (no patches)."""
        out = {}
        for case, fields, ic in (
                ('i01_precedence_current', _str_fields(), True),
                ('i02_precedence_unconfirmed', _str_fields(year=''), True),
                ('i03_precedence_other_parents_str', _str_fields(name=MOTHER, nric='750808-14-5002'),
                 False)):
            app = self.app()
            _mkdoc(app, 'parent_ic', 'father', name=FATHER, nric='700707-14-5001')
            if not ic:
                _mkdoc(app, 'parent_ic', 'mother', name=MOTHER, nric='750808-14-5002')
            _mkdoc(app, 'str', vf=fields)
            out[case] = {'fact': _norm(verdict_engine._verdict_income(app))}
        return out

    def test_income_fact_is_unchanged(self):
        results = self._precedence_cases()
        for case, (earner, knobs) in INCOME_CASES.items():
            results[case] = self._income_case(earner, knobs)
        self.check(results)


# ── 2. Identity, pathway, the genuineness caps, and the whole verdict ─────────────────────────

def _chk(**over):
    base = {'name': 'match', 'ic': 'match', 'programme': 'Asasi Sains', 'institution': 'UM',
            'pathway': 'match', 'declared_programme': '', 'declared_institution': '', 'bidang': '',
            'issuer': ''}
    base.update(over)
    return base


_PISMP_COURSE = {'course_id': 'PISMP-SJKT-BT', 'course_name': 'Bahasa Tamil SJKT', 'aliran': 'SJKT'}

#: name → (chk, app attributes, knobs). Knobs: offer (False = none on file), vf (offer
#: vision_fields), hearing, types (detect_pathway_type answer), resolved (resolve_pismp_course),
#: resolvable.
PATHWAY_CASES = {
    'p01_no_offer_declared':    (None, {'chosen_pathway': 'Matriculation'}, {'offer': False}),
    'p02_no_offer_undeclared':  (None, {}, {'offer': False}),
    'p03_offer_name_mismatch':  (_chk(name='mismatch'), {}, {}),
    'p03b_offer_ic_mismatch':   (_chk(ic='mismatch'), {}, {}),
    'p04_offer_not_read_yet':   (_chk(name='pending', ic='pending'), {}, {'vf': {}}),
    'p05_offer_no_identity':    (_chk(name='unreadable', ic='unreadable'), {}, {}),
    'p06_offer_unreadable':     (_chk(name='unreadable', ic='pending', programme='', institution=''),
                                 {}, {}),
    'p07_offer_clean':          (_chk(), {'chosen_pathway': 'Asasi'}, {}),
    'p08_offer_issuer_unchecked': (_chk(), {}, {'vf': {'fields': {'x': 1}, 'student_verdict': 'ok',
                                                       'authenticity': {'status': 'unchecked',
                                                                        'issuer': 'ILP Kuantan'}}}),
    'p09_confirmed':            (_chk(programme='', institution=''), {'confirmed': True}, {}),
    'p10_switch_to_pismp_resolved': (_chk(bidang='Bahasa Tamil'), {'chosen_pathway': 'stpm'},
                                     {'hearing': True, 'types': 'pismp', 'resolved': _PISMP_COURSE}),
    'p11_switch_to_pismp_hint': (_chk(bidang='Matematik'), {'chosen_pathway': 'stpm'},
                                 {'hearing': True, 'types': 'pismp'}),
    'p12_switch_to_matric':     (_chk(), {'chosen_pathway': 'stpm'}, {'hearing': True, 'types': 'matric'}),
    'p13_same_family_clash':    (_chk(pathway='mismatch', declared_programme='Asasi Sains',
                                      declared_institution='UiTM'),
                                 {'chosen_pathway': 'asasi'}, {'hearing': True, 'types': 'asasi'}),
    'p13b_clash_but_confirmed': (_chk(pathway='mismatch'), {'chosen_pathway': 'asasi', 'confirmed': True},
                                 {'hearing': True, 'types': 'asasi'}),
    'p14_undeclared_resolvable': (_chk(), {}, {'hearing': True, 'types': 'asasi', 'resolvable': True}),
    'p15_undeclared_pismp_unique': (_chk(bidang='Bahasa Tamil', programme='PISMP', institution='IPG'), {},
                                    {'hearing': True, 'types': 'pismp', 'resolved': _PISMP_COURSE}),
    'p16_undeclared_ambiguous': (_chk(), {}, {'hearing': True, 'types': 'asasi'}),
    'p16b_undeclared_pismp_picker': (_chk(bidang='Matematik'), {}, {'hearing': True, 'types': 'pismp'}),
    'p16c_autofilled_pick_is_undeclared': (_chk(), {'chosen_programme': {'course_id': 'X1',
                                                                         'source': 'offer_letter_auto'}},
                                           {'hearing': True, 'types': 'asasi'}),
    'p16d_real_pick_is_declared': (_chk(), {'chosen_programme': {'course_id': 'X1', 'source': 'search'}},
                                   {'hearing': True, 'types': 'asasi', 'resolvable': True}),
    'p17_clean_but_blank_offer': (_chk(programme='', institution=''), {}, {}),
}

_FAMILY = {'stpm': 'preu', 'matric': 'preu', 'asasi': 'preu', 'pismp': 'pismp'}


class TestGoldenFacts(_GoldenBase):
    SECTION = 'facts'

    def _pathway_case(self, chk, attrs, knobs):
        app = self.app()
        for k in ('chosen_pathway', 'intended_pathway', 'pre_u_track'):
            setattr(app, k, attrs.get(k, ''))
        app.chosen_programme = attrs.get('chosen_programme', {})
        app.pathway_confirmed_at = timezone.now() if attrs.get('confirmed') else None
        if knobs.get('offer', True):
            _mkdoc(app, 'offer_letter', vf=knobs.get('vf', {'fields': {'programme': 'x'},
                                                              'student_verdict': 'ok'}))
        calls = _Calls()
        types = knobs.get('types', 'asasi')
        patches = {
            f'{PE}.student_offer_check': lambda d: dict(chk or {}),
            f'{PE}.offer_hearing_ok': lambda d: knobs.get('hearing', False),
            f'{OP}.detect_pathway_type': calls.fake('detect_pathway_type', types, skip_first=False),
            f'{OP}.pathway_family': lambda t: {'matriculation': 'preu'}.get(t, _FAMILY.get(t, '')),
            f'{OP}.resolve_pismp_course': calls.fake('resolve_pismp_course', knobs.get('resolved'),
                                                     skip_first=False),
            f'{OP}.infer_pismp_aliran': lambda profile: 'SK',
            f'{OP}.offer_is_resolvable': calls.fake('offer_is_resolvable', knobs.get('resolvable', False),
                                                    skip_first=False),
        }
        with ExitStack() as stack:
            _patched(stack, patches)
            fact = verdict_engine._verdict_pathway(app)
        return {'fact': _norm(fact), 'calls': calls.log}

    def _identity_cases(self):
        out = {}
        for case, kw in (
                ('id01_no_ic', None),
                ('id02_match', {'nric': STUDENT_NRIC, 'name': STUDENT}),
                ('id03_truncated_name', {'nric': STUDENT_NRIC, 'name': 'ANBU A/L'}),
                ('id04_name_mismatch', {'nric': STUDENT_NRIC, 'name': 'MEENA A/P RAJU'}),
                ('id05_nric_mismatch', {'nric': '010101-01-0101', 'name': STUDENT}),
                ('id06_service_down', {'error': 'Vision API quota exceeded'}),
                ('id07_unreadable_image', {'error': 'empty image'}),
                ('id07b_no_nric_read', {'name': STUDENT}),
                ('id08_deferred_name', {'nric': STUDENT_NRIC, 'name': 'MEENA A/P RAJU', 'vf': _DEFERRED}),
                ('id09_no_name_read', {'nric': STUDENT_NRIC})):
            app = self.app()
            if kw is not None:
                kw = dict(kw)
                _mkdoc(app, 'ic', vf=kw.pop('vf', None), **kw)
            out[case] = _norm(verdict_engine._verdict_identity(app))
        return out

    def _caps_cases(self):
        out = {}

        def fact(status='verified', unresolved=()):
            return {'fact': 'income', 'status': status, 'evidence': [],
                    'unresolved': [{'code': c, 'params': {}} for c in unresolved]}
        for case, route, earner, docs, f, sc in (
                ('c01_str_suspect', 'str', 'father', {'str': 'suspect'}, fact(), None),
                ('c02_str_wrong_type_not_doubled', 'str', 'father', {'str': 'suspect'}, fact(),
                 _sc('wrong_type')),
                ('c03_mother_bc_suspect', 'str', 'mother', {'str': 'genuine', 'birth_certificate': 'suspect'},
                 fact('recommend'), None),
                ('c04_mother_bc_already_ticketed', 'str', 'mother',
                 {'str': 'genuine', 'birth_certificate': 'suspect'},
                 fact('review', ['birth_cert_not_genuine']), None),
                ('c05_salary_route_never_capped', 'salary', 'father', {'str': 'suspect'}, fact(), None),
                ('c06_already_not_genuine', 'str', 'father', {'str': 'suspect'},
                 fact('review', ['document_not_genuine']), None),
                ('c07_str_genuine', 'str', 'father', {'str': 'genuine'}, fact(), None),
                ('c08_str_not_an_str', 'str', 'father', {'str': 'not_str'}, fact('gap'), None)):
            app = self.app(route=route, earner=earner)
            for dt, st in docs.items():
                vf = _str_fields() if dt == 'str' else {'fields': {}}
                vf['authenticity'] = {'status': st}
                _mkdoc(app, dt, vf=vf)
            with ExitStack() as stack:
                if sc is not None:
                    stack.enter_context(mock.patch(f'{IE}.student_str_check', lambda d, sc=sc: dict(sc)))
                capped = verdict_engine._apply_genuineness_caps(app, [f])
            out[case] = _norm(capped)
        return out

    def _whole_verdict_cases(self):
        out = {}
        app = self.app(chosen_pathway='Matriculation')
        out['b01_empty_file'] = _norm(verdict_engine.build_verdict(app))
        app = self.app(chosen_pathway='Matriculation')
        _mkdoc(app, 'ic', nric=STUDENT_NRIC, name=STUDENT)
        _mkdoc(app, 'parent_ic', 'father', name=FATHER, nric='700707-14-5001')
        _mkdoc(app, 'str', vf={**_str_fields(), 'authenticity': {'status': 'genuine'}})
        out['b02_identity_and_settled_str'] = _norm(verdict_engine.build_verdict(app))
        return out

    def test_identity_pathway_caps_and_whole_verdict_are_unchanged(self):
        results = {}
        results.update(self._identity_cases())
        for case, (chk, attrs, knobs) in PATHWAY_CASES.items():
            results[case] = self._pathway_case(chk, attrs, knobs)
        results.update(self._caps_cases())
        results.update(self._whole_verdict_cases())
        self.check(results)
