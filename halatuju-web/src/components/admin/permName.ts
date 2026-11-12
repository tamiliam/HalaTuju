/**
 * Sprint M2b: a permission key's name for the screen. Today's keys (`see_all`) have their own words
 * (`admin.perm.<key>.name`); a v2 page key (`sponsors.view`, since M2b stored beside them) reads
 * "<page>: <level>" — the part before the dot names the page, the part after it the level. The server
 * serves the keys (the editor's `v2_keys`, the chips' `permissions_added`, the history's `added`); this
 * only words them.
 */
export function permName(t: (key: string, params?: Record<string, string>) => string, key: string): string {
  const dot = key.indexOf('.')
  if (dot < 0) return t(`admin.perm.${key}.name`)
  return t('admin.permV2.name', {
    page: t(`admin.permV2.page.${key.slice(0, dot)}`),
    level: t(`admin.permV2.level.${key.slice(dot + 1)}`),
  })
}
