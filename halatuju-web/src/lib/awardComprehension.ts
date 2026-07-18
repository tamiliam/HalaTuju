// Award comprehension quiz — UI chrome for the "Understand" step of /scholarship/award.
//
// The QUESTIONS are now served by the API from the org's active contract template
// (Sprint 4 — see AwardComprehensionQuiz.tsx + /scholarship/award/comprehension-quiz/);
// the static CHECKPOINTS that used to live here were captured in the seed fixture and
// removed. Only the surrounding chrome (intro / buttons / footnote / load + retake
// states) stays here. Gamified: a wrong answer is never penalised.
// en is final; ms is a working translation; ta is a first draft for the owner's refine.

export type Locale = 'en' | 'ms' | 'ta'

type Localised<T> = Record<Locale, T>

/** UI chrome strings for the quiz (the questions come from the API). The intro is
 *  donor-anonymous and amount-agnostic — the page already shows the particulars. */
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
  loading: string
  loadError: string
  retry: string
  versionChanged: string
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
    loading: 'Loading the key terms…',
    loadError: 'We couldn’t load the questions just now. Please try again.',
    retry: 'Try again',
    versionChanged: 'The agreement was updated — please review the key terms again.',
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
    loading: 'Memuatkan terma utama…',
    loadError: 'Kami tidak dapat memuatkan soalan buat masa ini. Sila cuba lagi.',
    retry: 'Cuba lagi',
    versionChanged: 'Perjanjian telah dikemas kini — sila semak semula terma utama.',
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
    loading: 'முக்கிய நிபந்தனைகளை ஏற்றுகிறது…',
    loadError: 'இப்போது கேள்விகளை ஏற்ற முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
    retry: 'மீண்டும் முயற்சி',
    versionChanged: 'ஒப்பந்தம் புதுப்பிக்கப்பட்டது — முக்கிய நிபந்தனைகளை மீண்டும் பாருங்கள்.',
  },
}

export function quizUiFor(locale: string) {
  return QUIZ_UI[(locale as Locale)] ?? QUIZ_UI.en
}
