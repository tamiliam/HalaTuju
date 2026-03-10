'use client'

import { useEffect, useState, useMemo } from 'react'
import Link from 'next/link'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'
import { checkAllPathways, type PathwayResult } from '@/lib/pathways'
import { STPM_SCHOOLS, type StpmSchool } from '@/data/stpm-schools'

const PAGE_SIZE = 50

export default function StpmDetailPage() {
  const { t } = useT()
  const [profile, setProfile] = useState<{
    grades: Record<string, string>
    coqScore: number
  } | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [stateFilter, setStateFilter] = useState('')
  const [streamFilter, setStreamFilter] = useState('')
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)

  // Load profile from localStorage
  useEffect(() => {
    const gradesStr = localStorage.getItem('halatuju_grades')
    const profileStr = localStorage.getItem('halatuju_profile')

    if (gradesStr && profileStr) {
      const grades = JSON.parse(gradesStr)
      const parsed = JSON.parse(profileStr)
      setProfile({
        grades,
        coqScore: parsed.coqScore ?? 5.0,
      })
    }

    setIsLoading(false)
  }, [])

  // Run pathway engine
  const stpmResults = useMemo(() => {
    if (!profile) return []
    const all = checkAllPathways(profile.grades, profile.coqScore)
    return all.filter((r) => r.pathway === 'stpm')
  }, [profile])

  const eligibleResults = useMemo(
    () => stpmResults.filter((r) => r.eligible),
    [stpmResults]
  )

  // Best mata gred among eligible bidang
  const bestMataGred = useMemo(() => {
    const eligible = eligibleResults.filter((r) => r.mataGred !== undefined)
    if (eligible.length === 0) return null
    return Math.min(...eligible.map((r) => r.mataGred!))
  }, [eligibleResults])

  // Map eligible bidang IDs to stream names used in school data
  const eligibleStreams = useMemo(() => {
    const streams = new Set<string>()
    for (const r of eligibleResults) {
      if (r.trackId === 'sains') streams.add('SAINS')
      if (r.trackId === 'sains_sosial') streams.add('SAINS SOSIAL')
    }
    return streams
  }, [eligibleResults])

  // Unique states from school data
  const allStates = useMemo(() => {
    const states = new Set<string>()
    STPM_SCHOOLS.forEach((s) => states.add(s.state))
    return Array.from(states).sort()
  }, [])

  // Filter schools: must offer at least one eligible stream, then by state/stream dropdowns
  const filteredSchools = useMemo(() => {
    let schools = STPM_SCHOOLS

    // Only show schools that offer at least one eligible stream
    if (eligibleStreams.size > 0) {
      schools = schools.filter((s) =>
        s.streams.some((stream) => eligibleStreams.has(stream))
      )
    } else {
      // No eligible streams — show nothing
      return []
    }

    // State filter
    if (stateFilter) {
      schools = schools.filter((s) => s.state === stateFilter)
    }

    // Stream filter
    if (streamFilter) {
      schools = schools.filter((s) => s.streams.includes(streamFilter))
    }

    return schools
  }, [eligibleStreams, stateFilter, streamFilter])

  const displayedSchools = filteredSchools.slice(0, displayCount)
  const remaining = filteredSchools.length - displayCount

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-primary-50 to-white">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mb-4" />
          <p className="text-gray-600">{t('common.loading')}</p>
        </div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            {t('dashboard.noProfile')}
          </h1>
          <p className="text-gray-600 mb-6">
            {t('dashboard.noProfileDesc')}
          </p>
          <Link href="/onboarding/exam-type" className="btn-primary">
            {t('dashboard.startOnboarding')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8">
        {/* Back link */}
        <Link
          href="/dashboard"
          className="text-sm text-primary-500 hover:text-primary-700 mb-6 inline-block"
        >
          &larr; {t('pathwayDetail.backToDashboard')}
        </Link>

        {/* Header */}
        <div className="bg-white rounded-xl border border-gray-200 px-6 py-5 mb-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-3">
            {t('pathwayDetail.stpmTitle')}
          </h1>

          {/* Mata Gred score */}
          {bestMataGred !== null && (
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-medium text-gray-600">
                {t('pathwayDetail.mataGred')}:
              </span>
              <span className="text-lg font-bold text-primary-600">
                {bestMataGred}
              </span>
            </div>
          )}

          {/* Eligible bidang badges */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-gray-600">
              {t('pathwayDetail.eligibleTracks')}:
            </span>
            {eligibleResults.length > 0 ? (
              eligibleResults.map((r) => (
                <span
                  key={r.trackId}
                  className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${
                    r.trackId === 'sains'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-blue-100 text-blue-800'
                  }`}
                >
                  {r.trackId === 'sains'
                    ? t('pathwayDetail.sains')
                    : t('pathwayDetail.sainsSosial')}
                  {r.mataGred !== undefined && (
                    <span className="ml-1.5 text-xs opacity-75">
                      ({t('pathwayDetail.mataGred')}: {r.mataGred}/{r.maxMataGred})
                    </span>
                  )}
                </span>
              ))
            ) : (
              <span className="text-sm text-gray-400">
                {t('pathways.noneEligible')}
              </span>
            )}
          </div>
        </div>

        {/* Filters + School Count */}
        {eligibleStreams.size > 0 && (
          <>
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                {t('pathwayDetail.schools')}{' '}
                <span className="text-gray-400 font-normal">
                  ({filteredSchools.length})
                </span>
              </h2>

              <div className="flex flex-wrap gap-2 sm:ml-auto">
                {/* State dropdown */}
                <select
                  value={stateFilter}
                  onChange={(e) => {
                    setStateFilter(e.target.value)
                    setDisplayCount(PAGE_SIZE)
                  }}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="">{t('pathwayDetail.allStates')}</option>
                  {allStates.map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </select>

                {/* Stream dropdown */}
                <select
                  value={streamFilter}
                  onChange={(e) => {
                    setStreamFilter(e.target.value)
                    setDisplayCount(PAGE_SIZE)
                  }}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="">{t('pathwayDetail.allStreams')}</option>
                  <option value="SAINS">{t('pathwayDetail.sains')}</option>
                  <option value="SAINS SOSIAL">
                    {t('pathwayDetail.sainsSosial')}
                  </option>
                </select>
              </div>
            </div>

            {/* School Table */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-6">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="text-left px-4 py-3 font-semibold text-gray-700">
                        {t('pathwayDetail.name')}
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-gray-700 hidden md:table-cell">
                        {t('pathwayDetail.state')}
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-gray-700 hidden lg:table-cell">
                        {t('pathwayDetail.ppd')}
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-gray-700">
                        {t('pathwayDetail.stream')}
                      </th>
                      <th className="text-left px-4 py-3 font-semibold text-gray-700 hidden sm:table-cell">
                        {t('pathwayDetail.phone')}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedSchools.map((school) => (
                      <SchoolRow key={school.code} school={school} />
                    ))}
                    {displayedSchools.length === 0 && (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-4 py-8 text-center text-gray-400"
                        >
                          No schools match the selected filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Load More */}
            {remaining > 0 && (
              <div className="text-center py-4">
                <button
                  className="btn-secondary"
                  onClick={() => setDisplayCount(displayCount + PAGE_SIZE)}
                >
                  {t('dashboard.loadMore')} ({remaining}{' '}
                  {t('dashboard.remaining')})
                </button>
              </div>
            )}
          </>
        )}

        {/* Caveat */}
        <p className="text-xs text-gray-400 mt-6">
          {t('pathwayDetail.stpmCaveat')}
        </p>
      </div>

      <AppFooter />
    </main>
  )
}

function SchoolRow({ school }: { school: StpmSchool }) {
  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50">
      <td className="px-4 py-3">
        <span className="font-medium text-gray-900">{school.name}</span>
        {/* Show state on mobile where column is hidden */}
        <span className="block text-xs text-gray-400 md:hidden">
          {school.state}
        </span>
      </td>
      <td className="px-4 py-3 text-gray-600 hidden md:table-cell">
        {school.state}
      </td>
      <td className="px-4 py-3 text-gray-600 hidden lg:table-cell">
        {school.ppd}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {school.streams.map((stream) => (
            <span
              key={stream}
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                stream === 'SAINS'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-blue-100 text-blue-800'
              }`}
            >
              {stream}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3 text-gray-600 hidden sm:table-cell">
        {school.phone}
      </td>
    </tr>
  )
}
