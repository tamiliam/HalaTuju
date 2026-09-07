/**
 * @jest-environment jsdom
 *
 * Which gift am I looking at — and the stale-list defect the owner hit on 2026-09-07.
 *
 * ⚠⚠ THE SYMPTOM WAS A DEAD SCREEN. They created a gift, were taken to Configuration, and it asked
 * WHICH gift — then every click on the answer did nothing, however many times they pressed.
 *
 * ⚠ THE GUARD WAS NOT THE BUG. `chosen` deliberately resolves to `''` for a code that is not in
 * the list, because accepting an unknown code is the 2026-09-03 defect (it showed the owner a
 * DIFFERENT programme's settings than the one they opened) and falling back to "the only one" is
 * the same defect wearing a hat. The list was STALE: the shell fetches the scopes once per console
 * session, so a gift created during that session was not in it.
 *
 * So these tests pin both halves at once — the refusal stays, and the list can be refreshed.
 */
import { act, render, screen } from '@testing-library/react'
import { ProgrammeScopeProvider, useProgrammeScope } from '@/lib/programmeScope'

const TWO = [{ code: 'bp', name: 'BrightPath' }, { code: 'test', name: 'Test' }]

function Probe() {
  const { chosen, ambiguous, select, reload } = useProgrammeScope()
  return (
    <div>
      <span data-testid="chosen">{chosen || '(none)'}</span>
      <span data-testid="ambiguous">{String(ambiguous)}</span>
      <button data-testid="pick-new" onClick={() => select('test2')}>pick new</button>
      <button data-testid="pick-known" onClick={() => select('test')}>pick known</button>
      <button data-testid="reload" onClick={() => { void reload() }}>reload</button>
    </div>
  )
}

const chosen = () => screen.getByTestId('chosen').textContent

describe('a code the list does not know', () => {
  it('⚠ resolves to NOTHING — never to whichever gift happens to be there', () => {
    // This is the guard doing its job. Do not "fix" the dead screen by loosening it.
    render(<ProgrammeScopeProvider choices={TWO}><Probe /></ProgrammeScopeProvider>)
    act(() => { screen.getByTestId('pick-new').click() })
    expect(chosen()).toBe('(none)')
  })

  it('and a code the list DOES know resolves, so the refusal is about staleness only', () => {
    render(<ProgrammeScopeProvider choices={TWO}><Probe /></ProgrammeScopeProvider>)
    act(() => { screen.getByTestId('pick-known').click() })
    expect(chosen()).toBe('test')
  })

  it('⚠ still resolves to NOTHING when there is exactly one gift, not to that one', () => {
    // The 2026-09-03 substitution, in its most tempting form: one gift, an unknown pick, and an
    // obvious "helpful" fallback that is how the owner was shown somebody else's settings.
    render(
      <ProgrammeScopeProvider choices={[{ code: 'bp', name: 'BrightPath' }]}>
        <Probe />
      </ProgrammeScopeProvider>,
    )
    expect(chosen()).toBe('bp')                                   // nothing picked → the only one
    act(() => { screen.getByTestId('pick-new').click() })
    expect(chosen()).toBe('(none)')                               // picked-but-unknown → ask
  })
})

describe('the list can be refreshed, which is the actual fix', () => {
  it('asks the shell to re-fetch, so a gift created just now becomes selectable', async () => {
    const onReload = jest.fn().mockResolvedValue(undefined)
    const { rerender } = render(
      <ProgrammeScopeProvider choices={TWO} onReload={onReload}><Probe /></ProgrammeScopeProvider>,
    )

    // The dead screen: pick a gift the stale list has never heard of.
    act(() => { screen.getByTestId('pick-new').click() })
    expect(chosen()).toBe('(none)')

    act(() => { screen.getByTestId('reload').click() })
    expect(onReload).toHaveBeenCalledTimes(1)

    // The shell re-fetches and hands down a list that now contains it — and the SAME pick, which
    // was never lost, resolves. That is why `select` is not re-fired after a reload.
    rerender(
      <ProgrammeScopeProvider choices={[...TWO, { code: 'test2', name: 'Test 2' }]}
        onReload={onReload}><Probe /></ProgrammeScopeProvider>,
    )
    expect(chosen()).toBe('test2')
  })

  it('a provider with no `onReload` still mounts and reload is a harmless no-op', async () => {
    // A test harness or the sandbox mounts without a shell; it must not throw.
    render(<ProgrammeScopeProvider choices={TWO}><Probe /></ProgrammeScopeProvider>)
    act(() => { screen.getByTestId('reload').click() })
    expect(chosen()).toBe('(none)')
  })
})
