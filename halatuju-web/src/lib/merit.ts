/**
 * Client-side merit calculator — port of engine.py calculate_merit_score()
 * and prepare_merit_inputs().
 *
 * MUST stay in sync with halatuju_api/apps/courses/engine.py
 */

// 18-point scale (same as engine.py MERIT_GRADE_POINTS)
const MERIT_GRADE_POINTS: Record<string, number> = {
  'A+': 18, 'A': 16, 'A-': 14,
  'B+': 12, 'B': 10, 'C+': 8, 'C': 6,
  'D': 4, 'E': 2, 'G': 0,
}

// Frontend subject IDs → engine internal keys (same as serializer GRADE_KEY_MAP)
const FRONTEND_TO_ENGINE: Record<string, string> = {
  'BM': 'bm', 'BI': 'eng', 'SEJ': 'hist', 'MAT': 'math',
  'PHY': 'phy', 'CHE': 'chem', 'BIO': 'bio', 'AMT': 'addmath',
  'PI': 'islam', 'PM': 'moral', 'SN': 'sci',
  'ECO': 'ekonomi', 'ACC': 'poa', 'BUS': 'business', 'GEO': 'geo',
}

function getPoints(grades: string[]): number {
  return grades.reduce((sum, g) => sum + (MERIT_GRADE_POINTS[g] || 0), 0)
}

/**
 * Map frontend grade keys to engine keys.
 */
function mapGrades(grades: Record<string, string>): Record<string, string> {
  const mapped: Record<string, string> = {}
  for (const [key, grade] of Object.entries(grades)) {
    const engineKey = FRONTEND_TO_ENGINE[key] || key.toLowerCase()
    mapped[engineKey] = grade
  }
  return mapped
}

/**
 * Split grades into Section 1 (5), Section 2 (3), Section 3 (history).
 * Port of engine.py prepare_merit_inputs().
 */
export function prepareMeritInputs(
  frontendGrades: Record<string, string>
): { sec1: string[]; sec2: string[]; sec3: string[] } {
  const grades = mapGrades(frontendGrades)

  const hasPhy = 'phy' in grades
  const hasChem = 'chem' in grades
  const isScience = hasPhy && hasChem

  const getG = (s: string) => grades[s] || 'G'

  // Section 3: History (critical for UPU)
  const sec3 = [getG('hist')]

  // Section 1: 5 critical subjects
  const sec1Keys: string[] = []
  if (isScience) {
    for (const k of ['math', 'addmath', 'phy', 'chem', 'bio']) {
      if (k in grades) sec1Keys.push(k)
    }
  } else {
    for (const k of ['bm', 'math', 'sci']) {
      if (k in grades) sec1Keys.push(k)
    }
  }

  // Fill Sec1 to 5 with best remaining (exclude low grades from padding)
  const used = new Set(['hist', ...sec1Keys])
  const remaining = Object.keys(grades)
    .filter(k => !used.has(k) && !['G', 'E', 'D', 'C+'].includes(grades[k]))
    .sort((a, b) => (MERIT_GRADE_POINTS[grades[b]] || 0) - (MERIT_GRADE_POINTS[grades[a]] || 0))

  while (sec1Keys.length < 5 && remaining.length > 0) {
    sec1Keys.push(remaining.shift()!)
  }

  const sec1 = sec1Keys.map(k => grades[k] || 'G')

  // Section 2: next 3 best
  const sec2Keys: string[] = []
  while (sec2Keys.length < 3 && remaining.length > 0) {
    sec2Keys.push(remaining.shift()!)
  }
  const sec2 = sec2Keys.map(k => grades[k] || 'G')

  return { sec1, sec2, sec3 }
}

/**
 * Calculate merit score. Port of engine.py calculate_merit_score().
 * Formula: academic = ((S1*5/9)+(S2*5/6)+(S3*5/18))*(9/8), cap 90
 * Final = academic + CoQ (0-10)
 */
export function calculateMeritScore(
  sec1: string[],
  sec2: string[],
  sec3: string[],
  coqScore: number
): { academicMerit: number; finalMerit: number } {
  const p1 = getPoints(sec1)
  const p2 = getPoints(sec2)
  const p3 = getPoints(sec3)

  let academicMerit = ((p1 * 5 / 9) + (p2 * 5 / 6) + (p3 * 5 / 18)) * (9 / 8)
  academicMerit = Math.min(academicMerit, 90.0)

  const coq = Math.min(Math.max(coqScore, 0), 10.0)
  const finalMerit = academicMerit + coq

  return {
    academicMerit: Math.round(academicMerit * 100) / 100,
    finalMerit: Math.round(finalMerit * 100) / 100,
  }
}

/**
 * Convenience: compute merit from raw frontend grades + CoQ.
 */
export function computeMerit(
  frontendGrades: Record<string, string>,
  coqScore: number
): { academicMerit: number; finalMerit: number } {
  const { sec1, sec2, sec3 } = prepareMeritInputs(frontendGrades)
  return calculateMeritScore(sec1, sec2, sec3, coqScore)
}
