/**
 * Synthetic application data for the sandbox.
 *
 * ⚠ THESE ARE TYPED AGAINST THE REAL INTERFACES ON PURPOSE. A JSON fixture would rot silently the
 * first time a payload changed, and the sandbox would keep showing a screen that no longer exists —
 * which is worse than having no sandbox, because a designer would approve it. Typed, `tsc` breaks
 * the moment the contract moves, and whoever changed the payload fixes the fixture in the same
 * commit. The compiler IS the anti-drift mechanism.
 *
 * ⚠ NOTHING HERE MAY RESEMBLE A REAL PERSON. `sandbox-safety.test.ts` enforces it mechanically:
 * no NRIC-shaped digits, every email on a `.invalid` domain, and no name from the live roster.
 * Identity numbers render as `XXXXXX-XX-XXXX` rather than plausible digits — a designer seeing
 * that knows instantly it is not somebody's real card, and no screenshot of this can ever be
 * mistaken for a leak. The names use *contoh* / *teladan* ("example", "model") for the same
 * reason: they lay out like real Malaysian names and read as obviously synthetic to anyone who
 * speaks the language.
 */
import type {
  ApplicantDocument,
  ApplicationCompleteness,
  ApplicationRequirements,
  ConsentStatus,
  FundingNeed,
  ScholarshipApplication,
} from '@/lib/api'

/** Renders in place of any identity number. Deliberately not digit-shaped. */
export const FAKE_NRIC = 'XXXXXX-XX-XXXX'

const completeness: ApplicationCompleteness = {
  quiz_done: true,
  details_done: true,
  funding_done: true,
  documents_done: false,
  consent_done: true,
  address_done: true,
  family_done: true,
  complete: false,
}

/**
 * What BrightPath asks for today — the platform defaults, resolved server-side.
 *
 * ⚠ Kept in the SAME ORDER and shape the API returns (sorted lists), so a designer is looking at
 * a real payload rather than a tidied one. `income_proof` is the aggregate switch over the whole
 * household-income route, not a card.
 */
const fullRequirements: ApplicationRequirements = {
  documents: {
    required: ['ic', 'income_proof', 'offer_letter', 'results_slip'],
    optional: ['electricity_bill', 'photo', 'school_leaving_cert', 'statement_of_intent',
               'water_bill'],
  },
}

/** A leaner programme: identity and results only, no means test, one optional extra. */
const leanRequirements: ApplicationRequirements = {
  documents: {
    required: ['ic', 'results_slip'],
    optional: ['statement_of_intent'],
  },
}

const fundingNeed: FundingNeed = {
  categories: ['tuition', 'transport', 'living'],
  funding_note: 'Yuran pengajian dan pengangkutan harian ke kampus.',
  programme_months: 36,
}

/**
 * One application, mid-flight: submitted, consent given, documents still outstanding. That state
 * is chosen deliberately — a completed application renders every card in its resting state and
 * shows a designer nothing about the screens people actually sit in.
 */
export const sandboxApplication: ScholarshipApplication = {
  id: 1001,
  cohort_code: 'sandbox-2026',
  cohort_name: 'Sandbox Intake 2026',
  profile_id: 'sandbox-profile-0001',
  exam_type: 'spm',
  spm_a_count: 6,
  stpm_pngk: null,
  household_income: 2400,
  household_size: 6,
  receives_str: true,
  receives_jkm: false,
  intended_pathway: 'diploma',
  intends_tertiary_2026: true,
  consent_to_contact: true,
  status: 'submitted',
  bucket: 'shortlist',
  shortlist_reason: '',
  maintenance_substate: 'on_track',
  closure_reason: '',
  acknowledged_at: '2026-02-02T09:00:00Z',
  submitted_at: '2026-02-01T08:30:00Z',
  updated_at: '2026-02-10T11:15:00Z',
  profile_completed_at: '2026-02-01T08:30:00Z',
  info_request_note: '',
  info_requested_at: null,

  aspirations: 'Saya ingin menjadi jurutera awam dan membantu membina kemudahan air bersih di kampung saya.',
  plans: 'Menyambung diploma kejuruteraan awam, kemudian bekerja sambil menyambung ijazah.',
  fears: 'Saya bimbang kos pengangkutan ke kampus setiap hari melebihi kemampuan keluarga.',
  justification: 'Pendapatan keluarga bergantung pada kerja harian bapa yang tidak menentu.',

  first_in_family: true,
  parents_occupation: 'Buruh binaan; suri rumah',
  siblings_studying_count: 2,
  family_context: 'Enam orang dalam satu rumah sewa dua bilik.',
  daily_life: 'Saya membantu ibu menjaga adik selepas sekolah sebelum mengulang kaji pada waktu malam.',

  father_name: 'Ahmad bin Contoh',
  father_occupation: 'construction_worker',
  father_occupation_other: '',
  mother_name: 'Siti binti Teladan',
  mother_occupation: 'homemaker',
  mother_occupation_other: '',
  other_family_members: [
    { role: 'brother', occupation: 'student' },
    { role: 'sister', occupation: 'student' },
  ],

  income_route: 'str',
  income_earner: 'father',
  income_working_members: ['father'],
  earner_work_status: '',
  household_other_earners: 0,
  siblings_in_school: 2,
  siblings_in_tertiary: 0,

  address: 'No. 12, Jalan Contoh 3, Taman Teladan',
  postal_code: '43000',
  city: 'Kajang',
  preferred_state: 'Selangor',

  funding_need: fundingNeed,
  completeness,
  requirements: fullRequirements,
  notify_email: 'aisyah@sandbox.invalid',
  contact_phone: '+60000000000',
  form_data: {},
}

/**
 * The SAME application as configured by a leaner programme — no means test, no offer letter, and
 * the extras trimmed to one.
 *
 * This exists so the sandbox can show both ends of Layer 0 side by side. A designer looking only
 * at the full form would style a page that half our tenants never render, and the reviewer of a
 * configuration sprint would have nothing to check the "less" case against except a passing test.
 *
 * Only `requirements` differs from `sandboxApplication` — spread, not retyped, so the two can
 * never drift into being two different students.
 */
export const sandboxApplicationLeanProgramme: ScholarshipApplication = {
  ...sandboxApplication,
  id: 1002,
  cohort_name: 'Sandbox Intake 2026 — lean programme',
  requirements: leanRequirements,
}

/**
 * Documents in mixed states — uploaded and verified, uploaded and pending, and outright missing —
 * because a designer needs to see the empty card, the busy card and the settled card side by side.
 * `authenticity` is populated on the IC only; that is how the real payload behaves.
 */
export const sandboxDocuments: ApplicantDocument[] = [
  {
    id: 5001,
    doc_type: 'ic',
    household_member: '',
    original_filename: 'kad-pengenalan.jpg',
    content_type: 'image/jpeg',
    size: 842_113,
    verification_status: 'verified',
    uploaded_at: '2026-02-01T09:05:00Z',
    download_url: null,
    vision_nric: FAKE_NRIC,
    vision_name: 'AISYAH BINTI CONTOH',
    vision_address: 'NO. 12, JALAN CONTOH 3, TAMAN TELADAN',
    vision_run_at: '2026-02-01T09:06:00Z',
    vision_error: '',
    vision_nric_verdict: 'match',
    vision_name_verdict: 'match',
    authenticity: { status: 'genuine', reason: 'Full card visible, both sides legible.' },
    vision_name_match: 'found',
    vision_address_match: 'found',
  },
  {
    id: 5002,
    doc_type: 'results_slip',
    household_member: '',
    original_filename: 'keputusan-spm.pdf',
    content_type: 'application/pdf',
    size: 331_902,
    verification_status: 'pending',
    uploaded_at: '2026-02-03T14:40:00Z',
    download_url: null,
    vision_nric: '',
    vision_name: '',
    vision_address: '',
    vision_run_at: null,
    vision_error: '',
    vision_nric_verdict: '',
    vision_name_verdict: '',
    vision_name_match: '',
    vision_address_match: '',
  },
  {
    id: 5003,
    doc_type: 'str',
    household_member: 'father',
    original_filename: 'str-kelulusan.pdf',
    content_type: 'application/pdf',
    size: 118_440,
    verification_status: 'verified',
    uploaded_at: '2026-02-04T10:12:00Z',
    download_url: null,
    vision_nric: '',
    vision_name: 'AHMAD BIN CONTOH',
    vision_address: '',
    vision_run_at: '2026-02-04T10:13:00Z',
    vision_error: '',
    vision_nric_verdict: '',
    vision_name_verdict: 'match',
    authenticity: { status: 'genuine', reason: 'Approval status visible.' },
    vision_name_match: 'found',
    vision_address_match: '',
  },
]

export const sandboxConsent: ConsentStatus = {
  is_minor: false,
  consent_version: 'v3',
  consents: [
    {
      id: 7001,
      consent_type: 'data_processing',
      version: 'v3',
      granted_by: 'self',
      guardian_name: '',
      guardian_relationship: '',
      guardian_nric: '',
      is_active: true,
      granted_at: '2026-02-01T08:29:00Z',
    },
  ],
  student_name: 'Aisyah binti Contoh',
  student_nric: FAKE_NRIC,
  student_gender: 'female',
  parent_ic_vision_nric: '',
  parent_ic_vision_name: '',
  // Empty = consent is ready to give. The blocked state is worth seeing too, so the
  // Documents surface swaps this for `blockedConsent` below.
  blockers: [],
}

/** The same consent state with work outstanding — the checklist a student actually meets first. */
export const sandboxConsentBlocked: ConsentStatus = {
  ...sandboxConsent,
  blockers: ['results_slip_missing', 'income_proof_missing'],
}
