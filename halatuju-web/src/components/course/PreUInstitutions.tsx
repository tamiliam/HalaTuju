'use client'

/**
 * The pre-university course pages' "where to study" sections — the Form Six schools of an STPM
 * stream and the matriculation colleges of a track — and the STPM subject key. Moved verbatim out
 * of `app/course/[id]/page.tsx` (Mobile M3; that page passed 600 lines when its phone layout came),
 * plus the M3 phone fixes they carry: no inner scroll box, 44 px links and selects, 20 schools a page.
 */
import { useMemo, useState } from 'react'
import { useT } from '@/lib/i18n'
import { STPM_SCHOOLS, type StpmSchool } from '@/data/stpm-schools'
import { MATRIC_COLLEGES, type MatricCollege } from '@/data/matric-colleges'
import { SUBJECT_NAMES, SUBJECT_CHIP, filterSubjects, legendSubjects } from '@/lib/stpmSubjects'
import { MATRIC_TRACK_MAP, TRACK_CHIP, TRACK_LABELS, type TrackId } from '@/lib/matricTracks'

// ── STPM rich institution section ────────────────────────────────────────

export function SubjectLegend({ stream }: { stream: string }) {
  const subjects = legendSubjects(stream)

  return (
    <section className="bg-ground-0 rounded-xl border border-ground-200 p-6">
      <h2 className="text-lg font-semibold text-ground-900 mb-3">Subject Key</h2>
      <div className="space-y-2">
        {subjects.map(code => (
          <div key={code} className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${SUBJECT_CHIP}`}>
              {code}
            </span>
            <span className="text-xs text-ground-600">{SUBJECT_NAMES[code]}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function formatPhone(raw: string): string {
  const d = raw.replace(/\D/g, '')
  if (d.length === 10) return `${d.slice(0, 3)}-${d.slice(3, 6)} ${d.slice(6)}`
  if (d.length === 9) return `${d.slice(0, 2)}-${d.slice(2, 5)} ${d.slice(5)}`
  if (d.length === 11) return `${d.slice(0, 3)}-${d.slice(3, 7)} ${d.slice(7)}`
  return raw
}

const STPM_STREAM_MAP: Record<string, string> = {
  'stpm-sains': 'Sains',
  'stpm-sains-sosial': 'Sains Sosial',
}

// 20, not 50 (Mobile M3): with the 600 px inner scroll box gone, the list is part of the page.
const PAGE_SIZE = 20

export function StpmInstitutionsSection({ courseId }: { courseId: string }) {
  const { t } = useT()
  const streamName = STPM_STREAM_MAP[courseId] || 'Sains'
  const [stateFilter, setStateFilter] = useState('')
  const [ppdFilter, setPpdFilter] = useState('')
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)

  const streamSchools = useMemo(() => {
    return STPM_SCHOOLS.filter(s => s.streams.includes(streamName))
  }, [streamName])

  const allStates = useMemo(() => {
    return Array.from(new Set(streamSchools.map(s => s.state))).sort()
  }, [streamSchools])

  const availablePpds = useMemo(() => {
    let schools = streamSchools
    if (stateFilter) schools = schools.filter(s => s.state === stateFilter)
    return Array.from(new Set(schools.map(s => s.ppd))).sort()
  }, [streamSchools, stateFilter])

  const filteredSchools = useMemo(() => {
    let schools = streamSchools
    if (stateFilter) schools = schools.filter(s => s.state === stateFilter)
    if (ppdFilter) schools = schools.filter(s => s.ppd === ppdFilter)
    return schools
  }, [streamSchools, stateFilter, ppdFilter])

  const displayedSchools = filteredSchools.slice(0, displayCount)
  const remaining = filteredSchools.length - displayCount

  return (
    <section className="bg-ground-0 rounded-xl border border-ground-200 p-4 sm:p-6">
      <h2 className="text-xl font-semibold text-ground-900 mb-4">
        {t('courseDetail.whereToStudy')}
        <span className="text-ground-500 font-normal ml-2">
          ({filteredSchools.length})
        </span>
      </h2>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={stateFilter}
          onChange={e => { setStateFilter(e.target.value); setPpdFilter(''); setDisplayCount(PAGE_SIZE) }}
          className="min-h-11 w-full min-w-0 rounded-lg border border-ground-300 px-3 py-2 text-sm bg-ground-0 focus:ring-2 focus:ring-brand-shape focus:border-brand-shape sm:w-auto"
        >
          <option value="">All States</option>
          {allStates.map(state => (
            <option key={state} value={state}>{state}</option>
          ))}
        </select>
        <select
          value={ppdFilter}
          onChange={e => { setPpdFilter(e.target.value); setDisplayCount(PAGE_SIZE) }}
          className="min-h-11 w-full min-w-0 rounded-lg border border-ground-300 px-3 py-2 text-sm bg-ground-0 focus:ring-2 focus:ring-brand-shape focus:border-brand-shape sm:w-auto"
        >
          <option value="">All Districts</option>
          {availablePpds.map(ppd => (
            <option key={ppd} value={ppd}>{ppd}</option>
          ))}
        </select>
      </div>

      {/* ⚠ NO INNER SCROLL BOX (Mobile M3). This was a 600 px box with its own scroll around 240
          schools: on a phone the thumb scrolled the box, not the page, and was trapped in it. The
          list is part of the page now, 20 at a time. `discoveryLayout.test.ts` holds it. */}
      <div className="space-y-3">
        {displayedSchools.length > 0 ? (
          displayedSchools.map(school => (
            <StpmSchoolCard key={school.code} school={school} stream={streamName} />
          ))
        ) : (
          <p className="text-ground-400 text-center py-8">
            No schools match the selected filters.
          </p>
        )}
      </div>

      {remaining > 0 && (
        <div className="text-center pt-4">
          <button
            className="btn-secondary"
            onClick={() => setDisplayCount(displayCount + PAGE_SIZE)}
          >
            {t('search.loadMore')} ({remaining} {t('search.remaining')})
          </button>
        </div>
      )}
    </section>
  )
}

function StpmSchoolCard({ school, stream }: { school: StpmSchool; stream: string }) {
  const subjects = school.subjects ? filterSubjects(school.subjects, stream) : []

  return (
    <div className="rounded-lg border border-ground-200 bg-ground-50 p-3 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-ground-900 text-sm sm:text-base mb-1 break-words">
            {school.name}
          </h3>
          <p className="text-xs sm:text-sm text-ground-500 mb-2">
            {school.state} &middot; {school.ppd}
          </p>
          {subjects.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {subjects.map(s => (
                <span key={s} className={`px-1.5 py-0.5 rounded text-[10px] sm:text-xs font-medium ${SUBJECT_CHIP}`}>
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
        {school.phone && (
          <a
            href={`tel:${school.phone}`}
            className="-my-2 inline-flex min-h-11 items-center gap-1 self-start whitespace-nowrap text-sm text-primary-600 hover:text-primary-800"
          >
            <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            {formatPhone(school.phone)}
          </a>
        )}
      </div>
    </div>
  )
}

// ── Matric rich institution section ──────────────────────────────────────

export function MatricInstitutionsSection({ courseId }: { courseId: string }) {
  const { t } = useT()
  // No fallback (Bumi D2): a track without a college list here (the two Bumi-only tracks) lists
  // no colleges, rather than the Science track's.
  const trackId: TrackId = MATRIC_TRACK_MAP[courseId]
  const [stateFilter, setStateFilter] = useState('')

  const trackColleges = useMemo(() => {
    let colleges = MATRIC_COLLEGES.filter(c =>
      c.tracks.includes(trackId as MatricCollege['tracks'][number])
    )
    if (stateFilter) colleges = colleges.filter(c => c.state === stateFilter)
    return colleges
  }, [trackId, stateFilter])

  const availableStates = useMemo(() => {
    const filtered = MATRIC_COLLEGES.filter(c =>
      c.tracks.includes(trackId as MatricCollege['tracks'][number])
    )
    return Array.from(new Set(filtered.map(c => c.state))).sort()
  }, [trackId])

  return (
    <section className="bg-ground-0 rounded-xl border border-ground-200 p-4 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h2 className="text-xl font-semibold text-ground-900">
          {t('courseDetail.whereToStudy')}
          <span className="text-ground-400 font-normal ml-2 text-base">
            ({trackColleges.length})
          </span>
        </h2>
        <select
          value={stateFilter}
          onChange={e => setStateFilter(e.target.value)}
          className="min-h-11 border border-ground-300 rounded-lg px-3 py-2 text-sm text-ground-700 bg-ground-0 focus:outline-none focus:ring-2 focus:ring-brand-shape focus:border-brand-shape"
        >
          <option value="">All States</option>
          {availableStates.map(state => (
            <option key={state} value={state}>{state}</option>
          ))}
        </select>
      </div>

      {trackColleges.length > 0 ? (
        <div className="space-y-3">
          {trackColleges.map(college => (
            <MatricCollegeCard key={college.id} college={college} trackId={trackId} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-ground-500 text-center py-8">
          No colleges found for the selected filters.
        </p>
      )}
    </section>
  )
}

function MatricCollegeCard({ college, trackId }: { college: MatricCollege; trackId: TrackId }) {
  return (
    <div className="bg-ground-50 rounded-lg p-4">
      <h3 className="font-semibold text-ground-900 mb-2">{college.name}</h3>

      <div className="flex items-center gap-1.5 text-sm text-ground-500 mb-3">
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        {college.state}
      </div>

      <div className="flex flex-wrap gap-1.5 mb-3">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TRACK_CHIP[trackId]}`}>
          {TRACK_LABELS[trackId]}
        </span>
      </div>

      <div className="flex items-center gap-2 text-sm text-ground-600 mb-1.5">
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
        </svg>
        {college.phone}
      </div>

      <a
        href={`https://${college.website}`}
        target="_blank"
        rel="noopener noreferrer"
        className="-my-1 inline-flex min-h-11 max-w-full items-center gap-2 break-all text-sm text-primary-600 hover:text-primary-700 hover:underline"
      >
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
        {college.website}
      </a>
    </div>
  )
}
