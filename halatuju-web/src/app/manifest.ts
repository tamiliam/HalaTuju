import type { MetadataRoute } from 'next'

/**
 * The web app manifest (Mobile M0). TODAY it gives a home-screen SHORTCUT: a student who taps "Add
 * to Home Screen" gets HalaTuju's own icon and name instead of a page screenshot — and tapping it
 * opens HalaTuju in the ordinary browser, with its bar, back button and signed-in session. It is
 * NOT an app-like window yet: `display` is 'browser' (reason beside it), and standalone waits for
 * roadmap M8. A consequence worth knowing: Chrome only offers its own "Install app" prompt for a
 * standalone-type display, so with 'browser' Android users add it from the menu like any page.
 * Next serves this at `/manifest.webmanifest` and links it from every page; the iPhone icon is
 * `apple-icon.png` beside this file, which Next links the same way.
 *
 * ⚠ NO SERVICE WORKER, NO OFFLINE MODE — deliberately, and still so in M8. HalaTuju from the home
 * screen is the live site and nothing more; caching pages would show a student yesterday's offers
 * and statuses.
 *
 * The icons were cut from the 2048 px master that was `src/app/icon.png` until Mobile M1a (in git
 * history; M1a replaced the favicon with a 64 px cut of the same artwork, 5.9 KB instead of 5.7 MB):
 * the artwork alone, centred, without the generator mark in its corner. The maskable one
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
    // 'browser', NOT 'standalone' — for now. An iPhone home-screen app in standalone mode has no
    // back button and its OWN storage, separate from Safari: a sign-in or email link opens in
    // Safari and the app never sees that session. Standalone waits until every screen has its own
    // way back and the sign-in links are proven inside it (roadmap M8).
    display: 'browser',
    background_color: 'rgb(255 255 255)',
    theme_color: 'rgb(255 255 255)',
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}
