'use client'

import { useT } from '@/lib/i18n'
import { usePhoneWidth } from '@/lib/phoneWidth'
import { PHONE_PILL_LG, PHONE_PILL_XS } from '@/lib/phonePill'

export interface PanelTab<K extends string> {
  key: K
  labelKey: string
  /** Rendered greyed and unclickable. Use when the tab has no content YET — never to gate
   *  permission, which belongs in the role check that decides whether to offer the tab at all. */
  disabled?: boolean
  /**
   * How many rows are behind this tab. Drawn as a quiet pill after the label.
   *
   * ⚠ **OPTIONAL, AND `0` IS A REAL ANSWER.** Only `undefined` hides the pill — a tab that has
   * genuinely nothing behind it should say "0", because an absent number reads as "not counted
   * yet" and the two mean opposite things to somebody deciding whether to click.
   *
   * ⚠ It is the count of the WHOLE list, not of the current page or the current filter. A number
   * that moved as you typed in a search box would stop being the thing you came to the tab to
   * read. (Owner, 2026-09-11.)
   */
  count?: number
}

/**
 * The tab bar every organisation surface wears: subject · Emails · Terms.
 *
 * ⚠ **THIS EXISTS BECAUSE FOUR PAGES HAD HAND-ROLLED THE SAME MARKUP** — Reviewers, Sponsors,
 * Sources and Invitations each carried their own copy of the identical `role="tablist"` block, so a
 * change to one silently left the others behind. Owner, 2026-08-04: they should all look the same.
 *
 * ⚠ **A TAB WITH NOTHING BEHIND IT IS SHOWN DISABLED, NOT HIDDEN** (owner's instruction). Hiding it
 * would make the surfaces look structurally different from each other when the only difference is
 * that one is not built yet — and it would give somebody no reason to expect it ever to appear.
 */
/** More tabs than this become one chooser on a phone (owner, Mobile M7a). */
export const PHONE_CHIPS_MAX = 4

export default function PanelTabs<K extends string>({ tabs, active, onSelect, ariaLabelKey }: {
  tabs: readonly PanelTab<K>[]
  active: K
  onSelect: (key: K) => void
  ariaLabelKey: string
}) {
  const { t } = useT()
  // Mobile M7a (owner, 2026-11-03): up to PHONE_CHIPS_MAX tabs stay chips on a phone (44 px, wrapping); MORE
  // become ONE chooser above the content below md (the Guide's pattern) — nine tabs in Tamil were four lines of
  // chips. From md the bar is the one it always was. The chooser calls the same onSelect with the same keys, and
  // it REPLACES the bar (below md by width, after mount) instead of sitting beside a hidden copy: one control.
  const phone = usePhoneWidth()
  const chooser = phone && tabs.length > PHONE_CHIPS_MAX
  return (<>
    {chooser && (
      <label className="mb-4 block">
        <span className="sr-only">{t(ariaLabelKey)}</span>
        <select value={active} onChange={(e) => onSelect(e.target.value as K)} data-panel-chooser
          className="min-h-11 w-full rounded-lg border border-ground-300 bg-ground-0 px-3 text-ground-800">
          {tabs.map((tab) => (
            <option key={tab.key} value={tab.key} disabled={tab.disabled}>
              {t(tab.labelKey)}{tab.count !== undefined ? ` (${tab.count})` : ''}{tab.disabled ? ` · ${t('admin.soon')}` : ''}
            </option>
          ))}
        </select>
      </label>
    )}
    {/* `flex-wrap`: four counted tabs in Tamil do not fit one row at 360 px (Requests list R1), and
        a tab bar that runs off the edge is a sideways scroll. A bar that fits is unchanged. */}
    {!chooser && <div role="tablist" aria-label={t(ariaLabelKey)} className="mb-6 flex flex-wrap items-center gap-2">
      {tabs.map((tab) => {
        const on = tab.key === active
        return (
          <button key={tab.key} type="button" role="tab" aria-selected={on}
            aria-disabled={tab.disabled || undefined}
            disabled={tab.disabled}
            onClick={() => !tab.disabled && onSelect(tab.key)}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors max-md:inline-flex max-md:min-h-11 max-md:items-center ${PHONE_PILL_LG} ${
              tab.disabled
                ? 'cursor-not-allowed border-ground-200 bg-ground-50 text-ground-400'
                : on ? 'border-info-600 bg-brand-fill text-brand-fill-ink'
                     : 'border-ground-200 bg-ground-0 text-ground-600 hover:bg-ground-50'}`}>
            {t(tab.labelKey)}
            {tab.count !== undefined && (
              <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] tabular-nums ${PHONE_PILL_XS} ${
                on ? 'bg-ground-0/25 text-brand-fill-ink' : 'bg-ground-100 text-ground-500'}`}>
                {tab.count}
              </span>
            )}
            {tab.disabled && (
              <span className={`ml-1.5 rounded-full bg-ground-200 px-1.5 py-0.5 text-[10px] text-ground-500 ${PHONE_PILL_XS}`}>
                {t('admin.soon')}
              </span>
            )}
          </button>
        )
      })}
    </div>}
  </>)
}
