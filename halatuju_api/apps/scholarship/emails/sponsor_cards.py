"""Sponsor new-student and digest mail, and the student cards they are built from.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .sending import _email_button, _html_email_shell, _send_html
from .shared import _P
from .student_decisions import normalise_lang


# ── F3: sponsor notifications (real-time alert + weekly digest) ───────────────
# Reworked to branded mini-card emails (HTML + plain-text pair) carrying the pool-card
# DNA. The body is built ONLY from already-serialised SponsorPoolDetailSerializer dicts
# (an allowlist) + the public FieldTaxonomy display names/artwork (non-identifying), so it
# can never contain a student's identity by construction. n-aware subjects (no "student(s)")
# with a standout hook; a per-student "Read their story" link; the sponsor's name in the
# greeting when the caller has it. NO '—' placeholders and NO empty lines — a missing fact
# is simply omitted.
FIELD_IMAGE_BASE = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images'
# Bright flat-illustration alternative set (no people/faces/text), used for the email
# THUMBNAIL — a photo cropped to 56px reads poorly. Same slug filenames, separate public
# bucket. (The sponsor detail-page strip uses the same set via the web `conceptFieldImageUrl`.)
FIELD_IMAGE_CONCEPT_BASE = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images-concept'

SPONSOR_NEW_SUBJECTS = {
    'en': {'one': 'A new student is waiting for a sponsor',
           'many': '{n} new students are waiting for a sponsor'},
    'ms': {'one': 'Seorang pelajar baharu menunggu penaja',
           'many': '{n} pelajar baharu menunggu penaja'},
    'ta': {'one': 'ஒரு புதிய மாணவர் நிதியுதவியாளருக்காகக் காத்திருக்கிறார்',
           'many': '{n} புதிய மாணவர்கள் நிதியுதவியாளருக்காகக் காத்திருக்கிறார்கள்'},
}
SPONSOR_DIGEST_SUBJECTS = {
    'en': {'one': 'Your weekly update: a student is waiting for a sponsor',
           'many': 'Your weekly update: {n} students waiting for a sponsor'},
    'ms': {'one': 'Kemas kini mingguan: seorang pelajar menunggu penaja',
           'many': 'Kemas kini mingguan: {n} pelajar menunggu penaja'},
    'ta': {'one': 'வாராந்திர புதுப்பிப்பு: ஒரு மாணவர் நிதியுதவியாளருக்காகக் காத்திருக்கிறார்',
           'many': 'வாராந்திர புதுப்பிப்பு: {n} மாணவர்கள் நிதியுதவியாளருக்காகக் காத்திருக்கிறார்கள்'},
}
# Standout hook appended to the subject when the best-academic card also has a state.
_SPONSOR_HOOK = {
    'en': ' — including {acad} from {state}',
    'ms': ' — termasuk {acad} dari {state}',
    'ta': ' — {state} மாநிலத்தைச் சேர்ந்த {acad} உட்பட',
}
_SPONSOR_GREETING = {'en': 'Dear {name},', 'ms': 'Salam {name},', 'ta': 'அன்புள்ள {name},'}
_SPONSOR_GREETING_GENERIC = {'en': 'Dear Sponsor,', 'ms': 'Salam Penaja,', 'ta': 'அன்புள்ள நிதியுதவியாளரே,'}
_SPONSOR_NEW_INTRO = {
    'en': {'one': 'A student is now ready for a sponsor — a young person from a low-income family who has done well despite the odds:',
           'many': 'More students are now ready for a sponsor — young people from low-income families who have done well despite the odds:'},
    'ms': {'one': 'Seorang pelajar kini bersedia untuk penaja — anak muda daripada keluarga berpendapatan rendah yang berjaya walaupun mencabar:',
           'many': 'Beberapa pelajar kini bersedia untuk penaja — anak muda daripada keluarga berpendapatan rendah yang berjaya walaupun mencabar:'},
    'ta': {'one': 'ஒரு மாணவர் இப்போது நிதியுதவியாளருக்குத் தயாராக உள்ளார் — சவால்களுக்கு மத்தியிலும் சிறந்து விளங்கிய, குறைந்த வருமானக் குடும்பத்தைச் சேர்ந்த ஓர் இளையவர்:',
           'many': 'சில மாணவர்கள் இப்போது நிதியுதவியாளருக்குத் தயாராக உள்ளனர் — சவால்களுக்கு மத்தியிலும் சிறந்து விளங்கிய, குறைந்த வருமானக் குடும்பங்களைச் சேர்ந்த இளையவர்கள்:'},
}
_SPONSOR_DIGEST_INTRO = {
    'en': {'one': 'Here is a student who has done well despite the odds — from a low-income family, and waiting for a sponsor to help them go further:',
           'many': 'Here are students who have done well despite the odds — each from a low-income family, and waiting for a sponsor to help them go further:'},
    'ms': {'one': 'Berikut seorang pelajar yang berjaya walaupun mencabar — daripada keluarga berpendapatan rendah, dan menunggu penaja untuk melangkah lebih jauh:',
           'many': 'Berikut pelajar yang berjaya walaupun mencabar — masing-masing daripada keluarga berpendapatan rendah, dan menunggu penaja untuk melangkah lebih jauh:'},
    'ta': {'one': 'சவால்களுக்கு மத்தியிலும் சிறந்து விளங்கிய ஒரு மாணவர் இங்கே — குறைந்த வருமானக் குடும்பத்தைச் சேர்ந்தவர், மேலும் முன்னேற நிதியுதவியாளருக்காகக் காத்திருக்கிறார்:',
           'many': 'சவால்களுக்கு மத்தியிலும் சிறந்து விளங்கிய மாணவர்கள் இங்கே — ஒவ்வொருவரும் குறைந்த வருமானக் குடும்பத்தைச் சேர்ந்தவர்கள், மேலும் முன்னேற நிதியுதவியாளருக்காகக் காத்திருக்கின்றனர்:'},
}
_SPONSOR_CTA = {'en': 'See all students', 'ms': 'Lihat semua pelajar', 'ta': 'அனைத்து மாணவர்களையும் காண்க'}
_SPONSOR_READ_STORY = {'en': 'Read their story →', 'ms': 'Baca kisah mereka →', 'ta': 'அவர்களின் கதையைப் படிக்க →'}
_SPONSOR_REGISTERS = {'en': 'registers {date}', 'ms': 'mendaftar {date}', 'ta': '{date} அன்று பதிவு'}
_SPONSOR_FOOTER = {
    'en': "You're receiving this because your notifications are set to {freq}. You can change this any time in your {account}.",
    'ms': "Anda menerima ini kerana pemberitahuan anda ditetapkan kepada {freq}. Anda boleh menukarnya bila-bila masa dalam {account} anda.",
    'ta': "உங்கள் அறிவிப்புகள் {freq} என அமைக்கப்பட்டுள்ளதால் இதைப் பெறுகிறீர்கள். எப்போது வேண்டுமானாலும் உங்கள் {account} இல் இதை மாற்றலாம்.",
}
_SPONSOR_ACCOUNT = {'en': 'sponsor account', 'ms': 'akaun penaja', 'ta': 'நிதியுதவியாளர் கணக்கு'}
# The team sign-off (from the seam) with a per-language "regards," prefix. Sponsor mail is
# platform-branded (see _send_sponsor_notify) so it reads from _P.
_SPONSOR_SIGNOFF = {
    'en': f'Warm regards,\n{_P.team_signoff("en")}',
    'ms': f'Salam hormat,\n{_P.team_signoff("ms")}',
    'ta': f'அன்புடன்,\n{_P.team_signoff("ta")}',
}
_SPONSOR_FREQ_WORD = {
    'realtime': {'en': 'real-time', 'ms': 'masa nyata', 'ta': 'நிகழ்நேரம்'},
    'weekly': {'en': 'weekly', 'ms': 'mingguan', 'ta': 'வாராந்திரம்'},
}


def _field_image_url(slug):
    """Public field-artwork URL from a slug — '' (omit the <img>) when the slug is empty.
    Uses the concept (illustration) set, which crops cleanly at thumbnail size."""
    slug = (slug or '').strip()
    return f'{FIELD_IMAGE_CONCEPT_BASE}/{slug}.png' if slug else ''


def _tax_name_map():
    """{taxonomy_key: {en,ms,ta}} — for turning a raw field key into a display name.
    Non-identifying (catalogue names shared by hundreds of courses); one query per send."""
    from apps.courses.models import FieldTaxonomy
    return {k: {'en': en, 'ms': ms, 'ta': ta}
            for k, en, ms, ta in FieldTaxonomy.objects.values_list(
                'key', 'name_en', 'name_ms', 'name_ta')}


def _programme_of(card, lang, tax):
    """The bold programme line: the confirmed course name, else the field's taxonomy
    DISPLAY name — NEVER a raw field key, NEVER '—'. '' when nothing is known (line omitted)."""
    prog = (card.get('course') or '').strip()
    if prog:
        return (tax[prog][lang] or prog) if prog in tax else prog
    field = (card.get('field') or '').strip()
    if not field:
        return ''
    return (tax.get(field, {}).get(lang) or field)


def _registers_line(card, lang):
    """'registers DD/MM/YYYY' when the course-start date is today/future; else ''."""
    iso = card.get('reporting_date')
    if not iso:
        return ''
    from datetime import date
    from django.utils import timezone
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ''
    if d < timezone.localdate():
        return ''
    return _SPONSOR_REGISTERS[lang].format(date=d.strftime('%d/%m/%Y'))


def _rm_whole(v):
    """Whole-ringgit, thousands-grouped, no decimals — "2000.00" → "2,000" (mirrors the web
    card's rmWhole)."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v or '')
    return f'{int(round(n)):,}'


def _facts_bits(card, lang):
    """academic · RMamount · registers <date> — only the parts present (no '—')."""
    bits = []
    if (card.get('academic') or '').strip():
        bits.append(card['academic'].strip())
    amt = card.get('award_amount')
    if amt:
        bits.append(f'RM{_rm_whole(amt)}')          # RM2,000 (matches the web card)
    reg = _registers_line(card, lang)
    if reg:
        bits.append(reg)
    return bits


def _acad_score(academic):
    """A rough 'best academic' score for the subject hook, off pool.academic_band's format
    ('SPM · N As' / 'STPM · PNGK X.X'): the SPM A-count, or an STPM CGPA magnitude — whichever
    is larger. Subject flavour only, never load-bearing."""
    import re
    a = (academic or '').upper()
    counts = [int(m) for m in re.findall(r'(\d+)\s*A', a)]   # "7 As" / "9A" → 7 / 9
    score = float(max(counts)) if counts else float(a.count('A'))
    m = re.search(r'(\d\.\d+)', a)                            # STPM "PNGK 3.5" → 3.5
    if m:
        score = max(score, float(m.group(1)))
    return score


def _pick_standout(cards):
    best, best_score = None, -1.0
    for c in cards:
        s = _acad_score(c.get('academic', ''))
        if s > best_score:
            best, best_score = c, s
    return best


def _sponsor_subject(subjects, cards, lang, count=None):
    # ``count`` is the FULL number of students this email is about (the subject reflects the
    # whole batch even when the body is capped); the standout hook is drawn from the shown cards.
    n = count if count is not None else len(cards)
    subject = subjects[lang]['one' if n == 1 else 'many'].format(n=n)
    st = _pick_standout(cards)
    if st and (st.get('academic') or '').strip() and (st.get('state') or '').strip():
        subject += _SPONSOR_HOOK[lang].format(acad=st['academic'].strip(), state=st['state'].strip())
    return subject


def _sponsor_card_text(card, lang, frontend, tax):
    """Plain-text mini-card — mirrors the HTML content (never regresses below the old text)."""
    ref = card.get('ref', '')
    prog = _programme_of(card, lang, tax)
    lines = [ref]
    if prog:
        lines.append(prog)
    # Institution only — the home state next to it misleads (matches the web card).
    inst = (card.get('institution') or '').strip()
    if inst:
        lines.append(inst)
    facts = _facts_bits(card, lang)
    if facts:
        lines.append(' · '.join(facts))
    blurb = (card.get('blurb') or '').strip()
    if blurb:
        lines.append(f'"{blurb}"')
    lines.append(f'{_SPONSOR_READ_STORY[lang]} {frontend}/sponsor/students/{card.get("id", "")}')
    return '\n'.join(lines)


def _sponsor_card_html(card, lang, frontend, tax):
    """One email-safe mini-card (table markup, shell-consistent). Thumbnail omitted when
    the field artwork slug is empty; every fact line is dropped when absent (no '—')."""
    import html as _h
    ref = _h.escape(card.get('ref', ''))
    prog = _h.escape(_programme_of(card, lang, tax))
    loc = _h.escape((card.get('institution') or '').strip())   # institution only (no state)
    facts = _h.escape(' · '.join(_facts_bits(card, lang)))
    blurb = (card.get('blurb') or '').strip()
    url = f'{frontend}/sponsor/students/{card.get("id", "")}'
    img = _field_image_url(card.get('field_image_slug', ''))
    thumb = (f'<td width="64" valign="top" style="padding-right:12px;">'
             f'<img src="{img}" width="56" height="56" alt="{prog or "Field"}" '
             f'style="width:56px;height:56px;border-radius:8px;object-fit:cover;display:block;"></td>') if img else ''
    prog_html = f'<div style="margin:6px 0 0;font-weight:700;color:#111827;">{prog}</div>' if prog else ''
    loc_html = f'<div style="color:#6b7280;font-size:13px;">{loc}</div>' if loc else ''
    facts_html = f'<div style="margin-top:4px;font-size:13px;color:#374151;">{facts}</div>' if facts else ''
    blurb_html = (f'<div style="margin:6px 0 0;color:#4b5563;font-style:italic;">{_h.escape(blurb)}</div>'
                  if blurb else '')
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;'
        'border-radius:12px;margin:0 0 12px;"><tr><td style="padding:14px;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'{thumb}<td valign="top">'
        f'<div style="display:inline-block;background:#eef2ff;color:#3730a3;font-size:11px;'
        f'font-weight:700;padding:2px 8px;border-radius:999px;">{ref}</div>'
        f'{prog_html}{loc_html}{facts_html}{blurb_html}'
        f'<div style="margin-top:8px;"><a href="{url}" style="color:#2563eb;text-decoration:none;'
        f'font-weight:600;font-size:13px;">{_SPONSOR_READ_STORY[lang]}</a></div>'
        '</td></tr></table></td></tr></table>'
    )


def _sponsor_email_max_cards(organisation=None):
    """A notification email shows at most this many students (a teaser — the 'See all
    students' button leads to the full pool). Organisation-tunable since Org Config Sprint B
    (`sponsor_email_max_cards`; the registry default reads `SPONSOR_EMAIL_MAX_CARDS`, 5 —
    owner 2026-07-18). None (or a mixed-organisation batch) = platform default."""
    from apps.courses import org_config
    return org_config.value(organisation, 'sponsor_email_max_cards')


def _send_sponsor_notify(to_email, subjects, cards, freq, lang, intro_map, name='',
                         organisation=None):
    if not to_email or not cards:
        return False
    import html as _h
    lang = normalise_lang(lang)
    frontend = _P.frontend_url
    freq_word = _SPONSOR_FREQ_WORD.get(freq, {}).get(lang, freq)
    tax = _tax_name_map()
    all_cards = list(cards)
    full_n = len(all_cards)                            # the whole batch — drives the subject/intro count
    cards = all_cards[:_sponsor_email_max_cards(organisation)]  # cap the BODY; the button shows the rest
    greeting = (_SPONSOR_GREETING[lang].format(name=name.strip())
                if (name or '').strip() else _SPONSOR_GREETING_GENERIC[lang])
    intro = intro_map[lang]['one' if full_n == 1 else 'many']
    subject = _sponsor_subject(subjects, cards, lang, count=full_n)
    signoff = _SPONSOR_SIGNOFF[lang]
    cta_url = f'{frontend}/sponsor/students'          # the pool itself, not the portal landing
    account_url = f'{frontend}/sponsor/account'

    # Footer: 'sponsor account' is a link in HTML, a bare URL in plain text.
    account = _SPONSOR_ACCOUNT[lang]
    footer_text = _SPONSOR_FOOTER[lang].format(freq=freq_word, account=f'{account} ({account_url})')
    footer_html = _h.escape(_SPONSOR_FOOTER[lang]).format(
        freq=_h.escape(freq_word),
        account=f'<a href="{account_url}" style="color:#2563eb;">{_h.escape(account)}</a>')

    text_cards = '\n\n'.join(_sponsor_card_text(c, lang, frontend, tax) for c in cards)
    text_body = (f'{greeting}\n\n{intro}\n\n{text_cards}\n\n'
                 f'{_SPONSOR_CTA[lang]}: {cta_url}\n\n{footer_text}\n\n{signoff}')

    html_cards = ''.join(_sponsor_card_html(c, lang, frontend, tax) for c in cards)
    html_body = _html_email_shell(
        f'<p style="margin:0 0 12px;">{_h.escape(greeting)}</p>'
        f'<p style="margin:0 0 16px;">{_h.escape(intro)}</p>'
        + html_cards +
        f'<p style="margin:18px 0 0;">{_email_button(cta_url, _SPONSOR_CTA[lang])}</p>'
        f'<p style="margin:18px 0 0;color:#6b7280;font-size:12px;">{footer_html}</p>'
        f'<p style="margin:12px 0 0;color:#6b7280;font-size:12px;">'
        f'{_h.escape(signoff).replace(chr(10), "<br>")}</p>'
    )
    return _send_html(
        to_email, subject, text_body, html_body,
        from_email=_P.email_from,
        reply_to=[_P.sponsor_reply_to],
    )


def send_sponsor_new_student_email(to_email, cards, lang='en', name='', organisation=None):
    """F3 real-time: alert a sponsor that newly-published student(s) are waiting.
    ``cards`` = a list of SponsorPoolDetailSerializer dicts (allowlist-safe).
    ``organisation`` = the batch's sole organisation (picks its card cap), else None."""
    return _send_sponsor_notify(to_email, SPONSOR_NEW_SUBJECTS, cards, 'realtime', lang,
                                _SPONSOR_NEW_INTRO, name=name, organisation=organisation)


def send_sponsor_digest_email(to_email, cards, lang='en', name='', organisation=None):
    """F3 weekly: a digest of students published since the sponsor's last digest.
    ``cards`` = a list of SponsorPoolDetailSerializer dicts (allowlist-safe).
    ``organisation`` = the batch's sole organisation (picks its card cap), else None."""
    return _send_sponsor_notify(to_email, SPONSOR_DIGEST_SUBJECTS, cards, 'weekly', lang,
                                _SPONSOR_DIGEST_INTRO, name=name, organisation=organisation)
