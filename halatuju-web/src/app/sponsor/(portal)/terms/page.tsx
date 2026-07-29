'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { getSponsorTerms, type SponsorTermsDocument } from '@/lib/api'

/**
 * The terms, re-readable at any time — half of what TD-186 was about: a sponsor could never go
 * back and see what they had agreed to.
 *
 * INSIDE the (portal) route group, so the layout's sign-in gate applies (owner: *"These terms
 * cannot be reached by outsiders"*). An outsider gets the short summary on the public /terms page
 * instead.
 */
export default function SponsorTermsPage() {
  const { t, locale } = useT()
  const { token } = useSponsorAuth()
  const [doc, setDoc] = useState<SponsorTermsDocument | null>(null)
  const [signed, setSigned] = useState('')
  const [acceptedAt, setAcceptedAt] = useState<string | null>(null)
  const [basis, setBasis] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!token) return
    getSponsorTerms(locale, { token })
      .then((d) => {
        setDoc(d.terms)
        setSigned(d.signed_name)
        setAcceptedAt(d.accepted_at)
        setBasis(d.state.terms_basis)
      })
      .catch(() => setError(t('sponsorPortal.terms.loadError')))
  }, [token, locale, t])

  useEffect(() => { load() }, [load])

  if (error) return <p className="text-sm text-critical-600">{error}</p>
  if (!doc) return <p className="text-sm text-ground-500">{t('sponsorPortal.terms.noneYet')}</p>

  return (
    <div className="max-w-2xl flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-ground-900">{doc.title}</h1>
        {doc.intro && <p className="text-ground-600 italic mt-2">{doc.intro}</p>}
      </div>

      {/* What they signed, and when. A GRANDFATHERED row is never dressed up as an acceptance —
          it says plainly that we did not ask. */}
      {acceptedAt && (
        <div className="rounded-xl border border-positive-200 bg-positive-50 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-positive-800">
            {t('sponsorPortal.terms.youAccepted')}
          </p>
          <p className="font-serif text-xl text-positive-900 mt-1">{signed}</p>
          <p className="text-xs text-positive-800/80 mt-0.5">
            {t('sponsorPortal.terms.acceptedStamp', { version: doc.version })}
          </p>
        </div>
      )}
      {basis === 'grandfathered' && (
        <div className="rounded-xl border border-ground-200 bg-ground-50 px-4 py-3 text-sm text-ground-600">
          {t('sponsorPortal.terms.grandfathered')}
        </div>
      )}

      <div className="flex flex-col gap-5">
        {doc.sections.map((s) => (
          <section key={s.order}>
            <h2 className="font-semibold text-ground-900">{s.order}. {s.heading}</h2>
            {s.body.split('\n\n').map((para, pi) => (
              <p key={pi} className="text-ground-700 mt-1.5 whitespace-pre-wrap">{para}</p>
            ))}
          </section>
        ))}
      </div>

      {/* §12 names the privacy notice, and section bodies are plain text with no links — so the
          link lives here, where someone reading that reference can actually follow it. */}
      <p className="text-xs text-ground-500 border-t border-ground-200 pt-4">
        {t('sponsorPortal.terms.privacyNote')}{' '}
        <Link href="/privacy" className="text-info-600 hover:underline">
          {t('sponsorAuth.privacyNotice')}
        </Link>.
      </p>
    </div>
  )
}
