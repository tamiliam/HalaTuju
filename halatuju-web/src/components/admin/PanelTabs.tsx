'use client'

import { useT } from '@/lib/i18n'

export interface PanelTab<K extends string> {
  key: K
  labelKey: string
  /** Rendered greyed and unclickable. Use when the tab has no content YET — never to gate
   *  permission, which belongs in the role check that decides whether to offer the tab at all. */
  disabled?: boolean
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
export default function PanelTabs<K extends string>({ tabs, active, onSelect, ariaLabelKey }: {
  tabs: readonly PanelTab<K>[]
  active: K
  onSelect: (key: K) => void
  ariaLabelKey: string
}) {
  const { t } = useT()
  return (
    <div role="tablist" aria-label={t(ariaLabelKey)} className="mb-6 flex items-center gap-2">
      {tabs.map((tab) => {
        const on = tab.key === active
        return (
          <button key={tab.key} type="button" role="tab" aria-selected={on}
            aria-disabled={tab.disabled || undefined}
            disabled={tab.disabled}
            onClick={() => !tab.disabled && onSelect(tab.key)}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
              tab.disabled
                ? 'cursor-not-allowed border-ground-200 bg-ground-50 text-ground-400'
                : on ? 'border-info-600 bg-primary-600 text-white'
                     : 'border-ground-200 bg-ground-0 text-ground-600 hover:bg-ground-50'}`}>
            {t(tab.labelKey)}
            {tab.disabled && (
              <span className="ml-1.5 rounded-full bg-ground-200 px-1.5 py-0.5 text-[10px] text-ground-500">
                {t('admin.soon')}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
