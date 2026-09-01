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
 * the five AUTO_TOKENS. The colour override writes `--brand-N` onto documentElement from the
 * tenant's STORED token set (Layer 1 A1) or, when it has none, from the derivation D3 shipped —
 * and the derivation still fires only when the tenant colour differs from the platform, so
 * BrightPath keeps its own `globals.css` ramps either way.
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

const PLATFORM_CODE = 'brightpath'

// Read INSIDE the functions, not once at module scope. Next inlines every `process.env.NEXT_PUBLIC_*`
// textually at build time, so production is identical either way — but a module-scope constant can
// only be changed by re-importing the module, and re-importing under `jest.resetModules()` hands
// the provider a SECOND copy of React, which then has no hooks. Reading lazily is what lets
// `branding-context.test.tsx` mount one org code per case.
function orgCode(): string {
  return process.env.NEXT_PUBLIC_ORG_CODE || ''
}

function apiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
}

function isPlatformMode(): boolean {
  const code = orgCode()
  return !code || code === PLATFORM_CODE
}

/**
 * Write the tenant's colours onto :root as RGB triplets, for the CURRENT mode.
 *
 * TWO SOURCES, and the order matters (Layer 1 A1):
 *
 *  1. **A STORED token set wins.** Those are the shades the tenant APPROVED, frozen at the moment
 *     they approved them. Deriving them again here would mean that improving `brandRamp()` later
 *     silently restyles every tenant's product — the same reason a student's requirements freeze at
 *     submit. The names arrive as `brand-50`, so painting is a straight `--brand-50`.
 *  2. **Otherwise, derive from the colour column, exactly as before A1.** This is what makes the
 *     sprint a no-op on deploy: the platform and every tenant that has not set colours behave
 *     identically to yesterday. The `=== PLATFORM.brandColour` guard is the old one, kept — it is
 *     what stops BrightPath ever getting an inline ramp over its own `globals.css`.
 *
 * ⚠ THESE ARE INLINE STYLES, SO THEY BEAT THE STYLESHEET — including the dark block. That is what
 * makes `useBrandRampForTheme` below necessary: without it a tenant would get the LIGHT ramp
 * pinned onto the element in dark mode, which is the exact defect F3 raised, except unfixable from
 * CSS because an inline style wins. A stored set has the same property and the same cure — hence
 * both modes being stored, and this function taking the mode.
 */
function applyColourOverride(b: ResolvedBranding, theme: 'light' | 'dark'): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (b.theme) {
    for (const [name, triplet] of Object.entries(b.theme[theme])) {
      root.style.setProperty(`--${name}`, triplet)
    }
    return
  }
  if (b.brandColour === PLATFORM.brandColour) return
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
    fetch(`${apiUrl()}/api/v1/branding/${encodeURIComponent(orgCode())}/`)
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
