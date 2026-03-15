'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useAuth } from '@/lib/auth-context'
import { getSavedCourses, saveCourse, unsaveCourse } from '@/lib/api'
import { useToast } from '@/components/Toast'

const RESUME_ACTION_KEY = 'halatuju_resume_action'

/**
 * Shared hook for saved course state across all pages.
 * Handles: loading saved IDs, optimistic toggle, auth gating, resume after login, toast feedback.
 */
export function useSavedCourses() {
  const { token, isAuthenticated, showAuthGate } = useAuth()
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())
  const { showToast } = useToast()
  const resumeHandledRef = useRef(false)

  // Load saved course IDs when token becomes available
  useEffect(() => {
    if (!token) return
    getSavedCourses({ token })
      .then(({ saved_courses }) => {
        setSavedIds(new Set(saved_courses.map(c => c.course_id)))
      })
      .catch(() => {})
  }, [token])

  // Resume save action after auth completion (from auth gate → Google OAuth redirect)
  useEffect(() => {
    if (!token || resumeHandledRef.current) return
    const resumeStr = localStorage.getItem(RESUME_ACTION_KEY)
    if (!resumeStr) return
    localStorage.removeItem(RESUME_ACTION_KEY)
    resumeHandledRef.current = true

    try {
      const { action, courseId } = JSON.parse(resumeStr)
      if (action === 'save' && courseId) {
        setSavedIds(prev => { const n = new Set(prev); n.add(courseId); return n })
        saveCourse(courseId, { token }).catch(() => {
          setSavedIds(prev => { const n = new Set(prev); n.delete(courseId); return n })
          showToast('Failed to save course', 'error')
        })
      }
    } catch {
      // Ignore malformed resume action
    }
  }, [token, showToast])

  const toggleSave = useCallback(async (courseId: string) => {
    if (!token) return
    const wasSaved = savedIds.has(courseId)

    // Optimistic update
    setSavedIds(prev => {
      const next = new Set(prev)
      if (wasSaved) next.delete(courseId)
      else next.add(courseId)
      return next
    })

    try {
      if (wasSaved) {
        await unsaveCourse(courseId, { token })
        showToast('Course removed from saved', 'success')
      } else {
        await saveCourse(courseId, { token })
        showToast('Course saved', 'success')
      }
    } catch {
      // Revert on failure
      setSavedIds(prev => {
        const next = new Set(prev)
        if (wasSaved) next.add(courseId)
        else next.delete(courseId)
        return next
      })
      showToast('Failed to update saved courses', 'error')
    }
  }, [token, savedIds, showToast])

  // Auth-gated toggle: shows auth gate if not logged in, otherwise toggles
  const toggleSaveOrGate = useCallback((courseId: string) => {
    if (!isAuthenticated) {
      showAuthGate('save', { courseId })
      return
    }
    toggleSave(courseId)
  }, [isAuthenticated, showAuthGate, toggleSave])

  return { savedIds, toggleSave: toggleSaveOrGate }
}
