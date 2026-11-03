'use client'
import { useEffect } from 'react'
import { useT } from '@/lib/i18n'

export interface ViewerDoc {
  label: string
  filename: string
  url: string
  kind: 'image' | 'pdf' | 'unsupported'
}

/**
 * In-cockpit document viewer (Option B). Opens a document EMBEDDED beside the verdict so the
 * reviewer views it in context — never a download, never dependent on the browser's "download
 * PDFs" setting. Images render via <img>, PDFs via <iframe>; HEIC/HEIF (browsers can't render
 * it) falls back to an "open the original" link. Esc / backdrop click closes.
 *
 * ⚠ NOT A SHEET, ON PURPOSE (Mobile M1b). A document needs the whole screen, not a bottom sheet
 * capped at 90 %: on a phone it is FULL SCREEN (no margin, no rounded corners, the header padded
 * clear of the notch, a 44 px close), on a desktop the framed viewer it always was. It is one of the
 * named exemptions in `mobileStandard.test.ts`. On a phone a PDF is a 44 px Open link to the phone's own
 * viewer in a new tab, not an iframe (Mobile M6b, owner 2026-11-03; page images were not chosen).
 */
/** What counts as a phone for the PDF rule: narrow, or touch-first (the globals.css 16 px field rule's test). */
export const PHONE_QUERY = '(max-width: 767.98px), (pointer: coarse)'

export default function DocViewer({ doc, onClose }: { doc: ViewerDoc | null; onClose: () => void }) {
  const { t } = useT()
  useEffect(() => {
    if (!doc) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [doc, onClose])
  if (!doc) return null

  // Mobile M6b (owner, 2026-11-03): ON A PHONE a PDF opens in the phone's OWN viewer, in a new tab —
  // every page, with zoom — never an iframe (iPhone draws page one only, without zoom). "Phone" is a
  // narrow screen OR a touch-first one (an iPhone held sideways is wider than md). Read when the viewer
  // opens; a browser without matchMedia is a desktop. Images stay inline everywhere.
  const phone = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia(PHONE_QUERY).matches
  const newTab = (
    <a href={doc.url} target="_blank" rel="noreferrer"
      className="text-xs text-primary-600 hover:underline max-md:inline-flex max-md:min-h-11 max-md:items-center max-md:px-1 max-md:text-sm">
      {t('admin.scholarship.docsDrawer.viewer.newTab')} ↗
    </a>
  )
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 md:p-4"
      role="dialog" aria-modal="true" aria-label={doc.label} onClick={onClose}>
      <div className="flex h-full w-full max-w-4xl flex-col overflow-hidden bg-ground-0 shadow-2xl md:max-h-[92dvh] md:rounded-xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-ground-100 px-4 pb-2.5 pt-[max(0.625rem,env(safe-area-inset-top))] md:pt-2.5">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-ground-800">{doc.label}</p>
            {doc.filename && <p className="truncate text-xs text-ground-400 md:text-[11px]">{doc.filename}</p>}
          </div>
          {newTab}
          <button type="button" onClick={onClose}
            aria-label={t('admin.scholarship.docsDrawer.viewer.close')}
            className="-mr-2 inline-flex h-11 w-11 items-center justify-center rounded-md text-ground-400 hover:bg-ground-100 hover:text-ground-700">✕</button>
        </div>
        <div className="flex-1 overflow-auto bg-ground-100">
          {doc.kind === 'image' && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={doc.url} alt={doc.label} className="mx-auto block max-h-full max-w-full object-contain" />
          )}
          {doc.kind === 'pdf' && !phone && (
            <iframe src={doc.url} title={doc.label} className="h-full w-full border-0" />
          )}
          {doc.kind === 'pdf' && phone && (
            <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center" data-pdf-phone>
              <p className="max-w-xs text-[15px] text-ground-700">{t('admin.scholarship.docsDrawer.viewer.pdfPhone')}</p>
              <a href={doc.url} target="_blank" rel="noreferrer"
                className="inline-flex min-h-12 items-center justify-center rounded-lg bg-brand-fill px-6 text-base font-semibold text-brand-fill-ink">
                {t('admin.scholarship.docsDrawer.viewer.openPdf')} ↗
              </a>
            </div>
          )}
          {doc.kind === 'unsupported' && (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
              <p className="max-w-sm text-sm text-ground-600">
                {t('admin.scholarship.docsDrawer.viewer.noPreview')}
              </p>
              {newTab}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
