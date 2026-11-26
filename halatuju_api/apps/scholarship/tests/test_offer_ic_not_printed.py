"""OCR-13: the offer-letter IC status 'not_printed' — a blank IC on a letter from an issuer that prints
no IC by design (offer_exact.ISSUER_PRINTS_NO_IC: UUM and UPSI only). Grey "Not printed" on the chip;
every decision reader treats it exactly as 'unreadable', so no verdict moves (owner 2026-11-26).
Synthetic values only (made-up names and numbers)."""
import re
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import pathway_engine as pe

NRIC = '990101-14-5678'
OTHER_NRIC = '980202-10-1234'
NAME = 'ZORBEX QUENTARO BIN ALFEN'
UUM, UPSI = 'UNIVERSITI UTARA MALAYSIA', 'UNIVERSITI PENDIDIKAN SULTAN IDRIS'
UNIMAS, UTHM = 'UNIVERSITI MALAYSIA SARAWAK', 'UNIVERSITI TUN HUSSEIN ONN MALAYSIA'


def _np_doc(institution='', nric='', verdict='ok', inputs=None):
    vf = {'student_verdict': verdict, 'fields': {'candidate_name': NAME, 'candidate_nric': nric,
                                                 'institution': institution}}
    if inputs is not None:
        vf['offer_reader_inputs'] = inputs
    return SimpleNamespace(vision_fields=vf, doc_type='offer_letter',
                           application=SimpleNamespace(profile=SimpleNamespace(nric=NRIC, name=NAME)))


def _np_ic(**kw):
    return pe.student_offer_check(_np_doc(**kw))['ic']


LOCK = {'reader': 'deterministic', 'nric_check': 'blank', 'rules_lane': 'ua:UUM', 'nric_not_printed': True}


class NotPrintedStatusTest(SimpleTestCase):
    def test_ai_read_uum_and_upsi_blank_ic_is_not_printed(self):
        for inst in (UUM, UPSI, 'UUM', 'UPSI', 'Universiti Utara Malaysia', 'universiti pendidikan sultan idris',
                     'UNIVERSITI UTARA MALAYSIA (UUM)', 'Universiti Pendidikan Sultan Idris, UPSI'):
            with self.subTest(inst=inst):
                self.assertEqual(_np_ic(institution=inst), 'not_printed')

    def test_rules_lock_blank_ic_is_not_printed(self):
        self.assertEqual(_np_ic(institution=UUM, inputs=LOCK), 'not_printed')
        self.assertEqual(_np_ic(institution='', inputs=dict(LOCK, rules_lane='ua:UPSI')), 'not_printed')

    def test_a_lock_flag_needs_the_deterministic_reader(self):
        self.assertEqual(_np_ic(institution=UNIMAS, inputs=dict(LOCK, reader='gemini')), 'unreadable')
        self.assertEqual(_np_ic(institution=UNIMAS, inputs=dict(LOCK, nric_not_printed='yes')), 'unreadable')
        self.assertEqual(_np_ic(institution=UNIMAS, inputs=dict(LOCK, rules_lane='ua:UNIMAS')), 'unreadable')
        with mock.patch('apps.scholarship.offer_exact.ISSUER_PRINTS_NO_IC', frozenset({'ua:UPSI'})):
            self.assertEqual(_np_ic(institution='', inputs=LOCK), 'unreadable')

    def test_other_issuers_keep_unreadable(self):
        for inst in (UNIMAS, UTHM, 'UNIMAS', 'UTHM', 'UNIVERSITI MALAYA', ''):
            with self.subTest(inst=inst):
                self.assertEqual(_np_ic(institution=inst), 'unreadable')

    def test_a_printed_ic_on_a_uum_letter_still_matches_or_mismatches(self):
        self.assertEqual(_np_ic(institution=UUM, nric=NRIC), 'match')
        self.assertEqual(_np_ic(institution=UUM, nric=OTHER_NRIC), 'mismatch')
        self.assertEqual(_np_ic(institution=UPSI, nric=NRIC, inputs=LOCK), 'match')

    def test_not_extracted_stays_pending(self):
        self.assertEqual(_np_ic(institution=UUM, verdict='review_manually'), 'pending')
        self.assertEqual(_np_ic(institution=UUM, verdict='', inputs=LOCK), 'pending')

    def test_not_printed_is_never_a_match(self):
        self.assertEqual(pe._ic_status('', NRIC, True, not_printed=True), 'not_printed')
        self.assertEqual(pe._ic_status('', NRIC, True), 'unreadable')
        self.assertEqual(pe._ic_status('', NRIC, False, not_printed=True), 'pending')


class NoIcIssuerResolverTest(SimpleTestCase):
    def test_exact_names_resolve(self):
        self.assertEqual(pe.no_ic_issuer_lane(UUM), 'ua:UUM')
        self.assertEqual(pe.no_ic_issuer_lane(' uum '), 'ua:UUM')
        self.assertEqual(pe.no_ic_issuer_lane(UPSI), 'ua:UPSI')

    def test_near_names_never_resolve(self):
        for near in ('UNIVERSITI UTARA MALAYSIAN', 'UUM SINTOK', 'UNIVERSITI UTARA MALAYSIA, SINTOK, KEDAH',
                     'UNIVERSITI PENDIDIKAN SULTAN IDRISS', 'UNIVERSITI PENDIDIKAN SULTAN', 'UPSI TANJONG MALIM',
                     'UNIMAS', 'UTHM', 'UM', 'UUMM', 'KOLEJ UNIVERSITI UTARA MALAYSIA', '', None, 123):
            with self.subTest(near=near):
                self.assertEqual(pe.no_ic_issuer_lane(near), '')

    def test_only_the_approved_set_counts(self):
        with mock.patch('apps.scholarship.offer_exact.ISSUER_PRINTS_NO_IC', frozenset({'ua:UUM'})):
            self.assertEqual(pe.no_ic_issuer_lane(UPSI), '')
            self.assertEqual(pe.no_ic_issuer_lane(UUM), 'ua:UUM')

    def test_the_map_names_only_the_approved_issuers(self):
        from apps.scholarship.offer_exact import ISSUER_PRINTS_NO_IC
        self.assertEqual(set(pe._NO_IC_ISSUER_NAMES.values()), set(ISSUER_PRINTS_NO_IC))
        self.assertEqual(set(ISSUER_PRINTS_NO_IC), {'ua:UUM', 'ua:UPSI'})


def _np_chk(name, ic, programme=''):
    return {'name': name, 'ic': ic, 'programme': programme, 'institution': programme, 'pathway': 'unknown',
            'issuer': '', 'declared_programme': '', 'declared_institution': '', 'reporting_date': ''}


NAMES = ('match', 'partial', 'mismatch', 'unreadable', 'pending')
PATCH = 'apps.scholarship.pathway_engine.student_offer_check'


class VerdictParityTest(SimpleTestCase):
    """For each decision reader, ic='not_printed' gives exactly what ic='unreadable' gives."""

    def _both(self, run):
        for name in NAMES:
            for prog in ('', 'SARJANA MUDA PERAKAUNAN'):
                got = []
                for ic in ('unreadable', 'not_printed'):
                    with mock.patch(PATCH, return_value=_np_chk(name, ic, prog)):
                        got.append(run())
                with self.subTest(name=name, prog=prog):
                    self.assertEqual(got[0], got[1])

    def test_verdict_pathway(self):
        from apps.scholarship.verdict_pathway import offer_pathway_fact
        app = SimpleNamespace(pathway_confirmed_at=None)
        offer = SimpleNamespace(vision_fields={'student_verdict': 'ok'})
        with mock.patch('apps.scholarship.pathway_engine.offer_hearing_ok', return_value=False):
            self._both(lambda: offer_pathway_fact(app, offer))

    def test_verdict_ladder_red_chips(self):
        from apps.scholarship import verdict_ladder
        with mock.patch.object(verdict_ladder, '_latest_doc', return_value=SimpleNamespace()):
            self._both(lambda: verdict_ladder._pathway_red_chips(SimpleNamespace()))

    def test_help_verdict(self):
        from apps.scholarship.help_verdict import _help_offer_letter
        self._both(lambda: _help_offer_letter(SimpleNamespace(vision_fields={'student_verdict': 'ok'})))

    def test_resolution_doc_match(self):
        from apps.scholarship.resolution_doc_match import _offer_letter
        with mock.patch('apps.scholarship.pathway_engine.offer_official_status', return_value='genuine'):
            self._both(lambda: _offer_letter(SimpleNamespace(), 'offer_letter'))

    def test_person_red_keys(self):
        from apps.scholarship.doc_red_keys import person_red, red_keys
        for name in NAMES:
            with self.subTest(name=name):
                a, b = _np_chk(name, 'unreadable'), _np_chk(name, 'not_printed')
                self.assertEqual(red_keys('offer_letter', a), red_keys('offer_letter', b))
                self.assertEqual(person_red('offer_letter', a), person_red('offer_letter', b))


class EveryIcReaderKnowsNotPrintedTest(SimpleTestCase):
    """Guard: a production line that compares an offer check's 'ic' with 'unreadable' must also name
    'not_printed' — so a new reader can't treat the two apart by accident (eval/ is frozen history)."""
    _IC = re.compile(r"""(\[['"]ic['"]\]|\.get\(['"]ic['"]\))\s*(==|!=|in\b|not\s+in\b)""")

    def test_scan(self):
        root = Path(__file__).resolve().parents[1]
        seen, bad = 0, []
        for path in root.rglob('*.py'):
            rel = path.relative_to(root).as_posix()
            if rel.startswith(('tests/', 'eval/', 'migrations/')):
                continue
            for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if self._IC.search(line):
                    seen += 1
                    if 'unreadable' in line and 'not_printed' not in line:
                        bad.append(f'{rel}:{n}')
        self.assertGreater(seen, 5)
        self.assertEqual(bad, [])
