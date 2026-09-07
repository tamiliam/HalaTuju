/**
 * @jest-environment jsdom
 *
 * "Configuration" — rendered (Org Config Sprint A).
 *
 * The registry's rules are pinned server-side in `test_org_config.py`. What is tested HERE is what
 * a pure test cannot see:
 *
 *  - a blank box means "follow the platform default" and the default is NAMED beside it;
 *  - Save is asleep until a value actually differs from what is stored (the nothing-to-save
 *    platform standard), and an out-of-range value puts it back to sleep with the reason shown;
 *  - the PUT carries ONLY the changed keys, and clearing a box sends null — never a copied default;
 *  - a refusal from the SERVER is rendered even when the browser thought the value was fine;
 *  - every registry key rendered has words behind it in all three languages.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import OrganisationConfigurationTab, { hhmmToMinutes, minutesToHhmm } from './OrganisationConfigurationTab'
import * as api from '@/lib/admin-api'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, vars?: Record<string, string>) =>
      (vars ? `${k}|${Object.values(vars).join(',')}` : k),
  }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const KEY = 'pool_funded_grace_days'

// The Sprint B registry rows, as the server payload carries them. They ride in every fixture so
// the tri-language walk below covers them and the group ordering is exercised as rendered.
const SPRINT_B: api.OrganisationConfigSetting[] = [
  { key: 'sponsor_email_max_cards', group: 'sponsor_page', unit: 'cards',
    min: 1, max: 20, value: null, default: 5 },
  { key: 'query_email_delay_hours', group: 'student_comms', unit: 'hours',
    min: 1, max: 168, value: null, default: 2 },
  { key: 'nudge_auto_delay_minutes', group: 'student_comms', unit: 'minutes',
    min: 5, max: 1440, value: null, default: 30 },
  { key: 'nudge_cooldown_hours', group: 'student_comms', unit: 'hours',
    min: 1, max: 168, value: null, default: 24 },
  { key: 'max_clarify_open', group: 'student_comms', unit: 'questions',
    min: 1, max: 10, value: null, default: 3 },
]

// The Sprint C registry rows — reviewers & staff, all in days.
const SPRINT_C: api.OrganisationConfigSetting[] = [
  { key: 'review_sla_days', group: 'reviewers_staff', unit: 'days',
    min: 1, max: 60, value: null, default: 10 },
  { key: 'review_nudge_soon_days', group: 'reviewers_staff', unit: 'days',
    min: 1, max: 30, value: null, default: 2 },
  { key: 'review_escalate_grace_days', group: 'reviewers_staff', unit: 'days',
    min: 1, max: 30, value: null, default: 4 },
  { key: 'temp_password_ttl_days', group: 'reviewers_staff', unit: 'days',
    min: 1, max: 30, value: null, default: 7 },
  { key: 'admin_dormant_days', group: 'reviewers_staff', unit: 'days',
    min: 7, max: 365, value: null, default: 90 },
]

// The Sprint D registry rows — interviews. Two shapes the tab had never drawn before: a CLOCK
// row (stored as minutes past midnight, typed as HH:MM) and a row whose vocabulary is a LIST.
const SPRINT_D: api.OrganisationConfigSetting[] = [
  { key: 'interview_duration_min', group: 'interviews', unit: 'minutes',
    min: 10, max: 180, value: null, default: 30 },
  { key: 'interview_window_start_min', group: 'interviews', unit: 'time_of_day',
    min: 0, max: 1439, value: null, default: 480 },
  { key: 'interview_window_end_min', group: 'interviews', unit: 'time_of_day',
    min: 0, max: 1439, value: null, default: 1290 },
  { key: 'interview_slot_step_min', group: 'interviews', unit: 'minutes',
    min: 5, max: 60, value: null, default: 30, allowed: [5, 10, 15, 20, 30, 60] },
  { key: 'interview_min_lead_hours', group: 'interviews', unit: 'hours',
    min: 1, max: 168, value: null, default: 24 },
  { key: 'interview_reschedule_cutoff_hours', group: 'interviews', unit: 'hours',
    min: 1, max: 168, value: null, default: 12 },
]

// The Sprint E registry rows — documents.
const SPRINT_E: api.OrganisationConfigSetting[] = [
  { key: 'max_doc_size_mb', group: 'documents', unit: 'megabytes',
    min: 1, max: 25, value: null, default: 8 },
  { key: 'max_docs_per_application', group: 'documents', unit: 'documents',
    min: 5, max: 200, value: null, default: 40 },
  { key: 'max_other_docs', group: 'documents', unit: 'documents',
    min: 1, max: 50, value: null, default: 10 },
  { key: 'doc_stage_max_attempts', group: 'documents', unit: 'attempts',
    min: 1, max: 10, value: null, default: 3 },
]

// The Sprint F registry rows — agreements. The FOUNDATION SIGNATORY is deliberately not here:
// it lives on the organisation's contract template, which is what prints on the agreement.
const SPRINT_F: api.OrganisationConfigSetting[] = [
  { key: 'sign_accept_deadline_days', group: 'agreements', unit: 'days',
    min: 1, max: 180, value: null, default: 30 },
  { key: 'sign_reminder_days', group: 'agreements', unit: 'days',
    min: 1, max: 60, value: null, default: 3 },
]

function config(over: Partial<api.OrganisationConfigSetting> = {}): api.OrganisationConfiguration {
  return {
    organisation: { code: 'alpha', name: 'Alpha Foundation' },
    settings: [{
      key: KEY, group: 'sponsor_page', unit: 'days', min: 1, max: 90,
      value: null, default: 2, ...over,
    }, ...SPRINT_B, ...SPRINT_C, ...SPRINT_D, ...SPRINT_E, ...SPRINT_F],
  }
}

/** Replace one Sprint D row in the fixture (to give a clock row a stored value, say). */
function configWith(key: string, over: Partial<api.OrganisationConfigSetting>) {
  const cfg = config()
  cfg.settings = cfg.settings.map((s) => (s.key === key ? { ...s, ...over } : s))
  return cfg
}

async function mount() {
  render(<OrganisationConfigurationTab />)
  // One `config-rows` list per GROUP — two groups since Sprint B, so getAll.
  await waitFor(() => expect(screen.getAllByTestId('config-rows').length).toBeGreaterThan(0))
}

const box = () => screen.getByTestId(`config-${KEY}`) as HTMLInputElement
const save = () => screen.getByTestId('save-config') as HTMLButtonElement
const outcome = () => screen.getByTestId('config-outcome').textContent

function type(value: string) {
  fireEvent.change(box(), { target: { value } })
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getOrganisationConfiguration.mockResolvedValue(config())
})

describe('a blank box means the platform default', () => {
  it('renders empty with the default as placeholder and named underneath', async () => {
    await mount()
    expect(box().value).toBe('')
    expect(box().placeholder).toBe('2')
    // The note interpolates {n} and {unit} — the harness renders vars after a pipe. Scoped to
    // THIS row's list item: since Sprint C, `review_nudge_soon_days` also reads "2, days", so a
    // page-wide query would match two rows.
    const row = box().closest('li') as HTMLElement
    expect(within(row).getByText(
      /admin\.orgSettings\.config\.defaultNote\|2,admin\.orgSettings\.config\.unit\.days/,
    )).toBeTruthy()
  })

  it('renders the stored value when the organisation has chosen one', async () => {
    mockApi.getOrganisationConfiguration.mockResolvedValue(config({ value: 30 }))
    await mount()
    expect(box().value).toBe('30')
  })
})

describe('saving', () => {
  // ⚠ IDLE SAYS NOTHING (owner, 2026-09-07). It used to say "No unsaved changes" while three
  // sibling tabs said three other things; the greyed button carries that fact and the tooltip
  // carries the words.
  it('is asleep with nothing changed, and says nothing about it', async () => {
    await mount()
    expect(save().disabled).toBe(true)
    expect(outcome()).toBe('')
    expect(save().title).toBe('common.nothingToSave')
  })

  it('wakes on a real edit and sends ONLY the changed key', async () => {
    mockApi.saveOrganisationConfiguration.mockResolvedValue(config({ value: 30 }))
    await mount()
    type('30')
    expect(save().disabled).toBe(false)
    expect(outcome()).toBe('common.unsavedChanges')
    fireEvent.click(save())
    await waitFor(() => expect(outcome()).toBe('admin.orgSettings.config.saved'))
    expect(mockApi.saveOrganisationConfiguration).toHaveBeenCalledWith(
      { [KEY]: 30 }, undefined, { token: 'tok' })
    expect(box().value).toBe('30')
  })

  it('typing the stored value back puts Save to sleep — nothing to save', async () => {
    mockApi.getOrganisationConfiguration.mockResolvedValue(config({ value: 30 }))
    await mount()
    type('7')
    expect(save().disabled).toBe(false)
    type('30')
    expect(save().disabled).toBe(true)
  })

  it('clearing the box sends null — back to the platform default, never a copied default', async () => {
    mockApi.getOrganisationConfiguration.mockResolvedValue(config({ value: 30 }))
    mockApi.saveOrganisationConfiguration.mockResolvedValue(config({ value: null }))
    await mount()
    type('')
    fireEvent.click(save())
    await waitFor(() => expect(outcome()).toBe('admin.orgSettings.config.saved'))
    expect(mockApi.saveOrganisationConfiguration).toHaveBeenCalledWith(
      { [KEY]: null }, undefined, { token: 'tok' })
  })

  it('an out-of-range or non-numeric value sleeps Save and says why at the row', async () => {
    await mount()
    for (const bad of ['365', '0', 'abc', '2.5']) {
      type(bad)
      expect(save().disabled).toBe(true)
      expect(screen.getByTestId(`config-${KEY}-invalid`)).toBeTruthy()
    }
    expect(outcome()).toBe('admin.orgSettings.config.invalid')
  })

  it('renders the SERVER refusal even when the browser thought the value was fine', async () => {
    const err = Object.assign(new Error('bad'), {
      body: { code: 'out_of_range', key: KEY },
    })
    mockApi.saveOrganisationConfiguration.mockRejectedValue(err)
    await mount()
    type('30')
    fireEvent.click(save())
    await waitFor(() => expect(outcome()).toContain('admin.orgSettings.config.refused'))
  })

  it('a failure with no code renders the generic line — no silent branch', async () => {
    mockApi.saveOrganisationConfiguration.mockRejectedValue(new Error('boom'))
    await mount()
    type('30')
    fireEvent.click(save())
    await waitFor(() => expect(outcome()).toBe('admin.orgSettings.config.errorGeneric'))
  })
})

describe('the Sprint B rows render, grouped and ordered', () => {
  it('draws every new box, with Student communications after Sponsor page', async () => {
    await mount()
    for (const s of SPRINT_B) {
      expect(screen.getByTestId(`config-${s.key}`)).toBeTruthy()
    }
    const text = document.body.textContent || ''
    const sponsor = text.indexOf('admin.orgSettings.config.group.sponsor_page')
    const comms = text.indexOf('admin.orgSettings.config.group.student_comms')
    expect(sponsor).toBeGreaterThanOrEqual(0)
    expect(comms).toBeGreaterThan(sponsor)
  })

  it('draws the Sprint C rows, with Reviewers & staff after Student communications', async () => {
    await mount()
    for (const s of SPRINT_C) {
      expect(screen.getByTestId(`config-${s.key}`)).toBeTruthy()
    }
    const text = document.body.textContent || ''
    const comms = text.indexOf('admin.orgSettings.config.group.student_comms')
    const staff = text.indexOf('admin.orgSettings.config.group.reviewers_staff')
    expect(comms).toBeGreaterThanOrEqual(0)
    expect(staff).toBeGreaterThan(comms)
  })

  it('every unit label sits in a fixed-width column so the boxes align down the page', async () => {
    // With a natural-width unit the right-aligned pair shifts each BOX by the unit's length
    // ("days" vs "questions") — the owner read it as untidy on 2026-09-07. The width class is
    // the alignment; losing it brings the drift back.
    await mount()
    for (const s of [{ key: KEY }, ...SPRINT_B, ...SPRINT_C, ...SPRINT_D, ...SPRINT_E, ...SPRINT_F]) {
      const unit = screen.getByTestId(`config-${s.key}-unit`)
      expect(unit.className).toContain('w-24')
    }
  })

  it('draws the Sprint F rows, with Agreements last', async () => {
    await mount()
    for (const s of SPRINT_F) {
      expect(screen.getByTestId(`config-${s.key}`)).toBeTruthy()
    }
    const text = document.body.textContent || ''
    const documents = text.indexOf('admin.orgSettings.config.group.documents')
    const agreements = text.indexOf('admin.orgSettings.config.group.agreements')
    expect(documents).toBeGreaterThanOrEqual(0)
    expect(agreements).toBeGreaterThan(documents)
  })

  it('draws the Sprint E rows, with Documents after Interviews', async () => {
    await mount()
    for (const s of SPRINT_E) {
      expect(screen.getByTestId(`config-${s.key}`)).toBeTruthy()
    }
    const text = document.body.textContent || ''
    const interviews = text.indexOf('admin.orgSettings.config.group.interviews')
    const documents = text.indexOf('admin.orgSettings.config.group.documents')
    expect(interviews).toBeGreaterThanOrEqual(0)
    expect(documents).toBeGreaterThan(interviews)
  })

  it('draws the Sprint D rows, with Interviews after Reviewers & staff', async () => {
    await mount()
    for (const s of SPRINT_D) {
      expect(screen.getByTestId(`config-${s.key}`)).toBeTruthy()
    }
    const text = document.body.textContent || ''
    const staff = text.indexOf('admin.orgSettings.config.group.reviewers_staff')
    const interviews = text.indexOf('admin.orgSettings.config.group.interviews')
    expect(staff).toBeGreaterThanOrEqual(0)
    expect(interviews).toBeGreaterThan(staff)
  })
})

describe('a clock row types a time, and stores a number', () => {
  const clock = () => screen.getByTestId('config-interview_window_start_min') as HTMLInputElement

  it('is a PLAIN box showing the default as HH:MM, not 480 and not type="time"', async () => {
    // ⚠ `type="time"` is what shipped first and it was wrong (owner, 2026-09-07): a native time
    // input follows the BROWSER's locale, so on a 12-hour browser it grows an AM/PM segment,
    // 21:30 cannot be typed, and an empty AM/PM makes the input report NO value — a filled-looking
    // box with a sleeping Save button and nothing on screen explaining it.
    await mount()
    expect(clock().type).toBe('text')
    expect(clock().value).toBe('')
    expect(clock().placeholder).toBe('08:00')
    // The note beside it names the default in the same shape the box takes, and says which clock.
    const row = clock().closest('li') as HTMLElement
    expect(within(row).getByText(/defaultNoteClock\|08:00/)).toBeTruthy()
  })

  it('takes a full 24-hour time — the one the picker refused', async () => {
    mockApi.saveOrganisationConfiguration.mockResolvedValue(config())
    await mount()
    const end = screen.getByTestId('config-interview_window_end_min') as HTMLInputElement
    expect(end.placeholder).toBe('21:30')
    fireEvent.change(end, { target: { value: '21:30' } })
    expect(save().disabled).toBe(false)
    fireEvent.click(save())
    await waitFor(() => expect(outcome()).toBe('admin.orgSettings.config.saved'))
    expect(mockApi.saveOrganisationConfiguration).toHaveBeenCalledWith(
      { interview_window_end_min: 1290 }, undefined, { token: 'tok' })
  })

  it('says what a valid answer looks like when the typing is not a time', async () => {
    await mount()
    for (const bad of ['2130', '9.30pm', '25:00', 'abc']) {
      fireEvent.change(clock(), { target: { value: bad } })
      expect(save().disabled).toBe(true)
      expect(screen.getByTestId('config-interview_window_start_min-invalid')).toBeTruthy()
    }
    expect(outcome()).toBe('admin.orgSettings.config.invalid')
  })

  it('renders a stored value as HH:MM and sends back minutes past midnight', async () => {
    mockApi.getOrganisationConfiguration.mockResolvedValue(
      configWith('interview_window_start_min', { value: 630 }))
    mockApi.saveOrganisationConfiguration.mockResolvedValue(config())
    await mount()
    expect(clock().value).toBe('10:30')
    fireEvent.change(clock(), { target: { value: '09:15' } })
    fireEvent.click(save())
    await waitFor(() => expect(outcome()).toBe('admin.orgSettings.config.saved'))
    expect(mockApi.saveOrganisationConfiguration).toHaveBeenCalledWith(
      { interview_window_start_min: 555 }, undefined, { token: 'tok' })
  })

  it('converts both ways, and refuses what is not a time', () => {
    // The pure pair, tested directly: a `type="time"` box will not let jsdom (or a person)
    // enter "half nine", but a pasted or autofilled value can still arrive as anything.
    expect(minutesToHhmm(0)).toBe('00:00')
    expect(minutesToHhmm(1290)).toBe('21:30')
    expect(hhmmToMinutes('21:30')).toBe(1290)
    expect(hhmmToMinutes('9:05')).toBe(545)
    for (const bad of ['', 'abc', '25:00', '10:75', '10.30', '1030']) {
      expect(hhmmToMinutes(bad)).toBeNull()
    }
  })

  it('names the opening time when the server refuses an inverted window', async () => {
    const err = Object.assign(new Error('bad'), {
      body: { code: 'window_inverted', key: 'interview_window_end_min' },
    })
    mockApi.saveOrganisationConfiguration.mockRejectedValue(err)
    await mount()
    fireEvent.change(clock(), { target: { value: '09:15' } })
    fireEvent.click(save())
    await waitFor(() => expect(outcome()).toContain('admin.orgSettings.config.refusedWindow'))
  })
})

describe('a row whose vocabulary is a list is a menu, not a box', () => {
  const step = () => screen.getByTestId('config-interview_slot_step_min') as HTMLSelectElement

  it('offers exactly the allowed values plus the follow-the-default choice', async () => {
    await mount()
    expect(step().tagName).toBe('SELECT')
    expect(Array.from(step().options).map((o) => o.value)).toEqual(
      ['', '5', '10', '15', '20', '30', '60'])
    expect(step().value).toBe('')
  })

  it('sends the chosen value', async () => {
    mockApi.saveOrganisationConfiguration.mockResolvedValue(config())
    await mount()
    fireEvent.change(step(), { target: { value: '15' } })
    fireEvent.click(save())
    await waitFor(() => expect(outcome()).toBe('admin.orgSettings.config.saved'))
    expect(mockApi.saveOrganisationConfiguration).toHaveBeenCalledWith(
      { interview_slot_step_min: 15 }, undefined, { token: 'tok' })
  })
})

describe('a super with several tenants', () => {
  it('is asked to choose, and choosing re-loads for that organisation', async () => {
    const err = Object.assign(new Error('choose'), {
      body: { code: 'organisation_required', organisations: ['alpha', 'beta'] },
    })
    mockApi.getOrganisationConfiguration
      .mockRejectedValueOnce(err)
      .mockResolvedValueOnce(config())
    render(<OrganisationConfigurationTab />)
    await waitFor(() => expect(screen.getByText('beta')).toBeTruthy())
    fireEvent.click(screen.getByText('beta'))
    await waitFor(() => expect(screen.getAllByTestId('config-rows').length).toBeGreaterThan(0))
    expect(mockApi.getOrganisationConfiguration).toHaveBeenLastCalledWith('beta', { token: 'tok' })
  })
})

describe('every rendered key has words behind it, in all three languages', () => {
  // The component derives its strings from the registry payload, so a new registry key with no
  // i18n leaf renders a raw dotted string at the moment somebody is configuring money-adjacent
  // behaviour. This walks what THIS build renders; the server test pins the registry itself.
  type Leaf = Record<string, unknown>
  const dig = (obj: Leaf, path: string[]): unknown =>
    path.reduce<unknown>((o, part) => (o as Leaf | undefined)?.[part as keyof Leaf], obj)

  it.each([['en', en], ['ms', ms], ['ta', ta]] as const)('%s', (_lang, messages) => {
    const cfg = config()
    for (const s of cfg.settings) {
      for (const leaf of ['label', 'desc']) {
        const value = dig(messages as unknown as Leaf,
          ['admin', 'orgSettings', 'config', 'setting', s.key, leaf])
        expect(typeof value).toBe('string')
        expect((value as string).length).toBeGreaterThan(0)
      }
      const unit = dig(messages as unknown as Leaf,
        ['admin', 'orgSettings', 'config', 'unit', s.unit])
      expect(typeof unit).toBe('string')
      const group = dig(messages as unknown as Leaf,
        ['admin', 'orgSettings', 'config', 'group', s.group])
      expect(typeof group).toBe('string')
    }
  })
})
