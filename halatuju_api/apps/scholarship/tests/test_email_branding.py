"""Golden snapshots of the trilingual email output — the BYTE-IDENTITY contract for the
per-org branding extraction (Sprint 5).

Each spec renders one email through ``django.core.mail.outbox`` and pins its full output:
subject + plain-text body + ``from_email`` + ``reply_to`` + the ``text/html`` alternative +
attachment filenames. The golden fixture (``fixtures/email_branding_golden.json``) is captured
against the NORMALISED copy (Sprint 5 Phase 0) and must stay green UNMODIFIED through the
Phase-2 branding extraction. If a snapshot changes, the refactor broke byte-identity — STOP.

Regenerate the golden ONLY when the copy legitimately changes (an owner-approved copy edit):
    UPDATE_EMAIL_GOLDEN=1 python -m pytest apps/scholarship/tests/test_email_branding.py

The ``.ics`` calendar attachment carries a non-deterministic DTSTAMP, so only the ``text/html``
alternative is pinned (never ``text/calendar``); attachment FILENAMES are pinned (they carry the
programme-name brand literal, e.g. the Vircle guide).
"""
import datetime
import json
import os
from pathlib import Path

import pytest
from django.core import mail

from apps.scholarship import emails

GOLDEN = Path(__file__).parent / 'fixtures' / 'email_branding_golden.json'

# A fixed, timezone-aware interview start (14:30 Asia/KL). Deterministic ICS UID + MYT format.
FIXED_START = datetime.datetime(2026, 8, 15, 6, 30, tzinfo=datetime.timezone.utc)

LANGS = ('en', 'ms', 'ta')
PROG = 'BrightPath Bursary'   # what every caller passes for programme_name (cohort.name)


def _card(ref, course, inst):
    return {
        'ref': ref, 'course': course, 'institution': inst,
        'academic': 'SPM · 9A', 'state': 'Selangor', 'award_amount': 3000,
        'blurb': 'A determined student who did well despite the odds.',
        'id': ref.lower(), 'field_image_slug': '',
    }


def _specs():
    """name -> (callable, kwargs). Every brand-bearing send_* rendered across languages."""
    s = {}

    def add(_spec_name, fn, **kw):
        s[_spec_name] = (fn, kw)

    for lang in LANGS:
        # {programme}-parameterised student mail (sign-off "The {programme} Team")
        add(f'ack.{lang}', emails.send_acknowledgement_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG, lang=lang)
        add(f'submission_received.{lang}', emails.send_submission_received_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG, lang=lang)
        add(f'pass.{lang}', emails.send_pass_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG, lang=lang)
        add(f'award_confirmed.{lang}', emails.send_award_confirmed_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG, lang=lang)
        add(f'application_closed.{lang}', emails.send_application_closed_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG, lang=lang)
        add(f'request_info.{lang}', emails.send_request_info_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG,
            note='Please upload your latest results slip.', lang=lang)
        add(f'query_raised.{lang}', emails.send_query_raised_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG,
            n_queries=2, lang=lang)
        add(f'query_reminder.{lang}', emails.send_query_reminder_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG,
            n_queries=2, days_left=3, lang=lang)
        # Completion reminders (persona in the help line) + sign-off
        for stage in (1, 2, 3, 4):
            add(f'reminder_s{stage}.{lang}', emails.send_reminder_email,
                to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG,
                stage=stage, lang=lang)
        # Declines (bucket-specific + generic; branded HTML sign-off)
        for cat in ('', 'merit', 'need', 'interview', 'contractual'):
            add(f'decline_{cat or "generic"}.{lang}', emails.send_decline_email,
                to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG,
                category=cat, lang=lang)
        # Hard-coded brand emails
        add(f'award_offer.{lang}', emails.send_award_offer_email,
            to_email='s@x.test', applicant_name='Aisyah', lang=lang)
        add(f'award_offer_guardian.{lang}', emails.send_award_offer_email,
            to_email='s@x.test', applicant_name='Aisyah', lang=lang, guardian_note=True)
        add(f'award_offer_sign.{lang}', emails.send_award_offer_sign_email,
            to_email='s@x.test', applicant_name='Aisyah', lang=lang)
        add(f'vircle_install.{lang}', emails.send_vircle_install_email,
            to_email='s@x.test', applicant_name='Aisyah', lang=lang)
        add(f'sign_invitation.{lang}', emails.send_sign_invitation_email,
            to_email='s@x.test', applicant_name='Aisyah', lang=lang)
        add(f'agreement_executed_plain.{lang}', emails.send_agreement_executed_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG, lang=lang)
        add(f'agreement_executed_pdf.{lang}', emails.send_agreement_executed_email,
            to_email='s@x.test', applicant_name='Aisyah', programme_name=PROG, lang=lang,
            link='http://localhost:3000/scholarship/application', pdf=b'%PDF-1.4 test')
        add(f'sponsor_new.{lang}', emails.send_sponsor_new_student_email,
            to_email='sp@x.test', name='Goban Arasu', lang=lang,
            cards=[_card('BP-001', 'Perubatan', 'Universiti Malaya'),
                   _card('BP-002', 'Kejuruteraan', 'UTM')])
        add(f'sponsor_digest.{lang}', emails.send_sponsor_digest_email,
            to_email='sp@x.test', name='Goban Arasu', lang=lang,
            cards=[_card('BP-003', 'Undang-undang', 'UKM')])
        add(f'sponsor_referral_invite.{lang}', emails.send_sponsor_referral_invite,
            to_email='p@x.test', inviter_name='Goban', note='Do join us.', code='ABC123', lang=lang)

    # English-only / bilingual student mail (english_only flag)
    for eo in (False, True):
        suf = 'eo' if eo else 'bi'
        add(f'student_assigned_reviewer.{suf}', emails.send_student_assigned_reviewer_email,
            to_email='s@x.test', student_name='Aisyah', english_only=eo,
            reviewer_name='Kalai', reviewer_email='k@x.test', reviewer_phone='012-3456789')
        add(f'profile_complete_student.{suf}', emails.send_profile_complete_student_email,
            to_email='s@x.test', student_name='Aisyah', english_only=eo)
        add(f'interview_booked.{suf}', emails.send_interview_booked_email,
            to_email='s@x.test', student_name='Aisyah', reviewer_name='Kalai',
            start=FIXED_START, meeting_url='https://meet.example/abc',
            english_only=eo, duration_min=45, reviewer_phone='012-3456789')
        add(f'interview_slots_proposed.{suf}', emails.send_interview_slots_proposed_email,
            to_email='s@x.test', student_name='Aisyah', english_only=eo, reviewer_name='Kalai')
        add(f'interview_reminder.{suf}', emails.send_interview_reminder_email,
            to_email='s@x.test', student_name='Aisyah', start=FIXED_START,
            meeting_url='https://meet.example/abc', when='1day', english_only=eo)
        add(f'interview_cancelled.{suf}', emails.send_interview_cancelled_email,
            to_email='s@x.test', student_name='Aisyah', english_only=eo)
        add(f'interview_released.{suf}', emails.send_interview_released_email,
            to_email='s@x.test', student_name='Aisyah', english_only=eo)
    add('interview_slots_proposed.reschedule', emails.send_interview_slots_proposed_email,
        to_email='s@x.test', student_name='Aisyah', reviewer_name='Kalai', rescheduled=True)
    add('interview_reminder.1hour', emails.send_interview_reminder_email,
        to_email='s@x.test', student_name='Aisyah', start=FIXED_START, when='1hour')

    # Internal (English) staff / partner mail
    add('executed_copy.link', emails.send_executed_copy_email,
        to_email='p@x.test', applicant_name='Aisyah', pdf=b'%PDF-1.4 test',
        link='http://localhost:3000/admin/scholarship/1')
    add('executed_copy.nolink', emails.send_executed_copy_email,
        to_email='p@x.test', applicant_name='Aisyah')
    add('witness_pending', emails.send_witness_pending_email,
        to_email='p@x.test', contact_person='Ravi', applicant_name='Aisyah',
        org_name='CUMIG', link='http://localhost:3000/admin')
    add('countersign_pending', emails.send_countersign_pending_email,
        to_email='p@x.test', applicant_name='Aisyah', link='http://localhost:3000/admin')
    add('reviewer_assigned', emails.send_reviewer_assigned_email,
        to_email='r@x.test', reviewer_name='Kalai', ref='BP-001',
        programme='BrightPath Bursary', review_by='2026-08-20')
    add('partner_welcome.pw', emails.send_partner_welcome_email,
        to_email='r@x.test', name='Kalai', role='reviewer', temp_password='Temp1234', google=False)
    add('partner_welcome.google', emails.send_partner_welcome_email,
        to_email='r@x.test', name='Kalai', role='reviewer', google=True)
    add('qc_returned', emails.send_qc_returned_email,
        to_email='r@x.test', reviewer_name='Kalai', ref='BP-001',
        applicant_name='Aisyah', qc_comments='Please recheck the income route.')
    add('qc_rejected', emails.send_qc_rejected_email,
        to_email='r@x.test', reviewer_name='Kalai', ref='BP-001',
        applicant_name='Aisyah', qc_comments='Declined on merit.')
    add('reviewer_interview_booked', emails.send_reviewer_interview_booked_email,
        to_email='r@x.test', reviewer_name='Kalai', applicant_name='Aisyah',
        start=FIXED_START, meeting_url='https://meet.example/abc', ref='BP-001', duration_min=45)
    add('reviewer_interview_reminder', emails.send_reviewer_interview_reminder_email,
        to_email='r@x.test', reviewer_name='Kalai', applicant_name='Aisyah',
        start=FIXED_START, meeting_url='https://meet.example/abc', when='1day',
        ref='BP-001', verdict_due='2026-08-25')
    add('reviewer_alternatives', emails.send_reviewer_alternatives_requested_email,
        to_email='r@x.test', reviewer_name='Kalai', applicant_name='Aisyah',
        note='None of these work for me.', ref='BP-001')
    add('reviewer_student_message', emails.send_reviewer_student_message_email,
        to_email='r@x.test', reviewer_name='Kalai', applicant_name='Aisyah',
        message='I may be a few minutes late.', ref='BP-001', interview_start=FIXED_START)
    add('reviewer_interview_cancelled', emails.send_reviewer_interview_cancelled_email,
        to_email='r@x.test', reviewer_name='Kalai', applicant_name='Aisyah',
        ref='BP-001', reason='Family emergency.')
    add('reviewer_verdict_due', emails.send_reviewer_verdict_due_email,
        to_email='r@x.test', reviewer_name='Kalai', applicant_name='Aisyah',
        ref='BP-001', due_by='2026-08-25', overdue=False)
    add('verdict_escalation', emails.send_verdict_escalation_email,
        to_email='a@x.test', applicant_name='Aisyah', ref='BP-001',
        reviewer_name='Kalai', due_by='2026-08-25')
    return s


def _capture(msg):
    html = ''
    for content, mime in getattr(msg, 'alternatives', None) or []:
        if mime == 'text/html':
            html = content
    return {
        'subject': msg.subject,
        'from_email': msg.from_email,
        'reply_to': list(msg.reply_to or []),
        'body': msg.body,
        'html': html,
        'attachments': [a[0] for a in (msg.attachments or [])],
    }


def _render_all():
    captured = {}
    for name, (fn, kw) in _specs().items():
        mail.outbox.clear()
        ok = fn(**kw)
        assert ok is not False, f'{name}: send returned False (no email produced)'
        assert mail.outbox, f'{name}: nothing landed in the outbox'
        captured[name] = _capture(mail.outbox[-1])
    return captured


@pytest.mark.django_db
def test_email_branding_golden():
    captured = _render_all()

    if os.environ.get('UPDATE_EMAIL_GOLDEN'):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(captured, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
        pytest.skip('regenerated the golden fixture')

    assert GOLDEN.exists(), 'golden fixture missing — run once with UPDATE_EMAIL_GOLDEN=1'
    golden = json.loads(GOLDEN.read_text())

    # Coverage stays complete: a new/removed spec must be a deliberate golden update.
    assert set(captured) == set(golden), (
        f'spec set drifted from the golden: '
        f'added={sorted(set(captured) - set(golden))} '
        f'removed={sorted(set(golden) - set(captured))}')
    mismatches = [name for name in captured if captured[name] != golden[name]]
    assert not mismatches, (
        'byte-identity broken for: ' + ', '.join(sorted(mismatches)) +
        ' — the branding extraction changed rendered output; STOP and reconcile.')


# ── Phase 4: the org-2 LEAK test ─────────────────────────────────────────────
# A second tenant ("inspire") with its OWN programme name, sign-off, persona, sender identity
# and frontend URL. Every branding-accepting send_* must render THAT tenant's brand and leak
# NONE of the platform's — the proof that the seam actually swaps per org.
from types import SimpleNamespace  # noqa: E402

from apps.scholarship import branding as _branding  # noqa: E402

_INSPIRE_ORG = SimpleNamespace(
    code='inspire',
    programme_name_en='Inspire Grant',
    programme_name_ms='Geran Inspire',
    programme_name_ta='இன்ஸ்பயர் மானியம்',
    team_signoff_en='The Inspire Grant Team',
    team_signoff_ms='Pasukan Geran Inspire',
    team_signoff_ta='இன்ஸ்பயர் மானியக் குழு',
    persona_name_en='Cikgu Aishah',
    persona_name_ms='Cikgu Aishah',
    persona_name_ta='சிக்கு ஐஷா',
    email_from='hello@inspire.example',
    email_reply_to='help@inspire.example',
    email_support='help@inspire.example',
    frontend_url='https://inspire.example',
)

# Byte-for-byte the platform brand tokens that must NEVER leak into a tenant's mail. 'BrightPath'
# subsumes every EN/MS form ("BrightPath Bursary", "Bursari BrightPath", "Pasukan Program Bursari
# BrightPath", "BrightPath Bursary குழு"); the two personas + the domain are named explicitly.
_PLATFORM_LEAK_TOKENS = ('BrightPath', 'halatuju.xyz', 'Cikgu Gopal', 'சிக்கு கோபால்')


def _inspire_specs(B):
    """name -> (callable, kwargs) for every send_* that accepts ``branding``, wired to the tenant."""
    s = {}
    for lang in LANGS:
        prog = B.programme_name(lang)
        s[f'award_offer.{lang}'] = (emails.send_award_offer_email, dict(
            to_email='s@x.test', applicant_name='Arefin', lang=lang, branding=B))
        s[f'award_offer_guardian.{lang}'] = (emails.send_award_offer_email, dict(
            to_email='s@x.test', applicant_name='Arefin', lang=lang, guardian_note=True, branding=B))
        s[f'award_offer_sign.{lang}'] = (emails.send_award_offer_sign_email, dict(
            to_email='s@x.test', applicant_name='Arefin', lang=lang, branding=B))
        s[f'vircle_install.{lang}'] = (emails.send_vircle_install_email, dict(
            to_email='s@x.test', applicant_name='Arefin', lang=lang, branding=B))
        s[f'sign_invitation.{lang}'] = (emails.send_sign_invitation_email, dict(
            to_email='s@x.test', applicant_name='Aefin', lang=lang, branding=B))
        s[f'agreement_executed.{lang}'] = (emails.send_agreement_executed_email, dict(
            to_email='s@x.test', applicant_name='Aefin', programme_name=prog, lang=lang, branding=B))
        s[f'agreement_executed_pdf.{lang}'] = (emails.send_agreement_executed_email, dict(
            to_email='s@x.test', applicant_name='Aefin', programme_name=prog, lang=lang,
            link='https://inspire.example/scholarship/application', pdf=b'%PDF-1.4 t', branding=B))
        for stage in (1, 2, 3, 4):
            s[f'reminder_s{stage}.{lang}'] = (emails.send_reminder_email, dict(
                to_email='s@x.test', applicant_name='Aefin', programme_name=prog,
                stage=stage, lang=lang, branding=B))
        s[f'application_closed.{lang}'] = (emails.send_application_closed_email, dict(
            to_email='s@x.test', applicant_name='Aefin', programme_name=prog, lang=lang, branding=B))
    return s


@pytest.mark.django_db
def test_org2_branding_appears_and_platform_never_leaks():
    B = _branding.for_organisation(_INSPIRE_ORG)
    assert B.email_from == 'hello@inspire.example'   # a real tenant sender, not the platform default

    specs = _inspire_specs(B)
    assert len(specs) >= 21, 'the leak test must exercise every branding-accepting send_*'

    for name, (fn, kw) in specs.items():
        lang = name.rsplit('.', 1)[-1]
        lang = lang if lang in LANGS else 'en'
        mail.outbox.clear()
        assert fn(**kw) is not False, f'{name}: send returned False'
        assert mail.outbox, f'{name}: nothing landed in the outbox'
        cap = _capture(mail.outbox[-1])
        # The rendered surfaces the brief names: subject, body, html, from, reply_to.
        blob = '\n'.join([cap['subject'], cap['body'], cap['html'], cap['from_email'],
                          ' '.join(cap['reply_to'])])

        # (1) the tenant's own brand is what actually renders.
        assert B.programme_name(lang) in blob, f'{name}: tenant programme name missing'
        assert cap['from_email'] == 'hello@inspire.example', f'{name}: sender not the tenant'
        # HTML sends set an explicit reply-to; the plain send_mail path (sign/agreement/reminder/
        # closed) sets none — either way it must never be a platform address.
        assert cap['reply_to'] in ([], ['help@inspire.example']), f'{name}: reply-to not the tenant'

        # (2) NOTHING of the platform's brand leaks through.
        for tok in _PLATFORM_LEAK_TOKENS:
            assert tok not in blob, f'{name}: platform token {tok!r} leaked into tenant mail'

    # The coach persona also swaps: the prompt names the tenant coach, never the platform one.
    from apps.scholarship import help_engine
    prompt = help_engine._build_help_prompt('ic', 'nric_mismatch', 'Aefin', 'English', branding=B)
    assert 'Cikgu Aishah' in prompt and 'Inspire Grant' in prompt
    for tok in ('Cikgu Gopal', 'BrightPath'):
        assert tok not in prompt, f'coach prompt leaked platform token {tok!r}'
