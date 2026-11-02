'use client'

/**
 * BrandLogo — the single logo element (platform Sprint 6, decision D4). `src`/`alt` come from the
 * branding seam (platform = today's values, so BrightPath renders pixel-identically). Each call site
 * passes its own width/height/priority/className.
 *
 * ⚠ A PLAIN <img>, NOT `next/image` (Mobile M4b). `next/image` is ~4.5 kB of JavaScript, and on most
 * student routes this logo was its ONLY user — so every page carried the component to draw one small
 * picture. The bundled platform asset still goes through Next's image optimiser exactly as before:
 * the same `/_next/image?url=…&w=…&q=75` addresses `next/image` wrote for a fixed-width image (1x and
 * 2x, each rounded up to the next of Next's default sizes — there is no `images` block in
 * next.config.js). A remote tenant URL, a `data:` / `blob:` URL or an SVG is used as it is, as next/image did.
 * That weight paid for the phone tab bar (`StudentTabBar`) on every route; `brandLogo.test.tsx` pins
 * the addresses.
 */
import { useBranding } from '@/lib/branding-context'

interface BrandLogoProps {
  width: number
  height: number
  priority?: boolean
  className?: string
}

/** Next's default `imageSizes` + `deviceSizes`, in order — the widths its optimiser will serve. */
const SIZES = [16, 32, 48, 64, 96, 128, 256, 384, 640, 750, 828, 1080, 1200, 1920, 2048, 3840]

/** The optimiser's address for `src` at the first served width of at least `w` (as next/image). */
export function optimised(src: string, w: number): string {
  const size = SIZES.find((s) => s >= w) ?? 3840
  return `/_next/image?url=${encodeURIComponent(src)}&w=${size}&q=75`
}

export default function BrandLogo({ width, height, priority, className }: BrandLogoProps) {
  const branding = useBranding()
  const src = branding.logoUrl
  // What next/image sent to the optimiser: not a remote URL (a tenant's, `unoptimized` as before), not a
  // `data:` / `blob:` URL and not an SVG (next/image passes those through as they are — M4b review).
  const local = !/^(https?:|data:|blob:)/.test(src) && !/\.svg($|\?)/i.test(src)
  return (
    // A plain <img>, as `CourseCard` draws its pictures: deliberate (the header above).
    <img
      src={local ? optimised(src, width * 2) : src}
      srcSet={local ? `${optimised(src, width)} 1x, ${optimised(src, width * 2)} 2x` : undefined}
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
