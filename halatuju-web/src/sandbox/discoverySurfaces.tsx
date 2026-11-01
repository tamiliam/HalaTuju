'use client'

/**
 * Student discovery, mounted for mobile-check and the owner's phone review (Mobile M3).
 *
 * Kept out of `surfaces.tsx` (on the oversize ledger); `SURFACES` spreads these in, and
 * `mobile-check/targets.ts` reads this file's list too. Every surface mounts the REAL component with
 * fixtures — the saved list and compare and the report are pure views (their pages fetch and hand the
 * data in), so nothing here signs in or touches the network. The saved surfaces wrap a synthetic
 * `AuthContext` (never `AuthProvider`, which would mint a real anonymous user). mobile-check runs each
 * at 360 and 390 px in English, Malay and Tamil.
 */
import { useState, type ReactNode } from 'react'
import SearchFilterSheet, { type FacetGroup } from '@/components/search/SearchFilterSheet'
import SavedCourseCard from '@/components/saved/SavedCourseCard'
import SavedCompareView, { CompareBar, type CompareData } from '@/components/saved/SavedCompare'
import ReportView from '@/components/ReportView'
import type { SavedCourseWithStatus } from '@/lib/api'
import { AuthContext } from '@/lib/auth-context'

/** Same shape as `SURFACES` takes (written out: importing it back would close an import loop). */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode }

function SignedIn({ children }: { children: ReactNode }) {
  return (
    <AuthContext.Provider value={{
      status: 'ready', isAuthenticated: true, isAnonymous: false, hasSession: true,
      token: 'sandbox-not-a-real-token', profile: null, showAuthGate: () => {},
      session: { user: { email: 'pelajar@contoh.invalid', user_metadata: { full_name: 'Kavitha Raman' } } },
    } as never}>
      {children}
    </AuthContext.Provider>
  )
}

const STATES = ['Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan', 'Pahang', 'Perak', 'Perlis',
  'Pulau Pinang', 'Sabah', 'Sarawak', 'Selangor', 'Terengganu', 'W.P. Kuala Lumpur', 'W.P. Labuan', 'W.P. Putrajaya']
const TYPES: [string, string][] = [['kkom', 'Kolej Komuniti'], ['matric', 'Kolej Matrikulasi'], ['tvet_other', 'Latihan Kemahiran'],
  ['mara', 'MARA'], ['ilkbs', 'ILKBS'], ['iljtm', 'ILJTM'], ['pismp', 'IPGM'], ['poly', 'Politeknik'], ['stpm', 'Tingkatan 6'], ['ua', 'Universiti']]
const LEVELS = ['Asasi', 'Diploma', 'Ijazah Sarjana Muda', 'Sijil', 'Sijil Kemahiran Malaysia']
const FIELDS = ['Kejuruteraan Mekanikal', 'Kejuruteraan Elektrik & Elektronik', 'Teknologi Maklumat', 'Perakaunan',
  'Pengurusan Perniagaan', 'Perhotelan & Pelancongan', 'Seni Bina & Ukur', 'Pertanian', 'Kesihatan', 'Pendidikan']

/** The phone filter sheet, open, with SPM / Politeknik / Selangor picked and every group present. */
function FilterSheetSurface() {
  const [v, setV] = useState<Record<string, string>>({ qualification: 'SPM', type: 'poly', state: 'Selangor' })
  const [open, setOpen] = useState(true)
  const set = (key: string) => (value: string) => setV((s) => ({ ...s, [key]: value }))
  const opt = (x: string) => ({ value: x, label: x })
  const groups: FacetGroup[] = [
    { key: 'qualification', title: 'Qualification', value: v.qualification ?? '', onChange: set('qualification'), options: ['SPM', 'STPM'].map(opt) },
    { key: 'type', title: 'Institution Type', value: v.type ?? '', onChange: set('type'), options: TYPES.map(([value, label]) => ({ value, label })) },
    { key: 'level', title: 'Course Level', value: v.level ?? '', onChange: set('level'), options: LEVELS.map(opt) },
    { key: 'state', title: 'State', value: v.state ?? '', onChange: set('state'), collapseAfter: 6, options: STATES.map(opt) },
    { key: 'field', title: 'Field', value: v.field ?? '', onChange: set('field'), collapseAfter: 6, options: FIELDS.map(opt) },
  ]
  const picked = Object.values(v).filter(Boolean).length
  return (
    <div className="min-h-[60dvh] bg-ground-50 p-4">
      <button type="button" onClick={() => setOpen(true)}
        className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-sm font-medium">
        Filters · {picked}
      </button>
      <SearchFilterSheet open={open} onClose={() => setOpen(false)} groups={groups}
        resultCount={128} onClear={() => setV({})} canClear={picked > 0} />
    </div>
  )
}

const course = (id: string, name: string, inst: string, level: string, field: string, status: string): SavedCourseWithStatus => ({
  course_id: id, course: name, institution_name: inst, level, field, field_key: '', interest_status: status, course_type: 'spm',
} as unknown as SavedCourseWithStatus)

const SAVED = [
  course('POLY-DIP-019', 'Diploma Kejuruteraan Mekanikal', 'Politeknik Ungku Omar', 'Diploma', 'Kejuruteraan', 'applied'),
  course('POLY-DIP-044', 'Diploma Teknologi Maklumat (Pengaturcaraan)', 'Politeknik Sultan Salahuddin Abdul Aziz Shah', 'Diploma', 'Teknologi Maklumat', 'interested'),
  course('UM-ASASI-07', 'Asasi Sains Komputer', 'Universiti Malaya', 'Asasi', 'Sains Komputer', 'got_offer'),
]

/** The saved list as a signed-in student sees it, two courses ticked for compare. */
function SavedListSurface() {
  const [list, setList] = useState(SAVED)
  const [picked, setPicked] = useState(new Set(['POLY-DIP-019', 'POLY-DIP-044']))
  const toggle = (id: string) => setPicked((p) => {
    const n = new Set(p)
    if (n.has(id)) n.delete(id); else if (n.size < 3) n.add(id)
    return n
  })
  return (
    <SignedIn>
      <div className="mx-auto max-w-3xl bg-ground-50 px-4 pt-6">
        <p className="mb-3 text-sm text-ground-500">Tick 2 or 3 courses to compare them side by side.</p>
        <div className="grid gap-4">
          {list.map((c) => (
            <SavedCourseCard key={c.course_id} course={c} href={`/course/${c.course_id}`}
              subtitle={[c.institution_name, c.level, c.field].filter(Boolean).join(' · ')}
              selected={picked.has(c.course_id)} updating={false}
              onToggleSelect={() => toggle(c.course_id)}
              onRemove={() => setList((l) => l.filter((x) => x.course_id !== c.course_id))}
              onStatus={(s) => setList((l) => l.map((x) => x.course_id === c.course_id
                ? { ...x, interest_status: x.interest_status === s ? 'interested' : s } : x))} />
          ))}
        </div>
        <div className="h-24" />
        <CompareBar count={picked.size} onCancel={() => setPicked(new Set())} onCompare={() => {}} />
      </div>
    </SignedIn>
  )
}

const COMPARE: CompareData[] = [
  { course_id: 'POLY-DIP-019', name: 'Diploma Kejuruteraan Mekanikal', level: 'Diploma', field: 'Kejuruteraan',
    institution: 'Politeknik Ungku Omar', state: 'Perak', type: 'Politeknik Premier', fees: 'RM200', allowance: '—',
    merit: '72.4', semesters: '6', courseType: 'spm',
    requirements: ['Warganegara Malaysia', 'Lulus SPM dengan 3 kepujian', 'Kepujian Matematik'] },
  { course_id: 'POLY-DIP-044', name: 'Diploma Teknologi Maklumat (Pengaturcaraan)', level: 'Diploma', field: 'Teknologi Maklumat',
    institution: 'Politeknik Sultan Salahuddin Abdul Aziz Shah', state: 'Selangor', type: 'Politeknik Premier', fees: 'RM200',
    allowance: 'RM100/month', merit: '80.1', semesters: '6', courseType: 'spm',
    requirements: ['Warganegara Malaysia', 'Lulus SPM dengan 3 kepujian', 'Lulus Bahasa Inggeris'] },
  { course_id: 'UM-ASASI-07', name: 'Asasi Sains Komputer', level: 'Asasi', field: 'Sains Komputer',
    institution: 'Universiti Malaya', state: 'W.P. Kuala Lumpur', type: 'Universiti Awam', fees: 'RM1,200', allowance: '—',
    merit: '92.0', semesters: '2', courseType: 'spm',
    requirements: ['Warganegara Malaysia', 'Kepujian Matematik Tambahan', 'Kepujian Fizik'] },
]

const REPORT = {
  report_id: 1, model_used: 'sandbox', summary: '', created_at: '2026-10-30T09:00:00Z',
  title: 'Laporan Kerjaya: Kavitha Raman',
  markdown: [
    '## Ringkasan', '',
    'Kekuatan anda dalam Matematik dan Sains menunjukkan minat yang jelas terhadap bidang teknikal. '
      + 'Berikut ialah tiga laluan yang paling sesuai, dengan sebab dan langkah seterusnya.', '',
    '## Laluan yang dicadangkan', '',
    '1. **Diploma Kejuruteraan Mekanikal** — Politeknik Ungku Omar, Perak.',
    '2. **Diploma Teknologi Maklumat (Pengaturcaraan)** — Politeknik Sultan Salahuddin Abdul Aziz Shah.',
    '3. **Asasi Sains Komputer** — Universiti Malaya.', '',
    '### Langkah seterusnya', '',
    '- Semak tarikh tutup permohonan UPU di https://upu.mohe.gov.my/portal/permohonan-lepasan-spm-dan-setaraf',
    '- Bincang pilihan anda dengan kaunselor sekolah sebelum menghantar permohonan.',
  ].join('\n'),
}

export const DISCOVERY_SURFACES: Surface[] = [
  {
    slug: 'search-filters',
    title: 'Course search — filter sheet open',
    note: 'The phone filters (Mobile M3): one group of 44 px chips per facet in the shared Sheet, the '
      + 'long ones behind "Show all", and Clear / "Show 128 courses" pinned at the foot.',
    render: () => <FilterSheetSurface />,
  },
  {
    slug: 'saved-list',
    title: 'Saved courses — two ticked for compare',
    note: 'A signed-in student\'s saved list: status pills that wrap in Tamil, a 44 px remove button, '
      + 'a "Compare" tick box with its word, and the compare bar stuck to the foot.',
    render: () => <SavedListSurface />,
  },
  {
    slug: 'saved-compare',
    title: 'Saved courses — compare, three picked',
    note: 'Layout B on a phone: two columns, each row\'s label above its two values, and "Compare with" '
      + 'to choose the second course. From md, the side-by-side table.',
    render: () => (
      <SignedIn>
        <div className="mx-auto max-w-5xl bg-ground-50 px-4 py-6">
          <SavedCompareView data={COMPARE} loading={false} onBack={() => {}} />
        </div>
      </SignedIn>
    ),
  },
  {
    slug: 'report',
    title: 'Career report',
    note: 'The report a student opens from her dashboard: 16 px gutters on a phone, a 44 px Download '
      + 'PDF button, and a long link that wraps instead of widening the page.',
    render: () => <div className="bg-ground-50"><ReportView report={REPORT} /></div>,
  },
]
