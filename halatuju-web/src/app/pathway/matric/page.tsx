'use client'

import { useEffect, useState, useMemo } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { checkAllPathways, type PathwayResult } from '@/lib/pathways'
import { MATRIC_COLLEGES, type MatricCollege } from '@/data/matric-colleges'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'

type TrackId = 'sains' | 'sains_komputer' | 'kejuruteraan' | 'perakaunan'

const TRACK_COLOURS: Record<TrackId, string> = {
  sains: 'bg-green-100 text-green-800',
  sains_komputer: 'bg-blue-100 text-blue-800',
  kejuruteraan: 'bg-orange-100 text-orange-800',
  perakaunan: 'bg-purple-100 text-purple-800',
}

const TRACK_I18N_KEYS: Record<TrackId, string> = {
  sains: 'pathwayDetail.sains',
  sains_komputer: 'pathwayDetail.sainsKomputer',
  kejuruteraan: 'pathwayDetail.kejuruteraan',
  perakaunan: 'pathwayDetail.perakaunan',
}

export default function MatricPathwayPage() {
  const { t } = useT()
  const [grades, setGrades] = useState<Record<string, string> | null>(null)
  const [coq, setCoq] = useState<number>(0)
  const [stateFilter, setStateFilter] = useState<string>('all')

  // Load profile from localStorage
  useEffect(() => {
    const gradesRaw = localStorage.getItem('halatuju_grades')
    const profileRaw = localStorage.getItem('halatuju_profile')

    if (gradesRaw && profileRaw) {
      setGrades(JSON.parse(gradesRaw))
      const profile = JSON.parse(profileRaw)
      setCoq(profile.coqScore ?? profile.coq ?? 5.0)
    }
  }, [])

  // Run pathway engine
  const matricResults = useMemo(() => {
    if (!grades) return []
    return checkAllPathways(grades, coq).filter(
      (r): r is PathwayResult & { pathway: 'matric' } => r.pathway === 'matric'
    )
  }, [grades, coq])

  const eligibleTracks = useMemo(
    () => matricResults.filter(r => r.eligible),
    [matricResults]
  )

  // Merit score: take the highest from eligible tracks (they can differ per track)
  const bestMerit = useMemo(() => {
    if (eligibleTracks.length === 0) return null
    return Math.max(...eligibleTracks.map(r => r.merit ?? 0))
  }, [eligibleTracks])

  // Merit band
  const meritBand = useMemo(() => {
    if (bestMerit === null) return null
    if (bestMerit >= 94) return { label: t('pathwayDetail.high'), colour: 'bg-green-100 text-green-800' }
    if (bestMerit >= 89) return { label: t('pathwayDetail.fair'), colour: 'bg-amber-100 text-amber-800' }
    return { label: t('pathwayDetail.low'), colour: 'bg-red-100 text-red-800' }
  }, [bestMerit, t])

  // Eligible track IDs for filtering colleges
  const eligibleTrackIds = useMemo(
    () => new Set(eligibleTracks.map(r => r.trackId)),
    [eligibleTracks]
  )

  // Filter colleges: must offer at least one eligible track
  const filteredColleges = useMemo(() => {
    let colleges = MATRIC_COLLEGES.filter(c =>
      c.tracks.some(track => eligibleTrackIds.has(track))
    )
    if (stateFilter !== 'all') {
      colleges = colleges.filter(c => c.state === stateFilter)
    }
    return colleges
  }, [eligibleTrackIds, stateFilter])

  // Unique states from filtered-by-track colleges (before state filter)
  const availableStates = useMemo(() => {
    const trackFilteredColleges = MATRIC_COLLEGES.filter(c =>
      c.tracks.some(track => eligibleTrackIds.has(track))
    )
    const states = Array.from(new Set(trackFilteredColleges.map(c => c.state))).sort()
    return states
  }, [eligibleTrackIds])

  // Loading / no profile state
  if (!grades) {
    return (
      <main className="min-h-screen bg-gray-50">
        <AppHeader />
        <div className="flex items-center justify-center py-24">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
            <p className="text-gray-600">{t('common.loadingProfile')}</p>
          </div>
        </div>
        <AppFooter />
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-4 sm:px-6 py-8 max-w-5xl">
        {/* Back link */}
        <Link
          href="/dashboard"
          className="inline-flex items-center text-sm text-gray-500 hover:text-primary-600 mb-6"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          {t('pathwayDetail.backToDashboard')}
        </Link>

        {/* Header card */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {t('pathwayDetail.matricTitle')}
              </h1>
              {bestMerit !== null && meritBand && (
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-sm text-gray-500">{t('pathwayDetail.meritScore')}</span>
                  <span className="text-xl font-semibold text-gray-900">{bestMerit}</span>
                  <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${meritBand.colour}`}>
                    {meritBand.label}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Eligible tracks */}
          {eligibleTracks.length > 0 && (
            <div className="mt-4">
              <p className="text-sm text-gray-500 mb-2">{t('pathwayDetail.eligibleTracks')}</p>
              <div className="flex flex-wrap gap-2">
                {eligibleTracks.map(track => (
                  <span
                    key={track.trackId}
                    className={`text-sm font-medium px-3 py-1 rounded-full ${TRACK_COLOURS[track.trackId as TrackId]}`}
                  >
                    {t(TRACK_I18N_KEYS[track.trackId as TrackId])}
                  </span>
                ))}
              </div>
            </div>
          )}

          {eligibleTracks.length === 0 && (
            <p className="mt-4 text-sm text-red-600">
              {t('pathwayDetail.eligibleTracks')}: 0
            </p>
          )}
        </div>

        {/* Colleges section */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              {t('pathwayDetail.colleges')}
              <span className="text-gray-400 font-normal ml-2 text-sm">
                ({filteredColleges.length})
              </span>
            </h2>

            {/* State filter */}
            <select
              value={stateFilter}
              onChange={e => setStateFilter(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="all">{t('pathwayDetail.allStates')}</option>
              {availableStates.map(state => (
                <option key={state} value={state}>{state}</option>
              ))}
            </select>
          </div>

          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left">
                  <th className="py-3 pr-4 font-medium text-gray-500">{t('pathwayDetail.name')}</th>
                  <th className="py-3 pr-4 font-medium text-gray-500">{t('pathwayDetail.state')}</th>
                  <th className="py-3 pr-4 font-medium text-gray-500">{t('pathwayDetail.tracks')}</th>
                  <th className="py-3 pr-4 font-medium text-gray-500">{t('pathwayDetail.phone')}</th>
                  <th className="py-3 font-medium text-gray-500">{t('pathwayDetail.website')}</th>
                </tr>
              </thead>
              <tbody>
                {filteredColleges.map(college => (
                  <CollegeRow key={college.id} college={college} eligibleTrackIds={eligibleTrackIds} />
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {filteredColleges.map(college => (
              <CollegeCard key={college.id} college={college} eligibleTrackIds={eligibleTrackIds} />
            ))}
          </div>

          {filteredColleges.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-8">
              No colleges found for the selected filters.
            </p>
          )}
        </div>

        {/* Caveat */}
        <p className="text-xs text-gray-400 text-center px-4 mb-8">
          {t('pathwayDetail.matricCaveat')}
        </p>
      </div>

      <AppFooter />
    </main>
  )
}

// --- Sub-components ---

function CollegeRow({
  college,
  eligibleTrackIds,
}: {
  college: MatricCollege
  eligibleTrackIds: Set<string>
}) {
  const { t } = useT()

  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50">
      <td className="py-3 pr-4 font-medium text-gray-900">{college.name}</td>
      <td className="py-3 pr-4 text-gray-600">{college.state}</td>
      <td className="py-3 pr-4">
        <div className="flex flex-wrap gap-1">
          {college.tracks.map(track => (
            <span
              key={track}
              className={`text-xs px-2 py-0.5 rounded-full ${
                eligibleTrackIds.has(track)
                  ? TRACK_COLOURS[track]
                  : 'bg-gray-100 text-gray-400'
              }`}
            >
              {t(TRACK_I18N_KEYS[track])}
            </span>
          ))}
        </div>
      </td>
      <td className="py-3 pr-4 text-gray-600 whitespace-nowrap">{college.phone}</td>
      <td className="py-3">
        <a
          href={`https://${college.website}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary-600 hover:text-primary-700 hover:underline"
        >
          {college.website}
        </a>
      </td>
    </tr>
  )
}

function CollegeCard({
  college,
  eligibleTrackIds,
}: {
  college: MatricCollege
  eligibleTrackIds: Set<string>
}) {
  const { t } = useT()

  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <h3 className="font-medium text-gray-900 mb-1">{college.name}</h3>
      <p className="text-sm text-gray-500 mb-2">{college.state}</p>

      <div className="flex flex-wrap gap-1 mb-3">
        {college.tracks.map(track => (
          <span
            key={track}
            className={`text-xs px-2 py-0.5 rounded-full ${
              eligibleTrackIds.has(track)
                ? TRACK_COLOURS[track]
                : 'bg-gray-100 text-gray-400'
            }`}
          >
            {t(TRACK_I18N_KEYS[track])}
          </span>
        ))}
      </div>

      <div className="flex flex-col gap-1 text-sm">
        <div className="flex items-center gap-2 text-gray-600">
          <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
          </svg>
          {college.phone}
        </div>
        <a
          href={`https://${college.website}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-primary-600 hover:underline"
        >
          <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          {college.website}
        </a>
      </div>
    </div>
  )
}
