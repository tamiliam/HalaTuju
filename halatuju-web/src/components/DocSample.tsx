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
      <SampleViewer open={open} name={name} typeName={typeName} title={t('scholarship.docs.sample.title', { type: typeName })}
        alt={t('scholarship.docs.sample.alt', { type: typeName })} onClose={() => setOpen(false)} />
    </>
  )
}

/** "Identity card (IC)" -> "identity card (IC)" and "Photo" -> "photo", but "EPF statement" and "SPM results slip" stay. */
function inSentence(typeName: string): string {
  return /^[A-Z][a-z]/.test(typeName) ? typeName.charAt(0).toLowerCase() + typeName.slice(1) : typeName
}

const CHECK_POINTS = [1, 2, 3, 4]

function SampleViewer({ open, name, typeName, title, alt, onClose }: {
  open: boolean; name: string; typeName: string; title: string; alt: string; onClose: () => void
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
      <h3 className="mt-4 text-sm font-semibold text-ground-800" data-testid="sample-check-heading">
        {t('scholarship.docs.sample.checkHeading')}
      </h3>
      <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-sm text-ground-700" data-testid="sample-check-list">
        {CHECK_POINTS.map((n) => <li key={n}>{t(`scholarship.docs.sample.check.${name}.p${n}`)}</li>)}
      </ol>
      <p className="mt-3 text-sm text-ground-600" data-testid="sample-caption">
        {t('scholarship.docs.sample.caption', { type: inSentence(typeName) })}
      </p>
    </Sheet>
  )
}
