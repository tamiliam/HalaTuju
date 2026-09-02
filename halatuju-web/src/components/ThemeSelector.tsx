'use client'

/**
 * Light / Dark / Auto — THE PRODUCT'S OWN SWITCH (Layer 1 F7d).
 *
 * The arc built a complete dark theme over F1–F7c and shipped every sprint of it with no way for a
 * person to reach it. This is that control, and F7d is the sprint that removes the flag behind it.
 *
 * ⚠ THE CHOICE IS DEVICE-LOCAL, NOT ACCOUNT-STORED (owner ruling, 2026-09-02). `theme.ts` used to
 * say the opposite in as many words, and F1b was scoped around it — four settings surfaces, three
 * identity models and a migration. That scoping is SUPERSEDED, not deferred. The argument that
 * settled it: LANGUAGE is a larger per-person choice and is already device-local, so making the
 * theme *more* persistent than the language would be backwards.
 *
 * ⚠ IT IS A `<select>` ON PURPOSE, AND IT MATCHES `LanguageSelector` CLASS FOR CLASS. The two sit
 * beside each other doing the same shape of job — pick one of a short list, applies at once, no
 * save button. Two differently-drawn controls in one corner reads as an accident, so the styling
 * is deliberately copied rather than re-invented. The sandbox's segmented version was chrome, and
 * it is deleted (a design review does not get a control the product does not have).
 *
 * ⚠ IT DOES NOT APPLY A THEME ON MOUNT, and that is what F7d changed. The sandbox toggle had to,
 * because the before-paint script was gated off and nothing had set `data-theme`. The script is
 * unconditional now, so the attribute is already correct before the first pixel — applying it again
 * here would be a second source of truth that could only ever disagree.
 *
 * The `auto` sunset flip is NOT handled here either. It belongs to the mechanism rather than to the
 * control, because a chromeless page (a document upload, say) renders no header and still has to
 * follow the device. See `ThemeWatcher`, mounted in the provider stack.
 */
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  DEFAULT_MODE, THEME_MODES, applyTheme, devicePrefersDark, readStoredMode, resolveTheme,
  writeStoredMode, type ThemeMode,
} from '@/lib/theme'

export default function ThemeSelector() {
  const { t } = useT()
  const [mode, setMode] = useState<ThemeMode>(DEFAULT_MODE)

  // Read AFTER mount, never during render: the server has no localStorage, so reading it in render
  // would make the first client render disagree with the server's HTML. The visible cost is that
  // the box says "Auto" for one frame before correcting itself, which nobody is looking at.
  useEffect(() => {
    setMode(readStoredMode())
  }, [])

  const pick = (next: ThemeMode) => {
    setMode(next)
    writeStoredMode(next)
    applyTheme(resolveTheme(next, devicePrefersDark()))
  }

  return (
    <select
      value={mode}
      onChange={(e) => pick(e.target.value as ThemeMode)}
      className="text-sm border border-ground-200 rounded-lg px-2 py-1.5 bg-ground-0 text-ground-600 focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none cursor-pointer"
      aria-label={t('theme.label')}
    >
      {THEME_MODES.map((m) => (
        <option key={m} value={m}>{t(`theme.${m}`)}</option>
      ))}
    </select>
  )
}
