/**
 * Client-side UPU merit calculator.
 *
 * UPU Formula (from official reference):
 *   Subjek Wajib (40%):    4 core (BM, BI, MAT, SEJ), max 72 pts
 *   Subjek Pilihan (30%):  2 stream subjects, max 36 pts
 *   Subjek Tambahan (10%): 2 elective subjects, max 36 pts
 *   Ko-kurikulum (10%):    0–10 marks
 *
 *   weighted = (core/72 × 40) + (stream/36 × 30) + (elective/36 × 10)
 *   academic = weighted × (9/8)   [same as (weighted/80) × 90, cap 90]
 *   final    = academic + CoQ     [cap 100]
 *
 * MUST stay in sync with halatuju_api/apps/courses/engine.py
 */

// 18-point scale (same as engine.py MERIT_GRADE_POINTS)
const MERIT_GRADE_POINTS: Record<string, number> = {
  'A+': 18, 'A': 16, 'A-': 14,
  'B+': 12, 'B': 10, 'C+': 8, 'C': 6,
  'D': 4, 'E': 2, 'G': 0,
}

function getPoints(grades: string[]): number {
  return grades.reduce((sum, g) => sum + (MERIT_GRADE_POINTS[g] || 0), 0)
}

/**
 * Calculate merit score using UPU formula.
 *
 * @param coreGrades     grades for 4 core subjects (BM, BI, MAT, SEJ)
 * @param streamGrades   grades for 2 stream subjects
 * @param electiveGrades grades for 0-2 elective subjects
 * @param coqScore       co-curricular score (0-10)
 */
export function calculateMeritScore(
  coreGrades: string[],
  streamGrades: string[],
  electiveGrades: string[],
  coqScore: number
): { academicMerit: number; finalMerit: number } {
  const corePoints = getPoints(coreGrades)
  const streamPoints = getPoints(streamGrades)
  const electivePoints = getPoints(electiveGrades)

  // UPU weighted sections (max 80)
  const weighted =
    (corePoints / 72) * 40 +
    (streamPoints / 36) * 30 +
    (electivePoints / 36) * 10

  // Scale to 90: (weighted / 80) × 90 = weighted × 9/8
  let academicMerit = weighted * (9 / 8)
  academicMerit = Math.min(academicMerit, 90.0)

  const coq = Math.min(Math.max(coqScore, 0), 10.0)
  const finalMerit = Math.min(academicMerit + coq, 100.0)

  return {
    academicMerit: Math.round(academicMerit * 100) / 100,
    finalMerit: Math.round(finalMerit * 100) / 100,
  }
}
