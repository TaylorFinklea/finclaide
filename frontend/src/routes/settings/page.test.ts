import { screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { THEMES, getTheme } from '$lib/theme/themes'
import { renderPage } from '../../test/render-page'
import SettingsPage from './+page.svelte'

afterEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  document.documentElement.removeAttribute('data-accent')
  document.documentElement.style.cssText = ''
})

describe('SettingsPage', () => {
  it('renders all 12 themes by default', () => {
    renderPage(SettingsPage as never)
    for (const theme of THEMES) {
      expect(screen.getByText(theme.name)).toBeInTheDocument()
    }
  })

  it('filters by mode chip', async () => {
    renderPage(SettingsPage as never)
    const lightChip = document.querySelector(
      '[data-mode-chip="light"]',
    ) as HTMLButtonElement
    await userEvent.click(lightChip)
    // Light themes only — the dark Tokyo Night card should disappear.
    expect(screen.queryByText('Tokyo Night')).not.toBeInTheDocument()
    expect(screen.getByText('Catppuccin Latte')).toBeInTheDocument()
    expect(screen.getByText('Solarized Light')).toBeInTheDocument()
    expect(screen.getByText('Gruvbox Light')).toBeInTheDocument()
  })

  it('clicking a theme card sets data-theme on <html> and writes localStorage', async () => {
    renderPage(SettingsPage as never)
    const draculaCard = document.querySelector(
      '[data-theme-card="dracula"]',
    ) as HTMLButtonElement | null
    expect(draculaCard).toBeTruthy()
    await userEvent.click(draculaCard!)
    expect(document.documentElement.dataset.theme).toBe('dracula')
    expect(window.localStorage.getItem('finclaide.theme')).toBe('dracula')
  })

  it('clicking an accent slot updates --primary to that slot value and persists', async () => {
    renderPage(SettingsPage as never)
    // Switch to Tokyo Night first so we know the slot palette.
    const tokyoCard = document.querySelector(
      '[data-theme-card="tokyo-night"]',
    ) as HTMLButtonElement
    await userEvent.click(tokyoCard)

    const purpleSwatch = document.querySelector(
      '[data-accent-slot="purple"]',
    ) as HTMLButtonElement
    await userEvent.click(purpleSwatch)

    const expected = getTheme('tokyo-night').accents.purple
    expect(document.documentElement.style.getPropertyValue('--primary')).toBe(expected)
    expect(window.localStorage.getItem('finclaide.accent')).toBe('purple')
  })

  it('switching themes carries the accent slot when the new theme exposes it', async () => {
    renderPage(SettingsPage as never)
    // Pick green on Tokyo Night, then switch to Nord — Nord exposes green too.
    await userEvent.click(
      document.querySelector('[data-theme-card="tokyo-night"]') as HTMLButtonElement,
    )
    await userEvent.click(
      document.querySelector('[data-accent-slot="green"]') as HTMLButtonElement,
    )
    await userEvent.click(
      document.querySelector('[data-theme-card="nord"]') as HTMLButtonElement,
    )
    const expected = getTheme('nord').accents.green
    expect(document.documentElement.style.getPropertyValue('--primary')).toBe(expected)
  })
})
