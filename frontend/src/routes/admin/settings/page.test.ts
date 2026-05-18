import { render, screen } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'

import SettingsPage from './+page.svelte'

describe('SettingsPage', () => {
  it('renders the stub heading after the theme picker was removed', () => {
    render(SettingsPage)
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByText(/Quartz redesign/)).toBeInTheDocument()
  })
})
