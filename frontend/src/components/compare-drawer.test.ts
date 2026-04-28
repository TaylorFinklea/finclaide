import { screen, waitFor, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CompareResponse } from '$lib/api'

import { renderPage } from '../test/render-page'
import CompareDrawer from './compare-drawer.svelte'

const apiMocks = vi.hoisted(() => ({
  compareScenario: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

const fixture: CompareResponse = {
  scenario_id: 200,
  active_id: 1,
  window: {
    since: '2025-10',
    through: '2026-04',
    months: ['2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03'],
  },
  rows: [
    {
      category_id: 10,
      name: 'Bills / Rent',
      group: 'Bills',
      block: 'monthly',
      planned_active_milliunits: 1200000,
      planned_scenario_milliunits: 1500000,
      actuals_avg_6mo_milliunits: 1300000,
      vs_actuals_milliunits: 200000,
      vs_active_milliunits: 300000,
      sparkline: [1000000, 1100000, 1200000, 1300000, 1400000, 1500000],
    },
    {
      category_id: 11,
      name: 'Bills / Utilities',
      group: 'Bills',
      block: 'monthly',
      planned_active_milliunits: 200000,
      planned_scenario_milliunits: 150000,
      actuals_avg_6mo_milliunits: 180000,
      vs_actuals_milliunits: -30000,
      vs_active_milliunits: -50000,
      sparkline: [200000, 180000, 200000, 170000, 190000, 200000],
    },
  ],
  totals: {
    planned_active_milliunits: 1400000,
    planned_scenario_milliunits: 1650000,
    vs_active_milliunits: 250000,
  },
}

describe('CompareDrawer', () => {
  beforeEach(() => {
    apiMocks.compareScenario.mockReset()
  })

  it('renders a row with sparkline svg per result row', async () => {
    apiMocks.compareScenario.mockResolvedValue(fixture)
    renderPage(CompareDrawer as never, {
      pageProps: { open: true, scenarioId: 200, onClose: () => {} } as never,
    })
    await screen.findByText('Bills / Rent')
    const dialog = screen.getByLabelText('Compare table')
    const sparks = within(dialog).getAllByRole('img')
    expect(sparks).toHaveLength(2)
  })

  it('clicking the Δ active header toggles sort direction', async () => {
    apiMocks.compareScenario.mockResolvedValue(fixture)
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(CompareDrawer as never, {
      pageProps: { open: true, scenarioId: 200, onClose: () => {} } as never,
    })
    await screen.findByText('Bills / Rent')
    const tableContainer = screen.getByLabelText('Compare table')
    const deltaHeader = within(tableContainer).getByRole('columnheader', { name: /Δ active/i })
      .parentElement?.querySelector('th[onclick], th') as HTMLElement | null
    // Default sort: vs_active_milliunits desc — Rent first, Utilities second.
    let bodyRows = within(tableContainer).getAllByRole('row').slice(1)
    expect(within(bodyRows[0]).getByText('Bills / Rent')).toBeTruthy()
    // Click header twice (once selects, once toggles to asc on the same key).
    const headers = within(tableContainer).getAllByRole('columnheader')
    const deltaActive = headers.find((h) => /Δ active/i.test(h.textContent ?? ''))
    expect(deltaActive).toBeTruthy()
    await user.click(deltaActive!)
    bodyRows = within(tableContainer).getAllByRole('row').slice(1)
    // After one toggle from desc default, dir flips to asc — Utilities (-50k) before Rent (+300k).
    expect(within(bodyRows[0]).getByText('Bills / Utilities')).toBeTruthy()
    void deltaHeader
  })

  it('does not fetch when scenarioId is null', async () => {
    apiMocks.compareScenario.mockResolvedValue(fixture)
    renderPage(CompareDrawer as never, {
      pageProps: { open: true, scenarioId: null, onClose: () => {} } as never,
    })
    // Wait a tick to ensure no async fetch fires.
    await new Promise((r) => setTimeout(r, 10))
    expect(apiMocks.compareScenario).not.toHaveBeenCalled()
    expect(screen.getByText(/No scenario selected/i)).toBeInTheDocument()
  })

  it('shows error message when the request fails', async () => {
    apiMocks.compareScenario.mockRejectedValue(new Error('boom'))
    renderPage(CompareDrawer as never, {
      pageProps: { open: true, scenarioId: 200, onClose: () => {} } as never,
    })
    await waitFor(() => {
      expect(screen.getByText(/Could not load comparison/i)).toBeInTheDocument()
    })
  })
})
