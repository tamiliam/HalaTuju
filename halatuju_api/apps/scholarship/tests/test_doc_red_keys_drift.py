"""TD-110 — the two "is this document wrong?" readers, characterised against ONE input list.

`resolution.doc_match_verdict` (the Action Centre: may this upload close its task?) and
`services.blockers.document_red_blockers` (the consent gate: may she submit?) each classified a
document's person-mismatch with their own copy of "which check keys count". The keys now live in
`doc_red_keys.PERSON_RED_KEYS` and both read it.

This file is the drift test. It drives BOTH readers over the same matrix — every document type,
every key of its check set to 'mismatch' one at a time, plus a clean check — and asserts they
agree on "is this document a confirmed person-red?", EXCEPT on the rows in `KNOWN_DIFFERENCES`.
Each of those is a disagreement found by the characterisation (written against the unchanged tree
on 2026-10-04), pinned with which side holds it and why. **None was changed**: picking a winner on
a row where the two disagree changes who may submit or whether a task closes, which is an owner's
ruling (TD-262's rule). A NEW disagreement — a key added to one reader and not the other — fails.

The gate is driven in the context where it is strictest (salary route, the slip's member selected,
income NOT yet established), so every difference below is a difference of the RULE and not of a
context the gate deliberately relaxes.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import academic_engine, doc_red_keys, income_engine, pathway_engine, resolution
from apps.scholarship.services import blockers
from apps.scholarship.tests.package_patch import patch_engine

#: The check each reader calls, per document type: (module, function name, every key it reads).
CHECKS = {
    'results_slip': (academic_engine, 'student_slip_check', ('name', 'results')),
    'offer_letter': (pathway_engine, 'student_offer_check', ('name', 'ic')),
    'parent_ic': (income_engine, 'student_income_ic_check',
                  ('name_status', 'proof_name_status', 'proof_nric_status')),
    'salary_slip': (income_engine, 'student_income_proof_check', ('name_status', 'nric_status')),
    'epf': (income_engine, 'student_income_proof_check', ('name_status', 'nric_status')),
    'str': (income_engine, 'student_str_check', ('name_status', 'nric_status')),
    'birth_certificate': (income_engine, 'student_bc_check',
                          ('child_status', 'mother_status', 'father_status')),
    'guardianship_letter': (income_engine, 'student_guardianship_check',
                            ('guardian_status', 'ward_status')),
}

#: (doc_type, the key set to 'mismatch' or a named extra) -> (action_centre_red, gate_red, why).
#: ⚠ May only SHRINK. Each row is an open question for the owner, recorded in TD-110's closure.
KNOWN_DIFFERENCES = {
    ('results_slip', 'results'): (True, False,
        'A GRADE mismatch: the gate stopped blocking on it (owner 2026-07-08 — the slip is the '
        'record, reconciled at review); the Action Centre still holds a slip task open on it.'),
    ('parent_ic', 'name_status+chain'): (False, True,
        'The IC-number chain (#9) rescues a parent IC in the Action Centre only; the gate still '
        'blocks it unless income is already established (when it skips the cluster entirely).'),
    ('parent_ic', 'proof_name_status+chain'): (False, True, 'as above — the chain rescue'),
    ('parent_ic', 'proof_nric_status+chain'): (False, True, 'as above — the chain rescue'),
    ('epf', 'name_status'): (True, False,
        'EPF never substitutes the salary slip, so the gate never blocks on it; the Action Centre '
        'holds an EPF task whose upload is the wrong person.'),
    ('epf', 'nric_status'): (True, False, 'as above — EPF is supplementary at the gate'),
    ('offer_letter', 'not_genuine'): (True, False,
        'A non-official offer: the Action Centre refuses it as the answer to "upload your official '
        'offer"; the gate has its OWN offer-genuineness blocker (with the STPM and Probable+ '
        'exemptions), outside document_red_blockers.'),
}


def _doc(doc_type):
    return SimpleNamespace(
        doc_type=doc_type, household_member='father', vision_run_at='2026-10-04',
        vision_error='', vision_fields={'student_verdict': 'ok'},
        vision_nric='', vision_name='', application=SimpleNamespace(profile=None))


def _readings(doc_type, check, *, not_genuine=False):
    """(Action Centre says mismatch?, gate emits a code?) for one document with `check`."""
    module, fn, _keys = CHECKS[doc_type]
    app = SimpleNamespace(income_route='salary', income_earner='father')
    doc = _doc(doc_type)
    patcher = (patch_engine(module, fn, return_value=dict(check)) if module is income_engine
               else mock.patch.object(module, fn, return_value=dict(check)))
    with patcher, \
            mock.patch.object(pathway_engine, 'offer_official_status',
                              return_value='not_genuine' if not_genuine else 'official'), \
            patch_engine(income_engine, 'income_established', return_value=False), \
            patch_engine(income_engine, 'working_members', return_value=['father']), \
            mock.patch.object(blockers, 'live_docs', return_value=[doc]):
        ac = resolution.doc_match_verdict(doc) == 'mismatch'
        gate = bool(blockers.document_red_blockers(app))
    return ac, gate


def _matrix():
    """Every (doc_type, label, check, not_genuine) row the two readers are compared on."""
    rows = []
    for dt, (_m, _f, keys) in CHECKS.items():
        rows.append((dt, 'clean', {k: 'match' for k in keys}, False))
        for k in keys:
            rows.append((dt, k, {**{x: 'match' for x in keys}, k: 'mismatch'}, False))
            if dt == 'parent_ic':
                rows.append((dt, f'{k}+chain',
                             {**{x: 'match' for x in keys}, k: 'mismatch', 'chain_verified': True,
                              'readable': True}, False))
    for state in income_engine.STR_RED_STATES:
        rows.append(('str', f'current_status={state}', {'current_status': state}, False))
    rows.append(('offer_letter', 'not_genuine', {'name': 'match', 'ic': 'match'}, True))
    return rows


class TestTheTwoReadersAgree(SimpleTestCase):

    def test_the_matrix_is_not_empty(self):
        self.assertGreaterEqual(len(_matrix()), 30, 'a matrix that shrank compares nothing')

    def test_they_agree_on_every_row_but_the_pinned_differences(self):
        surprises, still_different = [], set()
        for dt, label, check, not_genuine in _matrix():
            ac, gate = _readings(dt, check, not_genuine=not_genuine)
            pinned = KNOWN_DIFFERENCES.get((dt, label))
            if pinned is not None:
                if (ac, gate) == pinned[:2]:
                    still_different.add((dt, label))
                else:
                    surprises.append(f'{dt}/{label}: pinned {pinned[:2]}, now {(ac, gate)}')
            elif ac != gate:
                surprises.append(f'{dt}/{label}: Action Centre red={ac}, gate red={gate} — a NEW '
                                 f'disagreement between the two readers')
        self.assertEqual(surprises, [])
        # The ledger may only shrink: a pinned row that now AGREES must leave KNOWN_DIFFERENCES.
        self.assertEqual(sorted(set(KNOWN_DIFFERENCES) - still_different), [])

    def test_a_clean_document_is_red_to_neither(self):
        for dt, (_m, _f, keys) in CHECKS.items():
            with self.subTest(dt=dt):
                self.assertEqual(_readings(dt, {k: 'match' for k in keys}), (False, False))

    def test_the_father_row_holds_neither_door(self):
        """BrightPath #23: a BC father mismatch is read and shown, never a block or a held task."""
        keys = CHECKS['birth_certificate'][2]
        check = {**{k: 'match' for k in keys}, 'father_status': 'mismatch'}
        self.assertEqual(_readings('birth_certificate', check), (False, False))


class TestTheUnreadableHalfDiffersOnTheSlipTable(SimpleTestCase):
    """The OTHER half of TD-110, pinned and NOT changed: a slip whose name reads but whose SUBJECT
    table does not. The Action Centre holds the task ('unreadable' — fixed there, "previously only
    the name was checked"); the gate's `document_unreadable_blockers` still reads the name only, so
    it lets her submit. An owner's ruling — the gate is the one that would start refusing."""

    def test_a_slip_with_an_unreadable_subject_table(self):
        check = {'name': 'match', 'results': 'match', 'subjects': 'unreadable'}
        doc = _doc('results_slip')
        app = SimpleNamespace(income_route='', income_earner='')
        with mock.patch.object(academic_engine, 'student_slip_check', return_value=check), \
                mock.patch.object(blockers, 'latest_doc',
                                  side_effect=lambda a, t: doc if t == 'results_slip' else None):
            self.assertEqual(resolution.doc_match_verdict(doc), 'unreadable')
            self.assertNotIn('results_slip_unreadable', blockers.document_unreadable_blockers(app))
            # …and the name half agrees on both sides (the positive control).
            check['name'] = 'unreadable'
            self.assertEqual(resolution.doc_match_verdict(doc), 'unreadable')
            self.assertIn('results_slip_unreadable', blockers.document_unreadable_blockers(app))


class TestTheSharedKeys(SimpleTestCase):

    def test_both_readers_name_the_table_not_a_copy(self):
        import inspect
        for fn in (resolution.doc_match_verdict, blockers.document_red_blockers):
            with self.subTest(fn=fn.__name__):
                self.assertIn('person_red(', inspect.getsource(fn))

    def test_the_table_is_pinned_whole(self):
        """The agreement matrix cannot see a key REMOVED from the table — both readers lose it
        together and still agree. So the table is pinned as a literal: shrinking it un-reds a
        document at BOTH the Action Centre and the consent gate, and that is a deliberate,
        owner-visible edit, never a tidy-up (review of Later-tier batch 3, 2026-10-04)."""
        self.assertEqual(doc_red_keys.PERSON_RED_KEYS, {
            'offer_letter': ('name', 'ic'),
            'parent_ic': ('name_status', 'proof_name_status', 'proof_nric_status'),
            'salary_slip': ('name_status', 'nric_status'),
            'epf': ('name_status', 'nric_status'),
            'str': ('name_status', 'nric_status'),
            'birth_certificate': ('child_status', 'mother_status'),
            'guardianship_letter': ('guardian_status', 'ward_status'),
        })

    def test_every_tabled_type_is_one_the_readers_handle(self):
        self.assertEqual(set(doc_red_keys.PERSON_RED_KEYS) - set(CHECKS), set())
        self.assertNotIn('results_slip', doc_red_keys.PERSON_RED_KEYS)
