# Release Notes — v1.33.0

**Date:** 2026-03-12
**Codename:** Unified Pre-U Backend & IPGM Integration

## Features Delivered

### Backend Pre-U Eligibility
All Matric/STPM eligibility logic has been moved from the Next.js frontend to the Django backend. The new `pathways.py` module is a pure Python port covering:
- 4 Matriculation tracks (Science, Engineering, Computer Science, Accounting)
- 2 STPM bidangs (Science, Social Science)
- Full merit calculation with mata gred thresholds

Eligible tracks are now returned in the `eligible_courses` API response alongside DB-sourced courses, with merit labels, display fields, and track metadata.

### Unified Pre-U Ranking
A new `calculate_matric_stpm_fit_score()` function in the ranking engine scores Matric/STPM entries using the same prestige + academic bonus + field preference + signal adjustment pipeline as Asasi courses.

### IPGM Campus Integration
All 27 Institut Pendidikan Guru (IPG) campuses across 6 zones have been added as institutions:
- Zon Utara (5): Perlis, Darulaman, Sultan Abdul Halim, Pulau Pinang, Tuanku Bainun
- Zon Tengah (5): Bahasa Melayu, Bahasa Antarabangsa, Ilmu Khas, Pendidikan Islam, Ipoh
- Zon Selatan (5): Pendidikan Teknik, Raja Melewar, Perempuan Melayu Melaka, Tun Hussein Onn, Temenggong Ibrahim
- Zon Timur (4): Kota Bharu, Sultan Mizan, Dato' Razali Ismail, Tengku Ampuan Afzan
- Zon Sabah (4): Gaya, Kent, Keningau, Tawau
- Zon Sarawak (4): Batu Lintang, Tun Abdul Razak, Rajang, Sarawak

All 73 PISMP courses are linked to all 27 campuses (1,971 offerings). Course-to-campus mapping will be refined when specific data becomes available.

### Pathway-Based Sort Order
The dashboard sort now uses `PATHWAY_PRIORITY` (keyed by pathway_type) instead of `SOURCE_TYPE_PRIORITY` (keyed by source_type), enabling correct ordering:

**Asasi High > Matric High > STPM High > UA Diploma High > Poly High > PISMP > KKOM High > Any Fair > ILJTM/ILKBS > Any Low**

## Behaviour Changes

- PISMP courses now show "27 institutions" instead of "0 institutions" on the dashboard
- Matric/STPM courses appear at positions 5-9 (after Asasi) instead of being buried in the middle
- Frontend no longer computes synthetic pathway entries — all eligibility flows through the backend API

## Known Issues

- 73 PISMP courses still lack course tags (needed for quiz-based ranking)
- 87 offerings still missing tuition fee data
- `#` marker in course names (indicating interview requirement) is displayed as-is — badge UI deferred
- 9 pre-existing JWT test failures (malformed test tokens, not production issue)

## Breaking Changes

None. The API response shape is unchanged — Matric/STPM entries use the same fields as other eligible courses.
