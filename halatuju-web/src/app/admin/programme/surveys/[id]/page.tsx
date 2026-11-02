'use client'

import { useParams } from 'next/navigation'
import { lazySource } from '@/components/source/LazySource'
import { useProgrammeScope } from '@/lib/programmeScopeCore'

/**
 * One survey's **Results** (student maintenance S9; the SurveyResults board): the summary per question, each
 * scholar's answers, who has not answered, the reminder and the CSV. Staff only — the server's fence
 * (another organisation's survey is 404).
 *
 * ⚠ ITS OWN CHUNK (`lazySource`), like the Surveys list: the route carries only this loader.
 */
const SurveyResults = lazySource(() => import('@/components/surveys/SurveyResults').then((m) => m.default))

export default function SurveyResultsPage() {
  const params = useParams()
  // The chosen gift, read from the light context leaf (`programmeScopeCore`), not the provider module: with
  // `programmeScope` on this page webpack regrouped shared chunks and every student route grew ~1 kB (S9).
  const programme = useProgrammeScope().chosen || undefined
  return <SurveyResults id={Number(params?.id)} programme={programme} />
}
