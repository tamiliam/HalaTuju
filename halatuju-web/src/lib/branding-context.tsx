'use client'

/**
 * BrandingProvider — the app-wide resolved branding (platform Sprint 6, decision D1/D2).
 *
 * Delivery: `NEXT_PUBLIC_ORG_CODE`. Unset or 'brightpath' ⇒ PLATFORM MODE — the app renders the
 * baked platform defaults and NEVER fetches (zero change, zero flash for BrightPath). Any other
 * code ⇒ a dark, best-effort fetch of GET /api/v1/branding/<code>/ that swaps in the tenant's
 * identity once it lands.
 *
 * Mounted OUTSIDE I18nProvider (see providers.tsx) so `t()` can read the branding and auto-inject
 * the five AUTO_TOKENS. The colour override (D3) writes `--brand-N` onto documentElement ONLY when
 * the tenant colour differs from the platform — so it never fires for BrightPath.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

import {
  PLATFORM,
  resolveBranding,
  brandRamp,
  type ResolvedBranding,
  type BrandingConfig,
} from '@/lib/branding'
import { THEME_ATTR } from '@/lib/theme'

const BrandingContext = createContext<ResolvedBranding>(PLATFORM)

const ORG_CODE = process.env.NEXT_PUBLIC_ORG_CODE || ''
const PLATFORM_CODE = 'brightpath'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function isPlatformMode(): boolean {
  return !ORG_CODE || ORG_CODE === PLATFORM_CODE
}

/**
 * Write the tenant's colour ramp onto :root as `--brand-N` RGB triplets, for the CURRENT mode.
 * Never runs for the platform (guarded on a differing colour), so BrightPath keeps the static
 * `globals.css` ramps — both of them.
 *
 * ⚠ THESE ARE INLINE STYLES, SO THEY BEAT THE STYLESHEET — including the dark block. That is what
 * makes `useBrandRampForTheme` below necessary: without it a tenant would get the LIGHT ramp
 * pinned onto the element in dark mode, which is the exact defect F3 raised, except unfixable from
 * CSS because an inline style wins.
 */
function applyColourOverride(b: ResolvedBranding, theme: 'light' | 'dark'): void {
  if (typeof document === 'undefined') return
  if (b.brandColour === PLATFORM.brandColour) return
  const root = document.documentElement
  for (const [step, triplet] of Object.entries(brandRamp(b.brandColour, theme))) {
    root.style.setProperty(`--brand-${step}`, triplet)
  }
}

/** The mode currently painted, read from the attribute the boot script and `applyTheme` both set. */
function currentTheme(): 'light' | 'dark' {
  if (typeof document === 'undefined') return 'light'
  return document.documentElement.getAttribute(THEME_ATTR) === 'dark' ? 'dark' : 'light'
}

/**
 * Re-derive a TENANT's ramp whenever the mode changes.
 *
 * There is no theme event to subscribe to — `applyTheme` sets an attribute on `<html>` and that is
 * deliberately all it does, because it runs on a sunset timer while people are half-way through
 * forms. So the honest signal is the attribute itself, watched. The observer is cheap (one
 * attribute filter on one element) and it is the ONLY thing that keeps a tenant's inline ramp
 * honest, since inline styles outrank the dark block in `globals.css`.
 */
function useBrandRampForTheme(branding: ResolvedBranding): void {
  useEffect(() => {
    if (typeof document === 'undefined') return
    applyColourOverride(branding, currentTheme())
    const obs = new MutationObserver(() => applyColourOverride(branding, currentTheme()))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: [THEME_ATTR] })
    return () => obs.disconnect()
  }, [branding])
}

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<ResolvedBranding>(PLATFORM)
  useBrandRampForTheme(branding)

  useEffect(() => {
    if (isPlatformMode()) return // BrightPath: never fetch
    let cancelled = false
    fetch(`${API_URL}/api/v1/branding/${encodeURIComponent(ORG_CODE)}/`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: BrandingConfig | null) => {
        if (cancelled || !data) return
        const resolved = resolveBranding(data)
        setBranding(resolved)   // the hook below applies the ramp, for the mode on screen
      })
      .catch(() => {
        /* total — a failed fetch leaves the platform defaults in place */
      })
    return () => {
      cancelled = true
    }
  }, [])

  return <BrandingContext.Provider value={branding}>{children}</BrandingContext.Provider>
}

export function useBranding(): ResolvedBranding {
  return useContext(BrandingContext)
}
