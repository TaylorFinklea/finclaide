import { writable, type Readable } from 'svelte/store'

import { DEFAULT_THEME_ID, THEMES_BY_ID, getTheme } from './themes'
import {
  ACCENT_SLOTS,
  STORAGE_ACCENT_KEY,
  STORAGE_THEME_KEY,
  THEME_TOKEN_TO_CSS_VAR,
  type AccentSlot,
  type Theme,
  type ThemeTokens,
} from './types'

export interface ThemeState {
  theme: Theme
  accent: AccentSlot
}

function readStoredAccent(theme: Theme): AccentSlot {
  if (typeof window === 'undefined') return theme.defaultAccent
  const raw = window.localStorage.getItem(STORAGE_ACCENT_KEY)
  if (raw && (ACCENT_SLOTS as string[]).includes(raw)) {
    return raw as AccentSlot
  }
  return theme.defaultAccent
}

function readStoredTheme(): Theme {
  if (typeof window === 'undefined') return getTheme(DEFAULT_THEME_ID)
  return getTheme(window.localStorage.getItem(STORAGE_THEME_KEY))
}

function applyToRoot(theme: Theme, accent: AccentSlot): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  for (const key of Object.keys(theme.tokens) as Array<keyof ThemeTokens>) {
    root.style.setProperty(THEME_TOKEN_TO_CSS_VAR[key], theme.tokens[key])
  }
  const accentValue = theme.accents[accent] ?? theme.accents[theme.defaultAccent]
  root.style.setProperty('--primary', accentValue)
  root.style.setProperty('--ring', accentValue)
  root.style.setProperty('--chart-1', accentValue)
  root.dataset.theme = theme.id
  root.dataset.accent = accent
  root.classList.toggle('dark', theme.mode === 'dark')
  root.classList.toggle('light', theme.mode === 'light')
  root.style.colorScheme = theme.mode
}

const initialTheme = readStoredTheme()
const initialAccent = readStoredAccent(initialTheme)

const store = writable<ThemeState>({ theme: initialTheme, accent: initialAccent })

export const themeState: Readable<ThemeState> = { subscribe: store.subscribe }

export function initThemeOnHydrate(): void {
  // The inline pre-hydrate script in app.html sets the data-theme attribute
  // and class for first paint. This call writes the full token set via JS so
  // dynamic accent changes (which aren't in the static themes.css) take effect.
  const theme = readStoredTheme()
  const accent = readStoredAccent(theme)
  applyToRoot(theme, accent)
  store.set({ theme, accent })
}

export function setTheme(themeId: string): void {
  const theme = THEMES_BY_ID[themeId]
  if (!theme) return
  const currentAccent = (() => {
    if (typeof window === 'undefined') return theme.defaultAccent
    const stored = window.localStorage.getItem(STORAGE_ACCENT_KEY)
    if (stored && (ACCENT_SLOTS as string[]).includes(stored)) {
      const slot = stored as AccentSlot
      // Carry the slot name across themes if the destination has it; otherwise
      // fall back to the destination theme's default.
      return theme.accents[slot] ? slot : theme.defaultAccent
    }
    return theme.defaultAccent
  })()
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_THEME_KEY, themeId)
  }
  applyToRoot(theme, currentAccent)
  store.set({ theme, accent: currentAccent })
}

export function setAccent(slot: AccentSlot): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_ACCENT_KEY, slot)
  }
  store.update((state) => {
    applyToRoot(state.theme, slot)
    return { ...state, accent: slot }
  })
}
