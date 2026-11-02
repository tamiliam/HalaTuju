"""The offer letter's IC guard (`offer_ic.guard_nric`, S4 review 2026-11-02: H2, M1, M4).

Invented numbers only (`test_no_gitignored_corpus.py`). The profile IC below is well formed: born
2008-01-02, place code 10."""
import datetime

from django.test import SimpleTestCase

from apps.scholarship.offer_ic import guard_nric, ic_runs, plausible_ic

TODAY = datetime.date(2026, 11, 2)
MINE = '080102-10-5678'
OTHER = '070315-14-1234'          # a different, well-formed IC
PAGE = 'SURAT TAWARAN ' * 20      # page text long enough to cross-check


def guard(nric, source='label', profile=MINE, text='', layer=False):
    f = {'candidate_nric': nric, 'candidate_nric_source': source}
    outcome = guard_nric(f, profile_nric=profile, page1_text=text, page1_is_text_layer=layer, today=TODAY)
    return f['candidate_nric'], f['candidate_nric_source'], outcome


class ShapeTest(SimpleTestCase):
    def test_a_well_formed_ic(self):
        self.assertTrue(plausible_ic(MINE, TODAY))
        self.assertTrue(plausible_ic('080102105678', TODAY))

    def test_what_is_not_an_ic(self):
        for bad in ('081302-10-5678',      # month 13
                    '080230-10-5678',      # 30 February
                    '080102-17-5678',      # no place code 17
                    '080102-10-567',       # 11 digits
                    '200102-10-5678',      # born 2020: six years old
                    '400102-10-5678',      # born 1940: 86
                    'UPM/BPA/S/3-1'):
            self.assertFalse(plausible_ic(bad, TODAY), bad)

    def test_ic_runs_on_a_page(self):
        self.assertEqual(ic_runs(f'No. K/P: {MINE} Rujukan 123456789012345'), ['080102105678'])


class LabelledIcTest(SimpleTestCase):
    def test_the_students_own_ic_is_kept(self):
        self.assertEqual(guard(MINE), (MINE, 'label', 'kept_profile'))

    def test_one_digit_off_the_profile_is_kept_like_the_name_ic_check(self):   # reconciles _nric_close
        self.assertEqual(guard('080102-10-5679')[2], 'kept_profile')
        self.assertEqual(guard('080192-10-5678')[2], 'kept_profile')            # day 92: malformed, one digit off

    def test_another_well_formed_ic_is_kept_because_it_is_a_wrong_person_letter(self):
        self.assertEqual(guard(OTHER), (OTHER, 'label', 'kept_well_formed'))

    def test_a_malformed_number_is_blanked(self):
        self.assertEqual(guard('UPM/BPA/S/3-1'), ('', 'none', 'blanked_malformed'))
        self.assertEqual(guard('991302-10-5678', profile=''), ('', 'none', 'blanked_malformed'))   # month 13

    def test_no_profile_keeps_a_well_formed_ic(self):
        self.assertEqual(guard(OTHER, profile='')[2], 'kept_well_formed')


class CorroborateOnlyTest(SimpleTestCase):
    def test_a_reference_line_ic_is_kept_only_when_it_is_the_students(self):
        self.assertEqual(guard(MINE, source='reference_line'), (MINE, 'reference_line', 'kept_corroborated'))
        self.assertEqual(guard(OTHER, source='reference_line'), ('', 'none', 'blanked_uncorroborated'))
        self.assertEqual(guard(MINE, source='reference_line', profile='')[2], 'blanked_uncorroborated')

    def test_any_other_source_is_corroborate_only_too(self):
        self.assertEqual(guard(OTHER, source='other')[2], 'blanked_uncorroborated')
        self.assertEqual(guard(OTHER, source='made-up')[2], 'blanked_uncorroborated')


class CrossCheckAndBackstopTest(SimpleTestCase):
    def test_a_number_the_page_does_not_print_is_blanked(self):
        self.assertEqual(guard(OTHER, text=PAGE + f' No. K/P {MINE}')[2], 'blanked_not_on_page')
        self.assertEqual(guard(OTHER, text=PAGE + f' No. K/P {OTHER}')[2], 'kept_well_formed')

    def test_a_short_text_is_not_cross_checked(self):
        self.assertEqual(guard(OTHER, text=f'K/P {MINE}')[2], 'kept_well_formed')

    def test_a_blank_is_filled_only_from_page_ones_text_layer_printing_the_profile_ic(self):
        self.assertEqual(guard('', text=PAGE + f' {MINE}', layer=True),
                         ('080102105678', 'text_layer', 'blank+backstop'))
        self.assertEqual(guard('', text=PAGE + f' {MINE}', layer=False)[0], '')     # a photo's OCR: never
        self.assertEqual(guard('', text=PAGE + f' {OTHER}', layer=True)[0], '')     # not the profile's
        self.assertEqual(guard('', text=PAGE, layer=True, profile='')[0], '')

    def test_a_blank_stays_blank(self):
        self.assertEqual(guard('', source='none'), ('', 'none', 'blank'))


class ReReviewTest(SimpleTestCase):
    """The S4 adversarial re-review (2026-11-02): M1, M2, L2."""

    def test_m1_a_missing_or_unknown_source_is_corroborate_only_never_label(self):
        for source in ('', 'none', 'made-up'):
            self.assertEqual(guard(OTHER, source=source), ('', 'none', 'blanked_uncorroborated'), source)
        f = {'candidate_nric': OTHER}                       # no source key at all
        self.assertEqual(guard_nric(f, profile_nric=MINE, today=TODAY), 'blanked_uncorroborated')
        self.assertEqual(guard(MINE, source=''), (MINE, 'other', 'kept_corroborated'))

    def test_m2_a_refused_read_is_never_refilled_from_the_text_layer(self):
        page = PAGE + f' No. K/P {MINE}'
        self.assertEqual(guard(OTHER, text=page, layer=True), ('', 'none', 'blanked_not_on_page'))
        self.assertEqual(guard(OTHER, source='reference_line', text=page, layer=True)[0], '')
        # …but a read that gave nothing usable still is (the backstop's own case).
        self.assertEqual(guard('', text=page, layer=True)[2], 'blank+backstop')
        self.assertEqual(guard('UPM/BPA/S/3-1', text=page, layer=True)[2], 'blanked_malformed+backstop')

    def test_l2_corroborate_only_is_exact_not_one_digit_off(self):
        self.assertEqual(guard('080102-10-5679', source='reference_line')[2], 'blanked_uncorroborated')
        self.assertEqual(guard('080102-10-5679', source='label')[2], 'kept_profile')     # a label keeps the tolerance
