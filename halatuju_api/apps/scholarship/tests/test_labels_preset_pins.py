"""Sprint LABELS: the role is only a label, so moving the Overview and the assignment target onto keys must
change NOTHING for any standard preset.

Written on the base commit (a5ae5ffed, branch `navkeys`) BEFORE the code moved, and green there; the code
then changed (TD-621: each Overview section opens on its keys; TD-622: who may hold a case is read from
the target's keys, not `R1_SUPER_TARGET_ROLES`) with these pins staying green. A hand-granted key set may
move; those moves are tested and declared in `test_labels_key_moves.py`, never here.

Per standard preset (a row exactly as the product makes it: `factories.make_admin`):
  (a) the Programme Overview over HTTP — the sections served, or the refusal;
  (b) whether a super may give them a case, whether they may HOLD one, whom each may give a case to, and
      who appears in the super's assignment picker.
"""
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions_v2 as v2
from apps.courses.models import PartnerAdmin
from apps.scholarship.services import assignment
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org, make_programme,
)

OVERVIEW = '/api/v1/admin/scholarship/programme-overview/'
ASSIGNABLE = '/api/v1/admin/scholarship/assignable-admins/'
FULL = ['funnel', 'money', 'attention', 'applications_series', 'money_series']

#: The ten standard presets, plus the organisation admin who joined Team -> Reviewers (a stored `review`,
#: the one lead shape a super may give a case to).
SHAPES = ('super', 'org_admin', 'org_admin in Reviewers', 'admin', 'finance', 'qc', 'reviewer', 'member',
          'mentor', 'partner', 'source_partner')

#: (a) The Overview, per preset: the `sections` served (200), or the status of the refusal.
OVERVIEW_PINS = {
    'super': FULL,
    'org_admin': FULL,
    'org_admin in Reviewers': FULL,
    'admin': FULL,
    'finance': ['money', 'money_series'],
    'qc': ['qc'],
    'reviewer': ['mine'],
    'member': 403,
    'mentor': 403,
    'partner': 403,
    'source_partner': 403,
}

#: (b) May they HOLD a case (`is_review_target`)?
HOLDS_PINS = {'super': True, 'org_admin': True, 'org_admin in Reviewers': True, 'admin': True,
              'finance': False, 'qc': True, 'reviewer': True, 'member': False, 'mentor': False,
              'partner': False, 'source_partner': False}

#: (b) May a super give them a case (`may_assign_to(super, them)`)? The Reviewers table only (T1).
SUPER_GIVES_PINS = {'super': False, 'org_admin': False, 'org_admin in Reviewers': True, 'admin': False,
                    'finance': False, 'qc': True, 'reviewer': True, 'member': False, 'mentor': False,
                    'partner': False, 'source_partner': False}

#: (b) May they give a case to a reviewer (`may_assign_to(them, a reviewer)`)?
GIVES_PINS = {'super': True, 'org_admin': True, 'org_admin in Reviewers': True, 'admin': False,
              'finance': False, 'qc': False, 'reviewer': False, 'member': False, 'mentor': False,
              'partner': False, 'source_partner': False}

#: (b) Who the super's assignment picker LISTS (the served `assignable` flag is `SUPER_GIVES_PINS`).
LISTED_PINS = {'super', 'org_admin', 'org_admin in Reviewers', 'admin', 'qc', 'reviewer'}


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class StandardPresetsDoNotMove(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.gift = make_programme(organisation=cls.org)
        org = cls.org
        cls.rows = {}
        for shape in SHAPES:
            if shape == 'super':
                cls.rows[shape] = make_admin('super', super_admin=True)
            elif shape == 'org_admin in Reviewers':
                lead = make_admin('org_admin', owning_org=org)
                PartnerAdmin.objects.filter(pk=lead.pk).update(
                    permissions=v2.org_admin_list(lead, review=True))
                cls.rows[shape] = lead
            else:
                cls.rows[shape] = make_admin(shape, owning_org=org)
        PartnerAdmin.objects.filter(pk__in=[a.pk for a in cls.rows.values()]).update(
            first_seen_at=timezone.now())
        cls.target = make_admin('reviewer', owning_org=org, first_seen_at=timezone.now())
        # A caller who does not see every gift opens a gift's Overview only where a case is theirs (T5c P5).
        make_application('profile_complete', cohort=make_cohort(programme=cls.gift),
                         reviewer=cls.rows['reviewer'])

    def load(self, shape):
        return PartnerAdmin.objects.get(pk=self.rows[shape].pk)

    def test_a_the_overview_each_preset_is_served(self):
        for shape, pin in OVERVIEW_PINS.items():
            with self.subTest(shape=shape):
                r = authed_client(self.rows[shape]).get(f'{OVERVIEW}?programme={self.gift.code}')
                got = r.json()['sections'] if r.status_code == 200 else r.status_code
                self.assertEqual(got, pin)

    def test_b_who_may_hold_a_case(self):
        for shape, pin in HOLDS_PINS.items():
            with self.subTest(shape=shape):
                self.assertEqual(assignment.is_review_target(self.load(shape)), pin)

    def test_b_whom_a_super_may_give_a_case(self):
        sup = self.load('super')
        for shape, pin in SUPER_GIVES_PINS.items():
            with self.subTest(shape=shape):
                self.assertEqual(assignment.may_assign_to(sup, self.load(shape)), pin)

    def test_b_whom_each_preset_may_give_a_case_to(self):
        target = PartnerAdmin.objects.get(pk=self.target.pk)
        for shape, pin in GIVES_PINS.items():
            with self.subTest(shape=shape):
                self.assertEqual(assignment.may_assign_to(self.load(shape), target), pin)

    def test_b_the_super_s_picker_lists_and_offers_the_same_people(self):
        rows = authed_client(self.rows['super']).get(ASSIGNABLE).json()['admins']
        by_pk = {r['id']: r for r in rows}
        listed = {s for s, a in self.rows.items() if a.pk in by_pk}
        self.assertEqual(listed, LISTED_PINS)
        for shape in listed:
            with self.subTest(shape=shape):
                self.assertEqual(by_pk[self.rows[shape].pk]['assignable'], SUPER_GIVES_PINS[shape])
