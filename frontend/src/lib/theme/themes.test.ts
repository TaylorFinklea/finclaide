import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

import { THEMES } from './themes'
import { ACCENT_SLOTS, THEME_TOKEN_TO_CSS_VAR, type ThemeTokens } from './types'

const themesCss = readFileSync(
  path.resolve(__dirname, '..', '..', 'themes.css'),
  'utf8',
)

function blockFor(themeId: string): string {
  const marker = `[data-theme='${themeId}']`
  const start = themesCss.indexOf(marker)
  if (start === -1) {
    throw new Error(
      `themes.css is missing a [data-theme='${themeId}'] block. ` +
        `Add one or remove the theme from themes.ts.`,
    )
  }
  const open = themesCss.indexOf('{', start)
  const close = themesCss.indexOf('}', open)
  return themesCss.slice(open + 1, close)
}

function extractValue(block: string, varName: string): string {
  // Match the var line, allowing multi-line values for things like body-gradient.
  const escaped = varName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`${escaped}\\s*:\\s*([\\s\\S]*?);`)
  const match = block.match(re)
  if (!match) {
    throw new Error(
      `themes.css is missing ${varName}. Update the [data-theme] block.`,
    )
  }
  return match[1].trim().replace(/\s+/g, ' ')
}

function normalize(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

describe('themes drift check', () => {
  for (const theme of THEMES) {
    describe(theme.id, () => {
      const block = blockFor(theme.id)

      for (const tokenKey of Object.keys(theme.tokens) as Array<keyof ThemeTokens>) {
        const cssVar = THEME_TOKEN_TO_CSS_VAR[tokenKey]
        it(`${cssVar} matches themes.ts ${tokenKey}`, () => {
          const cssValue = normalize(extractValue(block, cssVar))
          const tsValue = normalize(theme.tokens[tokenKey])
          expect(cssValue).toBe(tsValue)
        })
      }

      it('exposes all 8 accent slots', () => {
        for (const slot of ACCENT_SLOTS) {
          expect(theme.accents[slot]).toBeTruthy()
        }
      })

      it('block defines a default accent fallback for first paint', () => {
        // Before theme-service hydrates, --primary / --ring / --chart-1 must
        // resolve from themes.css (not be undefined).
        expect(extractValue(block, '--primary')).toBeTruthy()
        expect(extractValue(block, '--ring')).toBeTruthy()
        expect(extractValue(block, '--chart-1')).toBeTruthy()
      })

      it('default accent in themes.ts matches the --primary fallback', () => {
        const fallback = normalize(extractValue(block, '--primary'))
        const expected = normalize(theme.accents[theme.defaultAccent])
        expect(fallback).toBe(expected)
      })
    })
  }
})
