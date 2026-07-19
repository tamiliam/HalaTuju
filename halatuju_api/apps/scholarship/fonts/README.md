# Bundled fonts

## IBM Plex Serif — the contract document font
`IBMPlexSerif-Regular.ttf`, `IBMPlexSerif-Bold.ttf` — used by `bursary.generate_pdf` (registered
with reportlab so xhtml2pdf embeds them in the signed agreement PDF). Set as the document
`font-family` in `bursary.render_agreement_html` (with a Georgia/Times serif fallback for the
browser preview iframe, which can't load the .ttf).

- **Source:** https://github.com/IBM/plex (IBM Plex Serif)
- **Licence:** SIL Open Font License 1.1 — see `OFL.txt`. Free to bundle/embed/redistribute.
