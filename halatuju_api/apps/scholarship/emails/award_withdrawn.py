"""The "award withdrawn" notice (A1.13, TD-198 / CO-09; owner rulings 2026-11-08).

Sent AFTER COMMIT once a checker APPROVES somebody else's withdrawal request (A1.13b maker and checker,
`award_withdrawal_chain.approve_withdrawal`). It tells the student, in her language, that the award no
longer stands and that her application stays with us. It NEVER carries the explanation or the checker's
note: those are internal (staff only). No amount, no sponsor identity (two-way anonymity).

The text below is the owner-approved wording (EN, MS, TA; 2026-11-08). It is the PLATFORM DEFAULT of the
organisation-worded family (`student_comms.DEFAULTS['award_withdrawn']`, A1.13b): an organisation may word
it itself under Organisation -> Settings -> Student communications, and the send goes through
`student_comms.send_student_email` (its log, its meter). It is LOCKED there (a decision: always sent).
"""

AWARD_WITHDRAWN_SUBJECTS = {
    'en': 'An update about your {programme} award',
    'ms': 'Makluman tentang anugerah {programme} anda',
    'ta': 'உங்கள் {programme} உதவித்தொகையைப் பற்றிய அறிவிப்பு',
}
AWARD_WITHDRAWN_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "We are writing about the award offered to you under the {programme} Programme.\n\n"
        "After a review, the award has been withdrawn, and the offer you received no longer "
        "stands. No payments will be made under it.\n\n"
        "Your application stays with us, and our team may consider it again. You do not need to "
        "do anything now.\n\n"
        "We know this is not the news you hoped for. If you have any questions, reply to this "
        "email or contact us at {support}.\n\n"
        "Warm regards,\n{signoff}"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Kami menulis mengenai anugerah yang ditawarkan kepada anda di bawah Program "
        "{programme}.\n\n"
        "Selepas semakan, anugerah ini telah ditarik balik, dan tawaran yang anda terima tidak "
        "lagi berkuat kuasa. Tiada pembayaran akan dibuat di bawahnya.\n\n"
        "Permohonan anda kekal bersama kami, dan pasukan kami mungkin menimbangkannya semula. "
        "Anda tidak perlu berbuat apa-apa sekarang.\n\n"
        "Kami faham ini bukan berita yang anda harapkan. Jika ada sebarang pertanyaan, balas "
        "e-mel ini atau hubungi kami di {support}.\n\n"
        "Salam hormat,\n{signoff}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "{programme} திட்டத்தின் கீழ் உங்களுக்கு வழங்கப்பட்ட உதவித்தொகையைப் பற்றி "
        "எழுதுகிறோம்.\n\n"
        "மறுஆய்வுக்குப் பிறகு, அந்த உதவித்தொகை திரும்பப் பெறப்பட்டுள்ளது; நீங்கள் பெற்ற வழங்கல் "
        "(offer) இனி செல்லாது. அதன் கீழ் எந்தக் கட்டணமும் வழங்கப்படாது.\n\n"
        "உங்கள் விண்ணப்பம் எங்களிடம் தொடர்ந்து இருக்கும்; எங்கள் குழு அதை மீண்டும் "
        "பரிசீலிக்கலாம். இப்போது நீங்கள் எதுவும் செய்ய வேண்டியதில்லை.\n\n"
        "நீங்கள் எதிர்பார்த்த செய்தி இது அல்ல என்பதை நாங்கள் அறிவோம். ஏதேனும் கேள்விகள் "
        "இருந்தால், இந்த மின்னஞ்சலுக்குப் பதிலளிக்கவும் அல்லது {support} இல் எங்களைத் "
        "தொடர்புகொள்ளவும்.\n\n"
        "அன்புடன்,\n{signoff}"
    ),
}

