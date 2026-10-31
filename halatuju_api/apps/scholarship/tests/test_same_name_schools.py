"""Same-name schools carry their town; documents are compared on the NAME only (owner, 2026-10-31).

Our lists now store "SMK CONVENT, TAIPING" where several schools share "SMK CONVENT". The owner's
ruling for the comparison: *"The model need to match the school names only and not the town as well
for this set of schools."* So `school_name_core` drops our ", TOWN" — and only ours — on both sides
of every record-vs-document school compare: the offer letter's institution (`_field_status`, which
drives `institution_status`) and the school-leaving certificate's school chip (`_school_match`).

The drift test at the bottom keeps the server's generated set equal to the names the web lists hold,
because the set is what decides whether a comma is ours.
"""
import json
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.academic_engine import _school_match
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.pathway_engine import _field_status, offer_pathway_match
from apps.scholarship.same_name_schools import SAME_NAME_SCHOOL_STATES, SAME_NAME_SCHOOLS
from apps.scholarship.school_names import clean_school_name, keep_our_town, school_name_core
from apps.scholarship.services import confirm_pathway
from apps.scholarship.tests.factories import make_application

WEB_DATA = Path(__file__).resolve().parents[4] / 'halatuju-web' / 'src' / 'data'


class TestSchoolNameCore(SimpleTestCase):
    def test_drops_our_town_only(self):
        self.assertEqual(school_name_core('SMK CONVENT, TAIPING'), 'SMK CONVENT')
        self.assertEqual(school_name_core('  SMK CHUNG HUA, SIBU '), 'SMK CHUNG HUA')

    def test_recognises_a_recased_or_spelt_out_copy(self):
        recased = clean_school_name('SMK CONVENT, TAIPING')   # "Sekolah Menengah Kebangsaan Convent, Taiping"
        self.assertEqual(school_name_core(recased), 'Sekolah Menengah Kebangsaan Convent')
        self.assertEqual(school_name_core('smk convent,  taiping'), 'smk convent')

    def test_a_real_comma_or_a_typed_town_is_left_alone(self):
        # "SMK PETAGAS, PENAMPANG" is the MOE's own name; nothing shares it.
        self.assertEqual(school_name_core('SMK PETAGAS, PENAMPANG'), 'SMK PETAGAS, PENAMPANG')
        self.assertEqual(school_name_core('SMK CONVENT, NOWHERE'), 'SMK CONVENT, NOWHERE')
        self.assertEqual(school_name_core('SMK CONVENT'), 'SMK CONVENT')
        self.assertEqual(school_name_core(''), '')
        self.assertEqual(school_name_core(None), '')


class TestOfferInstitution(SimpleTestCase):
    """`institution_status` = `_field_status(pre_u_institution, offer institution)`."""

    def test_letter_without_the_town_matches(self):
        self.assertEqual(_field_status('SMK CONVENT, TAIPING', 'SMK CONVENT'), 'match')

    def test_letter_with_the_town_matches(self):
        self.assertEqual(_field_status('SMK CONVENT, TAIPING', 'SEKOLAH MENENGAH KEBANGSAAN CONVENT TAIPING'), 'match')
        self.assertEqual(_field_status('SMK CONVENT, TAIPING', 'SMK Convent, 34000 Taiping, Perak'), 'match')

    def test_the_name_alone_decides(self):
        # The owner's rule: the town we added is not compared, so another Convent is still the name.
        self.assertEqual(_field_status('SMK CONVENT, TAIPING', 'SMK CONVENT KLANG'), 'match')

    def test_a_different_school_still_clashes(self):
        self.assertEqual(_field_status('SMK CONVENT, TAIPING', 'SMK ST GEORGE'), 'clash')
        self.assertEqual(offer_pathway_match('', 'SMK CONVENT, TAIPING', 'Tingkatan Enam', 'SMK ST GEORGE'),
                         'mismatch')

    def test_the_whole_match_reads_the_core(self):
        self.assertEqual(offer_pathway_match('', 'SMK CONVENT, TAIPING', 'Tingkatan Enam', 'SMK CONVENT'),
                         'match')


class TestCatalogueHint(SimpleTestCase):
    """`offer_pathway._refers_to_campus` — a stored pre-U school used as a hint against the catalogue."""

    def test_our_town_never_aligns_the_hint_with_another_school(self):
        from apps.scholarship.offer_pathway import _refers_to_campus
        self.assertIn('SMK TUN PERAK, MUAR', SAME_NAME_SCHOOLS)
        # Without the core, {tun, perak, muar} holds every token of "SMK MUAR" and aligned with it.
        self.assertFalse(_refers_to_campus('SMK MUAR', '', 'SMK TUN PERAK, MUAR'))
        self.assertTrue(_refers_to_campus('SMK TUN PERAK', '', 'SMK TUN PERAK, MUAR'))


class TestSchoolLeavingCertificate(SimpleTestCase):
    """`_school_match(cert school, profile school)` — the school chip."""

    def test_cert_without_the_town_matches(self):
        self.assertEqual(_school_match('SMK CONVENT', 'SMK CONVENT, TAIPING'), 'match')

    def test_cert_spelt_out_with_the_town_does_not_clash(self):
        self.assertEqual(_school_match('SEKOLAH MENENGAH KEBANGSAAN CONVENT TAIPING', 'SMK CONVENT, TAIPING'),
                         'match')

    def test_the_name_alone_decides(self):
        # The case the ruling decides: with our town compared, {CONVENT, TAIPING} vs {CONVENT, KLANG}
        # shares half its words and read 'mismatch'. The owner compares the name only.
        self.assertEqual(_school_match('SMK CONVENT KLANG', 'SMK CONVENT, TAIPING'), 'match')

    def test_a_different_school_still_clashes(self):
        self.assertEqual(_school_match('SEKOLAH MENENGAH KEBANGSAAN ST GEORGE', 'SMK CONVENT, TAIPING'),
                         'mismatch')


def _norm(name):
    """Case, punctuation and spacing ignored: "SMK ST. ANTHONY" is "SMK ST ANTHONY" (review 2)."""
    return ' '.join(re.sub(r'[^A-Z0-9]+', ' ', name.upper().replace("'", '')).split())


class TestGeneratedSetMatchesTheLists(SimpleTestCase):
    """The set is generated with the lists (`scripts/school_town_names.py`); they must agree."""

    def _names(self, file):
        return [r['name'] for r in json.loads((WEB_DATA / file).read_text(encoding='utf-8'))]

    def test_every_town_carrying_name_is_in_the_set_and_nothing_else(self):
        names = self._names('secondary-schools.json') + self._names('stpm-schools.json')
        ours = {n for n in names if n in SAME_NAME_SCHOOLS}
        self.assertEqual(ours, set(SAME_NAME_SCHOOLS))
        # Every member is "<NAME>, <TOWN>" and its NAME is used by another school in the national list.
        # A name another school shares once case and punctuation are ignored counts as shared.
        bare = Counter(_norm(n.rsplit(', ', 1)[0] if n in SAME_NAME_SCHOOLS else n)
                       for n in self._names('secondary-schools.json'))
        for n in SAME_NAME_SCHOOLS:
            self.assertRegex(n, r'^.+, [A-Z0-9 .\'()/-]+$')
            self.assertGreater(bare[_norm(n.rsplit(', ', 1)[0])], 1, n)
        self.assertEqual(set(SAME_NAME_SCHOOL_STATES), set(SAME_NAME_SCHOOLS))

    def test_no_name_is_shared_in_either_list_even_by_punctuation(self):
        for file in ('secondary-schools.json', 'stpm-schools.json'):
            dupes = [n for n, c in Counter(map(_norm, self._names(file))).items() if c > 1]
            self.assertEqual(dupes, [], file)

    def test_names_that_differ_only_by_punctuation_carry_their_towns(self):
        names = set(self._names('secondary-schools.json'))
        self.assertIn('SMK ST. ANTHONY, TELUK INTAN', names)
        self.assertIn('SMK METHODIST ACS, SEREMBAN', names)

    def test_the_example_rows(self):
        self.assertIn('SMK CONVENT, TAIPING', SAME_NAME_SCHOOLS)
        self.assertIn('SMK CHUNG HUA, SIBU', SAME_NAME_SCHOOLS)
        self.assertTrue(all(not re.search(r',\s*$', n) for n in SAME_NAME_SCHOOLS))


class TestKeepOurTown(SimpleTestCase):
    """Review fix 6: a letter naming the SAME school never drops our ", TOWN"; another school replaces it."""

    def test_the_same_school_keeps_the_stored_name(self):
        for letter in ('Smk Convent', 'Sekolah Menengah Kebangsaan Convent Taiping', 'Smk Convent, 34000 Taiping'):
            self.assertEqual(keep_our_town('SMK CONVENT, TAIPING', letter), 'SMK CONVENT, TAIPING', letter)

    def test_a_different_school_replaces_it(self):
        self.assertEqual(keep_our_town('SMK CONVENT, TAIPING', 'Smk St George'), 'Smk St George')
        self.assertEqual(keep_our_town('SMK CONVENT, TAIPING', 'Smk Convent Klang'), 'Smk Convent Klang')

    def test_strict_a_numbered_school_replaces(self):
        # "SMK SULTAN ISMAIL 2" is another school; a dropped digit used to read it as ours.
        self.assertEqual(keep_our_town('SMK SULTAN ISMAIL, JOHOR BAHRU', 'Smk Sultan Ismail 2'),
                         'Smk Sultan Ismail 2')

    def test_strict_a_reordered_name_replaces(self):
        self.assertEqual(keep_our_town('SMK MUNSHI ABDULLAH, MELAKA', 'Smk Abdullah Munshi'),
                         'Smk Abdullah Munshi')

    def test_strict_a_school_named_after_its_own_town_replaces(self):
        self.assertEqual(keep_our_town('SMK KEPALA BATAS, ALOR SETAR', 'Smk Kepala Batas, Kepala Batas'),
                         'Smk Kepala Batas, Kepala Batas')

    def test_strict_the_plain_same_school_keeps(self):
        for letter in ('SMK Sultan Ismail', 'Smk Sultan Ismail, Johor Bahru',
                       'Smk Sultan Ismail, 80100 Johor Bahru, Johor', 'SMK Sultan Ismail Johor'):
            self.assertEqual(keep_our_town('SMK SULTAN ISMAIL, JOHOR BAHRU', letter),
                             'SMK SULTAN ISMAIL, JOHOR BAHRU', letter)
        self.assertEqual(keep_our_town('SMK ST. ANTHONY, TELUK INTAN', 'SMK St Anthony'),
                         'SMK ST. ANTHONY, TELUK INTAN')                       # "ST." is "ST"

    def test_only_our_names_and_never_a_blank_letter(self):
        self.assertEqual(keep_our_town('SMK PETAGAS, PENAMPANG', 'Smk Petagas'), 'Smk Petagas')
        self.assertEqual(keep_our_town('SMK CONVENT, TAIPING', ''), '')


class TestConfirmKeepsTheTown(TestCase):
    """Through `confirm_pathway`, the path that wrote the letter's cleaned name over ours."""

    @staticmethod
    def _stpm_app():
        return make_application('shortlisted', chosen_pathway='stpm', pre_u_track='sains',
                                pre_u_institution='SMK CONVENT, TAIPING')

    def _app_and_offer(self, institution):
        app = self._stpm_app()
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
            vision_fields={'fields': {'institution': institution, 'programme': 'Tingkatan Enam Semester 1',
                                      'stream': 'SAINS'}, 'student_verdict': 'ok',
                           'authenticity': {'status': 'genuine', 'reason': 'x'}},
            vision_run_at=timezone.now())
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        return app

    def test_same_school_keeps_name_and_town(self):
        app = self._app_and_offer('SEKOLAH MENENGAH KEBANGSAAN CONVENT TAIPING')
        self.assertEqual(app.pre_u_institution, 'SMK CONVENT, TAIPING')
        self.assertEqual(app.chosen_programme['institution'], 'SMK CONVENT, TAIPING')

    def test_a_different_school_still_replaces_it(self):
        app = self._app_and_offer('KOLEJ TINGKATAN ENAM GOMBAK')
        self.assertEqual(app.pre_u_institution, 'Kolej Tingkatan Enam Gombak')

    def test_the_silent_autofill_keeps_it_too(self):
        from apps.scholarship.services import autofill_pathway_from_offer
        app = self._stpm_app()
        profile = app.profile
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/y',
            vision_fields={'fields': {'institution': 'SMK CONVENT TAIPING', 'stream': 'SAINS',
                                      'programme': 'Tingkatan Enam Semester 1',
                                      'candidate_name': profile.name, 'candidate_nric': profile.nric},
                           'student_verdict': 'ok', 'authenticity': {'status': 'genuine', 'reason': 'x'}},
            vision_run_at=timezone.now())
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme.get('institution'), 'SMK CONVENT, TAIPING')


class TestAnonymityScanReadsTheName(SimpleTestCase):
    """Review fix 5: our town is not the school, so a blurb naming the town is not flagged as it."""

    def _profile(self, school):
        return SimpleNamespace(name='Zxqvbn', school=school, city='', nric='', contact_phone='',
                               contact_email='')

    def test_the_town_is_not_the_school(self):
        from apps.scholarship.pool import scan_anon_for_identifiers
        prof = self._profile('SMK (L) METHODIST, KUALA LUMPUR')
        self.assertIn('SMK (L) METHODIST, KUALA LUMPUR', SAME_NAME_SCHOOLS)
        self.assertEqual(scan_anon_for_identifiers('She grew up in Kuala Lumpur.', prof), [])
        self.assertEqual(scan_anon_for_identifiers('She studied at Methodist.', prof), ['school'])
