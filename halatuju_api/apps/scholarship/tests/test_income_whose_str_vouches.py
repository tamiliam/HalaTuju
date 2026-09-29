"""TD-285 — `has_valid_str` learns to ask WHOSE STR it is (owner ruling, 2026-09-29).

**The ruling.** The owner's R5 of 2026-09-19 — *"only the family's own STR count"* — was applied
at the submission gate by F8 and at the verdict fall-through by the audit of 2026-09-21, but NOT
to the predicate that decides whether a household's STR vouches for a TYPED monthly figure.
`income_engine.has_valid_str` asked one question of the latest STR — is its currency `current` /
`unconfirmed`? — and never *whose* it was. On 2026-09-29 the owner chose option 1: *close it now,
the F8 way.* A POSITIVELY MISMATCHED STR (F8's `str_recipient_is_stranger`: a recipient that
matches no household member by name OR NRIC) no longer vouches for anything; an STR whose
recipient simply did not READ still does (F8 rule 1: **absence is not a mismatch**).

**What this file is.** A characterisation matrix of the FOUR callers TD-285 named, pinned on the
UNTOUCHED tree first and then held byte-identical across the change, row by row:

  (a) `income_declared_gaps`        — the Check-2 declared-wage ask and its STR short-circuit;
  (b) `earner_monthly_income` → `income_per_capita` → `income_headroom`, plus the two readers
      that print it — `profile_engine._income_evidence` and the household reconciliation tick;
  (c) `followups.high_utility_expense_context`'s `on_str` — which picks the STUDENT's high-utility
      clarify in Check 2, so it is pinned as codes and as the email in sections 5 and 6;
  (d) the income fact itself — band, asks and evidence codes, which is where
      `income_declared_accepted_str` vs `_evidenced` is rendered.

plus the live submission gate (`income_doc_blockers`) and, in its own class, the frozen gate
(`application_completeness`), neither of which may move.

**How a moved row is written.** `BEFORE` is what every row read on the untouched tree
(`cef458a7`), and it is never edited. `MOVED` names the rows the ruling moves and, for each, only
the readings that changed, as `(before, after)`. The tests assert that (1) every row not in
`MOVED` reads exactly `BEFORE`; (2) every row in `MOVED` reads `BEFORE` with just those readings
replaced; (3) the `before` half of every `MOVED` entry IS what `BEFORE` says, so the record of
what changed cannot drift from the record of what was; and (4) `MOVED` holds ONLY rows whose STR
provably names a stranger while a household IC is on file — and every such row. The moved set is
asserted, not argued.

Personal data is obviously fake.
"""
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship import income_engine, profile_engine, services, verdict_engine
from apps.scholarship.income_declared_gaps import declared_income_gaps
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.test_income_evidence_homes import (
    FATHER_NAME, FATHER_NRIC, STUDENT_NAME, _doc, _str_doc)

STRANGER_NAME = 'Roslan Bin Ahmad'
STRANGER_NRIC = '880808-10-5533'
MOTHER_NAME = 'Kamala A/P Suppiah'
MOTHER_NRIC = '750808-14-5002'
#: The household ICs a state may carry. The application records a father (private-sector) and a
#: mother (homemaker), so the STR ROSTER is {father, mother} in every state (owner's F1 ruling).
#: `ic -> (member, what its IC read: name, nric)`. The `*_only` variants are an IC on file that read
#: ONE field — review finding F-A: "read" is per FIELD, not per IC.
_ICS = {'father': ('father', FATHER_NAME, FATHER_NRIC), 'mother': ('mother', MOTHER_NAME, MOTHER_NRIC),
        'mother_nric_read': ('mother', '', MOTHER_NRIC),
        'mother_name_read': ('mother', MOTHER_NAME, '')}
_F, _FM = ('father',), ('father', 'mother')

#: The typed monthly figure. Five at home, so 1500 is RM300 a head — comfortably B40, which makes
#: an ACCEPTED figure visible as a whole band rather than a shade.
DECLARED = 1500
HOUSEHOLD_SIZE = 5

_STRANGER = dict(recipient_name=STRANGER_NAME, recipient_nric=STRANGER_NRIC)

#: `state -> (the STR on file, or None; whose ICs are on file)`. The roster is {father, mother}
#: throughout, so `_F` is an INCOMPLETE comparison set and `_FM` a complete one.
STATES = {
    # the family's own STR, matched every way the rule allows
    'own_name': (dict(recipient_name=FATHER_NAME, recipient_nric=''), _F),
    'own_nric': (dict(recipient_name=STRANGER_NAME, recipient_nric=FATHER_NRIC), _F),
    'own_both': (dict(recipient_name=FATHER_NAME, recipient_nric=FATHER_NRIC), _F),
    # ⚠ ABSENCE IS NOT A MISMATCH: the recipient did not read — it must STILL vouch
    'own_unread': (dict(recipient_name='', recipient_nric=''), _F),
    # ⚠ OWNER'S F1 RULING: WE CANNOT JUDGE IS NOT "STRANGER". The STR names nobody whose IC is on
    # file, but the mother is on the roster with no IC — so it still vouches, and her IC is ASKED.
    'stranger': (_STRANGER, _F),
    'stranger_dashboard': (dict(_STRANGER, source_type='dashboard'), _F),   # 'unconfirmed'
    'stranger_name_only': (dict(recipient_name=STRANGER_NAME, recipient_nric=''), _F),
    # the NAME did not read and the NRIC is somebody else's (adversarial review F3)
    'stranger_nric_only': (dict(recipient_name='', recipient_nric=STRANGER_NRIC), _F),
    # the owner's own example: the MOTHER's STR, with only the father's IC on file
    'mothers_str_only_fathers_ic': (dict(recipient_name=MOTHER_NAME, recipient_nric=MOTHER_NRIC),
                                    _F),
    # REVIEW F-A — "read" is per FIELD. The mother's IC is on file but read only the field the STR
    # does NOT offer, so on the field it DOES offer she was never compared: cannot judge, and her
    # IC is asked again as UNREADABLE (it is on file — review F-C).
    'mothers_name_str_her_ic_read_nric': (dict(recipient_name=MOTHER_NAME, recipient_nric=''),
                                          ('father', 'mother_nric_read')),
    'mothers_nric_str_her_ic_read_name': (dict(recipient_name='', recipient_nric=MOTHER_NRIC),
                                          ('father', 'mother_name_read')),
    # a TRUE stranger: every roster IC is on file and none matches — the ONLY rows that move fully
    'true_stranger': (_STRANGER, _FM),
    'true_stranger_dashboard': (dict(_STRANGER, source_type='dashboard'), _FM),
    'true_stranger_name_only': (dict(recipient_name=STRANGER_NAME, recipient_nric=''), _FM),
    'true_stranger_nric_only': (dict(recipient_name='', recipient_nric=STRANGER_NRIC), _FM),
    # …and COMPLETE ON ONE FIELD is enough (review F-A): the STR offers name and NRIC, the
    # mother's IC read only her name — the NAME comparison is complete and mismatched, so it is a
    # true stranger's even though the NRIC comparison is not
    'true_stranger_complete_on_name': (_STRANGER, ('father', 'mother_name_read')),
    # a stranger's STR with NO household IC to compare against — `no_ref`, so it still vouches
    'stranger_no_ic': (_STRANGER, ()),
    # currency already refused these; ownership cannot move them further
    'stranger_stale': (dict(_STRANGER, year='2024'), _F),
    'own_stale': (dict(recipient_name=FATHER_NAME, recipient_nric=FATHER_NRIC, year='2024'), _F),
    'own_unreadable': (dict(recipient_name=FATHER_NAME, recipient_nric=FATHER_NRIC, status=''),
                       _F),
    'none': (None, _F),
}
#: A TRUE stranger: the STR positively names somebody else AND every roster member's IC is on
#: file, and its currency would otherwise vouch. Every reading of these moves.
TRUE_STRANGER = frozenset({'true_stranger', 'true_stranger_dashboard', 'true_stranger_name_only',
                           'true_stranger_nric_only', 'true_stranger_complete_on_name'})
#: CANNOT JUDGE: a positive mismatch against the ICs compared, but a roster member was never
#: compared on a field the STR offers. The STR still vouches — every reading is the untouched
#: tree's — EXCEPT the gate, which no longer blocks (the lead's reading of the ruling, review
#: F-B/F-D: the STR counts; the ask is raised AFTER submission, where the upload can be taken).
#: `state -> the Check-2 ask it raises` (an IC not on file → `_missing`; on file, the field unread
#: → `_unreadable`, review F-C).
UNJUDGED_ASK = {
    'stranger': 'mother_ic_for_str_missing',
    'stranger_dashboard': 'mother_ic_for_str_missing',
    'stranger_name_only': 'mother_ic_for_str_missing',
    'stranger_nric_only': 'mother_ic_for_str_missing',
    'mothers_str_only_fathers_ic': 'mother_ic_for_str_missing',
    # stale, so it never vouched — but whose it is is still unknown, and the old gate blocked it
    # as `str_not_household` too
    'stranger_stale': 'mother_ic_for_str_missing',
    'mothers_name_str_her_ic_read_nric': 'mother_ic_for_str_unreadable',
    'mothers_nric_str_her_ic_read_name': 'mother_ic_for_str_unreadable',
}
UNJUDGED = frozenset(UNJUDGED_ASK)

ROUTES = ('salary', 'str')
EVIDENCE = ('none', 'payslip', 'epf', 'letter')
_PAYSLIP = {'gross_income': 'RM 1,800.00', 'net_income': 'RM 1,800.00', 'period': '08/2026'}
_EPF = {'employee_contribution_total': 'RM 1,188.00', 'months_counted': '6',
        'statement_date': '07/2026'}

#: The evidence codes that say WHY an income counted. Only these are pinned from the card, so a
#: soft household line elsewhere cannot make a row about STR ownership fail.
_INCOME_CODES = frozenset({'income_declared_accepted_str', 'income_declared_accepted_evidenced',
                           'income_declared_needs_evidence', 'income_per_capita_ok',
                           'income_proof_present', 'str_verified'})


#: The student-facing Check-2 codes TD-285 can move (adversarial review F2): `on_str` picks
#: between the two high-utility clarifies, and the declared-wage ask is the letter request.
CHECK2_CODES = frozenset({'high_utility_expense', 'high_utility_expense_str',
                          'high_utility_expense_noincome',       # TD-306
                          'declared_income_evidence_missing'}
                         | {f'{m}_ic_for_str_{k}'
                            for m in ('father', 'mother', 'guardian', 'brother', 'sister')
                            for k in ('missing', 'unreadable')})


def row_key(route, state, declared, evidence):
    return f'{route}/{state}/{"declared" if declared else "no-amount"}/{evidence}'


def all_keys():
    return [row_key(r, s, d, e) for r in ROUTES for s in STATES for d in (True, False)
            for e in EVIDENCE]


class WhoseStrBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(year=2026, income_ceiling=5860, per_capita_ceiling=1584)

    def build(self, route, state, declared, evidence, *, submitted=False):
        str_kw, ics = STATES[state]
        app = make_application(
            'profile_complete' if submitted else 'submitted',
            cohort=self.cohort, student=make_student(name=STUDENT_NAME),
            income_route=route,
            income_earner='father' if route == 'str' else '',
            income_working_members=['father'] if route == 'salary' else [],
            income_declared={'father': DECLARED} if declared else {},
            father_name=FATHER_NAME, father_occupation='private',
            mother_name=MOTHER_NAME, mother_occupation='homemaker',
            other_family_members=[], siblings_in_school=0, siblings_in_tertiary=0)
        app.profile.household_size = HOUSEHOLD_SIZE
        app.profile.save(update_fields=['household_size'])
        for ic in ics:
            member, name, nric = _ICS[ic]
            _doc(app, 'parent_ic', member, name=name, nric=nric)
        if str_kw is not None:
            _str_doc(app, **str_kw)
        if evidence == 'payslip':
            _doc(app, 'salary_slip', 'father', fields=_PAYSLIP)
        elif evidence == 'epf':
            _doc(app, 'epf', 'father', fields=_EPF)
        elif evidence == 'letter':
            d = _doc(app, 'income_support_doc', 'father')
            d.vision_fields = {'fields': {'employer': 'Kedai Runcit Aman'}, 'student_verdict': 'ok'}
            d.save(update_fields=['vision_fields'])
        return app

    def build_high_bills(self, route, state):
        """A SUBMITTED household (the Completed stage, where the machine may ask) with a typed
        amount, nothing else, and two RM200 bills — RM400 over five heads reads 'high', so the
        high-utility clarify fires and `on_str` picks its variant."""
        app = self.build(route, state, True, 'none', submitted=True)
        for dt in ('water_bill', 'electricity_bill'):
            d = _doc(app, dt, fields={'amount': 'RM200', 'name': STUDENT_NAME})
            d.vision_fields['student_verdict'] = 'ok'
            d.save(update_fields=['vision_fields'])
        return app

    def check2_codes(self, app):
        """The Check-2 codes `on_str` and the declared-wage ask decide, as `_gap_sets` would
        raise them (`gaps` ∪ `proof_wanted`), restricted to those three."""
        from apps.scholarship.check2_queries import _gap_sets
        gaps, proof = _gap_sets(app)
        return tuple(sorted((gaps | proof) & CHECK2_CODES))

    def readings(self, app):
        """Every reading the four callers give, plus the live gate, for ONE household — a tuple
        in ``FIELDS`` order."""
        # (c) `on_str` is only computed when the utility spend reads HIGH; the bill arithmetic is
        # not what this file is about, so the two utility readers are stood in for here.
        with mock.patch('apps.scholarship.income_engine.followups.utility_reasonable',
                        return_value={'status': 'high'}), \
                mock.patch('apps.scholarship.income_engine.followups.utility_monthly_total',
                           return_value=400.0):
            on_str = income_engine.high_utility_expense_context(app)['on_str']
        fact = verdict_engine._verdict_income(app)
        recon = income_engine.household_income_reconciliation(app)
        return (
            income_engine.has_valid_str(app),
            income_engine.earner_monthly_income(app, 'father'),
            income_engine.income_per_capita(app, ['father']),
            income_engine.income_headroom(app, ['father'])[0],
            tuple(g['member'] for g in declared_income_gaps(app)),
            on_str,
            (fact['status'], tuple(sorted(i['code'] for i in fact['unresolved'])),
             tuple(sorted(i['code'] for i in fact['evidence'] if i['code'] in _INCOME_CODES))),
            (recon['documented_total'], recon['all_known'], recon['matches']),
            profile_engine._income_evidence(app),
            tuple(sorted(services.income_doc_blockers(app))),
        )


#: The order of a reading. (a) is `declared_income_gaps`; (b) is `earner_monthly_income`,
#: `income_per_capita`, `income_headroom`, `reconciliation` and `profile_income`; (c) is `on_str`;
#: (d) is `verdict` = (band, unresolved codes, the income evidence codes); `blockers` is the live
#: submission gate, which may not move.
FIELDS = ('has_valid_str', 'earner_monthly_income', 'income_per_capita', 'income_headroom',
          'declared_income_gaps', 'on_str', 'verdict', 'reconciliation', 'profile_income',
          'blockers')


# ════════════════════════════════════════════════════════════════════════════════════════════
# THE UNTOUCHED TREE (cef458a7, 2026-09-29). Read off the code before the change; never edited.
# ════════════════════════════════════════════════════════════════════════════════════════════
BEFORE = {
    'salary/own_name/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_name/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_name/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_name/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_name/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, False, False), 'none on file', ()),
    'salary/own_name/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_name/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_name/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, False, False), 'none on file', ()),
    'salary/own_nric/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_nric/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_nric/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_nric/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_nric/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, False, False), 'none on file', ()),
    'salary/own_nric/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_nric/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_nric/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, False, False), 'none on file', ()),
    'salary/own_both/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_both/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_both/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_both/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_both/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, False, False), 'none on file', ()),
    'salary/own_both/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_both/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_both/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, False, False), 'none on file', ()),
    'salary/own_unread/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_unread/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_unread/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_unread/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_unread/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ()),
    'salary/own_unread/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_unread/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_unread/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ()),
    'salary/stranger/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/stranger/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/stranger/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_dashboard/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/stranger_dashboard/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger_dashboard/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger_dashboard/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/stranger_dashboard/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_dashboard/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger_dashboard/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger_dashboard/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_name_only/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/stranger_name_only/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger_name_only/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger_name_only/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/stranger_name_only/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_name_only/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger_name_only/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger_name_only/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_nric_only/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/stranger_nric_only/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger_nric_only/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger_nric_only/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/stranger_nric_only/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_nric_only/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger_nric_only/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger_nric_only/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/mothers_str_only_fathers_ic/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/mothers_str_only_fathers_ic/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/mothers_str_only_fathers_ic/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/mothers_str_only_fathers_ic/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/mothers_str_only_fathers_ic/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/mothers_str_only_fathers_ic/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/mothers_str_only_fathers_ic/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/mothers_str_only_fathers_ic/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/mothers_name_str_her_ic_read_nric/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/mothers_name_str_her_ic_read_nric/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/mothers_name_str_her_ic_read_nric/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/mothers_name_str_her_ic_read_nric/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/mothers_name_str_her_ic_read_nric/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/mothers_name_str_her_ic_read_nric/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/mothers_name_str_her_ic_read_nric/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/mothers_name_str_her_ic_read_nric/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/mothers_nric_str_her_ic_read_name/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/mothers_nric_str_her_ic_read_name/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/mothers_nric_str_her_ic_read_name/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/mothers_nric_str_her_ic_read_name/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/mothers_nric_str_her_ic_read_name/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/mothers_nric_str_her_ic_read_name/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/mothers_nric_str_her_ic_read_name/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/mothers_nric_str_her_ic_read_name/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger_complete_on_name/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/true_stranger_complete_on_name/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger_complete_on_name/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger_complete_on_name/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/true_stranger_complete_on_name/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger_complete_on_name/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger_complete_on_name/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger_complete_on_name/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/true_stranger/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/true_stranger/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger_dashboard/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/true_stranger_dashboard/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger_dashboard/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger_dashboard/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/true_stranger_dashboard/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger_dashboard/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger_dashboard/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger_dashboard/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger_name_only/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/true_stranger_name_only/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger_name_only/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger_name_only/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/true_stranger_name_only/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger_name_only/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger_name_only/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger_name_only/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger_nric_only/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'salary/true_stranger_nric_only/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger_nric_only/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger_nric_only/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/true_stranger_nric_only/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/true_stranger_nric_only/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/true_stranger_nric_only/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/true_stranger_nric_only/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_no_ic/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('gap', ('earner_ic_missing',), ('income_proof_present',)), (1500.0, True, False), "father's document shows about RM1500/month", ('parent_ic_missing:father',)),
    'salary/stranger_no_ic/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('gap', ('earner_ic_missing',), ('income_proof_present',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ('parent_ic_missing:father',)),
    'salary/stranger_no_ic/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('gap', ('earner_ic_missing',), ('income_proof_present',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ('parent_ic_missing:father',)),
    'salary/stranger_no_ic/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('gap', ('earner_ic_missing',), ('income_proof_present',)), (1500.0, True, False), "father's document shows about RM1500/month", ('parent_ic_missing:father',)),
    'salary/stranger_no_ic/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('gap', ('earner_ic_missing',), ()), (None, False, False), 'none on file', ('parent_ic_missing:father',)),
    'salary/stranger_no_ic/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('gap', ('earner_ic_missing',), ('income_proof_present',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ('parent_ic_missing:father',)),
    'salary/stranger_no_ic/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('gap', ('earner_ic_missing',), ('income_proof_present',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ('parent_ic_missing:father',)),
    'salary/stranger_no_ic/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('gap', ('earner_ic_missing',), ()), (None, False, False), 'none on file', ('parent_ic_missing:father',)),
    'salary/stranger_stale/declared/none': (False, (None, 'declared_unproven'), (None, False), 'unknown', ('father',), False, ('recommend', ('income_declared_needs_evidence',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_stale/declared/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger_stale/declared/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger_stale/declared/letter': (False, (1500.0, 'declared_evidenced'), (300.0, True), 'probable', (), False, ('verified', (), ('income_declared_accepted_evidenced', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/stranger_stale/no-amount/none': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/stranger_stale/no-amount/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/stranger_stale/no-amount/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/stranger_stale/no-amount/letter': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('str_not_household',)),
    'salary/own_stale/declared/none': (False, (None, 'declared_unproven'), (None, False), 'unknown', ('father',), False, ('recommend', ('income_declared_needs_evidence',), ()), (None, False, False), 'none on file', ()),
    'salary/own_stale/declared/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_stale/declared/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_stale/declared/letter': (False, (1500.0, 'declared_evidenced'), (300.0, True), 'probable', (), False, ('verified', (), ('income_declared_accepted_evidenced', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_stale/no-amount/none': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ()),
    'salary/own_stale/no-amount/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_stale/no-amount/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_stale/no-amount/letter': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ()),
    'salary/own_unreadable/declared/none': (False, (None, 'declared_unproven'), (None, False), 'unknown', ('father',), False, ('recommend', ('income_declared_needs_evidence',), ()), (None, False, False), 'none on file', ()),
    'salary/own_unreadable/declared/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_unreadable/declared/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_unreadable/declared/letter': (False, (1500.0, 'declared_evidenced'), (300.0, True), 'probable', (), False, ('verified', (), ('income_declared_accepted_evidenced', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/own_unreadable/no-amount/none': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ()),
    'salary/own_unreadable/no-amount/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/own_unreadable/no-amount/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/own_unreadable/no-amount/letter': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ()),
    'salary/none/declared/none': (False, (None, 'declared_unproven'), (None, False), 'unknown', ('father',), False, ('recommend', ('income_declared_needs_evidence',), ()), (None, False, False), 'none on file', ('income_evidence_missing:father',)),
    'salary/none/declared/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/none/declared/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/none/declared/letter': (False, (1500.0, 'declared_evidenced'), (300.0, True), 'probable', (), False, ('verified', (), ('income_declared_accepted_evidenced', 'income_per_capita_ok', 'income_proof_present')), (1500.0, True, False), "father's document shows about RM1500/month", ()),
    'salary/none/no-amount/none': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('income_evidence_missing:father',)),
    'salary/none/no-amount/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'salary/none/no-amount/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'salary/none/no-amount/letter': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('income_unverified_needs_interview',), ()), (None, False, False), 'none on file', ('income_evidence_missing:father',)),
    'str/own_name/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_name/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_name/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_name/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_name/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, True, False), 'none on file', ()),
    'str/own_name/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_name/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_name/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, True, False), 'none on file', ()),
    'str/own_nric/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_nric/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_nric/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_nric/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_nric/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, True, False), 'none on file', ()),
    'str/own_nric/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_nric/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_nric/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, True, False), 'none on file', ()),
    'str/own_both/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_both/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_both/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_both/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_both/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, True, False), 'none on file', ()),
    'str/own_both/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_both/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', (), ('str_verified',)), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_both/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('verified', (), ('str_verified',)), (None, True, False), 'none on file', ()),
    'str/own_unread/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('review', ('str_present_unverified',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_unread/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('review', ('str_present_unverified',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_unread/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('review', ('str_present_unverified',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_unread/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('review', ('str_present_unverified',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_unread/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('review', ('str_present_unverified',), ()), (None, True, False), 'none on file', ()),
    'str/own_unread/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('review', ('str_present_unverified',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_unread/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('review', ('str_present_unverified',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_unread/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('review', ('str_present_unverified',), ()), (None, True, False), 'none on file', ()),
    'str/stranger/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/stranger/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/stranger/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_dashboard/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/stranger_dashboard/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger_dashboard/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger_dashboard/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/stranger_dashboard/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('review', ('str_not_current',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_dashboard/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger_dashboard/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger_dashboard/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('review', ('str_not_current',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_name_only/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/stranger_name_only/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger_name_only/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger_name_only/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/stranger_name_only/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_name_only/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger_name_only/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger_name_only/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_nric_only/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/stranger_nric_only/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger_nric_only/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger_nric_only/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/stranger_nric_only/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_nric_only/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger_nric_only/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger_nric_only/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/mothers_str_only_fathers_ic/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/mothers_str_only_fathers_ic/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/mothers_str_only_fathers_ic/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/mothers_str_only_fathers_ic/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_declared_accepted_str', 'income_per_capita_ok', 'income_proof_present')), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/mothers_str_only_fathers_ic/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/mothers_str_only_fathers_ic/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/mothers_str_only_fathers_ic/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('verified', ('str_recipient_mismatch',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/mothers_str_only_fathers_ic/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/mothers_name_str_her_ic_read_nric/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/mothers_name_str_her_ic_read_nric/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/mothers_name_str_her_ic_read_nric/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/mothers_name_str_her_ic_read_nric/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/mothers_name_str_her_ic_read_nric/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/mothers_name_str_her_ic_read_nric/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/mothers_name_str_her_ic_read_nric/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/mothers_name_str_her_ic_read_nric/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/mothers_nric_str_her_ic_read_name/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/mothers_nric_str_her_ic_read_name/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/mothers_nric_str_her_ic_read_name/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/mothers_nric_str_her_ic_read_name/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/mothers_nric_str_her_ic_read_name/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/mothers_nric_str_her_ic_read_name/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/mothers_nric_str_her_ic_read_name/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/mothers_nric_str_her_ic_read_name/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger_complete_on_name/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/true_stranger_complete_on_name/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger_complete_on_name/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger_complete_on_name/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/true_stranger_complete_on_name/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger_complete_on_name/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger_complete_on_name/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger_complete_on_name/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/true_stranger/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/true_stranger/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger_dashboard/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/true_stranger_dashboard/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger_dashboard/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger_dashboard/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/true_stranger_dashboard/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('review', ('str_not_current',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger_dashboard/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger_dashboard/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('review', ('str_not_current',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger_dashboard/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('review', ('str_not_current',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger_name_only/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/true_stranger_name_only/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger_name_only/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger_name_only/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/true_stranger_name_only/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger_name_only/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger_name_only/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger_name_only/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger_nric_only/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ('str_not_household',)),
    'str/true_stranger_nric_only/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger_nric_only/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger_nric_only/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/true_stranger_nric_only/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/true_stranger_nric_only/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/true_stranger_nric_only/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('recommend', ('str_recipient_mismatch',), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/true_stranger_nric_only/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('recommend', ('str_recipient_mismatch',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_no_ic/declared/none': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('gap', ('earner_ic_missing', 'str_present_unverified'), ()), (None, True, False), "father's document shows about RM1500/month", ('parent_ic_missing:father',)),
    'str/stranger_no_ic/declared/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('gap', ('earner_ic_missing', 'str_present_unverified'), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ('parent_ic_missing:father',)),
    'str/stranger_no_ic/declared/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('gap', ('earner_ic_missing', 'str_present_unverified'), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ('parent_ic_missing:father',)),
    'str/stranger_no_ic/declared/letter': (True, (1500.0, 'declared_str'), (300.0, True), 'probable', (), True, ('gap', ('earner_ic_missing', 'str_present_unverified'), ()), (None, True, False), "father's document shows about RM1500/month", ('parent_ic_missing:father',)),
    'str/stranger_no_ic/no-amount/none': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('gap', ('earner_ic_missing', 'str_present_unverified'), ()), (None, True, False), 'none on file', ('parent_ic_missing:father',)),
    'str/stranger_no_ic/no-amount/payslip': (True, (1800.0, 'salary'), (360.0, True), 'probable', (), True, ('gap', ('earner_ic_missing', 'str_present_unverified'), ()), (1800.0, True, False), "father's salary slip shows about RM1800/month", ('parent_ic_missing:father',)),
    'str/stranger_no_ic/no-amount/epf': (True, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), True, ('gap', ('earner_ic_missing', 'str_present_unverified'), ()), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ('parent_ic_missing:father',)),
    'str/stranger_no_ic/no-amount/letter': (True, (None, 'unknown'), (None, False), 'unknown', (), True, ('gap', ('earner_ic_missing', 'str_present_unverified'), ()), (None, True, False), 'none on file', ('parent_ic_missing:father',)),
    'str/stranger_stale/declared/none': (False, (None, 'declared_unproven'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_stale/declared/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger_stale/declared/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger_stale/declared/letter': (False, (1500.0, 'declared_evidenced'), (300.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_declared_accepted_evidenced', 'income_per_capita_ok', 'income_proof_present')), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/stranger_stale/no-amount/none': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/stranger_stale/no-amount/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/stranger_stale/no-amount/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/stranger_stale/no-amount/letter': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ('str_not_household',)),
    'str/own_stale/declared/none': (False, (None, 'declared_unproven'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ()),
    'str/own_stale/declared/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_stale/declared/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_stale/declared/letter': (False, (1500.0, 'declared_evidenced'), (300.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_declared_accepted_evidenced', 'income_per_capita_ok', 'income_proof_present')), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_stale/no-amount/none': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ()),
    'str/own_stale/no-amount/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_stale/no-amount/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_stale/no-amount/letter': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ()),
    'str/own_unreadable/declared/none': (False, (None, 'declared_unproven'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ()),
    'str/own_unreadable/declared/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_unreadable/declared/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_unreadable/declared/letter': (False, (1500.0, 'declared_evidenced'), (300.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_declared_accepted_evidenced', 'income_per_capita_ok', 'income_proof_present')), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/own_unreadable/no-amount/none': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ()),
    'str/own_unreadable/no-amount/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/own_unreadable/no-amount/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', ('str_not_current',), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/own_unreadable/no-amount/letter': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('recommend', ('str_not_current',), ()), (None, True, False), 'none on file', ()),
    'str/none/declared/none': (False, (None, 'declared_unproven'), (None, False), 'unknown', (), False, ('gap', ('income_proof_missing',), ()), (None, True, False), 'none on file', ('str_missing',)),
    'str/none/declared/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/none/declared/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/none/declared/letter': (False, (1500.0, 'declared_evidenced'), (300.0, True), 'probable', (), False, ('verified', (), ('income_declared_accepted_evidenced', 'income_per_capita_ok', 'income_proof_present')), (None, True, False), "father's document shows about RM1500/month", ()),
    'str/none/no-amount/none': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('gap', ('income_proof_missing',), ()), (None, True, False), 'none on file', ('str_missing',)),
    'str/none/no-amount/payslip': (False, (1800.0, 'salary'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's salary slip shows about RM1800/month", ()),
    'str/none/no-amount/epf': (False, (1800.0, 'epf_estimate'), (360.0, True), 'probable', (), False, ('verified', (), ('income_per_capita_ok', 'income_proof_present')), (1800.0, True, False), "father's EPF statement shows about RM1800/month", ()),
    'str/none/no-amount/letter': (False, (None, 'unknown'), (None, False), 'unknown', (), False, ('gap', ('income_proof_missing',), ()), (None, True, False), 'none on file', ('str_missing',)),
}

#: The FROZEN gate (`application_completeness`, the already-submitted student's branch) on a
#: salary-route household with a typed amount or none and nothing else. Untouched tree; none of
#: these may move — a student already submitted is never un-submitted by a rule tightened after.
FROZEN_BEFORE = {
    ('own_name', True): True, ('own_name', False): True,
    ('own_nric', True): True, ('own_nric', False): True,
    ('own_both', True): True, ('own_both', False): True,
    ('own_unread', True): True, ('own_unread', False): True,
    ('stranger', True): True, ('stranger', False): True,
    ('stranger_dashboard', True): True, ('stranger_dashboard', False): True,
    ('stranger_name_only', True): True, ('stranger_name_only', False): True,
    ('stranger_nric_only', True): True, ('stranger_nric_only', False): True,
    ('mothers_str_only_fathers_ic', True): True, ('mothers_str_only_fathers_ic', False): True,
    ('true_stranger_complete_on_name', True): True,
    ('true_stranger_complete_on_name', False): True,
    ('mothers_name_str_her_ic_read_nric', True): True,
    ('mothers_name_str_her_ic_read_nric', False): True,
    ('mothers_nric_str_her_ic_read_name', True): True,
    ('mothers_nric_str_her_ic_read_name', False): True,
    ('true_stranger', True): True, ('true_stranger', False): True,
    ('true_stranger_dashboard', True): True, ('true_stranger_dashboard', False): True,
    ('true_stranger_name_only', True): True, ('true_stranger_name_only', False): True,
    ('true_stranger_nric_only', True): True, ('true_stranger_nric_only', False): True,
    ('stranger_no_ic', True): False, ('stranger_no_ic', False): False,
    ('stranger_stale', True): True, ('stranger_stale', False): True,
    ('own_stale', True): True, ('own_stale', False): True,
    ('own_unreadable', True): True, ('own_unreadable', False): True,
    ('none', True): False, ('none', False): False,
}

# ════════════════════════════════════════════════════════════════════════════════════════════
# WHAT THE RULING MOVED — `row: {reading: (before, after)}`. Nothing else may move.
# ════════════════════════════════════════════════════════════════════════════════════════════
#: EVERY moved row: the predicate itself, and `on_str` (caller c), which reads it raw. A stranger's
#: STR is no longer "on STR" — and that picks the STUDENT's high-utility clarify (section 5).
_ASKED_WHOSE = {'has_valid_str': (True, False), 'on_str': (True, False)}
_TYPED = (1500.0, 'declared_str')
_TYPED_ALONE_B = {        # caller (b): the typed figure is no longer a real number on either route
    'earner_monthly_income': (_TYPED, (None, 'declared_unproven')),
    'income_per_capita': ((300.0, True), (None, False)),
    'income_headroom': ('probable', 'unknown'),
    'profile_income': ("father's document shows about RM1500/month", 'none on file'),
}
#: SALARY route, a typed figure and nothing else. (a) Check 2 now ASKS for the supporting letter —
#: a stranger's STR fulfils nothing, so the 2026-09-20 short-circuit does not apply; (d) the band
#: falls Certain -> Unsure with `income_declared_needs_evidence` (the band that moves, hence the
#: VERDICT_ENGINE_VERSION bump); and the reconciliation tick can no longer total the household.
_TYPED_ALONE_SALARY = {
    **_ASKED_WHOSE, **_TYPED_ALONE_B,
    'declared_income_gaps': ((), ('father',)),
    'verdict': (('verified', (), ('income_declared_accepted_str', 'income_per_capita_ok',
                                  'income_proof_present')),
                ('recommend', ('income_declared_needs_evidence',), ())),
    'reconciliation': ((1500.0, True, False), (None, False, False)),
}
#: STR route, a typed figure and nothing else. No chase (the cash door is salary-route only — the
#: route guard, a ruling of its own) and NO BAND MOVE: the audit gate of 2026-09-21 had already
#: refused to let this figure raise the fall-through. Only the arithmetic and the profile line.
_TYPED_ALONE_STR = {**_ASKED_WHOSE, **_TYPED_ALONE_B}
#: A typed figure WITH a letter that read: still a real number, now for the honest reason.
_TYPED_WITH_LETTER = {**_ASKED_WHOSE,
                      'earner_monthly_income': (_TYPED, (1500.0, 'declared_evidenced'))}


def _letter_card(unresolved):
    """(d) the evidence code the officer reads: `_str` -> `_evidenced`. Band unchanged."""
    return {**_TYPED_WITH_LETTER, 'verdict': (
        ('verified', unresolved, ('income_declared_accepted_str', 'income_per_capita_ok',
                                  'income_proof_present')),
        ('verified', unresolved, ('income_declared_accepted_evidenced', 'income_per_capita_ok',
                                  'income_proof_present')))}


def _true_stranger_move(route, state, declared, evidence):
    """What a TRUE stranger's row moves by — the same for every true-stranger state. On the STR
    route the letter row renders no evidence code to change: with the mother's IC on file and no
    birth certificate the salary reading is itself incomplete and never raises the STR's band (and
    the dashboard STR bands `review` on `str_not_current` first), so only the figure's LABEL moves."""
    if evidence in ('none', 'letter') and declared:
        if evidence == 'none':
            return _TYPED_ALONE_SALARY if route == 'salary' else _TYPED_ALONE_STR
        return _letter_card(()) if route == 'salary' else _TYPED_WITH_LETTER
    return _ASKED_WHOSE


#: CANNOT JUDGE, AT THE GATE (the lead's reading of the owner's F1 ruling, review F-B/F-D): the STR
#: counts, so it no longer blocks — `str_not_household` simply leaves. The mother's IC is asked
#: AFTER submission, where the Action Centre can take it. Nothing else in these rows moves.
def _gate_frees(key):
    before = BEFORE.get(key, (None,) * len(FIELDS))[FIELDS.index('blockers')] or ()
    if 'str_not_household' not in before:           # (a missing row fails the completeness test)
        return {}
    return {'blockers': (before, tuple(c for c in before if c != 'str_not_household'))}


MOVED = {
    **{row_key(r, s, d, e): _true_stranger_move(r, s, d, e)
       for r in ROUTES for s in TRUE_STRANGER for d in (True, False) for e in EVIDENCE},
    **{k: m for k in all_keys() if k.split('/')[1] in UNJUDGED
       for m in (_gate_frees(k),) if m},
}

# ════════════════════════════════════════════════════════════════════════════════════════════
# THE STUDENT'S CHECK-2 ASKS (adversarial review F2). `on_str` is NOT officer-only: it picks which
# high-utility clarify the STUDENT is asked (`check2_queries._gap_sets`), beside the declared-wage
# letter request. A SUBMITTED household, typed amount, nothing else, bills reading high.
# `(route, state) -> codes`, untouched tree; never edited.
# ════════════════════════════════════════════════════════════════════════════════════════════
_HU, _HU_STR, _LETTER = ('high_utility_expense', 'high_utility_expense_str',
                         'declared_income_evidence_missing')
CHECK2_BEFORE = {
    ('salary', 'own_name'): (_HU_STR,), ('salary', 'own_nric'): (_HU_STR,),
    ('salary', 'own_both'): (_HU_STR,), ('salary', 'own_unread'): (_HU_STR,),
    ('salary', 'stranger'): (_HU_STR,), ('salary', 'stranger_dashboard'): (_HU_STR,),
    ('salary', 'stranger_name_only'): (_HU_STR,), ('salary', 'stranger_nric_only'): (_HU_STR,),
    ('salary', 'stranger_no_ic'): (_HU_STR,), ('salary', 'mothers_str_only_fathers_ic'): (_HU_STR,),
    ('salary', 'mothers_name_str_her_ic_read_nric'): (_HU_STR,),
    ('salary', 'mothers_nric_str_her_ic_read_name'): (_HU_STR,),
    **{('salary', s): (_HU_STR,) for s in TRUE_STRANGER},
    ('salary', 'stranger_stale'): (_LETTER, _HU), ('salary', 'own_stale'): (_LETTER, _HU),
    ('salary', 'own_unreadable'): (_LETTER, _HU), ('salary', 'none'): (_LETTER, _HU),
    ('str', 'own_name'): (_HU_STR,), ('str', 'own_nric'): (_HU_STR,),
    ('str', 'own_both'): (_HU_STR,), ('str', 'own_unread'): (_HU_STR,),
    ('str', 'stranger'): (_HU_STR,), ('str', 'stranger_dashboard'): (_HU_STR,),
    ('str', 'stranger_name_only'): (_HU_STR,), ('str', 'stranger_nric_only'): (_HU_STR,),
    ('str', 'stranger_no_ic'): (_HU_STR,), ('str', 'mothers_str_only_fathers_ic'): (_HU_STR,),
    ('str', 'mothers_name_str_her_ic_read_nric'): (_HU_STR,),
    ('str', 'mothers_nric_str_her_ic_read_name'): (_HU_STR,),
    **{('str', s): (_HU_STR,) for s in TRUE_STRANGER},
    ('str', 'stranger_stale'): (_HU,), ('str', 'own_stale'): (_HU,),
    ('str', 'own_unreadable'): (_HU,), ('str', 'none'): (_HU,),
}
#: The new Check-2 ask: the STR names somebody whose IC is not on file → ask for that member's IC.
_ASK_MOTHER_IC = 'mother_ic_for_str_missing'
#: What moved. A TRUE stranger's STR now reads as a household with no STR of its own — the income
#: variant of the clarify and, on the salary route only, the letter request. A household we CANNOT
#: JUDGE keeps its `_str` clarify and is asked for the mother's IC.
CHECK2_MOVED = {
    **{('salary', s): (_LETTER, _HU) for s in TRUE_STRANGER},
    **{('str', s): (_HU,) for s in TRUE_STRANGER},
    **{(r, s): tuple(sorted(CHECK2_BEFORE.get((r, s), ()) + (UNJUDGED_ASK[s],)))
       for r in ROUTES for s in UNJUDGED},
}


def expected(key):
    """`BEFORE[key]` with exactly the readings `MOVED` names replaced by their `after`."""
    row = list(BEFORE[key])
    for field, (_before, after) in MOVED.get(key, {}).items():
        row[FIELDS.index(field)] = after
    return tuple(row)


def _state_of(key):
    return key.split('/')[1]


# ════════════════════════════════════════════════════════════════════════════════════════════
# 1. THE MATRIX, ROW BY ROW — every row BEFORE, except exactly what MOVED says
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheFourCallersRowByRow(WhoseStrBase):
    """One test per (route, STR state), eight households each: typed amount or not, times
    nothing / a payslip / a readable EPF / a supporting letter that read. 208 rows."""


def _make_matrix_test(route, state):
    def test(self):
        for declared in (True, False):
            for evidence in EVIDENCE:
                key = row_key(route, state, declared, evidence)
                with self.subTest(row=key):
                    self.assertEqual(
                        self.readings(self.build(route, state, declared, evidence)),
                        expected(key),
                        f'{key} moved. Only a stranger\'s STR with a household IC on file may '
                        f'move under TD-285, and only as MOVED says. Fields: {FIELDS}')
    test.__name__ = f'test_{route}_{state}'
    return test


for _route in ROUTES:
    for _state in STATES:
        setattr(TestTheFourCallersRowByRow, f'test_{_route}_{_state}',
                _make_matrix_test(_route, _state))


# ════════════════════════════════════════════════════════════════════════════════════════════
# 2. THE MOVED SET IS THE RULING — asserted, not argued
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheMovedSetIsExactlyTheRuling(TestCase):

    def test_the_matrix_is_complete(self):
        self.assertEqual(sorted(BEFORE), sorted(all_keys()))
        self.assertEqual(len(BEFORE), 336)

    def test_every_before_half_is_what_before_says(self):
        """The record of what changed cannot drift from the record of what was."""
        for key, changes in MOVED.items():
            for field, (before, after) in changes.items():
                with self.subTest(row=key, field=field):
                    self.assertEqual(BEFORE[key][FIELDS.index(field)], before)
                    self.assertNotEqual(before, after, 'a MOVED entry that moves nothing')

    def test_only_a_true_stranger_or_an_unjudged_str_moves(self):
        strays = sorted(k for k in MOVED if _state_of(k) not in TRUE_STRANGER | UNJUDGED)
        self.assertEqual(strays, [], 'a row outside the ruling moved')

    def test_every_true_strangers_str_stops_vouching(self):
        """…and every one of them moves, at least in the predicate and `on_str`."""
        for key in all_keys():
            if _state_of(key) in TRUE_STRANGER:
                with self.subTest(row=key):
                    self.assertIn(key, MOVED)
                    self.assertEqual(MOVED[key]['has_valid_str'], (True, False))
                    self.assertEqual(MOVED[key]['on_str'], (True, False))

    def test_an_unjudged_str_moves_nothing_but_the_gate_freeing_it(self):
        """OWNER'S F1 RULING, AS THE LEAD READS IT (review F-B/F-D): we cannot judge is not
        "stranger" — the STR counts, so it does not block. Every reading of these rows is the
        untouched tree's, save the gate, from which `str_not_household` leaves and NOTHING takes
        its place (the Documents page cannot take a non-working mother's IC before submission)."""
        for key in all_keys():
            if _state_of(key) in UNJUDGED and key in MOVED:
                with self.subTest(row=key):
                    self.assertEqual(sorted(MOVED[key]), ['blockers'])
                    before, after = MOVED[key]['blockers']
                    self.assertIn('str_not_household', before)
                    self.assertEqual(set(before) - set(after), {'str_not_household'})
                    self.assertEqual(set(after) - set(before), set())

    def test_the_gate_never_blocks_a_row_it_did_not_block(self):
        """NOBODY IS NEWLY BLOCKED, row by row: a blocker that is on a row now was on it on the
        untouched tree. (The gate may only lose codes — the ruling allows widening.)"""
        for key in all_keys():
            with self.subTest(row=key):
                self.assertLessEqual(set(expected(key)[FIELDS.index('blockers')]),
                                     set(BEFORE[key][FIELDS.index('blockers')]))

    def test_a_true_strangers_gate_rows_are_unchanged(self):
        """A true stranger is still blocked EXACTLY as before — `str_not_household`."""
        self.assertEqual([k for k, c in MOVED.items()
                          if 'blockers' in c and _state_of(k) in TRUE_STRANGER], [])

    def test_only_the_salary_route_gains_a_chase_or_a_band(self):
        """(a) and the band half of (d) move on the SALARY route only: the cash door is never
        on the STR route, and the STR route's fall-through was already gated by the audit."""
        for key, changes in MOVED.items():
            if key.startswith('str/'):
                with self.subTest(row=key):
                    self.assertNotIn('declared_income_gaps', changes)
                    if 'verdict' in changes:
                        self.assertEqual(changes['verdict'][0][:2], changes['verdict'][1][:2])


# ════════════════════════════════════════════════════════════════════════════════════════════
# 3. THE FROZEN GATE — an already-submitted student is never un-submitted
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheFrozenGateDoesNotMove(WhoseStrBase):

    def test_documents_done_is_unchanged_in_every_state(self):
        for state in STATES:
            for declared in (True, False):
                with self.subTest(state=state, declared=declared):
                    app = self.build('salary', state, declared, 'none', submitted=True)
                    for needed in ('ic', 'results_slip'):
                        _doc(app, needed)
                    self.assertEqual(services.application_completeness(app)['documents_done'],
                                     FROZEN_BEFORE[(state, declared)])


# ════════════════════════════════════════════════════════════════════════════════════════════
# 4. THE RULING IN WORDS — the rows above, said once each where a person will read them
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheRulingInWords(WhoseStrBase):

    def test_a_strangers_str_no_longer_vouches_for_a_typed_amount(self):
        """R5: *"only the family's own STR count."* Before 2026-09-29 this read
        `(1500.0, 'declared_str')` — a figure the family typed, accepted as a real number on a
        document naming somebody else."""
        app = self.build('salary', 'true_stranger', True, 'none')
        self.assertIs(income_engine.has_valid_str(app), False)
        self.assertEqual(income_engine.earner_monthly_income(app, 'father'),
                         (None, 'declared_unproven'))

    def test_an_str_whose_recipient_did_not_read_still_vouches(self):
        """⚠ ABSENCE IS NOT A MISMATCH (F8 rule 1). Nothing was read off the recipient, so there is
        nothing to hold against the family: the STR vouches exactly as it did."""
        app = self.build('salary', 'own_unread', True, 'none')
        sc = income_engine.student_str_check(app.documents.get(doc_type='str'))
        self.assertEqual((sc['name_status'], sc['nric_status']), ('no_ref', 'no_ref'))
        self.assertIs(income_engine.has_valid_str(app), True)
        self.assertEqual(income_engine.earner_monthly_income(app, 'father'),
                         (1500.0, 'declared_str'))

    def test_a_strangers_name_with_no_household_ic_on_file_still_vouches(self):
        """⚠ The same rule from the other side: with no household IC there is nothing to compare
        against, so a name we cannot place is `no_ref`, not a stranger. The gate asks for the IC
        (it always did); the amount is not taken away for a gap in the file."""
        app = self.build('salary', 'stranger_no_ic', True, 'none')
        self.assertIs(income_engine.has_valid_str(app), True)
        self.assertEqual(income_engine.earner_monthly_income(app, 'father'),
                         (1500.0, 'declared_str'))

    def test_a_salary_household_on_a_strangers_str_is_now_asked_for_the_letter(self):
        """The 2026-09-20 ruling — *"If STR has been fulfilled, there is no need for the student
        to complete the cash door"* — is about an STR that FULFILS something. A stranger's STR
        fulfils nothing, so the fourth way's letter is asked for, as for any household with
        neither an STR of its own nor a payslip. Before 2026-09-29 this read `[]`."""
        app = self.build('salary', 'true_stranger', True, 'none')
        self.assertEqual(declared_income_gaps(app), [{'member': 'father'}])

    def test_the_familys_own_str_still_answers_the_cash_door(self):
        """…and the ruling's own rows stand: the family's own STR, however it matched, and an
        STR whose recipient did not read, are never chased for a letter."""
        for state in ('own_name', 'own_nric', 'own_both', 'own_unread'):
            with self.subTest(state=state):
                self.assertEqual(declared_income_gaps(self.build('salary', state, True, 'none')),
                                 [])

    def test_the_predicate_and_the_gate_ask_one_ownership_question(self):
        """`has_valid_str` is currency AND NOT `str_recipient_is_stranger` — the same rule the
        submission gate reads, applied to the same reading, so the two can never disagree about
        whose STR it is."""
        from apps.scholarship.income_str_ownership import str_recipient_is_stranger
        for state, (str_kw, _ic) in STATES.items():
            with self.subTest(state=state):
                app = self.build('salary', state, False, 'none')
                if str_kw is None:
                    self.assertIs(income_engine.has_valid_str(app), False)
                    continue
                sc = income_engine.student_str_check(app.documents.get(doc_type='str'))
                currency_ok = sc['current_status'] in ('current', 'unconfirmed')
                self.assertIs(income_engine.has_valid_str(app),
                              currency_ok and not str_recipient_is_stranger(app))

    def test_the_verdict_engine_version_records_the_move(self):
        """A fact's status moves (the salary-route typed-amount row, Certain -> Unsure), so the
        rule at `VERDICT_ENGINE_VERSION` requires a bump. This pins that it happened."""
        self.assertGreaterEqual(verdict_engine.VERDICT_ENGINE_VERSION, '2026-09-29.1')

    def test_an_nric_only_stranger_is_a_stranger(self):
        """Adversarial review F3. The name did not read; the NRIC read and is somebody else's.
        Name OR NRIC, each field on its own: a positive NRIC mismatch with no match anywhere is a
        stranger's STR. A rule that read the name alone would call this `no_ref` and let it vouch."""
        app = self.build('salary', 'true_stranger_nric_only', True, 'none')
        sc = income_engine.student_str_check(app.documents.get(doc_type='str'))
        self.assertEqual((sc['name_status'], sc['nric_status']), ('no_ref', 'mismatch'))
        self.assertIs(income_engine.has_valid_str(app), False)
        self.assertEqual(income_engine.earner_monthly_income(app, 'father'),
                         (None, 'declared_unproven'))

    def test_the_mothers_str_with_only_the_fathers_ic_cannot_be_judged(self):
        """OWNER'S F1 RULING, 2026-09-29: *"we cannot judge" is NOT "stranger".* The STR is in the
        mother's name; only the father's IC is on file, so it mismatches the one IC we can compare —
        but the mother is on the roster with no IC. The STR COUNTS — it does not block submission
        (the lead's reading, review F-B) — and her IC is ASKED after submission, through Check 2,
        as `mother_ic_for_str_missing`."""
        from apps.scholarship.check2_queries import _gap_sets
        from apps.scholarship.income_str_ownership import str_owner_ic_asks
        for route in ROUTES:
            with self.subTest(route=route):
                app = self.build(route, 'mothers_str_only_fathers_ic', True, 'none')
                sc = income_engine.student_str_check(app.documents.get(doc_type='str'))
                self.assertIn('mismatch', (sc['name_status'], sc['nric_status']))
                self.assertIs(income_engine.has_valid_str(app), True)
                self.assertEqual(str_owner_ic_asks(app), {'missing': ['mother'], 'unreadable': []})
                self.assertEqual(services.income_doc_blockers(app), [])
                submitted = self.build(route, 'mothers_str_only_fathers_ic', True, 'none',
                                       submitted=True)
                self.assertIn(_ASK_MOTHER_IC, _gap_sets(submitted)[1])

    def test_read_is_per_field_not_per_ic(self):
        """REVIEW F-A. The mother's IC is on file but read only the field the STR does NOT offer,
        so she was never compared on the field it DOES: cannot judge, both ways round. Her IC is
        asked again as UNREADABLE — it is on file (review F-C) — and the STR still counts."""
        from apps.scholarship.income_str_ownership import str_owner_ic_asks
        for state in ('mothers_name_str_her_ic_read_nric', 'mothers_nric_str_her_ic_read_name'):
            for route in ROUTES:
                with self.subTest(state=state, route=route):
                    app = self.build(route, state, True, 'none')
                    self.assertIs(income_engine.has_valid_str(app), True)
                    self.assertEqual(str_owner_ic_asks(app),
                                     {'missing': [], 'unreadable': ['mother']})
                    self.assertNotIn('str_not_household', services.income_doc_blockers(app))

    def test_a_true_stranger_is_compared_on_both_fields_and_refused(self):
        """…and the other side of F-A: every roster IC read BOTH fields, the STR offers both, and
        neither matches — a true stranger, refused, and still blocked at the gate."""
        from apps.scholarship.income_str_ownership import str_owner_ic_asks
        app = self.build('salary', 'true_stranger', True, 'none')
        sc = income_engine.student_str_check(app.documents.get(doc_type='str'))
        self.assertEqual((sc['name_status'], sc['nric_status']), ('mismatch', 'mismatch'))
        self.assertIs(income_engine.has_valid_str(app), False)
        self.assertEqual(str_owner_ic_asks(app), {'missing': [], 'unreadable': []})
        self.assertEqual(services.income_doc_blockers(app), ['str_not_household'])

    def test_the_roster_is_the_parents_the_guardian_the_earner_and_the_working_members(self):
        """The comparison set a positive mismatch must be judged against (owner's F1 ruling):
        a father / mother the application records and who is not recorded as deceased or out of
        contact, a guardian in the roster, the STR route's earner, and every ticked working member.
        Siblings join ONLY as the earner or a working member."""
        from apps.scholarship.income_str_ownership import str_roster
        app = self.build('salary', 'none', False, 'none')
        self.assertEqual(str_roster(app), ['father', 'mother'])
        app.mother_occupation = 'deceased'
        app.other_family_members = [{'role': 'guardian', 'occupation': 'retired'},
                                    {'role': 'sister', 'occupation': 'factory'}]
        app.income_working_members = ['father', 'brother']
        self.assertEqual(str_roster(app), ['father', 'guardian', 'brother'])
        app.father_occupation = 'no_contact'
        app.income_working_members = []
        app.income_route, app.income_earner = 'str', 'sister'
        self.assertEqual(str_roster(app), ['guardian', 'sister'])


# ════════════════════════════════════════════════════════════════════════════════════════════
# 5. WHAT THE STUDENT IS ASKED — and emailed (adversarial review F2)
# ════════════════════════════════════════════════════════════════════════════════════════════
_HU_NOINCOME = 'high_utility_expense_noincome'


def _since_td306(codes):
    """TD-306 (2026-09-29), applied on top of the two tables above, which stay as TD-285 froze them:
    these households report NO household income, so where they used to be asked the plain
    `high_utility_expense` ("…the household income of RM {income} a month you reported") — which
    printed the literal placeholder — they are now asked `high_utility_expense_noincome`. Nothing
    else moves; the `_str` wording and the letter request are untouched."""
    return tuple(sorted(_HU_NOINCOME if c == _HU else c for c in codes))


class TestTheStudentsCheck2Asks(WhoseStrBase):
    """`on_str` reaches the STUDENT: it picks `high_utility_expense_str` (asked against the STR)
    or `high_utility_expense` (asked against the household income the student reported), and the
    declared-wage ask raises `declared_income_evidence_missing`. Every row here is a code the
    student sees in the Action Centre."""

    def test_the_codes_per_state(self):
        for route in ROUTES:
            for state in STATES:
                with self.subTest(route=route, state=state):
                    want = CHECK2_MOVED.get((route, state), CHECK2_BEFORE[(route, state)])
                    self.assertEqual(self.check2_codes(self.build_high_bills(route, state)),
                                     _since_td306(want))

    def test_only_a_true_stranger_or_an_unjudged_str_moves_a_code(self):
        self.assertEqual(sorted({s for _r, s in CHECK2_MOVED}), sorted(TRUE_STRANGER | UNJUDGED))
        for key, after in CHECK2_MOVED.items():
            with self.subTest(key=key):
                self.assertNotEqual(CHECK2_BEFORE[key], after)
        self.assertEqual(sorted(CHECK2_BEFORE), sorted((r, s) for r in ROUTES for s in STATES))


# ════════════════════════════════════════════════════════════════════════════════════════════
# 6. THE SWAP, END TO END — the open clarify, the new asks, and the email the cron sends
# ════════════════════════════════════════════════════════════════════════════════════════════
@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestWhatAStrangersStrHouseholdIsSent(WhoseStrBase):
    """The end-to-end answer the owner asked for: a household SUBMITTED before the change, on a
    stranger's STR, with bills reading high, already asked the `_str` clarify and already emailed.
    After the change the next Check-2 sync closes that clarify itself, raises the income variant
    and (salary route) the letter request, and re-arms the one-time notice; the hourly sweep then
    sends the EXISTING "query raised" email — the same template, no new words."""

    def _already_asked(self, route, state='true_stranger'):
        """The household as the OLD tree left it. Check-2 syncs run with `has_valid_str`
        answering as it did before TD-285 (True — currency only), and the student answers each
        clarify as it arrives (a clarify is once-ever, so an answered one never returns), until the
        lowest-priority `_str` high-utility clarify has had its turn and sits OPEN. Then the
        one-time email went out, two days ago."""
        from datetime import timedelta
        from django.utils import timezone
        from apps.scholarship.check2_queries import sync_check2_queries
        app = self.build_high_bills(route, state)
        # The household income the student REPORTED at apply — what the income variant quotes.
        # (With none on file it would be `high_utility_expense_noincome` since TD-306 — the same
        # ask without a figure; before TD-306 the student's copy showed the literal "RM {income}".)
        app.profile.household_income = 1500
        app.profile.save(update_fields=['household_income'])
        app.profile_completed_at = timezone.now() - timedelta(days=3)
        app.save(update_fields=['profile_completed_at'])
        with mock.patch('apps.scholarship.income_engine.followups.has_valid_str',
                        return_value=True), \
                mock.patch('apps.scholarship.income_engine.has_valid_str', return_value=True):
            for _round in range(10):
                sync_check2_queries(app)
                if self._check2(app, 'open') == [(_HU_STR, '')]:
                    break
                (app.resolution_items.filter(source='check2', kind='clarify', status='open')
                 .exclude(code=_HU_STR)
                 .update(status='resolved', resolved_by='student', resolved_at=timezone.now(),
                         resolution_text='answered'))
        self.assertEqual(self._check2(app, 'open'), [(_HU_STR, '')],
                         'the fixture never reached the old tree\'s `_str` clarify')
        app.query_raised_notified_at = timezone.now() - timedelta(days=2)
        app.save(update_fields=['query_raised_notified_at'])
        return app

    def _check2(self, app, status):
        return sorted(app.resolution_items.filter(source='check2', status=status,
                                                  code__in=CHECK2_CODES)
                      .values_list('code', 'resolved_by'))

    def test_salary_route_the_clarify_is_swapped_and_the_existing_email_goes_out(self):
        from django.core import mail
        from apps.scholarship.check2_queries import sync_check2_queries
        from apps.scholarship.emails.student_queries import (QUERY_RAISED_BODIES,
                                                             QUERY_RAISED_SUBJECTS)
        from apps.scholarship.services import send_due_query_emails
        app = self._already_asked('salary')
        sync_check2_queries(app)
        app.refresh_from_db()
        self.assertEqual(self._check2(app, 'resolved'), [(_HU_STR, 'system')])
        self.assertEqual(self._check2(app, 'open'), [(_LETTER, ''), (_HU, '')])
        hu = app.resolution_items.get(code=_HU)
        self.assertEqual(hu.params, {'amount': 400, 'income': 1500})
        self.assertIsNone(app.query_raised_notified_at)          # the one-time notice re-armed

        mail.outbox.clear()
        self.assertEqual(send_due_query_emails()['sent'], 1)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        from apps.scholarship.resolution import STUDENT_DOC_REQUEST_CODES
        items = app.resolution_items.filter(status='open')       # counted as the sweep counts
        n = (items.filter(source='check2').count()
             + items.filter(source='system', code__in=STUDENT_DOC_REQUEST_CODES).count()
             + items.filter(source='officer').exclude(kind='human').count())
        self.assertEqual(sent.subject, QUERY_RAISED_SUBJECTS['en'].format(programme=app.cohort.name))
        self.assertEqual(sent.body, QUERY_RAISED_BODIES['en'].format(
            name=app.profile.name, programme=app.cohort.name, n=n,
            link=sent.body.split('here: ')[1].split('\n')[0]))

    def test_str_route_the_clarify_is_swapped_and_no_letter_is_asked(self):
        from apps.scholarship.check2_queries import sync_check2_queries
        app = self._already_asked('str')
        sync_check2_queries(app)
        self.assertEqual(self._check2(app, 'resolved'), [(_HU_STR, 'system')])
        self.assertEqual(self._check2(app, 'open'), [(_HU, '')])

    def test_at_interview_the_clarify_is_closed_and_nothing_replaces_it(self):
        """⚠ From `interviewing` the machine may not ASK (owner, 2026-07-13) but still tidies:
        the open `_str` clarify is auto-resolved by the system, nothing is raised in its place,
        and no email goes out. Pinned so the owner sees it, not endorsed by it."""
        from django.core import mail
        from apps.scholarship.check2_queries import sync_check2_queries
        from apps.scholarship.services import send_due_query_emails
        app = self._already_asked('salary')
        app.status = 'interviewing'
        app.save(update_fields=['status'])
        sync_check2_queries(app)
        app.refresh_from_db()
        self.assertEqual(self._check2(app, 'resolved'), [(_HU_STR, 'system')])
        self.assertEqual(self._check2(app, 'open'), [])
        self.assertIsNotNone(app.query_raised_notified_at)
        mail.outbox.clear()
        self.assertEqual(send_due_query_emails()['sent'], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_an_unjudged_str_keeps_its_clarify_and_the_mothers_ic_is_asked(self):
        """OWNER'S F1 RULING: the mother's STR, only the father's IC on file. The STR still counts,
        so the open `_str` clarify STAYS open (no swap), and the mother's IC is asked — an
        uncapped doc request, tagged to her so the upload lands in her slot. The same existing
        query email then goes out; no new email words."""
        from django.core import mail
        from apps.scholarship.check2_queries import sync_check2_queries
        from apps.scholarship.emails.student_queries import QUERY_RAISED_SUBJECTS
        from apps.scholarship.services import send_due_query_emails
        with mock.patch('apps.scholarship.income_str_ownership.str_owner_ic_asks',
                        return_value={'missing': [], 'unreadable': []}):
            app = self._already_asked('salary', 'mothers_str_only_fathers_ic')
        sync_check2_queries(app)
        app.refresh_from_db()
        self.assertEqual(self._check2(app, 'resolved'), [])
        self.assertEqual(self._check2(app, 'open'), [(_HU_STR, ''), (_ASK_MOTHER_IC, '')])
        ask = app.resolution_items.get(code=_ASK_MOTHER_IC)
        self.assertEqual((ask.kind, ask.doc_type, ask.params),
                         ('doc', 'parent_ic', {'household_member': 'mother'}))
        self.assertIsNone(app.query_raised_notified_at)
        mail.outbox.clear()
        self.assertEqual(send_due_query_emails()['sent'], 1)
        self.assertEqual(mail.outbox[0].subject,
                         QUERY_RAISED_SUBJECTS['en'].format(programme=app.cohort.name))

    def test_an_ic_on_file_that_read_nothing_is_asked_as_unreadable(self):
        """REVIEW F-C. The mother's IC IS on file; it read only her NRIC and the STR offers only
        her name. She is not asked for an IC she uploaded ("not on file" would be false): the ask
        is `mother_ic_for_str_unreadable` — re-upload a clear one — tagged to her."""
        from apps.scholarship.check2_queries import sync_check2_queries
        with mock.patch('apps.scholarship.income_str_ownership.str_owner_ic_asks',
                        return_value={'missing': [], 'unreadable': []}):
            app = self._already_asked('salary', 'mothers_name_str_her_ic_read_nric')
        sync_check2_queries(app)
        self.assertEqual(self._check2(app, 'open'),
                         [(_HU_STR, ''), ('mother_ic_for_str_unreadable', '')])
        self.assertFalse(app.resolution_items.filter(code=_ASK_MOTHER_IC).exists())
        ask = app.resolution_items.get(code='mother_ic_for_str_unreadable')
        self.assertEqual((ask.kind, ask.doc_type, ask.params),
                         ('doc', 'parent_ic', {'household_member': 'mother'}))
