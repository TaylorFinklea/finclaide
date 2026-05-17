import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { accentForGroup, categoryAccents, defaultCategoryAccent, quartz, status } from './tokens'

const here = dirname(fileURLToPath(import.meta.url))
const themesCss = readFileSync(resolve(here, '../../themes.css'), 'utf8')

describe('Quartz tokens', () => {
  it('every JS token has a matching CSS variable in themes.css', () => {
    for (const [key, value] of Object.entries(quartz)) {
      // CSS var name is --q-{kebab-key}; e.g. surface2 -> --q-surface-2
      const cssVar = '--q-' + key.replace(/([a-z])([0-9])/g, '$1-$2').replace(/([A-Z])/g, '-$1').toLowerCase()
      expect(themesCss).toContain(cssVar)
      expect(themesCss).toContain(value)
    }
  })

  it('exposes a category accent for the canonical groups in the V3 mock', () => {
    expect(categoryAccents.housing).toBeDefined()
    expect(categoryAccents.food).toBeDefined()
    expect(categoryAccents.transport).toBeDefined()
    expect(categoryAccents.health).toBeDefined()
    expect(categoryAccents.lifestyle).toBeDefined()
    expect(categoryAccents.saving).toBeDefined()
  })

  it('accentForGroup is case-insensitive and falls back to the neutral swatch', () => {
    expect(accentForGroup('Housing')).toBe(categoryAccents.housing)
    expect(accentForGroup('LIFESTYLE')).toBe(categoryAccents.lifestyle)
    expect(accentForGroup('zzz-unknown')).toBe(defaultCategoryAccent)
    expect(accentForGroup(null)).toBe(defaultCategoryAccent)
    expect(accentForGroup(undefined)).toBe(defaultCategoryAccent)
  })

  it('status palette pairs every key with both fg and bg hex strings', () => {
    for (const key of Object.keys(status) as Array<keyof typeof status>) {
      expect(status[key].fg).toMatch(/^#[0-9A-Fa-f]{6}$/)
      expect(status[key].bg).toMatch(/^#[0-9A-Fa-f]{6}$/)
    }
  })
})
