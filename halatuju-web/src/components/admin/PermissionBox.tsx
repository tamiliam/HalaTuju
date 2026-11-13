'use client'

import { useId, useState, type ReactNode } from 'react'
import Toggle from '@/components/Toggle'
import { useT } from '@/lib/i18n'
import { controlKeys, type PermBox, type PermRow, type PermSub } from '@/lib/permissionLayout'

/**
 * Sprint M2d: one BOX of the Permissions tab (D5) and the rows the layout puts in it (D2, D4) — split
 * out of `PermissionEditor` (file cap), travelling in the same lazy chunk (`'ad'`): only the editor
 * imports it.
 *
 * It draws; it decides nothing. Every key's state (`KeyState`) is the editor's, worked out from the
 * server's answer; a click goes back to the editor (`onSwitch`, `onTri`), which keeps the working set.
 */

/** One key as the card draws it. `lock` = the server will not let anyone here store it yet (`lead_only`):
 *  a padlock, never a reason. `disabled` adds the card's own reasons (fixed, busy, Quality check). */
export interface KeyState {
  shown: boolean
  on: boolean
  lock: boolean
  disabled: boolean
  changed: boolean
}

export type KeyStates = (key: string) => KeyState

/** The padlock (D4). Decorative: the control is disabled, and the one legend line says why. */
export function Padlock({ className = 'h-3.5 w-3.5' }: { className?: string }) {
  return (
    <svg className={`shrink-0 ${className}`} viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.6" aria-hidden="true" data-testid="perm-padlock">
      <rect x="3" y="7" width="10" height="7" rx="1.5" />
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" />
    </svg>
  )
}

export function ChangedPill() {
  const { t } = useT()
  return (
    <span className="rounded-full bg-primary-50 px-2 py-px text-[11px] font-semibold text-primary-700">
      {t('admin.permEditor.changed')}
    </span>
  )
}

/** D5: a collapsible box — a button with `aria-expanded` and a chevron, open on load, with "N of M on".
 *  Collapsing only hides the rows; the working set lives in the editor and is kept. */
export function BoxShell({ title, on, of, testId, children }: {
  title: string
  on: number
  of: number
  testId: string
  children: ReactNode
}) {
  const { t } = useT()
  const [open, setOpen] = useState(true)
  const rowsId = useId()
  return (
    <section className="overflow-hidden rounded-lg border border-ground-200 bg-ground-0" data-testid={testId}>
      <button type="button" aria-expanded={open} aria-controls={rowsId} onClick={() => setOpen(!open)}
        className="flex min-h-11 w-full items-center gap-2.5 px-4 py-3 text-left hover:bg-ground-50">
        <svg className={`h-4 w-4 shrink-0 text-ground-500 transition-transform motion-reduce:transition-none ${
          open ? '' : '-rotate-90'}`} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"
          aria-hidden="true">
          <path d="M5 7.5l5 5 5-5" />
        </svg>
        <h3 className="flex-1 text-[15px] font-semibold text-ground-900">{title}</h3>
        <span className="whitespace-nowrap rounded-full bg-primary-50 px-2 py-0.5 text-xs font-semibold tabular-nums text-primary-700"
          data-testid={`${testId}-count`}>
          {t('admin.permEditor.boxCount', { n: String(on), m: String(of) })}
        </span>
      </button>
      <div id={rowsId} hidden={!open} className="divide-y divide-ground-100 border-t border-ground-200">
        {children}
      </div>
    </section>
  )
}

const SEGMENTS = 'flex w-full gap-1 rounded-lg bg-ground-100 p-1 sm:w-auto'
const segment = (on: boolean) => `inline-flex min-h-11 min-w-0 flex-auto items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-2.5 text-center text-sm font-medium leading-tight disabled:cursor-not-allowed ${
  on ? 'bg-ground-0 text-ground-900 shadow-sm' : 'text-ground-600 hover:text-ground-900 disabled:text-ground-400 disabled:hover:text-ground-400'}`

/** D2: "No access / View / View and change" over a page's `.view` and `.edit` — the 44 px segmented
 *  pattern of `DisplaySegments` (copied, not imported: that module carries the theme and the toast). In a
 *  partly locked page only the locked option is disabled (Invitations: "View and change"). */
function Tri({ label, view, edit, onPick }: {
  label: string
  view: KeyState
  edit: KeyState
  onPick: (level: 0 | 1 | 2) => void
}) {
  const { t } = useT()
  const value = edit.on ? 2 : view.on ? 1 : 0
  const options = [
    { level: 0 as const, text: t('admin.permEditor.level.none'), key: view },
    { level: 1 as const, text: t('admin.permEditor.level.view'), key: view },
    { level: 2 as const, text: t('admin.permEditor.level.edit'), key: edit },
  ]
  return (
    <div role="radiogroup" aria-label={label} className={SEGMENTS}>
      {options.map((o) => (
        <button key={o.level} type="button" role="radio" aria-checked={value === o.level}
          disabled={o.key.disabled} onClick={() => { if (value !== o.level) onPick(o.level) }}
          className={segment(value === o.level)}>
          {o.level > 0 && o.key.lock && <Padlock />}
          {o.text}
        </button>
      ))}
    </div>
  )
}

/** One switch, with its padlock when locked (D4). */
function Switch({ label, k, onSwitch }: { label: string; k: KeyState; onSwitch: (on: boolean) => void }) {
  const toggle = <Toggle on={k.on} disabled={k.disabled} label={label} onChange={onSwitch} />
  if (!k.lock) return toggle
  return <span className="inline-flex items-center gap-1 text-ground-400"><Padlock />{toggle}</span>
}

function Words({ name, desc, changed, locked }: { name: string; desc: string; changed: boolean; locked: boolean }) {
  return (
    <div className="min-w-0 flex-[1_1_16rem]">
      <div className={`flex flex-wrap items-center gap-2 text-sm font-semibold ${locked ? 'text-ground-500' : 'text-ground-900'}`}>
        {name}
        {changed && <ChangedPill />}
      </div>
      <div className="text-[13px] text-ground-500">{desc}</div>
    </div>
  )
}

/** A box's count (D5): M = its enabled controls (a three-way once, sub-items each), N = those on. */
export function countBox(box: PermBox, ks: KeyStates): { on: number; of: number } {
  const counted = box.rows.flatMap((r) => [
    ...(r.control.kind === 'info' ? [] : [ks(controlKeys(r.control)[0])]),
    ...(r.subs ?? []).map((s) => ks(s.key)),
  ]).filter((k) => k.shown && !k.lock)
  return { on: counted.filter((k) => k.on).length, of: counted.length }
}

/** A row is drawn when its control or one of its sub-items is served; an Overview row always. */
const rowShown = (r: PermRow, ks: KeyStates) => (r.control.kind === 'info' && !r.subs)
  || controlKeys(r.control).some((k) => ks(k).shown) || (r.subs ?? []).some((s) => ks(s.key).shown)

export function LayoutBox({ box, ks, onSwitch, onTri }: {
  box: PermBox
  ks: KeyStates
  onSwitch: (key: string, on: boolean) => void
  onTri: (view: string, edit: string, level: 0 | 1 | 2) => void
}) {
  const { t } = useT()
  const rows = box.rows.filter((r) => rowShown(r, ks))
  const { on, of } = countBox(box, ks)
  const sub = (s: PermSub) => {
    const k = ks(s.key)
    if (!k.shown) return null
    return (
      <div key={s.key} data-key={s.key} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-1.5">
        <Words name={t(s.name)} desc={t(s.desc)} changed={k.changed} locked={k.lock} />
        <Switch label={t(s.name)} k={k} onSwitch={(v) => onSwitch(s.key, v)} />
      </div>
    )
  }
  const control = (r: PermRow) => {
    const c = r.control
    if (c.kind === 'tri' && ks(c.view).shown) {
      return <Tri label={t(r.name)} view={ks(c.view)} edit={ks(c.edit)} onPick={(level) => onTri(c.view, c.edit, level)} />
    }
    if (c.kind === 'switch' && ks(c.key).shown) {
      return <Switch label={t(r.name)} k={ks(c.key)} onSwitch={(v) => onSwitch(c.key, v)} />
    }
    return null
  }
  return (
    <BoxShell title={t(box.title)} on={on} of={of} testId={`perm-box-${box.id}`}>
      {rows.map((r) => {
        const keys = controlKeys(r.control).map(ks)
        const subs = (r.subs ?? []).filter((s) => ks(s.key).shown)
        return (
          <div key={r.id} data-row={r.id} className="grid gap-2 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <Words name={t(r.name)} desc={t(r.desc)} changed={keys.some((k) => k.changed)}
                locked={keys.length > 0 && keys.every((k) => k.lock)} />
              {control(r)}
            </div>
            {subs.length > 0 && (
              <div className="ml-3 grid border-l-2 border-ground-200 pl-3">{subs.map(sub)}</div>
            )}
          </div>
        )
      })}
    </BoxShell>
  )
}
