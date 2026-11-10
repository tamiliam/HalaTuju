/**
 * Pure logic for the Officer Review Cockpit (Sprint 5).
 *
 * All helpers are side-effect-free so they can be unit-tested in a plain
 * node env (no jsdom). The cockpit component consumes these; it never
 * re-implements them.
 *
 * ⚠ THIS FILE IS A RE-EXPORT BARREL (audit A3.3). It was 1,633 lines; it is now split by concern
 * into the five modules below, with no change to any line of logic. Importers keep using
 * `@/lib/officerCockpit`; new code may import the module it needs directly.
 */
export * from './cockpitVerdict'
export * from './cockpitDocFacts'
export * from './cockpitIncome'
export * from './cockpitStages'
export * from './cockpitTrail'
