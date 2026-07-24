'use client'

/**
 * BrandLogo — the single logo element (platform Sprint 6, decision D4). Replaces the 14
 * `<Image src="/logo-icon.png" alt="HalaTuju">` sites; `src`/`alt` come from the branding seam
 * (platform = today's values, so BrightPath renders pixel-identically). A remote tenant URL is
 * rendered `unoptimized` (no next.config remotePatterns churn, no raw <img>); the bundled platform
 * asset keeps Next's image optimisation. Each call site passes its own width/height/priority/className.
 */
import Image from 'next/image'

import { useBranding } from '@/lib/branding-context'

interface BrandLogoProps {
  width: number
  height: number
  priority?: boolean
  className?: string
}

export default function BrandLogo({ width, height, priority, className }: BrandLogoProps) {
  const branding = useBranding()
  const src = branding.logoUrl
  const isExternal = /^https?:\/\//.test(src)
  return (
    <Image
      src={src}
      alt={branding.logoAlt}
      width={width}
      height={height}
      priority={priority}
      className={className}
      unoptimized={isExternal}
    />
  )
}
