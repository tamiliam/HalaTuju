# Self-hosted fonts (TD-305)

These three files are loaded by `src/app/layout.tsx` through `next/font/local`. They replaced
`next/font/google`, which downloaded the fonts inside every `next build` — so on 2026-09-29 a
malformed answer from Google failed a deploy that had changed nothing about fonts. A build now
needs nothing from Google.

| Family | File | Version (Google Fonts) | Weights | Subset | Bytes | SHA-256 |
|---|---|---|---|---|---|---|
| Lexend | `lexend/lexend-latin-wght.woff2` | v26 | variable, 100–900 | latin | 39,692 | `1ec8f6ee2750554b4bc59ff0b507d316a82a7ba37e0e5bebc41d3bd9b9faad46` |
| Inter | `inter/inter-latin-wght.woff2` | v20 | variable, 100–900 | latin | 48,432 | `c940764593d0fe5d596be327ca7558855e018039fb78509aa21921fd3644c3e4` |
| IBM Plex Sans | `ibm-plex-sans/ibm-plex-sans-latin-wght.woff2` | v23 | variable, declared at 400 / 500 / 600 / 700 | latin | 40,240 | `056e4e2459f57a0033c8c9c844ff19d6e42ac8602027803d4345823bcc939818` |

Total: **128,364 bytes**.

## Where they came from

Fetched once on 2026-09-29 from the Google Fonts CSS2 endpoint, with the SAME request
`next/font/google` 14.2.0 made (same URL, same Chrome 104 user agent), taking the `/* latin */`
face of each:

- `https://fonts.googleapis.com/css2?family=Lexend:wght@100..900&display=swap`
  → `https://fonts.gstatic.com/s/lexend/v26/wlpwgwvFAVdoq2_v-6QU82RHaA.woff2`
- `https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap`
  → `https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7W0Q5nw.woff2`
- `https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap`
  → `https://fonts.gstatic.com/s/ibmplexsans/v23/zYXzKVElMYYaJe8bpLHnCwDKr932-G7dytD-Dmu1syxeKYbSB4Zh.woff2`
  (Google serves Plex as one variable file and declares it four times, once per weight.)

Each file is **byte-identical** to the preloaded (`.p.woff2`) file the last Google-loader build
emitted into `.next/static/media` — checked by SHA-256 — so the glyphs on screen are unchanged.

Only the **latin** subset is kept, as `layout.tsx` asked for (`subsets: ['latin']`). The Google
loader also declared latin-ext and vietnamese faces (and cyrillic/greek for Inter and Plex), which
a browser fetched only if a page used such a character; those now fall back to the metric-matched
Arial fallback instead.

## Licence

All three are under the SIL Open Font License 1.1, which permits self-hosting and redistribution
with the licence. Each family's `OFL.txt` is beside its file, taken from
`https://github.com/google/fonts/tree/main/ofl/<family>/OFL.txt`. The files are unmodified.

## Replacing one

Do it deliberately: new file, new SHA-256 here AND in `src/lib/__tests__/fontSources.test.ts`
(which refuses any other bytes), and look at the page before and after.
