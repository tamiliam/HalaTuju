"""The Vircle eWallet installation mail and the guide attachment it carries.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import os

from django.conf import settings
from .sending import _email_button, _html_email_shell, _send_html
from .shared import _DEFAULT_NAME, _P, logger
from .student_decisions import normalise_lang


# ── Vircle eWallet setup (VIRCLE_SETUP_ENABLED) ───────────────────────────────
# The follow-up to the award email (which said "nothing to do right now — look out for our
# next message"). This IS that message: the bursary is paid through the Vircle eWallet, so
# install it, then TELL US in the Action Centre. Owner decisions baked into this copy:
#   • The app calls the primary adult account a "Parent account" — say so plainly, or a
#     student reads it as the wrong option and stops. It is the correct account for them.
#   • Eligibility is by birth YEAR, not birthday: born 2008 or earlier.
#   • Two real-world blockers that strand people mid-setup, so they are WARNINGS not asides:
#     the ID check rejects a photo of a photo (physical MyKad only), and a very old phone can
#     fail activation even above the stated iOS 16 / Android 10 floor.
#   • The attached guide tells them to WhatsApp Vircle. We do NOT contradict the attachment —
#     they may, but it is optional; what we need is the Action-Centre confirmation, and we
#     relay to Vircle ourselves.
#   • Owner's edit (2026-07-12): ALL support routes to help@ — the email no longer points at
#     Vircle's WhatsApp line, so a student in trouble comes to US and we hear about it. (Their
#     own support number is still in the attached guide, and on the Action-Centre card.)

VIRCLE_INSTALL_SUBJECTS = {
    'en': 'Set up your Vircle eWallet to receive your {programme} 💳',
    'ms': 'Sediakan eWallet Vircle anda untuk menerima {programme} 💳',
    'ta': 'உங்கள் {programme}-ஐப் பெற Vircle eWallet-ஐ அமைக்கவும் 💳',
}
VIRCLE_INSTALL_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "We're ready to start paying your {programme}. Your money will reach you through "
        "Vircle, a Malaysian eWallet app — so the next step is to set up your Vircle account.\n\n"
        "Install the Vircle app from the Apple App Store, Google Play Store or Huawei AppGallery. "
        "You'll need iOS 16 or above, or Android 10 or above. Note that a very old phone can fail "
        "during registration even if it meets this — if it stalls, try again on a newer phone.\n\n"
        "When you sign up, the app asks you to register a Parent account. That is simply Vircle's "
        "name for the main adult account, and it is the correct one for you. You can register if "
        "you were born in 2008 or earlier. Have your MyKad in your hand before you start: the app "
        "photographs the actual card, so a picture of a photocopy, a scan, or an image on another "
        "screen will be rejected.\n\n"
        "If you were born after 2008, you cannot open your own Vircle account yet. Ask a parent or "
        "guardian to register their own Vircle account instead, then email us at {support} and "
        "we'll arrange for you to be added to it.\n\n"
        "The step-by-step guide is attached to this email.\n\n"
        "Once your account is active, please tell us in the Action Centre: enter the mobile "
        "number you registered with Vircle and confirm your account is active. We'll take it from "
        "there and arrange for your account to receive money monthly. (The attached guide asks "
        "you to message Vircle on WhatsApp — you may do so, but you don't have to. Telling us is "
        "what we need.)\n\n"
        "If you faced any trouble during registration or activation, reply to this email or "
        "contact us at {support}.\n\n"
        "Warm regards,\n{signoff}"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Kami sudah bersedia untuk mula membayar {programme} anda. Wang anda akan sampai "
        "melalui Vircle, sebuah aplikasi eWallet Malaysia — jadi langkah seterusnya ialah menyediakan "
        "akaun Vircle anda.\n\n"
        "Pasang aplikasi Vircle dari Apple App Store, Google Play Store atau Huawei AppGallery. Anda "
        "memerlukan iOS 16 ke atas, atau Android 10 ke atas. Perlu diingat, telefon yang terlalu lama "
        "boleh gagal semasa pendaftaran walaupun memenuhi syarat ini — jika ia tersekat, cuba semula "
        "dengan telefon yang lebih baharu.\n\n"
        "Semasa mendaftar, aplikasi akan meminta anda mendaftar Akaun Parent. Itu hanyalah nama Vircle "
        "bagi akaun dewasa utama, dan ia adalah akaun yang betul untuk anda. Anda boleh mendaftar jika "
        "anda lahir pada tahun 2008 atau lebih awal. Pastikan MyKad anda ada di tangan sebelum mula: "
        "aplikasi akan memotret kad sebenar, jadi gambar salinan fotostat, imbasan, atau imej pada "
        "skrin lain akan ditolak.\n\n"
        "Jika anda lahir selepas tahun 2008, anda belum boleh membuka akaun Vircle anda sendiri. "
        "Sebaliknya, minta ibu bapa atau penjaga anda mendaftar akaun Vircle mereka sendiri, "
        "kemudian e-mel kami di {support} dan kami akan uruskan supaya anda ditambah ke dalam "
        "akaun tersebut.\n\n"
        "Panduan langkah demi langkah disertakan bersama e-mel ini.\n\n"
        "Sebaik sahaja akaun anda aktif, sila beritahu kami di Pusat Tindakan: masukkan nombor "
        "telefon bimbit yang anda daftarkan dengan Vircle dan sahkan akaun anda aktif. "
        "Kami akan uruskan yang selebihnya dan memastikan akaun anda menerima wang "
        "setiap bulan. (Panduan yang disertakan meminta anda menghantar mesej WhatsApp kepada "
        "Vircle — anda boleh berbuat demikian, tetapi ia tidak wajib. Memberitahu kami sudah "
        "memadai.)\n\n"
        "Jika anda menghadapi sebarang masalah semasa pendaftaran atau pengaktifan, balas e-mel ini "
        "atau hubungi kami di {support}.\n\n"
        "Salam hormat,\n{signoff}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "உங்கள் {programme}-ஐ வழங்கத் தொடங்க நாங்கள் தயாராக உள்ளோம். உங்கள் பணம் Vircle என்ற "
        "மலேசிய eWallet செயலி வழியாக உங்களைச் சென்றடையும் — எனவே அடுத்த படி உங்கள் Vircle கணக்கை "
        "அமைப்பதாகும்.\n\n"
        "Apple App Store, Google Play Store அல்லது Huawei AppGallery-இலிருந்து Vircle செயலியை "
        "நிறுவவும். உங்களுக்கு iOS 16 அல்லது அதற்கு மேல், அல்லது Android 10 அல்லது அதற்கு மேல் தேவை. "
        "மிகவும் பழைய தொலைபேசி இதைப் பூர்த்தி செய்தாலும் பதிவின்போது தோல்வியடையலாம் — நின்றுவிட்டால், "
        "புதிய தொலைபேசியில் மீண்டும் முயற்சிக்கவும்.\n\n"
        "பதிவு செய்யும்போது, ஒரு Parent கணக்கைப் பதிவு செய்யுமாறு செயலி கேட்கும். அது Vircle நிறுவனம் "
        "முதன்மை வயதுவந்தோர் கணக்கிற்கு வைத்துள்ள பெயர் மட்டுமே; அதுவே உங்களுக்கான சரியான கணக்கு. "
        "நீங்கள் 2008 அல்லது அதற்கு முன் பிறந்திருந்தால் பதிவு செய்யலாம். தொடங்கும் முன் உங்கள் MyKad-ஐ "
        "கையில் வைத்திருங்கள்: செயலி உண்மையான அட்டையைப் புகைப்படம் எடுக்கிறது, எனவே நகல், ஸ்கேன், அல்லது "
        "மற்றொரு திரையில் உள்ள படத்தின் புகைப்படம் நிராகரிக்கப்படும்.\n\n"
        "நீங்கள் 2008-க்குப் பிறகு பிறந்திருந்தால், உங்கள் சொந்தக் கணக்கை இப்போது திறக்க முடியாது. "
        "அதற்குப் பதிலாக, உங்கள் பெற்றோர் அல்லது பாதுகாவலரை அவர்களின் சொந்த Vircle கணக்கைப் பதிவு "
        "செய்யச் சொல்லுங்கள்; பிறகு {support} இல் எங்களுக்கு மின்னஞ்சல் அனுப்புங்கள் — அந்தக் கணக்கில் "
        "உங்களைச் சேர்ப்பதற்கு நாங்கள் ஏற்பாடு செய்வோம்.\n\n"
        "படிப்படியான வழிகாட்டி இந்த மின்னஞ்சலுடன் இணைக்கப்பட்டுள்ளது.\n\n"
        "உங்கள் கணக்கு செயல்பட்டவுடன், Action Centre-இல் எங்களிடம் தெரிவியுங்கள்: Vircle-இல் நீங்கள் "
        "பதிவு செய்த கைபேசி எண்ணை உள்ளிட்டு, உங்கள் கணக்கு செயல்பாட்டில் உள்ளதை உறுதிப்படுத்தவும். "
        "மீதியை நாங்கள் கவனித்து, உங்கள் கணக்கு ஒவ்வொரு மாதமும் "
        "பணத்தைப் பெறுவதற்கு ஏற்பாடு செய்வோம். (இணைக்கப்பட்ட வழிகாட்டி Vircle-க்கு WhatsApp அனுப்பச் "
        "சொல்கிறது — நீங்கள் அனுப்பலாம், ஆனால் அது கட்டாயமில்லை. எங்களிடம் தெரிவிப்பதே எங்களுக்குத் "
        "தேவை.)\n\n"
        "பதிவு அல்லது செயல்படுத்தும் போது ஏதேனும் சிக்கல் ஏற்பட்டால், இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் "
        "அல்லது {support} இல் எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "அன்புடன்,\n{signoff}"
    ),
}

# Rendered BOLD in the HTML. Each MUST be an exact substring of its body above — a phrase that
# isn't found is silently left un-bolded (same contract as _BOLD_PHRASES).
_VIRCLE_BOLD_PHRASES = {
    'en': ['register a Parent account', 'born in 2008 or earlier',
           'photographs the actual card'],
    'ms': ['mendaftar Akaun Parent', 'lahir pada tahun 2008 atau lebih awal',
           'memotret kad sebenar'],
    'ta': ['Parent கணக்கைப் பதிவு செய்யுமாறு', '2008 அல்லது அதற்கு முன் பிறந்திருந்தால்',
           'உண்மையான அட்டையைப் புகைப்படம் எடுக்கிறது'],
}

# The Action Centre appears TWICE in the HTML, deliberately: as an inline link inside the sentence
# that asks for it, and again as a button under the sign-off. Both point at /scholarship/application.
# A student skim-reading finds the button; a student reading properly finds the link where the ask
# actually is. The plain-text fallback just reads the words, losing only the click.
_VIRCLE_LINK_PHRASES = {
    'en': 'the Action Centre',
    'ms': 'Pusat Tindakan',
    'ta': 'Action Centre-இல்',
}

VIRCLE_CTA_LABELS = {
    'en': 'Confirm in the Action Centre',
    'ms': 'Sahkan di Pusat Tindakan',
    'ta': 'Action Centre-இல் உறுதிப்படுத்தவும்',
}

# The installation guide, shipped as a repo asset (not PII → safe in git).
# ⚠ ONE DECLARED EDIT (code health H16): the asset lives at `apps/scholarship/assets/`, and this
# module sits one level deeper than the `emails.py` it came from — so the original single
# `dirname` now answers `apps/scholarship/emails/` and the attachment silently vanishes. The extra
# `dirname` keeps the path at exactly the file it always resolved to. A `__file__`-relative path
# is the same hazard as a `__name__` logger: a move changes it, and only a test that reads the
# real bytes notices. The email golden master caught this one.
_VIRCLE_GUIDE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'assets', 'vircle-installation-guide.pdf',
)
_VIRCLE_GUIDE_FILENAME = f'{_P.programme_name("en")} eWallet by Vircle - Installation Guide.pdf'


def vircle_guide_attachment():
    """The installation guide as a ``(filename, content, mimetype)`` triple, or None.

    Source of truth is the LIVE copy in the owner's Drive (``VIRCLE_GUIDE_FOLDER``) so an edit to
    the guide reflects in the next award email without a redeploy; the fetched bytes are cached
    briefly (``VIRCLE_GUIDE_CACHE_SECONDS``) so a batch send doesn't re-download per email. Falls
    back to the bundled repo asset when Drive is disabled/unreachable — a slightly-stale guide
    beats no guide, and no attachment still beats no email at all."""
    filename = getattr(settings, 'VIRCLE_GUIDE_FILENAME', '') or _VIRCLE_GUIDE_FILENAME
    content = _vircle_guide_bytes_from_drive() or _vircle_guide_bytes_from_asset()
    if content is None:
        return None
    return (filename, content, 'application/pdf')


def _vircle_guide_bytes_from_drive():
    """The live guide bytes from Drive, cached for ``VIRCLE_GUIDE_CACHE_SECONDS``. None when the
    folder is unset, Drive is disabled, or the fetch fails (all handled in ``sheets``)."""
    folder = getattr(settings, 'VIRCLE_GUIDE_FOLDER', '')
    if not folder:
        return None
    filename = getattr(settings, 'VIRCLE_GUIDE_FILENAME', '') or _VIRCLE_GUIDE_FILENAME
    ttl = int(getattr(settings, 'VIRCLE_GUIDE_CACHE_SECONDS', 0) or 0)
    # Hash the folder+filename into the key so it's cache-backend-safe (no spaces/slashes) and a
    # config change naturally lands on a fresh key instead of serving a stale cached copy.
    import hashlib
    digest = hashlib.sha1(f'{folder}\n{filename}'.encode('utf-8')).hexdigest()
    cache_key = f'vircle_guide_pdf:{digest}'
    if ttl > 0:
        from django.core.cache import cache
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    from .. import sheets
    content = sheets.fetch_drive_pdf(folder, filename)
    if content and ttl > 0:
        from django.core.cache import cache
        cache.set(cache_key, content, ttl)
    return content


def _vircle_guide_bytes_from_asset():
    """The bundled repo copy — the fallback when Drive is unavailable."""
    try:
        with open(_VIRCLE_GUIDE_PATH, 'rb') as fh:
            return fh.read()
    except OSError:
        logger.warning('Vircle installation guide missing at %s', _VIRCLE_GUIDE_PATH)
        return None


def _vircle_install_html(text_body, lang, branding=None):
    """HTML for the Vircle setup email: paragraphs, key phrases BOLD, the sign-off team name
    bolded, "the Action Centre" as an inline LINK where the ask is made, AND a call-to-action
    button under the sign-off. Both routes lead to /scholarship/application."""
    import html as _h
    frontend = (branding or _P).frontend_url
    link_phrase = _VIRCLE_LINK_PHRASES.get(lang, _VIRCLE_LINK_PHRASES['en'])
    phrases = _VIRCLE_BOLD_PHRASES.get(lang, [])

    def _emphasise(escaped):
        for ph in phrases:
            if ph:
                escaped = escaped.replace(_h.escape(ph), f'<strong>{_h.escape(ph)}</strong>')
        # Link the Action Centre in place. Bolded too — it is the one thing we're asking for.
        if link_phrase:
            esc_link = _h.escape(link_phrase)
            anchor = (f'<a href="{frontend}/scholarship/application" '
                      f'style="color:#2563eb;font-weight:600;">{esc_link}</a>')
            escaped = escaped.replace(esc_link, anchor, 1)
        return escaped

    paras = [p.strip() for p in (text_body or '').split('\n\n') if p.strip()]
    blocks = []
    for idx, para in enumerate(paras):
        esc = _emphasise(_h.escape(para))
        if idx == len(paras) - 1 and '\n' in para:   # final paragraph = the sign-off
            head, sep, team = esc.rpartition('\n')
            esc = f'{head}\n<strong>{team}</strong>' if sep else f'<strong>{esc}</strong>'
        blocks.append(f'<p style="margin:0 0 14px;">{esc.replace(chr(10), "<br>")}</p>')

    button = _email_button(f'{frontend}/scholarship/application',
                           VIRCLE_CTA_LABELS.get(lang, VIRCLE_CTA_LABELS['en']))
    blocks.append(f'<p style="margin:22px 0 6px;">{button}</p>')
    return _html_email_shell(''.join(blocks))


def send_vircle_install_email(to_email, applicant_name, lang='en', branding=None):
    """Vircle setup email: install the app, then confirm in the Action Centre. The installation
    guide PDF is attached. HTML (key phrases BOLD + one CTA button) + plain-text fallback, from
    info@, reply-to help@."""
    if not to_email:
        return False
    b = branding or _P
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    fmt = {'name': name, 'support': b.email_support,
           'programme': b.programme_name(lang), 'signoff': b.team_signoff(lang)}
    subject = VIRCLE_INSTALL_SUBJECTS[lang].format(**fmt)
    text_body = VIRCLE_INSTALL_BODIES[lang].format(**fmt)
    guide = vircle_guide_attachment()
    return _send_html(
        to_email, subject, text_body, _vircle_install_html(text_body, lang, b),
        from_email=b.email_from,
        reply_to=[b.email_support],
        attachments=[guide] if guide else None,
    )
