# Code health

Readings taken by `Settings/_tools/code_health.py`; decisions recorded per
`Settings/_workflows/code-health-audit.md`. The tool writes **Trend** and **Latest run**; people
write **Reviews**. A WARN is an absolute threshold crossed (the triage list). A FAIL is a reading
that got WORSE than the last run by more than a tolerance — the only thing that blocks a close.

Run: `python Settings/_tools/code_health.py --project . --write` (add `--full` at sprint close).

**The arc that produced these readings is CLOSED.** `docs/plans/2026-09-18-code-health-roadmap.md`
— nineteen sprints in six phases, **all shipped, H1 to H19**, 2026-09-18 to 2026-09-20. Its closing
retrospective (what moved, what was promised and missed, what is enforced and by what, what is
still open and whose it is) is the last section of that file. The development freeze was lifted at
the H10 checkpoint on 2026-09-19.

**What that means for a reading you are about to take.** Twelve standards are now tests inside the
Cloud Build deploy gate, ratcheting one way only — the two `code-standards.json` files hold the
numbers, and `halatuju_api/CLAUDE.md` `## Code standards` says what each one is for and how to move
a ledger key when a file moves. **This document is no longer a project being worked on; it is the
instrument the project is read with.** A WARN here is a triage item, not a task — six of them are
standing and decided, and the decision is in the newest `## Reviews` entry that names them. Three
of the arc's targets are NOT enforced by any ledger and can only be watched here: `fix%` (target
under 30, reads 42), `big` (target 12, reads 17) and `guard%` (target 12, reads 20 and rose because
drift tests are counted as the habit they cure). See TD-284.

## Trend
| date | sha | days | fix% | hot#1 | big | long | dup | xapp | supp | skip | mirror | guard% | td_open | unused | tsc | i18n | std |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-30 | b9028b4 | 90 | 51 | vision.py 28.1 | 16 | 15 | 4 | 73 | 93 | 0 | 3 | 12 | 144 | 0 | 0 | ok | ok |
| 2026-10-30 | 5ce4ee6 | 90 | 51 | vision.py 28.1 | 16 | 15 | 4 | 73 | 93 | 0 | 3 | 12 | 142 | 0 | 0 | ok | ok |
| 2026-10-29 | e6a03fb | 90 | 52 | vision.py 28.1 | 16 | 15 | 4 | 73 | 93 | 0 | 3 | 12 | 142 | 0 | 0 | ok | ok |
| 2026-10-29 | 860792b | 90 | 52 | vision.py 28.1 | 16 | 15 | 4 | 73 | 93 | 0 | 3 | 12 | 142 | 0 | 0 | ok | ok |
| 2026-10-29 | 71ae8cc | 90 | 52 | vision.py 28.1 | 16 | 15 | 4 | 73 | 93 | 0 | 3 | 11 | 143 | 0 | 0 | ok | ok |
| 2026-10-29 | f528264 | 90 | 52 | vision.py 28.1 | 16 | 15 | 4 | 73 | 93 | 0 | 3 | 11 | 140 | 0 | 0 | ok | ok |
| 2026-10-29 | f856d20 | 90 | 52 | vision.py 28.1 | 16 | 15 | 4 | 72 | 93 | 0 | 3 | 12 | 137 | 0 | 0 | ok | ok |
| 2026-10-28 | 6e1d66d | 90 | 52 | vision.py 28.1 | 17 | 15 | 4 | 72 | 92 | 0 | 3 | 12 | 136 | 0 | - | - | ok |
| 2026-10-28 | 00f1f7e | 90 | 53 | officerCockpit.ts 26.5 | 17 | 15 | 4 | 67 | 92 | 0 | 3 | 12 | 131 | 0 | 0 | ok | ok |
| 2026-10-27 | ddb26b6 | 90 | 53 | officerCockpit.ts 28.2 | 17 | 15 | 4 | 67 | 94 | 0 | 3 | 12 | 130 | 0 | 0 | ok | ok |
| 2026-10-27 | e3da157 | 90 | 52 | officerCockpit.ts 28.2 | 17 | 15 | 4 | 67 | 94 | 0 | 3 | 12 | 130 | 0 | 0 | ok | ok |
| 2026-10-26 | 4e6e0ec | 90 | 52 | officerCockpit.ts 26.5 | 17 | 15 | 4 | 64 | 135 | 0 | 3 | 12 | 131 | 0 | 0 | ok | ok |
| 2026-10-26 | c7871ee | 90 | 51 | officerCockpit.ts 26.5 | 17 | 15 | 4 | 64 | 135 | 0 | 3 | 12 | 130 | 0 | 0 | ok | ok |
| 2026-10-26 | a781b49 | 90 | 51 | views.py 24.4 | 17 | 15 | 4 | 64 | 135 | 0 | 3 | 12 | 131 | 0 | 0 | ok | ok |
| 2026-10-25 | ca5dc8b | 90 | 51 | views.py 26.8 | 17 | 15 | 4 | 52 | 135 | 0 | 3 | 13 | 130 | 0 | 0 | ok | ok |
| 2026-10-25 | 46b1c0b | 90 | 51 | views.py 26.8 | 17 | 15 | 4 | 51 | 135 | 0 | 3 | 13 | 129 | 0 | 0 | ok | ok |
| 2026-10-25 | 9d3ff53 | 90 | 50 | views.py 26.8 | 17 | 15 | 4 | 51 | 135 | 0 | 3 | 13 | 127 | 0 | 0 | ok | ok |
| 2026-10-18 | 65af261 | 90 | 46 | officerCockpit.ts 28.1 | 17 | 15 | 4 | 50 | 135 | 0 | 3 | 13 | 123 | 0 | - | - | ok |
| 2026-10-09 | ffa0983 | 90 | 45 | views.py 31.7 | 17 | 15 | 4 | 44 | 135 | 0 | 3 | 13 | 120 | 0 | 0 | ok | ok |
| 2026-10-07 | 5fd333e | 90 | 45 | views.py 31.6 | 17 | 15 | 4 | 43 | 135 | 0 | 3 | 13 | 118 | 0 | 0 | ok | ok |
| 2026-10-06 | a3aef00 | 90 | 45 | views.py 31.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 13 | 116 | 0 | - | - | ok |
| 2026-10-06 | 48fda4b | 90 | 45 | views.py 31.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 13 | 116 | 0 | 0 | ok | ok |
| 2026-10-06 | 161f11e | 90 | 43 | views.py 31.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 13 | 112 | 0 | 0 | ok | ok |
| 2026-10-06 | 538c82f | 90 | 43 | views.py 31.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 12 | 105 | 0 | 0 | ok | ok |
| 2026-10-05 | 7ab5d43 | 90 | 44 | officerCockpit.ts 33 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 12 | 100 | 0 | 0 | ok | ok |
| 2026-10-05 | 5d285ae | 90 | 44 | officerCockpit.ts 33 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 13 | 99 | 0 | - | - | ok |
| 2026-10-05 | 0e9f7ee | 90 | 43 | officerCockpit.ts 34.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 13 | 90 | 0 | - | - | ok |
| 2026-10-05 | 315c71a | 90 | 43 | officerCockpit.ts 34.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 13 | 92 | 0 | - | - | ok |
| 2026-10-04 | 09b6c62 | 90 | 43 | officerCockpit.ts 34.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 14 | 98 | 0 | - | - | ok |
| 2026-10-04 | d5fe223 | 90 | 43 | officerCockpit.ts 34.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 20 | 108 | 0 | - | - | ok |
| 2026-10-04 | 2269a51 | 90 | 43 | officerCockpit.ts 36.3 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 20 | 119 | 0 | - | - | ok |
| 2026-10-03 | d683e2d | 90 | 44 | officerCockpit.ts 38 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 20 | 119 | 0 | - | - | ok |
| 2026-10-03 | 699df64 | 90 | 44 | officerCockpit.ts 36.2 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 19 | 128 | 0 | - | - | ok |
| 2026-10-03 | 1a9ccf0 | 90 | 44 | vision.py 36.6 | 17 | 15 | 4 | 48 | 135 | 0 | 3 | 19 | 132 | 0 | - | - | ok |
| 2026-10-03 | 03d9f1f | 90 | 44 | vision.py 38.8 | 17 | 15 | 4 | 48 | 139 | 0 | 3 | 19 | 131 | 0 | - | - | ok |
| 2026-10-02 | c5408ab | 90 | 44 | officerCockpit.ts 46.1 | 17 | 15 | 4 | 48 | 139 | 0 | 3 | 20 | 130 | 0 | - | - | ok |
| 2026-10-02 | 7bc9ac4 | 90 | 44 | officerCockpit.ts 46.1 | 17 | 15 | 4 | 48 | 139 | 0 | 3 | 20 | 130 | 0 | - | - | ok |
| 2026-10-02 | c993050 | 90 | 44 | officerCockpit.ts 47.8 | 17 | 15 | 4 | 48 | 139 | 0 | 3 | 20 | 130 | 0 | - | - | ok |
| 2026-10-02 | 3703cdb | 90 | 44 | officerCockpit.ts 47.8 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 130 | 0 | - | - | ok |
| 2026-10-02 | b13fc89 | 90 | 44 | officerCockpit.ts 47.8 | 18 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 131 | 0 | - | - | ok |
| 2026-10-01 | ee52eb1 | 90 | 44 | officerCockpit.ts 46.1 | 18 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 132 | 0 | - | - | ok |
| 2026-10-01 | 849245c | 90 | 44 | officerCockpit.ts 46.1 | 18 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 133 | 0 | - | - | ok |
| 2026-10-01 | 849245c | 90 | 44 | officerCockpit.ts 46.1 | 18 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 132 | 0 | - | - | ok |
| 2026-10-01 | b582c93 | 90 | 44 | officerCockpit.ts 46.1 | 18 | 15 | 4 | 45 | 139 | 0 | 3 | 19 | 133 | 0 | - | - | ok |
| 2026-10-01 | 1fc39af | 90 | 44 | officerCockpit.ts 44.1 | 18 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 144 | 0 | - | - | ok |
| 2026-10-01 | 5af36e1 | 90 | 44 | officerCockpit.ts 44.1 | 18 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 152 | 0 | - | - | ok |
| 2026-09-30 | 810803a | 90 | 44 | officerCockpit.ts 44.1 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 159 | 0 | - | - | ok |
| 2026-09-30 | 75e2889 | 90 | 43 | officerCockpit.ts 44.1 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 99 | 0 | - | - | ok |
| 2026-09-30 | 34a5f4c | 90 | 43 | officerCockpit.ts 44.1 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 99 | 0 | 0 | ok | ok |
| 2026-09-30 | 40887ef | 90 | 44 | officerCockpit.ts 44.1 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 98 | 0 | - | - | ok |
| 2026-09-30 | 4583a83 | 90 | 44 | officerCockpit.ts 44.1 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 98 | 0 | - | - | ok |
| 2026-09-29 | 7435fa9 | 90 | 43 | officerCockpit.ts 44.1 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 96 | 0 | - | - | ok |
| 2026-09-29 | 244869c | 90 | 43 | officerCockpit.ts 44.1 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 19 | 96 | 0 | - | - | ok |
| 2026-09-29 | a543580 | 90 | 43 | officerCockpit.ts 44.1 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 19 | 92 | 0 | - | - | ok |
| 2026-09-28 | ca706fd | 90 | 43 | officerCockpit.ts 45.7 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 91 | 0 | - | - | ok |
| 2026-09-20 | be270fd | 90 | 42 | officerCockpit.ts 49 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 91 | 0 | - | - | ok |
| 2026-09-20 | 469133f | 90 | 42 | officerCockpit.ts 49 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 91 | 0 | - | - | ok |
| 2026-09-20 | 719f0c8 | 90 | 42 | officerCockpit.ts 49 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 91 | 0 | - | - | ok |
| 2026-09-20 | 586bcb0 | 90 | 42 | officerCockpit.ts 49 | 17 | 15 | 4 | 45 | 139 | 0 | 3 | 20 | 91 | 0 | - | - | ok |
| 2026-09-20 | 986702a | 90 | 42 | income_engine.py 95.6 | 19 | 15 | 4 | 46 | 139 | 0 | 3 | 20 | 91 | 0 | - | - | ok |
| 2026-09-20 | 591b6a9 | 90 | 42 | income_engine.py 95.6 | 19 | 15 | 4 | 46 | 139 | 0 | 3 | 19 | 92 | 0 | - | - | ok |
| 2026-09-20 | 676cc96 | 90 | 42 | income_engine.py 95.6 | 21 | 15 | 4 | 46 | 139 | 0 | 3 | 19 | 92 | 0 | - | - | ok |
| 2026-09-20 | 1a23b52 | 90 | 42 | income_engine.py 95.6 | 21 | 15 | 4 | 46 | 139 | 0 | 3 | 19 | 92 | 0 | - | - | ok |
| 2026-09-20 | d8e9571 | 90 | 42 | income_engine.py 95.6 | 22 | 15 | 4 | 46 | 139 | 0 | 3 | 19 | 91 | 0 | - | - | ok |
| 2026-09-20 | 0694ae2 | 90 | 42 | admin-api.ts 107.1 | 24 | 15 | 4 | 46 | 139 | 0 | 3 | 19 | 88 | 0 | - | - | ok |
| 2026-09-20 | 2b6274e | 90 | 42 | admin-api.ts 107.1 | 25 | 15 | 4 | 133 | 139 | 0 | 3 | 19 | 88 | 0 | - | - | ok |
| 2026-09-19 | 3eadcd9 | 90 | 42 | views_admin.py 273.8 | 25 | 15 | 4 | 133 | 139 | 0 | 3 | 19 | 88 | 0 | - | - | ok |
| 2026-09-19 | 9c5024a | 90 | 42 | views_admin.py 273.8 | 25 | 15 | 4 | 133 | 139 | 0 | 41 | 15 | 86 | 0 | - | - | ok |
| 2026-09-19 | b7a1350 | 90 | 41 | views_admin.py 273.8 | 25 | 16 | 4 | 133 | 139 | 0 | - | 11 | 84 | 0 | - | - | ok |
| 2026-09-19 | 981ac18 | 90 | 41 | views_admin.py 273.8 | 25 | 16 | 4 | 133 | 139 | 0 | - | 11 | 84 | 0 | - | - | ok |
| 2026-09-19 | 93761ad | 90 | 41 | views_admin.py 273.8 | 25 | 16 | 4 | 133 | 139 | 0 | - | 11 | 83 | 0 | - | - | ok |
| 2026-09-19 | 7977547 | 90 | 41 | views_admin.py 273.8 | 25 | 16 | 4 | 133 | 139 | 0 | - | 11 | 84 | 0 | - | - | ok |
| 2026-09-19 | 88c93f0 | 90 | 41 | views_admin.py 273.5 | 25 | 16 | 10 | 133 | 139 | 0 | - | 11 | 83 | 0 | 0 | ok | ok |
| 2026-09-19 | 13274d7 | 90 | 41 | views_admin.py 273.5 | 25 | 16 | 10 | 133 | 139 | 0 | - | 10 | 84 | 0 | 0 | ok | ok |
| 2026-09-19 | 5fbc6e1 | 90 | 41 | views_admin.py 273.5 | 25 | 16 | 10 | 133 | 139 | 0 | - | 18 | 83 | 0 | - | - | ok |
| 2026-09-19 | 1c24748 | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 18 | 83 | 0 | 0 | ok | ok |
| 2026-09-18 | 08ee0ce | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 17 | 83 | 0 | - | - | - |
| 2026-09-18 | cc4406f | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 17 | 84 | 0 | 0 | ok | - |
| 2026-09-18 | 257fcd4 | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 17 | 85 | 0 | - | - | - |
| 2026-09-18 | 1bef45b | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 0 | - | 17 | 83 | 0 | 0 | ok | - |
| 2026-09-18 | 2e3cd2b | 90 | 41 | views_admin.py 290.6 | 25 | 16 | 10 | 133 | 139 | 2 | - | 17 | 83 | 4 | 0 | ok | - |
| 2026-09-18 | b0c2687 | 90 | 41 | views_admin.py 285.4 | 25 | 16 | 10 | 132 | 139 | 2 | - | 17 | 84 | 4 | 24 | ok | - |

## Latest run (2026-10-30, b9028b4, window 2026-08-01 onward)

### Hotspots (fixes x KLOC — where the next bug is most likely)
| file | fixes | lines | score |
|---|---|---|---|
| `halatuju_api/apps/scholarship/vision.py` | 12 | 2338 | 28.1 |
| `halatuju-web/src/lib/officerCockpit.ts` | 16 | 1657 | 26.5 |
| `halatuju_api/apps/scholarship/views.py` | 9 | 2435 | 21.9 |
| `halatuju-web/src/app/admin/scholarship/[id]/view.tsx` | 15 | 1356 | 20.3 |
| `halatuju_api/apps/scholarship/verdict_engine.py` | 17 | 1004 | 17.1 |
| `halatuju_api/apps/scholarship/serializers_admin.py` | 11 | 1022 | 11.2 |
| `halatuju_api/apps/scholarship/serializers.py` | 8 | 1215 | 9.7 |
| `halatuju_api/apps/courses/views_admin.py` | 9 | 802 | 7.2 |
| `halatuju_api/apps/scholarship/services/blockers.py` | 13 | 557 | 7.2 |
| `halatuju_api/apps/courses/views.py` | 3 | 2190 | 6.6 |

### Fix ratio
- 222 fix / 215 feat commits since 2026-08-01

### Files over 1000 lines
- `2435  halatuju_api/apps/scholarship/views.py`
- `2338  halatuju_api/apps/scholarship/vision.py`
- `2190  halatuju_api/apps/courses/views.py`
- `1657  halatuju-web/src/lib/officerCockpit.ts`
- `1371  halatuju_api/apps/courses/stpm_quiz_data.py`
- `1356  halatuju-web/src/app/admin/scholarship/[id]/view.tsx`
- `1279  halatuju-web/src/app/profile/page.tsx`
- `1215  halatuju_api/apps/scholarship/serializers.py`
- `1143  halatuju_api/apps/scholarship/contracts.py`
- `1092  halatuju-web/src/lib/scholarship.ts`
- `1074  halatuju-web/src/app/scholarship/apply/page.tsx`
- `1054  halatuju_api/apps/courses/models.py`
- `1043  halatuju_api/apps/scholarship/profile_engine.py`
- `1022  halatuju_api/apps/scholarship/serializers_admin.py`
- `1007  halatuju_api/apps/scholarship/sponsorship.py`
- `1004  halatuju_api/apps/scholarship/verdict_engine.py`

### Python functions of 150+ lines
- `333  halatuju_api/apps/courses/ranking_engine.py:379 calculate_fit_score`
- `320  halatuju_api/apps/scholarship/views.py:1011 post`
- `315  halatuju_api/apps/scholarship/vision.py:2017 _run_field_extraction_impl`
- `294  halatuju_api/apps/courses/engine.py:354 check_eligibility`
- `293  halatuju_api/apps/courses/management/commands/backfill_spm_field_key.py:22 classify_course`
- `253  halatuju_api/apps/courses/views.py:126 get`
- `244  halatuju_api/apps/courses/management/commands/classify_stpm_fields.py:296 classify_stpm_course`
- `215  halatuju_api/apps/scholarship/verdict_engine.py:499 _verdict_income`
- `192  halatuju_api/apps/scholarship/services/offer_sync.py:168 autofill_pathway_from_offer`
- `186  halatuju_api/apps/scholarship/resolution.py:275 doc_match_verdict`
- `169  halatuju_api/apps/courses/management/commands/sync_stpm_mohe.py:37 handle`
- `167  halatuju_api/apps/courses/views_staff.py:193 post`
- `165  halatuju_api/apps/courses/views.py:1017 get`
- `162  halatuju_api/apps/scholarship/help_engine.py:342 verdict_for_document`
- `151  halatuju_api/apps/scholarship/bursary.py:129 render_agreement_html`

### Function names with 3+ homes in one app
- _gemini_generate x3 (scholarship): apply_copy_draft.py, contracts.py, sponsor_terms.py
- banned_phrases x3 (scholarship): email_templates.py, partner_comms.py, sponsor_comms.py
- render x3 (scholarship): email_templates.py, partner_comms.py, sponsor_comms.py
- unknown_placeholders x3 (scholarship): email_templates.py, partner_comms.py, sponsor_comms.py

### Cross-app imports
- courses -> scholarship: 17 edges (24 import statements)
- reports -> courses: 8 edges (9 import statements)
- reports -> scholarship: 2 edges (3 import statements)
- scholarship -> courses: 46 edges (222 import statements)

### Suppressions
- # noqa: 38
- # type: ignore: 11
- : any: 2
- eslint-disable: 42
- reasoned `# noqa: CODE — reason` (informational, not budgeted): 42

### Skipped tests
- none

### Front-end rules mirrored from the backend with no drift test
- 53 of 56 mirror claims in src/lib name a drift test
- halatuju-web/src/lib/incomeWizard.ts:1  Pure mirror of the backend income requirement engine (apps/scholarship/income_engine). Kep
- halatuju-web/src/lib/incomeWizard.ts:98  Malaysian patronymic connectors (A/L, A/P, S/O, D/O, bin, binti, @). A name that carries o
- halatuju-web/src/lib/incomeWizard.ts:125  Compulsory (mirrors income_engine.salary_member_blocks): IC → relationship doc. Income its

### Source-text guard tests (web)
- 35 of 298 web test files read source text (signals: readFileSync, apiSource); drift 24 (*Drift.test.ts, counted apart)

### Debt register
- 423 entries have a defining line; 144 carry no resolution marker on it
- no TD number defined twice (declared collisions: 151, 152)

### Debt register near-misses — read these by eye
- line 1376: - **TD-058**: The **prod DB has no `django_content_type` / auth tables** (the contenttypes/admin apps' tables were never created on this Supabase inst
- line 1398: - **TD-068**: **Contractual rejection (bucket 4) has no admin-typed reason or post-award capture flow.** v2.19.0 shipped the `contractual` category + 
- line 1415: - **TD-075**: **Phase E3 — the money + the rest of the sponsorship flow (deferred; built dark on mocked money in E3a).** v2.26.0 shipped the wallet/ma
- line 1704: - **TD-115**: **No fixed document-slot model — uploads share slots and the income engine stores docs by a
- line 6200: ### [TD-252] An award nobody answers stays open for ever; a test/abandoned case cannot be closed — medium
- line 6514: - **TD-318 (raised 2026-09-30 by the register review; the leftover of TD-135) — low, AN OWNER ACTION.** The WhatsApp inbound STOP/START webhook is bui
- line 6528: - **TD-328 (raised 2026-10-03 by Now sprint 5 part 1, TD-229) - medium, money — RULED 2026-10-04 (owner): the flat RM200 default STAYS until the FIRST
- line 6536: - **TD-336 (raised 2026-10-05 by Later-tier batch 5's review, TD-334) - low, tenancy-adjacent: the Programme Overview pools platform-wide money totals
- line 6554: - **TD-354 (raised 2026-10-05 by the same review, finding 8) - low, student-visible: the "This application is closed" card offers "See programmes that
- line 6556: - **TD-356 (raised 2026-10-06 by the TD-349 fix) - eligibility, pre-existing: `cancel_reopen` cannot tell an unmoved `interviewing` from a QC reopen's
- line 6561: - **TD-361 (raised 2026-10-06 by the Consolidation Review's code-health reading — the third-consecutive-accept rule) - low, hygiene: `big` has been ac
- line 6563: - **TD-363 (raised 2026-10-06 by the TD-352 sprint) - low, officer-visible: the status a case was closed FROM has no field, and the Close card cannot 
- line 6565: - **TD-365 (raised 2026-10-06 by the TD-352 sprint) - narrow race, money-adjacent, pre-existing class: a close and a fund can interleave.** `close_app
- line 6567: - **TD-367 (raised 2026-10-06 by the TD-352 adversarial review) - money, pre-existing: a payment run can pay a closed student.** `payments.complete` (
- line 6568: - **TD-368 (raised 2026-10-06 by the TD-352 review, round 3) - low, pre-existing, shared with rejected/expired: interview times can be proposed and bo
- line 6583: - **TD-383 (raised 2026-10-18 by the Consolidation Review, promoting a cluster) - money + eligibility: a write that depends on an application's status
- line 6586: - **TD-386 (raised 2026-10-18 by the sources-and-referrals Sprint B adversarial review) - low, multi-tenant: three seams still cross organisations onc

### Unused npm dependencies
- none

### Standards budgets vs the last recorded run
- budgets no looser than at e6a03fb

### tsc
- 0 errors in 0 files

### i18n
- ==================================================
- ALL PASSED (0 warnings)
- Total keys per locale: 6067

## Reviews

_Decisions per run, newest first. Written by a person or the agent — never by the tool._

### 2026-10-30 (b9028b4, published-hours + corrections close) — 0 FAIL; one reading moved, accepted

**0 FAIL, 5 standing WARNs** (`--full`). Against e6a03fb: `fix%` 52 → **51**, `hot#1` vision.py 28.1 unchanged,
`big` 16, `long` 15, `dup` 4, `xapp` 73, `supp` 93, `skip` 0, `mirror` 3, `guard%` 12, `unused` 0, `tsc` 0 —
all identical. One reading moved: **`td_open` 142 → 144.**

**The arithmetic:** +2 is exactly TD-425 and TD-426, both raised BY this sprint about this sprint's own work —
a correction whose month is never invoiced is silently stranded, and `hoursAnalysisId` duplicates the server's
`closing_report` in a second language. Neither was built because the sprint was already a live-money fix and the
remedies want their own gate (TD-426's is a payload change).

**Accepted.** This is a reading that moved because the sprint did the right thing: the alternative to +2 was to
leave two known gaps unwritten, and an unrecorded gap is not a smaller debt — it is the same debt, unfindable.
`td_open` counts rows, so honest disclosure can only ever push it up; it is a disclosure count wearing the
clothes of a debt count. No action, and nothing to engineer away.

**Not claimed:** `big` stayed 16 although this sprint SPLIT three files (`platform_cost.py` back under 600,
`ChargeCard`/`ChargeCorrections`/`UnbilledSection` out of the billing page, which left the web oversize ledger
entirely). F1 and S4b landed new modules in the same window, so the net is flat. The split is real; the number
does not show it, and saying otherwise would be taking credit the reading does not support.
### 2026-10-30 (5ce4ee6, Bumi Sprint F1 close) — 0 FAIL; nothing to promote

**0 FAIL, 5 standing WARNs** (`--full`). Against e6a03fb: `fix%` 52 -> 51 (window roll), `big` 16, `long` 15,
`dup` 4, `xapp` 73 and `td_open` 142 unchanged. F1's new modules (`tvet_*.py`, `catalogue_ingest.py`,
`ingest_tvet_courses.py`) all sit under 500 lines; `courses/views.py` 2182 -> 2190 and `scholarship.ts`
1090 -> 1092 for the two new pathways (both already listed over 1000; no new file crossed). **Accepted, no action.**

### 2026-10-29 (e6a03fb, default payment schedule close) — 0 FAIL; nothing moved

**0 FAIL, 5 standing WARNs** (`--full`). Against 860792b (D2 close) every headline reading is identical: `fix%`
52, `hot#1` vision.py 28.1, `big` 16, `long` 15, `dup` 4, `xapp` 73, `guard%` 12, `td_open` 142. The sprint added
one small module (`default_schedule.py`) and made `payments.py` shorter (595 -> 571 lines, the deleted fallback
constants). The hotspot table's churn shifts (views.py, serializers.py) are maintenance S4a's commits, not this
sprint's. **Accepted, no action.**

### 2026-10-29 (860792b, Bumi Sprint D2 close) — 0 FAIL; nothing to promote

**0 FAIL, 5 standing WARNs** (`--full`). Against f528264 (D1 close): `xapp` 73 unchanged (D2 imports stay inside
`apps/courses`); `guard%` 11 -> 12; `td_open` 140 -> 142 from other sessions' raises (Matric/Diploma, maintenance).
D2 grew no file past its budget (ranking_engine.py was left alone for that reason). **Accepted, no action.**

### 2026-10-29 (71ae8cc, billing meter guard + payment declarations close) — 0 FAIL; one reading moved, on purpose

**0 FAIL, 5 standing WARNs** (`--full`). Against the previous run (`f528264`) exactly ONE number moved:

| reading | was | now | decision |
|---|---|---|---|
| `td_open` | 140 | **143** | **ACCEPTED.** The three are TD-422, TD-423 and TD-424, all raised BY this sprint about its own work: the busy-meter guard asks a month-wide question rather than a per-tenant one (harmless at one tenant, wrong at two); a receipt whose email failed can only be re-sent by hand; and the platform now has two date formats. Writing them down is the sprint doing its job — a register that only ever falls is a register nobody is adding to honestly. |

Everything else is byte-identical: `fix%` 52, `hot#1` vision.py 28.1, `big` 16, `long` 15, `dup` 4, `xapp` 73,
`supp` 93, `skip` 0, `mirror` 3, `guard%` 11.

⚠ **Two moves-only splits in this sprint did NOT move `big`, and that is the reading being fair, not lucky.**
`platform_cost.py` fell 664 → 566 and LEFT the 600-line ledger entirely; `invoicing.py` fell 626 → 532. Both new
modules (`metered_usage.py` 199, `invoice_receipts.py` 132) are far below every threshold, so the count of large
files was always going to be unchanged — unlike the `xapp` case noted on 2026-09-20, where a faithful split could
only inflate the number. Nothing was engineered to hold a reading.

**Nothing promoted.** The five WARNs are the standing ones and none worsened.


### 2026-10-29 (f528264, Bumi Sprint D1 close) — 0 FAIL; nothing to promote

**0 FAIL, 5 standing WARNs** (`--full`). Reads across Bumi D1, maintenance S1–S2, Matric/Diploma M2 and the
billing pushes since f856d20. `xapp` 72 -> 73: not D1 — every import D1 added is inside `apps/courses`
(checked by diff over `1debc6cc..f5282643`). `td_open` 137 -> 140 = TD-419..421 raised by the maintenance
close. `guard%` 12 -> 11 is the denominator growing (D1 added ~1,600 lines of parser and ingest code under
plain unit tests). D1's own moves-only splits took `engine.py` 858 -> 640, `models.py` 1085 -> 1051 and
`views.py` 2309 -> 2177 lines of budget. **Accepted, no action.**

### 2026-10-29 (f856d20, Bumi Sprint C + TD-416 close) — 0 FAIL; `big` 17 -> 16; nothing to promote

**0 FAIL, 5 standing WARNs** (`--full`; `tsc` 0, `i18n` ok, `std` ok). Reads across Bumi Sprint C, TD-416, the
billing back-issue sprints and Matric/Diploma M1. `big` 17 -> 16: `org_requests.py` (Billing's split) left the
list and `serializers_admin.py` fell to 1,006; `/profile` page fell 1,389 -> 1,279 (Sprint B's split). `supp`
92 -> 93 (+1, other sessions' work this window; not from Sprint C, which added no suppression). `td_open`
136 -> 137 nets TD-417 raised against TD-416 closed (TD-418 opened and closed the same day). `xapp` 72
unchanged — Sprint C added no cross-app import. **Accepted, no action.**

### 2026-10-28 (6e1d66d, Consolidation Review) — `xapp` +5 FAIL accepted as TD-414 (the third accept); `hot#1` moved to `vision.py`

**1 FAIL, 5 standing WARNs** (plain run, as the review asks; `std` ok). Against the income
declarations close (00f1f7e); reads across TD-408 + TD-411, the health light, the billing-settings
change and STPM CGPA C1–C4.
- **`xapp` 67 → 72 (FAIL) — accepted, and made TD-414.** The five new edges, diffed by name against
  `00f1f7e` (a script over `git show <rev>:<file>` with the tool's own rule), are all
  `scholarship -> courses` and all the STPM CGPA arc's: `stpm_pngk.stpm_cgpa_of` and
  `stpm_pngk.pngk_from_grades` (`c56bc0c5`, `6c10bd1e`, `ae756af5`; read by `pool`, `shortlisting`,
  `profile_sync`, `higher_results`, `stpm_marks`, `stpm_asks`), and `exam_questions.merit_100`,
  `exam_questions.overall_from`, `stpm_engine.STPM_CGPA_POINTS` (only the one-off
  `backfill_stpm_cgpa` command). **The billing change adds no edge**: `views_admin/invoices.py`
  imports `apps.courses.models.PartnerOrganisation`, an edge that already existed (two more
  statements on it, 197 → 211 statements overall with the STPM work). TD-408, TD-411 and the health
  light add none. The direction is the sanctioned one and the back-edge (`courses -> scholarship`
  17) did not move. But this is the third accepted rise running (2026-10-18 +6, 2026-10-25 +1, +1),
  with the third results route's +15 (52 → 67) referred twice and never decided — so per the rule it
  is a ticket: **21 of the 22 edges added since 2026-10-18 point at the results rules**
  (`exam_questions` 17, `stpm_pngk` 2, `stpm_engine` 2). TD-414: name that public surface and test it
  is the only door. This review also decides the referred +15: accepted under the same TD.
- **`hot#1` `officerCockpit.ts` 26.5 → `vision.py` 28.1 (moved, ok).** `vision.py` 10 → 12 fixes:
  TD-408 (`8a8a56a5`, the patronymic matcher) and TD-411 (`8bac9363`, the watermark text layer), both
  sprints with their own review rounds; 2338 lines, under its ledger line. The 2026-10-27 retro's
  proposal (split the genuineness wiring out of `vision.py`) stands as the cure; no new TD.
- **`fix%` 53 → 52 (WARN, moved, better)** — the window; TD-385 unchanged.
- **`td_open` 131 → 136 (info):** +3 is the register seeing itself — TD-397, TD-398 and TD-399 had
  no defining entry (index pointers only, since 2026-10-25), written by this review; +2 is TD-414 and
  TD-415, raised by it. TD-412 and TD-413 (the billing change) were already counted.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 =
  TD-262. Near-misses: TD-411 left the list (closed); the rest unchanged and read.

### 2026-10-28 (00f1f7e, income declarations close) — 0 FAIL; standing WARNs unchanged

**0 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Against the TD-409 close (ddb26b6).
- **`fix%` 53, unchanged**; `xapp` 67, unchanged — #374 adds no cross-app edge.
- **Hotspots:** `vision.py` churn 8 → 10 and `verdict_engine.py` 15 → 17 (the #374 rounds); both held at their
  size caps (2340 / 1004 lines) — the next change in either trims first.
- **`supp` 39 → 37 bare** (reasoned 41 → 43, informational) — no new bare suppression.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 = TD-262.
- **wat_lint** 0 FAIL; 2 standing WARNs (memory pointer count; three earlier small-lane entries that add modules).

### 2026-10-27 (ddb26b6, TD-409 close) — 0 FAIL; `fix%` +1 accepted

**0 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Against the TD-407 + TD-404 close (e3da157).
- **`fix%` 52 → 53 (WARN, moved) — accepted, TD-385 again**: TD-409's two `fix:` commits enter a window that
  dropped an older `feat:`; nothing regressed.
- **`xapp` 67, unchanged** — TD-409 adds no cross-app edge (one more `scholarship -> courses` import statement on
  an existing edge, from the D16c commit it was rebased on). The +3 from the third results route stays referred.
- **`long`**: `doc_match_verdict` 185 → 186 lines, inside its ledger allowance (187) — near it; the next change
  there trims first.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 = TD-262.
- **wat_lint** FAILs on `98fe145d` (D16) and `2cb9d113` (D16c) having no consolidation-log line — those sprints'
  to log; not written here on their behalf. TD-409's two commits are logged.

### 2026-10-27 (e3da157, TD-407 + TD-404 close) — 1 FAIL (`xapp`), NOT these sprints' — referred to the lead

**1 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Against the corpus C3 + C4 close (4e6e0ec).
- **`xapp` 64 → 67 (FAIL) — NOT ACCEPTED HERE; it belongs to the third results route.** The three new
  `scholarship -> courses` edges (37 → 40) are from `01f8a723` (S3: 13 added `apps.courses` imports), `4bab4086`
  (S4: 2) and `fe48cd36` (1). TD-407 (`9bdb163f`, `e65a9cd3`) and TD-404 (`b1fe889c`, `71e38f89`, `0e03a678`) add
  no cross-app import. Raised to the coordinator with this close.
- **`supp` 135 → 94 (info, better)** — another session's clean-up; not ours.
- **`hot#1` `officerCockpit.ts` 26.5 → 28.2** — the third route's web work; TD-404 touched copy only.
- **`td_open` 131 → 130 (info)** against the register's own 134; the tool's near-miss gap.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 = TD-262.
- **Proposal (retro):** split the genuineness wiring out of `vision.py`, at its allowance two sprints running.
- **wat_lint** also FAILs this close on `98fe145d` (the D16 sprint) having no consolidation-log line — that
  sprint's to log; not written here on its behalf.

### 2026-10-26 (4e6e0ec, corpus gaps C3 + C4 close) — 0 FAIL; `fix%` +1 accepted

**0 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Against the TD-403 close's run (c7871ee).
- **`fix%` 51 → 52 (WARN, moved) — accepted, TD-385 again**: TD-403's and C3's `fix:`/`feat:` commits land in a
  window that dropped older `feat:` commits; nothing regressed.
- **`xapp` 64, unchanged** — the third results route's +12 (recorded at the C1 + C2 close) is still that
  sprint's to explain; C3 adds no cross-app import.
- **`td_open` 130 → 131 (info)** against the register's own 134 (TD-407 raised); the tool's near-miss gap.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 = TD-262.

### 2026-10-26 (c7871ee, TD-403 sprint close) — 0 FAIL; `hot#1` moved to `officerCockpit.ts`

**0 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Reads across TD-403 (`32a847f1`,
`cafcfc43`, `85921925`, `b67dd4f5`, `ed342354`) and corpus gaps C3 (`0ae5f431`, another session).
- **`hot#1` `views.py` 24.4 → `officerCockpit.ts` 26.5 (moved).** `officerCockpit.ts` 14 → 16 fixes, +6
  lines (1650 → 1656): TD-403's two `fix:` commits touched its STR chips and the "salary documents are
  supportive" mirror (a `stale` / `future` STR no longer counts, as `str_not_breached`). One rule, one
  mirror — no new branch family; it rose because the window counts commits, and the sprint's review fixes
  were separate commits. `views.py` unchanged (TD-403 deliberately added nothing there, 2 lines under its
  allowance).
- **`verdict_engine.py` 13.1 → 14.1** (TD-403's one fix; 1004 lines = its 984 + 20, held by the lead's
  `ed342354`). `vision.py` +3 lines is C3's.
- **`xapp` 64, unchanged; `fix%` 51, unchanged** (199 fix / 190 feat).
- **`td_open` 131 → 130 (info)** against the register's own 133 (TD-403 closed); the tool's near-miss gap.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 = TD-262.

### 2026-10-26 (a781b49, corpus gaps C1 + C2 close) — 1 FAIL (`xapp`), NOT this sprint's — referred to the lead

**1 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Reads across the third results route
S2a + S2b (another session) and corpus gaps C1 + C2.
- **`xapp` 52 → 64 (FAIL) — NOT ACCEPTED HERE; it belongs to the third results route.** The 12 new edges
  are `scholarship -> courses` +6 (31 → 37) and `reports -> courses` +6 (2 → 8). They come from
  `e4096440` (S2a: 12 added `apps.courses` imports) and `eddd4ad6` (S2b: 3, the `reports` app). C1 + C2
  (`1a2b4962`, `95131a65`, `1accaab9`, `a781b49a`) add no cross-app import — every import they add stays
  in `apps.scholarship`. This close does not accept another sprint's move; the third-route close (or the
  lead) records the reason or the fix. Raised to the coordinator with this close.
- **`fix%` 51, unchanged** (197 fix / 189 feat in the 90-day window).
- **`hot#1`** `views.py` 26.8 → 24.4 (the window moved; no C1/C2 change in `views.py`).
- **`td_open` 130 → 131 (info)** against the register's own 134 (TD-406 raised); the tool's near-miss gap.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 = TD-262.

### 2026-10-25 (ca5dc8b, TD-401/402 sprint close) — 0 FAIL; `xapp` +1 accepted (not this sprint's)

**0 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Reads across request #44's tail, the third
results route S1 (another session) and the TD-401/402 sprint.
- **`xapp` 51 → 52 (moved) — accepted, not this sprint's.** The new `scholarship -> courses` edge is
  `50df8d7f` (third results route S1: `apps.courses.exam_questions.merit_100`, the one 0-100 merit scale
  every route shares, which lives with the course engine by design). The TD-401/402 commits add no
  cross-app import.
- **`fix%` 51, unchanged** (202 fix / 196 feat; this sprint's three `fix:` commits are one piece of work
  and its two review rounds) — TD-385 stays the fix.
- **Hotspots:** `verdict_engine.py` 12 → 13 (TD-401's one fix, 1003 lines, under its 984 + 20);
  `serializers_admin.py` 16 → 15.8 and `views.py` +1 line are other sessions'. `hot#1` unchanged.
- **`td_open` 129 → 130 (info)** against the register's own 133 (TD-401, TD-402 closed; TD-403 to TD-405
  raised); the gap is the tool's near-miss counting, unchanged in kind.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 = TD-262.

### 2026-10-25 (46b1c0b, TD-390 sprint close) — 0 FAIL; `fix%` +1 accepted

**0 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Reads across request #45 and TD-390.
- **`fix%` 50 → 51 (WARN, moved) — accepted, TD-385 again.** 199 fix / 195 feat: two `fix:` commits landed
  (request #45 and TD-390, each one commit for a whole piece of work) while the 90-day window dropped two
  July `feat:` commits. Nothing regressed; TD-385 (count sprints from the consolidation log) stays the fix.
- **Hotspots moved, `hot#1` unchanged (`views.py` 26.8).** `vision.py` 9.2 → 11.7 (one more fix, +31 lines:
  the second-opinion mark and its no-degrade guard, inside its ledger line 2321 + 20); `verdict_engine.py`
  11 → 12 (1004, exactly at its 984 + 20 — comments compressed to fit, nothing raised);
  `serializers_admin.py` 14.8 → 16 is request #45's.
- **`td_open` 127 → 129 (info)** against the register's own 132 (TD-390 closed; TD-400 to TD-402 raised);
  the gap is the tool's near-miss counting, unchanged in kind from the last reading.
- **Standing WARNs, delta 0:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger; `mirror` 3 = TD-262.

### 2026-10-25 (9d3ff53, AI-outage sprint close) — 0 FAIL; `fix%` +4 and `xapp` +1 accepted with reasons

**0 FAIL, 5 standing WARNs** (`--full`; `std`, `tsc`, `i18n` ok). Reads across request #42, the Team person
pages sprint and the AI-outage sprint.
- **`fix%` 46 → 50 (WARN, moved) — accepted, TD-385 again.** The window slid to 2026-07-27, dropping 45 feat
  and 8 fix commits from late July (197 / 197 now). The AI-outage sprint shipped as ONE `fix:` commit, so it
  adds one; the rise is the window, not new breakage. TD-385 (read sprint SHAs from the consolidation log)
  remains the fix in the tool.
- **`xapp` 50 → 51 (moved) — accepted.** The new edge is `apps/reports/report_engine.py` importing
  `apps.scholarship.gemini.cascade_failure` (lazily, beside its existing lazy `apps.scholarship.usage`
  import): the counsellor report's cascade now names every model's error from the one home both cascade
  seams use, instead of a fourth copy. Same direction as the existing `reports -> scholarship` metering edge;
  `courses -> scholarship` statements unchanged (`std` ok).
- **`hot#1` `officerCockpit.ts` 28.1 → `views.py` 26.8 (ok).** The window dropped three of
  `officerCockpit.ts`'s fixes; `views.py` grew by 2 lines (the attempt/breaker guard, net of a de-duplicated
  lookup). `vision.py` rose 6.9 → 9.2 (one more fix, +14 lines — the outage choke point), still under its
  ledger line (2321 + 20).
- **`td_open` 123 → 127 (info):** TD-390, TD-393 to TD-399 raised and TD-391, TD-392 closed by the AI-outage
  sprint (the register's own header reads 130; the tool's count lags its near-miss rule — see near-misses).
- **Standing WARNs, delta 0, not re-accepted:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by ledger
  (`_run_field_extraction_impl` 306 → 311, inside its +10); `mirror` 3 = TD-262. Near-misses unchanged.

### 2026-10-18 (65af261, Consolidation Review) — `xapp` +6 FAIL accepted with reasons and one TD; `fix%` is TD-385

**1 FAIL, 5 standing WARNs** (plain run, as the review asks; `std` ok). It reads across the staff
lifecycle, sources Sprint A, request #32 and #33 — the first two closed with no reading of their own,
which is why six edges arrived at once.
- **`xapp` 44 → 50 (FAIL) — accepted, with TD-384.** The six new edges, diffed by name against
  `ffa0983`: `scholarship -> courses` +5 (`staff_lifecycle.py` reads `models_claim.ProfileLoginAlias`,
  `password_change_flag`, `supabase_admin`; `views_admin/staff.py` reads `views_admin._staff_target_manageable`;
  three Sprint A readers share the one door `referral_links.referring_org`) and `courses -> scholarship`
  +1 (`views_admin` reaching `staff_lifecycle`, inside the existing `scholarship_staff()` door — the
  back-edge statement budget held at 17, `std` ok). Five are the sanctioned direction: the staff rows
  are courses', the work footprint is scholarship's, and the lifecycle must see both. The one that is
  not fine is a private, underscore name of another app's VIEW module imported across the border:
  **TD-384** (move the fence check to a public module, moves only).
- **`fix%` 45 → 46 (WARN, moved) — TD-385, not a third explanation.** At least 18 of the window's
  205 `fix:` commits are sprints' own review rounds (TD-352 ×12, request #30, org-timing F1, TD-371..377,
  per-gift sources); without them it reads ~44. Explained the same way at `48fda4b`; the third time
  is a ticket. The fix is in the workspace tool (read the sprint SHAs the new sprint-close line records).
- **`hot#1` `views.py` 31.7 → `officerCockpit.ts` 28.1 (ok).** The 90-day window slid nine days and
  dropped two of `views.py`'s fixes (13 → 11, 26.8 now); neither file grew. No decision needed.
- **`td_open` 120 → 123 (info):** TD-383, TD-384, TD-385 raised by this review; nothing closed since
  `ffa0983` but TD-335 (closed and TD-382 raised by the staff lifecycle, net 0).
- **Standing WARNs, delta 0, not re-accepted:** `big` 17 = TD-361; `long` 15 and `dup` 4 held by
  ledger; `mirror` 3 = TD-262. Near-misses: the new TD-383 is counted open, correctly; the rest are
  unchanged from 2026-10-09.

### 2026-10-09 (ffa0983, per-gift referral sources S1 + S2 close) — no reading worse; `xapp` +1 is TD-372's audit import

**0 FAIL, the same 5 standing WARNs** (`--full`; `fix%` 45, `big` 17, `long` 15, `dup` 4, `mirror` 3 —
all delta 0). This reading also spans request #31, TD-371..375 and TD-376/377 (no close reading of their
own). `xapp` 43 → 44 (ok, not a FAIL): `courses -> scholarship` 15 → 16 edges (24 → 25 statements) is
`profile_claim._scholarship` now importing `birth_state` beside `whatsapp` and `emails` for TD-372's
audit line (`de158391`) — one statement carrying three names, which the tool counts as three; the
sources sprint added no cross-app import. Accepted. `td_open` 118 → 120 (info): TD-369 and TD-230
closed; TD-378, TD-379, TD-380, TD-381 raised. `big` files moved within their budgets
(`scholarship/views.py` 2429 → 2436, +7 from S2's refusal; `courses/models.py` 1384 → 1380 from S1's
deprecation); `mirror` claims 52 → 53 with the new one drift-tested (`referralSources.test.ts`).
Hotspot moves are the 90-day window sliding, not this sprint. Near-misses: TD-380 / TD-381 are open as
written; TD-369 left the list (resolved).

### 2026-10-07 (5fd333e, org-timing Sprint 1 close) — no reading worse; the cross-app edge count fell

**0 FAIL, the same 5 standing WARNs** (`--full`; `fix%` 45, `big` 17, `long` 15, `dup` 4, `mirror` 3 —
all unchanged). `td_open` 116 → 118: TD-369 and TD-370 raised by the sprint's adversarial review.
`courses -> scholarship` 20 → 15 edges (29 → 24 statements): the registry's six lazy constant imports
became one door, and the code-standards budget fell 25 → 20 with it — an improvement, accepted.
`scholarship -> courses` 135 → 145 statements, same 25 edges: every timing read site now imports
`apps.courses.org_config` lazily inside the function that reads it (the sanctioned spelling) — the
statement count measures that spelling, not new coupling (TD-268's definition note applies); accepted.
Hotspot moves are window churn (the 90-day window slid a day), not this sprint.

### 2026-10-06 (48fda4b, TD-352 close) — no reading worse; `fix%` 43 → 45 is this sprint's own review fixes

**0 FAIL, 5 standing WARNs, `tsc` 0, `i18n` ok, `std` ok** (`--full`). It reads across request #28's
follow-up (another session) and TD-352. `td_open` 112 → 116: TD-352 and TD-364 closed (−2), TD-363,
TD-365, TD-366, TD-367, TD-368 raised by the sprint and its three review rounds (+5), and request #28's
follow-up raised one (+1). `fix%` 43 → 45: the sprint's three review rounds landed as `fix:` commits
on the same day as its `feat:` commits (the lane's own word for a review fix is `fix:`), so the ratio
counts the review's rigour as churn — dated, not accepted; the arc's question is read again in December.
`hot#1` unchanged (`views.py` 31.6; this sprint added nothing to it). Two hotspots moved up by their
review-fix commits and NOT by size: `officerCockpit.ts` 29.7 → 31.4 (18 → 19 fixes, 1650 lines —
one token changed, `'closed'` joined `CASE_CLOSED_STATES`; the new stage logic went to
`lib/closeOffer.ts`), `view.tsx` 16.2 → 18.9 (12 → 14 fixes, 1351 lines, unchanged size — four call
sites now go through `stageStatus`). `serializers.py` 7.2 → 8.4 (+3 lines: `active_at` on the student
read). **Accepted**: the hotspot score weights fix commits, and a sprint whose review found a reader of
`closed` on these files had to touch them to fix it; neither grew. The standing WARNs (`big` 17 =
TD-361, `long` 15 and `dup` 4 enforced by ledger, `mirror` 3 = TD-262) are unchanged from the entry
below and are not re-accepted here.

### 2026-10-06 (161f11e, Consolidation Review) — no reading worse; the third accept of `big` is TD-361, not an accept

**0 FAIL, 5 standing WARNs, `tsc` 0, `i18n` ok, `std` ok** (`--full`). It reads across TD-349's close,
which deferred its own reading, and this review. `td_open` 105 → 112: TD-349 closed (−1), TD-355 to
TD-359 raised by its fix and review (+5), TD-360 to TD-362 raised by this review (+3). `guard%` 12 → 13
(28 of 225 → 30 of 226 files read text): `decisionReopenOffer.test.ts` (TD-349; reads `reopen.py`) and
`bundleBudgetReader.test.ts` (this review's near-line check; reads `package.json` and `cloudbuild.yaml`
to pin that only the gate passes `--gate`) — both wiring assertions, under the 15% line. **Accepted.**
`drift` 15 → 16 is request #28's `spendCategoryDrift.test.ts`.

**The third-consecutive-accept rule, WARN by WARN** (each read delta 0 at `7ab5d43`, `538c82f` and now):
- `big` 17 — **it bites: TD-361.** No live ticket since TD-284 closed on 2026-10-04 ("a Phase 4b when
  somebody wants one"), and the top two hotspots, `views.py` and `officerCockpit.ts`, are both on it.
- `long` 15 — not a bare accept: the api `long_functions` ledger holds exactly these fifteen and the
  deploy gate fails a sixteenth or a longer one. Enforced; no ticket.
- `dup` 4 — decided permanent (fifth reading, H7; restated by H19), and the api `duplicated_names`
  ledger holds the four. Enforced; no ticket.
- `mirror` 3 — parked behind TD-262, which is open (an owner decision); the web `unguarded_mirrors`
  ledger holds it at three. The ticket exists.
- `fix%` 43 — a 90-day ratio, WARN-only by design since TD-284 closed; it is dated, not accepted: the
  arc's question can be read again in December.

**For the tool, not the code (workspace repo, not changed here).** Four of the five WARNs are standing
decisions backed by a ledger or a ticket, so each review "accepts" them again and the rule then asks
for a ticket that would duplicate one already closed. Proposed for `code_health.py`: a project
declares a standing decision per WARN (reading, reason, ledger or TD id) and the tool prints it as
DECIDED, so the third-accept rule bites only on an undecided WARN — as it did on `big` here.

### 2026-10-06 (538c82f, one-application-per-organisation close) — no reading worse; `td_open` +5 is seven raised, two closed

**0 FAIL, 5 standing WARNs, `std` ok.** `fix%` 44 → 43; `big` 17, `long` 15, `dup` 4, `mirror` 3,
`guard%` 12 all unchanged. `td_open` 100 → 105: the sprint and its adversarial review raised TD-348 to
TD-354 and closed TD-337 (the owner's ruling, built) and TD-340 (submit errors stay visible) — the
arithmetic is +7 − 2. **TD-349 is the one to promote: a pre-existing way for an embargoed decline to
reach the student with no email (a reopen, or a failed release send); it sits in the Now tier.**
`hot#1` reads `views.py` 31.6 instead of `officerCockpit.ts` 33 only because the window moved a day
(2026-07-07 → 07-08) and two of the cockpit's commits left it (33 → 29.7); `views.py` itself did not
move (31.6 both runs, 2431 → 2429 lines) — a change of leader, not a reading that got worse. The new
modules (`services/apply_gate.py`, `student_status.py`, `views_apply_gate.py`, `useApplyGate.ts`) are
all small, so `big` did not move; `apply/page.tsx` and `serializers.py` both shrank.

### 2026-10-05 (7ab5d43, request #26 close) — no reading worse; `td_open` +1 is TD-347

**0 FAIL, 5 standing WARNs, `std` ok.** Every WARN delta 0 (`fix%` 44, `big` 17, `long` 15, `dup` 4,
`mirror` 3). `guard%` 13 → 12: request #26 added rendered and behaviour tests, not source-reading
ones — the right direction, accepted. `td_open` 99 → 100 is **TD-347**, raised by the final review and
left open by ruling (it must be fixed before `BURSARY_AGREEMENT_ENABLED` is set). The new modules
(`guardian_contact.py`, `parent_call.py`, `signing_window.py`, the two views) are all under 600 lines,
so `big` did not move. Nothing to promote.

### 2026-10-02 (c993050, Now sprint 4) — `xapp` 45 → 48 is the accessor move, accepted with the arithmetic

**1 FAIL (`xapp`), 6 standing WARNs, `td_open` 130, `std` ok.** TD-218 moved the two exam-type
accessors into `apps/courses/exam_questions.py` (so the profile view in `courses` can serve the
answer), and the six scholarship readers now each carry `from apps.courses.exam_questions import …`
where they used to read a profile ATTRIBUTE. Eight new import statements, every one in the
ALLOWED direction (scholarship → courses); the enforced standard — `courses → scholarship` ≤ 25,
module-level ≤ 1 (`test_code_standards.py`) — passed in the deploy gate unchanged. `xapp` counts
statements and is blind to direction (TD-268, 2026-09-20), so a faithful move can only raise it.
**Accepted. Do not undo the move to lower the number.** The reading is the tool's shortcoming,
already registered.

### 2026-09-20 (thirteenth reading) — H19 closes the arc: every reading delta 0, and the six standing WARNs are now decided in one place

Read-only (`--write` was excluded by the brief), taken on a tree where **no production code, no
test file and neither `code-standards.json` was changed.** **0 FAIL, 6 WARN**, every reading delta
0 against `469133f`: `fix%` 42, `big` 17, `long` 15, `dup` 4, `xapp` 45, `supp` 139, `skip` 0,
`mirror` 3, `guard%` 20, `unused` 0, `std` **ok**.

**The six WARNs are standing, and this is the entry to read before deciding one of them again.**
Each has been decided at least once above; H19's contribution is to say which are DONE and which
are unfinished, so a future close does not re-litigate all six every time.

| WARN | Reads | Status |
|---|---|---|
| `dup` 4 | `_gemini_generate` ×3 and the `render`/`banned_phrases`/`unknown_placeholders` trio | **DECIDED, PERMANENT** (fifth reading, H7). The metering seams tenancy rule 6 names, and one engine with two thin per-audience adapters. **Do not chase it to zero by renaming adapters.** |
| `mirror` 3 | `incomeWizard.ts` ×3 | **DECIDED, PARKED** (tenth reading, H10). A guard written today either fails on a disagreement nobody has ruled on or blesses one. Leaves the ledger when **TD-262** is settled, and whoever settles it writes the guard. |
| `long` 15 | 15 Python functions of 150+ lines | **ACCEPTED as baseline** (2026-09-18). Never had a target; ratcheted, not chased. |
| `big` 17 | files over 1,000 lines | **MISSED — the target was 12.** Eight left, nine remain; four nobody scoped, three a move cannot help, two are eligibility and money. The split table is empty, so **nothing is waiting**: this is a Phase 4b when somebody wants one. See the arc's closing retrospective. |
| `guard%` 20 | 33 of 163 web test files read source text | **THE READING NO LONGER MEASURES WHAT IT WAS BUILT TO MEASURE**, and the target (12) was missed in the wrong direction. Fifteen of the number are the drift tests H9/H10 wrote as the prescribed CURE for unguarded mirrors. The fix (exclude `*Drift.test.ts`, report `drift` separately) is in the tenth reading above and is now **TD-284**. Until it lands, a WARN here is expected and explained; a FAIL (a jump over 5 in one sprint) is still a real signal. |
| `fix%` 42 | 305 fix / 418 feat, 90 days | **CANNOT HAVE MOVED.** It is a ratio over a 90-day commit window and the arc is three days long. **It is the reading that answers the owner's original question, and it can only be read again in December.** Part of TD-284. |

**One decision, and it is about this document rather than about the code.** `big`, `guard%` and
`fix%` are the three arc targets **no test anywhere enforces** — they WARN, and a WARN is a triage
item. All three are the ones that were missed or moved the wrong way, while the twelve standards
that ARE tests in the deploy gate held for three days without anybody remembering them. *Decision:
**raise TD-284**, not accept* — per `code-health-audit.md`, a third consecutive accept of the same
WARN is a TD entry, and `guard%` has now been accepted at the ninth, tenth and (implicitly) every
reading since. The entry says which of the three can be ratcheted, which cannot, and why.

**⚠ One thing this run showed by accident, and it is worth knowing before anybody quotes
`td_open`.** H19 added TD-284 to the register and `td_open` **did not move** — it reads 91 before
and after. The tool counts entries by a DEFINING LINE shaped `### [TD-NNN] …`, and every entry
raised since TD-274 has been written as a BULLET in the curated list near the top of
`docs/technical-debt.md`, which is the house pattern the arc itself followed. So **eleven current
entries (TD-274 to TD-284) are invisible to this reading**, and `td_open` 84 → 91 across an arc
that raised about two dozen is an undercount, not a measure of restraint. *Decision: recorded here
rather than raised, because it is a property of the register's format and not of the code* — the
Consolidation Review's Open Items Index is where the register is counted **by reading**, and
`code-health-audit.md` already says `td_open` is not a score. Fix it in the register (give each
bullet a heading) or in the tool, whichever the next `system-audit.md` pass prefers.

**Not a reading, and the reason this entry exists:** the arc that produced every row above is
closed. Its retrospective is the last section of
`docs/plans/2026-09-18-code-health-roadmap.md`, and the header of this file now describes what is
enforced and where.

### 2026-09-20 (TD-272) — `std: FAIL` is the TOOL, and here is the exact line to change

A read-only run after TD-272 shipped: **every other reading delta 0** (`fix%` 42, `big` 21, `long`
15, `dup` 4, `xapp` 46, `supp` 139, `skip` 0, `mirror` 3, `guard%` 19, `td_open` 92, `unused` 0),
and **`std` FAIL**, twice, both lines reading
`budget.eslint_disable_without_reason: gained "src/components/ScholarshipDocuments/IncomeWizard.tsx::react-hooks/exhaustive-deps::N"`.

**That is a false FAIL and it is the fifth in a row of the same kind.** `loosened` grew a rename
exception on 2026-09-20 for a DICT budget entry (H11's file split), but the LIST branch has none —
it still reports every new member of a JSON array as `gained`. The two ledgers that are arrays,
`eslint_disable_without_reason` and `unguarded_mirrors`, are exactly the ones whose keys sit INSIDE
a moved body, so they are the ones a Phase-4 move relabels. **Raised as TD-274**, with the fix
stated: give the list branch the same three guards the dict branch has — a member left the same
list in the same step, the list did not grow, and (there being no number in a string ledger) one
arrived for each that left — and record it through `notes` exactly as the dict branch does.

Accepted for this change **only because the in-repo standard is the stricter of the two and it is
green**: `_moved` refuses a relabel that merges, invents, over-budgets or names a file that is not
in the tree, and nine bite-checks prove each refusal. The external tool is agreeing with an older
rule than the repo now has.

### 2026-09-20 (twelfth reading) — H12: `views_admin` wave 2; `big` falls, and `xapp` changes meaning

Read-only (`--write` was excluded by the brief). **0 FAIL, 6 WARN — the same six as the eleventh
reading.** `std` reads **ok**, so the tool fix the lead built after H11 works on a real split: the
oversize entry for `views_admin/__init__.py` was REMOVED (the root is 154 lines, under the
standard) and `loosened()` passed it in silence, as a tightening should be.

- **`big` 25 → 24.** `views_admin/__init__.py` left the over-1,000-lines list. This is the honest
  reading for this sprint and the one the roadmap asked for. `hot#1` is unchanged at
  `admin-api.ts` 107.1 and is still not evidence of anything here (see the H11 note below).
- **⚠ `xapp` 133 → 135 (+2), inside `TOL_COUNT` so it does not FAIL — but it is a real +2 and is
  recorded here rather than passed over.** *Decision: ACCEPTED, with the arithmetic.* The old root
  carried exactly two module-level imports into `apps.courses`:
  `from apps.courses.models import PartnerAdmin, PartnerOrganisation` and
  `from apps.courses.search import apply_people_search`. Those two lines fed **four** call sites
  that the split put in four different modules — `AdminScopeListView` and
  `AdminAssignableAdminsView` (`lifecycle.py`), `_ReviewersBase` (`reviewers.py`),
  `AdminAssignReviewerView` (`verdict.py`) and the people-search in `applications.py`. Four
  modules, four import lines, two lines removed from the root: 133 − 2 + 4 = 135.
  - **H11's rule was applied first and it removed nothing this time.** Every one of the other 22
    `apps.courses` imports in the package already sits inside the function that uses it, and each
    was checked against its own body before a header line was written; no header import is
    redundant, and no import was left behind in the root (the root has no imports at all now).
  - *Why it was not engineered away.* Two routes would have held the number at 133 and both were
    rejected: re-exporting `PartnerAdmin` through `base.py` (which hides a real dependency behind
    the org-fence module and makes `base.py` an import hub it is not), and regrouping four views
    into one module purely to share one import line (which would have made `reviewers.py` a
    four-span grab-bag of 640 lines). **A number held by hiding the thing it measures is worse
    than a number that went up honestly.**
  - *Proposed (not made — `Settings/_tools` was out of this sprint's scope):* `m_cross_app_imports`
    counts import STATEMENTS, so a pure file split can only ever inflate it, and the more
    faithfully a package is decomposed the worse it reads. Counting distinct `(app → app, name)`
    EDGES per source app would have read 133 → 133 here, because the same two names are read by
    the same four call sites as before. Raised as **TD-268**.
  - **✅ BUILT BY THE LEAD THE SAME DAY, before this row was recorded. TD-268 is resolved.**
    `xapp` is now the number of distinct `(from app → to app, imported name)` edges, and the old
    statement count stays beside it in the detail (`46 edges (133 import statements)`), because a
    name pulled in from twenty places is still worth seeing. Two cases pin it in
    `Settings/_tools/tests/test_code_health.py`: one module split into six must not move the
    reading, and reaching for a second name must. **⚠ THE TREND STEPS 133 → 46 AT THIS ROW AND
    THAT IS THE DEFINITION, NOT THE CODE.** Nothing was decoupled today. Read no improvement into
    it, and compare later rows only with rows from 2026-09-20 onward.
- **Everything else delta 0**, `supp` 139, `skip` 0, `unused` 0, `dup` 4, `long` 15, `mirror` 3,
  `guard%` 19, `fix%` 42.

### 2026-09-20 (eleventh reading) — H11: `views_admin.py` is a package; `std` FAILs on a rename

Read-only (`--write` was excluded by the brief). **One FAIL: `std`, and it is the tool reading a
ledger-key RENAME as a new exemption.** Every other reading is unchanged or better. No behaviour
changed: the ten moved bodies are byte-identical to the lines they came from, proved mechanically.

- **`hot#1` 273.8 → 107.1 (−61%).** `views_admin.py` (8,556 lines × 32 fix commits) left the table
  and `admin-api.ts` is now the worst file. *Decision: ACCEPT the reading, but do NOT read it as a
  61% reduction in risk.* `m_hotspots` counts fix commits by PATH, from `ctx.commits()`, with no
  rename following. `views_admin/__init__.py` is 5,093 lines of the same code and scores **zero**
  because no commit has ever touched that path. The honest figure is the one the roadmap asked for
  — the file that carried the risk is 40% smaller, and 3,532 of its lines now sit in ten modules
  averaging 370 — and the tool will re-learn the truth over the next 90 days as fixes land on the
  new paths. **H12's acceptance ("`hot#1` under 100") is therefore already nearly met by the rename
  alone and should not be treated as evidence of anything.**
  - *Proposed (not made — this sprint's brief excluded `Settings/_tools`):* `m_hotspots` should walk
    `git log --follow`, or at minimum attribute a deleted path's fixes to the file that replaced it.
    Until then, **every Phase-4 sprint will show a hotspot vanishing rather than shrinking**, which
    is the most flattering possible error and the one worth naming out loud.
- **⚠ `std` ok → FAIL, and it is the tool, not the change.** `loosened()` compares the `budget`
  block key by key: a key that disappears is a tightening and is silent, a key that appears is
  reported as "a NEW entry". A file split necessarily does both at once —
  `apps/scholarship/views_admin.py` became `apps/scholarship/views_admin/__init__.py` — so the one
  operation the in-repo standard's own failure message PRESCRIBES ("SPLIT IT into modules") is the
  operation the sprint-close tool refuses.
  - **✅ FIXED THE SAME DAY, in the tool, before this row was recorded.** The lead took the
    proposal below and built it: `loosened()` now treats an added key as a RENAME, and passes it
    in silence but not unrecorded, only when a key left the same list in the same step, the new
    number is no bigger than the biggest that left, and neither the list's total nor its length
    rose. Debt cannot grow through a rename, so the guard keeps its teeth. Six cases in
    `Settings/_tools/tests/test_code_health.py` pin it — one rename that must pass and four
    disguises that must still fail — and the rule was bite-checked (broken → red, restored
    byte-identical). **`std` reads ok, and H12, H13, H15 and H16 will not need this paragraph.**
  - *Decision as first recorded (now superseded): ACCEPTED, with the reason recorded in three
    places* — the `_history` note in
    `halatuju_api/code-standards.json`, the re-pin comment above `BASELINE_SHA256`, and the H11
    retrospective. Nothing was raised: the baseline keeps 8547 (the same file, at a new path), the
    budget falls 8547 → 5093, and **no ledger gained a member** — all ten new submodules are under
    the 600-line standard on purpose, which is why `requests` is two modules and the gift domain is
    three rather than one each.
  - *The proposal that was built:* `loosened()` should pair a removed key with an added one whose
    VALUE is lower and report a rename rather than an addition. Left standing here because the
    reasoning is the lesson: four acceptances in a row for a guard that is right about nothing in
    any of them is how a guard stops being read, and that is why it was fixed instead.
- **`xapp` held at 133 — and this took a deliberate decision.** The first cut repeated
  `from apps.courses.models import PartnerOrganisation` in three new modules and moved
  `PartnerAdminMixin` into `base.py` while leaving it in the root, reading **137**. The three
  repeats were redundant (each of those bodies already imports it inside the function that uses it,
  exactly as before the move) and the root's `PartnerAdminMixin` line was dead the moment
  `_AdminBase` left. *Decision: a split may not widen the app boundary. `base.py` is the only new
  module that imports from `apps.courses`, and it does so with the line the root gave up.*
- **`big` held at 25** — one oversize file swapped for another, as expected in wave 1. The package
  root leaves the list at H12.
- **`td_open` −1**, and **TD-267 raised** (three module-level imports in the old file that nothing
  has used for some time — found by the move, not caused by it, and deliberately not fixed).
- All other readings delta 0: `fix%` 42, `long` 15, `dup` 4, `supp` 139, `skip` 0, `mirror` 3,
  `guard%` 19, `unused` 0.

### 2026-09-19 (tenth reading) — H10: the mirror ledger is down to a documented exception

`--full`, read-only (the reading itself is the lead's `--write`). **No FAILs.** No production code
changed — nine drift test files, one helper extended, 38 comment blocks edited.
- **`mirror` 41 → 3 (−38).** 22 entries gained a drift test; 16 were comments that did not describe
  a copied rule and were reworded honestly. *Decision: the standard's target (0) is treated as MET,
  with a named exception.* The three that remain are `incomeWizard.ts` — the income rule, where
  TD-262 pins eleven homes disagreeing in sixteen places, several awaiting an owner ruling. A guard
  written today either fails on a disagreement nobody has ruled on, or passes and blesses one. The
  reason is recorded at the top of that file and beside the entries in `code-standards.json`, and
  it names the condition that releases them.
- **⚠ `guard% 15 → 19` — INSIDE TOLERANCE (+4 of 5), but now OVER its 15% WARN line, and this is
  the reading that needs a decision rather than an acceptance.** H9's review said exactly this
  would happen and named the question: *which of these could be a rendered or behavioural test
  instead?* The answer, having written fifteen of them: **none of the cross-language ones.** A rule
  that lives in a `.py` constant and a `.ts` constant has no runtime seam a jest test can reach;
  reading the source IS the instrument, and the alternative is the comment that rotted.
  - *Decision: ACCEPT the reading, and PROMOTE a change to the tool.* `guard%` was set at 15% to
    watch a specific bad habit — a test asserting a SHAPE where it could have asserted a
    BEHAVIOUR. The 15 drift tests are not that habit; they are the cure for a different one, and
    they now make up most of the number, so the reading no longer measures what it was built to
    measure.
  - *Proposed (not made — H10's brief excluded `Settings/_tools`):* `m_guard_share` should exclude
    files matching `*Drift.test.ts` and report them as a separate `drift` count, OR the threshold
    should rise with a note. Either way the two habits must be counted apart, because one is debt
    and the other is its repayment. **Until that lands, `guard%` WARN on HalaTuju is expected and
    explained here; a FAIL (a jump over 5 points in one sprint) is still a real signal.**
- **`td_open` +2** — TD-266 (the admin/student `ResolutionItem` pair has drifted; ONE serializer
  feeds both) and TD-265 (a finance column nothing renders). Both found by characterising before
  guarding; neither would ever have failed a test or thrown an error. *Decision: TD-266 is an
  ordinary next-sprint job (~1h, delete one copy, with the cockpit's rendered tests as the net);
  TD-265 is a design call — a per-row column, or the page header, now that the breadcrumb scopes
  the page.*
- All other readings delta 0; `std` ok. **PHASE 3 COMPLETE** — the "stabilised" checkpoint summary
  for the owner is in the roadmap.

### 2026-09-19 (ninth reading) — H9: the decision gates are drift-tested

`--full`, read-only (the reading itself is the lead's `--write`). **No FAILs.** No production code
changed — six drift test files, one shared test reader, seventeen comment blocks marked.
- **`mirror` — NEW READING, 41.** Front-end `src/lib` comments claiming a rule is mirrored, with no
  `drift-test:` marker. Added by this sprint at the roadmap's request, written to the same
  definition as `codeStandards.test.ts`, which is the authority; both read 41 on the day, so the
  tool's trend and the in-repo ledger are the same number. *Decision: promote* — H10's work list.
- **`unguarded_mirrors` 58 → 41** in `budget` (`baseline` untouched). The six rules H9 named were
  seventeen ledger entries; "rules" and "entries" are different units and the roadmap now says so.
- **`guard% 11 → 15` (+4, inside tolerance).** Two things, and only one of them is code.
  (a) Six new tests read the backend's source on purpose — that IS the H9 end state, and for a
  module-level constant it is the right instrument (a served constant could only fail at runtime;
  this fails in the deploy gate). *Accept, with the reason recorded in `docs/decisions.md`.*
  (b) The metric's definition was **widened** in the same sprint: it matched the literal
  `readFileSync`, so the six new tests — which delegate to `src/test/apiSource.ts` — were invisible
  to the reading that exists to watch them. `GUARD_SIGNALS` now counts a delegated read, dated in
  the source. Part of the step is the definition catching up, not the code getting worse.
  ⚠ **H10 adds ~15–20 more such tests. If `guard%` approaches the 15% WARN line, that is the
  signal to ask which of them could be a rendered or behavioural test instead** — the drift test is
  right for a constant and wrong for anything with a seam.
- **`td_open` +2** — TD-264 (medium, money path: the api and the web disagree on what a *digit* is
  on the payout account, and the api is the permissive side) and TD-263 (low). *Decision: TD-264 is
  the owner's — both candidate fixes change what the api accepts, and one of them needs a count of
  stored rows first.* Neither was found by a reading; both fell out of characterising before
  guarding, which is now three sprints running (H7's `_money`, H8's eleven homes, this).
- All other readings delta 0; `std` ok.

### 2026-09-19 (eighth reading) — TD-262 chunks 1–3 shipped

Plain run. No FAILs. Every reading delta 0 — the income work added small modules instead of growing
listed files (`docCategory.ts`, `incomeShown.ts`, `income_shown.py`).
- **Three files are at the edge of their allowance, and one function:** `src/lib/api.ts` (1 line
  left), `doc_parse.py` (1), `_verdict_income_salary` (1 of its +10), `view.tsx` (8). *Decision:
  promote* — H13 (api barrels) and H14 (cockpit panels) are the planned cures; `verdict_engine`'s
  salary branch wants splitting before TD-262 chunk R4 touches it.

### 2026-09-19 (seventh reading) — H8: Phase A delivered, Phase B stopped at its gate

Plain run. No FAILs. **No production code changed** — two characterisation test files.
- **td_open → +1** — **TD-262 (HIGH, eligibility):** the income rule has eleven homes, not four, and
  they disagree in sixteen places today. *Decision: owner's, step by step — every fix moves an
  eligibility answer.* This is the largest finding the arc has produced, and no reading could have
  found it: the numbers measure shape; only running the homes side by side measures agreement.
- **guard%** — one new web test reads source, to pin three module-private maps that have no seam.
  *Accept* — they are ledger pins, to be replaced by rendered tests once the owner rules.
- All other readings delta 0.

### 2026-09-19 (sixth reading) — TD-261 closed (on the owner's order)

Plain run. No FAILs. Not a roadmap sprint.
- **td_open 84 → 83** — TD-261 closed: five defects in money/figure helpers and three oddities,
  each fixed by EDITING its pinned characterisation row and seeing it red first.
- **`std` ok** — `doc_parse.py` 669 → 688 of 689 allowed: **one line of headroom left.** The next
  change to it splits the file first. Same standing as `src/lib/api.ts`.
- All other readings unchanged.

### 2026-09-19 (fifth reading) — H7 closed: `dup` 10 → 4

Plain run after sprint H7. No FAILs.
- **dup 10 → 4** — *done, and the four that remain are ACCEPTED, permanently.* `_gemini_generate` ×3
  are the metering seams tenancy rule 6 names; `render` / `banned_phrases` /
  `unknown_placeholders` ×3 are one engine and two thin per-audience adapters. The reading will
  keep WARNing at 4; that WARN is decided — do not chase it to zero by renaming adapters. The
  roadmap's target ("0 true duplicates") is met.
- **td_open 83 → 84** — **TD-261**: five defects in money/figure helpers found by characterising
  today's behaviour. *Decision: owner's — they change what money code returns.*
- **`std` ok** — six names left the budget; it tightened.
- All other WARNs unchanged; decisions stand as in the baseline.

### 2026-09-19 (fourth reading) — TD-254 + TD-259 closed (security, on the owner's order)

`--full`. No FAILs. Not a roadmap sprint; read because it touched the auth seam.
- **td_open 84 → 83** — TD-254 and TD-259 closed; **TD-260** raised (604 of 674 IC-holding students
  have no verified contact and support has no screen to help — two owner levers).
- **guard% 10 → 11** — *accept.* One new source-reading test, and it is a drift test between the
  api's refusal codes and the web's copy map — the kind the standards ask for.
- **`std` ok** — one budget moved and it tightened (`courses/views.py` 2,377 → 2,309).
- Flagged by the build, for the next sprint that touches it: `src/lib/api.ts` has **one line** of
  its +20 allowance left. H13 (the barrel split) is the planned cure; anything sooner splits first.

### 2026-09-19 (third reading) — H6 closed: Phase 2 complete; `guard%` 18 → 10

`--full` after sprint H6. No FAILs. **The first WARN to clear since the baseline.**
- **guard% 18 → 10** — *done; target was ≤ 12.* 25 source-reading web tests became 14 of 137. Four
  stopgap guards became mounts, eleven i18n guards became one. What remains reads source on
  purpose (brand, sandbox safety, IC padlock, ICU, the navigation and screenshot disk walks,
  soft-evidence drift, the standards test, theme) and is listed in `CLAUDE.md`.
- **td_open 83 → 84** — **TD-259** raised: eight i18n keys exist in no locale; four render raw on
  the IC-claim screen. **Decision: owner's, and to be fixed WITH TD-254 — the missing text is by
  accident hiding the holder's name.** Near-misses read: TD-003, TD-252 — open is right.
- Not a reading: the web suite fell 42 s → 21 s; the cockpit went from 0 rendered tests to 59.
- All other WARNs unchanged; decisions stand as in the baseline.

### 2026-09-19 (second reading) — H5 closed: the test factory; `std` holds

Plain run after sprint H5 (test code only). No FAILs.
- **`std` ok** — the api budget gained a whole new standard (`hand_built_application_fixtures`,
  154 files → 134). The tool first read that as a loosening; it is the opposite, and the tool was
  corrected the same day: a new top-level budget key is a new standard, a new ledger member is
  still a FAIL.
- **hot#1 290.6 → 273.5** — *no decision.* No source changed; the 90-day window moved a day and
  dropped old fixes from `views_admin.py`. The fall is time, not work. H11–H12 do the work.
- Not a reading: the suite fell from 174.6 s to 122.9 s, which is three-quarters of a build-minute
  back on every api deploy.
- All WARNs unchanged; decisions stand as in the baseline.

### 2026-09-19 — H4 closed: Phase 1 complete; a new reading, `std`

`--full` after sprint H4. No FAILs.
- **`std` — new reading, ok.** Compares each `code-standards.json` budget with the copy at the last
  recorded run's commit; FAILs if a limit rose or an exemption list gained a member. First reading
  of both files, so nothing to compare yet; from here on it holds the ratchet across history, which
  the in-repo tests (depth-1 deploy checkout) cannot.
- **guard% 17 → 18** — *accept.* The web standards test reads source by nature. H6 retires four
  text guards and pays it back.
- The tool's WARN list and the standards tests now agree by construction: the tests reuse this
  tool's definitions of source, test, long function, duplicated name and suppression. `big` reads 25
  here (over 1,000 lines) and 56 in the budgets (over 600) — a different threshold, on purpose.
- All other readings unchanged; decisions stand as in the baseline.

### 2026-09-18 (fifth reading) — H3 closed: three guards in, one real hole found

`--full` after sprint H3. No FAILs. No source reading moved — the sprint added guards, not code.
- **td_open 85 → 84** — three closed (TD-219, TD-240, TD-250), two raised: **TD-257** (22 endpoints
  no test drives) and **TD-258** (HIGH — the sponsor fund view sits outside the fence, and a mock
  donation endpoint is live). Near-misses read: TD-003, TD-252 — open is right.
- **TD-258 is the reading that matters and the tool cannot take it.** Numbers find growth; this
  was found by a guard scanning a file it had excused for two months. Decision: **promote, as a
  security fix ahead of H4** — the owner's call, and the freeze allows it.
- **TD-257 — promote to Phase 2** (after the H5 factory makes each endpoint test cheap).
- All WARNs unchanged; decisions stand as in the baseline.

### 2026-09-18 (fourth reading) — H2 closed: the gate is live; nothing in the code moved

Plain run after sprint H2 (config and one test file — no source changed). No FAILs.
- **td_open 83 → 85** — *expected.* Two entries raised by the sprint: **TD-255** (production
  builds on Node 18, past end of life; the dev box runs 24) and **TD-256** (an api test reads a
  docs file the api trigger ignores). Near-miss list unchanged and read: TD-003, TD-252 open is right.
- Not a reading the tool takes, but the point of the sprint: **tests now run before every deploy**
  (6,714 pytest + 2,354 jest in the first gated builds). First row of the roadmap's targets: done.
- All other readings unchanged; decisions stand as in the baseline.

### 2026-09-18 (third reading) — H1 closed: `unused` 4 → 0, `skip` 2 → 0

After sprint H1 of the roadmap. `--full`. No FAILs; nothing else moved.
- **unused 4 → 0** — *done.* Four packages removed, each proven unimported; `next build` exits 0.
- **skip 2 → 0** — *done.* One dead skip branch deleted; the email golden's regenerate mode now
  fails the run rather than skipping it. Three *runtime* skips remain and are honest: "real corpus
  not present on this machine".
- **A flaky test surfaced in the clean-room run** and was fixed (a sentinel a timestamp could
  contain). Not a reading the tool takes; noted because from H2 a flaky test blocks a deploy.
- All other WARNs unchanged; decisions stand as in the baseline.

### 2026-09-18 (second reading) — the type check is a gate again: tsc 24 → 0

Taken after the first act on the baseline (TD-221 closed). No FAILs.
- **tsc 24 → 0** — *done.* No suppressions. Seven config, fourteen test-side, three a real app-type
  drift (`StrCheck.current_status`). Any tsc error is now a regression: tolerance is zero.
- **td_open 84 → 83** — TD-221 carries its marker.
- **hot#1 +5.2 and xapp +1** — *accept.* Both came from another sprint's commits (Overview phase 2
  Sprint A) landing between the two readings, not from this change. Inside tolerance.
- Everything else unchanged; decisions stand as in the baseline below.

### 2026-09-18 — baseline: the bugs land in eight files, and nothing was measuring that

First reading. Nothing can FAIL on a first run, so every line below is a WARN read for the first
time. **No app code was changed** — the owner's ruling was *measure only*.

**Where the next bug is most likely (fixes in 90 days x size).** This is not blame; it is where a
test, a split or a choke-point pays back first.
1. `apps/scholarship/views_admin.py` — fixed **34 times** in 90 days and **8,393 lines** long. Its
   score (285) is nearly three times the next file. No person or agent can hold it in one head.
2. `halatuju-web/src/lib/admin-api.ts` — 25 fixes, 4,008 lines, imported by ~109 files: a change
   here touches a quarter of the web app.
3. `apps/scholarship/services.py` — 32 fixes, 2,931 lines.
4. `apps/scholarship/income_engine.py` — 29 fixes, 3,187 lines. Same family as TD-235 (the income
   rule has four homes).
5. `apps/scholarship/emails.py` — 14 fixes, 4,242 lines.
6. `halatuju-web/src/lib/officerCockpit.ts` — 28 fixes in 1,634 lines: the **densest** fix rate on
   the web side. Request #24 (today) was one of them.
7. `apps/scholarship/vision.py` and `views.py` — 18 and 17 fixes.
8. `admin/scholarship/[id]/view.tsx` — 3,587 lines, the largest component, 7 fixes.

**Decisions on the readings**
- **fix% 41** (300 fixes to 430 features; `refactor:` is 20 commits since June) — *accept as the
  baseline.* Four fixes for every six features is the owner's observation, in a number. It is the
  reading to watch; the ratchet FAILs at 47.
- **big 25 / long 16** — *accept as baseline; do not split files for the sake of a number.* A split
  is promoted only when a hotspot above is next touched by a sprint. Ratchet holds the line.
- **dup 10** — *candidate TD, owner to pick.* `_money` has **seven** homes in `scholarship`
  (`doc_parse`, `invoice_parsers`, `invoicing`, `import_vircle_csv`, `payments`, `sponsor_comms`,
  `sponsorship`), and `render` / `banned_phrases` / `unknown_placeholders` are a whole template
  trio copied three times. A money-format fix made in one copy is not made in the other six. This
  is the cheapest real risk on the list and it touches money — so it is a sprint, not a small change.
- **xapp 132** — `scholarship -> courses` 103 and the back-edge `courses -> scholarship` 25. *Accept;*
  the back-edge is the one to watch.
- **supp 139** — 80 `# noqa` (mostly the deliberate "a mirror must never break the write" broad
  excepts), 42 `eslint-disable` (33 are `exhaustive-deps`). *Accept as baseline.*
- **skip 2** — both golden-master tests skip themselves on the run *after* their baseline is
  regenerated: the least-supervised moment passes green. *Candidate TD, low.*
- **guard% 17** — 24 of 138 web tests assert on source TEXT. Some are right (brand, i18n). But
  today's #24 guard cried wolf on a CRLF and an earlier one was decorative. *Accept; watch.*
- **unused 4** — `next-intl`, `react-hook-form`, `tailwind-merge`, `@supabase/ssr`. *Candidate, 15 min.*
- **tsc 24** — ⚠ **new fact: all 24 errors are in TEST files (9 of them); the app code has none.**
  TD-221 calls this gate a no-op. It is one jest-types fix away from being a real gate at zero.
  *Candidate, promoted to the top of the list below.*
- **td_open 84 of 146 defined.** The hand count on this date said 86 of 140. The tool finds six
  more definitions (headings shaped `### ✅ [TD-197 — RESOLVED …]`, which the hand rule skipped)
  and reads four `— RESOLVED` titles with no date as resolved (TD-002, -015, -017, -213). Near-misses
  read by eye: TD-003 (*partially* resolved — open is right) and TD-252 (open is right).

**Gate holes found by the survey — candidates for the owner, none done here**
1. `tsc` fails on 24 test-file errors, so nobody reads it (TD-221). Fix the 9 test files → a real gate.
2. `package.json` has no `test` or `typecheck` script; `scripts/check-i18n.js` is wired to nothing.
   The four web gates exist only as lines in `CLAUDE.md`.
3. Nothing runs tests before a deploy: the api image build runs `collectstatic`, the web build runs
   `next build`. A red suite can ship.
4. `requirements.txt` pins by range, has no lock file, and does not list `pytest` — two builds a week
   apart install different code, and a fresh clone cannot run the suite.
5. Four unused npm packages.
6. No coverage is configured on either side, so "is this file tested?" has no answer.
