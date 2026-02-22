# Description Sprint Retrospective — Quality Audit + English Translations

**Date**: 2026-02-21
**Duration**: 3 sessions (first hit context limit, second completed code + commit, third deployed after crash)

## What Was Built

- Full quality audit of all 383 course descriptions across 6 institution types
- 33 quality fixes (tone, typos, thin content)
- English translations (`headline_en` + `synopsis_en`) for all 383 entries
- Updated fallback function with English defaults

## What Went Well

- **Parallel agents for translation**: Launching 5 agents simultaneously to translate each section (Polytechnic, KKOM, TVET, University, PISMP) cut translation time significantly. All 5 produced valid JSON translation files.
- **Merger script approach**: Writing a line-by-line Python merger script to inject translations avoided concurrent file edit conflicts. The script ran cleanly on first attempt — 299 entries injected, valid Python syntax confirmed.
- **AST verification**: Using Python's `ast.parse` to verify every course entry had both `headline_en` and `synopsis_en` gave high confidence in completeness.
- **Quality audit was thorough**: Checking all 383 descriptions for tone (anda vs mereka), typos, thin content, and suitability found real issues — 33 fixes across all sections.

## What Went Wrong

- **Context exhaustion in first session**: The audit + fix + translation pipeline was too much for one session. The first session crashed while 5 background translation agents were running, losing all their work.
- **Orphaned background agent**: An agent from the previous session (a67b14a) continued running in the new session, directly editing description.py while new agents were also running. Could have caused file conflicts. Had to manually stop it.
- **Initial grep count was wrong**: First grep for `headline_en` returned "9" when there were actually 22 entries — caused confusion about progress. Lesson: use precise regex patterns with quotes, not bare strings.
- **Session crashed before deploying**: The second session committed the code (4c43ecc) but crashed before deploying. A third session was needed to fake-apply Django migrations 0006 + 0007, redeploy backend (rev 20) and frontend (rev 15).

## Design Decisions

1. **`headline_en` + `synopsis_en` as dict fields (not separate file)**: Keeping translations co-located with the Malay originals makes maintenance easier — when you edit a description, you see both languages side by side.
2. **JSON translation files as intermediate step**: Rather than having agents edit the Python file directly (risking concurrent writes), agents produced JSON files that a merger script processed sequentially.
3. **Line-by-line merger vs regex replacement**: The merger script processes the file line-by-line instead of using regex on the full file content. This is more robust for edge cases (escaped characters, multiline strings, pathway fields).
4. **British English for all translations**: Consistent with the project's existing i18n approach and user preference.

## Numbers

| Metric | Value |
|--------|-------|
| Descriptions audited | 383 |
| Quality fixes | 33 |
| Entries translated | 383 (100%) |
| File growth | ~2,400 → ~3,090 lines (+690) |
| Translation agents | 5 parallel |
| Commits | 3 (quality fixes, translations, CLAUDE.md update) |
| Tests | 156 (unchanged) |
| Golden master | 8280 (unchanged) |
| Backend deploy | rev 20 |
| Frontend deploy | rev 15 |
