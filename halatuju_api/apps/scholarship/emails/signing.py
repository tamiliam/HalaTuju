"""The agreement lifecycle mail: sign invitation, executed agreement, the executed copy,
witness and countersignature chasers, and the raw partner / sponsor send primitives.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .sending import _email_button, _html_email_shell, _send_html
from .shared import _DEFAULT_NAME, _P, _PROG_EN, _TEAM_EN
from .student_decisions import _send, normalise_lang


# ── Bursary signing chain (BURSARY_AGREEMENT_ENABLED) ─────────────────────────
# Two student-facing trilingual emails (the "now sign" follow-up + the executed
# confirmation) + two internal English notifications (partner witness-pending +
# Foundation countersign-pending). No donor is ever named in any of them.

SIGN_INVITE_SUBJECTS = {
    'en': 'Your {programme} agreement is ready to sign ✍️',
    'ms': 'Perjanjian {programme} anda sedia untuk ditandatangani ✍️',
    'ta': 'உங்கள் {programme} ஒப்பந்தம் கையொப்பமிடத் தயாராக உள்ளது ✍️',
}
SIGN_INVITE_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "The next step in your bursary is ready: your bursary agreement. Please log in and "
        "open your Action Centre, where you'll first go through a short, friendly check to "
        "make sure the terms are clear, and then sign the agreement together with your parent "
        "or guardian — all on the same device.\n{link}\n\n"
        "Please have your parent or guardian with you when you sign: they sign as your "
        "guarantor, and we'll send a one-time PIN to their phone to confirm it's them.\n\n"
        "If you have any questions, reply to this email or contact us at {support}.\n\n"
        "Warm wishes,\n{signoff}"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Langkah seterusnya dalam biasiswa anda sudah sedia: perjanjian biasiswa anda. Sila "
        "log masuk dan buka Pusat Tindakan anda. Anda akan melalui semakan ringkas dan mesra "
        "dahulu untuk memastikan terma jelas, kemudian menandatangani perjanjian bersama ibu "
        "bapa atau penjaga anda — semuanya pada peranti yang sama.\n{link}\n\n"
        "Sila pastikan ibu bapa atau penjaga anda bersama anda semasa menandatangani: mereka "
        "menandatangani sebagai penjamin anda, dan kami akan menghantar PIN sekali guna ke "
        "telefon mereka untuk mengesahkannya.\n\n"
        "Jika ada sebarang pertanyaan, balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Salam mesra,\n{signoff}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "உங்கள் உதவித்தொகையின் அடுத்த படி தயாராக உள்ளது: உங்கள் உதவித்தொகை ஒப்பந்தம். உள்நுழைந்து "
        "உங்கள் செயல் மையத்தைத் (Action Centre) திறக்கவும். முதலில் விதிமுறைகள் தெளிவாக இருப்பதை "
        "உறுதிசெய்ய ஒரு சிறிய, நட்பான சரிபார்ப்பின் வழியாகச் செல்வீர்கள், பின்னர் உங்கள் பெற்றோர் "
        "அல்லது பாதுகாவலருடன் சேர்ந்து — ஒரே சாதனத்தில் — ஒப்பந்தத்தில் கையொப்பமிடுவீர்கள்.\n{link}\n\n"
        "கையொப்பமிடும்போது உங்கள் பெற்றோர் அல்லது பாதுகாவலர் உங்களுடன் இருப்பதை உறுதிசெய்யவும்: "
        "அவர்கள் உங்கள் பிணையாளராகக் கையொப்பமிடுகிறார்கள், அவர்கள்தான் என்பதை உறுதிப்படுத்த அவர்களின் "
        "தொலைபேசிக்கு ஒரு முறை PIN அனுப்புவோம்.\n\n"
        "ஏதேனும் கேள்விகள் இருந்தால், இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் "
        "எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "அன்புடன்,\n{signoff}"
    ),
}


def send_sign_invitation_email(to_email, applicant_name, lang='en', branding=None):
    """The follow-up "your agreement is ready to sign" email (owner-sent, after the
    bank-details email). Points to /scholarship/application → Action Centre → the
    comprehension quiz → signing. NO amount, NO sponsor identity. Plain text + info@."""
    if not to_email:
        return False
    b = branding or _P
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    return _send(to_email, SIGN_INVITE_SUBJECTS, SIGN_INVITE_BODIES, name,
                 b.programme_name(lang), lang,
                 extra={'support': b.email_support, 'signoff': b.team_signoff(lang)},
                 branding=b)


AGREEMENT_EXECUTED_SUBJECTS = {
    'en': 'Your {programme} agreement is now in effect 🎓',
    'ms': 'Perjanjian {programme} anda kini berkuat kuasa 🎓',
    'ta': 'உங்கள் {programme} ஒப்பந்தம் இப்போது அமலுக்கு வந்துள்ளது 🎓',
}
AGREEMENT_EXECUTED_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Good news — your bursary agreement is now fully signed and in effect. Everyone who "
        "needed to sign has done so, and your bursary is confirmed.\n\n"
        "You can view your application and your signed agreement here:\n{link}\n\n"
        "We'll be in touch with the next steps. If you have any questions, reply to this email "
        "or contact us at {support}.\n\n"
        "Warm congratulations,\n{signoff}"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Berita baik — perjanjian biasiswa anda kini ditandatangani sepenuhnya dan berkuat "
        "kuasa. Semua pihak yang perlu menandatangani telah berbuat demikian, dan biasiswa anda "
        "telah disahkan.\n\n"
        "Anda boleh melihat permohonan dan perjanjian anda yang ditandatangani di sini:\n{link}\n\n"
        "Kami akan menghubungi anda dengan langkah seterusnya. Jika ada sebarang pertanyaan, "
        "balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Tahniah,\n{signoff}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "நல்ல செய்தி — உங்கள் உதவித்தொகை ஒப்பந்தம் இப்போது முழுமையாகக் கையொப்பமிடப்பட்டு அமலுக்கு "
        "வந்துள்ளது. கையொப்பமிட வேண்டிய அனைவரும் கையொப்பமிட்டுவிட்டனர், உங்கள் உதவித்தொகை "
        "உறுதிப்படுத்தப்பட்டுள்ளது.\n\n"
        "உங்கள் விண்ணப்பத்தையும் கையொப்பமிடப்பட்ட ஒப்பந்தத்தையும் இங்கே காணலாம்:\n{link}\n\n"
        "அடுத்த படிகளுடன் நாங்கள் உங்களைத் தொடர்புகொள்வோம். ஏதேனும் கேள்விகள் இருந்தால், இந்த "
        "மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "இதயப்பூர்வ வாழ்த்துகள்,\n{signoff}"
    ),
}


def send_agreement_executed_email(to_email, applicant_name, programme_name='', lang='en',
                                  link='', pdf=None, branding=None):
    """Sent when the bursary agreement is fully executed (student + guarantor + Foundation
    signed → application 'active'). Confirms the bursary is in effect. NO sponsor identity.
    From info@. When ``pdf`` (the signed-agreement bytes) is given, it is ATTACHED and the
    mail goes HTML via ``_send_html``; otherwise the plain ``_send`` path (backward-compat)."""
    if not to_email:
        return False
    b = branding or _P
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    # The brand name is language-specific and read from the seam (the {programme} placeholder);
    # the caller's ``programme_name`` (the EN cohort name) is not the per-language brand form.
    signoff = b.team_signoff(lang)
    if pdf is None:
        return _send(to_email, AGREEMENT_EXECUTED_SUBJECTS, AGREEMENT_EXECUTED_BODIES,
                     name, b.programme_name(lang), lang,
                     extra={'support': b.email_support, 'signoff': signoff}, branding=b)
    subject = AGREEMENT_EXECUTED_SUBJECTS[lang].format(programme=b.programme_name(lang))
    text = AGREEMENT_EXECUTED_BODIES[lang].format(
        name=name, link=link or '', support=b.email_support,
        programme=b.programme_name(lang), signoff=signoff)
    html = _html_email_shell('<p style="margin:0 0 14px;">'
                             + text.replace('\n\n', '</p><p style="margin:0 0 14px;">').replace('\n', '<br>')
                             + '</p>')
    return _send_html(
        to_email, subject, text, html,
        from_email=b.email_from,
        reply_to=[b.email_support],
        attachments=[('bursary_agreement.pdf', pdf, 'application/pdf')])


def send_executed_copy_email(to_email, *, applicant_name='', programme_name='', pdf=None, link=''):
    """A copy of a fully-executed bursary agreement, for the witnessing partner contact and
    the org admins (Sprint 5 distribution). Internal (English); the signed PDF attached when
    available. From info@, reply-to help@. Best-effort → bool. Donor never named."""
    if not to_email:
        return False
    who = applicant_name or 'a student'
    subject = f'Executed bursary agreement — {who}'
    text = (f"Hello,\n\nThe bursary agreement for {who} is now fully signed and in effect. "
            f"A copy of the signed agreement is attached for your records.\n\n"
            + (f"View the application:\n{link}\n\n" if link else "")
            + _TEAM_EN)
    html = _html_email_shell(
        '<p style="margin:0 0 14px;">Hello,</p>'
        f'<p style="margin:0 0 14px;">The bursary agreement for <strong>{who}</strong> is now '
        'fully signed and in effect. A copy of the signed agreement is attached for your records.</p>'
        + (f'<p style="margin:0 0 6px;">{_email_button(link, "Open the application")}</p>' if link else '')
        + f'<p style="margin:18px 0 0;">{_TEAM_EN}</p>')
    attachments = [('bursary_agreement.pdf', pdf, 'application/pdf')] if pdf else None
    return _send_html(
        to_email, subject, text, html,
        from_email=_P.email_from,
        reply_to=[_P.email_support], attachments=attachments)


def send_witness_pending_email(to_email, *, contact_person='', applicant_name='',
                               org_name='', link=''):
    """Internal (English) nudge to the referring partner organisation: a bursary agreement
    for a student they referred is awaiting their WITNESS signature. Best-effort. The donor
    is never named; the partner already knows the student (they referred them).

    ⚠ **IT USED TO SAY "log in to the partner console", AND THERE IS NO SUCH CONSOLE.** The button
    pointed at `bursary._cockpit_link` → `/admin/scholarship/<id>`, a page no referral-org login can
    load: `_b40_scope` returns `'none'` for the `partner` role, so they would have been told to do
    something impossible and then bounced. Corrected 2026-08-03 to ask them to reply, which is a
    thing they can actually do.

    ``link`` is still accepted — every caller passes it and the argument is the natural home for the
    address once a source-organisation console exists — but it is deliberately NOT rendered. Restore
    the button in the same change that gives them somewhere to land, not before.
    """
    if not to_email:
        return False
    greeting = f'Dear {contact_person},' if contact_person else 'Hello,'
    who = f'<strong>{applicant_name}</strong>' if applicant_name else 'a student you referred'
    text = (
        f"{greeting}\n\n"
        f"A {_PROG_EN} agreement for {applicant_name or 'a student you referred'} is "
        f"ready for your organisation's witness signature. The student and their parent/guardian "
        f"have signed; you are recorded as the witnessing partner.\n\n"
        f"Just reply to this email and we will send you everything you need to add your "
        f"signature.\n\n"
        f"Thank you,\n{_TEAM_EN}"
    )
    html = _html_email_shell(
        f'<p style="margin:0 0 14px;">{greeting}</p>'
        f'<p style="margin:0 0 14px;">A {_PROG_EN} agreement for {who} is ready for '
        f'your organisation’s <strong>witness signature</strong>. The student and their '
        f'parent or guardian have signed; you are recorded as the witnessing partner'
        f'{(" for " + org_name) if org_name else ""}.</p>'
        f'<p style="margin:0 0 18px;">Just reply to this email and we will send you everything '
        f'you need to add your signature.</p>'
        f'<p style="margin:18px 0 0;">Thank you,<br><strong>{_TEAM_EN}</strong></p>'
    )
    return _send_html(
        to_email, 'A bursary agreement is awaiting your witness signature', text, html,
        from_email=_P.email_from,
        reply_to=[_P.email_support],
    )


def send_partner_email(to_email, *, subject, text_body, html_body):
    """Send ONE already-rendered partner-organisation email (2026-07-26).

    The subject/text/html come from `partner_comms.render`, which owns the wording; this function
    owns only the envelope — the shared HTML shell (so a partner email looks like every other
    HalaTuju email and stays inside the branding guard), the programme's own sender identity, and
    a reply-to that works, since there is no bursary partner console to send anyone to.

    HTML is the primary part with a plain-text alternative carrying the same information (owner:
    HTML by default, 2026-07-26). Best-effort → bool, like every other sender here.
    """
    if not to_email:
        return False
    return _send_html(
        to_email, subject, text_body, _html_email_shell(html_body),
        from_email=_P.email_from,
        reply_to=[_P.email_support],
    )


def send_sponsor_email(to_email, *, subject, text_body, html_body):
    """Send ONE already-rendered sponsor email (S3, 2026-07-28).

    The twin of `send_partner_email`, and for the same reason: the subject/text/html come from
    `sponsor_comms.render`, which owns the WORDING, and this owns only the ENVELOPE — the shared
    HTML shell (so an editable email still looks like every other HalaTuju email and stays inside
    the branding guard), the programme's sender identity, and the sponsor reply-to that already
    serves the notification emails.

    HTML primary, plain text carrying the same information. Best-effort → bool.
    """
    if not to_email:
        return False
    return _send_html(
        to_email, subject, text_body, _html_email_shell(html_body),
        from_email=_P.email_from,
        reply_to=[_P.sponsor_reply_to],
    )


def send_countersign_pending_email(to_email, *, applicant_name='', link=''):
    """Internal (English) nudge to the Foundation officer / super admins: a bursary agreement
    is awaiting the Foundation's COUNTERSIGNATURE (the binding, final signature that activates
    the bursary). Best-effort. No donor named."""
    if not to_email:
        return False
    who = f'<strong>{applicant_name}</strong>' if applicant_name else 'a student'
    text = (
        "Hello,\n\n"
        f"A {_PROG_EN} agreement for {applicant_name or 'a student'} is awaiting the "
        f"Foundation's countersignature. The student, their guarantor"
        f"{' and the witnessing partner' if link else ''} have signed; the Foundation's "
        f"signature is the final, binding step that activates the bursary.\n\n"
        f"Please log in to the console to review and countersign:\n{link}\n\n"
        f"Thank you,\n{_TEAM_EN}"
    )
    html = _html_email_shell(
        f'<p style="margin:0 0 14px;">Hello,</p>'
        f'<p style="margin:0 0 14px;">A {_PROG_EN} agreement for {who} is awaiting the '
        f'<strong>Foundation’s countersignature</strong> — the final, binding step '
        f'that activates the bursary.</p>'
        f'<p style="margin:0 0 6px;">{_email_button(link, "Open the console")}</p>'
        f'<p style="margin:18px 0 0;">Thank you,<br><strong>{_TEAM_EN}</strong></p>'
    )
    return _send_html(
        to_email, 'A bursary agreement is awaiting the Foundation countersignature', text, html,
        from_email=_P.email_from,
        reply_to=[_P.email_support],
    )
