export type ThemeMode = 'dark' | 'light'

export type AccentSlot =
  | 'blue'
  | 'purple'
  | 'green'
  | 'cyan'
  | 'yellow'
  | 'red'
  | 'teal'
  | 'orange'

export const ACCENT_SLOTS: AccentSlot[] = [
  'blue',
  'purple',
  'green',
  'cyan',
  'yellow',
  'red',
  'teal',
  'orange',
]

export interface ThemeTokens {
  background: string
  foreground: string
  card: string
  cardElevated: string
  surfaceInset: string
  popover: string
  popoverForeground: string
  primaryForeground: string
  secondary: string
  secondaryForeground: string
  muted: string
  mutedForeground: string
  accent: string
  accentForeground: string
  destructive: string
  border: string
  input: string
  chart2: string
  chart3: string
  chart4: string
  chart5: string
  bodyGradient: string
}

export interface Theme {
  id: string
  name: string
  mode: ThemeMode
  defaultAccent: AccentSlot
  tokens: ThemeTokens
  accents: Record<AccentSlot, string>
}

export const THEME_TOKEN_TO_CSS_VAR: Record<keyof ThemeTokens, string> = {
  background: '--background',
  foreground: '--foreground',
  card: '--card',
  cardElevated: '--card-elevated',
  surfaceInset: '--surface-inset',
  popover: '--popover',
  popoverForeground: '--popover-foreground',
  primaryForeground: '--primary-foreground',
  secondary: '--secondary',
  secondaryForeground: '--secondary-foreground',
  muted: '--muted',
  mutedForeground: '--muted-foreground',
  accent: '--accent',
  accentForeground: '--accent-foreground',
  destructive: '--destructive',
  border: '--border',
  input: '--input',
  chart2: '--chart-2',
  chart3: '--chart-3',
  chart4: '--chart-4',
  chart5: '--chart-5',
  bodyGradient: '--body-gradient',
}

export const STORAGE_THEME_KEY = 'finclaide.theme'
export const STORAGE_ACCENT_KEY = 'finclaide.accent'
