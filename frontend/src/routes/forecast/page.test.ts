import { screen, waitFor } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CashflowTimeline } from '$lib/api'

import { renderPage } from '../../test/render-page'
import ForecastPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  getCashflowTimeline: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

function makeTimeline(overrides: Partial<CashflowTimeline> = {}): CashflowTimeline {
  const baseMonths = Array.from({ length: 12 }, (_, i) => {
    const m = ((4 + i) % 12) + 1
    const y = i < 8 ? 2026 : 2027
    return {
      month: `${y}-${m.toString().padStart(2, '0')}`,
      inflows_milliunits: 1_000_000,
      outflows_milliunits: 800_000,
      obligation_lumps: [],
      top_outflow_categories: [],
      net_milliunits: 200_000,
      ending_balance_milliunits: 5_000_000 + i * 200_000,
    }
  })
  return {
    as_of_month: '2026-05',
    months_ahead: 12,
    starting_balance_milliunits: 5_000_000,
    months: baseMonths,
    lowest_balance: { month: '2026-05', balance_milliunits: 5_200_000 },
    first_negative_month: null,
    shortfall_drivers: null,
    ...overrides,
  }
}

describe('ForecastPage', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
  })

  it('renders the headline cards with cash on hand and lowest balance', async () => {
    apiMocks.getCashflowTimeline.mockResolvedValue(makeTimeline())
    renderPage(ForecastPage as never)
    await screen.findByText(/Cash on hand/i)
    expect(screen.getByText(/Lowest projected/i)).toBeInTheDocument()
    // "stays positive" message when no negative month.
    await waitFor(() => {
      expect(screen.getByText(/stays positive 12 months/i)).toBeInTheDocument()
    })
  })

  it('shows the rose alert when first_negative_month is set', async () => {
    apiMocks.getCashflowTimeline.mockResolvedValue(
      makeTimeline({
        first_negative_month: '2026-09',
        lowest_balance: { month: '2027-04', balance_milliunits: -2_000_000 },
        shortfall_drivers: [
          { group_name: 'Bills', category_name: 'Rent', total_milliunits: 4_000_000 },
        ],
      }),
    )
    renderPage(ForecastPage as never)
    await waitFor(() => {
      expect(screen.getByText(/Yes\b/)).toBeInTheDocument()
    })
    // "Sep 26" appears in both the headline and the shortfall-drivers
    // card; assert the alert headline contains the month text.
    expect(screen.getAllByText(/Sep 26/).length).toBeGreaterThan(0)
  })

  it('lists top shortfall drivers when first_negative_month is set', async () => {
    apiMocks.getCashflowTimeline.mockResolvedValue(
      makeTimeline({
        first_negative_month: '2026-09',
        lowest_balance: { month: '2027-04', balance_milliunits: -2_000_000 },
        shortfall_drivers: [
          { group_name: 'Bills', category_name: 'Rent', total_milliunits: 4_000_000 },
          { group_name: 'Expenses', category_name: 'Groceries', total_milliunits: 1_500_000 },
        ],
      }),
    )
    renderPage(ForecastPage as never)
    await waitFor(() => {
      expect(screen.getByText('Rent')).toBeInTheDocument()
    })
    expect(screen.getByText('Groceries')).toBeInTheDocument()
    expect(screen.getByText(/Top shortfall drivers/i)).toBeInTheDocument()
  })
})
