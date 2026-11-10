'use client'

import '@/lib/messagesScholarship'   // TD-416: this page's scholarship.* words (their own slice)
import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import CourseInterestsSection from '@/components/profile/LazyCourseInterestsSection'   // own chunk (JS budget)
import AppHeader from '@/components/AppHeader'
import { useToast } from '@/components/ToastContext'
import { useOnboardingGuard } from '@/lib/useOnboardingGuard'
import { PHONE_GUTTER } from '@/lib/phoneSection'
import { useProfileForm } from './useProfileForm'
import { useProfileEditor } from './useProfileEditor'
import { useProfileEditors } from './useProfileEditors'
import IdentitySection from './sections/IdentitySection'
import ContactDetailsSection from './sections/ContactDetailsSection'
import LocationSection from './sections/LocationSection'
import FamilySection from './sections/FamilySection'
import ApplicationSection from './sections/ApplicationSection'

/**
 * /profile: the student's own record, five sections and her course interests. A3.9 split the
 * old 1,274-line page: state and load in `useProfileForm`, section/save logic in
 * `useProfileEditor`, each section in `sections/`, the edit panels in `sections/edit/` (one
 * lazily fetched chunk, see `useProfileEditors`). Behaviour and look are unchanged.
 */
export default function ProfilePage() {
  const router = useRouter()
  const { t } = useT()
  const { ready: onboarded, loading: guardLoading, needsNric } = useOnboardingGuard()
  const { token, isAuthenticated, isLoading: authLoading, showAuthGate } = useAuth()
  const { showToast } = useToast()
  const f = useProfileForm()
  const ed = useProfileEditor(f)
  const { editors, failed, retry } = useProfileEditors()
  const { loading, loadData, savedCourses, setSavedCourses } = f
  const { nextUrl, editingSection, cancelEditing } = ed

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      showAuthGate('profile')
      return
    }
    if (token) loadData()
  }, [token, authLoading, isAuthenticated, showAuthGate, loadData])

  // The edit panels could not be fetched. The first Edit tap after a failure retries the import once;
  // if that fails too, say so (once) and close the section rather than leave it stuck.
  const retried = useRef(false)
  useEffect(() => {
    if (!editingSection) { retried.current = false; return }
    if (editors || !failed) return
    if (!retried.current) { retried.current = true; retry(); return }
    cancelEditing()
    showToast(t('errors.unexpectedError'), 'error')
  }, [editors, failed, editingSection, retry, cancelEditing, showToast, t])

  // Redirect to onboarding if guard resolves with no grades
  useEffect(() => {
    if (guardLoading) return
    if (needsNric) {
      showAuthGate('profile')
    } else if (!onboarded) {
      router.replace('/onboarding/exam-type')
    }
  }, [guardLoading, onboarded, needsNric, showAuthGate, router])

  if (authLoading || loading || guardLoading) {
    return (
      <>
        <AppHeader />
        <main className="min-h-screen bg-ground-50 flex items-center justify-center">
          <p className="text-ground-500">{t('common.loading')}</p>
        </main>
      </>
    )
  }

  return (
    <>
      <AppHeader />
      <main className="min-h-screen bg-ground-50">
        <div className={`container mx-auto ${PHONE_GUTTER} py-4 md:py-10 max-w-2xl`}>
          {nextUrl && (
            <Link href={nextUrl} className="inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:underline mb-4">
              ← {t('scholarship.apply.backToApplication')}
            </Link>
          )}
          {/* Page title */}
          <div className="md:mb-8">
            <h1 className="text-2xl font-bold text-ground-900 mb-1">
              {t('profile.title')}
            </h1>
            <p className="text-ground-500">
              {t('profile.subtitle')}
            </p>
          </div>

          <IdentitySection f={f} ed={ed} Edit={editors?.IdentityEdit} />
          <ContactDetailsSection f={f} ed={ed} Edit={editors?.ContactDetailsEdit} />
          <LocationSection f={f} ed={ed} Edit={editors?.LocationEdit} />
          <FamilySection f={f} ed={ed} Edit={editors?.FamilyEdit} />
          <ApplicationSection f={f} ed={ed} Edit={editors?.ApplicationEdit} />

          {/* My Course Interests */}
          <CourseInterestsSection savedCourses={savedCourses} setSavedCourses={setSavedCourses} token={token} />
        </div>
      </main>
    </>
  )
}
