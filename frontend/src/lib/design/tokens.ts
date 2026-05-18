/**
 * Quartz design tokens, typed.
 *
 * The single source of truth for the design system is themes.css. This module
 * mirrors the palette so TypeScript code (chart authors, sparklines, the AI
 * suggestion card) can grab the same hex value without parsing a CSS var at
 * runtime. Keep the two in sync — the lone responsibility of the
 * `tokens.test.ts` is to assert that every key here resolves to a CSS variable
 * present in themes.css.
 */

export const quartz = {
  bg: '#FAFAF9',
  surface: '#FFFFFF',
  surface2: '#F5F4F2',
  surface3: '#EFEDE9',
  line: '#EBE9E6',
  line2: '#DCDAD5',
  ink: '#1A1A1A',
  ink2: '#4F4F4F',
  ink3: '#8A8A85',
  ink4: '#B5B3AD',
  accent: '#4E46E5',
  accent2: '#6E64FF',
  accentSoft: '#EDEBFF',
  red: '#D14444',
  redSoft: '#FBECEC',
  amber: '#C68A21',
  amberSoft: '#FBF1DC',
  green: '#2F8A57',
  greenSoft: '#E7F2EC',
  blue: '#2A6FDB',
  blueSoft: '#E8F0FC',
} as const

export type QuartzToken = keyof typeof quartz

/**
 * Per-category accent colors. Plan / Review screens look up the category's
 * group name and render the swatch + bar in this color. The keys are matched
 * case-insensitively at the lookup site (see `accentForGroup`).
 */
export const categoryAccents: Record<string, string> = {
  housing: '#5B7CFA',
  food: '#E07A5F',
  transport: '#3E8C7E',
  health: '#B255C7',
  lifestyle: '#D9A441',
  saving: '#2E8540',
  savings: '#2E8540',
  income: '#2F8A57',
  taxes: '#8A8A85',
  giving: '#D14444',
  stipends: '#6E64FF',
}

/** Fallback used when a group has no explicit accent. */
export const defaultCategoryAccent = '#8A8A85'

export function accentForGroup(groupName: string | null | undefined): string {
  if (!groupName) return defaultCategoryAccent
  const key = groupName.trim().toLowerCase()
  return categoryAccents[key] ?? defaultCategoryAccent
}

/** Status palette for chips, severity badges, and pace indicators. */
export const status = {
  good: { fg: quartz.green, bg: quartz.greenSoft },
  warn: { fg: quartz.amber, bg: quartz.amberSoft },
  crit: { fg: quartz.red, bg: quartz.redSoft },
  info: { fg: quartz.blue, bg: quartz.blueSoft },
  neutral: { fg: quartz.ink3, bg: quartz.surface2 },
} as const

export type StatusKey = keyof typeof status
