/**
 * The field taxonomy, and the stateless public calculators — merit, CGPA, pathways.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'

// ── Field Taxonomy types ──────────────────────────────────────────────

export interface FieldTaxonomyEntry {
  key: string
  name_en: string
  name_ms: string
  name_ta: string
  image_slug: string
  parent_key: string | null
  sort_order: number
  children: FieldTaxonomyEntry[]
}

export async function fetchFieldTaxonomy(
  options?: ApiOptions
): Promise<{ groups: FieldTaxonomyEntry[] }> {
  return apiRequest('/api/v1/fields/', options)
}

// ── Calculation types ──────────────────────────────────────────────────

export interface MeritResult {
  academic_merit: number
  final_merit: number
}

export interface CgpaResult {
  cgpa: number
  academic_cgpa: number
  merit_percent: number
}

export interface PathwayResult {
  pathway: 'matric' | 'stpm'
  trackId: string
  trackName: string
  trackNameMs: string
  trackNameTa: string
  eligible: boolean
  merit: number | null
  mataGred: number | null
  maxMataGred: number | null
  fitScore: number
  reason: string | null
}

// ── Calculation API functions (stateless, public) ──────────────────────

export async function calculateMerit(
  grades: Record<string, string>,
  coqScore: number,
  streamSubjects?: string[],
  options?: ApiOptions
): Promise<MeritResult> {
  return apiRequest('/api/v1/calculate/merit/', {
    method: 'POST',
    body: JSON.stringify({
      grades, coq_score: coqScore,
      // TD-063: omit when empty so the backend falls back to the heuristic.
      ...(streamSubjects && streamSubjects.length ? { stream_subjects: streamSubjects } : {}),
    }),
    ...options,
  })
}

export async function calculateCgpa(
  stpmGrades: Record<string, string>,
  kokoScore: number = 0,
  options?: ApiOptions
): Promise<CgpaResult> {
  return apiRequest('/api/v1/calculate/cgpa/', {
    method: 'POST',
    body: JSON.stringify({ stpm_grades: stpmGrades, koko_score: kokoScore }),
    ...options,
  })
}

export async function calculatePathways(
  grades: Record<string, string>,
  coqScore: number,
  signals?: Record<string, Record<string, number>> | null,
  options?: ApiOptions
): Promise<{ pathways: PathwayResult[] }> {
  const raw = await apiRequest<{ pathways: Array<Record<string, unknown>> }>('/api/v1/calculate/pathways/', {
    method: 'POST',
    body: JSON.stringify({ grades, coq_score: coqScore, signals: signals || undefined }),
    ...options,
  })
  // Map snake_case backend keys to camelCase frontend keys
  const pathways: PathwayResult[] = raw.pathways.map(p => ({
    pathway: p.pathway as 'matric' | 'stpm',
    trackId: p.track_id as string,
    trackName: p.track_name as string,
    trackNameMs: p.track_name_ms as string,
    trackNameTa: p.track_name_ta as string,
    eligible: p.eligible as boolean,
    merit: (p.merit as number) ?? null,
    mataGred: (p.mata_gred as number) ?? null,
    maxMataGred: (p.max_mata_gred as number) ?? null,
    fitScore: (p.fit_score as number) ?? 0,
    reason: (p.reason as string) ?? null,
  }))
  return { pathways }
}

