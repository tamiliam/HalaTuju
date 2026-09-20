"""Student interview mail: booked, slots proposed, reminder, cancelled, released.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .sending import _email_button, _fmt_myt, _gcal_url, _html_email_shell, _interview_ics, _join_line, _send_html
from .shared import _P, _PROG_EN, _PROG_MS, _TEAM_EN, _TEAM_MS


def send_interview_booked_email(to_email, *, student_name, reviewer_name, start,
                                meeting_url='', english_only=False, duration_min=None,
                                reviewer_phone='', reschedule_cutoff_hours=None):
    """Student confirmation that an interview slot is booked. HTML primary + plain-text
    fallback; bilingual (EN + BM) by default, ``english_only=True`` drops the BM mirror.
    Names the interviewer (no contact details); attaches an .ics + an Add-to-calendar
    button. Best-effort. (``reviewer_phone`` kept for call compatibility; unused.)"""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    reviewer = (reviewer_name or '').strip()
    rev_en = reviewer or 'one of our interviewers'
    rev_bm = reviewer or 'salah seorang penemu duga kami'
    when = _fmt_myt(start)
    # ⚠ Both numbers belong to the ORGANISATION, and this sender has none — the caller
    # (`scheduling.book`) resolves them and passes them in. The fallback below is the ONE
    # registry default, never a literal: a second literal here is how the cutoff this email
    # PROMISES drifts from the cutoff `_cutoff_ok` ENFORCES.
    from apps.courses import org_config
    cutoff = (reschedule_cutoff_hours if reschedule_cutoff_hours is not None
              else org_config.default('interview_reschedule_cutoff_hours'))
    duration_min = duration_min or org_config.default('interview_duration_min')
    app_link = f"{_P.frontend_url}/scholarship/application"
    summary = '' + _PROG_EN + ' Programme interview'
    details = f'Join: {meeting_url}' if meeting_url else 'Your interviewer will share the video-call link.'
    gcal = _gcal_url(start=start, duration_min=duration_min, text=summary,
                     details=details, location=meeting_url or 'Video call')
    ics = _interview_ics(start=start, duration_min=duration_min, summary=summary,
                         description=details, location=meeting_url or 'Video call')
    join_en = (f'Join here: {meeting_url}' if meeting_url
               else 'Your interviewer will share the video-call link before the interview.')
    join_bm = (f'Sertai di sini: {meeting_url}' if meeting_url
               else 'Penemu duga anda akan berkongsi pautan panggilan video sebelum temu duga.')

    en_text = (
        f'Hi {en_name},\n\n'
        f'Your ' + _PROG_EN + ' Programme interview is confirmed. Here are the details:\n\n'
        f'Date & time: {when}\n'
        f'Interviewer: {rev_en}\n'
        f'{join_en}\n\n'
        f'Add to calendar: {gcal}\n\n'
        f'The interview is a video call and takes about 30 minutes. Please join with your camera '
        f'on. If you are under 18, please have a parent or guardian with you; whatever your age, '
        f'they’re welcome to join too.\n\n'
        f'Need a different time? You can reschedule or cancel from your application page in '
        f'HalaTuju ({app_link}) up to {cutoff} hours before the interview.\n\n'
        f'One note for your peace of mind: we’ll only ever ask about you and your studies. We will '
        f'never ask you for money, a bank password, or an OTP or PIN. If anyone does, it’s not us — '
        f'please tell us at {_P.email_support}.\n\n'
        f'We look forward to speaking with you.\n\n'
        f'Warm regards,\n' + _TEAM_EN
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'Temu duga Program ' + _PROG_MS + ' anda telah disahkan. Berikut butirannya:\n\n'
        f'Tarikh & masa: {when}\n'
        f'Penemu duga: {rev_bm}\n'
        f'{join_bm}\n\n'
        f'Tambah ke kalendar: {gcal}\n\n'
        f'Temu duga ialah panggilan video dan mengambil masa kira-kira 30 minit. Sila sertai '
        f'dengan kamera dibuka. Jika anda di bawah 18 tahun, sila pastikan ibu bapa atau penjaga '
        f'bersama anda; tidak kira umur anda, mereka juga dialu-alukan untuk menyertai.\n\n'
        f'Perlu masa lain? Anda boleh menjadual semula atau membatalkan melalui halaman permohonan '
        f'anda di HalaTuju ({app_link}) sehingga {cutoff} jam sebelum temu duga.\n\n'
        f'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan pengajian '
        f'anda. Kami tidak sekali-kali akan meminta wang, kata laluan bank, atau OTP atau PIN. Jika '
        f'sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.\n\n'
        f'Kami menantikan untuk bercakap dengan anda.\n\n'
        f'Salam hormat,\n' + _TEAM_MS
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    def section(greeting, lead, rows, join, btn_label, body, safety, closing, signoff):
        detail_rows = ''.join(
            f'<tr><td style="padding:2px 10px 2px 0;color:#6b7280;white-space:nowrap;">{k}</td>'
            f'<td style="padding:2px 0;">{v}</td></tr>' for k, v in rows)
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 12px;">{lead}</p>'
            f'<table style="margin:0 0 16px;border-collapse:collapse;font-size:15px;"><tbody>'
            f'{detail_rows}<tr><td style="padding:2px 10px 2px 0;color:#6b7280;">{join[0]}</td>'
            f'<td style="padding:2px 0;">{join[1]}</td></tr></tbody></table>'
            f'<p style="margin:0 0 18px;">{_email_button(gcal, btn_label)}</p>'
            f'<p style="margin:0 0 14px;">{body}</p>'
            f'<p style="margin:0 0 16px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0 0 14px;">{closing}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    join_cell_en = (f'<a href="{meeting_url}">{meeting_url}</a>' if meeting_url
                    else 'Your interviewer will share the link before the interview.')
    join_cell_bm = (f'<a href="{meeting_url}">{meeting_url}</a>' if meeting_url
                    else 'Penemu duga anda akan berkongsi pautan sebelum temu duga.')
    en_html = section(
        f'Hi {en_name},',
        'Your ' + _PROG_EN + ' Programme interview is confirmed. Here are the details:',
        [('Date &amp; time', when), ('Interviewer', rev_en)], ('Join here', join_cell_en),
        'Add to calendar',
        'The interview is a video call and takes about 30 minutes. Please join with your camera on. '
        'If you are under 18, please have a parent or guardian with you; whatever your age, they’re '
        'welcome to join too. Need a different time? You can reschedule or cancel from '
        f'<a href="{app_link}">your application page</a> in HalaTuju up to {cutoff} hours before the '
        'interview.',
        'One note for your peace of mind: we’ll only ever ask about you and your studies. We will '
        f'never ask you for money, a bank password, or an OTP or PIN. If anyone does, it’s not us — '
        f'please tell us at {_P.email_support}.',
        'We look forward to speaking with you.',
        'Warm regards,<br>' + _TEAM_EN)
    bm_html = section(
        f'Salam {bm_name},',
        'Temu duga Program ' + _PROG_MS + ' anda telah disahkan. Berikut butirannya:',
        [('Tarikh &amp; masa', when), ('Penemu duga', rev_bm)], ('Sertai di sini', join_cell_bm),
        'Tambah ke kalendar',
        'Temu duga ialah panggilan video dan mengambil masa kira-kira 30 minit. Sila sertai dengan '
        'kamera dibuka. Jika anda di bawah 18 tahun, sila pastikan ibu bapa atau penjaga bersama '
        'anda; tidak kira umur anda, mereka juga dialu-alukan untuk menyertai. Perlu masa lain? Anda '
        f'boleh menjadual semula atau membatalkan melalui <a href="{app_link}">halaman permohonan '
        f'anda</a> sehingga {cutoff} jam sebelum temu duga.',
        'Satu nota untuk ketenangan anda: kami hanya akan bertanya tentang diri dan pengajian anda. '
        f'Kami tidak sekali-kali akan meminta wang, kata laluan bank, atau OTP atau PIN. Jika sesiapa '
        f'berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.',
        'Kami menantikan untuk bercakap dengan anda.',
        'Salam hormat,<br>' + _TEAM_MS)
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, 'Your ' + _PROG_EN + ' Programme interview is booked',
                      text_body, html_body, ics=ics)


def send_interview_slots_proposed_email(to_email, *, student_name, english_only=False,
                                        reviewer_name='', rescheduled=False):
    """Student notice that interview times are ready to pick — fired when the reviewer
    PROPOSES slots, so the in-app scheduler isn't invisible to students. HTML primary +
    plain-text fallback. Bilingual (EN + BM) by default; ``english_only=True`` drops the
    BM mirror (used for confidently English-preferring students). Links to the application
    page (the booking panel lives there); a Google Meet link is created automatically on
    booking. ``rescheduled=True`` is sent when the REVIEWER moved an already-booked
    interview — the intro/subject then explain the original time was released and ask the
    student to pick again. Best-effort → bool. (``reviewer_name`` kept for call compat.)"""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    frontend = _P.frontend_url
    link = f'{frontend}/scholarship/application'
    subject = ('Your ' + _PROG_EN + ' Programme interview time has changed — pick a new slot'
               if rescheduled
               else 'Pick a time slot for your ' + _PROG_EN + ' Programme interview')
    intro_en = (
        'Your interviewer has had to move your interview, so the time you had booked has been '
        'released. Please choose a new date and time that suits you best.'
        if rescheduled else
        'The next step in your ' + _PROG_EN + ' Programme application is a short interview, and '
        'you can choose the date and time that suits you best.')
    intro_bm = (
        'Penemu duga anda terpaksa menukar temu duga anda, jadi masa yang anda tempah sebelum ini '
        'telah dilepaskan. Sila pilih tarikh dan masa baharu yang paling sesuai untuk anda.'
        if rescheduled else
        'Langkah seterusnya dalam permohonan Program ' + _PROG_MS + ' anda ialah temu duga ringkas, '
        'dan anda boleh memilih tarikh dan masa yang paling sesuai.')

    # ── Plain-text fallback ───────────────────────────────────────────────────
    en_text = (
        f'Hi {en_name},\n\n'
        f'{intro_en}\n\n'
        f'Choose your interview time: {link}\n\n'
        f'The interview is a video call and takes about 30 minutes. Once you pick a slot, we’ll '
        f'email you a confirmation with a Google Meet link, and send reminders one day and one '
        f'hour before.\n\n'
        f'If none of them suit you, you can ask for other times on that same page — your '
        f'interviewer will then suggest new ones.\n\n'
        f'For your peace of mind: we’ll only ever ask about you and your studies. We will never '
        f'ask you for money, your password, or an OTP or PIN. If anyone claiming to represent the '
        f'' + _PROG_EN + ' Programme does, it isn’t us.\n\n'
        f'Warm regards,\n' + _TEAM_EN
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'{intro_bm}\n\n'
        f'Pilih masa temu duga anda: {link}\n\n'
        f'Temu duga dijalankan melalui panggilan video dan mengambil masa kira-kira 30 minit. '
        f'Setelah anda memilih slot, kami akan menghantar e-mel pengesahan dengan pautan Google '
        f'Meet, serta peringatan satu hari dan satu jam sebelumnya.\n\n'
        f'Jika tiada yang sesuai, anda boleh meminta masa lain pada halaman yang sama — penemu '
        f'duga anda kemudian akan mencadangkan masa baharu.\n\n'
        f'Untuk ketenangan anda: kami hanya akan bertanya tentang diri dan pengajian anda. Kami '
        f'tidak sekali-kali akan meminta wang, kata laluan, atau OTP atau PIN. Jika sesiapa yang '
        f'mendakwa mewakili Program ' + _PROG_MS + ' berbuat demikian, itu bukan kami.\n\n'
        f'Salam hormat,\n' + _TEAM_MS
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML primary (EN then BM) ─────────────────────────────────────────────
    def section(greeting, intro, btn_label, detail, alt, safety, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 18px;">{intro}</p>'
            f'<p style="margin:0 0 18px;">{_email_button(link, btn_label)}</p>'
            f'<p style="margin:0 0 14px;">{detail}</p>'
            f'<p style="margin:0 0 18px;">{alt}</p>'
            f'<p style="margin:0 0 18px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = section(
        f'Hi {en_name},',
        intro_en,
        'Choose your interview time',
        'The interview is a video call and takes about 30 minutes. Once you pick a slot, we’ll '
        'email you a confirmation with a Google Meet link, and send reminders one day and one '
        'hour before.',
        'If none of them suit you, you can ask for other times on that same page — your '
        'interviewer will then suggest new ones.',
        'For your peace of mind: we’ll only ever ask about you and your studies. We will never ask '
        'you for money, your password, or an OTP or PIN. If anyone claiming to represent the B40 '
        'Assistance Programme does, it isn’t us.',
        'Warm regards,<br>' + _TEAM_EN)
    bm_html = section(
        f'Salam {bm_name},',
        intro_bm,
        'Pilih masa temu duga anda',
        'Temu duga dijalankan melalui panggilan video dan mengambil masa kira-kira 30 minit. '
        'Setelah anda memilih slot, kami akan menghantar e-mel pengesahan dengan pautan Google '
        'Meet, serta peringatan satu hari dan satu jam sebelumnya.',
        'Jika tiada yang sesuai, anda boleh meminta masa lain pada halaman yang sama — penemu duga '
        'anda kemudian akan mencadangkan masa baharu.',
        'Untuk ketenangan anda: kami hanya akan bertanya tentang diri dan pengajian anda. Kami '
        'tidak sekali-kali akan meminta wang, kata laluan, atau OTP atau PIN. Jika sesiapa yang '
        'mendakwa mewakili Program ' + _PROG_MS + ' berbuat demikian, itu bukan kami.',
        'Salam hormat,<br>' + _TEAM_MS)

    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)
    return _send_html(to_email, subject, text_body, html_body)


def send_interview_reminder_email(to_email, *, student_name, start, meeting_url='', when='1day',
                                  english_only=False):
    """Student reminder (1 day / 1 hour before). HTML primary + plain-text fallback. Bilingual
    (EN+BM) by default; ``english_only=True`` drops the BM mirror. Best-effort."""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'
    whenfmt = _fmt_myt(start)
    soon_en = 'tomorrow' if when == '1day' else 'in about an hour'
    soon_bm = 'esok' if when == '1day' else 'dalam kira-kira sejam'

    # ── Plain-text fallback ───────────────────────────────────────────────────
    en_text = (
        f'Hi {en_name},\n\n'
        f'A reminder that your {_PROG_EN} Programme interview is {soon_en}:\n\n'
        f'• {whenfmt}\n'
        f'{_join_line(meeting_url, "en")}\n'
        f'Please be on camera and ready a few minutes early. See you soon.\n\n'
        f'Warm regards,\n' + _TEAM_EN
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'Peringatan bahawa temu duga Program {_PROG_MS} anda adalah {soon_bm}:\n\n'
        f'• {whenfmt}\n'
        f'{_join_line(meeting_url, "bm")}\n'
        f'Sila buka kamera dan bersedia beberapa minit lebih awal. Jumpa tidak lama lagi.\n\n'
        f'Salam hormat,\n' + _TEAM_MS
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML primary ──────────────────────────────────────────────────────────
    if meeting_url:
        join_en_html = _email_button(meeting_url, 'Join the video call')
        join_bm_html = _email_button(meeting_url, 'Sertai panggilan video')
    else:
        join_en_html = 'Your interviewer will share the video-call link before the interview.'
        join_bm_html = 'Penemu duga anda akan berkongsi pautan panggilan video sebelum temu duga.'

    def section(greeting, lead, join_html, footer, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 10px;">{lead}</p>'
            f'<p style="margin:0 0 6px;font-weight:600;">{whenfmt}</p>'
            f'<p style="margin:0 0 18px;">{join_html}</p>'
            f'<p style="margin:0 0 18px;">{footer}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = section(
        f'Hi {en_name},',
        f'A reminder that your {_PROG_EN} Programme interview is {soon_en}:',
        join_en_html,
        'Please be on camera and ready a few minutes early. See you soon.',
        'Warm regards,<br>' + _TEAM_EN)
    bm_html = section(
        f'Salam {bm_name},',
        f'Peringatan bahawa temu duga Program {_PROG_MS} anda adalah {soon_bm}:',
        join_bm_html,
        'Sila buka kamera dan bersedia beberapa minit lebih awal. Jumpa tidak lama lagi.',
        'Salam hormat,<br>' + _TEAM_MS)
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    subj = ('Reminder: your B40 interview is tomorrow' if when == '1day'
            else 'Reminder: your B40 interview is in 1 hour')
    return _send_html(to_email, subj, text_body, html_body)


def send_interview_cancelled_email(to_email, *, student_name, english_only=False):
    """Confirmation to the student that *they* cancelled their interview (this notice is sent
    on every cancel, and a student-initiated cancel is the common case). HTML primary +
    plain-text fallback. Bilingual (EN+BM) by default; ``english_only=True`` drops the BM
    mirror. Best-effort."""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'

    # ── Plain-text fallback (the owner-approved copy) ─────────────────────────
    en_text = (
        f'Hi {en_name},\n\n'
        f"This confirms that you've cancelled your interview for the {_PROG_EN} Programme, so "
        f'the time you had booked is now released.\n\n'
        f'Your application is still active — cancelling the interview doesn\'t affect it. Your '
        f"interviewer will propose some alternative times, and you're welcome to choose one "
        f"whenever you're ready, if you'd like to take this forward.\n\n"
        f"If you didn't mean to cancel, or you have any questions, just reply to this email and "
        f"we'll help you sort it out.\n\n"
        f'One note for your peace of mind: we\'ll only ever ask about you and your studies. We '
        f'will never ask you for money, a bank password, or an OTP or PIN. If anyone does, it\'s '
        f'not us — please tell us at {_P.email_support}.\n\n'
        f'Warm regards,\n' + _TEAM_EN
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'E-mel ini mengesahkan bahawa anda telah membatalkan temu duga Program ' + _PROG_MS + ' anda, '
        f'jadi masa yang anda tempah sebelum ini kini dilepaskan.\n\n'
        f'Permohonan anda masih aktif — membatalkan temu duga tidak menjejaskannya. Penemu duga '
        f'anda akan mencadangkan beberapa masa alternatif, dan anda dialu-alukan untuk memilih satu '
        f'bila-bila masa anda bersedia, jika anda ingin meneruskannya.\n\n'
        f'Jika anda tidak berniat untuk membatalkannya, atau anda mempunyai sebarang pertanyaan, '
        f'balas sahaja e-mel ini dan kami akan membantu anda.\n\n'
        f'Satu perkara untuk ketenangan fikiran anda: kami hanya akan bertanya tentang anda dan '
        f'pengajian anda. Kami tidak akan sekali-kali meminta wang, kata laluan bank, atau OTP atau '
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.\n\n'
        f'Salam hormat,\n' + _TEAM_MS
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    # ── HTML primary ──────────────────────────────────────────────────────────
    def section(greeting, p_confirm, p_active, p_reply, safety, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{p_confirm}</p>'
            f'<p style="margin:0 0 14px;">{p_active}</p>'
            f'<p style="margin:0 0 18px;">{p_reply}</p>'
            f'<p style="margin:0 0 18px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = section(
        f'Hi {en_name},',
        f"This confirms that you've cancelled your interview for the {_PROG_EN} Programme, so the "
        'time you had booked is now released.',
        "Your application is still active — cancelling the interview doesn’t affect it. Your interviewer "
        "will propose some alternative times, and you’re welcome to choose one whenever you’re ready, if "
        "you’d like to take this forward.",
        "If you didn’t mean to cancel, or you have any questions, just reply to this email and we’ll help "
        "you sort it out.",
        f'One note for your peace of mind: we’ll only ever ask about you and your studies. We will never '
        f'ask you for money, a bank password, or an OTP or PIN. If anyone does, it’s not us — please tell '
        f'us at {_P.email_support}.',
        'Warm regards,<br>' + _TEAM_EN)
    bm_html = section(
        f'Salam {bm_name},',
        'E-mel ini mengesahkan bahawa anda telah membatalkan temu duga Program ' + _PROG_MS + ' anda, jadi '
        'masa yang anda tempah sebelum ini kini dilepaskan.',
        'Permohonan anda masih aktif — membatalkan temu duga tidak menjejaskannya. Penemu duga anda akan '
        'mencadangkan beberapa masa alternatif, dan anda dialu-alukan untuk memilih satu bila-bila masa '
        'anda bersedia, jika anda ingin meneruskannya.',
        'Jika anda tidak berniat untuk membatalkannya, atau anda mempunyai sebarang pertanyaan, balas '
        'sahaja e-mel ini dan kami akan membantu anda.',
        f'Satu perkara untuk ketenangan fikiran anda: kami hanya akan bertanya tentang anda dan pengajian '
        f'anda. Kami tidak akan sekali-kali meminta wang, kata laluan bank, atau OTP atau PIN. Jika '
        f'sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.',
        'Salam hormat,<br>' + _TEAM_MS)
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, f"You've cancelled your {_PROG_EN} Programme interview",
                      text_body, html_body)


def send_interview_released_email(to_email, *, student_name, english_only=False):
    """Notice to the student when the interview is released because their INTERVIEWER
    changed (an admin unassigned the reviewer) — distinct from the student-initiated
    cancellation above (which says 'you cancelled'). Reassures them nothing is wrong and
    they need do nothing until a new interviewer proposes fresh times. HTML primary +
    plain-text fallback; bilingual (EN+BM) unless ``english_only``. Best-effort."""
    first = (student_name or '').strip().split(' ')[0]
    en_name = first or 'there'
    bm_name = first or 'di sana'

    en_text = (
        f'Hi {en_name},\n\n'
        f"There's been a change to who will be interviewing you for the {_PROG_EN} "
        f"Programme, so the interview time you'd booked has been released.\n\n"
        f"Your application is still active and this doesn't affect it. A new interviewer will "
        f"be assigned and will propose fresh times for you to choose from — there's nothing you "
        f"need to do right now.\n\n"
        f"If you have any questions, just reply to this email and we'll help.\n\n"
        f"One note for your peace of mind: we'll only ever ask about you and your studies. We "
        f"will never ask you for money, a bank password, or an OTP or PIN. If anyone does, it's "
        f"not us — please tell us at {_P.email_support}.\n\n"
        f'Warm regards,\n' + _TEAM_EN
    )
    bm_text = (
        f'Salam {bm_name},\n\n'
        f'Terdapat perubahan pada penemu duga yang akan menemu duga anda untuk Program {_PROG_MS}, '
        f'jadi masa temu duga yang anda tempah sebelum ini kini dilepaskan.\n\n'
        f'Permohonan anda masih aktif dan perkara ini tidak menjejaskannya. Seorang penemu duga '
        f'baharu akan ditugaskan dan akan mencadangkan masa baharu untuk anda pilih — tiada apa '
        f'yang perlu anda lakukan sekarang.\n\n'
        f'Jika anda mempunyai sebarang pertanyaan, balas sahaja e-mel ini dan kami akan membantu.\n\n'
        f'Satu perkara untuk ketenangan fikiran anda: kami hanya akan bertanya tentang anda dan '
        f'pengajian anda. Kami tidak akan sekali-kali meminta wang, kata laluan bank, atau OTP atau '
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.\n\n'
        f'Salam hormat,\n' + _TEAM_MS
    )
    text_body = en_text if english_only else f'{en_text}\n\n———\n\n{bm_text}'

    def section(greeting, p_confirm, p_active, p_reply, safety, signoff):
        return (
            f'<p style="margin:0 0 14px;">{greeting}</p>'
            f'<p style="margin:0 0 14px;">{p_confirm}</p>'
            f'<p style="margin:0 0 14px;">{p_active}</p>'
            f'<p style="margin:0 0 18px;">{p_reply}</p>'
            f'<p style="margin:0 0 18px;color:#6b7280;font-size:13px;">{safety}</p>'
            f'<p style="margin:0;">{signoff}</p>'
        )
    en_html = section(
        f'Hi {en_name},',
        f"There’s been a change to who will be interviewing you for the {_PROG_EN} "
        "Programme, so the interview time you’d booked has been released.",
        "Your application is still active and this doesn’t affect it. A new interviewer will be "
        "assigned and will propose fresh times for you to choose from — there’s nothing you need "
        "to do right now.",
        "If you have any questions, just reply to this email and we’ll help.",
        f'One note for your peace of mind: we’ll only ever ask about you and your studies. We will '
        f'never ask you for money, a bank password, or an OTP or PIN. If anyone does, it’s not us — '
        f'please tell us at {_P.email_support}.',
        'Warm regards,<br>' + _TEAM_EN)
    bm_html = section(
        f'Salam {bm_name},',
        f'Terdapat perubahan pada penemu duga yang akan menemu duga anda untuk Program {_PROG_MS}, '
        'jadi masa temu duga yang anda tempah sebelum ini kini dilepaskan.',
        'Permohonan anda masih aktif dan perkara ini tidak menjejaskannya. Seorang penemu duga '
        'baharu akan ditugaskan dan akan mencadangkan masa baharu untuk anda pilih — tiada apa yang '
        'perlu anda lakukan sekarang.',
        'Jika anda mempunyai sebarang pertanyaan, balas sahaja e-mel ini dan kami akan membantu.',
        f'Satu perkara untuk ketenangan fikiran anda: kami hanya akan bertanya tentang anda dan '
        f'pengajian anda. Kami tidak akan sekali-kali meminta wang, kata laluan bank, atau OTP atau '
        f'PIN. Jika sesiapa berbuat demikian, itu bukan kami — sila beritahu kami di {_P.email_support}.',
        'Salam hormat,<br>' + _TEAM_MS)
    html_body = _html_email_shell(en_html) if english_only else _html_email_shell(en_html, bm_html)

    return _send_html(to_email, 'Your ' + _PROG_EN + ' Programme interview time has been released',
                      text_body, html_body)
