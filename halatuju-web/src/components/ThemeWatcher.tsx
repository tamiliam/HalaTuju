'use client'

/**
 * Keeps `auto` honest for as long as the tab is open (Layer 1 F7d). Renders nothing.
 *
 * The before-paint script resolves `auto` ONCE, at load. A device that flips at sunset — which is
 * the entire point of `auto`, and what macOS and Windows both do on a schedule the person already
 * set — would otherwise leave a half-finished session in the wrong theme until the next navigation.
 *
 * ⚠ IT IS MOUNTED IN THE PROVIDER STACK, NOT IN `ThemeSelector`, AND THE DIFFERENCE IS REAL.
 * The listener belongs to the MECHANISM; the selector is a control. A chromeless page renders no
 * header — document upload is one, and it is exactly the screen someone sits on for a long time —
 * so hanging this off the control would drop the flip precisely where it matters most.
 *
 * ⚠ IT RE-READS STORAGE INSIDE THE HANDLER rather than closing over React state. The subscription
 * is then correct for the life of the tab with no dependency list, so switching to `dark` and back
 * to `auto` cannot leave a stale listener behind — the class of bug that survives a green suite.
 *
 * `applyTheme` sets one attribute and nothing else, so a sunset flip costs no re-render and cannot
 * lose a half-filled form. Never make it do more.
 */
import { useEffect } from 'react'
import { applyTheme, devicePrefersDark, readStoredMode, resolveTheme } from '@/lib/theme'

export default function ThemeWatcher() {
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    let mq: MediaQueryList
    try {
      mq = window.matchMedia('(prefers-color-scheme: dark)')
    } catch {
      return
    }
    const onChange = () => {
      if (readStoredMode() !== 'auto') return
      applyTheme(resolveTheme('auto', devicePrefersDark()))
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return null
}
