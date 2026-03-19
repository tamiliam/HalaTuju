'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  getSavedCourses,
  unsaveCourse,
  updateSavedCourseStatus,
  getCourse,
  getStpmCourseDetail,
  type SavedCourseWithStatus,
  type Institution,
  type CourseRequirements,
  type StpmRequirements,
} from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useToast } from '@/components/Toast'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'
import { useFieldTaxonomy } from '@/hooks/useFieldTaxonomy'
import { useOnboardingGuard } from '@/lib/useOnboardingGuard'

type QualificationTab = 'SPM' | 'STPM'

interface CompareData {
  course_id: string
  name: string
  level: string
  field: string
  institution: string
  state: string
  type: string
  fees: string
  allowance: string
  merit: string
  requirements: string[]
  semesters: string
  courseType: 'spm' | 'stpm'
}

export default function SavedPage() {
  const { t, locale } = useT()
  const router = useRouter()
  const { getFieldName } = useFieldTaxonomy(locale)
  const { ready: onboarded, loading: guardLoading } = useOnboardingGuard()
  const { token, isAuthenticated, isLoading: authLoading } = useAuth()
  const { showToast } = useToast()
  const [courses, setCourses] = useState<SavedCourseWithStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<QualificationTab>('SPM')
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  // Compare state (desktop only)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [comparing, setComparing] = useState(false)
  const [compareData, setCompareData] = useState<CompareData[]>([])
  const [compareLoading, setCompareLoading] = useState(false)

  useEffect(() => {
    if (authLoading) return
    if (!isAuthenticated || !token) {
      setLoading(false)
      return
    }
    getSavedCourses({ token })
      .then(({ saved_courses }) => setCourses(saved_courses))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [authLoading, isAuthenticated, token])

  // Clear selection when switching tabs
  useEffect(() => {
    setSelected(new Set())
    setComparing(false)
  }, [activeTab])

  const filteredCourses = courses.filter(c =>
    (c.course_type === 'stpm' ? 'STPM' : 'SPM') === activeTab
  )

  const spmCount = courses.filter(c => c.course_type !== 'stpm').length
  const stpmCount = courses.filter(c => c.course_type === 'stpm').length

  const handleRemove = async (courseId: string) => {
    if (!token) return
    setCourses(prev => prev.filter(c => c.course_id !== courseId))
    setSelected(prev => { const next = new Set(prev); next.delete(courseId); return next })
    try {
      await unsaveCourse(courseId, { token })
      showToast('Course removed', 'success')
    } catch {
      const { saved_courses } = await getSavedCourses({ token })
      setCourses(saved_courses)
      showToast('Failed to remove course', 'error')
    }
  }

  const handleStatusUpdate = async (courseId: string, newStatus: string) => {
    if (!token) return
    setUpdatingId(courseId)

    const course = courses.find(c => c.course_id === courseId)
    let targetStatus = newStatus
    if (course?.interest_status === newStatus) {
      targetStatus = newStatus === 'got_offer' ? 'applied' : 'interested'
    }

    setCourses(prev => prev.map(c =>
      c.course_id === courseId ? { ...c, interest_status: targetStatus } : c
    ))

    try {
      await updateSavedCourseStatus(courseId, targetStatus, { token })
    } catch {
      setCourses(prev => prev.map(c =>
        c.course_id === courseId ? { ...c, interest_status: course?.interest_status || 'interested' } : c
      ))
      showToast('Failed to update status', 'error')
    }
    setUpdatingId(null)
  }

  const toggleSelect = (courseId: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(courseId)) {
        next.delete(courseId)
      } else if (next.size < 3) {
        next.add(courseId)
      } else {
        showToast('Maximum 3 courses to compare', 'error')
      }
      return next
    })
  }

  const formatSpmReqs = (reqs: CourseRequirements): string[] => {
    const items: string[] = []
    for (const g of reqs.general) {
      items.push(g.label)
    }
    for (const s of reqs.special) {
      items.push(s.label)
    }
    if (reqs.merit_cutoff) items.push(`Merit: ${reqs.merit_cutoff}`)
    return items.length > 0 ? items : ['—']
  }

  const formatStpmReqs = (reqs: StpmRequirements): string[] => {
    const items: string[] = []
    if (reqs.min_cgpa) items.push(`CGPA ≥ ${reqs.min_cgpa}`)
    if (reqs.min_muet_band) items.push(`MUET Band ≥ ${reqs.min_muet_band}`)
    if (reqs.stpm_subjects?.length) items.push(`STPM: ${reqs.stpm_subjects.join(', ')}`)
    if (reqs.spm_prerequisites?.length) items.push(`SPM: ${reqs.spm_prerequisites.join(', ')}`)
    if (reqs.req_interview) items.push('Temuduga')
    if (reqs.no_colorblind) items.push('Tiada buta warna')
    return items.length > 0 ? items : ['—']
  }

  const handleCompare = async () => {
    if (selected.size < 2) {
      showToast('Select at least 2 courses', 'error')
      return
    }
    setCompareLoading(true)
    setComparing(true)

    try {
      const results: CompareData[] = []

      for (const courseId of Array.from(selected)) {
        const savedCourse = courses.find(c => c.course_id === courseId)
        const isStpm = savedCourse?.course_type === 'stpm'

        if (isStpm) {
          const detail = await getStpmCourseDetail(courseId, { token: token! })
          results.push({
            course_id: courseId,
            name: detail.course_name,
            level: 'Ijazah Sarjana Muda',
            field: detail.field_key ? getFieldName(detail.field_key) : detail.field,
            institution: detail.institution?.institution_name || detail.university,
            state: detail.institution?.state || '—',
            type: detail.institution?.type || '—',
            fees: '—',
            allowance: '—',
            merit: detail.merit_score ? String(detail.merit_score) : '—',
            requirements: formatStpmReqs(detail.requirements),
            semesters: '—',
            courseType: 'stpm',
          })
        } else {
          const { course, institutions, requirements, merit_cutoff } = await getCourse(courseId, { token: token! })
          const inst = institutions?.[0]
          results.push({
            course_id: courseId,
            name: course.course,
            level: course.level,
            field: course.field_key ? getFieldName(course.field_key) : course.field,
            institution: inst?.institution_name || '—',
            state: inst?.state || '—',
            type: inst?.type || '—',
            fees: inst?.tuition_fee_semester || '—',
            allowance: inst?.monthly_allowance ? `RM${inst.monthly_allowance}/bln` : '—',
            merit: merit_cutoff ? String(merit_cutoff) : '—',
            requirements: requirements ? formatSpmReqs(requirements) : ['—'],
            semesters: course.semesters ? String(course.semesters) : '—',
            courseType: 'spm',
          })
        }
      }

      setCompareData(results)
    } catch {
      showToast('Failed to load course details', 'error')
      setComparing(false)
    }
    setCompareLoading(false)
  }

  const detailHref = (course: SavedCourseWithStatus) =>
    course.course_type === 'stpm'
      ? `/stpm/${course.course_id}`
      : `/course/${course.course_id}`

  const rows: { label: string; key: keyof CompareData }[] = [
    { label: 'Institusi', key: 'institution' },
    { label: 'Negeri', key: 'state' },
    { label: 'Jenis', key: 'type' },
    { label: 'Tahap', key: 'level' },
    { label: 'Bidang', key: 'field' },
    { label: 'Semester', key: 'semesters' },
    { label: 'Yuran/sem', key: 'fees' },
    { label: 'Elaun', key: 'allowance' },
    { label: 'Merit', key: 'merit' },
  ]

  // Redirect to onboarding if guard resolves with no grades
  useEffect(() => {
    if (!guardLoading && !onboarded) {
      router.replace('/onboarding/exam-type')
    }
  }, [guardLoading, onboarded, router])

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8">
        {(loading || guardLoading) && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          </div>
        )}

        {!loading && !guardLoading && onboarded && !isAuthenticated && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">{t('saved.signInPrompt')}</p>
            <Link href="/login" className="btn-primary">{t('saved.signIn')}</Link>
          </div>
        )}

        {!loading && isAuthenticated && courses.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">{t('saved.empty')}</p>
            <Link href="/dashboard" className="btn-primary">{t('saved.browseCourses')}</Link>
          </div>
        )}

        {!loading && isAuthenticated && courses.length > 0 && !comparing && (
          <>
            {/* SPM / STPM tabs */}
            <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
              <button
                onClick={() => setActiveTab('SPM')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'SPM'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                SPM ({spmCount})
              </button>
              <button
                onClick={() => setActiveTab('STPM')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'STPM'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                STPM ({stpmCount})
              </button>
            </div>

            {/* Course list */}
            {filteredCourses.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-500">
                  {activeTab === 'STPM'
                    ? t('saved.noStpm')
                    : t('saved.noSpm')}
                </p>
              </div>
            ) : (
              <div className="grid gap-4">
                {filteredCourses.map(course => {
                  const isApplied = course.interest_status === 'applied' || course.interest_status === 'got_offer'
                  const hasOffer = course.interest_status === 'got_offer'
                  const isSelected = selected.has(course.course_id)

                  return (
                    <div
                      key={course.course_id}
                      className={`bg-white rounded-xl border p-5 transition-colors ${
                        isSelected ? 'border-primary-400 ring-1 ring-primary-200' : 'border-gray-200'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        {/* Desktop-only checkbox */}
                        <label
                          className="hidden md:flex items-center mr-3 mt-1 cursor-pointer"
                          title="Select to compare"
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelect(course.course_id)}
                            className="w-4 h-4 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                          />
                        </label>

                        <Link href={detailHref(course)} className="flex-1">
                          <h3 className="font-semibold text-gray-900">{course.course || course.course_id}</h3>
                          <p className="text-sm text-gray-500 mt-0.5">
                            {course.institution_name && (
                              <>{course.institution_name} &middot; </>
                            )}
                            {course.level} &middot; {getFieldName(course.field_key)}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5 font-mono">{course.course_id}</p>
                        </Link>
                        <button
                          onClick={() => handleRemove(course.course_id)}
                          className="ml-4 p-2 text-gray-400 hover:text-red-500 transition-colors"
                          aria-label={t('saved.remove')}
                        >
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>

                      {/* Status buttons */}
                      <div className="mt-3 flex gap-2">
                        <button
                          onClick={() => handleStatusUpdate(course.course_id, 'applied')}
                          disabled={updatingId === course.course_id}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors disabled:opacity-50 ${
                            isApplied
                              ? 'bg-primary-100 text-primary-700 border border-primary-300'
                              : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          {isApplied && (
                            <svg className="w-3.5 h-3.5 inline mr-1 -mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                          )}
                          {t('outcomes.iApplied')}
                        </button>
                        <button
                          onClick={() => handleStatusUpdate(course.course_id, 'got_offer')}
                          disabled={updatingId === course.course_id}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors disabled:opacity-50 ${
                            hasOffer
                              ? 'bg-green-100 text-green-700 border border-green-300'
                              : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          {hasOffer && (
                            <svg className="w-3.5 h-3.5 inline mr-1 -mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                          )}
                          {t('outcomes.iGotOffer')}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Floating compare bar — desktop only */}
            {selected.size >= 2 && (
              <div className="hidden md:block fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
                <div className="bg-gray-900 text-white rounded-full px-6 py-3 shadow-lg flex items-center gap-4">
                  <span className="text-sm">{selected.size} kursus dipilih</span>
                  <button
                    onClick={handleCompare}
                    className="bg-primary-500 hover:bg-primary-600 text-white px-5 py-1.5 rounded-full text-sm font-medium transition-colors"
                  >
                    Bandingkan
                  </button>
                  <button
                    onClick={() => setSelected(new Set())}
                    className="text-gray-400 hover:text-white text-sm"
                  >
                    Batal
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Compare view */}
        {comparing && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Perbandingan Kursus</h2>
              <button
                onClick={() => { setComparing(false); setSelected(new Set()) }}
                className="text-sm text-primary-600 hover:text-primary-800 font-medium"
              >
                Kembali ke senarai
              </button>
            </div>

            {compareLoading ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
                <p className="text-gray-500 mt-3">Memuatkan maklumat kursus...</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  {/* Course name header */}
                  <thead>
                    <tr>
                      <th className="text-left p-3 bg-gray-50 border border-gray-200 w-32 text-sm font-medium text-gray-500">
                        Kursus
                      </th>
                      {compareData.map(c => (
                        <th key={c.course_id} className="p-3 bg-primary-50 border border-gray-200 text-left min-w-[220px]">
                          <Link
                            href={c.courseType === 'stpm' ? `/stpm/${c.course_id}` : `/course/${c.course_id}`}
                            className="text-sm font-semibold text-primary-700 hover:underline block"
                          >
                            {c.name}
                          </Link>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(row => (
                      <tr key={row.key}>
                        <td className="p-3 bg-gray-50 border border-gray-200 text-sm font-medium text-gray-500">
                          {row.label}
                        </td>
                        {compareData.map(c => (
                          <td key={c.course_id} className="p-3 border border-gray-200 text-sm text-gray-900">
                            {String(c[row.key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {/* Requirements row (list) */}
                    <tr>
                      <td className="p-3 bg-gray-50 border border-gray-200 text-sm font-medium text-gray-500">
                        Syarat
                      </td>
                      {compareData.map(c => (
                        <td key={c.course_id} className="p-3 border border-gray-200 text-sm text-gray-900">
                          <ul className="list-disc list-inside space-y-0.5">
                            {c.requirements.map((r, i) => (
                              <li key={i} className="text-xs">{r}</li>
                            ))}
                          </ul>
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      <AppFooter />
    </main>
  )
}
