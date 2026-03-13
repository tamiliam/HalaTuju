/**
 * STPM CGPA calculator — mirrors backend stpm_engine.py STPM_CGPA_POINTS.
 */

const STPM_CGPA_POINTS: Record<string, number> = {
  'A': 4.00, 'A-': 3.67,
  'B+': 3.33, 'B': 3.00, 'B-': 2.67,
  'C+': 2.33, 'C': 2.00, 'C-': 1.67,
  'D+': 1.33, 'D': 1.00,
  'F': 0.00,
}

export function calculateStpmCgpa(grades: Record<string, string>): number {
  const entries = Object.values(grades).filter(g => g in STPM_CGPA_POINTS)
  if (entries.length === 0) return 0
  const total = entries.reduce((sum, g) => sum + STPM_CGPA_POINTS[g], 0)
  return Math.round((total / entries.length) * 100) / 100
}
