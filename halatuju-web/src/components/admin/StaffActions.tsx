'use client'

import { useCallback, useEffect, useId, useRef, useState, type PointerEvent } from 'react'

import { useT } from '@/lib/i18n'
import { workSummary } from '@/lib/staffRole'

type Bubble = typeof import(/* webpackChunkName: 'ad' */ '../InfoTipBubble').default

/**
 * Sprint T2 (owner, 2026-11-08): **Revoke / Restore, then Delete**, the same pair on every Team table
 * (Admins, Reviewers, Mentors) and on every person's page. "I want the team member tables and
 * profiles to be similar. Each must have Revoke and Delete. The delete however will be greyed out if
 * there is work on record."
 *
 * ⚠ THE SERVER DECIDES DELETE. `deletable`, `delete_never` and `work` come from one rule
 * (`staff_delete_rules.delete_fields`; D6: reviewers, QC and mentors too, under the one no-work test).
 * This only draws the answer:
 *   - `deletable`           → Delete, live;
 *   - `deleteNever`         → no Delete at all (T2 review N2): nobody can delete this row here — a
 *                             super, a partner or source login, a row this viewer may not touch, the
 *                             sole organisation admin — so a greyed "work on record" would mislead;
 *   - work on record        → Delete, GREYED, and the reason on hover, on tap and on keyboard focus;
 *   - none of these         → no Delete (an older payload without the flag);
 *   - an organisation admin → Delete only for a SUPER viewer (owner: "For org admins, the delete
 *                             button should be visible only to super admin"). The server refuses an
 *                             org_admin caller anyway (404); this keeps the dead button off.
 *
 * ⚠ THE GREYED DELETE IS `aria-disabled`, NOT `disabled`. A disabled button takes no focus and, in
 * most browsers, no pointer events — so its reason could never be read by hover, tap or keyboard.
 * It does nothing when pressed except show why. The reason is also its `aria-describedby`, so a
 * screen reader hears it with the button, before any bubble has loaded.
 *
 * ⚠ THE BUBBLE IS `InfoTip`'s (`InfoTipBubble`), fetched the first time it opens — the same look, the
 * same on-screen clamp, the same close on an outside tap or Escape. It is fetched into the ADMIN chunk
 * `ad`, NOT the students' `mi`: an admin importer of `mi` re-split the shared chunks under
 * /scholarship/apply (+0.18 kB first load, over its budget, 2026-11-10). No new chunk either way.
 *
 * Resend and Remove-from-table are NOT here: each caller keeps them where they were, either side.
 *
 * Sprint M1b (owner O3): the pair lives on the STAFF list only (and a super's platform screens' Revoke);
 * the group tables keep Add and Remove. `toggleBlocked` greys Suspend with its reason (O18: they still
 * mentor scholars), `deleteBlocked` greys Delete with the Staff list's own reason (O7: work unfinished).
 * `Greyed` is exported for the group tables' blocked Remove (O17: the reason in the tip, never inline).
 */
export interface StaffActionsProps {
  /** Is the person active? Decides Revoke (true) or Restore (false). */
  active: boolean
  /** Revoke / Restore. Absent = not offered on this row. */
  onToggle?: () => void
  /** Delete. Absent = this viewer is offered no delete here at all. */
  onDelete?: () => void
  deletable?: boolean
  /** The server's `delete_never`: nobody may ever delete this row here, so no Delete is drawn. */
  deleteNever?: boolean
  work?: Record<string, number>
  /** The row is an organisation admin: Delete is drawn only for a super viewer. */
  orgAdmin?: boolean
  viewerSuper?: boolean
  busy?: boolean
  /** Label keys, when a table words Revoke / Restore its own way. */
  revokeKey?: string
  restoreKey?: string
  /** `data-testid` of the Revoke / Restore button (the Mentors table's tests name theirs). */
  toggleTestId?: string
  /** Text size: `xs` on the dense tables, `sm` on the Mentors table and the person pages. */
  size?: 'xs' | 'sm'
  /** M1b (O18): Revoke / Suspend is refused — drawn greyed, this reason in its tip. */
  toggleBlocked?: string | null
  /** M1b (O7): Delete is refused for this reason — drawn greyed with it (instead of `work`'s summary). */
  deleteBlocked?: string | null
  /** M1b: the Delete label key (the Staff list says "Delete" too; kept for a table's own words). */
  deleteKey?: string
}

export default function StaffActions({
  active, onToggle, onDelete, deletable = false, deleteNever = false, work, orgAdmin = false, viewerSuper = false,
  busy = false, revokeKey = 'admin.revoke', restoreKey = 'admin.restore', toggleTestId, size = 'xs',
  toggleBlocked = null, deleteBlocked = null, deleteKey = 'admin.delete',
}: StaffActionsProps) {
  const { t } = useT()
  const text = size === 'xs' ? 'text-xs' : 'text-sm'
  const hasWork = (!!work && Object.keys(work).length > 0) || !!deleteBlocked
  const showDelete = !!onDelete && !deleteNever && (!orgAdmin || viewerSuper) && (deletable || hasWork)
  const why = deleteBlocked || t('admin.deleteHasWork', { work: workSummary(work) })
  return (
    <>
      {onToggle && toggleBlocked && (
        <Greyed label={t(active ? revokeKey : restoreKey)} reason={toggleBlocked} text={text}
          testId={toggleTestId ? `${toggleTestId}-greyed` : 'staff-toggle-greyed'} />
      )}
      {onToggle && !toggleBlocked && (
        <button type="button" disabled={busy} onClick={onToggle} data-testid={toggleTestId}
          className={`${text} ${TAP} font-medium disabled:opacity-50 ${
            active ? 'text-critical-600 hover:text-critical-800' : 'text-primary-600 hover:text-primary-800'}`}>
          {t(active ? revokeKey : restoreKey)}
        </button>
      )}
      {showDelete && (deletable
        ? (
          <button type="button" disabled={busy} onClick={onDelete} data-testid="staff-delete"
            className={`${text} ${TAP} font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50`}>
            {t(deleteKey)}
          </button>
        )
        : <Greyed label={t(deleteKey)} reason={why} text={text} testId="staff-delete-greyed" />)}
    </>
  )
}

/** Phone tap target (44px): the max-md pattern the person pages use on their own buttons. */
const TAP = 'max-md:inline-flex max-md:min-h-11 max-md:items-center'

/** A refused action, greyed, with its reason on hover (a mouse), on tap or click (pinned), and on focus.
 *  Delete here; Suspend (O18) and the group tables' blocked Remove (M1b, O17) too. */
export function Greyed({ label, reason, text = 'text-xs', testId }: {
  label: string
  reason: string
  text?: string
  testId: string
}) {
  const id = useId()
  const root = useRef<HTMLSpanElement>(null)
  const [pinned, setPinned] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [Bubble, setBubble] = useState<Bubble | null>(null)
  const open = pinned || hovered || focused

  useEffect(() => {
    if (!open || Bubble) return
    let live = true
    import(/* webpackChunkName: 'ad' */ '../InfoTipBubble')
      .then((m) => { if (live) setBubble(() => m.default) }).catch(() => {})
    return () => { live = false }
  }, [open, Bubble])

  const close = useCallback(() => { setPinned(false); setFocused(false) }, [])
  const onMouse = (on: boolean) => (e: PointerEvent) => { if (e.pointerType === 'mouse') setHovered(on) }

  return (
    <span ref={root} className="relative inline-flex" data-testid={testId}
      onPointerEnter={onMouse(true)} onPointerLeave={onMouse(false)}>
      <button type="button" aria-disabled="true" aria-describedby={id} aria-expanded={open}
        onClick={() => setPinned((v) => !v)}
        onFocus={() => setFocused(true)}
        // InfoTip's rule: a tap pins it, and only focus moving to ANOTHER control unpins it — Chrome
        // blurs a tapped button to <body> when the bubble's own text is tapped.
        onBlur={(e) => {
          setFocused(false)
          const to = e.relatedTarget as Node | null
          if (to && !root.current?.contains(to)) setPinned(false)
        }}
        className={`${text} ${TAP} cursor-not-allowed font-medium text-ground-400`}>
        {label}
      </button>
      <span id={id} className="sr-only">{reason}</span>
      {open && Bubble && <Bubble text={reason} root={root} onClose={close} />}
    </span>
  )
}
