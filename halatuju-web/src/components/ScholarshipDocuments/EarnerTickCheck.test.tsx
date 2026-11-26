/**
 * @jest-environment jsdom
 *
 * Request #84 (2026-11-25): the income step asks before it saves a "working" tick the family
 * details disagree with. The disagreement is SERVED (`earner_tick_conflicts`); nothing is ever
 * unticked for the student.
 */
import { useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'

import type { EarnerTickConflicts, WorkingMemberRole } from '@/lib/api/application'
import { useEarnerTickCheck } from './EarnerTickCheck'

const t = (k: string) => k
const CONFLICTS: EarnerTickConflicts = {
  mother: { kind: 'not_working', occupation: 'unemployed' },
  guardian: { kind: 'not_listed' },
}

function Harness({ start, onSave, conflicts = CONFLICTS, route = 'salary' }: {
  start: WorkingMemberRole[]; onSave: (n: WorkingMemberRole[]) => void; conflicts?: EarnerTickConflicts | null; route?: string
}) {
  const [members, setMembers] = useState(start)
  const check = useEarnerTickCheck({ conflicts, members, t, route, saveMembers: (n) => { onSave(n); setMembers(n) } })
  return (
    <div>
      {(['father', 'mother', 'guardian'] as const).map((m) => (
        <button key={m} type="button" onClick={(e) => check.toggle(m, e.currentTarget)}>{`tick-${m}`}</button>
      ))}
      {check.node}
    </div>
  )
}

const W = 'scholarship.docs.income.wizard.earnerCheck'

describe('#84: ask before saving a disagreeing tick', () => {
  it('an agreeing tick saves at once, with no question', () => {
    const onSave = jest.fn()
    render(<Harness start={[]} onSave={onSave} />)
    fireEvent.click(screen.getByText('tick-father'))
    expect(onSave).toHaveBeenCalledWith(['father'])
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('a disagreeing tick is held and asked about; "No" saves nothing', () => {
    const onSave = jest.fn()
    render(<Harness start={['father']} onSave={onSave} />)
    fireEvent.click(screen.getByText('tick-mother'))
    expect(onSave).not.toHaveBeenCalled()
    expect(screen.getByRole('alertdialog').textContent).toContain(`${W}.askNotWorking`)
    fireEvent.click(screen.getByText(`${W}.cancel`))
    expect(onSave).not.toHaveBeenCalled()
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('"Yes" saves the tick, and a standing note stays while it disagrees', () => {
    const onSave = jest.fn()
    render(<Harness start={['father']} onSave={onSave} />)
    fireEvent.click(screen.getByText('tick-guardian'))
    expect(screen.getByRole('alertdialog').textContent).toContain(`${W}.askNotListed`)
    fireEvent.click(screen.getByText(`${W}.confirm`))
    expect(onSave).toHaveBeenCalledWith(['father', 'guardian'])
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(screen.getByTestId('earner-tick-note-guardian').textContent).toContain(`${W}.noteNotListed`)
  })

  it('a saved disagreeing tick (an open case) shows the note; unticking it saves and clears it', () => {
    const onSave = jest.fn()
    render(<Harness start={['father', 'mother']} onSave={onSave} />)
    expect(screen.getByTestId('earner-tick-note-mother').textContent).toContain(`${W}.noteNotWorking`)
    fireEvent.click(screen.getByText('tick-mother'))
    expect(onSave).toHaveBeenCalledWith(['father'])
    expect(screen.queryByTestId('earner-tick-note-mother')).toBeNull()
  })

  it('focus: into the question on "No" (never on "Yes"), described by the check line; back to the toggle on close', () => {
    render(<Harness start={[]} onSave={jest.fn()} />)
    fireEvent.click(screen.getByText('tick-mother'))
    const dialog = screen.getByRole('alertdialog')
    expect(document.activeElement).toBe(screen.getByText(`${W}.cancel`))   // review round 2: Enter twice never confirms unread
    expect(document.getElementById(dialog.getAttribute('aria-labelledby') || '')?.textContent).toContain(`${W}.askNotWorking`)
    expect(document.getElementById(dialog.getAttribute('aria-describedby') || '')?.textContent).toBe(`${W}.askCheck`)
    fireEvent.click(screen.getByText(`${W}.confirm`))
    expect(document.activeElement).toBe(screen.getByText('tick-mother'))
  })

  it('review round 2: Enter on the first focus answers "No"; Escape is "No" too; focus returns to the toggle', () => {
    const onSave = jest.fn()
    render(<Harness start={[]} onSave={onSave} />)
    fireEvent.click(screen.getByText('tick-mother'))
    fireEvent.click(document.activeElement as HTMLElement)   // what Enter does on a focused button
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(onSave).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('tick-guardian'))
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(onSave).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(screen.getByText('tick-guardian'))
  })

  it('the served answer changes while asking and the member now agrees: the question is dropped, never drawn empty', () => {
    const onSave = jest.fn()
    const { rerender } = render(<Harness start={[]} onSave={onSave} />)
    fireEvent.click(screen.getByText('tick-mother'))
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    rerender(<Harness start={[]} onSave={onSave} conflicts={{ guardian: { kind: 'not_listed' } }} />)
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(screen.queryByTestId('earner-tick-check')).toBeNull()
    expect(onSave).not.toHaveBeenCalled()
    // and it does not come back if the disagreement returns
    rerender(<Harness start={[]} onSave={onSave} conflicts={CONFLICTS} />)
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('a route change drops an open question (STR and back does not revive it)', () => {
    const onSave = jest.fn()
    const { rerender } = render(<Harness start={[]} onSave={onSave} />)
    fireEvent.click(screen.getByText('tick-guardian'))
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    rerender(<Harness start={[]} onSave={onSave} route="str" />)
    rerender(<Harness start={[]} onSave={onSave} route="salary" />)
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(onSave).not.toHaveBeenCalled()
  })

  it('no served answer (an older api) asks nothing', () => {
    const onSave = jest.fn()
    render(<Harness start={[]} onSave={onSave} conflicts={null} />)
    fireEvent.click(screen.getByText('tick-mother'))
    expect(onSave).toHaveBeenCalledWith(['mother'])
    expect(screen.queryByTestId('earner-tick-check')).toBeNull()
  })
})
