"""Tests for the deterministic anomaly engine (S16 Phase A).

One positive + one negative case per rule. Plus an integration sanity check
that ordering matches the registered detector list (so the admin sees a
predictable surface for the same data).
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.anomaly_engine import detect_anomalies
from apps.scholarship.models import (
    ApplicantDocument, FundingNeed, ScholarshipApplication, ScholarshipCohort,
)


class _Base(TestCase):
    """Shared fixture: a clean profile + a shortlisted application with
    fields zeroed out, so each test toggles only what it cares about."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        # Fresh profile + app per test to keep rule states isolated.
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'anom-{self.id()}',
            name='Priya Devi',
            nric='030101-14-1234',
            preferred_state='Selangor',
            household_income=2000,
            household_size=4,
            receives_str=False,
            receives_jkm=False,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
        )


def _add_ic(app, *, vision_nric='', vision_name='', vision_address=''):
    """Convenience: attach an IC document with S13 Vision fields populated."""
    return ApplicantDocument.objects.create(
        application=app, doc_type='ic', storage_path=f'{app.id}/ic/x',
        vision_nric=vision_nric, vision_name=vision_name, vision_address=vision_address,
        vision_run_at=timezone.now(), vision_error='',
    )


# ─── Per-rule tests ─────────────────────────────────────────────────────────

class TestVisionNricMismatch(_Base):
    def test_flag_when_ocr_nric_differs(self):
        _add_ic(self.app, vision_nric='710829-02-5709', vision_name=self.profile.name)
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('vision_nric_mismatch', codes)

    def test_no_flag_when_ocr_nric_matches(self):
        _add_ic(self.app, vision_nric=self.profile.nric, vision_name=self.profile.name)
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('vision_nric_mismatch', codes)


class TestVisionNameMismatch(_Base):
    def test_flag_on_partial_name(self):
        # OCR omits the middle name → partial → flag.
        _add_ic(self.app, vision_nric=self.profile.nric, vision_name='PRIYA KRISHNAN')
        # First override profile name so partial logic triggers.
        self.profile.name = 'PRIYA DEVI KRISHNAN'
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('vision_name_mismatch', codes)

    def test_no_flag_on_exact_match(self):
        _add_ic(self.app, vision_nric=self.profile.nric, vision_name=self.profile.name)
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('vision_name_mismatch', codes)


class TestAddressStateMismatch(_Base):
    def test_flag_when_ic_state_differs_from_profile_state(self):
        # Profile says Selangor; IC address says Kedah.
        _add_ic(
            self.app, vision_nric=self.profile.nric, vision_name=self.profile.name,
            vision_address='NO 12 JALAN ABC, TAMAN BAHAGIA, 08000 SUNGAI PETANI, KEDAH',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('address_state_mismatch', codes)

    def test_no_flag_when_states_align_after_wp_normalisation(self):
        self.profile.preferred_state = 'W.P. Putrajaya'
        self.profile.save()
        _add_ic(
            self.app, vision_nric=self.profile.nric, vision_name=self.profile.name,
            vision_address='BLOK A, PERSIARAN PERDANA, 62100 PUTRAJAYA',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        # "Putrajaya" / "W.P. Putrajaya" normalise equal — no flag.
        self.assertNotIn('address_state_mismatch', codes)


class TestJkmHighIncome(_Base):
    def test_flag_when_jkm_with_income_over_3000(self):
        self.profile.receives_jkm = True
        self.profile.household_income = 5000
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('jkm_high_income', codes)

    def test_no_flag_when_jkm_with_low_income(self):
        self.profile.receives_jkm = True
        self.profile.household_income = 2500
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('jkm_high_income', codes)


class TestHouseholdSizeOne(_Base):
    def test_flag_when_household_size_is_one(self):
        self.profile.household_size = 1
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('household_size_one', codes)

    def test_no_flag_when_household_size_is_normal(self):
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('household_size_one', codes)


class TestFirstInFamilyWithSiblingsStudying(_Base):
    def test_flag_when_first_in_family_and_siblings_studying(self):
        self.app.first_in_family = True
        self.app.siblings_studying_count = 2
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('first_in_family_with_siblings_studying', codes)

    def test_no_flag_when_count_is_zero(self):
        self.app.first_in_family = True
        self.app.siblings_studying_count = 0
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('first_in_family_with_siblings_studying', codes)


class TestFundingOtherWithoutNote(_Base):
    def test_flag_when_other_ticked_but_note_blank(self):
        FundingNeed.objects.create(
            application=self.app, categories=['living', 'other'], funding_note='',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('funding_other_without_note', codes)

    def test_no_flag_when_other_ticked_with_note(self):
        FundingNeed.objects.create(
            application=self.app, categories=['other'],
            funding_note='Bus pass for the daily commute.',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('funding_other_without_note', codes)


class TestDeclarationNameMismatch(_Base):
    def test_flag_when_declaration_differs_from_profile(self):
        # Profile name has a middle name absent from the declaration — partial.
        self.profile.name = 'NUR AISYAH BINTI ABDULLAH'
        self.profile.save()
        self.app.declaration_name = 'NUR AISYAH ABDULLA'  # missing H — true diff
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('declaration_name_mismatch', codes)

    def test_no_flag_when_declaration_matches_profile(self):
        self.app.declaration_name = self.profile.name
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('declaration_name_mismatch', codes)


class TestStrClaimedNoDoc(_Base):
    def test_flag_when_str_claimed_without_doc(self):
        self.profile.receives_str = True
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('str_claimed_no_doc', codes)

    def test_no_flag_when_str_claimed_with_doc(self):
        self.profile.receives_str = True
        self.profile.save()
        ApplicantDocument.objects.create(
            application=self.app, doc_type='str',
            storage_path=f'{self.app.id}/str/proof',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('str_claimed_no_doc', codes)


class TestDeviceInFunding(_Base):
    def test_flag_when_device_ticked(self):
        FundingNeed.objects.create(
            application=self.app, categories=['living', 'device'],
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('device_in_funding', codes)

    def test_no_flag_when_device_not_ticked(self):
        FundingNeed.objects.create(
            application=self.app, categories=['living', 'transport'],
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('device_in_funding', codes)


# ─── Integration / shape tests ──────────────────────────────────────────────

class TestAnomalyShape(_Base):
    def test_empty_application_returns_empty_list(self):
        """A bare application with default values produces no flags."""
        self.assertEqual(detect_anomalies(self.app), [])

    def test_anomaly_dict_shape(self):
        """Each flag is a JSON-serialisable dict with code + params."""
        self.profile.household_size = 1
        self.profile.save()
        anomalies = detect_anomalies(self.app)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(set(anomalies[0].keys()), {'code', 'params'})
        self.assertIsInstance(anomalies[0]['code'], str)
        self.assertIsInstance(anomalies[0]['params'], dict)

    def test_multiple_flags_in_registration_order(self):
        """Order is stable + matches the _DETECTORS tuple — so the admin
        always sees the same flags in the same order for the same data."""
        # Trigger flags from the 4th + 7th + 9th detectors (jkm_high_income,
        # funding_other_without_note, str_claimed_no_doc) and confirm order.
        self.profile.receives_jkm = True
        self.profile.receives_str = True
        self.profile.household_income = 5000
        self.profile.save()
        FundingNeed.objects.create(
            application=self.app, categories=['other'], funding_note='',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        # jkm comes before funding_other comes before str_claimed in _DETECTORS.
        self.assertEqual(codes, [
            'jkm_high_income',
            'funding_other_without_note',
            'str_claimed_no_doc',
        ])
