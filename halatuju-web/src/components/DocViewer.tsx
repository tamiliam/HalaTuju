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
 */
export default function DocViewer({ doc, onClose }: { doc: ViewerDoc | null; onClose: () => void }) {
  const { t } = useT()
  useEffect(() => {
    if (!doc) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [doc, onClose])
  if (!doc) return null

  const newTab = (
    <a href={doc.url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline">
      {t('admin.scholarship.docsDrawer.viewer.newTab')} ↗
    </a>
  )
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog" aria-modal="true" onClick={onClose}>
      <div className="flex h-full max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-gray-100 px-4 py-2.5">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-gray-800">{doc.label}</p>
            {doc.filename && <p className="truncate text-[11px] text-gray-400">{doc.filename}</p>}
          </div>
          {newTab}
          <button type="button" onClick={onClose}
            aria-label={t('admin.scholarship.docsDrawer.viewer.close')}
            className="rounded-md px-2 py-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700">✕</button>
        </div>
        <div className="flex-1 overflow-auto bg-gray-100">
          {doc.kind === 'image' && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={doc.url} alt={doc.label} className="mx-auto block max-h-full max-w-full object-contain" />
          )}
          {doc.kind === 'pdf' && (
            <iframe src={doc.url} title={doc.label} className="h-full w-full border-0" />
          )}
          {doc.kind === 'unsupported' && (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
              <p className="max-w-sm text-sm text-gray-600">
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
