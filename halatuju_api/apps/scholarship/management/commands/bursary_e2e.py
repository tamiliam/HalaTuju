"""Local end-to-end driver for the bursary signing chain — exercise the WHOLE flow
locally, with every external seam mocked (no Twilio, no PDF engine, no storage, no real
email), before anything goes to prod.

It seeds a throwaway awarded student and walks:
  comprehension pass -> parent PIN verified -> student+guarantor sign -> (partner witness)
  -> Foundation countersign -> executed (app 'active'), printing a readable trace of the
  status transitions and every email that would have been sent, and asserting each step.

By default it runs inside a transaction that is ROLLED BACK at the end, so it leaves no
data behind. Pass --keep to commit the seeded records instead.

    python manage.py bursary_e2e            # full chain, with a referring partner
    python manage.py bursary_e2e --no-org   # graceful path: no partner -> Foundation direct
    python manage.py bursary_e2e --keep      # keep the seeded data

SAFE TO RUN LOCALLY. It forces BURSARY_AGREEMENT_ENABLED on for the run only and uses the
in-memory email backend, so it never sends a real email or touches a real document bucket.
"""
from contextlib import ExitStack
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import override_settings
from django.utils import timezone


class _Done(Exception):
    """Sentinel to unwind the rollback transaction once the walk is complete."""


class Command(BaseCommand):
    help = 'Walk the bursary signing chain locally end-to-end with all external seams mocked.'

    def add_arguments(self, parser):
        parser.add_argument('--no-org', action='store_true',
                            help='No referring partner -> the chain skips witness to the Foundation.')
        parser.add_argument('--keep', action='store_true',
                            help='Commit the seeded records instead of rolling back.')

    def handle(self, *args, **options):
        keep = options['keep']
        with ExitStack() as stack:
            # Mock every external seam: PDF render, storage upload + signed URL, Twilio Verify,
            # and route email to the in-memory backend so we can read it back.
            stack.enter_context(override_settings(
                BURSARY_AGREEMENT_ENABLED=True,
                EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                FOUNDATION_NOTIFY_EMAIL='foundation.officer@example.test',
                TWILIO_ACCOUNT_SID='sid', TWILIO_AUTH_TOKEN='tok',
                TWILIO_VERIFY_SERVICE_SID='VA-local', PHONE_VERIFY_CHANNEL='sms',
            ))
            stack.enter_context(patch('apps.scholarship.bursary.generate_pdf',
                                      return_value=b'%PDF-1.4 local-e2e'))
            stack.enter_context(patch('apps.scholarship.storage.upload_object', return_value=True))
            stack.enter_context(patch('apps.scholarship.storage.create_signed_download_url',
                                      return_value='https://signed.local/agreement.pdf'))
            stack.enter_context(patch('apps.scholarship.whatsapp._post_to_verify',
                                      return_value={'status': 'approved'}))
            mail.outbox = []   # locmem backend appends here; init before the first send
            try:
                with transaction.atomic():
                    self._walk(no_org=options['no_org'])
                    if not keep:
                        raise _Done()
            except _Done:
                self._line('rolled back - no data kept (use --keep to commit)')
        self.stdout.write(self.style.SUCCESS('\nBursary E2E walk completed OK'))

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _ascii(s):
        # Console-safe: email subjects carry emoji that crash a cp1252 (Windows) terminal.
        return str(s).encode('ascii', 'replace').decode('ascii')

    def _line(self, msg):
        self.stdout.write(self._ascii(f'  - {msg}'))

    def _step(self, n, msg):
        self.stdout.write(self.style.MIGRATE_HEADING(self._ascii(f'\n[{n}] {msg}')))

    def _emails_since(self, mark):
        return [(m.to[0], m.subject) for m in mail.outbox[mark:]]

    def _check(self, cond, msg):
        if not cond:
            raise AssertionError(f'E2E assertion failed: {msg}')
        self._line(f'[ok] {msg}')

    # ── the walk ─────────────────────────────────────────────────────────────
    def _walk(self, *, no_org):
        from apps.courses.models import PartnerOrganisation, PartnerAdmin, StudentProfile
        from apps.scholarship import bursary
        from apps.scholarship import sponsorship as svc
        from apps.scholarship.models import (
            ApplicantDocument, ScholarshipApplication, ScholarshipCohort, Sponsor,
            SponsorProfile, Donation, Consent,
        )

        guar_name, guar_nric, guar_phone = 'Rahmah Binti Ahmad', '700101-10-5555', '013-1112222'
        cohort = ScholarshipCohort.objects.create(code='e2e', name='B40 E2E', year=2026)

        org = None
        if not no_org:
            org = PartnerOrganisation.objects.create(
                code='e2e-org', name='E2E Partner', contact_email='partner@example.test',
                contact_person='Cik Partner')
        # The Foundation officer who can countersign (super).
        PartnerAdmin.objects.create(
            supabase_user_id='e2e-super', name='Foundation Officer',
            email='foundation.officer@example.test', is_super_admin=True, role='super', is_active=True)

        profile = StudentProfile.objects.create(
            supabase_user_id='e2e-stu', name='E2E Student', nric='000101-10-1233',
            preferred_state='Kedah', exam_type='spm', grades={'bm': 'A'},
            contact_email='e2e.student@example.test', contact_phone='012-7776666',
            guardians=[{'name': guar_name, 'phone': guar_phone}], referred_by_org=org)
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='recommended', award_amount=Decimal('3000'),
            notify_email='e2e.student@example.test',
            chosen_programme={'course_name': 'Diploma in Nursing', 'institution': 'Politeknik KL'})
        SponsorProfile.objects.create(application=app, anon_markdown='Determined.', anon_published=True)
        Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
        ApplicantDocument.objects.create(
            application=app, doc_type='parent_ic', storage_path=f'{app.id}/parent_ic.jpg',
            vision_run_at=timezone.now(), vision_name=guar_name, vision_nric=guar_nric, vision_error='')

        self._step(1, f'Seed an awarded student ({"with" if org else "no"} referring partner)')
        sponsor = Sponsor.objects.create(
            supabase_user_id='e2e-spon', name='Anon Sponsor', email='spon@example.test',
            phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        Donation.objects.create(sponsor=sponsor, amount=Decimal('3000'))
        svc.fund_student(sponsor, app)
        app.refresh_from_db()
        self._check(app.status == 'awarded', f"application funded -> status '{app.status}'")

        self._step(2, 'Student passes the comprehension quiz ("Understand")')
        app.comprehension_passed_at = timezone.now()
        app.save(update_fields=['comprehension_passed_at'])
        self._check(app.comprehension_passed_at is not None, 'comprehension_passed_at stamped')

        self._step(3, "Parent PIN verified on the guardian's locked phone (Twilio mocked)")
        from apps.scholarship import whatsapp
        approved, _ = whatsapp.check_phone_verification(guar_phone, '123456')
        self._check(approved, 'mocked Twilio Verify returned approved')
        app.guarantor_phone = guar_phone
        app.guarantor_phone_verified_at = timezone.now()
        app.save(update_fields=['guarantor_phone', 'guarantor_phone_verified_at'])
        self._check(bursary.guarantor_phone_verification_fresh(app), 'phone verification is fresh')

        self._step(4, 'Student + guarantor sign in-session -> next party notified')
        mark = len(mail.outbox)
        svc.respond_to_award(
            app, action='accept', student_signed_name='E2E Student',
            guarantor_name=guar_name, guarantor_nric=guar_nric, guarantor_relationship='mother')
        app.refresh_from_db()
        ag = app.bursary_agreement
        self._check(ag.binds, 'agreement binds (student + guarantor signed)')
        self._check(app.status == 'awarded', "app stays 'awarded' until the Foundation countersigns")
        for to, subj in self._emails_since(mark):
            self._line(f'EMAIL -> {to}: "{subj}"')
        if org:
            self._check(any('partner@example.test' == to for to, _ in self._emails_since(mark)),
                        'partner emailed to witness (sequenced first)')
        else:
            self._check(any('foundation.officer@example.test' == to for to, _ in self._emails_since(mark)),
                        'Foundation emailed directly (no partner — graceful)')

        if org:
            self._step(5, 'Partner records the witness attestation -> Foundation notified')
            mark = len(mail.outbox)
            bursary.record_witness(ag, org=org, by_name='Partner Admin', witness_name=org.name)
            ag.refresh_from_db()
            self._check(ag.witness_signed_at is not None, 'witness signed')
            for to, subj in self._emails_since(mark):
                self._line(f'EMAIL -> {to}: "{subj}"')
            self._check(any('foundation.officer@example.test' == to for to, _ in self._emails_since(mark)),
                        'Foundation emailed to countersign')

        self._step(6 if org else 5, 'Foundation countersigns -> agreement executed -> student notified')
        mark = len(mail.outbox)
        bursary.countersign_foundation(ag, by_name='Foundation Officer')
        app.refresh_from_db()
        ag.refresh_from_db()
        self._check(app.status == 'active', f"app flips 'awarded' -> '{app.status}' (executed)")
        self._check(ag.foundation_signed_at is not None, 'Foundation signature stamped')
        for to, subj in self._emails_since(mark):
            self._line(f'EMAIL -> {to}: "{subj}"')
        self._check(any('e2e.student@example.test' == to for to, _ in self._emails_since(mark)),
                    'student emailed that the agreement is in effect')

        self._step('done', 'Final state')
        self._line(f"application status   = {app.status}")
        self._line(f"agreement status     = {ag.status}")
        self._line(f"signed PDF path      = {ag.pdf_storage_path}")
        self._line(f"total emails sent    = {len(mail.outbox)}")
