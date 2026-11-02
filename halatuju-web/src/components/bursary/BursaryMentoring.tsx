'use client'

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { PHONE_SECTION_FLAT } from '@/lib/phoneSection'   // rule 15 (Mobile M4c)
import { getBursaryMentoring, type BursaryMentoring as Payload } from '@/lib/api/bursaryMentoring'

const P = 'bursaryTabs.mentoring'

/** "KR" for "Kavitha Raman" — the circle beside the name. Students never see a photo. */
function initials(name: string): string {
  return name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join('')
}

/**
 * The student's Mentoring tab on My Bursary (student maintenance S7b; the owner-approved MentoringStudent board).
 *
 * ⚠ WHAT THE STUDENT SEES IS THE SERVER'S ALLOWLIST (`mentoring.student_payload`): the CURRENT mentor's name,
 * area, languages, About, an Email button, a Call button ONLY when the mentor shares their phone,
 * "Your mentor since", and the meetings as date + how. Never a photo, a note, a next step, minutes or a
 * past mentor. With no mentor, a calm line pointing to the organisation's own contact
 * (`{supportEmail}`, the same address the student's emails give). Words: the `bursaryTabs` namespace.
 */
export default function BursaryMentoring({ token }: { token: string | null }) {
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!token) return
    let live = true
    getBursaryMentoring({ token })
      .then((d) => { if (live) { setData(d); setFailed(false) } })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [token])

  if (failed) return <p className="text-sm text-critical-600">{t(`${P}.loadFailed`)}</p>
  if (!data) return null
  const m = data.mentor

  if (!m) {
    return (
      <section className="border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-dashed md:border-ground-300 md:bg-ground-0 md:p-5" data-testid="student-no-mentor">
        <h2 className="text-base font-semibold text-ground-900">{t(`${P}.none.title`)}</h2>
        <p className="mt-1 text-sm text-ground-700">{t(`${P}.none.body`)}</p>
      </section>
    )
  }

  const langs = [...m.languages.map((c) => t(`${P}.lang.${c}`)), ...(m.other_language ? [m.other_language] : [])]
  return (
    <>
      <section className={`space-y-3 ${PHONE_SECTION_FLAT}`} data-testid="student-mentor">
        <p className="text-xs font-semibold uppercase tracking-wide text-ground-600">{t(`${P}.title`)}</p>
        <div className="flex items-center gap-3">
          <span aria-hidden className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-info-50 font-semibold text-info-800">
            {initials(m.name)}
          </span>
          <div className="min-w-0">
            <p className="break-words text-lg font-semibold text-ground-900">{m.name}</p>
            <p className="break-words text-sm text-ground-600">{[m.area, langs.join(', ')].filter(Boolean).join(' · ')}</p>
          </div>
        </div>
        {m.about && <p className="whitespace-pre-line break-words text-sm leading-relaxed text-ground-700">{m.about}</p>}
        {m.email && (
          <a href={`mailto:${m.email}`} data-testid="student-mentor-email"
            className="flex h-11 items-center justify-center rounded-xl bg-brand-fill text-sm font-semibold text-brand-fill-ink">
            {t(`${P}.email`, { name: m.name })}
          </a>
        )}
        {m.phone && (
          <a href={`tel:${m.phone.replace(/[^\d+]/g, '')}`} data-testid="student-mentor-call"
            className="flex h-11 items-center justify-center rounded-xl border border-ground-300 bg-ground-0 text-sm text-ground-900">
            {t(`${P}.call`, { phone: m.phone })}
          </a>
        )}
        <p className="text-sm text-ground-600">{t(`${P}.since`, { date: formatDate(m.since) })}</p>
      </section>

      <section className="border-b border-ground-100 md:rounded-2xl md:border-0 md:bg-ground-0 md:shadow-sm" data-testid="student-meetings">
        <h2 className="pb-2 pt-4 text-base md:px-5 font-semibold text-ground-900">{t(`${P}.meetings`)}</h2>
        {data.meetings.length === 0
          ? <p className="border-t border-ground-100 py-3 text-sm text-ground-600 md:px-5">{t(`${P}.noMeetings`)}</p>
          : (
            <ul>
              {data.meetings.map((x, i) => (
                <li key={i} className="flex justify-between gap-3 border-t border-ground-100 py-3 text-sm md:px-5">
                  <span className="text-ground-900">{formatDate(x.met_on)}</span>
                  <span className="text-ground-600">{t(`${P}.mode.${x.mode}`)}</span>
                </li>
              ))}
            </ul>
          )}
      </section>

      <p className="px-1 text-xs text-ground-600">{t(`${P}.contact`)}</p>
    </>
  )
}
