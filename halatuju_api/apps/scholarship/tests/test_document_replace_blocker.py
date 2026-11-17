"""H6 fix round 3 (owner 2026-11-17): the blocker allowance before consent.

Before consent nobody can ask (a reviewer's request is refused until she consents), so a slot whose live copy
stops consent would be a dead end at four uploads. While the copy (or the slot's empty type) holds the consent
gate and `profile_completed_at` is unset, the slot takes up to four more, eight in all; the 409 at eight sends
her to support (`replace_limit_support`), never to a reviewer. After the copy passes, after consent, or for a
copy that does not hold the gate, the normal four stand.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import branding
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.services.consent_blockers import EVERY_SLOT, consent_blockers, consent_blocking_slots
from apps.scholarship.tests.doc_keys import issued_key as _key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, create_document, make_application, make_cohort, make_student,
)

DOCS = '/api/v1/scholarship/documents/'
_UNREADABLE = {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable', 'service_error': False, 'error': ''}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, CHECK2_STUDENT_QUERIES_ENABLED=True)
@patch('apps.scholarship.storage.delete_own_doc_objects', return_value=None)
@patch('apps.scholarship.upload_read.needs_read', return_value=True)    # recorded queued: no paid read
@patch('apps.scholarship.storage.object_exists', return_value=True)
class TestBlockerAllowance(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='rb', name='Blocker', year=2026)

    def _case(self, stage='shortlisted'):
        student = make_student()
        app = make_application(stage, cohort=self.cohort, student=student)
        return app, authed_client(student.supabase_user_id)

    def _post(self, client, app, doc_type='offer_letter'):
        return client.post(DOCS, {'doc_type': doc_type, 'storage_path': _key(app, doc_type, 'x'),
                                  'original_filename': 'a.pdf', 'size': 1000, 'household_member': '',
                                  'request_code': '', 'replace': True}, format='json')

    def _blocking_offer(self, app):
        """The first upload: an offer letter the read could not make out, which holds the consent gate."""
        return ApplicantDocument.objects.create(application=app, doc_type='offer_letter', storage_path='first',
                                                vision_fields=_UNREADABLE)

    def _listed(self, client, doc_type='offer_letter'):
        return [(d['replaces_left'], d['replace_support'])
                for d in client.get(DOCS).json()['documents'] if d['doc_type'] == doc_type]

    def _codes(self, client, app, n, doc_type='offer_letter'):
        return [self._post(client, app, doc_type).status_code for _i in range(n)]

    def test_the_signal_is_the_live_copy_the_gate_reads(self, *_):
        app, _c = self._case()
        doc = self._blocking_offer(app)
        slots, _missing = consent_blocking_slots(app)
        self.assertIn(('offer_letter', '', ''), slots)
        doc.delete()                                                      # emptied: its type is asked for
        _slots, missing = consent_blocking_slots(app)
        self.assertIn(('offer_letter', None), missing)

    def test_a_blocking_copy_before_consent_gets_uploads_five_to_eight_then_support(self, *_):
        app, client = self._case()
        self._blocking_offer(app)
        self.assertEqual(self._codes(client, app, 3), [201, 201, 201])    # uploads 2 to 4: the normal cap
        self.assertEqual(self._listed(client), [(4, False)])               # the server's count: four more
        self.assertEqual(self._codes(client, app, 4), [201, 201, 201, 201])   # uploads 5 to 8
        self.assertEqual(self._listed(client), [(0, True)])
        resp = self._post(client, app)                                     # the 9th
        body = resp.json()
        self.assertEqual((resp.status_code, body['error'], body['code']),
                         (409, 'replace_limit_reached', 'replace_limit_support'))
        email = branding.for_application(app).email_support
        self.assertEqual(body['support_email'], email)
        self.assertIn(f'write to us at {email}', body['message'])
        self.assertNotIn('reviewer', body['message'])
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 8)   # nothing recorded

    def test_an_emptied_blocking_slot_still_gets_the_allowance_and_no_more(self, *_):
        app, client = self._case()
        self._blocking_offer(app)
        self.assertEqual(self._codes(client, app, 3), [201, 201, 201])
        ApplicantDocument.objects.filter(application=app).delete()        # as Remove leaves it: the count stays
        self.assertEqual(self._codes(client, app, 5), [201, 201, 201, 201, 409])

    def test_once_the_copy_passes_the_normal_cap_applies(self, *_):
        app, client = self._case()
        self._blocking_offer(app)
        self.assertEqual(self._codes(client, app, 4), [201, 201, 201, 201])   # the 5th: allowance
        with patch('apps.scholarship.services.consent_blockers.consent_blocking_slots',
                   return_value=(set(), set())):                          # the copy now passes the gate
            self.assertEqual(self._listed(client), [(0, True)])           # shut; before consent: support
            resp = self._post(client, app)
            self.assertEqual((resp.status_code, resp.json()['code']), (409, 'replace_limit_support'))

    def test_after_consent_the_normal_cap_applies(self, *_):
        app, client = self._case('profile_complete')
        self.assertIsNotNone(app.profile_completed_at)
        self._blocking_offer(app)
        self.assertEqual(self._codes(client, app, 4), [201, 201, 201, 409])
        resp = self._post(client, app)
        self.assertEqual((resp.json()['code'], self._listed(client)), ('replace_limit_reached', [(0, False)]))

    def test_a_copy_that_does_not_hold_the_gate_gets_no_extra_tries(self, *_):
        app, client = self._case()
        slots, missing = consent_blocking_slots(app)
        self.assertTrue(slots or missing)                                  # the gate holds her, elsewhere
        self.assertNotIn(EVERY_SLOT, missing)                              # every code of hers is mapped
        ApplicantDocument.objects.create(application=app, doc_type='bank_statement', storage_path='first',
                                         vision_fields=_UNREADABLE)
        self.assertEqual(self._codes(client, app, 4, 'bank_statement'), [201, 201, 201, 409])
        resp = self._post(client, app, 'bank_statement')
        # Fix round 4: before consent nobody can ask, so even the normal cap's 409 sends her to support.
        self.assertEqual(resp.json()['code'], 'replace_limit_support')
        self.assertEqual(self._listed(client, 'bank_statement'), [(0, True)])


# ── Fix round 4: the dead end is impossible by construction ─────────────────────────────────────────────
_STUDENT_NRIC, _STUDENT = '060606-14-0001', 'Placeholder Student'
_FATHER, _FATHER_NRIC = 'Placeholder Father', '700707-14-0003'
_CHECKED = {'issuer_header': '', 'approver_name': '', 'approver_title': '', 'has_stamp_or_signature': 'no'}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, CHECK2_STUDENT_QUERIES_ENABLED=True)
@patch('apps.scholarship.storage.delete_own_doc_objects', return_value=None)
@patch('apps.scholarship.upload_read.needs_read', return_value=True)    # recorded queued: no paid read
@patch('apps.scholarship.storage.object_exists', return_value=True)
class TestEveryGateCodeOpensASlot(TestCase):
    """The round 3 review found gate codes the map missed (an STR needing its recipient's IC number, an
    unsigned income letter, an STR no card matched): their slots shut at four before consent, with nobody
    able to ask. Each is now mapped, and any code the map cannot tie to a slot opens every slot."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='rb4', name='Blocker4', year=2026)

    def _app(self, **kw):
        student = make_student(nric=_STUDENT_NRIC, name=_STUDENT)
        kw.setdefault('income_route', 'str')
        kw.setdefault('income_earner', 'father')
        kw.setdefault('father_name', _FATHER)
        kw.setdefault('income_working_members', [])
        app = make_application('shortlisted', cohort=self.cohort, student=student, mother_name='Placeholder Mother',
                               father_occupation='private', mother_occupation='homemaker',
                               other_family_members=[], **kw)
        return app, authed_client(student.supabase_user_id)

    def _post(self, client, app, doc_type='str', member=''):
        return client.post(DOCS, {'doc_type': doc_type, 'storage_path': _key(app, doc_type, 'x'),
                                  'original_filename': 'a.pdf', 'size': 1000, 'household_member': member,
                                  'request_code': '', 'replace': True}, format='json')

    def _str(self, app, name, nric=''):
        return create_document(application=app, doc_type='str', household_member='father', storage_path='t/str',
                               vision_run_at=timezone.now(), vision_fields={
                                   'fields': {'recipient_name': name, 'recipient_nric': nric, 'status': 'Lulus',
                                              'year': '2026', 'source_type': 'semakan_status'},
                                   'student_verdict': 'ok', 'error': ''})

    def _father_ic(self, app, name):
        return create_document(application=app, doc_type='parent_ic', household_member='father', storage_path='t/pic',
                               vision_run_at=timezone.now(), vision_name=name, vision_nric=_FATHER_NRIC)

    def _walk(self, client, app, doc_type, member, n):
        return [self._post(client, app, doc_type, member).status_code for _i in range(n)]

    def test_d_an_str_needing_its_recipients_ic_number_opens_the_str_and_the_card(self, *_):
        app, client = self._app(father_name='Tan Ah Kau')
        self._father_ic(app, 'TAN AH KAU')
        self._str(app, 'TAN AH KOW')                         # one syllable off, no IC number on the page
        codes = consent_blockers(app)
        self.assertIn('str_needs_recipient_ic:father', codes)
        slots, missing = consent_blocking_slots(app)
        self.assertIn(('str', 'father', ''), slots)
        self.assertIn(('parent_ic', 'father', ''), slots)
        self.assertNotIn(EVERY_SLOT, missing)
        self.assertEqual(self._walk(client, app, 'str', '', 7), [201] * 7)                # uploads 2 to 8
        self.assertEqual(self._post(client, app).json()['code'], 'replace_limit_support')  # the 9th
        self.assertEqual(self._walk(client, app, 'parent_ic', 'father', 7), [201] * 7)

    def test_e_an_unsigned_income_letter_opens_its_own_slot(self, *_):
        app, client = self._app(income_route='salary', income_earner='', income_working_members=['father'],
                                income_declared={'father': 800})
        self._father_ic(app, _FATHER.upper())
        create_document(application=app, doc_type='income_support_doc', household_member='father',
                        storage_path='t/isd', vision_run_at=timezone.now(), vision_fields={
                            'fields': {'amount': 'RM800', **_CHECKED}, 'student_verdict': 'ok', 'error': '',
                            'authenticity': {'status': 'suspect', 'doc_seen': 'declaration', 'probability': 0.5}})
        self.assertIn('income_doc_unapproved:father', consent_blockers(app))
        slots, missing = consent_blocking_slots(app)
        self.assertIn(('income_support_doc', 'father', ''), slots)
        self.assertNotIn(EVERY_SLOT, missing)
        self.assertEqual(self._walk(client, app, 'income_support_doc', 'father', 7), [201] * 7)
        resp = self._post(client, app, 'income_support_doc', 'father')
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'replace_limit_support'))

    def test_an_str_no_card_could_match_opens_the_str_and_the_cards(self, *_):
        app, client = self._app()
        self._father_ic(app, _FATHER.upper())
        self._str(app, '')                                   # the recipient did not read
        self.assertIn('income_document_unreadable', consent_blockers(app))
        slots, missing = consent_blocking_slots(app)
        self.assertIn(('str', 'father', ''), slots)
        self.assertIn(('parent_ic', 'father', ''), slots)
        self.assertEqual(self._walk(client, app, 'str', '', 7), [201] * 7)

    def test_an_str_tagged_to_an_earlier_earner_opens_the_current_earners_str_slot(self, *_):
        app, client = self._app(income_earner='mother')
        stale = self._str(app, _FATHER.upper(), _FATHER_NRIC)    # tagged 'father', last year's
        stale.vision_fields['fields']['year'] = '2025'
        stale.save()
        self.assertTrue(any(c.startswith('str_stale') for c in consent_blockers(app)))
        slots, _missing = consent_blocking_slots(app)
        self.assertIn(('str', 'mother', ''), slots)
        self.assertEqual(self._walk(client, app, 'str', '', 7), [201] * 7)

    def test_a_gate_code_the_map_cannot_tie_opens_every_slot(self, *_):
        app, client = self._app()
        with patch('apps.scholarship.services.consent_blockers.consent_blockers',
                   return_value=['quiz_incomplete', 'a_code_added_next_year']):
            slots, missing = consent_blocking_slots(app)
            self.assertIn(EVERY_SLOT, missing)
            self.assertEqual(self._walk(client, app, 'bank_statement', '', 8), [201] * 8)  # first + seven
            self.assertEqual(self._post(client, app, 'bank_statement').json()['code'], 'replace_limit_support')

    def test_every_code_the_gate_can_give_is_mapped_or_opens_every_slot(self, *_):
        """Walks the consent gate's SOURCE (consent_blockers and every function of the two blocker modules it
        reaches) for each code it can emit, so a code added later is covered without editing this test."""
        import importlib
        cb_module = importlib.import_module('apps.scholarship.services.consent_blockers')
        emitted = _gate_codes()
        for known in ('quiz_incomplete', 'str_missing', 'offer_not_official', 'ic_unreadable', 'str_not_household',
                      'str_needs_recipient_ic', 'income_doc_unapproved', 'income_document_unreadable',
                      'income_evidence_missing', 'parent_ic_missing', 'str_person_mismatch', 'ic_service_down'):
            self.assertIn(known, emitted)                    # the walk reads the real gate
        exempt = set(cb_module.NOT_DOCUMENT_CODES) | set(cb_module.OUR_WAIT_CODES)
        self.assertLessEqual(exempt, emitted)                # no stale exemption
        app, _client = self._app()
        for head in sorted(emitted):
            for code in (head, f'{head}:father'):
                with self.subTest(code=code), patch(
                        'apps.scholarship.services.consent_blockers.consent_blockers', return_value=[code]):
                    slots, missing = consent_blocking_slots(app)
                    if head in exempt:
                        self.assertEqual((slots, missing), (set(), set()))
                    else:
                        self.assertTrue(slots or missing)    # mapped to a slot, or EVERY_SLOT

    def test_before_consent_the_normal_cap_409_sends_her_to_support(self, *_):
        app, client = self._app()
        with patch('apps.scholarship.services.consent_blockers.consent_blocking_slots',
                   return_value=(set(), set())):
            self.assertEqual(self._walk(client, app, 'bank_statement', '', 4), [201] * 4)
            body = self._post(client, app, 'bank_statement').json()
        self.assertEqual((body['error'], body['code']), ('replace_limit_reached', 'replace_limit_support'))
        email = branding.for_application(app).email_support
        self.assertIn(f'write to us at {email}', body['message'])
        self.assertNotIn('reviewer', body['message'])


def _gate_codes():
    """Every code head (the part before ':') the consent gate can emit, read from its source: the string
    literals and module constants inside each append / add / extend argument and each return value of
    `consent_blockers` and of every function it reaches in `services/consent_blockers.py` and
    `services/blockers.py`."""
    import ast
    import importlib
    import inspect
    import re
    from apps.scholarship import income_declaration, income_str_ownership
    blockers = importlib.import_module('apps.scholarship.services.blockers')    # the package re-exports the
    cb_module = importlib.import_module('apps.scholarship.services.consent_blockers')   # functions' names
    consts = {}
    for mod in (income_str_ownership, income_declaration, blockers, cb_module):
        consts.update({k: v for k, v in vars(mod).items() if k.isupper() and isinstance(v, str)})
    funcs = {}
    for mod in (blockers, cb_module):
        for node in ast.parse(inspect.getsource(mod)).body:
            if isinstance(node, ast.FunctionDef):
                funcs[node.name] = node
    seen, todo, heads = set(), ['consent_blockers'], set()

    def collect(expr):
        for n in ast.walk(expr):
            text = None
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                text = n.value
            elif isinstance(n, ast.Name) and n.id in consts:
                text = consts[n.id]
            if text is not None:
                head = text.split(':', 1)[0]
                if re.fullmatch(r'[a-z][a-z0-9_]*', head):
                    heads.add(head)

    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for n in ast.walk(funcs[name]):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcs:
                todo.append(n.func.id)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ('append', 'add',
                                                                                              'extend'):
                for arg in n.args:
                    collect(arg)
            elif isinstance(n, ast.Return) and n.value is not None:
                collect(n.value)
    return heads
