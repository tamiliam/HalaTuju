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
  type CourseRequirements,
  type StpmRequirements,
} from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { useToast } from '@/components/ToastContext'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'
import { useFieldTaxonomy } from '@/hooks/useFieldTaxonomy'
import { useOnboardingGuard } from '@/lib/useOnboardingGuard'
import SavedCourseCard from '@/components/saved/SavedCourseCard'
import SavedCompareView, { CompareBar, type CompareData } from '@/components/saved/SavedCompare'
// Mobile M3: the compare words (the `discovery` slice), loaded by this PAGE.
import '@/lib/messagesDiscovery'

type QualificationTab = 'SPM' | 'STPM'

export default function SavedPage() {
  const { t, locale } = useT()
  const router = useRouter()
  const { getFieldName } = useFieldTaxonomy(locale)
  const { ready: onboarded, loading: guardLoading, needsNric } = useOnboardingGuard()
  const { token, isAuthenticated, isLoading: authLoading, showAuthGate } = useAuth()
  const { showToast } = useToast()
  const [courses, setCourses] = useState<SavedCourseWithStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<QualificationTab>('SPM')
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  // Compare state — phones too since Mobile M3 (layout B, `components/saved/SavedCompare.tsx`)
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
        showToast(t('discovery.maxThree'), 'error')
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
    if (reqs.req_interview) items.push(t('discovery.reqInterview'))
    if (reqs.no_colorblind) items.push(t('discovery.reqNoColourBlind'))
    return items.length > 0 ? items : ['—']
  }

  const handleCompare = async () => {
    if (selected.size < 2) {
      showToast(t('discovery.minTwo'), 'error')
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
            allowance: inst?.monthly_allowance ? t('discovery.perMonth', { amount: String(inst.monthly_allowance) }) : '—',
            merit: merit_cutoff ? String(merit_cutoff) : '—',
            requirements: requirements ? formatSpmReqs(requirements) : ['—'],
            semesters: course.semesters ? String(course.semesters) : '—',
            courseType: 'spm',
          })
        }
      }

      setCompareData(results)
    } catch {
      showToast(t('discovery.loadFailed'), 'error')
      setComparing(false)
    }
    setCompareLoading(false)
  }

  const detailHref = (course: SavedCourseWithStatus) =>
    course.course_type === 'stpm'
      ? `/stpm/${course.course_id}`
      : `/course/${course.course_id}`


  // Redirect to onboarding if guard resolves with no grades
  useEffect(() => {
    if (guardLoading) return
    if (needsNric) {
      showAuthGate('profile')
    } else if (!onboarded) {
      router.replace('/onboarding/exam-type')
    }
  }, [guardLoading, onboarded, needsNric, showAuthGate, router])

  return (
    <main className="min-h-screen bg-ground-50">
      <AppHeader />

      <div className="container mx-auto px-4 py-6 sm:px-6 md:py-8">
        {(loading || guardLoading) && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-brand-shape border-t-transparent" />
          </div>
        )}

        {!loading && !guardLoading && onboarded && !isAuthenticated && (
          <div className="text-center py-12">
            <p className="text-ground-600 mb-4">{t('saved.signInPrompt')}</p>
            <Link href="/login" className="btn-primary">{t('saved.signIn')}</Link>
          </div>
        )}

        {!loading && isAuthenticated && courses.length === 0 && (
          <div className="text-center py-12">
            <p className="text-ground-600 mb-4">{t('saved.empty')}</p>
            <Link href="/dashboard" className="btn-primary">{t('saved.browseCourses')}</Link>
          </div>
        )}

        {!loading && isAuthenticated && courses.length > 0 && !comparing && (
          <>
            <h1 className="mb-4 text-2xl font-bold text-ground-900">{t('saved.title')}</h1>
            {/* SPM / STPM tabs */}
            <div className="flex gap-1 mb-6 bg-ground-100 rounded-lg p-1 w-fit">
              <button
                onClick={() => setActiveTab('SPM')}
                className={`min-h-11 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'SPM'
                    ? 'bg-ground-0 text-ground-900 shadow-sm'
                    : 'text-ground-500 hover:text-ground-700'
                }`}
              >
                SPM ({spmCount})
              </button>
              <button
                onClick={() => setActiveTab('STPM')}
                className={`min-h-11 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'STPM'
                    ? 'bg-ground-0 text-ground-900 shadow-sm'
                    : 'text-ground-500 hover:text-ground-700'
                }`}
              >
                STPM ({stpmCount})
              </button>
            </div>

            {/* Course list */}
            {filteredCourses.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-ground-500">
                  {activeTab === 'STPM'
                    ? t('saved.noStpm')
                    : t('saved.noSpm')}
                </p>
              </div>
            ) : (
              <>
                {filteredCourses.length > 1 && (
                  <p className="mb-3 text-sm text-ground-500">{t('discovery.compareHint')}</p>
                )}
                <div className="grid gap-4">
                  {filteredCourses.map(course => (
                    <SavedCourseCard
                      key={course.course_id}
                      course={course}
                      subtitle={[course.institution_name, course.level, getFieldName(course.field_key)]
                        .filter(Boolean).join(' · ')}
                      href={detailHref(course)}
                      selected={selected.has(course.course_id)}
                      updating={updatingId === course.course_id}
                      onToggleSelect={() => toggleSelect(course.course_id)}
                      onRemove={() => handleRemove(course.course_id)}
                      onStatus={(status) => handleStatusUpdate(course.course_id, status)}
                    />
                  ))}
                </div>
              </>
            )}

            <CompareBar count={selected.size} onCancel={() => setSelected(new Set())} onCompare={handleCompare} />
          </>
        )}

        {/* Compare view */}
        {comparing && (
          <SavedCompareView
            data={compareData}
            loading={compareLoading}
            onBack={() => { setComparing(false); setSelected(new Set()) }}
          />
        )}
      </div>

      <AppFooter />
    </main>
  )
}
