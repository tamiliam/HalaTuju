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
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import OrganisationConfigurationTab from './OrganisationConfigurationTab'
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

function config(over: Partial<api.OrganisationConfigSetting> = {}): api.OrganisationConfiguration {
  return {
    organisation: { code: 'alpha', name: 'Alpha Foundation' },
    settings: [{
      key: KEY, group: 'sponsor_page', unit: 'days', min: 1, max: 90,
      value: null, default: 2, ...over,
    }, ...SPRINT_B],
  }
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
    // The note interpolates {n} and {unit} — the harness renders vars after a pipe. Pinned to
    // the DAYS unit: the query-delay row also defaults to 2, in hours.
    expect(screen.getByText(
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
  it('is asleep with nothing changed', async () => {
    await mount()
    expect(save().disabled).toBe(true)
    expect(outcome()).toBe('admin.orgSettings.config.nothingToDo')
  })

  it('wakes on a real edit and sends ONLY the changed key', async () => {
    mockApi.saveOrganisationConfiguration.mockResolvedValue(config({ value: 30 }))
    await mount()
    type('30')
    expect(save().disabled).toBe(false)
    expect(outcome()).toBe('admin.orgSettings.config.unsaved')
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
