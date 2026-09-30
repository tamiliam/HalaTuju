"""TD-167 — the EXACT set of fields a sponsor can see, pinned against a literal list.

⚠ IF THIS TEST FAILED BECAUSE YOU ADDED OR REMOVED A FIELD, STOP AND RE-READ THE CONSENT FIRST.
The student (or their parent) agreed to share exactly what the consent wording describes —
`scholarship.consent.text` and `scholarship.consent.textMinor` in
`halatuju-web/src/messages/en.json` (and its ms/ta siblings): "an anonymised summary … Prior to
selection: state, school, course of study, plans, and financial need. During sponsorship: academic
progress, and how the bursary was spent." A new field must fit inside that sentence, or the
consent must change FIRST (an owner decision, with the ms/ta translations) — never the other way.

Why this exists: the consent and the sponsor payload drifted silently for months (it promised
"profile and documents"; no document was ever shared) and were reconciled only because the owner
read the form (2026-07-22). The existing sponsor tests assert the NEGATIVE (no name/NRIC/address/
phone/email). This asserts the POSITIVE: nothing reaches a sponsor that this list does not name.

Every serializer on the sponsor path is pinned: the pool CARD (`/sponsor/pool/`), the pool DETAIL,
and the two portfolio serializers a funding sponsor reads.
"""
from django.test import SimpleTestCase

from apps.scholarship.serializers import (
    SponsorMyStudentDetailSerializer, SponsorPoolCardSerializer, SponsorPoolDetailSerializer,
    SponsorSponsorshipSerializer,
)

#: The pool card. Re-read `scholarship.consent.text` before changing this list.
POOL_CARD = {
    'id', 'ref', 'state', 'school', 'field', 'course', 'academic', 'institution', 'blurb',
    'funding_categories', 'programme_months', 'award_amount', 'funded_amount', 'funded',
    'portfolio_status', 'supported_semesters', 'progress_state', 'support_status',
    'enrolment_verified', 'field_image_slug', 'reporting_date', 'course_href',
}
#: The pool detail = the card + the reviewed, anonymised profile markdown.
POOL_DETAIL = POOL_CARD | {'anon_profile'}
#: A sponsor's own allocation; `student` is the POOL_CARD above, nested.
SPONSORSHIP = {'id', 'status', 'amount', 'offered_at', 'accept_deadline', 'decided_at',
               'student', 'onboarded', 'semesters'}
#: A funded student's portfolio page: the allocation + the anon profile + spend by category.
MY_STUDENT_DETAIL = SPONSORSHIP | {'anon_profile', 'spending'}


class SponsorVisibleFieldsArePinnedTest(SimpleTestCase):
    def _fields(self, serializer_class):
        return set(serializer_class().fields.keys())

    def test_the_pool_card(self):
        self.assertEqual(self._fields(SponsorPoolCardSerializer), POOL_CARD,
                         'The sponsor pool card changed — re-read scholarship.consent.text.')

    def test_the_pool_detail(self):
        self.assertEqual(self._fields(SponsorPoolDetailSerializer), POOL_DETAIL,
                         'The sponsor pool detail changed — re-read scholarship.consent.text.')

    def test_a_sponsors_allocation(self):
        self.assertEqual(self._fields(SponsorSponsorshipSerializer), SPONSORSHIP,
                         'A sponsor allocation changed — re-read scholarship.consent.text.')

    def test_a_funded_students_portfolio_page(self):
        self.assertEqual(self._fields(SponsorMyStudentDetailSerializer), MY_STUDENT_DETAIL,
                         'The portfolio detail changed — re-read scholarship.consent.text.')

    def test_the_nested_student_is_the_pinned_card(self):
        # `student` is built by SponsorPoolCardSerializer, so POOL_CARD governs it too.
        import inspect
        src = inspect.getsource(SponsorSponsorshipSerializer.get_student)
        self.assertIn('SponsorPoolCardSerializer(sponsorship.application).data', src)
