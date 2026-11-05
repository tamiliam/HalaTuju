'use client'

/**
 * BrandLogo — the single logo element (platform Sprint 6, decision D4). `src`/`alt` come from the
 * branding seam (platform = today's values, so BrightPath renders pixel-identically). Each call site
 * passes its own width/height/priority/className.
 *
 * ⚠ A PLAIN <img>, NOT `next/image` (Mobile M4b). `next/image` is ~4.5 kB of JavaScript, and on most
 * student routes this logo was its ONLY user. Since the security patch (pre-v3.1.0) the image optimiser
 * is OFF (`images.unoptimized` in next.config.js), so the logo is served as it is from /public: no
 * `/_next/image` address and no srcset. `brandLogo.test.tsx` pins this.
 */
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
  return (
    // A plain <img>, as `CourseCard` draws its pictures: deliberate (the header above).
    <img
      src={src}
      alt={branding.logoAlt}
      width={width}
      height={height}
      loading={priority ? 'eager' : 'lazy'}
      // The header's logo is the first picture on every page (next/image's `priority` did this). React 18
      // does not know the camelCase prop, so the attribute is written in lower case, as next/image does.
      {...(priority ? { fetchpriority: 'high' } : {})}
      decoding="async"
      className={className}
      style={{ color: 'transparent' }}
    />
  )
}
