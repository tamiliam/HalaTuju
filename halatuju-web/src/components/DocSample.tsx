'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import Sheet from '@/components/Sheet'
import { sampleFor, samplePath } from '@/lib/docSamples'

/**
 * H8: "See a sample" on a document card, and the viewer it opens (the approved mock_4: a sheet
 * from the bottom with the drawing, a short caption and a Close button).
 *
 * The drawing is a picture of a made-up document. It is never sent anywhere. Tap the picture to
 * enlarge it (it then scrolls sideways); tap again to fit the screen. Renders nothing for a
 * document type that has no sample.
 */
export function DocSample({ docType, kind, className = '' }: {
  docType: string
  /** The results kind for `higher_results` ('stpm' | 'matric'); anything else is ignored. */
  kind?: string | null
  className?: string
}) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const name = sampleFor(docType, kind)
  if (!name) return null
  const typeName = t(`scholarship.docs.type.${docType}`)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} data-sample-link={docType}
        className={`inline-flex min-h-11 items-center text-sm font-medium text-primary-600 underline hover:text-primary-700 ${className}`}>
        {t('scholarship.docs.sample.link')}
      </button>
      <SampleViewer open={open} name={name} title={t('scholarship.docs.sample.title', { type: typeName })}
        alt={t('scholarship.docs.sample.alt', { type: typeName })} onClose={() => setOpen(false)} />
    </>
  )
}

function SampleViewer({ open, name, title, alt, onClose }: {
  open: boolean; name: string; title: string; alt: string; onClose: () => void
}) {
  const { t } = useT()
  const [zoomed, setZoomed] = useState(false)
  // The shared Sheet: a bottom sheet on a phone, Escape and the backdrop close it, the page stays still.
  return (
    <Sheet open={open} onClose={() => { setZoomed(false); onClose() }} title={title} testId="sample-viewer"
      footer={
        <button type="button" onClick={() => { setZoomed(false); onClose() }} data-testid="sample-close"
          className="min-h-11 w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
          {t('scholarship.docs.sample.close')}
        </button>
      }>
      <button type="button" onClick={() => setZoomed((z) => !z)} data-testid="sample-zoom"
        aria-label={t(zoomed ? 'scholarship.docs.sample.shrink' : 'scholarship.docs.sample.enlarge')}
        className="block w-full overflow-auto rounded-lg border border-ground-300 p-0">
        <img src={samplePath(name)} alt={alt} className="block h-auto max-w-none"
          style={{ width: zoomed ? '220%' : '100%' }} />
      </button>
      <p className="mt-2 text-xs text-ground-500">{t('scholarship.docs.sample.zoomHint')}</p>
      <p className="mt-2 text-sm text-ground-600" data-testid="sample-caption">{t('scholarship.docs.sample.caption')}</p>
    </Sheet>
  )
}
