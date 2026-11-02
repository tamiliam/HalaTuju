'use client'

/**
 * Theme and language as 44 px segmented controls — moved out of `StudentMenus.tsx` in Mobile M5 so the
 * sponsor's My Account can draw the SAME controls on a phone (the portal's phone header has no room for
 * the two selects). Nothing about them changed in the move.
 *
 * ⚠ Still NOT variants of `ThemeSelector` / `LanguageSelector`: those ride eagerly on the console and the
 * sponsor portal's desktop row, and a variant there added bytes to ~75 routes (the route median among
 * them) for a control only menus show (Mobile M2). The student header reaches this module through its
 * lazy `StudentMenus` chunk; the sponsor reaches it from the My Account page only.
 */
import { useEffect, useRef, useState } from 'react'
import { useToast } from '@/components/ToastContext'
import { useT, LOCALE_LABELS, type Locale } from '@/lib/i18n'
import {
  DEFAULT_MODE, THEME_MODES, applyTheme, devicePrefersDark, readStoredMode, resolveTheme,
  writeStoredMode, type ThemeMode,
} from '@/lib/theme'

const SEGMENTS = 'flex w-full gap-1 rounded-lg bg-ground-100 p-1'
const segment = (on: boolean) => `inline-flex min-h-11 flex-auto items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 text-sm font-medium ${
  on ? 'bg-ground-0 text-ground-900 shadow-sm' : 'text-ground-600 hover:text-ground-900'}`

/**
 * Light / Dark / Auto as three 44 px buttons — `ThemeSelector`'s job (read after mount, write the
 * device-local choice, apply it), drawn for a menu of big rows.
 */
export function ThemeSegments() {
  const { t } = useT()
  const [mode, setMode] = useState<ThemeMode>(DEFAULT_MODE)
  useEffect(() => { setMode(readStoredMode()) }, [])
  const pick = (next: ThemeMode) => {
    setMode(next)
    writeStoredMode(next)
    applyTheme(resolveTheme(next, devicePrefersDark()))
  }
  return (
    <div role="radiogroup" aria-label={t('theme.label')} className={SEGMENTS}>
      {THEME_MODES.map((m) => (
        <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => pick(m)} className={segment(mode === m)}>
          {t(`theme.${m}`)}
        </button>
      ))}
    </div>
  )
}

/**
 * English / Bahasa Melayu / தமிழ் as three 44 px buttons, sized to their words (`flex-auto`, so
 * "Bahasa Melayu" gets its room and the row still fits a 320 px sheet body). ⚠ The SAME rule as
 * `LanguageSelector` (read its header): the pending choice is this control's own state, shown at once
 * with a spinner while the catalogue loads; a failed load puts it back and says so in the house toast;
 * an answer for a choice already replaced is ignored.
 */
export function LanguageSegments() {
  const { locale, setLocale, t } = useT()
  const { showToast } = useToast()
  const [pending, setPending] = useState<Locale | null>(null)
  const latest = useRef<Locale | null>(null)
  const choose = (next: Locale) => {
    latest.current = next
    setPending(next)
    setLocale(next).then(
      () => { if (latest.current === next) setPending(null) },
      () => {
        if (latest.current !== next) return
        setPending(null)
        showToast(t('common.languageLoadFailed'), 'error')
      },
    )
  }
  const shown = pending ?? locale
  const busy = pending !== null && pending !== locale
  return (
    <div role="radiogroup" aria-label={t('settings.language')} aria-busy={busy} className={SEGMENTS}>
      {(Object.keys(LOCALE_LABELS) as Locale[]).map((key) => (
        <button key={key} type="button" role="radio" aria-checked={shown === key}
          onClick={() => { if (key !== shown) choose(key) }} className={segment(shown === key)}>
          {LOCALE_LABELS[key]}
          {busy && shown === key && (
            <span aria-hidden className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand-shape border-t-transparent" />
          )}
        </button>
      ))}
    </div>
  )
}

/** Theme and language, as 44 px segmented controls. */
export function DisplayControls() {
  const { t } = useT()
  return (
    <div className="space-y-3">
      <div>
        <p className="px-1 pb-1.5 text-xs font-semibold uppercase tracking-wide text-ground-500">{t('theme.label')}</p>
        <ThemeSegments />
      </div>
      <div>
        <p className="px-1 pb-1.5 text-xs font-semibold uppercase tracking-wide text-ground-500">{t('settings.language')}</p>
        <LanguageSegments />
      </div>
    </div>
  )
}
