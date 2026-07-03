// Award comprehension quiz — the "Understand" step of /scholarship/award.
//
// Ported from the owner-approved prototype (scratchpad/bursary_preview), then
// RECONCILED to the real AGREEMENT_CLAUSES on 2026-07-03 (code-health S3 #10) —
// the prototype taught terms the agreement does not contain.
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
// Reconciled to AGREEMENT_CLAUSES 2026-07-03 (code-health S3 #10): the earlier draft
// taught terms the agreement does NOT contain (a 3.0-CGPA rule, a 7-day notice, a
// per-semester upload/suspension duty, a locked programme). Every checkpoint below
// paraphrases a real clause: 1↔Declaration+Cl.10 · 2↔Cl.11 (gift) · 3↔Cl.4/5
// (enrolment) · 4↔Cl.7 (notify changes) · 5↔Cl.6 (progress = supportive review) ·
// 6↔Cl.3 (evidence on request) · 7↔Cl.9 (mentor + activities) · 8↔Cl.10 (suspension,
// fair response). Owner review pending before BURSARY_AGREEMENT_ENABLED ever flips.
export const CHECKPOINTS: Localised<QuizCheckpoint[]> = {
  en: [
    {
      tag: 'Your declaration · True and complete information',
      plain: 'Everything you gave us — your family income, your results, your documents — must be true and complete, and you agree to provide honest evidence when the Foundation reasonably asks. Your bursary was awarded on the basis that your details are honest.',
      question: 'The income, results and documents you submitted must be…',
      options: [
        { text: 'Roughly right is good enough.', correct: false },
        { text: 'True and complete — honest in every detail.', correct: true },
        { text: 'Only the parts that help my case.', correct: false },
      ],
      why: 'Correct. Your bursary rests on honest information. Under the agreement, false information can lead to support being suspended or withheld, and a bursary obtained by fraud can be reclaimed.',
    },
    {
      tag: 'The bursary is a gift',
      plain: 'This money is a GIFT to help you study — it is NOT repayable like a loan. Repayment of the affected amount can only be required if the bursary was obtained by fraud or has been misused.',
      question: 'Is the bursary a loan you must repay?',
      options: [
        { text: 'Yes — I must pay it all back after I graduate.', correct: false },
        { text: 'No — it is a gift, not repayable (unless it was obtained by fraud or misused).', correct: true },
        { text: 'Only if I fail my exams.', correct: false },
      ],
      why: 'Right — it is a gift, not a debt. Ordinary, good-faith use is never clawed back.',
    },
    {
      tag: 'Enrol — and stay enrolled — in the stated course',
      plain: 'You confirm you are (or will be) enrolled at a recognised government institution for the course stated in your agreement, and you agree to stay enrolled for the duration of the bursary. If you intend to defer, change or withdraw from the course, you must tell the Foundation promptly.',
      question: 'You are thinking of deferring or changing your course. What does the agreement ask of you?',
      options: [
        { text: 'Nothing — my course is my own business.', correct: false },
        { text: 'Tell the Foundation promptly about my intention.', correct: true },
        { text: 'Change first, mention it if anyone asks.', correct: false },
      ],
      why: 'Correct — stay enrolled, and tell the Foundation promptly BEFORE you defer, change or withdraw, so your support can be looked after.',
    },
    {
      tag: 'Tell the Foundation when things change',
      plain: 'If anything material changes — your institution, course, contact details, or household situation — you agree to tell the Foundation within a reasonable time. Don’t sit on news; keeping the Foundation informed protects your bursary.',
      question: 'Your phone number changes, or your family situation shifts. When must you tell the Foundation?',
      options: [
        { text: 'Never — it is not their concern.', correct: false },
        { text: 'Within a reasonable time — promptly, not months later.', correct: true },
        { text: 'Only if they happen to ask.', correct: false },
      ],
      why: 'Correct — within a reasonable time. A quick message when something changes is all it takes.',
    },
    {
      tag: 'Academic progress · A supportive review, never automatic',
      plain: 'You agree to work towards satisfactory academic progress, as described in your agreement’s Particulars. If your progress falls short, the Foundation will REVIEW the situation with you supportively — your bursary is NOT automatically suspended.',
      question: 'Your results fall short one semester. What happens under the agreement?',
      options: [
        { text: 'My bursary is automatically suspended.', correct: false },
        { text: 'The Foundation reviews the situation with me supportively — nothing is automatic.', correct: true },
        { text: 'Nothing — my progress does not matter.', correct: false },
      ],
      why: 'Correct — a shortfall leads to a supportive review WITH you, never an automatic suspension. Working towards satisfactory progress is your side of the commitment.',
    },
    {
      tag: 'Evidence when reasonably asked',
      plain: 'From time to time the Foundation may reasonably ask for evidence — your academic results, household income, or continued eligibility (for example an STR document) — so it can administer the bursary responsibly. You agree to provide it when asked.',
      question: 'The Foundation asks for your latest results or an income document. You…',
      options: [
        { text: 'Can ignore the request.', correct: false },
        { text: 'Provide the evidence when reasonably requested.', correct: true },
        { text: 'Only provide it if the news is good.', correct: false },
      ],
      why: 'Correct — providing evidence when reasonably asked is how the Foundation administers everyone’s bursary responsibly.',
    },
    {
      tag: 'Your mentor and Foundation activities',
      plain: 'You will be assigned a mentor. You agree to keep reasonable communication with them, and to take part in Foundation or programme activities — mentoring, seminars and the like — when invited.',
      question: 'Your assigned mentor writes to you, or the Foundation invites you to a seminar. You…',
      options: [
        { text: 'Can ignore them.', correct: false },
        { text: 'Keep in reasonable contact with my mentor and take part when invited.', correct: true },
        { text: 'Only respond if I am paid to.', correct: false },
      ],
      why: 'Correct — the mentor and the activities exist to help you succeed; reasonable communication and taking part are your side of the commitment.',
    },
    {
      tag: 'If you don’t keep your side',
      plain: 'If you fail to comply with the agreement, provide false information, or misuse the bursary, the Foundation may suspend or withhold future support. You will always be given a fair opportunity to respond first.',
      question: 'Can the Foundation suspend or withhold your support, and will you get a chance to respond?',
      options: [
        { text: 'Never, for any reason.', correct: false },
        { text: 'Yes — for non-compliance, false information or misuse, but only after a fair opportunity to respond.', correct: true },
        { text: 'Yes — anytime, with no explanation.', correct: false },
      ],
      why: 'Correct — suspension or withholding is only for cause (non-compliance, false information, misuse), and you always get a fair opportunity to respond first.',
    },
  ],

  ms: [
    {
      tag: 'Perakuan anda · Maklumat benar dan lengkap',
      plain: 'Segala yang anda berikan kepada kami — pendapatan keluarga, keputusan, dokumen anda — mestilah benar dan lengkap, dan anda bersetuju memberikan bukti yang jujur apabila Yayasan memintanya dengan munasabah. Biasiswa anda diberikan atas dasar maklumat anda jujur.',
      question: 'Pendapatan, keputusan dan dokumen yang anda hantar mestilah…',
      options: [
        { text: 'Lebih kurang betul sudah memadai.', correct: false },
        { text: 'Benar dan lengkap — jujur dalam setiap butiran.', correct: true },
        { text: 'Hanya bahagian yang membantu kes saya.', correct: false },
      ],
      why: 'Betul. Biasiswa anda bergantung pada maklumat yang jujur. Di bawah perjanjian, maklumat palsu boleh menyebabkan sokongan digantung atau ditahan, dan biasiswa yang diperoleh melalui penipuan boleh dituntut balik.',
    },
    {
      tag: 'Biasiswa ialah satu pemberian',
      plain: 'Wang ini ialah PEMBERIAN untuk membantu pengajian anda — ia TIDAK perlu dibayar balik seperti pinjaman. Bayaran balik amaun yang terjejas hanya boleh dituntut jika biasiswa diperoleh melalui penipuan atau telah disalahgunakan.',
      question: 'Adakah biasiswa ini pinjaman yang mesti anda bayar balik?',
      options: [
        { text: 'Ya — saya mesti bayar semua selepas tamat pengajian.', correct: false },
        { text: 'Tidak — ia satu pemberian, tidak perlu dibayar balik (kecuali diperoleh melalui penipuan atau disalahgunakan).', correct: true },
        { text: 'Hanya jika saya gagal peperiksaan.', correct: false },
      ],
      why: 'Betul — ia satu pemberian, bukan hutang. Penggunaan biasa dengan suci hati tidak sekali-kali dituntut balik.',
    },
    {
      tag: 'Daftar — dan kekal mendaftar — dalam kursus yang dinyatakan',
      plain: 'Anda mengesahkan bahawa anda sedang (atau akan) mendaftar di institusi kerajaan yang diiktiraf untuk kursus yang dinyatakan dalam perjanjian anda, dan bersetuju kekal mendaftar sepanjang tempoh biasiswa. Jika anda berhasrat menangguh, menukar atau menarik diri daripada kursus, anda mesti memberitahu Yayasan dengan segera.',
      question: 'Anda berfikir untuk menangguh atau menukar kursus. Apa yang perjanjian minta daripada anda?',
      options: [
        { text: 'Tiada apa — kursus saya urusan saya sendiri.', correct: false },
        { text: 'Memberitahu Yayasan dengan segera tentang hasrat saya.', correct: true },
        { text: 'Tukar dahulu, sebut jika ada yang bertanya.', correct: false },
      ],
      why: 'Betul — kekal mendaftar, dan beritahu Yayasan dengan segera SEBELUM anda menangguh, menukar atau menarik diri, supaya sokongan anda dapat diuruskan.',
    },
    {
      tag: 'Beritahu Yayasan apabila keadaan berubah',
      plain: 'Jika sebarang perkara penting berubah — institusi, kursus, butiran perhubungan, atau keadaan isi rumah anda — anda bersetuju memberitahu Yayasan dalam masa yang munasabah. Jangan tangguhkan; memaklumkan Yayasan melindungi biasiswa anda.',
      question: 'Nombor telefon anda berubah, atau keadaan keluarga anda berubah. Bila anda mesti beritahu Yayasan?',
      options: [
        { text: 'Tidak perlu — ia bukan urusan mereka.', correct: false },
        { text: 'Dalam masa yang munasabah — segera, bukan berbulan-bulan kemudian.', correct: true },
        { text: 'Hanya jika mereka kebetulan bertanya.', correct: false },
      ],
      why: 'Betul — dalam masa yang munasabah. Satu pesanan ringkas apabila sesuatu berubah sudah memadai.',
    },
    {
      tag: 'Kemajuan akademik · Semakan menyokong, bukan automatik',
      plain: 'Anda bersetuju berusaha ke arah kemajuan akademik yang memuaskan, seperti yang diterangkan dalam Butiran perjanjian anda. Jika kemajuan kurang memuaskan, Yayasan akan MENYEMAK keadaan bersama anda secara menyokong — biasiswa anda TIDAK digantung secara automatik.',
      question: 'Keputusan anda kurang memuaskan pada satu semester. Apa yang berlaku di bawah perjanjian?',
      options: [
        { text: 'Biasiswa saya digantung secara automatik.', correct: false },
        { text: 'Yayasan menyemak keadaan bersama saya secara menyokong — tiada apa-apa yang automatik.', correct: true },
        { text: 'Tiada apa — kemajuan saya tidak penting.', correct: false },
      ],
      why: 'Betul — kekurangan membawa kepada semakan menyokong BERSAMA anda, bukan penggantungan automatik. Berusaha ke arah kemajuan yang memuaskan ialah tanggungjawab anda.',
    },
    {
      tag: 'Bukti apabila diminta dengan munasabah',
      plain: 'Dari semasa ke semasa Yayasan boleh meminta bukti dengan munasabah — keputusan akademik, pendapatan isi rumah, atau kelayakan berterusan anda (contohnya dokumen STR) — supaya biasiswa dapat ditadbir dengan bertanggungjawab. Anda bersetuju memberikannya apabila diminta.',
      question: 'Yayasan meminta keputusan terkini atau dokumen pendapatan anda. Anda…',
      options: [
        { text: 'Boleh abaikan permintaan itu.', correct: false },
        { text: 'Memberikan bukti apabila diminta dengan munasabah.', correct: true },
        { text: 'Hanya beri jika beritanya baik.', correct: false },
      ],
      why: 'Betul — memberikan bukti apabila diminta dengan munasabah membolehkan Yayasan mentadbir biasiswa semua pelajar dengan bertanggungjawab.',
    },
    {
      tag: 'Mentor anda dan aktiviti Yayasan',
      plain: 'Anda akan ditugaskan seorang mentor. Anda bersetuju mengekalkan komunikasi yang munasabah dengan mereka, dan menyertai aktiviti Yayasan atau program — bimbingan, seminar dan seumpamanya — apabila dijemput.',
      question: 'Mentor anda menghubungi anda, atau Yayasan menjemput anda ke seminar. Anda…',
      options: [
        { text: 'Boleh abaikan mereka.', correct: false },
        { text: 'Kekal berhubung secara munasabah dengan mentor saya dan menyertai apabila dijemput.', correct: true },
        { text: 'Hanya balas jika saya dibayar.', correct: false },
      ],
      why: 'Betul — mentor dan aktiviti ini wujud untuk membantu anda berjaya; komunikasi yang munasabah dan penyertaan ialah tanggungjawab anda.',
    },
    {
      tag: 'Jika anda tidak menunaikan tanggungjawab anda',
      plain: 'Jika anda gagal mematuhi perjanjian, memberikan maklumat palsu, atau menyalahgunakan biasiswa, Yayasan boleh menggantung atau menahan sokongan masa hadapan. Anda sentiasa diberi peluang yang adil untuk menjawab terlebih dahulu.',
      question: 'Bolehkah Yayasan menggantung atau menahan sokongan anda, dan adakah anda diberi peluang menjawab?',
      options: [
        { text: 'Tidak sekali-kali, atas apa-apa sebab.', correct: false },
        { text: 'Ya — kerana ketidakpatuhan, maklumat palsu atau penyalahgunaan, tetapi hanya selepas peluang yang adil untuk menjawab.', correct: true },
        { text: 'Ya — bila-bila masa, tanpa penjelasan.', correct: false },
      ],
      why: 'Betul — penggantungan atau penahanan hanya atas sebab (ketidakpatuhan, maklumat palsu, penyalahgunaan), dan anda sentiasa diberi peluang yang adil untuk menjawab dahulu.',
    },
  ],

  // ── Tamil: FIRST DRAFT — needs the owner’s refine per the Tamil style guide. ──
  ta: [
    {
      tag: 'உங்கள் உறுதிமொழி · உண்மையான, முழுமையான தகவல்',
      plain: 'நீங்கள் எங்களுக்குக் கொடுத்த அனைத்தும் — குடும்ப வருமானம், தேர்வு முடிவுகள், ஆவணங்கள் — உண்மையாகவும் முழுமையாகவும் இருக்க வேண்டும்; அறக்கட்டளை நியாயமான முறையில் கேட்கும்போது நேர்மையான சான்றுகளை வழங்கவும் ஒப்புக்கொள்கிறீர்கள். உங்கள் விவரங்கள் நேர்மையானவை என்ற அடிப்படையில்தான் உதவித்தொகை வழங்கப்பட்டது.',
      question: 'நீங்கள் சமர்ப்பித்த வருமானம், முடிவுகள், ஆவணங்கள் எப்படி இருக்க வேண்டும்…',
      options: [
        { text: 'தோராயமாகச் சரியாக இருந்தால் போதும்.', correct: false },
        { text: 'உண்மையாகவும் முழுமையாகவும் — ஒவ்வொரு விவரத்திலும் நேர்மையாக.', correct: true },
        { text: 'எனக்கு உதவும் பகுதிகள் மட்டும்.', correct: false },
      ],
      why: 'சரி. உங்கள் உதவித்தொகை நேர்மையான தகவலின் அடிப்படையிலானது. ஒப்பந்தத்தின்படி, தவறான தகவல் உதவி இடைநிறுத்தப்படவோ நிறுத்திவைக்கப்படவோ காரணமாகலாம்; மோசடியால் பெறப்பட்ட உதவித்தொகை திரும்பக் கோரப்படலாம்.',
    },
    {
      tag: 'உதவித்தொகை ஒரு கொடை',
      plain: 'இந்தப் பணம் உங்கள் படிப்புக்கு உதவும் ஒரு கொடை — கடனைப் போலத் திருப்பிச் செலுத்த வேண்டியதில்லை. மோசடியால் பெறப்பட்டிருந்தால் அல்லது தவறாகப் பயன்படுத்தப்பட்டிருந்தால் மட்டுமே, பாதிக்கப்பட்ட தொகையைத் திருப்பிச் செலுத்தக் கோர முடியும்.',
      question: 'உதவித்தொகை நீங்கள் திருப்பிச் செலுத்த வேண்டிய கடனா?',
      options: [
        { text: 'ஆம் — பட்டம் பெற்ற பிறகு அனைத்தையும் திருப்பிச் செலுத்த வேண்டும்.', correct: false },
        { text: 'இல்லை — இது ஒரு கொடை; திருப்பிச் செலுத்த வேண்டியதில்லை (மோசடி அல்லது தவறான பயன்பாடு தவிர).', correct: true },
        { text: 'நான் தேர்வில் தோல்வியடைந்தால் மட்டும்.', correct: false },
      ],
      why: 'சரி — இது ஒரு கொடை, கடன் அல்ல. நல்லெண்ணத்துடன் செய்யும் இயல்பான பயன்பாடு ஒருபோதும் திரும்பக் கோரப்படாது.',
    },
    {
      tag: 'குறிப்பிட்ட பாடத்தில் சேர்ந்து — தொடர்ந்து — படியுங்கள்',
      plain: 'ஒப்பந்தத்தில் குறிப்பிடப்பட்ட பாடத்திற்காக அங்கீகரிக்கப்பட்ட அரசாங்க உயர்கல்வி நிறுவனத்தில் சேர்ந்திருப்பதை (அல்லது சேரப்போவதை) உறுதிப்படுத்துகிறீர்கள்; உதவித்தொகைக் காலம் முழுவதும் தொடர்ந்து பதிவில் இருக்கவும் ஒப்புக்கொள்கிறீர்கள். படிப்பை ஒத்திவைக்க, மாற்ற அல்லது விலக எண்ணினால், உடனடியாக அறக்கட்டளைக்குத் தெரிவிக்க வேண்டும்.',
      question: 'படிப்பை ஒத்திவைக்கவோ மாற்றவோ யோசிக்கிறீர்கள். ஒப்பந்தம் உங்களிடம் என்ன கேட்கிறது?',
      options: [
        { text: 'எதுவும் இல்லை — என் படிப்பு என் சொந்த விஷயம்.', correct: false },
        { text: 'என் எண்ணத்தை உடனடியாக அறக்கட்டளைக்குத் தெரிவிப்பது.', correct: true },
        { text: 'முதலில் மாற்றிவிட்டு, யாராவது கேட்டால் சொல்வது.', correct: false },
      ],
      why: 'சரி — தொடர்ந்து பதிவில் இருங்கள்; ஒத்திவைப்பு, மாற்றம் அல்லது விலகலுக்கு முன் அறக்கட்டளைக்கு உடனடியாகத் தெரிவியுங்கள் — அப்போதுதான் உங்கள் உதவியைச் சரியாகப் பராமரிக்க முடியும்.',
    },
    {
      tag: 'மாற்றங்களை அறக்கட்டளைக்குத் தெரிவியுங்கள்',
      plain: 'முக்கியமான எதுவும் மாறினால் — நிறுவனம், பாடம், தொடர்பு விவரங்கள், அல்லது குடும்பச் சூழல் — நியாயமான காலத்திற்குள் அறக்கட்டளைக்குத் தெரிவிக்க ஒப்புக்கொள்கிறீர்கள். தாமதிக்காதீர்கள்; தெரிவித்து வைப்பது உங்கள் உதவித்தொகையைப் பாதுகாக்கிறது.',
      question: 'உங்கள் தொலைபேசி எண் மாறுகிறது, அல்லது குடும்பச் சூழல் மாறுகிறது. எப்போது அறக்கட்டளைக்குத் தெரிவிக்க வேண்டும்?',
      options: [
        { text: 'தேவையில்லை — இது அவர்கள் விஷயம் அல்ல.', correct: false },
        { text: 'நியாயமான காலத்திற்குள் — உடனடியாக; மாதக்கணக்கில் தாமதிக்காமல்.', correct: true },
        { text: 'அவர்கள் கேட்டால் மட்டும்.', correct: false },
      ],
      why: 'சரி — நியாயமான காலத்திற்குள். ஏதேனும் மாறும்போது ஒரு சிறு செய்தி அனுப்பினாலே போதும்.',
    },
    {
      tag: 'கல்வி முன்னேற்றம் · ஆதரவான மறுஆய்வு; தானியங்கி நிறுத்தம் இல்லை',
      plain: 'ஒப்பந்த விவரங்களில் கூறியபடி, திருப்திகரமான கல்வி முன்னேற்றத்தை நோக்கி முயல ஒப்புக்கொள்கிறீர்கள். முன்னேற்றம் குறைந்தால், அறக்கட்டளை உங்களுடன் சேர்ந்து ஆதரவான முறையில் நிலைமையை மறுஆய்வு செய்யும் — உங்கள் உதவித்தொகை தானாக இடைநிறுத்தப்படாது.',
      question: 'ஒரு பருவத்தில் உங்கள் முடிவுகள் குறைகின்றன. ஒப்பந்தத்தின்படி என்ன நடக்கும்?',
      options: [
        { text: 'என் உதவித்தொகை தானாக இடைநிறுத்தப்படும்.', correct: false },
        { text: 'அறக்கட்டளை என்னுடன் சேர்ந்து ஆதரவாக நிலைமையை மறுஆய்வு செய்யும் — எதுவும் தானியங்கி அல்ல.', correct: true },
        { text: 'எதுவும் இல்லை — என் முன்னேற்றம் முக்கியமல்ல.', correct: false },
      ],
      why: 'சரி — குறைவு ஏற்பட்டால் உங்களுடன் சேர்ந்த ஆதரவான மறுஆய்வுதான் நடக்கும்; தானியங்கி இடைநிறுத்தம் இல்லை. திருப்திகரமான முன்னேற்றத்தை நோக்கி முயல்வது உங்கள் பங்கு.',
    },
    {
      tag: 'நியாயமாகக் கேட்கும்போது சான்று',
      plain: 'அவ்வப்போது அறக்கட்டளை நியாயமான முறையில் சான்று கேட்கலாம் — கல்வி முடிவுகள், குடும்ப வருமானம், அல்லது தொடர் தகுதி (எடுத்துக்காட்டாக STR ஆவணம்) — உதவித்தொகையைப் பொறுப்புடன் நிர்வகிக்க. கேட்கும்போது வழங்க ஒப்புக்கொள்கிறீர்கள்.',
      question: 'அறக்கட்டளை உங்கள் சமீபத்திய முடிவுகளையோ வருமான ஆவணத்தையோ கேட்கிறது. நீங்கள்…',
      options: [
        { text: 'கோரிக்கையைப் புறக்கணிக்கலாம்.', correct: false },
        { text: 'நியாயமாகக் கேட்கப்படும்போது சான்றை வழங்குவேன்.', correct: true },
        { text: 'செய்தி நல்லதாக இருந்தால் மட்டும் கொடுப்பேன்.', correct: false },
      ],
      why: 'சரி — நியாயமாகக் கேட்கப்படும்போது சான்று வழங்குவதன் மூலமே அறக்கட்டளை அனைவரின் உதவித்தொகையையும் பொறுப்புடன் நிர்வகிக்கிறது.',
    },
    {
      tag: 'உங்கள் வழிகாட்டியும் அறக்கட்டளை நடவடிக்கைகளும்',
      plain: 'உங்களுக்கு ஒரு வழிகாட்டி நியமிக்கப்படுவார். அவருடன் நியாயமான தொடர்பைப் பேணவும், அழைக்கப்படும்போது அறக்கட்டளை அல்லது திட்ட நடவடிக்கைகளில் — வழிகாட்டுதல், கருத்தரங்குகள் போன்றவற்றில் — பங்கேற்கவும் ஒப்புக்கொள்கிறீர்கள்.',
      question: 'உங்கள் வழிகாட்டி உங்களைத் தொடர்புகொள்கிறார், அல்லது அறக்கட்டளை ஒரு கருத்தரங்குக்கு அழைக்கிறது. நீங்கள்…',
      options: [
        { text: 'புறக்கணிக்கலாம்.', correct: false },
        { text: 'வழிகாட்டியுடன் நியாயமான தொடர்பில் இருந்து, அழைக்கப்படும்போது பங்கேற்பேன்.', correct: true },
        { text: 'பணம் கொடுத்தால் மட்டும் பதிலளிப்பேன்.', correct: false },
      ],
      why: 'சரி — வழிகாட்டியும் நடவடிக்கைகளும் நீங்கள் வெற்றிபெற உதவவே; நியாயமான தொடர்பும் பங்கேற்பும் உங்கள் பங்கு.',
    },
    {
      tag: 'உங்கள் பங்கை நிறைவேற்றாவிட்டால்',
      plain: 'ஒப்பந்தத்தைப் பின்பற்றத் தவறினால், தவறான தகவல் கொடுத்தால், அல்லது உதவித்தொகையைத் தவறாகப் பயன்படுத்தினால், அறக்கட்டளை எதிர்கால உதவியை இடைநிறுத்தலாம் அல்லது நிறுத்திவைக்கலாம். பதிலளிக்க உங்களுக்கு எப்போதும் முதலில் நியாயமான வாய்ப்பு வழங்கப்படும்.',
      question: 'அறக்கட்டளை உங்கள் உதவியை இடைநிறுத்தவோ நிறுத்திவைக்கவோ முடியுமா? பதிலளிக்க வாய்ப்புக் கிடைக்குமா?',
      options: [
        { text: 'எந்தக் காரணத்திற்காகவும் ஒருபோதும் இல்லை.', correct: false },
        { text: 'ஆம் — இணங்காமை, தவறான தகவல் அல்லது தவறான பயன்பாட்டிற்காக; ஆனால் பதிலளிக்க நியாயமான வாய்ப்புக்குப் பிறகே.', correct: true },
        { text: 'ஆம் — எந்த நேரத்திலும், எந்த விளக்கமும் இல்லாமல்.', correct: false },
      ],
      why: 'சரி — இடைநிறுத்தமோ நிறுத்திவைப்போ காரணத்திற்காக மட்டுமே (இணங்காமை, தவறான தகவல், தவறான பயன்பாடு); பதிலளிக்க உங்களுக்கு எப்போதும் முதலில் நியாயமான வாய்ப்பு உண்டு.',
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
