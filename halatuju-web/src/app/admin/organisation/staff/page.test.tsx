/**
 * @jest-environment jsdom
 *
 * Organisation → Invitations, rendered. Owner's four-kind shape, 2026-08-03.
 *
 * The claims that matter here are mostly about ABSENCE, which a source-shape guard cannot see:
 * org_admin is listed but not offered; a sponsor row has no Revoke; Source offers no invite form.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import OrganisationInvitationsPage from './page'
import * as api from '@/lib/admin-api'

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

const WAITING = { admins: 1, reviewers: 0, source: 0, sponsors: 2 }
// EVERY invitation ever sent, per kind. ⚠ Bigger than WAITING on purpose: the accepted ones are no
// longer listed (2026-09-09), and `totals` is the only thing that lets the empty state tell
// "nobody asked yet" apart from "everybody asked has arrived".
const TOTALS = { admins: 2, reviewers: 13, source: 0, sponsors: 2 }

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
           programmes: giftChoices, invitations: [] }
}

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  giftChoices = [{ id: 7, code: 'flagship', name: 'BrightPath Bursary' }]
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

  it('says Source is coming soon and offers no way to invite one', async () => {
    await loaded()
    await pick('source')
    await waitFor(() =>
      expect(screen.getAllByText('admin.invitations.sourceComingSoon').length).toBeGreaterThan(0))
    expect(screen.queryByText('admin.sendInvite')).toBeNull()
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
    fireEvent.change(screen.getByPlaceholderText('admin.name'), { target: { value: 'Donor' } })
    fireEvent.change(screen.getByPlaceholderText('admin.emailLabel'),
      { target: { value: 'donor@example.org' } })
  }

  it('⚠ asks NOTHING when the organisation runs one gift — today’s BrightPath form', async () => {
    await loaded()
    await pick('sponsors')
    expect(screen.queryByText('admin.invitations.giftLabel')).toBeNull()
  })

  it('sends no gift in that case, and the server takes the sole one', async () => {
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor', note: '' }, { token: 'tok' }))
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
        note: 'Dear Ravi,\n\nWe would value your support.' }, { token: 'tok' }))
  })

  it('asks once there are two, and starts BLANK — never a silent default', async () => {
    giftChoices = [
      { id: 7, code: 'flagship', name: 'BrightPath Bursary' },
      { id: 9, code: 'sabah', name: 'Sabah Bursary' },
    ]
    await loaded()
    await pick('sponsors')
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('')
    expect(select.required).toBe(true)
  })

  it('sends the chosen gift', async () => {
    giftChoices = [
      { id: 7, code: 'flagship', name: 'BrightPath Bursary' },
      { id: 9, code: 'sabah', name: 'Sabah Bursary' },
    ]
    mockApi.inviteSponsor.mockResolvedValue({ id: 1, emailed: true })
    await loaded()
    await pick('sponsors')
    inviteSponsorNamed()
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '9' } })
    fireEvent.click(screen.getByText('admin.sendInvite'))
    await waitFor(() => expect(mockApi.inviteSponsor).toHaveBeenCalledWith(
      { email: 'donor@example.org', name: 'Donor', note: '', programme_id: 9 },
      { token: 'tok' }))
  })

  it('shows which gift an existing invitation was for', async () => {
    await loaded()
    await pick('sponsors')
    await waitFor(() => expect(screen.getByText('Donor')).toBeTruthy())
    expect(screen.getByText('BrightPath Bursary')).toBeTruthy()
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
    expect(link.getAttribute('href')).toBe('/admin/organisation/reviewers')
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
