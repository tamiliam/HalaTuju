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

afterEach(cleanup)
