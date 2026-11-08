"""T2 review B1: the staff footprint cannot quietly fall behind the models.

A person with no footprint may be DELETED (D6: reviewers, QC and mentors too). The first T2 pass
missed `StudentActivity.actor_email`, so a QC user who had written a student note read as `{}` and
deletable. This walks EVERY model and every field that can name a staff member's act:

  * a foreign key or one-to-one to `PartnerAdmin` or `Mentor`;
  * any field named `*_by`, `*_by_email` or `actor_email`.

Each must be COUNTED by `staff_footprint` or sit in `NOT_WORK` below with a one-line reason. A new
field fails here until somebody decides which it is.
"""
from django.apps import apps
from django.test import SimpleTestCase

from apps.courses.models import PartnerAdmin
from apps.scholarship import staff_footprint
from apps.scholarship.models import Mentor

#: Fields that match the walk but are NOT a staff member's work, each with its reason.
NOT_WORK = {
    'courses.PartnerAdmin.mentor': "the login's own link to its mentor record (MENTOR_TRACES read it)",
    'courses.ReviewerGift.partner_admin': 'a programme seat the person holds: configuration, not an act',
    'scholarship.ReviewerProfile.partner_admin': "the person's own profile",
    'scholarship.Invitation.partner_admin': "the person's own invitation (invited_by counts the sender)",
    'scholarship.Invitation.mentor': "the mentor's own invitations, deleted first by delete_mentor",
    'scholarship.Invitation.superseded_by': 'a link to the newer invitation, not to a person',
    'scholarship.ApplicantDocument.superseded_by': 'a link to the newer document, not to a person',
    'scholarship.ResultsExpectation.satisfied_by': 'a link to the SemesterResult that met it',
    'scholarship.Consent.granted_by': 'a choice (self / guardian), never staff',
    'scholarship.BursarySpendTxn.decided_by': 'a choice (duitnow / rule / inferred), never staff',
    'scholarship.MerchantCategory.decided_by': 'a choice (duitnow / rule / inferred); decided_by_email counts',
    'scholarship.Donation.recorded_by': 'a display name; recorded_by_email counts the person',
    'scholarship.Donation.finance_checked_by': 'a display name; finance_checked_by_email counts the person',
    'scholarship.Donation.confirmed_by': 'a display name; confirmed_by_email counts the person',
    'scholarship.OrgRequestAnalysis.authored_by': 'the author label (a model name such as claude-opus)',
    'scholarship.BursaryAgreement.foundation_signed_by': 'a typed name; the act is a counted '
                                                         'StaffActivity (contract_countersigned)',
    'scholarship.BursaryAgreement.witness_signed_by': 'a typed name; witness_admin counts the person',
    'scholarship.StaffPermissionChange.target': 'about them, not by them; changed_by_email counts the doer',
    'scholarship.ReviewerNote.author': 'the twin of author_email, which counts',
    'scholarship.AwardWithdrawalRequest.requested_by': 'the twin of requested_by_email, which counts',
    'scholarship.AwardWithdrawalRequest.decided_by': 'the twin of decided_by_email, which counts',
}


def _counted():
    """Every `app.Model.field` the footprint reads, from its own tables."""
    out = set()
    for _key, label, model, fields, _extra in staff_footprint.FK_TRACES:
        out |= {f'{label}.{model}.{f}' for f in fields}
    for _key, label, model, _extra in staff_footprint.MENTOR_TRACES:
        out.add(f'{label}.{model}.mentor')
    for _key, label, model, fields in staff_footprint.CORE_EMAIL_STAMPS + staff_footprint.EMAIL_STAMPS:
        out |= {f'{label}.{model}.{f}' for f in fields}
    return out


def _walked():
    """Every field that could name a staff member's act, across every installed model."""
    found = set()
    for model in apps.get_models():
        for f in model._meta.get_fields():
            if not getattr(f, 'concrete', False):
                continue
            to_staff = (f.is_relation and (f.many_to_one or f.one_to_one)
                        and f.related_model in (PartnerAdmin, Mentor))
            named = f.name.endswith(('_by', '_by_email')) or f.name == 'actor_email'
            if to_staff or named:
                found.add(f'{model._meta.app_label}.{model.__name__}.{f.name}')
    return found


class TestTheFootprintCoversEveryField(SimpleTestCase):

    def test_every_field_is_counted_or_excused(self):
        missing = sorted(_walked() - _counted() - set(NOT_WORK))
        self.assertEqual(missing, [], 'A field can name a staff member\'s act and the footprint does '
                         'not count it. Add it to staff_footprint (a delete would lose or orphan the '
                         'record), or to NOT_WORK here with the reason it is not work.')

    def test_every_excuse_still_names_a_real_uncounted_field(self):
        stale = sorted(set(NOT_WORK) - (_walked() - _counted()))
        self.assertEqual(stale, [], 'NOT_WORK names a field that is gone, renamed or now counted.')

    def test_every_excuse_gives_a_reason(self):
        self.assertEqual([k for k, why in NOT_WORK.items() if len(why.strip()) < 10], [])

    def test_every_counted_field_exists(self):
        real = {f'{m._meta.app_label}.{m.__name__}.{f.name}'
                for m in apps.get_models() for f in m._meta.get_fields() if getattr(f, 'concrete', False)}
        self.assertEqual(sorted(_counted() - real), [])

    def test_the_walk_sees_the_field_that_was_missed(self):
        """The guard would have caught B1: the note's stamp is in the walk and is now counted."""
        self.assertIn('scholarship.StudentActivity.actor_email', _walked())
        self.assertIn('scholarship.StudentActivity.actor_email', _counted())
