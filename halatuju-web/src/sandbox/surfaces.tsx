'use client'

/**
 * The list of screens the sandbox offers, and how each one is mounted.
 *
 * ⚠ EVERY ENTRY MOUNTS A REAL COMPONENT. If a surface cannot be mounted without re-implementing
 * part of it, it does not belong here — fix the component so it can be mounted (usually by taking
 * its data as props), or leave the surface out. A hand-written approximation would be worse than
 * nothing: a designer would sign off on a screen that does not exist.
 *
 * `token` is a synthetic string, never a real session. It exists because the components take one;
 * the stubbed fetch ignores it, and there is no backend for it to reach.
 */
import { useState, type ReactNode } from 'react'
import ScholarshipDocuments from '@/components/ScholarshipDocuments'
import ScholarshipNextSteps from '@/components/ScholarshipNextSteps'
import ActionCentre from '@/components/ActionCentre'
import SponsorLanding from '@/components/SponsorLanding'
import SpecialConditions from '@/components/SpecialConditions'
import PathwayTrackCard, { type PathwayTrack } from '@/components/PathwayTrackCard'
import InfoBox from '@/components/InfoBox'
import ProgressStepper from '@/components/ProgressStepper'
import FilterPill from '@/components/FilterPill'
import Toggle from '@/components/Toggle'
import InfoTip from '@/components/InfoTip'
import VerifiedTick from '@/components/VerifiedTick'
import { FundingBar } from '@/components/FundingBar'
import { Pagination } from '@/components/Pagination'
import CourseCard from '@/components/CourseCard'
import CourseHeader from '@/components/CourseHeader'
import type { EligibleCourse } from '@/lib/api'
import ScholarshipApplyPage from '@/app/scholarship/apply/page'
import SponsorStudentsPage from '@/app/sponsor/(portal)/students/page'
import AdminProgrammeConfigPage from '@/app/admin/programme/page'
import { AuthContext } from '@/lib/auth-context'
import { AdminAuthContext } from '@/lib/admin-auth-context'
import { SponsorPortalContext } from '@/lib/sponsor-portal-context'
import {
  sandboxApplication, sandboxApplicationLeanProgramme, sandboxNoApplications,
  sandboxProfileFormSix, sandboxProfileSpm, sandboxProfileStpm,
  sandboxProgrammeConfiguration, sandboxProgrammeConfigurationLean,
  sandboxResolutionItems, sandboxResolutionItemsClear,
} from './fixtures/scholarship'
import { sandboxPool } from './fixtures/sponsor'

const SANDBOX_TOKEN = 'sandbox-not-a-real-token'

export interface Surface {
  slug: string
  title: string
  /** What a designer is looking at, and which state it is in — states are chosen, not accidental. */
  note: string
  render: () => ReactNode
  /**
   * Endpoint answers for THIS surface only, layered over the shared ones. Needed where two
   * screens want different answers from the same endpoint — see `setSurfaceRoutes`.
   */
  routes?: Record<string, () => unknown>
}

export const SURFACES: Surface[] = [
  {
    slug: 'documents',
    title: 'Documents',
    note:
      'The student’s upload surface, mid-flight: identity card verified, results slip pending, '
      + 'household income evidenced by an approved STR. The remaining cards are still empty.',
    render: () => (
      <ScholarshipDocuments token={SANDBOX_TOKEN} app={sandboxApplication} />
    ),
  },
  {
    slug: 'documents-lean',
    title: 'Documents — a leaner programme',
    note:
      'The SAME student, at an organisation that asks for less: identity card and results slip '
      + 'only, no household means test, and one optional extra. Nothing about this page is coded '
      + 'differently — it is the same component reading a different configuration, which is what '
      + 'Layer 0 buys. Style both: a tenant will land on each.',
    render: () => (
      <ScholarshipDocuments token={SANDBOX_TOKEN} app={sandboxApplicationLeanProgramme} />
    ),
  },
  {
    slug: 'application-steps',
    title: 'Application — the step wizard',
    note:
      'The pre-submit Step-4 wizard on the FULL programme: five steps in the rail, every '
      + 'story question drawn, the Funding step present. Layer 0 Sprint 4 made the questions '
      + 'configuration-driven; this is the baseline to compare the lean surface against.',
    render: () => (
      <ScholarshipNextSteps
        initialApp={{ ...sandboxApplication, status: 'shortlisted' }}
        token={SANDBOX_TOKEN}
      />
    ),
  },
  {
    slug: 'application-steps-lean',
    title: 'Application — the step wizard, leaner programme',
    note:
      'The SAME student at an organisation that switched questions off: the Funding step is '
      + 'gone from the rail (four steps — computed at render, never stored), and “Your story” '
      + 'no longer draws the daily-life or worries questions. Same component reading a '
      + 'different configuration — nothing about this page is coded differently.',
    render: () => (
      <ScholarshipNextSteps
        initialApp={{ ...sandboxApplicationLeanProgramme, status: 'shortlisted' }}
        token={SANDBOX_TOKEN}
      />
    ),
  },
  {
    slug: 'apply-results',
    title: 'Apply — My Results (sat SPM)',
    note:
      'Step 3 of the application form, for a student whose SPM results are on file. The step '
      + 'DISPLAYS results and offers to correct them; it never collects them — the only place '
      + 'they are entered is the course-guide onboarding, which writes the same profile. Click '
      + '“My Results” in the step rail.',
    routes: { '/api/v1/scholarship/applications/': () => sandboxNoApplications },
    render: () => (
      <WithAuth profile={sandboxProfileSpm}>
        <ScholarshipApplyPage />
      </WithAuth>
    ),
  },
  {
    slug: 'apply-results-stpm',
    title: 'Apply — My Results (sat STPM)',
    note:
      'The same step for a student who has sat STPM: the count of A’s is replaced by the PNGK. '
      + 'Same component, same code path — the branch is `exam_type`.',
    routes: { '/api/v1/scholarship/applications/': () => sandboxNoApplications },
    render: () => (
      <WithAuth profile={sandboxProfileStpm}>
        <ScholarshipApplyPage />
      </WithAuth>
    ),
  },
  {
    slug: 'apply-results-form-six',
    title: 'Apply — My Results (Form Six: the defect)',
    note:
      'A Form Six student: ten SPM grades on file, sitting STPM now, so she answered “STPM” at '
      + '“Choose Your Exam” — the exam she is heading FOR. The step looks only where the declared '
      + 'exam points, finds no CGPA, and tells her WE DO NOT HAVE HER RESULTS while they sit in '
      + 'the database. The button it offers goes back to the screen that produced the '
      + 'declaration. One live applicant is in this state. Compare it against the first surface: '
      + 'same student data, one field different.',
    routes: { '/api/v1/scholarship/applications/': () => sandboxNoApplications },
    render: () => (
      <WithAuth profile={sandboxProfileFormSix}>
        <ScholarshipApplyPage />
      </WithAuth>
    ),
  },
  {
    slug: 'sponsor-browse',
    title: 'Sponsor — browse students',
    note:
      'The sponsor’s discovery grid, and the FIRST surface converted onto the theme tokens '
      + '(Layer 1 F1). Five cards chosen to put every conditional state on screen at once: '
      + 'verified against unverified enrolment, artwork against none, fully funded against '
      + 'part-funded against untouched, a written blurb against an empty one, and a reporting '
      + 'date against a missing one. Check it in BOTH modes — this is the surface the sprint '
      + 'claims is correct in dark.',
    render: () => (
      <WithSponsorPortal>
        <SponsorStudentsPage />
      </WithSponsorPortal>
    ),
  },
  {
    slug: 'action-centre',
    title: 'Action Centre — tasks outstanding',
    note:
      'The post-submit task list, and the largest single surface Layer 1 F2a repainted (82 '
      + 'colour utilities). Every tone the sprint touches is on screen at once: two open tasks, '
      + 'the info-toned "a person is looking at this" card that replaces the upload prompt when a '
      + 'ticket is escalated, and two finished tasks as positive Done cards. The progress bar is '
      + 'BRAND, not a tone — a tenant’s colour reaches it. Check both modes.',
    routes: {
      '/api/v1/scholarship/resolution-items/': () => sandboxResolutionItems,
    },
    render: () => (
      <WithAuth profile={sandboxProfileSpm}>
        <ActionCentre token={SANDBOX_TOKEN} studentName="Aina Contoh" applicationId={1} />
      </WithAuth>
    ),
  },
  {
    slug: 'action-centre-clear',
    title: 'Action Centre — nothing left to do',
    note:
      'The same component with an empty open list: the calm "we’ll be in touch" card, which '
      + 'is a different card entirely rather than an empty version of the one above. Its ground '
      + 'and its positive Done cards are the whole surface, so it is where a wrong ground tone '
      + 'shows up most plainly in dark.',
    routes: {
      '/api/v1/scholarship/resolution-items/': () => sandboxResolutionItemsClear,
    },
    render: () => (
      <WithAuth profile={sandboxProfileSpm}>
        <ActionCentre token={SANDBOX_TOKEN} studentName="Aina Contoh" applicationId={1} />
      </WithAuth>
    ),
  },
  {
    slug: 'pieces',
    title: 'The small shared pieces',
    note:
      'The rest of F2a’s components, mounted for real and side by side, because each is too '
      + 'small to justify a surface of its own and together they carry the whole tone vocabulary. '
      + 'InfoBox is the piece that NAMES it — success / info / warning / block — so if its four '
      + 'boxes read correctly in dark, the vocabulary is right; if they do not, nothing else will '
      + 'be. The tick and the funding bar are the two hand-corrections this sprint made.',
    render: () => <PiecesGallery />,
  },
  {
    slug: 'sponsor-landing',
    title: 'Sponsor landing — the public page',
    note:
      'The public "become a sponsor" page, repainted in F2b. The two call-to-action buttons and '
      + 'the numbered step circles were corrected BY HAND from the info tone to the brand — the '
      + 'codemod was right that they were blue and wrong that they meant "information", which is '
      + 'the same defect F1 found on the sponsor portal. In dark they must read as the tenant’s '
      + 'colour, not as a pale blue notice.',
    render: () => (
      <WithAuth profile={sandboxProfileSpm}>
        <SponsorLanding count={12} />
      </WithAuth>
    ),
  },
  {
    slug: 'category-colours',
    title: 'Category colours — the fifth family',
    note:
      'Every colour here identifies a CATEGORY — a field of study, an institution type, an entry '
      + 'condition — and its only job is to differ from its neighbours. F2b could not convert them: '
      + 'the four tones each mean something, so a family rename collapsed two institution types '
      + 'onto one colour and claimed "Science" is a success. F2c added an eighth-swatch CATEGORY '
      + 'family instead (owner decision), three roles each — surface, ink, dot — with dark as a '
      + 'ROLE SWAP rather than a mirror, so a chip stays a chip. Check both modes: all seven '
      + 'conditions and all six badges must stay tellable apart in each. Two pairs that were '
      + 'ALREADY identical before any of this (ua/pismp, and no-colourblindness/no-disability) are '
      + 'fixed here. The merit dot stays a TONE — it is a state, not a category.',
    render: () => <CategoryColours />,
  },
  {
    slug: 'course-guide',
    title: 'Course guide — the last surface (F6)',
    note:
      'The public course guide, the final repaint before the switch. Two things to check, and '
      + 'both need the cards SIDE BY SIDE. First: the eight institution types must stay tellable '
      + 'apart, in each mode — they are a category set, so their only job is to differ from each '
      + 'other, and F6 moved them into one module because the search grid and the course page had '
      + 'been describing them separately. Second: every LEVEL chip is grey on purpose. The two '
      + 'sets sit adjacent and together wanted thirteen swatches against a family of eight; the '
      + 'chip already reads “Diploma”, and an unrecognised level had ALWAYS been grey. The same '
      + 'reasoning made the seventeen STPM subject chips grey. If a later sprint wants either set '
      + 'coloured, the change is to --category-*, not to these files.',
    render: () => <CourseGuide />,
  },
  {
    slug: 'programme-config',
    title: 'Admin — what we ask for',
    note:
      'The org_admin’s Layer 0 screen (Sprint 5): every document and question the platform knows, '
      + 'with the programme’s choice on each row. Six rows are locked at Required by the platform '
      + 'and say so in muted text; the household-income row is tinted because it is a whole '
      + 'section, not one upload. 41 students are in flight, so the amber warning names them. '
      + 'Save wakes only on a real change. Content column only — the admin shell is not mounted.',
    routes: {
      '/api/v1/admin/scholarship/programme/configuration/': () => sandboxProgrammeConfiguration,
    },
    render: () => (
      <WithAdminAuth>
        <AdminProgrammeConfigPage />
      </WithAdminAuth>
    ),
  },
  {
    slug: 'programme-config-lean',
    title: 'Admin — what we ask for, a leaner programme',
    note:
      'The same screen for a programme that switched off everything it could: only the six '
      + 'locked rows are Required, nobody is in flight, so the warning is the calm one-liner. '
      + 'Style both — a tenant will land on each.',
    routes: {
      '/api/v1/admin/scholarship/programme/configuration/': () => sandboxProgrammeConfigurationLean,
    },
    render: () => (
      <WithAdminAuth>
        <AdminProgrammeConfigPage />
      </WithAdminAuth>
    ),
  },
]

/**
 * The portal pages read their data from a context rather than props, so the sandbox supplies that
 * context with fixtures instead of the network. `SponsorPortalContext` is exported for exactly this
 * — the page below is the REAL one, unmodified.
 *
 * Only the fields this page reads are filled. Casting a partial value is deliberate: filling
 * fourteen unrelated fields with nulls would suggest they are part of what this surface shows.
 */
/**
 * The signed-in student screens read their identity from `useAuth`, so the sandbox supplies that
 * context with a synthetic value. `AuthProvider` is deliberately NOT used: it mints an anonymous
 * Supabase user on mount, and a design review must not create real auth rows.
 *
 * Only the four fields these screens read are filled — `status`, `profile`, `token`, and the auth
 * gate they never open. Casting a partial value is the same deliberate choice made below.
 */
function WithAuth({ profile, children }: { profile: unknown; children: ReactNode }) {
  return (
    <AuthContext.Provider
      value={{ status: 'ready', profile, token: SANDBOX_TOKEN, showAuthGate: () => {} } as never}
    >
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Admin screens read their session from `useAdminAuth`. Same rule as `WithAuth`: the provider is
 * bypassed (it would call the live role endpoint), and only the fields the screen reads are set.
 * The role is an org_admin — the person "What we ask for" is built for.
 */
function WithAdminAuth({ children }: { children: ReactNode }) {
  return (
    <AdminAuthContext.Provider
      value={{
        session: null, token: SANDBOX_TOKEN, isLoading: false, isAdminAuthenticated: true,
        role: {
          is_admin: true, is_super_admin: false, role: 'org_admin', admin_id: 1,
          org_name: 'Yayasan Contoh', owning_org_id: 1, owning_org_name: 'Yayasan Contoh',
          admin_name: 'Pentadbir Contoh', reviewer_profile_complete: true,
        },
        refreshRole: async () => {},
      }}
    >
      {children}
    </AdminAuthContext.Provider>
  )
}

function WithSponsorPortal({ children }: { children: ReactNode }) {
  return (
    <SponsorPortalContext.Provider value={{ pool: sandboxPool } as never}>
      {children}
    </SponsorPortalContext.Provider>
  )
}

/**
 * F2a's small components, mounted for real, one row each.
 *
 * ⚠ This is a GALLERY, not a mock: every element below is the actual exported component with real
 * props. The layout around them is scaffolding — labels and spacing — and carries no colour of its
 * own beyond the ground, so nothing here can make a broken component look correct.
 */
/**
 * The colours F2b could NOT convert, mounted so the gap can be seen rather than described.
 *
 * ⚠ Every component below is the real one. The point of the surface is that in dark mode these
 * stay light — a category palette has no dark counterpart yet, because the product has no
 * categorical token family. That is an owner decision, not an oversight.
 */
const SANDBOX_TRACKS: PathwayTrack[] = [
  { id: '1', pathway: 'stpm', track: 'sains', meritScore: 88, meritLabel: 'High', collegeCount: 21 },
  { id: '2', pathway: 'stpm', track: 'sains_sosial', meritScore: 71, meritLabel: 'Fair', collegeCount: 34 },
  { id: '3', pathway: 'matric', track: 'perakaunan', meritScore: 64, meritLabel: 'Fair', collegeCount: 12 },
  { id: '4', pathway: 'matric', track: 'kejuruteraan', meritScore: 79, meritLabel: 'High', collegeCount: 18 },
]

function CategoryColours() {
  return (
    <div className="mx-auto max-w-4xl px-4">
      <h2 className="mb-1 text-lg font-semibold text-ground-900">Entry conditions</h2>
      <p className="mb-3 text-sm text-ground-500">
        Seven conditions, seven dot colours. None of them is a warning — “female applicants only”
        is a requirement, not an error — so none of them maps onto a tone.
      </p>
      <SpecialConditions
        reqInterview noColorblind reqMedicalFitness reqMale reqFemale single noDisability
      />

      <h2 className="mb-1 mt-8 text-lg font-semibold text-ground-900">Fields of study</h2>
      <p className="mb-3 text-sm text-ground-500">
        The badge on each card is one of five field colours, plus a sixth for the pathway.
        Converting by colour family would put two of them on the same token.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {SANDBOX_TRACKS.map((track) => <PathwayTrackCard key={track.id} track={track} />)}
      </div>
    </div>
  )
}

/**
 * F6's surface. The eight institution types are the sprint's whole visual argument, and they only
 * make it side by side — one card on its own says nothing about whether the set separates.
 */
const SANDBOX_COURSES: EligibleCourse[] = ([
  ['ua', 'Ijazah Sarjana Muda Kejuruteraan Awam', 'Ijazah Sarjana Muda', 'engineering'],
  ['poly', 'Diploma Teknologi Maklumat', 'Diploma', 'computing'],
  ['ilkbs', 'Diploma Belia dan Sukan', 'Diploma', 'social'],
  ['matric', 'Matrikulasi Sains', 'Pra-U', 'science'],
  ['kkom', 'Sijil Kulinari', 'Sijil', 'hospitality'],
  ['iljtm', 'Sijil Kemahiran Kimpalan', 'Sijil', 'engineering'],
  ['pismp', 'PISMP Pendidikan Matematik', 'Ijazah Sarjana Muda', 'education'],
  ['stpm', 'STPM Aliran Sains', 'Pra-U', 'science'],
] as const).map(([source_type, course_name, level, field_key], i) => {
  // ⚠ `merit_label` is a CLOSED set — 'High' | 'Fair' | 'Low' — and anything else falls through to
  // "Low Chance" with a red bar. The first draft of this fixture said 'Good' and rendered all eight
  // cards as bad news, which a reader takes for a bug in the thing they were asked to look at.
  const label = (['High', 'Fair', 'Low'] as const)[i % 3]
  return {
    course_id: `sandbox-${source_type}`,
    course_name,
    level,
    field: field_key,
    field_key,
    source_type,
    merit_cutoff: 85,
    student_merit: label === 'High' ? 92 : label === 'Fair' ? 86 : 79,
    merit_label: label,
    merit_color: null,
    institution_count: 3 + i,
  }
})

function CourseGuide() {
  return (
    <div className="mx-auto max-w-5xl">
      <CourseHeader
        sourceType="poly"
        level="Diploma"
        title="Diploma Teknologi Maklumat"
        subtitle="Politeknik Malaysia"
      />
      <div className="px-4">
        <p className="my-4 text-sm text-ground-500">
          Eight institution types, eight category swatches — the set only has to differ from itself,
          and this is the only place you can see whether it does. Beside each one is the LEVEL chip,
          which is deliberately grey in every card: it sits next to the type chip, the two sets
          together wanted thirteen swatches against a family of eight, and the chip already says
          “Diploma”. An unrecognised level had always been grey; now they all agree.
        </p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {SANDBOX_COURSES.map((course) => (
            <CourseCard key={course.course_id} course={course} isSaved={false} />
          ))}
        </div>
      </div>
    </div>
  )
}

function PiecesGallery() {
  const [on, setOn] = useState(false)
  const [pill, setPill] = useState('all')
  const [page, setPage] = useState(2)
  const row = 'flex flex-wrap items-center gap-4 border-b border-ground-200 py-4'
  return (
    <div className="mx-auto max-w-3xl px-4">
      <div className={row}>
        <div className="w-full space-y-2">
          {(['success', 'info', 'warning', 'block'] as const).map((kind) => (
            <InfoBox key={kind} kind={kind}>
              <strong className="capitalize">{kind}</strong> — the tone vocabulary this component names.
            </InfoBox>
          ))}
        </div>
      </div>
      <div className={row}>
        <ProgressStepper currentStep={2} totalSteps={3} />
      </div>
      <div className={row}>
        <FilterPill
          label="Status" value={pill} options={['all', 'open', 'done']}
          optionLabels={{ all: 'All', open: 'Open', done: 'Done' }} onChange={setPill}
        />
        <Toggle on={on} onChange={setOn} label="A switch" />
        <InfoTip text="A hint that opens on click." defaultOpen />
        <span className="text-ground-700">Matched value <VerifiedTick label="Matches MyKad" /></span>
      </div>
      <div className={row}>
        {/* The BRAND correction, visible: this bar must follow a tenant's colour. */}
        <div className="w-full max-w-sm"><FundingBar funded={3200} award={5000} /></div>
      </div>
      <div className={row}>
        <Pagination page={page} totalPages={7} pageSize={20} onPageChange={setPage} />
      </div>
    </div>
  )
}

export function surfaceBySlug(slug: string): Surface | undefined {
  return SURFACES.find((s) => s.slug === slug)
}
