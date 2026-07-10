"""Private / continuing-education (IPTS) ARM veto + the course-switch note (owner 2026-07-10).

Two owner decisions off applicant #13 (a UTM SPACE offer that read a silent Certain green):
  1. A public university's fee-paying continuing-education ARM (UTM SPACE, UM CCE, …) is an IPTS
     option — disqualifying, like AIMST / UTAR. The genuineness scorer vetoes it to not_offer_letter
     (MODEL_VERSION 1.6.0) and the reporting-date bonus is blocked (gate 3b), so it can't sit at amber.
  2. A course SWITCH (the live offer replaced a genuinely different prior offer, any→any) is surfaced
     ALWAYS — even after the student confirms — so a swap never rides through as a silent green.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.genuineness.results_doc import signature_genuineness
from apps.scholarship.pathway_engine import (
    offer_reporting_bonus, offer_pathway_switch, offer_official_status,
)
from apps.scholarship.verdict_engine import build_verdict


# UTM SPACE — the parent UA name (UTM, one of the 20) makes the ua_offer anchor fire, so WITHOUT the
# veto this scores genuine. The arm names itself ("Pendidikan Berterusan (SPACE)") — the 'tell'.
UTM_SPACE_TEXT = """UNIVERSITI TEKNOLOGI MALAYSIA
SEKOLAH PENDIDIKAN PROFESIONAL DAN PENDIDIKAN BERTERUSAN (SPACE)
TAWARAN KEMASUKAN KE UNIVERSITI TEKNOLOGI MALAYSIA
Program : DSPD - DIPLOMA SAINS KOMPUTER
Pertukaran program adalah tidak dibenarkan.
Tarikh : 6 JULAI 2026
"""

# A genuine public UA offer with none of the arm markers — the control.
GENUINE_UA_TEXT = """UNIVERSITI MALAYA
PUSAT PENGURUSAN AKADEMIK
TAWARAN KEMASUKAN PROGRAM ASASI SAINS SOSIAL
Program Pengajian : Asasi Sains Sosial
Tarikh Pendaftaran : 5 Julai 2026
Pertukaran program adalah tidak dibenarkan.
"""


def _codes(items):
    return [i['code'] for i in items]


class TestPrivateArmVeto(TestCase):
    def test_space_offer_scores_not_offer_letter(self):
        g = signature_genuineness(UTM_SPACE_TEXT, doc_type='offer_letter')
        self.assertEqual(g['status'], 'not_offer_letter')
        self.assertIn('private', g['reason'].lower())

    def test_genuine_ua_offer_unaffected(self):
        g = signature_genuineness(GENUINE_UA_TEXT, doc_type='offer_letter')
        self.assertEqual(g['status'], 'genuine')

    def test_sdn_bhd_operator_offer_is_vetoed(self):
        g = signature_genuineness(GENUINE_UA_TEXT + '\nDikendalikan oleh UM SPACE Sdn. Bhd.',
                                  doc_type='offer_letter')
        self.assertEqual(g['status'], 'not_offer_letter')

    def test_veto_is_offer_scoped(self):
        # 'SPACE' in a NON-offer type must not be vetoed (a slip is scored on its own family).
        g = signature_genuineness('SPACE ' + GENUINE_UA_TEXT, doc_type='results_slip')
        self.assertNotEqual(g['status'], 'not_offer_letter')

    def test_aerospace_token_does_not_falsely_veto(self):
        # ' SPACE ' is matched as a standalone token — AEROSPACE must not trip it.
        g = signature_genuineness(GENUINE_UA_TEXT + '\nProgram : Asasi Kejuruteraan Aerospace',
                                  doc_type='offer_letter')
        self.assertEqual(g['status'], 'genuine')


class _OfferBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'arm-{self.id()}', name='HARINISHA A/P ANANDAN',
            nric='080219-10-1512', household_income=1800, household_size=4,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            chosen_pathway='poly',
        )

    def _offer(self, *, fields, authenticity=None, superseded=False):
        vf = {'fields': fields, 'warnings': [], 'student_verdict': 'ok', 'error': ''}
        if authenticity:
            vf['authenticity'] = authenticity
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter',
            storage_path=f'{self.app.id}/offer/{"old" if superseded else "live"}',
            vision_fields=vf, vision_run_at=timezone.now(),
            superseded_at=timezone.now() if superseded else None,
        )


class TestReportingBonusGate(_OfferBase):
    _AUTH = {'status': 'genuine', 'doc_seen': 'ua_offer',
             'present': ['public university (UA) name']}
    _RD = {'reporting_date': '6 Jul 2026', 'reporting_date_label': 'Tarikh',
           'institution': 'Universiti Teknologi Malaysia'}

    def test_bonus_blocked_for_space_arm(self):
        offer = self._offer(fields={**self._RD,
                                    'issuer': 'SEKOLAH PENDIDIKAN PROFESIONAL DAN '
                                              'PENDIDIKAN BERTERUSAN (SPACE)'},
                            authenticity=self._AUTH)
        self.assertFalse(offer_reporting_bonus(offer))       # gate 3b

    def test_bonus_allowed_for_ordinary_ua_offer(self):
        offer = self._offer(fields={**self._RD, 'issuer': 'Pejabat Pendaftar UTM'},
                            authenticity=self._AUTH)
        self.assertTrue(offer_reporting_bonus(offer))        # control — the tell absent


class TestPathwaySwitch(_OfferBase):
    def _switch_pair(self, *, live_auth=None):
        self._offer(fields={'programme': 'Asasi Teknologi Kejuruteraan',
                            'institution': 'Politeknik Nilai',
                            'candidate_name': 'HARINISHA A/P ANANDAN',
                            'candidate_nric': '080219101512'}, superseded=True)
        return self._offer(fields={'programme': 'DSPD - Diploma Sains Komputer',
                                   'institution': 'Universiti Teknologi Malaysia',
                                   'candidate_name': 'HARINISHA A/P ANANDAN',
                                   'candidate_nric': '080219101512'},
                           authenticity=live_auth)

    def test_switch_detected_any_to_any(self):
        self._switch_pair()
        sw = offer_pathway_switch(self.app)
        self.assertIsNotNone(sw)
        self.assertIn('Politeknik Nilai', sw['from_institution'])
        self.assertIn('Diploma Sains Komputer', sw['to_programme'])

    def test_no_switch_when_single_offer(self):
        self._offer(fields={'programme': 'Diploma Sains Komputer',
                            'institution': 'Politeknik Nilai'})
        self.assertIsNone(offer_pathway_switch(self.app))

    def test_public_switch_does_not_downgrade_verdict(self):
        # A PUBLIC switch is acceptable (owner): a confirmed genuine public offer stays Certain
        # (verified) — the switch must NOT downgrade the band. It is flashed via the cockpit banner +
        # the offer chip (data below), not by penalising the verdict.
        self._switch_pair(live_auth={'status': 'genuine', 'doc_seen': 'ua_offer'})
        self.app.pathway_confirmed_at = timezone.now()
        self.app.save(update_fields=['pathway_confirmed_at'])
        pathway = {f['fact']: f for f in build_verdict(self.app)}['pathway']
        self.assertEqual(pathway['status'], 'verified')      # NOT downgraded
        self.assertNotIn('pathway_switched', _codes(pathway['unresolved']))
        self.assertIsNotNone(offer_pathway_switch(self.app))  # the banner still has its data

    def test_private_arm_switch_is_fail(self):
        # The #13 shape: switched INTO a private continuing-education arm → the veto makes it
        # not_offer_letter (−2) + the pathway red chip (−1) → Fail. The RED comes from the
        # genuineness veto (not the switch); the switch is informational only.
        self._switch_pair(live_auth={'status': 'not_offer_letter', 'doc_seen': 'ua_offer'})
        self.app.pathway_confirmed_at = timezone.now()
        self.app.save(update_fields=['pathway_confirmed_at'])
        offer = ApplicantDocument.objects.filter(
            application=self.app, doc_type='offer_letter', superseded_at__isnull=True).first()
        self.assertEqual(offer_official_status(offer), 'not_genuine')
        pathway = {f['fact']: f for f in build_verdict(self.app)}['pathway']
        self.assertEqual(pathway['status'], 'gap')           # Fail — from the veto, not the switch
        self.assertIsNotNone(offer_pathway_switch(self.app))
