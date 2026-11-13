"""The seeded world for the role-by-endpoint access matrix (`test_access_matrix.py`).

Not collected (no `test_` prefix). Two organisations, every caller the API knows, and one of each
object a URL can name, all on dummy data (`@example.test`, the factory's fake NRICs).

  ORGANISATION A  — the target. Student A holds an ACTIVE scholarship in it: an approved sponsor
                    funds it, a tranche is scheduled, a payment run and a credit name it, a bank
                    account, a document, a letter, a result, a referee and a resolution item are
                    hers. Every staff role of the organisation sits beside it.
  ORGANISATION B  — the neighbour. Its org admin (the strongest non-super tier) is the
                    cross-tenant caller: an org-A object must be refused to it.
  STUDENT B       — a second scholar in organisation A, with her own case, so a refusal of
                    student A's objects to her is a real cross-owner refusal, not "no account".
  SPONSOR B       — an approved sponsor who funds nobody: the cross-owner sponsor.

⚠ THE URL KWARGS ARE FILLED FROM `OBJECT_IDS`, MOST SPECIFIC ROUTE PREFIX FIRST. A route whose id
names an object that is not built here falls back to student A's application id, and the manifest
records it as `object: null` — the gate is still swept, but the cross-tenant claim is not made.
"""
import base64
import datetime
import hashlib
import hmac
import json
import re
from decimal import Decimal

from django.utils import timezone

from apps.scholarship.tests.factories import (
    authed_client, make_admin, make_application, make_cohort, make_org, make_programme,
    make_shortlistable_student, make_source,
)

#: Every caller that carries a Supabase JWT, plus the anonymous one. The order is the column order
#: of the manifest's role lists, so a reviewer reads them the same way every time.
JWT_ROLES = (
    'super',            # platform super: global, no organisation
    'org_admin_a',      # organisation A lead tier (see_all, scholars, qc, spending, manage_team, ...)
    'admin_a',          # organisation A `admin` preset (see_all, scholars, spending, payments_prepare)
    'qc_a',             # organisation A `qc` preset (see_all, qc)
    'reviewer_a',       # organisation A reviewer ASSIGNED to student A's case
    'reviewer_a2',      # organisation A reviewer with NO assignment (the assignment fence)
    'finance_a',        # organisation A `finance` preset (payments_approve)
    'partner_a',        # organisation A referral partner (legacy `partner` role)
    'member_a',         # organisation A `member` (no permissions; deny by default)
    'source_a',         # organisation A source user (deny by default; its own console)
    'mentor_a',         # organisation A mentor login, mentoring student A
    'org_admin_b',      # organisation B lead tier: the CROSS-TENANT caller
    'student_a',        # owns every student-side object below
    'student_b',        # a second scholar in organisation A: the CROSS-OWNER student
    'sponsor_a',        # approved sponsor funding student A
    'sponsor_b',        # approved sponsor funding nobody: the CROSS-OWNER sponsor
    'anon',             # no Authorization header at all
)

#: Callers that authenticate with a shared secret instead of a JWT. They carry no JWT, so on every
#: other route they ARE the anonymous caller (only the three internal views read these headers —
#: `cron.py` X-Cron-Secret, `cron.py` X-Vircle-Secret, `intake.py` X-Twilio-Signature).
SECRET_ROLES = ('cron_money', 'cron_email', 'vircle', 'twilio')
INTERNAL_ROUTES = ('api/v1/internal/cron/<str:job>/', 'api/v1/internal/vircle/airtable/',
                   'api/v1/scholarship/whatsapp/inbound/')

#: Test-only secrets (never real values). The family keys are distinct so a wrong-family key is
#: a real refusal; the shared legacy CRON_SECRET is unset, as the owner's end state has it.
TEST_SECRETS = dict(
    CRON_SECRET='',
    CRON_FAMILY_SECRETS={'money': 'test-cron-money', 'paid': 'test-cron-paid',
                         'email': 'test-cron-email', 'maintenance': 'test-cron-maintenance'},
    VIRCLE_AIRTABLE_SECRET='test-vircle-secret',
    TWILIO_AUTH_TOKEN='test-twilio-token',
)
#: The cron job the sweep names: a MONEY-family job, so the email-family key must be refused.
CRON_JOB = 'award-students-batch'


def roles_for(route):
    """The callers swept against ``route``."""
    return JWT_ROLES + (SECRET_ROLES if route in INTERNAL_ROUTES else ())


# ── Which object each URL id names ──────────────────────────────────────────────────────────
#: ``(route prefix, {kwarg: world attribute})``, most specific first. The first prefix that the
#: route starts with and that names the kwarg wins; then `DEFAULT_IDS` by kwarg name.
OBJECT_IDS = (
    ('api/v1/admin/scholarship/billing/corrections/', {'pk': 'correction_a'}),
    ('api/v1/admin/scholarship/billing/receipts/', {'pk': 'receipt_a'}),
    ('api/v1/admin/scholarship/billing/invoices/', {'pk': 'invoice_a'}),
    ('api/v1/admin/scholarship/billing/hours/', {'org_id': 'org_a'}),
    ('api/v1/admin/scholarship/payment-runs/', {'pk': 'run_a', 'item_id': 'run_item_a'}),
    ('api/v1/admin/scholarship/credits/', {'pk': 'credit_a'}),
    ('api/v1/admin/scholarship/disbursements/', {'pk': 'tranche_a'}),
    ('api/v1/admin/scholarship/withdrawal-requests/', {'pk': 'withdrawal_a'}),
    ('api/v1/admin/scholarship/resolution-items/', {'item_id': 'resolution_a'}),
    ('api/v1/admin/scholarship/requests/', {'pk': 'org_request_a'}),
    ('api/v1/admin/scholarship/programmes/', {'pk': 'gift_a'}),
    ('api/v1/admin/scholarship/intake-years/', {'pk': 'cohort_a'}),
    ('api/v1/admin/scholarship/sources/', {'pk': 'source_obj_a'}),
    ('api/v1/admin/scholarship/announcements/', {'pk': 'announcement_a'}),
    ('api/v1/admin/scholarship/surveys/', {'pk': 'survey_a'}),
    ('api/v1/admin/scholarship/development/', {'pk': 'module_a', 'app_id': 'app_a'}),
    ('api/v1/admin/scholarship/scholars/', {'pk': 'app_a', 'result_id': 'result_a',
                                           'lid': 'letter_a'}),
    ('api/v1/admin/scholarship/applications/', {'pk': 'app_a', 'ref_id': 'referee_a',
                                               'doc_id': 'document_a'}),
    ('api/v1/admin/graduation-messages/', {'pk': 'grad_message_a'}),
    ('api/v1/admin/source/', {'pk': 'app_a'}),
    ('api/v1/admin/mentor/students/', {'pk': 'app_a'}),
    ('api/v1/admin/mentors/', {'pk': 'mentor_obj_a'}),
    ('api/v1/admin/reviewers/', {'pk': 'reviewer_a'}),
    ('api/v1/admin/source-users/', {'pk': 'source_a'}),
    ('api/v1/admin/sponsors/', {'pk': 'sponsor_a'}),
    ('api/v1/admin/invitations/', {'pk': 'invitation_a'}),
    ('api/v1/admin/referral-partners/', {'org_id': 'org_a'}),
    ('api/v1/admin/students/', {'user_id': 'student_a'}),
    ('api/v1/admin/admins/', {'admin_id': 'reviewer_a2'}),
    ('api/v1/scholarship/applications/', {'pk': 'app_a'}),
    ('api/v1/scholarship/documents/', {'pk': 'document_a'}),
    ('api/v1/scholarship/resolution-items/', {'pk': 'resolution_a'}),
    ('api/v1/scholarship/bursary/letters/', {'lid': 'letter_a'}),
    ('api/v1/scholarship/bursary/surveys/', {'pk': 'survey_a'}),
    ('api/v1/scholarship/bursary/growth/', {'pk': 'module_a'}),
    ('api/v1/sponsor/sponsorships/', {'pk': 'sponsorship_a'}),
    ('api/v1/sponsor/pool/', {'ref': 'pool_ref_a'}),
    ('api/v1/sponsor/my-students/', {'ref': 'pool_ref_a'}),
    ('api/v1/reports/', {'report_id': 'report_a'}),
    ('api/v1/branding/', {'code': 'org_a_code'}),
    ('api/v1/internal/cron/', {'job': 'cron_job'}),
)
#: ``(route prefix, {kwarg: literal})`` for the verb-in-the-url routes, most specific first. Each is
#: a verb the view KNOWS: an unknown verb is refused (400 / 404) BEFORE the fence on several of
#: these views, and a sweep that only ever met that refusal would prove nothing about who may act.
ACTION_IDS = (
    ('api/v1/admin/scholarship/disbursements/', {'action': 'withhold'}),
    ('api/v1/admin/scholarship/resolution-items/', {'action': 'waive'}),
    ('api/v1/admin/scholarship/billing/invoices/<int:pk>/declaration/', {'action': 'declare'}),
    ('api/v1/admin/scholarship/billing/invoices/', {'action': 'send'}),
    ('api/v1/admin/scholarship/scholars/<int:pk>/letters/', {'action': 'resend'}),
    ('api/v1/admin/scholarship/scholars/<int:pk>/mentoring/', {'action': 'end'}),
    ('api/v1/admin/scholarship/surveys/', {'action': 'close'}),
    ('api/v1/admin/scholarship/development/<int:pk>/progress/', {'action': 'review'}),
    ('api/v1/admin/scholarship/development/', {'action': 'archive'}),
    ('api/v1/admin/mentors/', {'action': 'stop'}),
    ('api/v1/scholarship/bursary/letters/', {'action': 'read'}),
    ('api/v1/scholarship/bursary/growth/', {'action': 'read'}),
)
#: Literal fills by kwarg name (after `OBJECT_IDS` and `ACTION_IDS`).
DEFAULT_IDS = {'kind': 'weekly_summary', 'action': 'x', 'table': 'reviewers',
               'step': 'x', 'member': 'father', 'order': '1'}

#: The request body per route (else ``{}``). Where a view checks the body BEFORE the seat or the
#: fence, an empty body answers 400 to everybody and hides who could act; these bodies carry the
#: request past that check so the seat and the fence are what answer.
BODIES = {
    'api/v1/admin/sponsors/<int:pk>/review/': {'action': 'approve'},
    'api/v1/admin/scholarship/withdrawal-requests/<int:pk>/refuse/': {'reason': 'Access matrix'},
    'api/v1/admin/scholarship/applications/<int:pk>/withdrawal-request/':
        {'explanation': 'Access matrix'},
}


def object_for(route):
    """The world attribute the route's FIRST id names, or None when the route names no seeded
    object (no id at all, or an id `OBJECT_IDS` does not map)."""
    names = re.findall(r'<(?:\w+:)?(\w+)>', route)
    for prefix, ids in OBJECT_IDS:
        if route.startswith(prefix):
            for name in names:
                if name in ids:
                    return ids[name]
    return None


class World:
    """Holds the seeded rows and one client per caller."""

    def fill(self, route):
        def one(m):
            conv, name = m.group(1) or 'str', m.group(2)
            for prefix, ids in OBJECT_IDS:
                if route.startswith(prefix) and name in ids:
                    return str(self.ident(ids[name]))
            for prefix, ids in ACTION_IDS:
                if route.startswith(prefix) and name in ids:
                    return ids[name]
            if name in DEFAULT_IDS:
                return DEFAULT_IDS[name]
            return str(self.app_a.pk) if conv == 'int' else 'x'
        return '/' + re.sub(r'<(?:(\w+):)?(\w+)>', one, route)

    def ident(self, attr):
        value = getattr(self, attr)
        if attr == 'student_a':
            return value.supabase_user_id
        return getattr(value, 'pk', value)

    def call(self, role, route, method):
        url = self.fill(route)
        client = self.clients[role]
        headers = {}
        if role == 'cron_money':
            headers['HTTP_X_CRON_SECRET'] = TEST_SECRETS['CRON_FAMILY_SECRETS']['money']
        elif role == 'cron_email':
            headers['HTTP_X_CRON_SECRET'] = TEST_SECRETS['CRON_FAMILY_SECRETS']['email']
        elif role == 'vircle':
            headers['HTTP_X_VIRCLE_SECRET'] = TEST_SECRETS['VIRCLE_AIRTABLE_SECRET']
        if route == 'api/v1/scholarship/whatsapp/inbound/':
            if role == 'twilio':
                headers['HTTP_X_TWILIO_SIGNATURE'] = twilio_signature('http://testserver' + url)
            return client.generic(method.upper(), url, data='',
                                  content_type='application/x-www-form-urlencoded', **headers)
        return client.generic(method.upper(), url, data=json.dumps(BODIES.get(route, {})),
                              content_type='application/json', **headers)


def twilio_signature(url, params=None):
    """Twilio's own scheme (`whatsapp.verify_twilio_signature`), with the TEST token."""
    params = params or {}
    payload = url + ''.join(f'{k}{params[k]}' for k in sorted(params))
    digest = hmac.new(TEST_SECRETS['TWILIO_AUTH_TOKEN'].encode(), payload.encode(), hashlib.sha1)
    return base64.b64encode(digest.digest()).decode()


def build_world():
    """Seed both organisations and every caller. Runs once per module (inside an outer
    transaction the module fixture rolls back)."""
    from rest_framework.test import APIClient

    from apps.reports.models import GeneratedReport
    from apps.scholarship import pool
    from apps.scholarship.models import (
        AwardWithdrawalRequest, BankAccount, Consent, Disbursement, Donation, GraduationMessage,
        Invitation, Invoice, InvoiceReceipt, Letter, MentorAssignment, OrgBillingCorrection,
        OrgRequest, PaymentRun, PaymentRunItem, ProgrammeReferralSource, Referee, ResolutionItem,
        SemesterResult, Sponsor, SponsorProgrammeMembership, Sponsorship,
    )
    from apps.scholarship.models import ApplicantDocument, Announcement, DevelopmentModule, Survey

    w = World()
    now = timezone.now()
    today = datetime.date.today()

    # ── organisation A ──
    w.org_a = make_org()
    w.org_a_code = w.org_a.code
    w.gift_a = make_programme(organisation=w.org_a)
    w.cohort_a = make_cohort(programme=w.gift_a)
    w.source_obj_a = make_source(organisation=w.org_a)
    ProgrammeReferralSource.objects.create(programme=w.gift_a, source=w.source_obj_a)

    w.super = make_admin('reviewer', super_admin=True)
    w.org_admin_a = make_admin('org_admin', owning_org=w.org_a)
    w.admin_a = make_admin('admin', owning_org=w.org_a)
    w.qc_a = make_admin('qc', owning_org=w.org_a)
    w.reviewer_a = make_admin('reviewer', owning_org=w.org_a, gifts=[w.gift_a])
    w.reviewer_a2 = make_admin('reviewer', owning_org=w.org_a, gifts=[w.gift_a])
    w.finance_a = make_admin('finance', owning_org=w.org_a)
    w.partner_a = make_admin('partner', org=w.org_a, owning_org=w.org_a)
    w.member_a = make_admin('member', owning_org=w.org_a)
    w.source_a = make_admin('source_partner', owning_org=w.org_a, source=w.source_obj_a)
    w.mentor_a = make_admin('mentor', owning_org=w.org_a)
    w.mentor_obj_a = w.mentor_a.mentor

    w.student_a = make_shortlistable_student()
    w.student_b = make_shortlistable_student()
    w.app_a = make_application('active', cohort=w.cohort_a, student=w.student_a,
                               reviewer=w.reviewer_a, source=w.source_obj_a)
    w.app_b = make_application('active', cohort=w.cohort_a, student=w.student_b,
                               reviewer=w.reviewer_a2)
    MentorAssignment.objects.create(application=w.app_a, mentor=w.mentor_obj_a)

    # ── money around student A ──
    w.sponsor_a = Sponsor.objects.create(
        supabase_user_id='access-matrix-sponsor-a', name='Test Sponsor A',
        email='sponsor-a@example.test', phone='0100000000', source='friend', consent_at=now,
        status='approved')
    w.sponsor_b = Sponsor.objects.create(
        supabase_user_id='access-matrix-sponsor-b', name='Test Sponsor B',
        email='sponsor-b@example.test', phone='0100000001', source='friend', consent_at=now,
        status='approved')
    for sponsor in (w.sponsor_a, w.sponsor_b):
        SponsorProgrammeMembership.objects.create(sponsor=sponsor, programme=w.gift_a,
                                                  status='approved')
    w.credit_a = Donation.objects.create(sponsor=w.sponsor_a, amount=Decimal('2000'),
                                         programme=w.gift_a, status=Donation.STATUS_CONFIRMED)
    w.sponsorship_a = Sponsorship.objects.create(sponsor=w.sponsor_a, application=w.app_a,
                                                 amount=Decimal('2000'), status='active')
    w.tranche_a = Disbursement.objects.create(application=w.app_a, sponsorship=w.sponsorship_a,
                                              amount=Decimal('500'), status='scheduled',
                                              sequence=1)
    w.bank_a = BankAccount.objects.create(application=w.app_a, bank_name='Test Bank',
                                          account_number='0000000001',
                                          account_holder=w.student_a.name, confirmed_at=now)
    w.run_a = PaymentRun.objects.create(organisation=w.org_a, programme=w.gift_a,
                                        payment_date=today + datetime.timedelta(days=7),
                                        period_month=today.replace(day=1),
                                        reference=f'AM-{w.app_a.pk}')
    w.run_item_a = PaymentRunItem.objects.create(run=w.run_a, application=w.app_a,
                                                 included=True, amount=Decimal('500'))
    w.invoice_a = Invoice.objects.create(
        number=f'INV-AM-{w.org_a.pk:04d}', organisation=w.org_a, period_month='2026-08',
        issued_on=datetime.date(2026, 9, 15), due_on=datetime.date(2026, 9, 29),
        subtotal_myr=Decimal('100.00'), total_myr=Decimal('100.00'),
        sent_at=now)   # a tenant sees only SENT invoices (`_visible_invoices`)
    w.receipt_a = InvoiceReceipt.objects.create(
        number=f'RCP-AM-{w.org_a.pk:04d}', invoice=w.invoice_a,
        received_on=datetime.date(2026, 10, 1), amount_myr=Decimal('100.00'), reference='TEST-1')
    w.correction_a = OrgBillingCorrection.objects.create(
        organisation=w.org_a, period_month='2026-08', amount_myr=Decimal('-1.00'),
        reason='Access matrix fixture')
    # The withdrawal chain acts only on an AWARDED case (`award_withdrawal.WITHDRAWABLE`) and checks
    # that before the checker's seat, so the pending request sits on a third, awarded case of
    # organisation A. The `admin` made it, so the lead tier (which holds the checker's seat) is
    # not refused as the maker.
    w.app_w = make_application('awarded', cohort=w.cohort_a, student=make_shortlistable_student(),
                               reviewer=w.reviewer_a)
    w.withdrawal_a = AwardWithdrawalRequest.objects.create(
        application=w.app_w, organisation=w.org_a, explanation='Access matrix fixture',
        requested_by=w.admin_a, requested_by_email=w.admin_a.email)

    # ── student A's own papers ──
    w.document_a = ApplicantDocument.objects.create(application=w.app_a, doc_type='ic',
                                                    storage_path='test/access-matrix/ic')
    w.letter_a = Letter.objects.create(
        application=w.app_a, kind='general', language='en', subject='S', body='B',
        response_due_on=today + datetime.timedelta(days=14),
        pdf_path=f'{w.org_a.pk}/{w.app_a.pk}/letters/1.pdf')
    w.result_a = SemesterResult.objects.create(application=w.app_a, semester='Sem 1',
                                               cgpa=Decimal('3.25'), review_status='pending')
    w.referee_a = Referee.objects.create(application=w.app_a, name='Test Referee',
                                         role='counsellor')
    w.resolution_a = ResolutionItem.objects.create(application=w.app_a, code='x', prompt='x',
                                                   created_by=w.reviewer_a.email)
    w.grad_message_a = GraduationMessage.objects.create(application=w.app_a,
                                                        raw_text='thank you', status='pending')
    w.report_a = GeneratedReport.objects.create(
        student=w.student_a, title='T', content='C', student_profile_snapshot={},
        eligible_courses_snapshot=[], model_used='none')
    w.pool_ref_a = pool.pool_ref(w.app_a.pk)
    Consent.objects.get_or_create(application=w.app_a, consent_type='share_with_sponsors',
                                  defaults={'version': 't', 'is_active': True})

    # ── organisation-level content ──
    w.org_request_a = OrgRequest.objects.create(organisation=w.org_a, submitted_by=w.org_admin_a,
                                                kind='bug', title='A bug', description='x')
    w.announcement_a = Announcement.objects.create(organisation=w.org_a, title='Notice', body='B')
    w.survey_a = Survey.objects.create(organisation=w.org_a, title='Survey', status='published',
                                       opens_at=now - datetime.timedelta(hours=1),
                                       closes_at=now + datetime.timedelta(days=10))
    w.module_a = DevelopmentModule.objects.create(
        organisation=w.org_a, title='Module', status='published',
        publish_at=now - datetime.timedelta(hours=1), task_kind='reflection', task_prompt='P')
    w.invitation_a = Invitation.objects.create(
        audience='staff', email='invitee-a@example.test', name='Somebody',
        code=f'am-{w.org_a.pk}', expires_at=now + datetime.timedelta(days=7),
        partner_admin=w.reviewer_a2)
    w.cron_job = CRON_JOB

    # ── organisation B ──
    w.org_b = make_org()
    w.gift_b = make_programme(organisation=w.org_b)
    w.org_admin_b = make_admin('org_admin', owning_org=w.org_b)

    # Every staff caller has opened the console before (`first_seen_at`): the maker-checker seats
    # refuse a holder who never signed in, and each swept request is rolled back, so the stamp
    # `get_admin` writes on a first request would never stick.
    from apps.courses.models import PartnerAdmin
    PartnerAdmin.objects.update(first_seen_at=now)

    # ── one client per caller ──
    w.clients = {}
    for role in JWT_ROLES:
        if role == 'anon':
            w.clients[role] = APIClient(raise_request_exception=False)
            continue
        who = getattr(w, role)
        w.clients[role] = authed_client(who, APIClient(raise_request_exception=False))
    for role in SECRET_ROLES:
        w.clients[role] = APIClient(raise_request_exception=False)
    return w
