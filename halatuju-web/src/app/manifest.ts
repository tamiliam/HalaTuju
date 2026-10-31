import type { MetadataRoute } from 'next'

/**
 * The web app manifest (Mobile M0) — what lets a student "Add to Home Screen" and open HalaTuju
 * like an app: its own icon, no browser bar, the right name under the icon. Next serves this at
 * `/manifest.webmanifest` and links it from every page; the iPhone icon is `apple-icon.png` beside
 * this file, which Next links the same way.
 *
 * ⚠ NO SERVICE WORKER, NO OFFLINE MODE — deliberately. An installed HalaTuju is the live site in its
 * own window and nothing more; caching pages would show a student yesterday's offers and statuses.
 *
 * The icons were cut from `src/app/icon.png` (2048 px): the artwork alone, centred. The maskable one
 * sits on white with the artwork inside the 80 % safe circle, so Android can crop it to any shape
 * without clipping the arrow. Colours are `--ground-0` (white), matching the page header and the
 * light `themeColor` in `layout.tsx`.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: '/',
    name: 'HalaTuju',
    short_name: 'HalaTuju',
    description: 'Masukkan keputusan SPM atau STPM anda dan temui kursus yang anda layak. Percuma.',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    background_color: 'rgb(255 255 255)',
    theme_color: 'rgb(255 255 255)',
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}
