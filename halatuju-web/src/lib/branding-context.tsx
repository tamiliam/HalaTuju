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

const BrandingContext = createContext<ResolvedBranding>(PLATFORM)

const ORG_CODE = process.env.NEXT_PUBLIC_ORG_CODE || ''
const PLATFORM_CODE = 'brightpath'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function isPlatformMode(): boolean {
  return !ORG_CODE || ORG_CODE === PLATFORM_CODE
}

/** Write the tenant's colour ramp onto :root as `--brand-N` RGB triplets. Never runs for the
 *  platform (guarded on a differing colour), so BrightPath keeps the static globals.css ramp. */
function applyColourOverride(b: ResolvedBranding): void {
  if (typeof document === 'undefined') return
  if (b.brandColour === PLATFORM.brandColour) return
  const root = document.documentElement
  for (const [step, triplet] of Object.entries(brandRamp(b.brandColour))) {
    root.style.setProperty(`--brand-${step}`, triplet)
  }
}

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<ResolvedBranding>(PLATFORM)

  useEffect(() => {
    if (isPlatformMode()) return // BrightPath: never fetch
    let cancelled = false
    fetch(`${API_URL}/api/v1/branding/${encodeURIComponent(ORG_CODE)}/`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: BrandingConfig | null) => {
        if (cancelled || !data) return
        const resolved = resolveBranding(data)
        setBranding(resolved)
        applyColourOverride(resolved)
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
