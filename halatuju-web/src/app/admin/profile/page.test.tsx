/**
 * @jest-environment jsdom
 *
 * The common Profile page (common profile S1, 2026-10-31): ONE shell for every role, rendering the
 * cards `lib/profileCards.ts` names and nothing else, with ONE Save that writes each changed part
 * to its own endpoint. The source user's half is the retired `SourceProfile.tsx`'s tests, moved.
 * S2: the name and the person's card (job title, About, phone, who sees the phone) save through
 * `admin/me/` for every role; the photo is its own action.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import ProfilePage from './page'
import { ME, PROFILE } from '@/components/source/testFixtures'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
const refreshRole = jest.fn(() => Promise.resolve())
const push = jest.fn()
let mockAuth: Record<string, unknown> = {}
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => mockAuth }))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push, replace: jest.fn() }) }))
const updateUser = jest.fn()
const refreshSession = jest.fn()
const signInAgain = jest.fn()
jest.mock('@/lib/admin-supabase', () => ({
  getAdminSupabase: () => ({ auth: { updateUser, refreshSession } }),
  adminSignInWithPassword: (...a: unknown[]) => signInAgain(...a),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

/** Each role's RESOLVED permissions as the server serves them (staff_permissions.py presets). */
const PRESET: Record<string, string[]> = {
  super: ['review', 'see_all', 'qc', 'spending', 'payments_prepare', 'payments_check', 'payments_approve',
          'manage_team'],
  org_admin: ['see_all', 'qc', 'spending', 'manage_team'],
  admin: ['see_all', 'spending', 'payments_prepare'],
  finance: ['payments_approve'],
  reviewer: ['review'],
  qc: ['see_all', 'qc'],
  partner: [],
  source_partner: [],
}

const STAFF_PROFILE = { id: 7, name: 'Priya', email: 'priya@example.org', is_super_admin: false,
  org_name: null, org_contact_person: null, org_phone: null }
const FULL_REVIEWER: api.ReviewerProfile = {
  highest_qualification: 'PhD', university: 'Universiti Malaya', graduation_year: 2010,
  field_of_study: 'Law', phone: '12-345 6789', address: '', street_address: '', postcode: '',
  city: '', state: '', english_fluency: 'fluent', bm_fluency: '', tamil_fluency: '',
  other_language: '', other_language_fluency: '', share_phone_with_students: true, paused: false,
}
const EMPTY_REVIEWER: api.ReviewerProfile = { ...FULL_REVIEWER, highest_qualification: '', university: '',
  graduation_year: null, field_of_study: '', phone: '', english_fluency: '' }

const setHeaderPhoto = jest.fn()
const STAFF_ME: api.AdminMe = { ...ME, name: 'Priya', email: 'priya@example.org', role: 'reviewer', source: null,
  permissions: ['review'], phone: '12-345 6789' }

function signIn(role: string, extra: Record<string, unknown> = {}, providers = ['email']) {
  mockAuth = {
    token: 'tok', refreshRole, setPhotoUrl: setHeaderPhoto,
    session: { user: { app_metadata: { providers } } },
    role: { role, is_admin: true, is_super_admin: role === 'super', permissions: PRESET[role],
            reviewer_profile_complete: true, ...extra },
  }
}

const save = () => screen.getByText('common.save').closest('button') as HTMLButtonElement
const shownCards = () => screen.getAllByTestId(/^profile-card-/).map((n) => n.dataset.testid?.replace('profile-card-', ''))

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getAdminMe.mockResolvedValue(STAFF_ME)
  mockApi.updateAdminMe.mockImplementation((data) => Promise.resolve({ ...STAFF_ME, ...data }))
  mockApi.getAdminProfile.mockResolvedValue(STAFF_PROFILE)
  mockApi.getReviewerProfile.mockResolvedValue(FULL_REVIEWER)
  mockApi.updateAdminProfile.mockResolvedValue({})
  mockApi.updateReviewerProfile.mockResolvedValue(FULL_REVIEWER)
  mockApi.getSourceProfile.mockResolvedValue(PROFILE)
})

// ── The card matrix, rendered ──────────────────────────────────────────────────────────────────
describe.each([
  ['super', ['you', 'contact', 'access', 'signin']],
  ['org_admin', ['you', 'contact', 'access', 'signin']],
  ['admin', ['you', 'contact', 'access', 'signin']],
  ['finance', ['you', 'contact', 'access', 'signin']],
  ['qc', ['you', 'contact', 'access', 'signin']],
  ['reviewer', ['you', 'contact', 'access', 'qualifications', 'address', 'takingPart', 'signin']],
  ['partner', ['you', 'contact', 'access', 'organisation', 'signin']],
  ['source_partner', ['you', 'contact', 'access', 'organisation', 'signin']],
] as const)('%s', (role, cards) => {
  it('renders exactly its cards, in order', async () => {
    signIn(role)
    render(<ProfilePage />)
    await screen.findByTestId('profile-card-signin')
    await waitFor(() => expect(shownCards()).toEqual(cards))
    // A card that is not shown is never fetched for: no reviewer profile without the cards, and the
    // staff profile only for the partner's organisation.
    expect(mockApi.getReviewerProfile).toHaveBeenCalledTimes(cards.includes('qualifications' as never) ? 1 : 0)
    expect(mockApi.getAdminProfile).toHaveBeenCalledTimes(role === 'partner' ? 1 : 0)
    expect(mockApi.getAdminMe).toHaveBeenCalledTimes(1)
  })
})

it('an admin given `review` gets the reviewer cards and a reminder — never the hold', async () => {
  signIn('admin', { permissions: ['review', 'see_all'] })
  mockApi.getReviewerProfile.mockResolvedValue(EMPTY_REVIEWER)
  mockApi.getAdminMe.mockResolvedValue({ ...STAFF_ME, phone: '' })      // the phone is the card's (S2)
  render(<ProfilePage />)
  await screen.findByTestId('profile-card-qualifications')
  const reminder = await screen.findByTestId('reviewer-reminder')
  expect(within(reminder).getByText('admin.reviewer.phone')).toBeTruthy()
  expect(screen.queryByText('admin.reviewer.onboarding.title')).toBeNull()
})

it('a reviewer whose `review` was taken away loses the reviewer cards', async () => {
  signIn('reviewer', { permissions: [] })
  render(<ProfilePage />)
  await screen.findByTestId('profile-card-signin')
  await waitFor(() => expect(shownCards()).toEqual(['you', 'contact', 'access', 'signin']))
  expect(mockApi.getReviewerProfile).not.toHaveBeenCalled()
})

// ── Staff saves ────────────────────────────────────────────────────────────────────────────────
it('a name change goes to admin/me only, and refreshes the header', async () => {
  signIn('reviewer')
  render(<ProfilePage />)
  const name = await screen.findByDisplayValue('Priya')
  await screen.findByTestId('profile-card-qualifications')
  expect(save().disabled).toBe(true)
  fireEvent.change(name, { target: { value: 'Priya D' } })
  expect(save().disabled).toBe(false)
  fireEvent.click(save())
  await waitFor(() => expect(mockApi.updateAdminMe).toHaveBeenCalledWith({ name: 'Priya D' }, { token: 'tok' }))
  expect(mockApi.updateReviewerProfile).not.toHaveBeenCalled()
  expect(mockApi.updateAdminProfile).not.toHaveBeenCalled()
  await waitFor(() => expect(refreshRole).toHaveBeenCalled())
  expect(await screen.findByText('admin.profileUpdated')).toBeTruthy()
  expect(save().disabled).toBe(true)                     // the baseline moved with the save
})

it('the share-phone and pause switches are Toggles; each saves through its own endpoint', async () => {
  signIn('reviewer')
  render(<ProfilePage />)
  const share = await screen.findByRole('switch', { name: 'admin.reviewer.sharePhone' })
  expect(share.getAttribute('aria-checked')).toBe('true')
  fireEvent.click(share)
  fireEvent.click(await screen.findByRole('switch', { name: 'admin.reviewer.pauseLabel' }))
  expect(await screen.findByText('admin.reviewer.pausedNote')).toBeTruthy()
  expect(screen.queryAllByRole('checkbox')).toEqual([])
  fireEvent.click(save())
  await waitFor(() => expect(mockApi.updateAdminMe).toHaveBeenCalledWith(
    { share_phone_with_students: false }, { token: 'tok' }))
  await waitFor(() => expect(mockApi.updateReviewerProfile).toHaveBeenCalledWith(
    expect.objectContaining({ paused: true }), { token: 'tok' }))
  // ⚠ The phone and "share with students" are the card's (admin/me/) — never sent twice.
  const sent = mockApi.updateReviewerProfile.mock.calls[0][0]
  expect('phone' in sent || 'share_phone_with_students' in sent).toBe(false)
  expect(mockApi.updateAdminProfile).not.toHaveBeenCalled()
})

it('a held Reviewer sees the onboarding banner and the completing save sends them on', async () => {
  signIn('reviewer', { reviewer_profile_complete: false })
  mockApi.getAdminMe.mockResolvedValue({ ...STAFF_ME, phone: '' })
  render(<ProfilePage />)
  expect(await screen.findByText('admin.reviewer.onboarding.title')).toBeTruthy()
  fireEvent.change(await screen.findByPlaceholderText('12-345 6789'), { target: { value: '123456789' } })
  expect(await screen.findByText('admin.reviewer.onboarding.allSet')).toBeTruthy()
  fireEvent.click(save())
  await waitFor(() => expect(push).toHaveBeenCalledWith('/admin/scholarship'))
  expect(mockApi.updateAdminMe).toHaveBeenCalledWith({ phone: '12-345 6789' }, { token: 'tok' })
  expect(refreshRole).toHaveBeenCalled()
})

it("a partner edits its organisation's contact through admin/profile", async () => {
  signIn('partner')
  mockApi.getAdminProfile.mockResolvedValue({ ...STAFF_PROFILE, org_name: 'CUMIG',
    org_contact_person: 'Ravi', org_phone: '12-111 2222' })
  render(<ProfilePage />)
  fireEvent.change(await screen.findByDisplayValue('Ravi'), { target: { value: 'Kavi' } })
  fireEvent.click(save())
  await waitFor(() => expect(mockApi.updateAdminProfile).toHaveBeenCalledWith(
    { org_contact_person: 'Kavi', org_phone: '12-111 2222' }, { token: 'tok' }))
  expect(mockApi.updateAdminMe).not.toHaveBeenCalled()
  expect(refreshRole).not.toHaveBeenCalled()
})

// ── S2: the person's card ──────────────────────────────────────────────────────────────────────
it('staff may show their phone to the team; only a review holder sees the students switch', async () => {
  signIn('finance')
  render(<ProfilePage />)
  const team = await screen.findByRole('switch', { name: 'admin.myProfile.showToTeam' })
  expect(screen.queryByRole('switch', { name: 'admin.reviewer.sharePhone' })).toBeNull()
  expect(screen.queryByTestId('phone-seen-by-inviter')).toBeNull()
  fireEvent.click(team)
  fireEvent.click(save())
  await waitFor(() => expect(mockApi.updateAdminMe).toHaveBeenCalledWith(
    { share_phone_with_team: true }, { token: 'tok' }))
})

it('job title and About save through admin/me, and About counts to 600', async () => {
  signIn('admin')
  render(<ProfilePage />)
  fireEvent.change(await screen.findByLabelText('admin.myProfile.jobTitle'), { target: { value: 'Officer' } })
  const about = screen.getByLabelText('admin.myProfile.about') as HTMLTextAreaElement
  expect(about.maxLength).toBe(600)
  fireEvent.change(about, { target: { value: 'Hello' } })
  expect(screen.getByText('admin.myProfile.aboutCount')).toBeTruthy()
  fireEvent.click(save())
  await waitFor(() => expect(mockApi.updateAdminMe).toHaveBeenCalledWith(
    { job_title: 'Officer', about: 'Hello' }, { token: 'tok' }))
})

it('an admin/me refusal reads in its own words', async () => {
  signIn('reviewer')
  mockApi.updateAdminMe.mockRejectedValue(Object.assign(new Error('x'), { code: 'phone_required' }))
  render(<ProfilePage />)
  fireEvent.change(await screen.findByPlaceholderText('12-345 6789'), { target: { value: '' } })
  fireEvent.click(save())
  expect((await screen.findByRole('alert')).textContent).toBe('admin.myProfile.error.phone_required')
})

it('a photo uploads straight away, and the header follows', async () => {
  signIn('admin')
  mockApi.uploadAdminPhoto.mockResolvedValue({ photo_url: 'https://signed/p.webp' })
  render(<ProfilePage />)
  const input = await screen.findByTestId('photo-input')
  const file = new File(['x'], 'me.png', { type: 'image/png' })
  fireEvent.change(input, { target: { files: [file] } })
  await waitFor(() => expect(mockApi.uploadAdminPhoto).toHaveBeenCalledWith(file, { token: 'tok' }))
  expect(await screen.findByText('admin.myProfile.photo.saved')).toBeTruthy()
  expect(setHeaderPhoto).toHaveBeenCalledWith('https://signed/p.webp')
  expect((screen.getByTestId('staff-avatar-photo') as HTMLImageElement).src).toBe('https://signed/p.webp')
  // Not part of Save.
  expect(save().disabled).toBe(true)
})

it('a photo over 2 MB is refused before the call; Remove deletes it', async () => {
  signIn('admin')
  mockApi.getAdminMe.mockResolvedValue({ ...STAFF_ME, photo_url: 'https://signed/old.webp' })
  mockApi.deleteAdminPhoto.mockResolvedValue({ photo_url: null })
  render(<ProfilePage />)
  const big = new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'big.jpg', { type: 'image/jpeg' })
  fireEvent.change(await screen.findByTestId('photo-input'), { target: { files: [big] } })
  expect((await screen.findByRole('alert')).textContent).toBe('admin.myProfile.photo.tooLarge')
  expect(mockApi.uploadAdminPhoto).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('admin.myProfile.photo.remove'))
  await waitFor(() => expect(mockApi.deleteAdminPhoto).toHaveBeenCalled())
  await waitFor(() => expect(setHeaderPhoto).toHaveBeenCalledWith(null))
  expect(screen.getByTestId('staff-avatar-initials')).toBeTruthy()
})

it('Your access names the role, the gifts and what they can do, read only', async () => {
  signIn('reviewer')
  mockApi.getAdminMe.mockResolvedValue({ ...ME, role: 'reviewer', source: null, permissions: ['review'],
    programmes: 'all' })
  render(<ProfilePage />)
  const card = await screen.findByTestId('profile-card-access')
  await waitFor(() => expect(within(card).getByText('admin.shell.allGifts')).toBeTruthy())
  expect(within(card).getByText('admin.role.reviewer')).toBeTruthy()
  expect(within(card).getByText('admin.perm.review.name')).toBeTruthy()
  expect(within(card).getByText('admin.myProfile.onlyOrgAdmin')).toBeTruthy()
  expect(within(card).queryAllByRole('textbox')).toEqual([])
})

// ── Sign-in ────────────────────────────────────────────────────────────────────────────────────
it('a Google-only account sees no password change', async () => {
  signIn('admin', {}, ['google'])
  render(<ProfilePage />)
  const card = await screen.findByTestId('profile-card-signin')
  expect(within(card).getByText('Google')).toBeTruthy()
  expect(within(card).queryByText('admin.myProfile.changePassword')).toBeNull()
})

/** Opens the change form and fills it. */
async function fillPassword(current: string, pw: string, pw2 = pw) {
  fireEvent.click(within(await screen.findByTestId('profile-card-signin')).getByText('admin.myProfile.changePassword'))
  fireEvent.change(screen.getByLabelText('admin.myProfile.currentPassword'), { target: { value: current } })
  fireEvent.change(screen.getByLabelText('admin.myProfile.newPassword'), { target: { value: pw } })
  fireEvent.change(screen.getByLabelText('admin.myProfile.confirmPassword'), { target: { value: pw2 } })
}
const submitPassword = () => fireEvent.click(within(screen.getByTestId('change-password'))
  .getByText('admin.myProfile.changePassword'))

it('a password account changes its password through admin/me/password/, never updateUser', async () => {
  signIn('admin')
  mockApi.changeOwnPassword.mockResolvedValue({ ok: true })
  refreshSession.mockResolvedValue({ error: null })
  render(<ProfilePage />)
  await fillPassword('old-secret', 'short')
  submitPassword()
  expect((await screen.findByRole('alert')).textContent).toBe('admin.passwordTooShort')
  fireEvent.change(screen.getByLabelText('admin.myProfile.newPassword'), { target: { value: 'longenough1' } })
  fireEvent.change(screen.getByLabelText('admin.myProfile.confirmPassword'), { target: { value: 'longenough2' } })
  submitPassword()
  await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('admin.passwordMismatch'))
  expect(mockApi.changeOwnPassword).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('admin.myProfile.confirmPassword'), { target: { value: 'longenough1' } })
  submitPassword()
  await waitFor(() => expect(mockApi.changeOwnPassword).toHaveBeenCalledWith(
    'old-secret', 'longenough1', { token: 'tok' }))
  expect(await screen.findByText('admin.myProfile.passwordChanged')).toBeTruthy()
  expect(updateUser).not.toHaveBeenCalled()
  expect(signInAgain).not.toHaveBeenCalled()
  // Not part of the page's Save, and the fields are cleared (the form closes).
  expect(mockApi.updateAdminProfile).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('admin.myProfile.changePassword'))
  expect((screen.getByLabelText('admin.myProfile.currentPassword') as HTMLInputElement).value).toBe('')
  expect((screen.getByLabelText('admin.myProfile.newPassword') as HTMLInputElement).value).toBe('')
})

it('a session the change ended is signed in again with the new password, and says so', async () => {
  signIn('admin')
  mockApi.changeOwnPassword.mockResolvedValue({ ok: true })
  refreshSession.mockResolvedValue({ error: { message: 'Invalid Refresh Token' } })
  signInAgain.mockResolvedValue({ error: null })
  render(<ProfilePage />)
  await screen.findByDisplayValue('Priya')
  await fillPassword('old-secret', 'longenough1')
  submitPassword()
  expect(await screen.findByText('admin.myProfile.signedInAgain')).toBeTruthy()
  expect(signInAgain).toHaveBeenCalledWith('priya@example.org', 'longenough1')
})

it('the new password equal to the current one is refused before the call', async () => {
  signIn('admin')
  render(<ProfilePage />)
  await fillPassword('same-secret1', 'same-secret1')
  submitPassword()
  expect((await screen.findByRole('alert')).textContent).toBe('admin.myProfile.samePassword')
  expect(mockApi.changeOwnPassword).not.toHaveBeenCalled()
})

it.each([
  [{ code: 'wrong_current_password', status: 400 }, 'admin.myProfile.wrongCurrent'],
  [{ code: 'weak_password', status: 400 }, 'admin.myProfile.weakPassword'],
  [{ code: 'no_password_sign_in', status: 400 }, 'admin.myProfile.noPasswordSignIn'],
  [{ code: '', status: 429 }, 'admin.myProfile.tooManyAttempts'],
  [{ code: 'supabase_unavailable', status: 503 }, 'admin.myProfile.unavailable'],
  [{ code: 'odd', status: 400 }, 'admin.myProfile.passwordFailed'],
])('a %j refusal reads in its own words and takes the focus', async (e, words) => {
  signIn('admin')
  mockApi.changeOwnPassword.mockRejectedValue(Object.assign(new Error('x'), e))
  render(<ProfilePage />)
  await fillPassword('old-secret', 'longenough1')
  submitPassword()
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toBe(words)
  await waitFor(() => expect(document.activeElement).toBe(alert))
})

// ── A source user (the retired SourceProfile.tsx's behaviour, moved) ───────────────────────────
describe('a source user', () => {
  beforeEach(() => {
    signIn('source_partner', { source_id: 3, source_name: 'MUETMyWay' })
    mockApi.getAdminMe.mockResolvedValue(ME)
    mockApi.updateAdminMe.mockImplementation((data) => Promise.resolve({ ...ME, ...data }))
  })

  it('has no team: its Contact card says the inviting organisation sees the number', async () => {
    render(<ProfilePage />)
    expect(await screen.findByTestId('phone-seen-by-inviter')).toBeTruthy()
    expect(screen.queryByRole('switch', { name: 'admin.myProfile.showToTeam' })).toBeNull()
    expect(screen.queryByRole('switch', { name: 'admin.reviewer.sharePhone' })).toBeNull()
  })

  it('shows its name and organisation; the sign-in email is read-only; Save sleeps until something changes', async () => {
    render(<ProfilePage />)
    await screen.findByDisplayValue('MUETMyWay')
    // Two fields hold that address — the read-only sign-in and the editable contact email.
    const both = screen.getAllByDisplayValue('muetmyway@example.org') as HTMLInputElement[]
    expect(both.map((i) => i.disabled)).toEqual([true, false])
    expect(save().disabled).toBe(true)
    fireEvent.change(screen.getByDisplayValue('016-845 1270'), { target: { value: '0168451271' } })
    expect(save().disabled).toBe(false)
    expect(mockApi.getAdminProfile).not.toHaveBeenCalled()
  })

  it('saves the organisation details through admin/source/profile, never the name', async () => {
    mockApi.updateSourceProfile.mockResolvedValue({
      ...PROFILE, source: { ...PROFILE.source, contact_person: 'Kavi' } })
    render(<ProfilePage />)
    const person = (await screen.findAllByDisplayValue('Audrey Koh Sui Ean'))[1]
    fireEvent.change(person, { target: { value: 'Kavi' } })
    fireEvent.click(save())
    await waitFor(() => expect(mockApi.updateSourceProfile).toHaveBeenCalledWith({
      source: { name: 'MUETMyWay', contact_person: 'Kavi', contact_email: 'muetmyway@example.org',
                phone: '016-845 1270' },
    }, { token: 'tok' }))
    expect(await screen.findByText('admin.profileUpdated')).toBeTruthy()
    expect(mockApi.updateAdminMe).not.toHaveBeenCalled()
    expect(refreshRole).not.toHaveBeenCalled()
  })

  it('a changed own name goes through admin/me (S2) and refreshes the header', async () => {
    render(<ProfilePage />)
    const own = (await screen.findAllByDisplayValue('Audrey Koh Sui Ean'))[0]
    fireEvent.change(own, { target: { value: 'Audrey K' } })
    fireEvent.click(save())
    await waitFor(() => expect(mockApi.updateAdminMe).toHaveBeenCalledWith({ name: 'Audrey K' }, { token: 'tok' }))
    expect(mockApi.updateSourceProfile).not.toHaveBeenCalled()
    await waitFor(() => expect(refreshRole).toHaveBeenCalled())
  })

  it('M2: a stored phone the check would refuse does not block saving the name', async () => {
    mockApi.getSourceProfile.mockResolvedValue({ ...PROFILE, source: { ...PROFILE.source, phone: '12' } })
    mockApi.updateSourceProfile.mockResolvedValue(PROFILE)
    render(<ProfilePage />)
    const own = (await screen.findAllByDisplayValue('Audrey Koh Sui Ean'))[0]
    fireEvent.change(own, { target: { value: 'Audrey K' } })
    expect(save().disabled).toBe(false)
    expect(screen.queryByText('profile.invalidPhone')).toBeNull()
    // …but an EDITED bad phone still does.
    fireEvent.change(screen.getByDisplayValue('12'), { target: { value: '123' } })
    await waitFor(() => expect(save().disabled).toBe(true))
    expect(screen.getByText('profile.invalidPhone')).toBeTruthy()
  })

  it('L4: a changed organisation name refreshes the header too', async () => {
    mockApi.updateSourceProfile.mockResolvedValue({ ...PROFILE, source: { ...PROFILE.source, name: 'MUET Way' } })
    render(<ProfilePage />)
    fireEvent.change(await screen.findByDisplayValue('MUETMyWay'), { target: { value: 'MUET Way' } })
    fireEvent.click(save())
    await waitFor(() => expect(refreshRole).toHaveBeenCalled())
  })

  it('L10: a refusal sits beside Save and takes the focus', async () => {
    mockApi.updateSourceProfile.mockRejectedValue(Object.assign(new Error('x'), { code: 'bad_email' }))
    render(<ProfilePage />)
    fireEvent.change(await screen.findByDisplayValue('016-845 1270'), { target: { value: '0168451271' } })
    fireEvent.click(save())
    const alert = await screen.findByRole('alert')
    expect(alert.parentElement).toBe(save().parentElement)
    await waitFor(() => expect(document.activeElement).toBe(alert))
  })

  it.each(['name_required', 'source_name_required', 'bad_email', 'not_editable', 'source_unavailable', 'odd'])(
    'shows the %s refusal in its own words', async (code) => {
      mockApi.updateSourceProfile.mockRejectedValue(Object.assign(new Error(code), { code }))
      render(<ProfilePage />)
      fireEvent.change(await screen.findByDisplayValue('016-845 1270'), { target: { value: '0168451271' } })
      fireEvent.click(save())
      const words = code === 'odd' ? 'generic' : code
      await waitFor(() => expect(screen.getByRole('alert').textContent)
        .toBe(`admin.sourceConsole.profile.error.${words}`))
    })

  it('names its source and organisation under Your access, and holds no staff power', async () => {
    render(<ProfilePage />)
    const card = await screen.findByTestId('profile-card-access')
    await waitFor(() => expect(within(card).getByText('MUETMyWay')).toBeTruthy())
    expect(within(card).getByText('Harapan')).toBeTruthy()
    expect(within(card).getByText('Flagship')).toBeTruthy()
    expect(within(card).getByText('admin.myProfile.can.source_partner')).toBeTruthy()
  })
})

describe('the optional fourth language (owner, 2026-10-31)', () => {
  it('half of it (a fluency with no language) is refused inline and Save sleeps; both save with the reviewer card', async () => {
    signIn('reviewer')
    render(<ProfilePage />)
    const fluency = await screen.findByLabelText('admin.reviewer.otherLang.fluency')
    fireEvent.change(fluency, { target: { value: 'fluent' } })
    expect(await screen.findByTestId('other-language-incomplete')).toBeTruthy()
    await waitFor(() => expect(save().disabled).toBe(true))
    const pick = screen.getByDisplayValue('admin.reviewer.otherLang.select') as HTMLSelectElement
    fireEvent.change(pick, { target: { value: 'Kadazandusun' } })
    await waitFor(() => expect(screen.queryByTestId('other-language-incomplete')).toBeNull())
    fireEvent.click(save())
    await waitFor(() => expect(mockApi.updateReviewerProfile).toHaveBeenCalledWith(
      expect.objectContaining({ other_language: 'Kadazandusun', other_language_fluency: 'fluent' }), { token: 'tok' }))
  })

  it('does not count for the onboarding hold: English, BM or Tamil is still needed', async () => {
    signIn('reviewer', { reviewer_profile_complete: false })
    mockApi.getReviewerProfile.mockResolvedValue({ ...FULL_REVIEWER, english_fluency: '',
      other_language: 'Mandarin', other_language_fluency: 'fluent' })
    render(<ProfilePage />)
    expect(await screen.findByText('admin.reviewer.onboarding.title')).toBeTruthy()
    expect(screen.getByText('admin.reviewer.onboarding.languages')).toBeTruthy()
  })
})

describe('S2 review fixes', () => {
  it('M1: a review holder is told the people who assign their cases see the phone; others are not', async () => {
    signIn('reviewer')
    const { unmount } = render(<ProfilePage />)
    expect((await screen.findByTestId('phone-who-sees')).textContent).toBe('admin.myProfile.assignerSees')
    unmount()
    signIn('finance')
    render(<ProfilePage />)
    expect((await screen.findByTestId('phone-who-sees')).textContent).toBe('admin.myProfile.contactPrivate')
  })

  it('M2: when the other sessions could not be ended, the card says so', async () => {
    signIn('admin')
    mockApi.changeOwnPassword.mockResolvedValue({ ok: true, others_signed_out: false })
    refreshSession.mockResolvedValue({ error: null })
    render(<ProfilePage />)
    await fillPassword('old-secret', 'longenough1')
    submitPassword()
    expect(await screen.findByText('admin.myProfile.othersStillIn')).toBeTruthy()
  })
})
