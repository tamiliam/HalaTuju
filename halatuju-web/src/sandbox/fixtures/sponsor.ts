/**
 * Synthetic sponsor-portal data for the sandbox.
 *
 * ⚠ Same rules as `scholarship.ts`: typed against the real interfaces so `tsc` breaks when the
 * payload moves, and nothing here may resemble a real person. A pool card is anonymous by design —
 * it carries a reference, never a name — so the risk is lower than the student fixtures, but the
 * school and institution names still use *contoh* / *teladan* and the states are real ones chosen
 * to spread the cards apart visually rather than to describe anybody.
 */
import type { SponsorPoolCard } from '@/lib/api'

/**
 * Five cards, chosen to put every conditional state on screen at once — because a repaint sprint
 * is reviewed by LOOKING, and a grid of five identical happy cards shows a designer nothing.
 *
 * Covered: verified vs unverified enrolment, a card with artwork and one without, a funded card
 * beside unfunded ones, a long blurb against an empty one, and a future reporting date against a
 * missing one (the countdown appears and disappears on that alone).
 *
 * ⚠ THE REPORTING DATES ROT, AND THAT IS THE LESSER EVIL. A far-future date (2099) never expires
 * but renders "Starts in 26,697 days", which a designer reads as a bug and which tells them
 * nothing about how the chip really looks. These are near-dated instead, so the countdown reads
 * like a real one. When they pass, the chip simply stops rendering — a state card 2 already
 * covers — so a rotted fixture degrades to a legitimate screen rather than a broken one.
 * Refresh them when they go stale; the sandbox is a design tool, not a golden master.
 *
 * ⚠ `portfolio_status` covers three badge tones on purpose, `graduated` among them — that badge
 * moved off indigo onto a deeper `positive` in this sprint and is the one deliberate visual change
 * in it, so it has to be visible to whoever reviews.
 *
 * ⚠ AND NOTE WHAT TYPING THIS CAUGHT. The first draft omitted `course_href`, `funded`,
 * `portfolio_status` and `supported_semesters`; `next build` refused it. The jsdom test at
 * `students/page.test.tsx` carries the same gap and has never complained, because a cast in a test
 * silences the compiler. A typed fixture is the anti-drift mechanism the sandbox rests on.
 */
export const sandboxPool: SponsorPoolCard[] = [
  {
    id: 901, ref: 'S-CTH-01', state: 'Perak', school: 'SMK Contoh Satu',
    field: 'engineering', course: 'Diploma Kejuruteraan Mekanikal',
    academic: 'SPM · 7A', institution: 'Politeknik Teladan',
    blurb: 'Membaiki motosikal jiran sejak umur 13 tahun, dan mahu menjadi jurutera.',
    funding_categories: ['tuition', 'transport'], programme_months: 24,
    award_amount: '3000', funded_amount: '0',
    progress_state: null, support_status: null, enrolment_verified: true,
    field_image_slug: 'kejuruteraan', reporting_date: '2026-09-01',
    course_href: '/course/DIP-MEK', funded: false, portfolio_status: null, supported_semesters: 4,
  },
  {
    id: 902, ref: 'S-CTH-02', state: 'Kedah', school: 'SMK Contoh Dua',
    field: 'health', course: 'Diploma Kejururawatan',
    academic: 'SPM · 5A', institution: 'Kolej Teladan',
    // Deliberately blank: a card with no blurb and no artwork is the state most likely to be
    // forgotten in a redesign, and it is common on real data.
    blurb: '', funding_categories: [], programme_months: 36,
    award_amount: '2000', funded_amount: '0',
    progress_state: null, support_status: null, enrolment_verified: false,
    field_image_slug: '', reporting_date: null,
    course_href: '', funded: false, portfolio_status: null, supported_semesters: null,
  },
  {
    id: 903, ref: 'S-CTH-03', state: 'Selangor', school: 'SMK Contoh Tiga',
    field: 'computing', course: 'Asasi Sains Komputer',
    academic: 'SPM · 8A', institution: 'Universiti Teladan',
    blurb: 'Belajar membuat laman web daripada video, dan kini mengajar adiknya.',
    funding_categories: ['tuition', 'living', 'device'], programme_months: 12,
    award_amount: '3000', funded_amount: '3000',   // fully funded — the settled state
    progress_state: null, support_status: null, enrolment_verified: true,
    field_image_slug: 'teknologi-maklumat', reporting_date: '2026-10-15',
    course_href: '/course/ASASI-SK', funded: true, portfolio_status: 'on_track', supported_semesters: 2,
  },
  {
    id: 904, ref: 'S-CTH-04', state: 'Johor', school: 'SMK Contoh Empat',
    field: 'education', course: 'PISMP Pendidikan Rendah',
    academic: 'SPM · 6A', institution: 'Institut Pendidikan Teladan',
    blurb: 'Mahu mengajar di sekolah yang sama seperti tempat dia belajar.',
    funding_categories: ['tuition'], programme_months: 48,
    award_amount: '3000', funded_amount: '1500',   // part-funded — the progress rail mid-way
    progress_state: null, support_status: null, enrolment_verified: true,
    field_image_slug: 'pendidikan', reporting_date: '2026-08-20',
    course_href: '/course/PISMP-PR', funded: false, portfolio_status: 'graduated', supported_semesters: 8,
  },
  {
    id: 905, ref: 'S-CTH-05', state: 'Pulau Pinang', school: 'SMK Contoh Lima',
    field: 'business', course: 'Diploma Perakaunan',
    academic: 'STPM · PNGK 3.4', institution: 'Kolej Komuniti Teladan',
    blurb: 'Menguruskan kedai runcit keluarga selepas waktu sekolah, dan menyimpan setiap resit.',
    funding_categories: ['tuition', 'living'], programme_months: 30,
    award_amount: '2500', funded_amount: '0',
    progress_state: null, support_status: null, enrolment_verified: false,
    field_image_slug: 'perniagaan', reporting_date: '2026-12-01',
    course_href: '', funded: false, portfolio_status: 'needs_attention', supported_semesters: 5,
  },
]
