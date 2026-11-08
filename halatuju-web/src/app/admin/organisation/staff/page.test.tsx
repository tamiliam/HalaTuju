/**
 * @jest-environment jsdom
 *
 * Organisation → Invitations, rendered. Owner's four-kind shape, 2026-08-03.
 *
 * The claims that matter here are mostly about ABSENCE, which a source-shape guard cannot see:
 * org_admin is listed but not offered; a sponsor row has no Revoke; Source invites only for the
 * roles that may (source sign-in S2 — its form and roster are pinned in `SourceInvite.test.tsx`).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import OrganisationInvitationsPage from './page'
import * as api from '@/lib/admin-api'
import { TH } from '@/components/admin/TableFrame'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (over: Partial<api.InvitationRow>): api.InvitationRow => ({
  id: 1, name: 'Someone', email: 's@example.org', role: 'admin', status: 'accepted',
  sent_at: '2026-07-21T00:00:00Z', send_count: 1, last_send_ok: true, last_send_error: '',
  accepted_at: '2026-07-22T00:00:00Z', admin_id: 10, is_active: true, paused: false,
  // Blank = EVERY gift, which is what a staff invitation carries and what every row written
  // before the column existed reads as.
  programme: '', programme_name: '', ...over,
})

const WAITING = { admins: 1, reviewers: 0, source: 0, mentor: 0, sponsors: 2 }
// EVERY invitation ever sent, per kind. ⚠ Bigger than WAITING on purpose: the accepted ones are no
// longer listed (2026-09-09), and `totals` is the only thing that lets the empty state tell
// "nobody asked yet" apart from "everybody asked has arrived".
const TOTALS = { admins: 2, reviewers: 13, source: 0, mentor: 0, sponsors: 2 }

/** The organisation's ACTIVE gifts. Default one — today's BrightPath shape, where the invite
 *  form asks nothing. Tests that need the picker pass two. */
let giftChoices: api.InvitationsPayload['programmes'] =
  [{ id: 7, code: 'flagship', name: 'BrightPath Bursary' }]

const payloadFor = (kind: api.InvitationKind): api.InvitationsPayload => {
  if (kind === 'admins') {
    return {
      kind, waiting: WAITING, totals: TOTALS, invitable_roles: ['admin', 'finance'],
      programmes: giftChoices,
      // ⚠ ONE ROW, AND SHE HAS NOT REPLIED. The server serves the WAITING ones only since
      // 2026-09-09; an accepted admin (there is one, hence TOTALS.admins = 2) belongs to
      // Organisation → People now. Putting an accepted row back in this fixture would test a
      // payload the endpoint cannot produce.
      invitations: [
        row({ id: 1, name: 'Yeoh Liew Se', role: 'admin', status: 'no_reply',
              accepted_at: null, admin_id: 10 }),
      ],
    }
  }
  if (kind === 'sponsors') {
    return {
      kind, waiting: WAITING, totals: TOTALS, invitable_roles: [], programmes: giftChoices,
      invitations: [row({ id: 3, name: 'Donor', role: '', status: 'invited',
                          accepted_at: null, admin_id: null, is_active: null,
                          programme: 'flagship', programme_name: 'BrightPath Bursary' })],
    }
  }
  return { kind, waiting: WAITING, totals: TOTALS,
           invitable_roles: kind === 'reviewers' ? ['reviewer', 'qc'] : [],
           programmes: giftChoices, reviewer_programmes: reviewerGiftChoices ?? giftChoices,
           invitations: [] }
}

/** The REVIEWER invite's own gift list (TD-501, A1.3 review); unset → the same as `giftChoices`. */
let reviewerGiftChoices: api.InvitationsPayload['programmes'] | undefined

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  giftChoices = [{ id: 7, code: 'flagship', name: 'BrightPath Bursary' }]
  reviewerGiftChoices = undefined
  mockApi.getInvitations.mockImplementation(async (kind) => payloadFor(kind))
  // `useStaffAdmin` still owns invite/resend/revoke, and loads the staff list on mount; the
  // auto-mock must answer it or the hook throws before anything renders.
  mockApi.getAdmins.mockResolvedValue({ admins: [] })
  mockApi.getInvitationEmails.mockResolvedValue(
    { templates: [] } as unknown as api.PartnerEmailsPayload)
})

const loaded = async () => {
  render(<OrganisationInvitationsPage />)
  await waitFor(() => expect(screen.getByText('Yeoh Liew Se')).toBeTruthy())
}

const pick = async (kind: string) => {
  fireEvent.click(screen.getByText(`admin.invitations.kindOne.${kind}`).closest('button')!)
  await waitFor(() => expect(mockApi.getInvitations).toHaveBeenCalledWith(kind, expect.anything()))
}

describe('the four kinds', () => {
  it('offers all four', async () => {
    await loaded()
    for (const k of ['admins', 'reviewers', 'source', 'sponsors']) {
      expect(screen.getByText(`admin.invitations.kindOne.${k}`)).toBeTruthy()
    }
  })

  it('⚠ names the KIND on the button and the STATE on the heading', async () => {
    // Owner, 2026-08-04, then 2026-09-09. The button completes "Invite as … Admin". The heading
    // used to repeat the kind ("Admins"), which over a waiting-only table read as a roster and
    // said "Admins (0)" on an organisation with five of them. It names what the rows ARE instead;
    // which kind you are looking at is already said by the pressed button.
    await loaded()
    expect(screen.getByText('admin.invitations.kindOne.admins')).toBeTruthy()
    expect(screen.getByText('admin.invitations.waitingHeading')).toBeTruthy()
    expect(screen.queryByText('admin.invitations.kind.admins')).toBeNull()
  })

  it('⚠ shows the waiting count for kinds NOT on screen', async () => {
    // Only one table is visible, so without this an invitation waiting elsewhere is invisible —
    // the exact failure the page exists to end.
    await loaded()
    const sponsors = screen.getByText('admin.invitations.kindOne.sponsors').closest('button')!
    expect(within(sponsors).getByText('2')).toBeTruthy()
  })

  it('shows one kind at a time', async () => {
    await loaded()
    expect(screen.getByText('Yeoh Liew Se')).toBeTruthy()
    await pick('sponsors')
    await waitFor(() => expect(screen.queryByText('Yeoh Liew Se')).toBeNull())
    expect(screen.getByText('Donor')).toBeTruthy()
  })
})

describe('listed is not the same as invitable', () => {
  // ⚠ THE "LISTED" HALF OF THIS PAIR MOVED TO ORGANISATION → PEOPLE ON 2026-09-09. An organisation
  // admin who has ACCEPTED is not shown here any more — nobody who has accepted is — so the claim
  // "an org_admin appears in the admins table" is now the People page's to make, and its test
  // makes it. What survives here is the half that was always the point: they are never OFFERED.

  it('⚠ never OFFERS organisation admin in the selector', async () => {
    // Appointing one is a platform act a super performs. Offering it here would let an org_admin
    // appoint their own successor.
    //
    // Asserted as the EXACT set rather than by querying for an org_admin label: no such label
    // exists, and naming one in a test conjures a key the i18n hygiene guard then demands — which
    // is how a phantom string gets added to satisfy a test rather than a screen.
    await loaded()
    const chips = Array.from(document.querySelectorAll('button'))
      .map((b) => b.textContent || '')
      .filter((s) => s.startsWith('admin.administration.staffRole.'))
    expect(chips).toEqual([
      'admin.administration.staffRole.admin',
      'admin.administration.staffRole.finance',
    ])
  })
})

describe('what each kind can do', () => {
  it('offers Resend to somebody still waiting', async () => {
    await loaded()
    expect(screen.getByText('admin.resend')).toBeTruthy()
  })

  it('⚠ offers REVOKE to nobody at all — it moved to Organisation → People', async () => {
    // The table holds only people who have NOT arrived, and revoking is something you do to
    // somebody who has. Leaving the control here would have been a button that could never fire.
    await loaded()
    expect(screen.queryByText('admin.revoke')).toBeNull()
    expect(screen.queryByText('admin.restore')).toBeNull()
  })

  it('⚠ offers NO action at all on a sponsor invitation beyond resending it', async () => {
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByText('Donor')).toBeTruthy())
    expect(screen.queryByText('admin.revoke')).toBeNull()
  })

  // ⚠ CHANGED ON PURPOSE (source sign-in S2, 2026-10-30): Source is no longer "coming soon". An
  // org_admin (or a super) invites a source's person here — which is also how a source is added.
  it('Source offers the invite form to an org_admin, and the "coming soon" note is gone', async () => {
    await loaded()
    await pick('source')
    await waitFor(() => expect(screen.getByTestId('source-invite-form')).toBeTruthy())
    expect(screen.getByTestId('source-roster')).toBeTruthy()
    expect(screen.queryByText('admin.invitations.sourceComingSoon')).toBeNull()
  })

  // Invitations I2 (owner ruling 2026-11-08): the Source tab lists the WAITING only, like every
  // tab — the "Signed in" table and its Remove moved to the Sources page.
  it('I2: the Source tab has no "Signed in" table and no Remove — even with a joined person', async () => {
    mockApi.getInvitations.mockImplementation(async (kind) => (kind === 'source' ? {
      ...payloadFor(kind), invitations: [],
      source_users: [{ id: 42, name: 'Audrey', email: 'muet@example.org', source_id: 3,
        source_name: 'MUETMyWay', source_code: 'muet', organisation: 'harapan', is_active: true,
        first_seen_at: '2026-10-20', last_seen_at: '2026-10-30', manageable: true, invitation: null }],
      sources: [{ id: 3, code: 'muet', name: 'MUETMyWay', organisation: 'harapan', sign_in: 'joined', user_count: 1 }],
    } as unknown as api.InvitationsPayload : payloadFor(kind)))
    await loaded()
    await pick('source')
    await waitFor(() => expect(screen.getByTestId('source-roster')).toBeTruthy())
    // Nobody waiting: the one table's empty state, and no second table at all.
    expect(screen.getByText('admin.invitations.source.noneWaiting')).toBeTruthy()
    expect(screen.getByTestId('source-roster').querySelectorAll('table')).toHaveLength(0)
    expect(screen.queryByText('Audrey')).toBeNull()
    expect(screen.queryByText('admin.invitations.source.signedIn')).toBeNull()
    expect(screen.queryByText('admin.invitations.source.remove')).toBeNull()
    expect(screen.queryByText('admin.sources.person.remove')).toBeNull()
  })

  it('⚠ shows Finance the Source roster read-only — no form, no actions', async () => {
    viewerRole = { role: 'finance' }
    await loaded()
    await pick('source')
    await waitFor(() => expect(screen.getByTestId('source-roster')).toBeTruthy())
    expect(screen.queryByTestId('source-invite-form')).toBeNull()
    expect(screen.queryByText('admin.resend')).toBeNull()
    expect(screen.getByText('admin.administration.viewOnlyNote')).toBeTruthy()
  })

  it('L5: a tab that could not be read says so — never an empty roster that reads as "nobody waiting"', async () => {
    await loaded()
    mockApi.getInvitations.mockRejectedValueOnce(new Error('down'))
    await pick('source')
    await waitFor(() => expect(screen.getByTestId('invitations-load-failed')).toBeTruthy())
    expect(screen.queryByTestId('source-roster')).toBeNull()
    expect(screen.queryByText('admin.invitations.source.noneWaiting')).toBeNull()
  })

  it('opens on the Source tab when the address asks for it (?kind=source, from Sources)', async () => {
    window.history.pushState({}, '', '/admin/organisation/staff?kind=source')
    try {
      render(<OrganisationInvitationsPage />)
      await waitFor(() => expect(screen.getByTestId('source-invite-form')).toBeTruthy())
      expect(mockApi.getInvitations).toHaveBeenLastCalledWith('source', { token: 'tok' })
    } finally { window.history.pushState({}, '', '/') }
  })
})

/**
 * Which gift a sponsor invitation is for (S-ASSIGN, 2026-09-04).
 *
 * Until now this form asked for an email, a name and a note and never asked which gift, so a
 * benefactor invited for Sabah would have registered straight into the flagship, silently —
 * and their credit would then have been refused `sponsor_not_in_programme`.
 */
describe('which gift a sponsor is invited into', () => {
  const inviteSponsorNamed = () => {
    fireEvent.change(screen.getByLabelText('admin.name'), { target: { value: 'Donor' } })
    fireEvent.change(screen.getByLabelText('admin.emailLabel'),
      { target: { value: 'donor@example.org' } })
  }

  const giftTick = (id: string) => screen.getByTestId(`invite-sponsor-gift-${id}`) as HTMLInputElement
  const TWO_GIFTS = [
    { id: 7, code: 'flagship', name: 'BrightPath Bursary' },
    { id: 9, code: 'sabah', name: 'Sabah Bursary' },
  ]

  it('I3: shows the tick list even with ONE gift, and pre-ticks that gift', async () => {
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByTestId('invite-sponsor-gift')).toBeTruthy())
    expect(giftTick('every').checked).toBe(false)
    expect(giftTick('gift-7').checked).toBe(true)
    expect(screen.getByText('admin.invitations.sponsorGiftHelp')).toBeTruthy()
  })

  it('sends that one gift by id — what the server would have taken anyway', async () => {
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    await waitFor(() => expect(giftTick('gift-7').checked).toBe(true))
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor', note: '', programme_ids: [7] }, { token: 'tok' }))
  })

  it('with one gift UN-ticked, sends no gift and the server takes the sole one', async () => {
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    await waitFor(() => expect(giftTick('gift-7').checked).toBe(true))
    fireEvent.click(giftTick('gift-7'))
    // allowNone: the last tick cleared is NOTHING, not a silent Every gift.
    expect(giftTick('every').checked).toBe(false)
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor', note: '' }, { token: 'tok' }))
  })

  it('names the tick list for a screen reader (role=group, labelled by its heading)', async () => {
    await loaded()
    await pick('sponsors')
    expect(await screen.findByRole('group', { name: 'admin.invitations.sponsorGiftLabel' })).toBeTruthy()
  })

  it('⚠ with two gifts starts with NOTHING ticked and refuses to send until a choice is made', async () => {
    giftChoices = TWO_GIFTS
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    await waitFor(() => expect(screen.getByTestId('invite-sponsor-gift-gift-9')).toBeTruthy())
    expect(giftTick('every').checked).toBe(false)
    expect(giftTick('gift-7').checked).toBe(false)
    expect(giftTick('gift-9').checked).toBe(false)
    fireEvent.click(screen.getByText('admin.sendInvite'))
    expect((await screen.findByRole('alert')).textContent).toBe('admin.invitations.sponsorGiftRequired')
    expect(mockApi.inviteSponsor).not.toHaveBeenCalled()
    // Ticking a gift clears the warning.
    fireEvent.click(giftTick('gift-9'))
    expect(screen.queryByText('admin.invitations.sponsorGiftRequired')).toBeNull()
  })

  it('sends several ticked gifts by id', async () => {
    giftChoices = TWO_GIFTS
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    await waitFor(() => expect(screen.getByTestId('invite-sponsor-gift-gift-9')).toBeTruthy())
    fireEvent.click(giftTick('gift-9'))
    fireEvent.click(giftTick('gift-7'))
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor', note: '', programme_ids: [7, 9] },
      { token: 'tok' }))
  })

  it('sends Every gift as an empty list', async () => {
    giftChoices = TWO_GIFTS
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    await waitFor(() => expect(screen.getByTestId('invite-sponsor-gift-every')).toBeTruthy())
    fireEvent.click(giftTick('every'))
    expect(giftTick('gift-7').disabled).toBe(true)
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor', note: '', programme_ids: [] },
      { token: 'tok' }))
  })

  it('⚠ says so when the invite is refused, rather than looking sent', async () => {
    giftChoices = TWO_GIFTS
    mockApi.inviteSponsor.mockRejectedValue(new Error('not_found'))
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    await waitFor(() => expect(screen.getByTestId('invite-sponsor-gift-gift-9')).toBeTruthy())
    fireEvent.click(giftTick('gift-9'))
    fireEvent.click(screen.getByText('admin.sendInvite'))
    expect(await screen.findByText('admin.invitations.inviteFailed')).toBeTruthy()
  })

  it('⚠ Resend on a donor row actually sends, and says so (BrightPath #16)', async () => {
    // The defect: the link was drawn, checked for a staff account, found none and returned in
    // silence. No request, no record, no message — which is why the owner could not tell whether
    // it had worked and was "inclined to repeat it".
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    fireEvent.click(screen.getAllByText('admin.resend')[0])
    // Re-issuing the invitation IS the resend: create_or_refresh finds the open row, moves its
    // expiry, sends and records. No note (it is not stored) and no programme_id (naming one would
    // re-home the benefactor into whichever gift the form is showing).
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 's@example.org', name: 'Donor' }, { token: 'tok' }))
    expect(await screen.findByText('admin.invitations.resent')).toBeTruthy()
  })

  it('⚠ and says so when it did NOT go, rather than looking successful', async () => {
    // The endpoint answers 502 when the letter failed. Silence here would rebuild the original
    // defect in a new place: an action that reports nothing reads as an action that worked.
    mockApi.inviteSponsor.mockRejectedValue(new Error('smtp down'))
    await loaded()
    await pick('sponsors')
    fireEvent.click(screen.getAllByText('admin.resend')[0])
    expect(await screen.findByText('admin.invitations.resendFailed')).toBeTruthy()
  })

  it('⚠ a STAFF row still resends through the account, which also rotates its password', async () => {
    // The other arm of the same link. A staff resend must NOT become a re-invitation: it goes
    // through the account so the temporary-password clock moves with it.
    await loaded()
    fireEvent.click(screen.getAllByText('admin.resend')[0])
    await waitFor(() => expect(mockApi.inviteSponsor).not.toHaveBeenCalled())
  })

  it('⚠ shows NO Role column on the sponsors table — it could only ever print a dash', async () => {
    // Owner, 2026-09-08, looking at the live table: "what is the purpose of the role column?" A
    // sponsor invitation creates no account and carries no role, so every row read "—" for ever.
    await loaded()
    await pick('sponsors')
    expect(screen.queryByText('admin.roleHeader')).toBeNull()
  })

  it('⚠ and KEEPS it on the staff tables, where it separates Admin from Finance', async () => {
    // The other direction, and the one that matters: this must not become "hide Role everywhere".
    // The role read is `admin` rather than `org_admin` since 2026-09-09 — the accepted org_admin
    // row left with every other accepted row; what is asserted is the COLUMN, not which role.
    await loaded()
    expect(screen.getByText('admin.roleHeader')).toBeTruthy()
    expect(screen.getByText('admin.role.admin')).toBeTruthy()
  })

  it('⚠ the note is a TEXTAREA inside the form, which is what stops Enter sending (#17)', async () => {
    // BrightPath #17, and the reason it was urgent: the note used to be a single-line box inside
    // this form, so Enter did the form's main action — posting an invitation to a DONOR, half
    // written, with no way to take it back.
    //
    // ⚠ THIS PINS THE TAG, NOT THE KEYSTROKE, AND THE FIRST VERSION OF THIS TEST DID THE
    // OPPOSITE AND WAS VACUOUS. "Press Enter, assert nothing was sent" PASSES against the broken
    // single-line box too: implicit form submission is a browser behaviour and **jsdom does not
    // implement it**, so no rendered test in this suite can ever observe the defect directly. It
    // was caught by injecting the old <input> and watching this file stay green. What decides the
    // real behaviour is the pair below — a textarea, inside the form — so that is what is
    // asserted. If this ever moves to a real-browser suite, assert the send there instead.
    await loaded()
    await pick('sponsors')
    const note = screen.getByPlaceholderText('admin.invitations.notePlaceholder')
    expect(note.tagName).toBe('TEXTAREA')
    expect(note.closest('form')).not.toBeNull()
  })

  it('sends a multi-line note as typed, with the breaks intact', async () => {
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    fireEvent.change(screen.getByPlaceholderText('admin.invitations.notePlaceholder'),
      { target: { value: 'Dear Ravi,\n\nWe would value your support.' } })
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor',
        note: 'Dear Ravi,\n\nWe would value your support.', programme_ids: [7] }, { token: 'tok' }))
  })

  it('shows which gift an existing invitation was for (a payload from before I3)', async () => {
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByText('Donor')).toBeTruthy())
    const cell = screen.getByText('Donor').closest('td')!
    expect(within(cell).getByText('BrightPath Bursary')).toBeTruthy()
  })

  it('I3: lists an invitation’s several gifts under the name, or Every gift', async () => {
    const sponsorsPayload = payloadFor('sponsors')
    mockApi.getInvitations.mockImplementation(async (kind) => (kind !== 'sponsors' ? payloadFor(kind) : {
      ...sponsorsPayload,
      invitations: [
        row({ id: 3, name: 'Donor', role: '', status: 'invited', accepted_at: null, admin_id: null,
              is_active: null, programme: '', programme_name: '', every_gift: false,
              gifts: [{ id: 7, code: 'flagship', name: 'BrightPath Bursary' },
                      { id: 9, code: 'sabah', name: 'Sabah Bursary' }] }),
        row({ id: 4, name: 'Patron', email: 'p@example.org', role: '', status: 'invited',
              accepted_at: null, admin_id: null, is_active: null, programme: '', programme_name: '',
              every_gift: true, gifts: [] }),
      ],
    }))
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByText('Patron')).toBeTruthy())
    expect(within(screen.getByText('Donor').closest('td')!)
      .getByText('BrightPath Bursary, Sabah Bursary')).toBeTruthy()
    expect(within(screen.getByText('Patron').closest('td')!)
      .getByText('admin.invitations.reviewerGiftEvery')).toBeTruthy()
  })

  it('⚠ prints nothing for a staff invitation, which carries no gift', async () => {
    // A blank means EVERY gift. An empty line under a staff row would read as a missing value.
    await loaded()
    const row = screen.getByText('Yeoh Liew Se').closest('td')!
    expect(row.querySelectorAll('div').length).toBe(0)
  })
})

describe('an empty table says WHICH empty it is', () => {
  // ⚠ THE EMPTY STATE IS THE USUAL STATE HERE since the table went waiting-only, so these words
  // are most of what the page shows on a settled organisation. Two different empties reach it and
  // they must not print the same sentence: on this tenant "nobody has been invited in this group
  // yet" would have sat over thirteen reviewers who all accepted.

  it('says everyone has accepted, and points at where they are', async () => {
    await loaded()
    await pick('reviewers')          // 0 waiting, 13 sent — TOTALS.reviewers
    await waitFor(() => expect(screen.getByText('admin.invitations.allAccepted')).toBeTruthy())
    const link = screen.getByText('admin.invitations.seePeople').closest('a')!
    expect(link.getAttribute('href')).toBe('/admin/organisation/reviewers?tab=reviewers')
  })

  it('⚠ but says nobody has been ASKED when nobody has — the other empty', async () => {
    // Drive over the bump: a page that always printed "everyone has accepted" would pass the
    // test above and lie about a group nobody has ever been invited into.
    mockApi.getInvitations.mockImplementation(async (kind) => ({
      ...payloadFor(kind), totals: { ...TOTALS, reviewers: 0 },
    }))
    await loaded()
    await pick('reviewers')
    await waitFor(() => expect(screen.getByText('admin.invitations.noneInKind')).toBeTruthy())
    expect(screen.queryByText('admin.invitations.allAccepted')).toBeNull()
  })

  it('⚠ carries the TAB, so an ADMINS question lands on the Admins tab', async () => {
    // Owner, 2026-09-09: sent bare, this link dropped you on Reviewers — a different answer to
    // the question you had just asked. The People page opens on Reviewers by default.
    mockApi.getInvitations.mockImplementation(async (kind) => (
      kind === 'admins' ? { ...payloadFor(kind), invitations: [] } : payloadFor(kind)))
    render(<OrganisationInvitationsPage />)
    await waitFor(() => expect(screen.getByText('admin.invitations.allAccepted')).toBeTruthy())
    expect(screen.getByText('admin.invitations.seePeople').closest('a')!.getAttribute('href'))
      .toBe('/admin/organisation/reviewers?tab=admins')
  })

  it('sends a benefactor to the benefactors, not to the staff directory', async () => {
    // Only the sponsors kind is emptied — `loaded()` waits for the admins table to arrive.
    mockApi.getInvitations.mockImplementation(async (kind) => (
      kind === 'sponsors' ? { ...payloadFor(kind), invitations: [] } : payloadFor(kind)))
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByText('admin.invitations.allAccepted')).toBeTruthy())
    expect(screen.getByText('admin.invitations.seeSponsors').closest('a')!.getAttribute('href'))
      .toBe('/admin/sponsors')
  })
})

describe('cancelling an invitation sent by mistake (TD-214)', () => {
  afterEach(() => jest.restoreAllMocks())

  it('offers Cancel on a waiting sponsor row, asks first, cancels it and reloads', async () => {
    const confirm = jest.spyOn(window, 'confirm').mockReturnValue(true)
    mockApi.cancelInvitation.mockResolvedValue({ id: 3, status: 'revoked' })
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByText('Donor')).toBeTruthy())
    const calls = mockApi.getInvitations.mock.calls.length
    fireEvent.click(screen.getByText('admin.invitations.cancel'))
    expect(confirm).toHaveBeenCalledWith('admin.invitations.cancelConfirm')
    await waitFor(() => expect(mockApi.cancelInvitation).toHaveBeenCalledWith(3, { token: 'tok' }))
    await waitFor(() => expect(screen.getByText('admin.invitations.cancelled')).toBeTruthy())
    expect(mockApi.getInvitations.mock.calls.length).toBeGreaterThan(calls)
  })

  it('offers it on a waiting STAFF row too, by the invitation id — not the account', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(true)
    mockApi.cancelInvitation.mockResolvedValue({ id: 1, status: 'revoked' })
    await loaded()
    fireEvent.click(screen.getByText('admin.invitations.cancel'))
    await waitFor(() => expect(mockApi.cancelInvitation).toHaveBeenCalledWith(1, { token: 'tok' }))
  })

  it('does nothing when the person says no', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(false)
    await loaded()
    fireEvent.click(screen.getByText('admin.invitations.cancel'))
    expect(mockApi.cancelInvitation).not.toHaveBeenCalled()
  })

  it('says so when the server refuses, rather than looking successful', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(true)
    mockApi.cancelInvitation.mockRejectedValue(new Error('not_open'))
    await loaded()
    fireEvent.click(screen.getByText('admin.invitations.cancel'))
    await waitFor(() => expect(screen.getByText('admin.invitations.cancelFailed')).toBeTruthy())
  })

  it('⚠ never offers an org_admin Cancel on an organisation-admin invitation; a super gets it', async () => {
    // Review fix (2026-10-05): the rows an org_admin could not have sent. The server 404s it too.
    const withOrgAdminRow = async (kind: api.InvitationKind) => {
      const p = payloadFor(kind)
      return kind === 'admins'
        ? { ...p, invitations: [row({ id: 9, name: 'Org Head', role: 'org_admin', status: 'invited',
                                      accepted_at: null, admin_id: 11 })] }
        : p
    }
    mockApi.getInvitations.mockImplementation(withOrgAdminRow)
    const { unmount } = render(<OrganisationInvitationsPage />)
    await waitFor(() => expect(screen.getByText('Org Head')).toBeTruthy())
    expect(screen.getByText('admin.resend')).toBeTruthy()
    expect(screen.queryByText('admin.invitations.cancel')).toBeNull()
    unmount()

    viewerRole = { role: 'super', is_super_admin: true }
    render(<OrganisationInvitationsPage />)
    await waitFor(() => expect(screen.getByText('Org Head')).toBeTruthy())
    expect(screen.getByText('admin.invitations.cancel')).toBeTruthy()
  })

  it('⚠ offers it to nobody who may only look', async () => {
    viewerRole = { role: 'finance' }
    render(<OrganisationInvitationsPage />)
    await waitFor(() => expect(screen.getByText('Yeoh Liew Se')).toBeTruthy())
    expect(screen.queryByText('admin.invitations.cancel')).toBeNull()
  })
})

describe('the page shell', () => {
  it('carries the Invitations and Emails tabs', async () => {
    await loaded()
    expect(screen.getByText('admin.invitations.tab.invitations')).toBeTruthy()
    expect(screen.getByText('admin.invitations.tab.emails')).toBeTruthy()
  })

  it('shows finance the page with no invite form', async () => {
    viewerRole = { role: 'finance' }
    render(<OrganisationInvitationsPage />)
    await waitFor(() => expect(screen.getByText('Yeoh Liew Se')).toBeTruthy())
    expect(screen.queryByText('admin.sendInvite')).toBeNull()
    expect(screen.getByText('admin.administration.viewOnlyNote')).toBeTruthy()
  })
})

/**
 * Request #39 S1: an address that already has an account. The SERVER words both answers — the
 * page adds no string for either, it shows what it was sent (the cross-organisation one confirms
 * nothing about the other account, and only the server knows which case it is).
 */
describe('inviting an address that already has an account', () => {
  const refuse = (text: string, code: string) => {
    const err = new Error(text) as Error & { code?: string }
    err.code = code
    mockApi.inviteAdmin.mockRejectedValue(err)
  }
  const send = async (email: string) => {
    await loaded()
    fireEvent.change(screen.getByLabelText('admin.name'), { target: { value: 'Rohini' } })
    fireEvent.change(screen.getByLabelText('admin.emailLabel'), { target: { value: email } })
    fireEvent.click(screen.getByText('admin.sendInvite'))
  }

  it('shows the served sentence naming a colleague, as a warning not an error', async () => {
    const said = 'Rohini is already on your team as Reviewer. To change what they can do, open People → Rohini.'
    refuse(said, 'already_on_team')
    await send('rohini@example.org')
    const banner = await screen.findByText(said)
    expect(banner.className).toContain('bg-caution-50')
    expect(mockApi.inviteAdmin).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'rohini@example.org' }), expect.anything())
  })

  it('shows the neutral sentence for anyone else exactly as served, as an error', async () => {
    const said = "This email address can't be invited. Ask HalaTuju support."
    refuse(said, 'not_invitable')
    await send('someone@elsewhere.org')
    const banner = await screen.findByText(said)
    expect(banner.className).toContain('bg-critical-50')
  })
})

/**
 * A REVIEWER invite names its gifts (TD-501 A1.3; multi-gift, owner design 2026-11-06). The same
 * tick list as the pencil pop-over, with "Every gift" ticked BY DEFAULT and a helper line. It is
 * always sent as `programme_ids` (`[]` = every gift). Admins are not asked.
 */
describe('a reviewer invite names its gifts', () => {
  beforeEach(() => {
    giftChoices = [{ id: 7, code: 'flagship', name: 'BrightPath Bursary' },
                   { id: 9, code: 'sabah', name: 'Sabah Gift' }]
    mockApi.inviteAdmin.mockResolvedValue({ message: 'Sent' } as Awaited<ReturnType<typeof api.inviteAdmin>>)
  })
  const fill = () => {
    fireEvent.change(screen.getByLabelText('admin.name'), { target: { value: 'Asha' } })
    fireEvent.change(screen.getByLabelText('admin.emailLabel'), { target: { value: 'asha@example.org' } })
  }
  const tick = (id: string) => screen.getByTestId(`invite-reviewer-gift-${id}`) as HTMLInputElement

  it('offers Every gift, ticked by default, the gifts greyed, and the helper line', async () => {
    await loaded()
    await pick('reviewers')
    await waitFor(() => expect(screen.getByTestId('invite-reviewer-gift')).toBeTruthy())
    expect(tick('every').checked).toBe(true)
    expect(tick('gift-7').disabled).toBe(true)
    expect(tick('gift-9').disabled).toBe(true)
    expect(screen.getByText('admin.invitations.reviewerGiftHelp')).toBeTruthy()
    expect(screen.getByRole('group', { name: 'admin.invitations.reviewerGiftLabel' })).toBeTruthy()
  })

  it('offers only the gifts the server lists for the reviewer invite, never another organisation’s', async () => {
    // Regression (A1.3 review): a super's `programmes` holds every organisation's gifts, but the
    // invite binds to one organisation and refuses the rest, so the list reads its own payload.
    giftChoices = [...giftChoices, { id: 11, code: 'other', name: 'Another Tenant Gift' }]
    reviewerGiftChoices = [{ id: 7, code: 'flagship', name: 'BrightPath Bursary' },
                           { id: 9, code: 'sabah', name: 'Sabah Gift' }]
    await loaded()
    await pick('reviewers')
    await waitFor(() => expect(screen.getByTestId('invite-reviewer-gift')).toBeTruthy())
    expect(screen.queryByTestId('invite-reviewer-gift-gift-11')).toBeNull()
    expect(tick('gift-9')).toBeTruthy()
  })

  it('sends the ticked gifts by id', async () => {
    await loaded()
    await pick('reviewers')
    fill()
    await waitFor(() => expect(screen.getByTestId('invite-reviewer-gift')).toBeTruthy())
    fireEvent.click(tick('every'))
    fireEvent.click(tick('gift-9'))
    fireEvent.click(tick('gift-7'))
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteAdmin).toHaveBeenCalledWith(
      { email: 'asha@example.org', name: 'Asha', role: 'reviewer', programme_ids: [7, 9] },
      expect.anything()))
  })

  it('sends every gift (an empty list) when nothing is changed', async () => {
    await loaded()
    await pick('reviewers')
    fill()
    await waitFor(() => expect(screen.getByTestId('invite-reviewer-gift')).toBeTruthy())
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteAdmin).toHaveBeenCalledWith(
      { email: 'asha@example.org', name: 'Asha', role: 'reviewer', programme_ids: [] },
      expect.anything()))
  })

  it('does not ask an admin invite, and sends no gift for it', async () => {
    await loaded()
    expect(screen.queryByTestId('invite-reviewer-gift')).toBeNull()
    fill()
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteAdmin).toHaveBeenCalledWith(
      { email: 'asha@example.org', name: 'Asha', role: 'admin' }, expect.anything()))
  })
})

describe('S7b follow-up: the Mentor kind, like Source', () => {
  afterEach(() => { window.history.replaceState({}, '', '/') })

  it('shows the Mentor chip, with its waiting count, to super and org_admin only', async () => {
    mockApi.getInvitations.mockImplementation(async (kind) => ({ ...payloadFor(kind), waiting: { ...WAITING, mentor: 3 } }))
    for (const [who, shown] of [[{ role: 'org_admin' }, true], [{ role: 'super', is_super_admin: true }, true],
      [{ role: 'admin' }, false], [{ role: 'finance' }, false]] as const) {
      viewerRole = who
      const { unmount } = render(<OrganisationInvitationsPage />)
      await waitFor(() => expect(screen.getByText('Yeoh Liew Se')).toBeTruthy())
      const chip = screen.queryByText('admin.invitations.kindOne.mentor')
      expect([who.role, !!chip]).toEqual([who.role, shown])
      if (chip) expect(chip.closest('button')!.textContent).toContain('3')
      unmount()
    }
  })

  it('?kind=mentor opens the Mentor tab with its form and its roster', async () => {
    window.history.replaceState({}, '', '/admin/organisation/staff?kind=mentor')
    render(<OrganisationInvitationsPage />)
    await waitFor(() => expect(mockApi.getInvitations).toHaveBeenCalledWith('mentor', expect.anything()))
    expect(await screen.findByTestId('mentor-invite-form')).toBeTruthy()
    expect(await screen.findByTestId('mentor-roster')).toBeTruthy()
  })

  it('an admin asking for ?kind=mentor stays on Admins', async () => {
    viewerRole = { role: 'admin' }
    window.history.replaceState({}, '', '/admin/organisation/staff?kind=mentor')
    render(<OrganisationInvitationsPage />)
    await waitFor(() => expect(screen.getByText('Yeoh Liew Se')).toBeTruthy())
    expect(mockApi.getInvitations).not.toHaveBeenCalledWith('mentor', expect.anything())
  })
})

/**
 * I1 (2026-11-08, roadmap `2026-11-08-invitations-consistency-roadmap.md`): the five Invite-as tabs
 * wear ONE form layout (a label above every box, the tab's note under the fields, Send Invite at the
 * left beneath it — never pushed right beside a note) and draw ONE waiting table (the same `TH`
 * headings, "Waiting (date)", Resend + a red "Cancel invitation").
 */
describe('I1: one form and one waiting table on every tab', () => {
  const TAB: Record<string, { nameLabel: string; note: string | null; lead?: string; role?: boolean }> = {
    admins: { nameLabel: 'admin.name', note: 'admin.team.inviteAdminNote', role: true },
    reviewers: { nameLabel: 'admin.name', note: 'admin.invitations.reviewerGiftHelp', role: true },
    mentor: { nameLabel: 'admin.mentors.invite.name', note: 'admin.mentors.invite.note' },
    source: { nameLabel: 'admin.invitations.source.personName', note: 'admin.invitations.source.note',
              lead: 'admin.invitations.source.col.source' },
    sponsors: { nameLabel: 'admin.name', note: 'admin.invitations.sponsorGiftHelp' },
  }

  beforeEach(() => {
    viewerRole = { role: 'super', is_super_admin: true }
    mockApi.getInvitations.mockImplementation(async (kind) => {
      const base = payloadFor(kind)
      if (kind === 'reviewers') {
        return { ...base, invitations: [row({ id: 2, name: 'Asha', role: 'reviewer', status: 'invited',
                                              accepted_at: null, admin_id: 11 })] }
      }
      if (kind === 'source') {
        return { ...base, sources: [], invitations: [row({ id: 31, name: 'Shah', email: 'shah@example.org',
          role: 'source_partner', status: 'invited', accepted_at: null, admin_id: 41,
          source_name: 'LearnifAI' } as Partial<api.InvitationRow>)],
          source_users: [{ id: 41, name: 'Shah', email: 'shah@example.org', source_id: 2, source_name: 'LearnifAI',
            source_code: 'learnifi', organisation: 'harapan', is_active: true, first_seen_at: null,
            last_seen_at: null, manageable: true, invitation: null }],
        } as unknown as api.InvitationsPayload
      }
      if (kind === 'mentor') {
        return { ...base, invitations: [row({ id: 51, name: 'Priya', email: 'priya@example.org', role: 'mentor',
          status: 'invited', accepted_at: null, admin_id: 99, mentor_id: 7 } as Partial<api.InvitationRow>)],
          mentors: [{ id: 7, name: 'Priya', email: 'priya@example.org', manageable: true }],
        } as unknown as api.InvitationsPayload
      }
      return base
    })
    mockApi.mentorAction.mockResolvedValue({ emailed: true } as unknown as Awaited<ReturnType<typeof api.mentorAction>>)
    window.confirm = jest.fn(() => true)
  })

  it.each(Object.keys(TAB))('%s: labels above the boxes, the note under them, Send Invite at the left', async (kind) => {
    await loaded()
    if (kind !== 'admins') await pick(kind)
    const foot = await screen.findByTestId('invite-foot')
    const form = foot.closest('form')!
    const want = TAB[kind]
    // A visible label names every box (no placeholder-only boxes).
    expect(within(form).getByLabelText(want.nameLabel).tagName).toBe('INPUT')
    expect((within(form).getByLabelText('admin.emailLabel') as HTMLInputElement).type).toBe('email')
    // The button sits in the shared foot, under the note, never in a justify-between row beside it.
    const button = within(foot).getByText('admin.sendInvite')
    expect(button.parentElement).toBe(foot)
    expect(foot.className).not.toContain('justify-between')
    expect(button.closest('.justify-between')).toBeNull()
    const note = within(foot).queryByTestId('invite-note')
    if (want.note) {
      expect(note?.textContent).toBe(want.note)
      expect(note!.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    } else {
      expect(note).toBeNull()
    }
  })

  it.each(Object.keys(TAB))('%s: the one waiting table — same TH headings, Waiting (date), red Cancel invitation', async (kind) => {
    await loaded()
    if (kind !== 'admins') await pick(kind)
    const table = await screen.findByTestId('invitations-table')
    const want = TAB[kind]
    const heads = within(table).getAllByRole('columnheader')
    expect(heads.map((h) => h.textContent)).toEqual([
      ...(want.lead ? [want.lead] : []), 'admin.nameHeader', 'admin.emailHeader',
      ...(want.role ? ['admin.roleHeader'] : []), 'admin.statusHeader', 'admin.actionHeader'])
    for (const h of heads) expect(h.className).toBe(TH)
    // Phone cards: the frame restacks the rows below md.
    expect(table.querySelector('[data-phone-rows]')).toBeTruthy()
    // Admins' fixture row has had no reply; the rest are plain waiting.
    expect(within(table).getByText(/^admin\.invitations\.status\.(invited|no_reply) \(/)).toBeTruthy()
    expect(within(table).getByText('admin.resend')).toBeTruthy()
    expect(within(table).getByText('admin.invitations.cancel').className).toContain('text-critical-600')
    expect(within(table).queryByText('admin.mentors.action.revoke')).toBeNull()
  })

  it('Mentor: "Cancel invitation" still calls the mentor REVOKE (with its confirm), never the generic Cancel', async () => {
    await loaded()
    await pick('mentor')
    const table = await screen.findByTestId('invitations-table')
    fireEvent.click(within(table).getByText('admin.invitations.cancel'))
    expect(window.confirm).toHaveBeenCalledWith('admin.mentors.confirm.revoke')
    await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(7, 'revoke', { token: 'tok' }))
    expect(mockApi.cancelInvitation).not.toHaveBeenCalled()
  })
})
