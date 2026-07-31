/**
 * @jest-environment jsdom
 *
 * The DISCUSSION on a request (TD-201) — RENDERED, not read as source text.
 *
 * This file exists because of a specific failure earlier in the same sprint: a source-shape guard
 * asserted `/onPaste=/`, went green, and the feature was dead on both surfaces for a day. A regex
 * over a `.tsx` file can prove a string is present; it cannot prove a box appears, that the right
 * endpoint is called, or that a control DISAPPEARS when a window closes. Those are the claims here.
 *
 * The two that matter most, and why:
 *
 *  1. **The comment box survives acceptance.** The owner's model is Bugzilla — "open
 *     discussion/debate, even after it has been assigned to someone". The reply box and the
 *     screenshot control both close at acceptance because they change what was priced; a remark
 *     does not. Three windows that look alike and are not, so the asymmetry is asserted directly.
 *
 *  2. **The internal checkbox is the owner's alone.** It must not render for an org_admin. This is
 *     a convenience, NOT the control — the server refuses `internal` from anyone else and an org
 *     author can never be internal at all — but a checkbox that appears and then 403s is a lie
 *     about who can be private on this platform.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import AdminRequestDetailPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: '4' }),
  useRouter: () => ({ push: jest.fn() }),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
// The screenshot panel has its own rendered tests and a DocViewer behind it; it is not the subject
// here, and rendering it would drag its upload plumbing into every case below.
jest.mock('@/components/OrgRequestAttachments', () => ({ __esModule: true, default: () => null }))

let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const comment = (over: Partial<api.OrgRequestComment> = {}): api.OrgRequestComment => ({
  id: 1,
  author_kind: 'ai',
  author_name: '',
  body: 'Which report do you mean?',
  visibility: 'shared',
  awaiting_reply: false,
  created_at: '2026-07-31T02:00:00Z',
  ...over,
})

const analysis = (over: Partial<api.OrgRequestAnalysis> = {}): api.OrgRequestAnalysis => ({
  id: 1,
  body: 'It reuses the existing invite engine.',
  estimated_hours: '4.0',
  cited_files: ['apps/scholarship/referrals.py'],
  authored_by: 'claude-opus-5',
  repo_sha: 'abcdef0123456789abcdef0123456789abcdef01',
  proposed_kind: '',
  proposed_lane: '',
  created_at: '2026-07-31T03:00:00Z',
  approved_at: null,
  approved_by_name: '',
  superseded_at: null,
  is_current: false,
  ...over,
})

const approvedAnalysis = (over: Partial<api.OrgRequestAnalysis> = {}) =>
  analysis({
    approved_at: '2026-07-31T04:00:00Z', approved_by_name: 'Ve. Elanjelian',
    is_current: true, ...over,
  })

const detail = (over: Partial<api.OrgRequestDetail> = {}): api.OrgRequestDetail => ({
  id: 4,
  kind: 'feature',
  title: 'Add a sponsor directly',
  description: 'We would like to add sponsors ourselves.',
  component: '',
  urgency: '',
  steps_to_reproduce: '',
  status: 'submitted',
  comments: [],
  attachments: [],
  quote_hours: null,
  quote_note: '',
  quoted_at: null,
  approved_at: null,
  scheduled_for: null,
  decline_reason: '',
  created_at: '2026-07-30T00:00:00Z',
  updated_at: '2026-07-30T00:00:00Z',
  submitted_by_name: 'Dina',
  ...over,
})

/** Render and wait out the initial load, so no case asserts against the loading state. */
async function show(over: Partial<api.OrgRequestDetail> = {}) {
  mockApi.getOrgRequest.mockResolvedValue(detail(over))
  render(<AdminRequestDetailPage />)
  await waitFor(() => expect(screen.getByText('Add a sponsor directly')).toBeTruthy())
}

const commentBox = () => screen.queryByPlaceholderText('admin.requests.detail.commentPlaceholder')

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
})

describe('the thread renders as one stream', () => {
  it('shows every comment with WHO spoke', async () => {
    await show({
      comments: [
        comment({ id: 1, author_kind: 'ai', body: 'Which report do you mean?' }),
        comment({ id: 2, author_kind: 'org', author_name: 'Dina', body: 'The monthly one.' }),
        comment({ id: 3, author_kind: 'owner', body: 'We would build an invite instead.' }),
      ],
    })
    expect(screen.getByText('Which report do you mean?')).toBeTruthy()
    expect(screen.getByText('The monthly one.')).toBeTruthy()
    expect(screen.getByText('We would build an invite instead.')).toBeTruthy()
    // Provenance is the point of ONE shared thread: the reviewer's reading, the owner's judgement
    // and the requester's own words do not carry the same weight.
    expect(screen.getByText('admin.requests.detail.author.ai')).toBeTruthy()
    expect(screen.getByText('admin.requests.detail.author.org')).toBeTruthy()
    expect(screen.getByText('admin.requests.detail.author.owner')).toBeTruthy()
  })

  it('says so plainly when nothing has been said', async () => {
    await show({ comments: [] })
    expect(screen.getByText('admin.requests.detail.noComments')).toBeTruthy()
  })

  it('prompts for an answer only where answering is still possible', async () => {
    // The request #3 defect, in rendered form: a quote went out with a question open, the reply box
    // unmounted, and the thread kept demanding an answer the page had removed the means to give.
    await show({ status: 'approved', comments: [comment({ awaiting_reply: true })] })
    expect(screen.queryByText('admin.requests.list.answerNeeded')).toBeNull()
    expect(screen.getByText('admin.requests.detail.unanswered')).toBeTruthy()
  })

  it('does prompt while the window is open', async () => {
    await show({ status: 'submitted', comments: [comment({ awaiting_reply: true })] })
    expect(screen.getByText('admin.requests.list.answerNeeded')).toBeTruthy()
  })
})

describe('the comment box', () => {
  it('posts what was typed and clears itself', async () => {
    await show()
    mockApi.commentOrgRequest.mockResolvedValue(detail({ comments: [comment({ body: 'Noted.' })] }))

    const box = screen.getByPlaceholderText('admin.requests.detail.commentPlaceholder')
    fireEvent.change(box, { target: { value: 'Noted.' } })
    fireEvent.click(screen.getByText('admin.requests.detail.commentSend'))

    await waitFor(() => expect(mockApi.commentOrgRequest).toHaveBeenCalledWith(
      4, { body: 'Noted.', visibility: 'shared' }, { token: 'tok' }))
    await waitFor(() => expect((box as HTMLTextAreaElement).value).toBe(''))
  })

  it('will not post an empty comment', async () => {
    await show()
    // Disabled rather than sent-and-refused: the server raises `body_required`, and a round trip to
    // be told you typed nothing is a worse answer than a button that cannot be pressed.
    const send = () => screen.getByText('admin.requests.detail.commentSend') as HTMLButtonElement
    expect(send().disabled).toBe(true)
    fireEvent.change(screen.getByPlaceholderText('admin.requests.detail.commentPlaceholder'),
      { target: { value: '   ' } })
    expect(send().disabled).toBe(true)
    expect(mockApi.commentOrgRequest).not.toHaveBeenCalled()
  })

  it('STAYS after the quote is accepted, when everything else has closed', async () => {
    // The owner's ruling, rendered. `approved` is past acceptance: no reply box, no new question,
    // and the discussion carries on regardless.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ status: 'approved', comments: [comment({ awaiting_reply: true })] })
    expect(commentBox()).toBeTruthy()
    expect(screen.queryByPlaceholderText('admin.requests.detail.answerPlaceholder')).toBeNull()
    expect(screen.queryByPlaceholderText('admin.requests.detail.askPlaceholder')).toBeNull()
  })

  it.each(['done', 'declined'])('is gone once the request is %s', async (status) => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ status })
    expect(commentBox()).toBeNull()
  })

  it.each(['triaged', 'quoted', 'approved', 'scheduled'])(
    'is offered to the requesting organisation at %s', async (status) => {
      // The owner's complaint that started this: a second org_admin could open the request and only
      // watch. They can already read it, so speaking adds no visibility.
      viewerRole = { role: 'org_admin' }
      await show({ status })
      expect(commentBox()).toBeTruthy()
    })
})

describe('the internal note is the owner’s alone', () => {
  it('offers no internal checkbox to the requesting organisation', async () => {
    viewerRole = { role: 'org_admin' }
    await show()
    expect(screen.queryByText('admin.requests.detail.commentInternal')).toBeNull()
  })

  it('offers it to the owner, and sends visibility=internal when ticked', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show()
    mockApi.commentOrgRequest.mockResolvedValue(detail())

    fireEvent.change(screen.getByPlaceholderText('admin.requests.detail.commentPlaceholder'),
      { target: { value: 'privately: this smells like consent' } })
    fireEvent.click(screen.getByLabelText('admin.requests.detail.commentInternal'))
    // The warning is shown BEFORE sending — the moment to notice you are about to write something
    // the requester will never see is while you can still untick it.
    expect(screen.getByText('admin.requests.detail.commentInternalHint')).toBeTruthy()
    fireEvent.click(screen.getByText('admin.requests.detail.commentSend'))

    await waitFor(() => expect(mockApi.commentOrgRequest).toHaveBeenCalledWith(
      4, { body: 'privately: this smells like consent', visibility: 'internal' }, { token: 'tok' }))
  })

  it('badges an internal comment in the thread so the owner can see what is not shared', async () => {
    // Only ever reachable by the super — the server filters internal ROWS out of the org payload.
    // An unmarked internal note is how something private gets written as though it were shared.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ comments: [comment({ visibility: 'internal', body: 'ours only' })] })
    expect(screen.getByText('admin.requests.detail.internalBadge')).toBeTruthy()
  })

  it('defaults to shared on a fresh box', async () => {
    // A checkbox that remembered its last state would eventually make something private by
    // accident, which is the only direction this mistake goes.
    viewerRole = { role: 'super', is_super_admin: true }
    await show()
    const box = screen.getByLabelText('admin.requests.detail.commentInternal') as HTMLInputElement
    expect(box.checked).toBe(false)
  })
})

describe("the engineer's analysis panel (TD-204)", () => {
  it('is OWNER-ONLY — an org_admin never sees the files or the hours', async () => {
    // Belt and braces on the frontend. The server puts no `analyses` key on an org payload at
    // all; this asserts the page would not render one even if it arrived.
    viewerRole = { role: 'org_admin' }
    await show({ analyses: [approvedAnalysis()] })
    expect(screen.queryByText('admin.requests.owner.analysisTitle')).toBeNull()
    expect(screen.queryByText('apps/scholarship/referrals.py')).toBeNull()
  })

  it('shows the owner the reasoning, the files, who read them and at which commit', async () => {
    // `authored_by` and `repo_sha` are rendered in the same change that stores them. This project
    // has already found five stored-but-never-surfaced fields; this is why there is not a sixth.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ analyses: [approvedAnalysis()] })
    expect(screen.getByText('It reuses the existing invite engine.')).toBeTruthy()
    expect(screen.getByText('apps/scholarship/referrals.py')).toBeTruthy()
    expect(screen.getByText('claude-opus-5')).toBeTruthy()
    expect(screen.getByText('abcdef012345')).toBeTruthy()
  })

  it('says NO ANALYSIS RECORDED rather than implying one is missing', async () => {
    // Every request predating TD-204 has none, so the empty state must read as the absence of a
    // record and never as a finding.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ analyses: [] })
    expect(screen.getByText('admin.requests.owner.analysisNone')).toBeTruthy()
  })

  it('offers Approve on a draft', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ analyses: [analysis()] })
    expect(screen.getByText('admin.requests.owner.analysisApprove')).toBeTruthy()
  })

  it('offers no Approve on one already approved', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ analyses: [approvedAnalysis()] })
    expect(screen.queryByText('admin.requests.owner.analysisApprove')).toBeNull()
  })

  it('approving calls the endpoint with the analysis id', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true)
    await show({ analyses: [analysis({ id: 77 })] })
    mockApi.approveOrgRequestAnalysis.mockResolvedValue(detail())
    fireEvent.click(screen.getByText('admin.requests.owner.analysisApprove'))
    await waitFor(() => expect(mockApi.approveOrgRequestAnalysis)
      .toHaveBeenCalledWith(4, 77, { token: 'tok' }))
    confirmSpy.mockRestore()
  })

  it('warns when something was said after the analysis was written', async () => {
    // An answer can change scope without superseding — only `modify` does that — so this is a
    // note for the owner's judgement, not a block.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({
      analyses: [approvedAnalysis()],
      comments: [comment({ id: 9, author_kind: 'org', created_at: '2026-07-31T09:00:00Z',
                           body: 'Actually we need it on the dashboard too.' })],
    })
    expect(screen.getByText('admin.requests.owner.analysisStale')).toBeTruthy()
  })

  it('does NOT warn when the newest comment is the analysis’s own post', async () => {
    // Approving posts an engineer comment. If that counted as "something said since", the warning
    // would fire on every freshly approved analysis and teach the owner to ignore it.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({
      analyses: [approvedAnalysis()],
      comments: [comment({ id: 9, author_kind: 'engineer', created_at: '2026-07-31T09:00:00Z',
                           body: 'It reuses the existing invite engine.' })],
    })
    expect(screen.queryByText('admin.requests.owner.analysisStale')).toBeNull()
  })

  it('renders the engineer badge on the posted comment', async () => {
    // `author_kind` gained a fourth value; the thread builds its label key FROM that value, so a
    // missing i18n key prints a raw dotted path to the requester.
    viewerRole = { role: 'org_admin' }
    await show({ comments: [comment({ author_kind: 'engineer' })] })
    expect(screen.getByText('admin.requests.detail.author.engineer')).toBeTruthy()
  })
})

describe('triage starts from the AI reading, not from the expensive default', () => {
  // Owner, 2026-07-31, on request #4: the AI had classified it a BUG and the triage form still
  // offered "Feature request / Sprint" — a hard-coded default that disagreed with the reading
  // directly above it. The two values are not equivalent: a bug is FREE and a feature is PRICED,
  // so accepting the default silently turns one into the other.
  const SUBMITTED = { status: 'submitted', triaged_kind: '' }
  const kindSelect = () => screen.getByLabelText(/triageKind/) as HTMLSelectElement
  const laneSelect = () => screen.getByLabelText(/triageLane/) as HTMLSelectElement

  it('seeds kind and lane from the AI draft', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, ai_draft_kind: 'bug', ai_draft_lane: 'small_change' })
    await waitFor(() => expect(kindSelect().value).toBe('bug'))
    expect(laneSelect().value).toBe('small_change')
  })

  it('NEVER clobbers a classification the owner picked', async () => {
    // The owner's judgement is authoritative and the AI's is not; a re-render must not undo them.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, ai_draft_kind: 'bug', ai_draft_lane: 'small_change' })
    await waitFor(() => expect(kindSelect().value).toBe('bug'))
    fireEvent.change(kindSelect(), { target: { value: 'feature' } })
    fireEvent.change(screen.getByPlaceholderText('admin.requests.owner.triageNote'),
      { target: { value: 'reclassified deliberately' } })
    expect(kindSelect().value).toBe('feature')
  })

  it('falls back to feature/sprint when the AI has not read it yet', async () => {
    // No draft — an un-run request keeps the previous behaviour rather than seeding something
    // arbitrary. The owner is choosing from scratch, which is the honest state.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, ai_draft_kind: '', ai_draft_lane: '' })
    expect(kindSelect().value).toBe('feature')
    expect(laneSelect().value).toBe('sprint')
  })

  // ── The engineer's proposal (2026-08-01) ───────────────────────────────────────────────
  // A THIRD opinion now reaches this form. Gemini reads the description; the engineer reads the
  // code. Neither is authoritative — the owner decides — but the box has to start somewhere, and
  // an unattributed default is what put 'feature' in front of every bug in the first place.

  it('prefers the ENGINEER proposal over the AI draft', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, ai_draft_kind: 'feature', ai_draft_lane: 'sprint',
                 analyses: [analysis({ proposed_kind: 'bug', proposed_lane: 'small_change' })] })
    await waitFor(() => expect(kindSelect().value).toBe('bug'))
    expect(laneSelect().value).toBe('small_change')
  })

  it('says WHOSE reading is in the boxes', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, ai_draft_kind: 'feature',
                 analyses: [analysis({ proposed_kind: 'bug' })] })
    await waitFor(() => expect(kindSelect().value).toBe('bug'))
    expect(screen.getByText('admin.requests.owner.triageSeededEngineer')).toBeTruthy()
    expect(screen.queryByText('admin.requests.owner.triageSeededAi')).toBeNull()
  })

  it('attributes the AI when that is what seeded it', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, ai_draft_kind: 'bug', analyses: [analysis()] })
    await waitFor(() => expect(kindSelect().value).toBe('bug'))
    expect(screen.getByText('admin.requests.owner.triageSeededAi')).toBeTruthy()
  })

  it('takes the proposal from a DRAFT analysis, not only an approved one', async () => {
    // A draft the owner is reading right now is exactly when the prefill is wanted — the analysis
    // panel sits directly above this form.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, ai_draft_kind: 'feature',
                 analyses: [analysis({ approved_at: null, proposed_kind: 'bug' })] })
    await waitFor(() => expect(kindSelect().value).toBe('bug'))
  })

  it('an analysis with NO opinion leaves the AI reading alone', async () => {
    // Blank is not agreement, and it must not overwrite the reading that does exist.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, ai_draft_kind: 'bug', ai_draft_lane: 'small_change',
                 analyses: [analysis({ proposed_kind: '', proposed_lane: '' })] })
    await waitFor(() => expect(kindSelect().value).toBe('bug'))
    expect(laneSelect().value).toBe('small_change')
  })

  it('still never clobbers what the owner picked', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...SUBMITTED, analyses: [analysis({ proposed_kind: 'bug' })] })
    await waitFor(() => expect(kindSelect().value).toBe('bug'))
    fireEvent.change(kindSelect(), { target: { value: 'feature' } })
    expect(kindSelect().value).toBe('feature')
    expect(screen.queryByText('admin.requests.owner.triageSeededEngineer')).toBeNull()
  })
})

describe('the quote form stands on the analysis', () => {
  const TRIAGED = { status: 'triaged', triaged_kind: 'feature' }
  const hoursInput = () =>
    screen.getByLabelText(/quoteHours/) as HTMLInputElement

  it('prefills the hours from the approved analysis', async () => {
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...TRIAGED, analyses: [approvedAnalysis({ estimated_hours: '4.0' })] })
    await waitFor(() => expect(hoursInput().value).toBe('4.0'))
  })

  it('NEVER clobbers a number the owner typed', async () => {
    // Deliberately the opposite of the income wizard (S14), which needed a RE-seeding effect.
    // Here re-seeding is the bug: the owner routinely quotes differently from the engineer
    // (bundling, goodwill, margin) and a re-render must not undo that.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...TRIAGED, analyses: [approvedAnalysis({ estimated_hours: '4.0' })] })
    await waitFor(() => expect(hoursInput().value).toBe('4.0'))
    fireEvent.change(hoursInput(), { target: { value: '6' } })
    // Something else re-renders the page.
    fireEvent.change(screen.getByPlaceholderText('admin.requests.owner.quoteNote'),
      { target: { value: 'bundled with the other one' } })
    expect(hoursInput().value).toBe('6')
  })

  it('renders analysis_required as ITS OWN message, not the generic one', async () => {
    // A code absent from KNOWN_ERR renders "Something went wrong", which tells the owner nothing
    // about what to do next. This assertion is what keeps it in the array.
    viewerRole = { role: 'super', is_super_admin: true }
    await show({ ...TRIAGED })
    mockApi.quoteOrgRequest.mockRejectedValue(
      Object.assign(new Error('refused'), { code: 'analysis_required' }))
    fireEvent.change(hoursInput(), { target: { value: '6' } })
    fireEvent.click(screen.getByText('admin.requests.action.quote'))
    await waitFor(() =>
      expect(screen.getByText('admin.requests.error.analysis_required')).toBeTruthy())
    expect(screen.queryByText('admin.requests.error.generic')).toBeNull()
  })
})

afterEach(cleanup)
