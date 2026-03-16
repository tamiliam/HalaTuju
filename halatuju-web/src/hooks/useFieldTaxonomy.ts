'use client'

import { useState, useEffect } from 'react'
import { fetchFieldTaxonomy, type FieldTaxonomyEntry } from '@/lib/api'
import type { Locale } from '@/lib/i18n'

interface FieldOption {
  key: string
  label: string
}

interface FieldTaxonomyData {
  /** Map from field_key to image_slug */
  imageSlugMap: Map<string, string>
  /** Map from field_key to trilingual names */
  nameMap: Map<string, { en: string; ms: string; ta: string }>
  /** Flat list of all leaf field keys with localised labels, for dropdown */
  fieldOptions: FieldOption[]
  /** Whether taxonomy data has loaded */
  loaded: boolean
}

const SUPABASE_STORAGE = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images'

// Module-level cache so multiple components/pages share the same data
let cachedData: FieldTaxonomyData | null = null
let fetchPromise: Promise<FieldTaxonomyData> | null = null

function buildTaxonomyData(groups: FieldTaxonomyEntry[], locale: Locale): FieldTaxonomyData {
  const imageSlugMap = new Map<string, string>()
  const nameMap = new Map<string, { en: string; ms: string; ta: string }>()
  const fieldOptions: FieldOption[] = []

  const nameKey = `name_${locale}` as keyof FieldTaxonomyEntry

  for (const group of groups) {
    // Parent groups are not leaf fields — skip them for dropdown
    // but register their image_slug in case courses reference them
    imageSlugMap.set(group.key, group.image_slug)
    nameMap.set(group.key, { en: group.name_en, ms: group.name_ms, ta: group.name_ta })

    for (const child of group.children) {
      imageSlugMap.set(child.key, child.image_slug)
      nameMap.set(child.key, { en: child.name_en, ms: child.name_ms, ta: child.name_ta })
      fieldOptions.push({
        key: child.key,
        label: child[nameKey] as string,
      })
    }
  }

  return { imageSlugMap, nameMap, fieldOptions, loaded: true }
}

async function loadTaxonomy(locale: Locale): Promise<FieldTaxonomyData> {
  const { groups } = await fetchFieldTaxonomy()
  const data = buildTaxonomyData(groups, locale)
  cachedData = data
  return data
}

export function useFieldTaxonomy(locale: Locale = 'ms'): FieldTaxonomyData & {
  getImageUrl: (fieldKey: string | undefined) => string
  getFieldName: (fieldKey: string | undefined) => string
} {
  const [data, setData] = useState<FieldTaxonomyData>(
    cachedData || { imageSlugMap: new Map(), nameMap: new Map(), fieldOptions: [], loaded: false }
  )

  useEffect(() => {
    if (cachedData) {
      // Rebuild options for current locale (image/name maps are locale-independent)
      setData(cachedData)
      return
    }
    if (!fetchPromise) {
      fetchPromise = loadTaxonomy(locale)
    }
    fetchPromise.then(setData).catch(() => {
      // Taxonomy fetch failed — CourseCard falls back to default image
    })
  }, [locale])

  const getImageUrl = (fieldKey: string | undefined): string => {
    if (!fieldKey) return `${SUPABASE_STORAGE}/umum-kemanusiaan.png`
    const slug = data.imageSlugMap.get(fieldKey) || 'umum-kemanusiaan'
    return `${SUPABASE_STORAGE}/${slug}.png`
  }

  const getFieldName = (fieldKey: string | undefined): string => {
    if (!fieldKey) return ''
    const names = data.nameMap.get(fieldKey)
    if (!names) return fieldKey
    return names[locale] || names.ms || fieldKey
  }

  return { ...data, getImageUrl, getFieldName }
}
