"""The award offer and the offer-signing mail, with their bold-phrase HTML dressing.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .sending import _email_button, _html_email_shell, _send_html
from .shared import _DEFAULT_NAME, _P
from .student_decisions import normalise_lang
from .vircle_install import VIRCLE_CTA_LABELS, _VIRCLE_LINK_PHRASES, vircle_guide_attachment


# Sent when a student is AWARDED (a sponsor committed → status 'awarded'), BEFORE the formal
# offer/acceptance.
#
# MERGED 2026-07-12 (owner): this now carries the GOOD NEWS **and** the Vircle setup in ONE email.
# It used to end "there's nothing you need to do right now — look out for our next message", and a
# second email followed with the Vircle instructions. That seam is gone: a student awarded from now
# on is told the news and the one thing to do, in the same breath. (The standalone Vircle email is
# KEPT — the 22 students already awarded got the old good-news email, and it's still the tool for a
# re-send or a manual case.)
#
# UNCHANGED and deliberate: NO amount (the formal offer carries the figure), NO sponsor identity
# (two-way anonymity), NO bank-details ask (money moves through Vircle now). The formal offer +
# bursary contract still follow as their own step — the contract is being finalised.
# From info@, reply-to help@. Guide PDF attached. Good-news wording owner-cleared 2026-06-30.
AWARD_OFFER_SUBJECTS = {
    'en': 'Good news about your {programme} application 🎓',
    'ms': 'Berita baik tentang permohonan {programme} anda 🎓',
    'ta': 'உங்கள் {programme} விண்ணப்பம் பற்றிய நல்ல செய்தி 🎓',
}
AWARD_OFFER_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "We're delighted to share some good news. Your application to the {programme} "
        "Programme has been successful — you have been selected to receive financial support for "
        "your studies.\n\n"
        "Your support is paid monthly through Vircle, a Malaysian eWallet app. There are TWO "
        "steps to start receiving it, and your payments can only begin once BOTH are done.\n\n"
        "STEP 1 — Install Vircle and activate your account.\n"
        "Install the Vircle app from the Apple App Store, Google Play Store or Huawei AppGallery "
        "(you'll need iOS 16 or above, or Android 10 or above — a very old phone can fail during "
        "registration even if it meets this; if it stalls, try again on a newer phone). When you "
        "sign up, the app asks you to register a Parent account: that is simply Vircle's name for "
        "the main adult account, and it is the correct one for you. Have your MyKad in your hand "
        "before you start — the app photographs the actual card, so a photocopy, a scan, or an "
        "image on another screen will be rejected. The step-by-step guide is attached to this "
        "email.\n\n"
        "{guardian_note}"
        "STEP 2 — Tell us in the Action Centre.\n"
        "Once your account is active, sign in at {domain} and open your application page. In "
        "the Action Centre, enter the mobile number you registered with Vircle and confirm your "
        "account is active.\n\n"
        "Step 2 is not optional: we can only arrange your monthly payments after you have "
        "confirmed. (The attached guide may ask you to message Vircle on WhatsApp — you may, "
        "but confirming in the Action Centre is what starts your payments.)\n\n"
        "A formal offer and bursary contract will follow separately, along with the simple steps to "
        "accept it.\n\n"
        "If you faced any trouble during registration or activation, or have any questions, reply "
        "to this email or contact us at {support}.\n\n"
        "Warm congratulations,\n{signoff}"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Kami gembira berkongsi berita baik. Permohonan anda ke Program {programme} telah "
        "berjaya — anda telah dipilih untuk menerima bantuan kewangan bagi pengajian anda.\n\n"
        "Bantuan anda dibayar setiap bulan melalui Vircle, sebuah aplikasi eWallet Malaysia. "
        "Terdapat DUA langkah untuk mula menerimanya, dan pembayaran hanya boleh bermula setelah "
        "KEDUA-DUA langkah selesai.\n\n"
        "LANGKAH 1 — Pasang Vircle dan aktifkan akaun anda.\n"
        "Pasang aplikasi Vircle dari Apple App Store, Google Play Store atau Huawei AppGallery "
        "(anda memerlukan iOS 16 ke atas, atau Android 10 ke atas — telefon yang terlalu lama "
        "boleh gagal semasa pendaftaran walaupun memenuhi syarat ini; jika ia tersekat, cuba "
        "semula dengan telefon yang lebih baharu). Semasa mendaftar, aplikasi akan meminta anda "
        "mendaftar Akaun Parent: itu hanyalah nama Vircle bagi akaun dewasa utama, dan ia adalah "
        "akaun yang betul untuk anda. Pastikan MyKad anda ada di tangan sebelum mula — aplikasi "
        "akan memotret kad sebenar, jadi gambar salinan fotostat, imbasan, atau imej pada skrin "
        "lain akan ditolak. Panduan langkah demi langkah disertakan bersama e-mel ini.\n\n"
        "{guardian_note}"
        "LANGKAH 2 — Beritahu kami di Pusat Tindakan.\n"
        "Sebaik sahaja akaun anda aktif, log masuk di {domain} dan buka halaman permohonan "
        "anda. Di Pusat Tindakan, masukkan nombor telefon bimbit yang anda daftarkan dengan "
        "Vircle dan sahkan akaun anda aktif.\n\n"
        "Langkah 2 bukan pilihan: kami hanya dapat mengaturkan pembayaran bulanan anda selepas "
        "anda membuat pengesahan. (Panduan yang disertakan mungkin meminta anda menghantar "
        "mesej WhatsApp kepada Vircle — anda boleh berbuat demikian, tetapi pengesahan di "
        "Pusat Tindakan itulah yang memulakan pembayaran anda.)\n\n"
        "Tawaran rasmi dan kontrak biasiswa akan menyusul secara berasingan, berserta langkah mudah "
        "untuk menerimanya.\n\n"
        "Jika anda menghadapi sebarang masalah semasa pendaftaran atau pengaktifan, atau ada "
        "pertanyaan, balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Tahniah,\n{signoff}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "ஒரு நல்ல செய்தியைப் பகிர்வதில் மகிழ்ச்சி அடைகிறோம். {programme} திட்டத்திற்கான உங்கள் "
        "விண்ணப்பம் வெற்றிபெற்றுள்ளது — உங்கள் படிப்பிற்கான நிதியுதவியைப் பெற நீங்கள் தேர்ந்தெடுக்கப்பட்டுள்ளீர்கள்.\n\n"
        "உங்கள் உதவி Vircle என்ற மலேசிய eWallet செயலி வழியாக மாதந்தோறும் வழங்கப்படும். அதைப் பெறத் "
        "தொடங்க இரண்டு படிகள் உள்ளன; இரண்டையும் முடித்த பிறகே கட்டணங்கள் தொடங்க முடியும்.\n\n"
        "படி 1 — Vircle-ஐ நிறுவி உங்கள் கணக்கைச் செயல்படுத்துங்கள்.\n"
        "Apple App Store, Google Play Store அல்லது Huawei AppGallery-இலிருந்து Vircle செயலியை "
        "நிறுவவும் (iOS 16 அல்லது அதற்கு மேல், அல்லது Android 10 அல்லது அதற்கு மேல் தேவை — மிகவும் "
        "பழைய தொலைபேசி இதைப் பூர்த்தி செய்தாலும் பதிவின்போது தோல்வியடையலாம்; நின்றுவிட்டால், புதிய "
        "தொலைபேசியில் மீண்டும் முயற்சிக்கவும்). பதிவு செய்யும்போது, ஒரு Parent கணக்கைப் பதிவு செய்யுமாறு "
        "செயலி கேட்கும்: அது Vircle நிறுவனம் முதன்மை வயதுவந்தோர் கணக்கிற்கு வைத்துள்ள பெயர் மட்டுமே; "
        "அதுவே உங்களுக்கான சரியான கணக்கு. தொடங்கும் முன் உங்கள் MyKad-ஐ கையில் வைத்திருங்கள் — செயலி "
        "உண்மையான அட்டையைப் புகைப்படம் எடுக்கிறது; நகல், ஸ்கேன், அல்லது மற்றொரு திரையில் உள்ள படம் "
        "நிராகரிக்கப்படும். படிப்படியான வழிகாட்டி இந்த மின்னஞ்சலுடன் இணைக்கப்பட்டுள்ளது.\n\n"
        "{guardian_note}"
        "படி 2 — Action Centre-இல் எங்களிடம் தெரிவியுங்கள்.\n"
        "உங்கள் கணக்கு செயல்பட்டவுடன், {domain}-இல் உள்நுழைந்து உங்கள் விண்ணப்பப் பக்கத்தைத் "
        "திறக்கவும். Action Centre-இல், Vircle-இல் நீங்கள் பதிவு செய்த கைபேசி எண்ணை உள்ளிட்டு, "
        "உங்கள் கணக்கு செயல்பாட்டில் உள்ளதை உறுதிப்படுத்தவும்.\n\n"
        "படி 2 விருப்பத்தேர்வு அல்ல: நீங்கள் உறுதிப்படுத்திய பிறகே உங்கள் மாதாந்திரக் கட்டணங்களை "
        "நாங்கள் ஏற்பாடு செய்ய முடியும். (இணைக்கப்பட்ட வழிகாட்டி Vircle-க்கு WhatsApp அனுப்பச் "
        "சொல்லலாம் — நீங்கள் அனுப்பலாம்; ஆனால் Action Centre-இல் உறுதிப்படுத்துவதே உங்கள் "
        "கட்டணங்களைத் தொடங்கும்.)\n\n"
        "முறையான வழங்கல் (offer) மற்றும் உதவித்தொகை ஒப்பந்தம் (bursary contract), அதை ஏற்கும் எளிய "
        "படிகளுடன், தனியாக அனுப்பப்படும்.\n\n"
        "பதிவு அல்லது செயல்படுத்தும் போது ஏதேனும் சிக்கல் ஏற்பட்டால், அல்லது ஏதேனும் கேள்விகள் இருந்தால், "
        "இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் எங்களைத் தொடர்புகொள்ளவும்.\n\n"
        "இதயப்பூர்வ வாழ்த்துகள்,\n{signoff}"
    ),
}

# The parent/guardian route (owner 2026-07-17): shown ONLY to a student born after 2008
# (``not vircle.can_register(app)``) — everyone else never sees it. {support} is pre-formatted
# by the sender before insertion.
AWARD_OFFER_GUARDIAN_NOTES = {
    'en': (
        "If you were born after 2008, you cannot open your own Vircle account yet. Ask a parent "
        "or guardian to register their own Vircle account instead, then email us at {support} "
        "and we'll arrange for you to be added to it."
    ),
    'ms': (
        "Jika anda lahir selepas tahun 2008, anda belum boleh membuka akaun Vircle anda sendiri. "
        "Sebaliknya, minta ibu bapa atau penjaga anda mendaftar akaun Vircle mereka sendiri, "
        "kemudian e-mel kami di {support} dan kami akan uruskan supaya anda ditambah ke dalam "
        "akaun tersebut."
    ),
    'ta': (
        "நீங்கள் 2008-க்குப் பிறகு பிறந்திருந்தால், உங்கள் சொந்த Vircle கணக்கை இப்போது திறக்க முடியாது. "
        "அதற்குப் பதிலாக, உங்கள் பெற்றோர் அல்லது பாதுகாவலரை அவர்களின் சொந்த Vircle கணக்கைப் பதிவு "
        "செய்யச் சொல்லுங்கள்; பிறகு {support} இல் எங்களுக்கு மின்னஞ்சல் அனுப்புங்கள் — அந்தக் கணக்கில் "
        "உங்களைச் சேர்ப்பதற்கு நாங்கள் ஏற்பாடு செய்வோம்."
    ),
}


# The key phrases rendered BOLD in the HTML, per language. Each must be an exact substring of the
# body above — a phrase that isn't found is silently left un-bolded. Since the merge these cover
# BOTH halves: how support is paid, and the Vircle facts a student must not miss (the "Parent"
# account, the birth-year rule, the physical-MyKad rule) plus the contract still to come.
_BOLD_PHRASES = {
    'en': ['TWO steps', 'STEP 1 — Install Vircle and activate your account.',
           'STEP 2 — Tell us in the Action Centre.', 'register a Parent account',
           'photographs the actual card', 'Step 2 is not optional',
           'formal offer and bursary contract'],
    'ms': ['DUA langkah', 'LANGKAH 1 — Pasang Vircle dan aktifkan akaun anda.',
           'LANGKAH 2 — Beritahu kami di Pusat Tindakan.', 'mendaftar Akaun Parent',
           'memotret kad sebenar', 'Langkah 2 bukan pilihan',
           'Tawaran rasmi dan kontrak biasiswa'],
    'ta': ['இரண்டு படிகள்', 'படி 1 — Vircle-ஐ நிறுவி உங்கள் கணக்கைச் செயல்படுத்துங்கள்.',
           'படி 2 — Action Centre-இல் எங்களிடம் தெரிவியுங்கள்.', 'Parent கணக்கைப் பதிவு செய்யுமாறு',
           'உண்மையான அட்டையைப் புகைப்படம் எடுக்கிறது',
           'படி 2 விருப்பத்தேர்வு அல்ல'],
}


def _award_offer_html(text_body, lang, branding=None):
    """HTML for the award email: paragraphs, key phrases BOLD, the sign-off team name bolded,
    "the Action Centre" as an inline LINK where the ask is made, and a call-to-action button under
    the sign-off. Since the merge this email DOES ask something of the student (set up Vircle), so
    it carries both routes to /scholarship/application. Falls back gracefully: a phrase that isn't
    found is left un-bolded/un-linked."""
    import html as _h
    frontend = (branding or _P).frontend_url
    link_phrase = _VIRCLE_LINK_PHRASES.get(lang, _VIRCLE_LINK_PHRASES['en'])
    phrases = _BOLD_PHRASES.get(lang, [])

    def _emphasise(escaped):
        for ph in phrases:
            if ph:
                escaped = escaped.replace(_h.escape(ph), f'<strong>{_h.escape(ph)}</strong>')
        if link_phrase:
            esc_link = _h.escape(link_phrase)
            anchor = (f'<a href="{frontend}/scholarship/application" '
                      f'style="color:#2563eb;font-weight:600;">{esc_link}</a>')
            escaped = escaped.replace(esc_link, anchor, 1)
        return escaped

    def _bold_team(escaped):
        # Bold the team-name line (after the salutation) of the sign-off paragraph.
        head, sep, team = escaped.rpartition('\n')
        return f'{head}\n<strong>{team}</strong>' if sep else f'<strong>{escaped}</strong>'

    paras = [p.strip() for p in (text_body or '').split('\n\n') if p.strip()]
    blocks = []
    for idx, para in enumerate(paras):
        esc = _emphasise(_h.escape(para))
        if idx == len(paras) - 1 and '\n' in para:   # final paragraph = the sign-off
            esc = _bold_team(esc)
        blocks.append(f'<p style="margin:0 0 14px;">{esc.replace(chr(10), "<br>")}</p>')

    button = _email_button(f'{frontend}/scholarship/application',
                           VIRCLE_CTA_LABELS.get(lang, VIRCLE_CTA_LABELS['en']))
    blocks.append(f'<p style="margin:22px 0 6px;">{button}</p>')
    return _html_email_shell(''.join(blocks))


def send_award_offer_email(to_email, applicant_name, lang='en', guardian_note=False, branding=None):
    """Award email: a sponsor has committed (status 'awarded'). Since the 2026-07-12 merge this is
    ONE email carrying the good news AND the Vircle setup, restructured 2026-07-17 (owner) as TWO
    explicit steps — STEP 1 install/activate, STEP 2 confirm in the Action Centre (students were
    skipping step 2). The installation guide is attached. The formal offer + bursary contract still
    follow separately. NO amount, NO sponsor identity, NO bank-details ask. HTML (key phrases BOLD,
    inline Action-Centre link + CTA button) + plain-text fallback, from info@, reply-to help@.

    ``guardian_note=True`` (a student born after 2008, ``not vircle.can_register(app)``) inserts
    the parent/guardian-account paragraph after step 1; everyone else never sees it.

    The CALLER raises the Action-Centre task on a successful send (see sponsorship.py) — the task
    must never appear for a student who didn't get the email."""
    if not to_email:
        return False
    b = branding or _P
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    note = (AWARD_OFFER_GUARDIAN_NOTES[lang].format(support=b.email_support) + '\n\n'
            if guardian_note else '')
    fmt = {'name': name, 'support': b.email_support, 'guardian_note': note,
           'programme': b.programme_name(lang), 'signoff': b.team_signoff(lang),
           'domain': b.frontend_domain}
    subject = AWARD_OFFER_SUBJECTS[lang].format(**fmt)
    text_body = AWARD_OFFER_BODIES[lang].format(**fmt)
    guide = vircle_guide_attachment()
    return _send_html(
        to_email, subject, text_body, _award_offer_html(text_body, lang, b),
        from_email=b.email_from,
        reply_to=[b.email_support],
        attachments=[guide] if guide else None,
    )


# ── Award email, CONTRACT-MODE variant (BURSARY_AGREEMENT_ENABLED) ────────────
# The go-live transition (2026-07-19) splits the award email in two. When the bursary
# agreement flag is ON, the good-news email's next step is to REVIEW AND SIGN the
# agreement — NOT to set up Vircle. Vircle setup now follows automatically once the
# agreement is fully executed (bursary.distribute_executed_agreement). So this variant
# carries NO Vircle content and NO guide attachment, and its caller raises NO setup task.
# Still: NO amount, NO sponsor identity. First-draft trilingual copy — owner to review.
AWARD_OFFER_SIGN_SUBJECTS = {
    'en': 'Good news about your {programme} application 🎓',
    'ms': 'Berita baik tentang permohonan {programme} anda 🎓',
    'ta': 'உங்கள் {programme} விண்ணப்பம் பற்றிய நல்ல செய்தி 🎓',
}
AWARD_OFFER_SIGN_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "We're delighted to share some good news. Your application to the {programme} "
        "Programme has been successful — you have been selected to receive financial support for "
        "your studies.\n\n"
        "The next step is to review and sign your bursary agreement. Please log in and open your "
        "application page, where you'll first go through a short, friendly check to make sure the "
        "terms are clear, and then sign the agreement together with your parent or guardian — all "
        "on the same device.\n{link}\n\n"
        "Please have your parent or guardian with you when you sign: they sign as your guarantor, "
        "and we'll send a one-time PIN to their phone to confirm it's them.\n\n"
        "Once everything is signed, we'll be in touch with the simple steps to start receiving your "
        "monthly support.\n\n"
        "If you have any questions, reply to this email or contact us at {support}.\n\n"
        "Warm congratulations,\n{signoff}"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Kami gembira berkongsi berita baik. Permohonan anda ke Program {programme} telah "
        "berjaya — anda telah dipilih untuk menerima bantuan kewangan bagi pengajian anda.\n\n"
        "Langkah seterusnya ialah menyemak dan menandatangani perjanjian biasiswa anda. Sila log "
        "masuk dan buka halaman permohonan anda. Anda akan melalui semakan ringkas dan mesra "
        "dahulu untuk memastikan terma jelas, kemudian menandatangani perjanjian bersama ibu bapa "
        "atau penjaga anda — semuanya pada peranti yang sama.\n{link}\n\n"
        "Sila pastikan ibu bapa atau penjaga anda bersama anda semasa menandatangani: mereka "
        "menandatangani sebagai penjamin anda, dan kami akan menghantar PIN sekali guna ke telefon "
        "mereka untuk mengesahkannya.\n\n"
        "Setelah semuanya ditandatangani, kami akan menghubungi anda dengan langkah mudah untuk "
        "mula menerima bantuan bulanan anda.\n\n"
        "Jika ada sebarang pertanyaan, balas e-mel ini atau hubungi kami di {support}.\n\n"
        "Tahniah,\n{signoff}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "ஒரு நல்ல செய்தியைப் பகிர்வதில் மகிழ்ச்சி அடைகிறோம். {programme} திட்டத்திற்கான உங்கள் "
        "விண்ணப்பம் வெற்றிபெற்றுள்ளது — உங்கள் படிப்பிற்கான நிதியுதவியைப் பெற நீங்கள் தேர்ந்தெடுக்கப்பட்டுள்ளீர்கள்.\n\n"
        "அடுத்த படி, உங்கள் உதவித்தொகை ஒப்பந்தத்தை மதிப்பாய்வு செய்து கையொப்பமிடுவதாகும். உள்நுழைந்து உங்கள் "
        "விண்ணப்பப் பக்கத்தைத் திறக்கவும். முதலில் விதிமுறைகள் தெளிவாக இருப்பதை உறுதிசெய்ய ஒரு சிறிய, நட்பான "
        "சரிபார்ப்பின் வழியாகச் செல்வீர்கள், பின்னர் உங்கள் பெற்றோர் அல்லது பாதுகாவலருடன் சேர்ந்து — ஒரே சாதனத்தில் — "
        "ஒப்பந்தத்தில் கையொப்பமிடுவீர்கள்.\n{link}\n\n"
        "கையொப்பமிடும்போது உங்கள் பெற்றோர் அல்லது பாதுகாவலர் உங்களுடன் இருப்பதை உறுதிசெய்யவும்: அவர்கள் உங்கள் "
        "பிணையாளராகக் கையொப்பமிடுகிறார்கள், அவர்கள்தான் என்பதை உறுதிப்படுத்த அவர்களின் தொலைபேசிக்கு ஒரு முறை "
        "PIN அனுப்புவோம்.\n\n"
        "எல்லாம் கையொப்பமிடப்பட்ட பிறகு, உங்கள் மாதாந்திர உதவியைப் பெறத் தொடங்குவதற்கான எளிய படிகளுடன் உங்களைத் "
        "தொடர்புகொள்வோம்.\n\n"
        "ஏதேனும் கேள்விகள் இருந்தால், இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் எங்களைத் "
        "தொடர்புகொள்ளவும்.\n\n"
        "இதயப்பூர்வ வாழ்த்துகள்,\n{signoff}"
    ),
}


def send_award_offer_sign_email(to_email, applicant_name, lang='en', branding=None):
    """Contract-mode (BURSARY_AGREEMENT_ENABLED) award email: the same good news, but the
    next step is to REVIEW AND SIGN the bursary agreement — NOT Vircle setup (which now
    follows at agreement execution). Points to /scholarship/award. NO amount, NO sponsor
    identity, NO Vircle content or guide. Best-effort; from info@, reply-to help@.

    The CALLER (release_award_offer_emails, flag-ON branch) does NOT raise a Vircle setup
    task on this path — the task is raised at execution instead."""
    if not to_email:
        return False
    b = branding or _P
    lang = normalise_lang(lang)
    name = applicant_name or _DEFAULT_NAME[lang]
    frontend = b.frontend_url
    link = f'{frontend}/scholarship/award'
    fmt = {'name': name, 'link': link, 'support': b.email_support,
           'programme': b.programme_name(lang), 'signoff': b.team_signoff(lang)}
    body = AWARD_OFFER_SIGN_BODIES[lang].format(**fmt)
    html = _html_email_shell('<p style="margin:0 0 14px;">'
                             + body.replace('\n\n', '</p><p style="margin:0 0 14px;">').replace('\n', '<br>')
                             + '</p>')
    return _send_html(
        to_email, AWARD_OFFER_SIGN_SUBJECTS[lang].format(**fmt), body, html,
        from_email=b.email_from,
        reply_to=[b.email_support],
    )
