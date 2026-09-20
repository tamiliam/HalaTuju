"""Rich HTML student notices: assigned reviewer, profile complete, the application nudge, and
the contact-submission admin note.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.core.mail import EmailMessage
from .sending import _email_button, _html_email_shell, _send_html
from .shared import _P, _PROG_EN, _PROG_MS, _TEAM_EN, _TEAM_MS, logger


def send_student_assigned_reviewer_email(to_email, *, student_name, english_only=False,
                                         reviewer_name='', reviewer_email='', reviewer_phone=''):
    """Advance notice to the STUDENT once a reviewer is assigned: what happens next (an
    interview is coming, times to follow), with a short prep list. HTML primary + plain-text
    fallback; bilingual (EN + BM) by default, ``english_only=True`` drops the BM mirror. The
    interviewer's NAME is woven in when known, but never their contact details (owner's design).
    Best-effort; never breaks the assignment. Gated by STUDENT_ASSIGNMENT_EMAIL_ENABLED at the
    call site. (reviewer_email/reviewer_phone kept for call compatibility; unused.)"""
    if not to_email:
        return False
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    reviewer = (reviewer_name or '').strip()
    subject = 'Your ' + _PROG_EN + ' Programme interview — what happens next'

    en_intro = ('Your application has reached the interview stage of the ' + _PROG_EN + ' Programme, '
                + (f'and your interview will be with {reviewer}, one of our programme’s interviewers.'
                   if reviewer else 'and an interviewer from our team has now been assigned to you.'))
    en_what = ('The interview is a short video call, about 30 minutes, to understand your '
               'family’s situation fairly. We’ll send you a few times to choose from shortly, '
               'so you can pick the one that suits you best. Once you choose, we’ll send a '
               'Google Meet link and, if necessary, reminders before the call — there’s nothing you '
               'need to arrange yourself in the meantime.')
    en_points = [
        'Please join by video, with your camera on, as this helps us verify your application.',
        'If you are under 18, please have a parent or guardian with you for the call. If they’re '
        'available, our interviewer would be glad to speak with them whatever your age.',
        'The support is for families with genuine financial need, so we’ll ask honestly about your '
        'circumstances — and we value your honesty in return.',
    ]
    en_safety = (f'One note for your peace of mind: we’ll only ever ask about you and your studies. '
                 f'We will never ask you for money, a bank password, or an OTP or PIN. If anyone '
                 f'does, it’s not us — please tell us at {_P.email_support}.')

    bm_intro = ('Permohonan anda telah sampai ke peringkat temu duga Program ' + _PROG_MS + ', '
                + (f'dan temu duga anda akan bersama {reviewer}, salah seorang penemu duga program kami.'
                   if reviewer else 'dan seorang penemu duga daripada pasukan kami kini telah ditugaskan kepada anda.'))
    bm_what = ('Temu duga ialah panggilan video ringkas, kira-kira 30 minit, untuk memahami '
               'keadaan keluarga anda secara adil. Kami akan menghantar kepada anda beberapa masa '
               'untuk dipilih tidak lama lagi, supaya anda boleh memilih yang '
               'paling sesuai. Setelah anda memilih, kami akan menghantar pautan Google Meet dan, '
               'jika perlu, peringatan sebelum panggilan — tiada apa-apa yang perlu anda uruskan '
               'sendiri buat masa ini.')
    bm_points = [
        'Sila sertai melalui video, dengan kamera dibuka, kerana ini membantu kami mengesahkan '
        'permohonan anda.',
        'Jika anda di bawah 18 tahun, sila pastikan ibu bapa atau penjaga bersama anda semasa '
        'panggilan. Jika mereka ada, penemu duga kami amat berbesar hati untuk bercakap dengan '
        'mereka tidak kira umur anda.',
        'Bantuan ini untuk keluarga yang benar-benar memerlukan, jadi kami akan bertanya secara '
        'jujur tentang keadaan anda — dan kami menghargai kejujuran anda sebagai balasan.',
    ]
    bm_safety = (f'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan '
                 f'pengajian anda. Kami tidak sekali-kali akan meminta wang, kata laluan bank, '
                 f'atau OTP atau PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila '
                 f'beritahu kami di {_P.email_support}.')

    # ── Plain text ────────────────────────────────────────────────────────────
    def text_block(greeting, intro, what, points_label, points, safety, closing, signoff):
        bullets = '\n'.join(f'• {p}' for p in points)
        return (f'{greeting}\n\n{intro}\n\n{what}\n\n{points_label}\n{bullets}\n\n'
                f'{safety}\n\n{closing}\n\n{signoff}')
    en_text = text_block(
        f'Hi {en_name},', en_intro, en_what, 'A few things to know beforehand:', en_points,
        en_safety, 'We look forward to speaking with you.',
        'Warm regards,\n' + _TEAM_EN)
    bm_text = text_block(
        f'Salam {bm_name},', bm_intro, bm_what, 'Beberapa perkara untuk diketahui:', bm_points,
        bm_safety, 'Kami menantikan untuk bercakap dengan anda.',
        'Salam hormat,\n' + _TEAM_MS)
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML ──────────────────────────────────────────────────────────────────
    def html_block(greeting, intro, what, points_label, points, safety, closing, signoff):
        lis = ''.join(f'<li style="margin:0 0 8px;">{p}</li>' for p in points)
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{intro}</p>'
            f'<p style="margin:0 0 14px;">{what}</p>'
            f'<p style="margin:0 0 6px;">{points_label}</p>'
            f'<ul style="margin:0 0 16px;padding-left:20px;">{lis}</ul>'
            f'<p style="margin:0 0 16px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0 0 14px;">{closing}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = html_block(
        f'Hi {en_name},', en_intro, en_what, 'A few things to know beforehand:', en_points,
        en_safety, 'We look forward to speaking with you.',
        'Warm regards,<br>' + _TEAM_EN)
    bm_html = html_block(
        f'Salam {bm_name},', bm_intro, bm_what, 'Beberapa perkara untuk diketahui:', bm_points,
        bm_safety, 'Kami menantikan untuk bercakap dengan anda.',
        'Salam hormat,<br>' + _TEAM_MS)
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, subject, text_body, html_body)


def send_profile_complete_student_email(to_email, *, student_name, english_only=False):
    """Sent to the STUDENT when they confirm their profile (shortlisted → profile_complete):
    thanks + congratulates them for completing the stage and submitting documents, then sets
    expectations for what comes next (Check-2 review → possible doc requests / questions →
    interview with three slots to pick → minors need a parent/guardian present). HTML primary
    + plain-text fallback; bilingual (EN + BM) unless ``english_only``. Best-effort → bool."""
    if not to_email:
        return False
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    subject = 'Your B40 application is in — here’s what happens next'

    en_intro = ('Thank you — your application and documents for the ' + _PROG_EN + ' Programme are '
                'safely in. Pulling everything together takes real effort, so well done for getting '
                'it done.')
    en_lead = ('Your application is now with our team. Here’s exactly what happens next, so there '
               'are no surprises:')
    en_steps = [
        ('We review everything you’ve sent.', 'Our team reads through your application and documents '
         'carefully, to understand your family’s situation fairly. Sometimes we need a clearer copy '
         'of a document, an extra document, or a short answer to a question — if so, it’ll appear in '
         'your Action Centre and we’ll email to let you know. Just reply inside the Action Centre; '
         'responding quickly helps your application move along.'),
        ('We invite you to a short interview.', 'Once the review is settled, we’ll offer you three '
         'time slots — pick the one that suits you best. If you’re under 18, please choose a time a '
         'parent or guardian can join too, as they’ll need to be with you for the call.'),
        ('The interview itself.', 'It’s a short video call, about 30 minutes, on Google Meet. We’ll '
         'email the joining link as soon as you book, with a reminder before the call. Please join '
         'with your camera on so we can meet you face to face. If you’re under 18, your parent or '
         'guardian should be with you — and whatever your age, our interviewer is always glad to '
         'say hello to them.'),
    ]
    en_after = ('For now, there’s nothing you need to arrange — just keep an eye on your email and '
                'Action Centre. You’ll usually hear from us within about one to two weeks, whether '
                'that’s a quick question or your invitation to interview.')
    en_safety = (f'One note for your peace of mind: we’ll only ever ask about you and your studies. '
                 f'We will never ask you for money, a bank password, or an OTP or PIN. If anyone '
                 f'does, it isn’t us — please tell us straight away at {_P.email_support}.')

    bm_intro = ('Terima kasih — permohonan dan dokumen anda untuk Program ' + _PROG_MS + ' telah selamat '
                'diterima. Mengumpulkan semuanya memerlukan usaha yang sungguh-sungguh, jadi syabas '
                'kerana menyelesaikannya.')
    bm_lead = ('Permohonan anda kini bersama pasukan kami. Berikut ialah perkara yang akan berlaku '
               'seterusnya, supaya tiada kejutan:')
    bm_steps = [
        ('Kami menyemak semua yang anda hantar.', 'Pasukan kami membaca permohonan dan dokumen anda '
         'dengan teliti, untuk memahami keadaan keluarga anda secara adil. Kadangkala kami '
         'memerlukan salinan dokumen yang lebih jelas, dokumen tambahan, atau jawapan ringkas '
         'kepada soalan — jika ya, ia akan muncul di Pusat Tindakan anda dan kami akan menghantar '
         'e-mel untuk memberitahu anda. Balas sahaja di dalam Pusat Tindakan; membalas dengan cepat '
         'membantu permohonan anda bergerak.'),
        ('Kami menjemput anda ke temu duga ringkas.', 'Setelah semakan selesai, kami akan menawarkan '
         'anda tiga slot masa — pilih yang paling sesuai untuk anda. Jika anda di bawah 18 tahun, '
         'sila pilih masa yang membolehkan ibu bapa atau penjaga turut menyertai, kerana mereka '
         'perlu bersama anda semasa panggilan.'),
        ('Temu duga itu sendiri.', 'Ia panggilan video ringkas, kira-kira 30 minit, melalui Google '
         'Meet. Kami akan menghantar pautan untuk menyertai sebaik sahaja anda menempah, dengan '
         'peringatan sebelum panggilan. Sila sertai dengan kamera dibuka supaya kami dapat bertemu '
         'anda secara bersemuka. Jika anda di bawah 18 tahun, ibu bapa atau penjaga anda perlu '
         'bersama anda — dan tidak kira umur anda, penemu duga kami sentiasa berbesar hati untuk '
         'menyapa mereka.'),
    ]
    bm_after = ('Buat masa ini, tiada apa-apa yang perlu anda uruskan — pantau sahaja e-mel dan '
                'Pusat Tindakan anda. Kebiasaannya anda akan mendengar daripada kami dalam masa '
                'kira-kira satu hingga dua minggu, sama ada soalan ringkas atau jemputan temu duga '
                'anda.')
    bm_safety = (f'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan '
                 f'pengajian anda. Kami tidak sekali-kali akan meminta wang, kata laluan bank, atau '
                 f'OTP atau PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami '
                 f'dengan segera di {_P.email_support}.')

    # ── Plain text ────────────────────────────────────────────────────────────
    def text_block(greeting, intro, lead, steps, btn_line, after, safety, signoff):
        body_steps = '\n\n'.join(f'{i}. {t} {d}' for i, (t, d) in enumerate(steps, 1))
        return (f'{greeting}\n\n{intro}\n\n{lead}\n\n{body_steps}\n\n{btn_line}\n\n'
                f'{after}\n\n{safety}\n\n{signoff}')
    en_text = text_block(
        f'Hi {en_name},', en_intro, en_lead, en_steps, f'View my application: {link}', en_after,
        en_safety, 'Warm regards,\n' + _TEAM_EN)
    bm_text = text_block(
        f'Salam {bm_name},', bm_intro, bm_lead, bm_steps, f'Lihat permohonan saya: {link}', bm_after,
        bm_safety, 'Salam hormat,\n' + _TEAM_MS)
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML ──────────────────────────────────────────────────────────────────
    def html_block(greeting, intro, lead, steps, btn_label, after, safety, signoff):
        lis = ''.join(
            f'<li style="margin:0 0 12px;"><strong>{t}</strong> {d}</li>' for t, d in steps)
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{intro}</p>'
            f'<p style="margin:0 0 10px;">{lead}</p>'
            f'<ol style="margin:0 0 18px;padding-left:20px;">{lis}</ol>'
            f'<p style="margin:0 0 18px;">{_email_button(link, btn_label)}</p>'
            f'<p style="margin:0 0 14px;">{after}</p>'
            f'<p style="margin:0 0 16px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = html_block(
        f'Hi {en_name},', en_intro, en_lead, en_steps, 'View my application', en_after,
        en_safety, 'Warm regards,<br>' + _TEAM_EN)
    bm_html = html_block(
        f'Salam {bm_name},', bm_intro, bm_lead, bm_steps, 'Lihat permohonan saya', bm_after,
        bm_safety, 'Salam hormat,<br>' + _TEAM_MS)
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    # General programme email → from info@ (DEFAULT_FROM_EMAIL), reply to support; NOT interview@.
    return _send_html(to_email, subject, text_body, html_body,
                      from_email=_P.email_from,
                      reply_to=[_P.email_support])


def send_application_nudge_email(to_email, *, student_name, english_only=False):
    """A short, warm note (deliberately NOT a nagging reminder) to a SHORTLISTED student who has
    finished everything but not pressed the final "Review & submit" (so their application is still
    a draft with us). It leads with what they've DONE — the nudge only fires when nothing is
    outstanding — and points at the single last action. Sent by the auto sweep AND the org-admin
    Blockers-box button (one shared template). HTML primary + plain-text fallback; bilingual
    (EN + BM) unless ``english_only``. Best-effort → bool."""
    if not to_email:
        return False
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    link = f'{_P.frontend_url}/scholarship/application'
    subject = f'One last step to finish your {_PROG_EN} application'

    en_intro = (f'<strong>You’re almost there!</strong> You have completed all the groundwork for '
                f'your {_PROG_EN} application: your details, your documents, and your consent are '
                'all in place.')
    en_body = ('There’s just <strong>one final step</strong> left, and it takes less than a minute: '
               'log in, open your application, and press the "Review &amp; submit" button. That '
               'final press is what sends your application to us for review — until you press it, it '
               'stays a draft with us, so please do it when you have a moment.')
    en_after = ('If you have any trouble, just reply to this email and we’ll help you.')
    en_safety = (f'One note for your peace of mind: we’ll only ever ask about you and your studies. '
                 f'We will never ask you for money, a bank password, or an OTP or PIN. If anyone '
                 f'does, it isn’t us — please tell us straight away at {_P.email_support}.')

    bm_intro = (f'<strong>Anda hampir selesai!</strong> Anda telah melengkapkan semua asas untuk '
                f'permohonan {_PROG_MS} anda: butiran anda, dokumen anda, dan persetujuan anda '
                'semuanya sudah ada.')
    bm_body = ('Tinggal <strong>satu langkah terakhir</strong> sahaja, dan ia mengambil masa kurang '
               'seminit: log masuk, buka permohonan anda, dan tekan butang "Semak &amp; hantar". '
               'Tekanan terakhir itulah yang menghantar permohonan anda kepada kami untuk semakan — '
               'selagi anda tidak menekannya, ia kekal sebagai draf dengan kami, jadi sila lakukannya '
               'apabila anda ada masa.')
    bm_after = ('Jika anda menghadapi sebarang masalah, balas sahaja e-mel ini dan kami akan '
                'membantu anda.')
    bm_safety = (f'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan '
                 f'pengajian anda. Kami tidak sekali-kali akan meminta wang, kata laluan bank, atau '
                 f'OTP atau PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami '
                 f'dengan segera di {_P.email_support}.')

    def text_block(greeting, intro, body, btn_line, after, safety, signoff):
        # Plain-text: drop the HTML emphasis tags + the ampersand entity used in the HTML.
        intro = intro.replace('<strong>', '').replace('</strong>', '')
        body = body.replace('<strong>', '').replace('</strong>', '').replace('&amp;', '&')
        return f'{greeting}\n\n{intro}\n\n{body}\n\n{btn_line}\n\n{after}\n\n{safety}\n\n{signoff}'
    en_text = text_block(f'Hi {en_name},', en_intro, en_body, f'Open my application: {link}',
                         en_after, en_safety, 'Warm regards,\n' + _TEAM_EN)
    bm_text = text_block(f'Salam {bm_name},', bm_intro, bm_body, f'Buka permohonan saya: {link}',
                         bm_after, bm_safety, 'Salam hormat,\n' + _TEAM_MS)
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    def html_block(greeting, intro, body, btn_label, after, safety, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{intro}</p>'
            f'<p style="margin:0 0 18px;">{body}</p>'
            f'<p style="margin:0 0 18px;">{_email_button(link, btn_label)}</p>'
            f'<p style="margin:0 0 14px;">{after}</p>'
            f'<p style="margin:0 0 16px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = html_block(f'Hi {en_name},', en_intro, en_body, 'Open my application', en_after,
                         en_safety, 'Warm regards,<br>' + _TEAM_EN)
    bm_html = html_block(f'Salam {bm_name},', bm_intro, bm_body, 'Buka permohonan saya', bm_after,
                         bm_safety, 'Salam hormat,<br>' + _TEAM_MS)
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    # General programme email → from info@ (DEFAULT_FROM_EMAIL), reply to support; NOT interview@.
    return _send_html(to_email, subject, text_body, html_body,
                      from_email=_P.email_from,
                      reply_to=[_P.email_support])


def send_contact_submission_admin_email(*, to_email, name, contact, category, message, created_at):
    """Internal: email a public contact-form submission to the team (contact@ via
    ADMIN_NOTIFY_EMAIL). Reply-To is set to the submitter's contact when it looks like
    an email, so a reply goes straight back to them. Plain English. Best-effort → bool."""
    if not to_email:
        return False
    body = (
        f'New contact-form message — {category}\n\n'
        f'From:     {name}\n'
        f'Contact:  {contact}\n'
        f'Received: {created_at}\n\n'
        f'{message}\n'
    )
    reply_to = [contact] if (contact and '@' in contact) else None
    try:
        EmailMessage(
            subject=f'[HalaTuju contact] {category} — {name}'[:120],
            body=body,
            from_email=_P.email_from,
            to=[to_email],
            reply_to=reply_to,
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send contact-submission email to %s', to_email, exc_info=True)
        return False
