'use client'

/**
 * The sandbox's own Light / Dark / Auto control (Layer 1 F1).
 *
 * ⚠ THIS IS SANDBOX CHROME, NOT THE PRODUCT'S SWITCH. The real control belongs on a person's
 * account settings and saves to their account; it does not exist yet and is F1's remaining work.
 * This exists so a designer — or whoever is reviewing a repaint sprint — can flip modes on any
 * surface without a login and without waiting for that control to ship. Every sprint from F2 to F6
 * repaints a surface and has to be looked at in both modes; this is how.
 *
 * It writes the same storage key the real mechanism reads, so a reload keeps the mode — which also
 * makes it a live check that `public/theme-boot.js` and `src/lib/theme.ts` agree about that key.
 */
import { useEffect, useState } from 'react'
import {
  DEFAULT_MODE, THEME_MODES, applyTheme, devicePrefersDark, readStoredMode, resolveTheme,
  writeStoredMode, type ThemeMode,
} from '@/lib/theme'

export function SandboxThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(DEFAULT_MODE)

  // Read after mount, never during render: the server has no localStorage, and reading it in
  // render would make the first client render disagree with the server's HTML.
  //
  // ⚠ IT ALSO APPLIES, not just reads. The before-paint boot script is gated on the theme flag —
  // which is unset everywhere except a deliberate test — so on a sandbox load there is no
  // `data-theme` on <html> at all and the page starts light. Without this the toggle would show
  // "Dark" while the page sat light until you clicked something. A brief light-first flash is the
  // right trade here: the sandbox is a design tool, and the alternative is shipping the boot
  // script to real visitors before their surfaces are painted for it.
  useEffect(() => {
    const stored = readStoredMode()
    setMode(stored)
    applyTheme(resolveTheme(stored, devicePrefersDark()))
  }, [])

  // On `auto`, the device can change its mind mid-session — that is the whole point of auto, and
  // the sunset flip is the case this arc has to survive without losing a half-filled form.
  useEffect(() => {
    if (mode !== 'auto' || typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => applyTheme(resolveTheme('auto', mq.matches))
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [mode])

  const pick = (next: ThemeMode) => {
    setMode(next)
    writeStoredMode(next)
    applyTheme(resolveTheme(next, devicePrefersDark()))
  }

  return (
    <div className="flex items-center gap-1 rounded-lg border border-caution-300 p-0.5">
      {THEME_MODES.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => pick(m)}
          aria-pressed={mode === m}
          className={`rounded px-2 py-1 text-xs font-medium capitalize transition-colors ${
            mode === m
              ? 'bg-caution-900 text-white'
              : 'text-caution-900 hover:bg-caution-100'
          }`}
        >
          {m}
        </button>
      ))}
    </div>
  )
}
