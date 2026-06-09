# Partner-admin pagination — rollout plan

**Branch:** `feature/partner-pagination` (worktree, off `main`; not pushed)
**Why:** Adopt the MySkills-style server-side pagination the owner prefers.
Today the partner tables fetch *every* row and either slice in the browser
(Students — 672 rows, 67 page buttons) or never paginate at all (B40
Applications). This replaces both with one reusable pattern.

## Design decisions

- **Per-view, not global.** We deliberately do **not** set a global
  `DEFAULT_PAGINATION_CLASS` in `REST_FRAMEWORK`. HalaTuju has many list
  endpoints that return full lists by contract; a global default would silently
  break them (and the B40 table the reviewer track is editing). Pagination is
  opted into per view via `FlexiblePageNumberPagination`.
- **Envelope preserved.** `paginator.envelope(...)` keeps each view's existing
  top-level fields (e.g. `org_name`) and adds standard pagination metadata
  (`count`, `total_pages`, `page`, `page_size`, `next`, `previous`).
- **Reusable frontend control.** One stateless `<Pagination>` component +
  `pageWindow()` helper, dropped onto any admin table.
- **CSV export stays unpaginated** — it must dump every row.

## Stage 1 — Students table ✅ DONE (this branch)

| File | Change |
|------|--------|
| `halatuju_api/halatuju/pagination.py` | **New** `FlexiblePageNumberPagination` (page_size 25, `?page_size` up to 100) + `.envelope()` helper |
| `halatuju_api/apps/courses/views_admin.py` | `PartnerStudentListView` paginates via the helper |
| `halatuju_api/apps/courses/tests/test_student_pagination.py` | **New** 7 tests (default page, envelope, page 2, last-page remainder, custom size, max-cap, ordering) |
| `halatuju-web/src/components/Pagination.tsx` | **New** reusable control (windowed buttons + optional page-size selector) |
| `halatuju-web/src/lib/pagination.ts` + `__tests__/pagination.test.ts` | **New** `pageWindow()` helper + 7 jest tests |
| `halatuju-web/src/lib/admin-api.ts` | `StudentListData` gains pagination fields; `getPartnerStudents({page,pageSize}, opts)`; `DEFAULT_STUDENT_PAGE_SIZE` |
| `halatuju-web/src/app/admin/students/page.tsx` | Server-side paging; renders `<Pagination>`; client slicing removed |
| `messages/{en,ms,ta}.json` | One new key `admin.perPage` |

**Verified:** 23 courses pytest pass (incl. 7 new); 7 jest pass; `tsc --noEmit`
clean on all changed files.

## Stage 2 — B40 Applications table ⏳ DEFERRED

Deferred only to avoid colliding with the in-flight reviewer sprint, which is
actively editing the `scholarship` app. Apply this once that track pauses. The
component + backend helper already exist, so this is purely wiring.

### Backend — `apps/scholarship/views_admin.py` (`AdminApplicationListView`)

Current tail of `get()`:

```python
        data = AdminApplicationListSerializer(qs, many=True).data
        return Response({'applications': data, 'total_count': len(data)})
```

Replace with:

```python
        from halatuju.pagination import FlexiblePageNumberPagination  # or top-of-file import
        paginator = FlexiblePageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = AdminApplicationListSerializer(page, many=True).data
        return paginator.envelope(data, results_key='applications')
```

`qs` is already ordered (`-submitted_at`), so pagination is stable. The
`status` / `bucket` / `assigned` filters are applied **before** pagination, so
filtering + paging compose correctly. Keep `total_count` only if something else
reads it — otherwise callers should move to `count`.

### Frontend — `lib/admin-api.ts`

```ts
export interface AdminScholarshipListData {
  count: number
  total_pages: number
  page: number
  page_size: number
  next: string | null
  previous: string | null
  applications: AdminScholarshipListItem[]
}

export async function getScholarshipApplications(
  params: { bucket?: string; status?: string; assigned?: string; page?: number; pageSize?: number },
  options?: ApiOptions,
) {
  const qs = new URLSearchParams()
  if (params.bucket)   qs.set('bucket', params.bucket)
  if (params.status)   qs.set('status', params.status)
  if (params.assigned) qs.set('assigned', params.assigned)
  if (params.page && params.page > 1) qs.set('page', String(params.page))
  if (params.pageSize) qs.set('page_size', String(params.pageSize))
  return adminFetch<AdminScholarshipListData>(
    `/api/v1/admin/scholarship/applications/${qs.toString() ? `?${qs}` : ''}`,
    options,
  )
}
```

### Frontend — `app/admin/scholarship/page.tsx`

- Add `page` / `pageSize` state (default 25).
- **Reset `page` to 1 whenever a filter changes** (status/bucket/assigned) —
  otherwise you can land on "page 5 of 2".
- Fetch with `{ ...filters, page, pageSize }`; render `data.applications`.
- Drop in `<Pagination page={data.page} totalPages={data.total_pages}
  total={data.count} pageSize={data.page_size} onPageChange={setPage}
  pageSizeOptions={[10,25,50]} onPageSizeChange={(s)=>{setPageSize(s);setPage(1)}} />`.

### Tests
- Backend: clone `test_student_pagination.py` for the applications endpoint
  (default page, filter+page compose, custom size, cap).
- Frontend: `pageWindow` is already covered; add a hook/fetch test only if the
  page has existing coverage to extend.

### i18n
No new keys — reuse `admin.showingRange` / `admin.perPage`. (`showingRange`
reads "…of {total} students"; if that wording grates on the applications table,
add a neutral `admin.showingRangeItems` variant.)

## Merge / conflict notes
- Stage 1 touches `courses` + shared frontend — minimal overlap with the
  reviewer track (which lives in `scholarship`).
- Likely small merges at integration time: `CHANGELOG.md` `[Unreleased]` and,
  for Stage 2, `scholarship/views_admin.py` + `scholarship/page.tsx`.
- **Do not push** — HalaTuju push triggers a deploy and is owner-gated.
