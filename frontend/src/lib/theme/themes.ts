import type { Theme } from './types'

// Tokyo Night — canonical palette from the source theme.
// Reference: https://github.com/folke/tokyonight.nvim
// This is the new Finclaide default; the previous custom palette was retired
// because it lacked contrast.
const tokyoNight: Theme = {
  id: 'tokyo-night',
  name: 'Tokyo Night',
  mode: 'dark',
  defaultAccent: 'blue',
  tokens: {
    background: '#1a1b26',
    foreground: '#c0caf5',
    card: '#1f2335',
    cardElevated: '#24283b',
    surfaceInset: '#16161e',
    popover: '#1f2335',
    popoverForeground: '#c0caf5',
    primaryForeground: '#1a1b26',
    secondary: '#292e42',
    secondaryForeground: '#c0caf5',
    muted: '#1f2335',
    mutedForeground: '#a9b1d6',
    accent: '#292e42',
    accentForeground: '#c0caf5',
    destructive: '#f7768e',
    border: '#3b4261',
    input: '#24283b',
    chart2: '#9ece6a',
    chart3: '#e0af68',
    chart4: '#f7768e',
    chart5: '#bb9af7',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(122 162 247 / 0.08), transparent 45%), linear-gradient(180deg, #1a1b26, #16161e)',
  },
  accents: {
    blue: '#7aa2f7',
    purple: '#bb9af7',
    green: '#9ece6a',
    cyan: '#7dcfff',
    yellow: '#e0af68',
    red: '#f7768e',
    teal: '#73daca',
    orange: '#ff9e64',
  },
}

export const THEMES: Theme[] = [tokyoNight]

export const THEMES_BY_ID: Record<string, Theme> = Object.fromEntries(
  THEMES.map((theme) => [theme.id, theme]),
)

export const DEFAULT_THEME_ID = 'tokyo-night'

export function getTheme(id: string | null | undefined): Theme {
  if (id && THEMES_BY_ID[id]) {
    return THEMES_BY_ID[id]
  }
  return THEMES_BY_ID[DEFAULT_THEME_ID]
}
