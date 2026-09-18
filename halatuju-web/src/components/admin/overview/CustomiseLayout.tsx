'use client'
/**
 * "Customise" — which Overview widgets this ORGANISATION shows, and (Sprint B) in what order.
 *
 * ⚠⚠ **THE EDITOR REPLACES THE WIDGETS; IT DOES NOT SIT BESIDE THEM.** A switched-off widget has
 * no data in the payload to draw — the server never sends figures for a key it narrowed away — so
 * a customise mode that kept the live panels on screen would have to draw empty placeholders
 * beside real ones, and that reads as broken rather than as an editor.
 *
 * ⚠⚠ **SAVE PUTS THE FULL ORDERED LIST, NEVER A DIFF.** The server validates `sections` as a
 * permutation of the five customisable widgets; a diff carries no order, and the order is half of
 * what this screen exists to record. (Configuration sends only what changed, deliberately, for the
 * opposite reason: its rows have no order and the audit line should name real changes.)
 *
 * ⚠ THE LIST IS THE SERVER'S, NOT OURS. `initial` comes from the Overview payload's `layout`, so
 * an organisation whose row does not exist yet is already holding the platform default by the time
 * it reaches this component — there is no "not customised yet" state to invent here.
 *
 * Save follows the platform's nothing-to-save standard (`SaveBar`): asleep until the list actually
 * differs from what arrived, with the reason one hover away. Every outcome has a line on screen —
 * saved, refused with the offending panel named, or a generic failure. There is no silent branch.
 */
import { useState } from 'react'

import SaveBar, { SAVE_BAR_PRIMARY, SAVE_BAR_SECONDARY } from '@/components/admin/SaveBar'
import { Toggle } from '@/components/sources/shared'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { saveOverviewLayout } from '@/lib/admin-api'
import { SECTION_KEYS, isDirty, setOn, type LayoutRow } from '@/lib/overviewLayout'

/** ⚠ The i18n guard resolves `${K}.` templates by this LITERAL name. */
const K = 'admin.programmeOverview'

type Outcome =
  | { kind: 'idle' }
  | { kind: 'saved' }
  | { kind: 'error' }
  | { kind: 'refused'; code: string; key: string }

export default function CustomiseLayout({ initial, org, onSaved, onCancel }: {
  initial: LayoutRow[]
  /** A super's `?org=` override; an org_admin sends nothing and edits their own organisation. */
  org?: string
  onSaved: () => void
  onCancel: () => void
}) {
  const { token } = useAdminAuth()
  const { t } = useT()

  const [list, setList] = useState<LayoutRow[]>(initial)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })

  const dirty = isDirty(initial, list)
  const canSave = dirty && !busy

  /** ⚠ AN ALLOWLIST, so a refusal naming a key we do not know can never render as a raw dotted
   *  string in front of an admin — it falls back to the key itself, which is at least true. */
  const sectionName = (key: string) =>
    (SECTION_KEYS.indexOf(key as (typeof SECTION_KEYS)[number]) === -1
      ? key
      : t(`${K}.sections.${key}`))

  const flip = (key: string, on: boolean) => {
    setOutcome({ kind: 'idle' })
    setList((current) => setOn(current, key, on))
  }

  const onSave = async () => {
    if (!token || !canSave) return
    setBusy(true)
    try {
      // The WHOLE list, in the order the cards are in — see the module note.
      await saveOverviewLayout(list, org, { token })
      setOutcome({ kind: 'saved' })
      onSaved()
    } catch (e) {
      const err = e as Error & { body?: { code?: string; key?: string } }
      if (err.body?.code && err.body.key) {
        setOutcome({ kind: 'refused', code: err.body.code, key: err.body.key })
      } else {
        setOutcome({ kind: 'error' })
      }
    } finally {
      setBusy(false)
    }
  }

  const statusLine = () => {
    switch (outcome.kind) {
      case 'saved': return t(`${K}.customise.saved`)
      case 'error': return t(`${K}.customise.error`)
      case 'refused':
        return t(`${K}.customise.refused`, { name: sectionName(outcome.key) })
      default:
        // ⚠ NOTHING while idle (the SaveBar rule) — the greyed button already says it, and a
        // sentence repeating it is the loudest thing in the bar saying the least.
        return dirty ? t('common.unsavedChanges') : null
    }
  }

  return (
    <div className="mt-6" data-testid="customise-layout">
      <h2 className="text-sm font-semibold text-ground-900">{t(`${K}.customise.title`)}</h2>
      <p className="mt-1 text-sm text-ground-600">{t(`${K}.customise.hint`)}</p>

      <ul className="mt-3 space-y-2">
        {list.map((row) => {
          const name = sectionName(row.key)
          return (
            <li key={row.key}
              data-testid={`customise-card-${row.key}`}
              // ⚠ THE WHOLE CARD FADES WHEN THE PANEL IS OFF, not just its badge. The switch is
              // 44px of the row; what a person scans is the block, so the block has to carry the
              // answer.
              className={`flex items-center justify-between gap-3 rounded-xl border border-ground-200 bg-ground-0 px-4 py-3 ${
                row.on ? '' : 'opacity-50'}`}>
              <div className="min-w-0">
                <p className="text-sm font-medium text-ground-900">{name}</p>
                <p className="mt-0.5 text-[11px] text-ground-500">
                  {row.on ? t(`${K}.customise.visible`) : t(`${K}.customise.hidden`)}
                </p>
              </div>
              <Toggle on={row.on} disabled={busy} label={name}
                onClick={() => flip(row.key, !row.on)} />
            </li>
          )
        })}
      </ul>

      <SaveBar status={statusLine()} testId="customise-outcome">
        <button type="button" data-testid="discard-layout" onClick={onCancel}
          className={SAVE_BAR_SECONDARY}>
          {t(`${K}.customise.discard`)}
        </button>
        <button type="button" data-testid="save-layout" disabled={!canSave}
          onClick={() => void onSave()}
          title={!dirty ? t('common.nothingToSave') : undefined}
          className={SAVE_BAR_PRIMARY}>
          {t(`${K}.customise.save`)}
        </button>
      </SaveBar>
    </div>
  )
}
