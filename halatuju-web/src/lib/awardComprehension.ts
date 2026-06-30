// Award comprehension quiz — the "Understand" step of /scholarship/award.
//
// Ported verbatim from the owner-approved prototype (scratchpad/bursary_preview).
// 8 multiple-choice checkpoints, each mirroring a clause of the bursary agreement
// (bursary.py is the single source of truth — keep these in lockstep with it).
// Gamified: a wrong answer is never penalised — the student re-reads and tries again.
//
// Content lives here (not the message JSONs) like the existing quiz_data modules, so the
// legal copy stays together and reviewable. en is final; ms is a working translation;
// ta is a first draft for the owner's refine (per the Tamil style guide).

export type Locale = 'en' | 'ms' | 'ta'

export interface QuizOption {
  /** The answer text shown on the button. */
  text: string
  /** Exactly one option per question is correct. */
  correct: boolean
}

export interface QuizCheckpoint {
  /** Short clause label (small caps header). */
  tag: string
  /** "What this means for you" plain-language explainer (blue box). */
  plain: string
  /** The comprehension question. */
  question: string
  options: QuizOption[]
  /** Shown after the correct answer is chosen. */
  why: string
}

type Localised<T> = Record<Locale, T>

// ── The 8 checkpoints, per locale ────────────────────────────────────────────
export const CHECKPOINTS: Localised<QuizCheckpoint[]> = {
  en: [
    {
      tag: 'Your declaration · True and complete information',
      plain: 'Everything you gave us — your family income, your results, your documents — must be true and complete. Your bursary was awarded on the basis that your details are honest.',
      question: 'The income, results and documents you submitted must be…',
      options: [
        { text: 'Roughly right is good enough.', correct: false },
        { text: 'True and complete — honest in every detail.', correct: true },
        { text: 'Only the parts that help my case.', correct: false },
      ],
      why: 'Correct. Your bursary rests on honest information. False details can lead to the bursary being withdrawn and repayment required.',
    },
    {
      tag: 'The bursary is a gift',
      plain: 'This money is a GIFT to help you study — you do not repay it like a loan. Repayment can only be asked if you obtained it dishonestly or misused it.',
      question: 'Is the bursary a loan you must repay?',
      options: [
        { text: 'Yes — I must pay it all back after I graduate.', correct: false },
        { text: 'No — it is a gift, not repayable (unless I lied or misused it).', correct: true },
        { text: 'Only if I fail my exams.', correct: false },
      ],
      why: 'Right — it is a gift, not a debt.',
    },
    {
      tag: 'Study in the stated government programme',
      plain: 'You must enrol and actually study the EXACT programme at the government institution stated in your agreement.',
      question: 'Can you use the bursary for a different course or college than the one stated?',
      options: [
        { text: 'Yes, any course I like.', correct: false },
        { text: 'No — I must study the stated programme at the stated government institution.', correct: true },
        { text: 'Yes, as long as it is also a diploma.', correct: false },
      ],
      why: 'Correct — the bursary is tied to the stated programme and institution. To change, you must get the Foundation’s agreement first.',
    },
    {
      tag: 'Tell the Foundation within 7 days',
      plain: 'If ANYTHING changes — your course, institution, phone number, or family situation — you must tell the Foundation within 7 days.',
      question: 'Your phone number changes, or you switch course. By when must you tell the Foundation?',
      options: [
        { text: 'Whenever I next remember.', correct: false },
        { text: 'Within 7 days.', correct: true },
        { text: 'Only at the end of the year.', correct: false },
      ],
      why: 'Correct — within 7 days. Keeping the Foundation informed protects your bursary.',
    },
    {
      tag: 'Maintain a 3.0 CGPA',
      plain: 'You must keep your CGPA at 3.0 or above. If you fall below 3.0, the Foundation may discontinue the bursary — after reviewing your situation with you.',
      question: 'What CGPA must you keep, and what can happen if you fall below it?',
      options: [
        { text: 'Any CGPA is fine — there is no minimum.', correct: false },
        { text: 'At least 3.0 — below that, the Foundation may discontinue the bursary.', correct: true },
        { text: '2.0, with no consequences.', correct: false },
      ],
      why: 'Correct — keep your CGPA at 3.0 or above. Falling below can lead to the bursary being discontinued.',
    },
    {
      tag: 'Upload your results every semester — promptly',
      plain: 'At the end of each semester you must upload your official results promptly. If you don’t, your bursary can be SUSPENDED, and continued failure can lead to TERMINATION.',
      question: 'You finish a semester. What must you do — and what if you don’t?',
      options: [
        { text: 'Nothing — they’ll ask if they need it.', correct: false },
        { text: 'Upload my results promptly — not doing so can lead to suspension and termination.', correct: true },
        { text: 'Upload them only if my grades are good.', correct: false },
      ],
      why: 'Correct — upload every semester, promptly. Missing this can suspend and ultimately terminate your bursary.',
    },
    {
      tag: 'Take part in Foundation activities',
      plain: 'The Foundation runs mentoring, seminars and other activities to help you succeed. You commit to taking part in these when invited.',
      question: 'The Foundation invites you to a mentoring session or seminar. You…',
      options: [
        { text: 'Can ignore it.', correct: false },
        { text: 'Commit to taking part — these are there to benefit me.', correct: true },
        { text: 'Only go if I am paid to attend.', correct: false },
      ],
      why: 'Correct — these activities are for your benefit; taking part is part of your commitment.',
    },
    {
      tag: 'If you don’t keep your side',
      plain: 'If you break this agreement — give false information, leave the stated programme without telling us, fall below 3.0, fail to upload results, or misuse the money — the Foundation may suspend or discontinue the bursary. You will always be given a fair chance to explain first.',
      question: 'Can the Foundation discontinue the bursary, and will you get a chance to respond?',
      options: [
        { text: 'Never, for any reason.', correct: false },
        { text: 'Yes — for breaking the agreement, but only after a fair chance to respond.', correct: true },
        { text: 'Yes — anytime, with no explanation.', correct: false },
      ],
      why: 'Correct — discontinuation is only for cause, and you always get a fair chance to respond first.',
    },
  ],

  ms: [
    {
      tag: 'Perakuan anda · Maklumat benar dan lengkap',
      plain: 'Segala yang anda berikan kepada kami — pendapatan keluarga, keputusan, dokumen anda — mestilah benar dan lengkap. Biasiswa anda diberikan atas dasar maklumat anda jujur.',
      question: 'Pendapatan, keputusan dan dokumen yang anda hantar mestilah…',
      options: [
        { text: 'Lebih kurang betul sudah memadai.', correct: false },
        { text: 'Benar dan lengkap — jujur dalam setiap butiran.', correct: true },
        { text: 'Hanya bahagian yang membantu kes saya.', correct: false },
      ],
      why: 'Betul. Biasiswa anda bergantung pada maklumat yang jujur. Butiran palsu boleh menyebabkan biasiswa ditarik balik dan bayaran balik dituntut.',
    },
    {
      tag: 'Biasiswa ialah satu pemberian',
      plain: 'Wang ini ialah PEMBERIAN untuk membantu pengajian anda — anda tidak membayarnya semula seperti pinjaman. Bayaran balik hanya boleh dituntut jika anda memperolehnya secara tidak jujur atau menyalahgunakannya.',
      question: 'Adakah biasiswa ini pinjaman yang mesti anda bayar balik?',
      options: [
        { text: 'Ya — saya mesti bayar semua selepas tamat pengajian.', correct: false },
        { text: 'Tidak — ia satu pemberian, tidak perlu dibayar balik (kecuali saya menipu atau menyalahgunakannya).', correct: true },
        { text: 'Hanya jika saya gagal peperiksaan.', correct: false },
      ],
      why: 'Betul — ia satu pemberian, bukan hutang.',
    },
    {
      tag: 'Belajar dalam program kerajaan yang dinyatakan',
      plain: 'Anda mesti mendaftar dan benar-benar belajar program TEPAT di institusi kerajaan yang dinyatakan dalam perjanjian anda.',
      question: 'Bolehkah anda gunakan biasiswa untuk kursus atau kolej yang berbeza daripada yang dinyatakan?',
      options: [
        { text: 'Ya, mana-mana kursus yang saya suka.', correct: false },
        { text: 'Tidak — saya mesti belajar program yang dinyatakan di institusi kerajaan yang dinyatakan.', correct: true },
        { text: 'Ya, asalkan ia juga diploma.', correct: false },
      ],
      why: 'Betul — biasiswa terikat dengan program dan institusi yang dinyatakan. Untuk menukar, anda mesti mendapat persetujuan Yayasan terlebih dahulu.',
    },
    {
      tag: 'Beritahu Yayasan dalam 7 hari',
      plain: 'Jika APA SAHAJA berubah — kursus, institusi, nombor telefon, atau keadaan keluarga anda — anda mesti beritahu Yayasan dalam tempoh 7 hari.',
      question: 'Nombor telefon anda berubah, atau anda menukar kursus. Bila anda mesti beritahu Yayasan?',
      options: [
        { text: 'Bila-bila masa saya teringat nanti.', correct: false },
        { text: 'Dalam tempoh 7 hari.', correct: true },
        { text: 'Hanya pada hujung tahun.', correct: false },
      ],
      why: 'Betul — dalam tempoh 7 hari. Memaklumkan Yayasan melindungi biasiswa anda.',
    },
    {
      tag: 'Kekalkan PNGK 3.0',
      plain: 'Anda mesti mengekalkan PNGK pada 3.0 atau lebih tinggi. Jika anda jatuh di bawah 3.0, Yayasan boleh memberhentikan biasiswa — selepas menyemak keadaan anda bersama anda.',
      question: 'PNGK berapa yang mesti anda kekalkan, dan apa boleh berlaku jika anda jatuh di bawahnya?',
      options: [
        { text: 'Mana-mana PNGK boleh — tiada minimum.', correct: false },
        { text: 'Sekurang-kurangnya 3.0 — di bawah itu, Yayasan boleh memberhentikan biasiswa.', correct: true },
        { text: '2.0, tanpa sebarang akibat.', correct: false },
      ],
      why: 'Betul — kekalkan PNGK pada 3.0 atau lebih. Jatuh di bawahnya boleh menyebabkan biasiswa diberhentikan.',
    },
    {
      tag: 'Muat naik keputusan setiap semester — segera',
      plain: 'Pada hujung setiap semester anda mesti memuat naik keputusan rasmi anda dengan segera. Jika tidak, biasiswa anda boleh DIGANTUNG, dan kegagalan berterusan boleh membawa kepada PENAMATAN.',
      question: 'Anda tamat satu semester. Apa anda mesti buat — dan jika tidak?',
      options: [
        { text: 'Tiada apa — mereka akan minta jika perlu.', correct: false },
        { text: 'Muat naik keputusan dengan segera — jika tidak boleh membawa kepada penggantungan dan penamatan.', correct: true },
        { text: 'Muat naik hanya jika keputusan saya baik.', correct: false },
      ],
      why: 'Betul — muat naik setiap semester, dengan segera. Terlepas ini boleh menggantung dan akhirnya menamatkan biasiswa anda.',
    },
    {
      tag: 'Sertai aktiviti Yayasan',
      plain: 'Yayasan menganjurkan bimbingan, seminar dan aktiviti lain untuk membantu anda berjaya. Anda berjanji untuk mengambil bahagian apabila dijemput.',
      question: 'Yayasan menjemput anda ke sesi bimbingan atau seminar. Anda…',
      options: [
        { text: 'Boleh abaikannya.', correct: false },
        { text: 'Berjanji untuk menyertainya — ia untuk manfaat saya.', correct: true },
        { text: 'Pergi hanya jika saya dibayar untuk hadir.', correct: false },
      ],
      why: 'Betul — aktiviti ini untuk manfaat anda; menyertainya sebahagian daripada komitmen anda.',
    },
    {
      tag: 'Jika anda tidak menunaikan tanggungjawab anda',
      plain: 'Jika anda melanggar perjanjian ini — memberi maklumat palsu, meninggalkan program yang dinyatakan tanpa memberitahu kami, jatuh di bawah 3.0, gagal memuat naik keputusan, atau menyalahgunakan wang — Yayasan boleh menggantung atau memberhentikan biasiswa. Anda sentiasa diberi peluang yang adil untuk menjelaskan terlebih dahulu.',
      question: 'Bolehkah Yayasan memberhentikan biasiswa, dan adakah anda akan diberi peluang menjawab?',
      options: [
        { text: 'Tidak sekali-kali, atas apa-apa sebab.', correct: false },
        { text: 'Ya — kerana melanggar perjanjian, tetapi hanya selepas peluang yang adil untuk menjawab.', correct: true },
        { text: 'Ya — bila-bila masa, tanpa penjelasan.', correct: false },
      ],
      why: 'Betul — pemberhentian hanya atas sebab, dan anda sentiasa diberi peluang yang adil untuk menjawab dahulu.',
    },
  ],

  // ── Tamil: FIRST DRAFT — needs the owner's refine per the Tamil style guide. ──
  ta: [
    {
      tag: 'உங்கள் உறுதிமொழி · உண்மையான மற்றும் முழுமையான தகவல்',
      plain: 'நீங்கள் எங்களுக்குக் கொடுத்த அனைத்தும் — உங்கள் குடும்ப வருமானம், உங்கள் முடிவுகள், உங்கள் ஆவணங்கள் — உண்மையாகவும் முழுமையாகவும் இருக்க வேண்டும். உங்கள் விவரங்கள் நேர்மையானவை என்ற அடிப்படையில்தான் உங்கள் உதவித்தொகை வழங்கப்பட்டது.',
      question: 'நீங்கள் சமர்ப்பித்த வருமானம், முடிவுகள் மற்றும் ஆவணங்கள் எவ்வாறு இருக்க வேண்டும்…',
      options: [
        { text: 'தோராயமாகச் சரியாக இருந்தால் போதும்.', correct: false },
        { text: 'உண்மையாகவும் முழுமையாகவும் — ஒவ்வொரு விவரத்திலும் நேர்மையாக.', correct: true },
        { text: 'எனக்கு உதவும் பகுதிகள் மட்டும்.', correct: false },
      ],
      why: 'சரி. உங்கள் உதவித்தொகை நேர்மையான தகவலை அடிப்படையாகக் கொண்டது. தவறான விவரங்கள் உதவித்தொகை திரும்பப் பெறப்படுவதற்கும் பணம் திருப்பிச் செலுத்தக் கோரப்படுவதற்கும் வழிவகுக்கும்.',
    },
    {
      tag: 'உதவித்தொகை ஒரு கொடை',
      plain: 'இந்தப் பணம் உங்கள் படிப்புக்கு உதவும் ஒரு கொடை — கடனைப் போல திருப்பிச் செலுத்த வேண்டியதில்லை. நீங்கள் நேர்மையற்ற முறையில் பெற்றிருந்தால் அல்லது தவறாகப் பயன்படுத்தினால் மட்டுமே திருப்பிச் செலுத்தக் கோரப்படும்.',
      question: 'உதவித்தொகை நீங்கள் திருப்பிச் செலுத்த வேண்டிய கடனா?',
      options: [
        { text: 'ஆம் — பட்டம் பெற்ற பிறகு அனைத்தையும் திருப்பிச் செலுத்த வேண்டும்.', correct: false },
        { text: 'இல்லை — இது ஒரு கொடை, திருப்பிச் செலுத்த வேண்டியதில்லை (நான் பொய் சொன்னால் அல்லது தவறாகப் பயன்படுத்தினால் தவிர).', correct: true },
        { text: 'நான் தேர்வில் தோல்வியடைந்தால் மட்டும்.', correct: false },
      ],
      why: 'சரி — இது ஒரு கொடை, கடன் அல்ல.',
    },
    {
      tag: 'குறிப்பிட்ட அரசாங்கத் திட்டத்தில் படியுங்கள்',
      plain: 'உங்கள் ஒப்பந்தத்தில் குறிப்பிடப்பட்ட அரசாங்க நிறுவனத்தில் சரியான திட்டத்தில் நீங்கள் சேர்ந்து உண்மையாகப் படிக்க வேண்டும்.',
      question: 'குறிப்பிட்டதைத் தவிர வேறு பாடம் அல்லது கல்லூரிக்கு உதவித்தொகையைப் பயன்படுத்த முடியுமா?',
      options: [
        { text: 'ஆம், எனக்குப் பிடித்த எந்தப் பாடமும்.', correct: false },
        { text: 'இல்லை — குறிப்பிட்ட அரசாங்க நிறுவனத்தில் குறிப்பிட்ட திட்டத்தைப் படிக்க வேண்டும்.', correct: true },
        { text: 'ஆம், அதுவும் டிப்ளமோவாக இருந்தால் சரி.', correct: false },
      ],
      why: 'சரி — உதவித்தொகை குறிப்பிட்ட திட்டத்துடனும் நிறுவனத்துடனும் இணைக்கப்பட்டுள்ளது. மாற்ற, முதலில் அறக்கட்டளையின் ஒப்புதலைப் பெற வேண்டும்.',
    },
    {
      tag: '7 நாட்களுக்குள் அறக்கட்டளைக்குத் தெரிவியுங்கள்',
      plain: 'எதுவாக இருந்தாலும் மாறினால் — உங்கள் பாடம், நிறுவனம், தொலைபேசி எண், அல்லது குடும்ப நிலை — 7 நாட்களுக்குள் அறக்கட்டளைக்குத் தெரிவிக்க வேண்டும்.',
      question: 'உங்கள் தொலைபேசி எண் மாறுகிறது, அல்லது பாடத்தை மாற்றுகிறீர்கள். எப்போதுக்குள் அறக்கட்டளைக்குத் தெரிவிக்க வேண்டும்?',
      options: [
        { text: 'அடுத்து நினைவுக்கு வரும்போது.', correct: false },
        { text: '7 நாட்களுக்குள்.', correct: true },
        { text: 'ஆண்டின் இறுதியில் மட்டும்.', correct: false },
      ],
      why: 'சரி — 7 நாட்களுக்குள். அறக்கட்டளைக்குத் தெரிவித்து வைப்பது உங்கள் உதவித்தொகையைப் பாதுகாக்கிறது.',
    },
    {
      tag: '3.0 CGPA பராமரியுங்கள்',
      plain: 'உங்கள் CGPA-வை 3.0 அல்லது அதற்கு மேல் பராமரிக்க வேண்டும். 3.0-க்குக் கீழே சென்றால், உங்கள் நிலையை உங்களுடன் சேர்ந்து பரிசீலித்த பிறகு அறக்கட்டளை உதவித்தொகையை நிறுத்தலாம்.',
      question: 'எந்த CGPA-வைப் பராமரிக்க வேண்டும், அதற்குக் கீழே சென்றால் என்ன நடக்கலாம்?',
      options: [
        { text: 'எந்த CGPA-வும் சரி — குறைந்தபட்சம் இல்லை.', correct: false },
        { text: 'குறைந்தது 3.0 — அதற்குக் கீழே, அறக்கட்டளை உதவித்தொகையை நிறுத்தலாம்.', correct: true },
        { text: '2.0, எந்த விளைவும் இல்லை.', correct: false },
      ],
      why: 'சரி — CGPA-வை 3.0 அல்லது அதற்கு மேல் பராமரியுங்கள். அதற்குக் கீழே செல்வது உதவித்தொகை நிறுத்தப்படுவதற்கு வழிவகுக்கும்.',
    },
    {
      tag: 'ஒவ்வொரு செமஸ்டரிலும் உங்கள் முடிவுகளை உடனடியாகப் பதிவேற்றுங்கள்',
      plain: 'ஒவ்வொரு செமஸ்டர் முடிவிலும் உங்கள் அதிகாரப்பூர்வ முடிவுகளை உடனடியாகப் பதிவேற்ற வேண்டும். இல்லையெனில், உங்கள் உதவித்தொகை இடைநிறுத்தப்படலாம், தொடர்ந்து தவறினால் முடிவுக்கு வரலாம்.',
      question: 'ஒரு செமஸ்டரை முடிக்கிறீர்கள். என்ன செய்ய வேண்டும் — செய்யாவிட்டால் என்ன?',
      options: [
        { text: 'எதுவும் இல்லை — தேவைப்பட்டால் அவர்கள் கேட்பார்கள்.', correct: false },
        { text: 'என் முடிவுகளை உடனடியாகப் பதிவேற்றுவேன் — செய்யாவிட்டால் இடைநிறுத்தம் மற்றும் முடிவுக்கு வழிவகுக்கும்.', correct: true },
        { text: 'என் மதிப்பெண்கள் நன்றாக இருந்தால் மட்டும் பதிவேற்றுவேன்.', correct: false },
      ],
      why: 'சரி — ஒவ்வொரு செமஸ்டரிலும் உடனடியாகப் பதிவேற்றுங்கள். இதைத் தவறவிடுவது உங்கள் உதவித்தொகையை இடைநிறுத்தி இறுதியில் முடிவுக்குக் கொண்டுவரும்.',
    },
    {
      tag: 'அறக்கட்டளை நடவடிக்கைகளில் பங்கேற்கவும்',
      plain: 'நீங்கள் வெற்றிபெற உதவ அறக்கட்டளை வழிகாட்டுதல், கருத்தரங்குகள் மற்றும் பிற நடவடிக்கைகளை நடத்துகிறது. அழைக்கப்படும்போது இவற்றில் பங்கேற்க உறுதியளிக்கிறீர்கள்.',
      question: 'அறக்கட்டளை உங்களை வழிகாட்டுதல் அமர்வு அல்லது கருத்தரங்குக்கு அழைக்கிறது. நீங்கள்…',
      options: [
        { text: 'புறக்கணிக்கலாம்.', correct: false },
        { text: 'பங்கேற்க உறுதியளிக்கிறேன் — இவை என் நலனுக்காகவே.', correct: true },
        { text: 'பணம் கொடுத்தால் மட்டும் செல்வேன்.', correct: false },
      ],
      why: 'சரி — இந்த நடவடிக்கைகள் உங்கள் நலனுக்காகவே; பங்கேற்பது உங்கள் உறுதிப்பாட்டின் ஒரு பகுதி.',
    },
    {
      tag: 'உங்கள் பங்கை நீங்கள் நிறைவேற்றாவிட்டால்',
      plain: 'நீங்கள் இந்த ஒப்பந்தத்தை மீறினால் — தவறான தகவல் கொடுத்தல், தெரிவிக்காமல் குறிப்பிட்ட திட்டத்தை விட்டு வெளியேறுதல், 3.0-க்குக் கீழே செல்லுதல், முடிவுகளைப் பதிவேற்றத் தவறுதல், அல்லது பணத்தைத் தவறாகப் பயன்படுத்துதல் — அறக்கட்டளை உதவித்தொகையை இடைநிறுத்தலாம் அல்லது நிறுத்தலாம். விளக்க உங்களுக்கு எப்போதும் முதலில் நியாயமான வாய்ப்பு வழங்கப்படும்.',
      question: 'அறக்கட்டளை உதவித்தொகையை நிறுத்த முடியுமா, பதிலளிக்க உங்களுக்கு வாய்ப்புக் கிடைக்குமா?',
      options: [
        { text: 'எந்தக் காரணத்திற்காகவும் ஒருபோதும் இல்லை.', correct: false },
        { text: 'ஆம் — ஒப்பந்தத்தை மீறியதற்காக, ஆனால் பதிலளிக்க நியாயமான வாய்ப்புக்குப் பிறகே.', correct: true },
        { text: 'ஆம் — எந்த நேரத்திலும், எந்த விளக்கமும் இல்லாமல்.', correct: false },
      ],
      why: 'சரி — நிறுத்தம் காரணத்திற்காக மட்டுமே, மேலும் பதிலளிக்க உங்களுக்கு எப்போதும் முதலில் நியாயமான வாய்ப்பு வழங்கப்படும்.',
    },
  ],
}

/** UI chrome strings for the quiz (the questions themselves are in CHECKPOINTS). The intro
 *  is donor-anonymous and amount-agnostic — the page already shows the particulars. */
export const QUIZ_UI: Localised<{
  introTitle: string
  introBody: string
  whatHappens: string
  step1: (count: number) => string
  step2: string
  step3: string
  begin: string
  heldNote: string
  understandHeading: string
  ofCount: (n: number, total: number) => string
  whatThisMeans: string
  next: string
  finish: string
  notQuite: string
  footnote: string
}> = {
  en: {
    introTitle: 'Congratulations — you’ve been awarded a bursary!',
    introBody: 'Before your funding is confirmed, we’ll take a few minutes to make sure you understand the agreement — then you and your parent or guardian sign it together.',
    whatHappens: 'What happens now:',
    step1: (count) => `Understand the key terms (${count} quick checkpoints)`,
    step2: 'Read the full agreement',
    step3: 'Sign — with your parent or guardian as your guarantor',
    begin: 'Let’s begin',
    heldNote: 'Your funding is held by an independent trust foundation and released as you progress.',
    understandHeading: 'Understand the key terms',
    ofCount: (n, total) => `${n} of ${total}`,
    whatThisMeans: 'What this means for you: ',
    next: 'Next',
    finish: 'I understand — read & sign',
    notQuite: 'Not quite. Read the blue box once more, then try again — there is no penalty.',
    footnote: 'Wrong answers aren’t held against you — we explain and let you try again. This is to help you understand, not to test you.',
  },
  ms: {
    introTitle: 'Tahniah — anda telah dianugerahkan biasiswa!',
    introBody: 'Sebelum pembiayaan anda disahkan, kami akan mengambil beberapa minit untuk memastikan anda memahami perjanjian ini — kemudian anda dan ibu bapa atau penjaga anda menandatanganinya bersama.',
    whatHappens: 'Apa yang berlaku sekarang:',
    step1: (count) => `Fahami terma utama (${count} pemeriksaan ringkas)`,
    step2: 'Baca perjanjian penuh',
    step3: 'Tandatangani — dengan ibu bapa atau penjaga anda sebagai penjamin',
    begin: 'Mari mulakan',
    heldNote: 'Pembiayaan anda dipegang oleh sebuah yayasan amanah bebas dan dikeluarkan apabila anda maju.',
    understandHeading: 'Fahami terma utama',
    ofCount: (n, total) => `${n} daripada ${total}`,
    whatThisMeans: 'Apa maksudnya untuk anda: ',
    next: 'Seterusnya',
    finish: 'Saya faham — baca & tandatangani',
    notQuite: 'Belum tepat. Baca kotak biru sekali lagi, kemudian cuba lagi — tiada penalti.',
    footnote: 'Jawapan salah tidak menjejaskan anda — kami terangkan dan benarkan anda cuba lagi. Ini untuk membantu anda faham, bukan untuk menguji anda.',
  },
  ta: {
    introTitle: 'வாழ்த்துகள் — உங்களுக்கு உதவித்தொகை வழங்கப்பட்டுள்ளது!',
    introBody: 'உங்கள் நிதி உறுதிப்படுத்தப்படுவதற்கு முன், ஒப்பந்தத்தை நீங்கள் புரிந்துகொள்வதை உறுதிசெய்ய சில நிமிடங்கள் எடுத்துக்கொள்வோம் — பின்னர் நீங்களும் உங்கள் பெற்றோர் அல்லது பாதுகாவலரும் இணைந்து கையெழுத்திடுவீர்கள்.',
    whatHappens: 'இப்போது என்ன நடக்கும்:',
    step1: (count) => `முக்கிய நிபந்தனைகளைப் புரிந்துகொள்ளுங்கள் (${count} விரைவு சரிபார்ப்புகள்)`,
    step2: 'முழு ஒப்பந்தத்தையும் படியுங்கள்',
    step3: 'கையெழுத்திடுங்கள் — உங்கள் பெற்றோர் அல்லது பாதுகாவலர் பிணையாளராக',
    begin: 'தொடங்குவோம்',
    heldNote: 'உங்கள் நிதி ஒரு சுயாதீன அறக்கட்டளையால் வைத்திருக்கப்பட்டு, நீங்கள் முன்னேறும்போது வழங்கப்படுகிறது.',
    understandHeading: 'முக்கிய நிபந்தனைகளைப் புரிந்துகொள்ளுங்கள்',
    ofCount: (n, total) => `${total}-ல் ${n}`,
    whatThisMeans: 'இது உங்களுக்கு என்ன அர்த்தம்: ',
    next: 'அடுத்து',
    finish: 'புரிந்தது — படித்து கையெழுத்திடு',
    notQuite: 'சரியாக இல்லை. நீலப் பெட்டியை மீண்டும் படித்து, பின்னர் முயற்சிக்கவும் — தண்டனை இல்லை.',
    footnote: 'தவறான பதில்கள் உங்களுக்கு எதிராகக் கணக்கிடப்படாது — நாங்கள் விளக்கி, மீண்டும் முயற்சிக்க அனுமதிக்கிறோம். இது உங்களைச் சோதிப்பதற்கல்ல, புரியவைப்பதற்கே.',
  },
}

export const CHECKPOINT_COUNT = CHECKPOINTS.en.length

export function checkpointsFor(locale: string): QuizCheckpoint[] {
  return CHECKPOINTS[(locale as Locale)] ?? CHECKPOINTS.en
}

export function quizUiFor(locale: string) {
  return QUIZ_UI[(locale as Locale)] ?? QUIZ_UI.en
}
