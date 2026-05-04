import { screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CashflowRecommendations } from '$lib/api'

import { renderPage } from '../test/render-page'
import ForecastRecommendationsCard from './forecast-recommendations-card.svelte'

const apiMocks = vi.hoisted(() => ({
  updatePlanCategory: vi.fn(),
  getActivePlan: vi.fn(),
}))

const navMocks = vi.hoisted(() => ({
  goto: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

vi.mock('$app/navigation', async () => {
  const actual = await vi.importActual<typeof import('$app/navigation')>('$app/navigation')
  return { ...actual, ...navMocks }
})

const RECS: CashflowRecommendations = {
  as_of_month: '2026-05',
  baseline_lowest_balance_milliunits: -2_000_000,
  baseline_first_negative_month: '2026-08',
  recommendations: [
    {
      kind: 'plan_calibration',
      category: {
        id: 42,
        group_name: 'Expenses',
        category_name: 'Groceries',
        block: 'monthly',
      },
      current_planned_milliunits: 300_000,
      suggested_planned_milliunits: 400_000,
      run_rate_milliunits: 400_000,
      monthly_delta_milliunits: 100_000,
      annual_impact_milliunits: 1_200_000,
      headline:
        'Expenses / Groceries: averaging $400/mo against $300 plan. Raise plan to $400.',
      rationale:
        '6-month run-rate is $400/mo, 33% over the $300/mo plan.',
      projected_impact: {
        lowest_balance_before_milliunits: -2_000_000,
        lowest_balance_after_milliunits: -3_200_000,
        first_negative_month_before: '2026-08',
        first_negative_month_after: '2026-08',
      },
    },
  ],
}

describe('ForecastRecommendationsCard', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    for (const mock of Object.values(navMocks)) mock.mockReset()
  })

  it('renders the recommendation with Apply and Project buttons', () => {
    renderPage(ForecastRecommendationsCard as never, {
      pageProps: { recommendations: RECS, isLoading: false, isError: false } as never,
    })
    expect(screen.getByText(/averaging \$400\/mo/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Apply/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Project/i })).toBeInTheDocument()
  })

  it('clicking Apply calls updatePlanCategory with the suggested amount', async () => {
    apiMocks.getActivePlan.mockResolvedValue({
      plan: { id: 4 },
      blocks: { monthly: [], annual: [], one_time: [], stipends: [], savings: [] },
      totals: {
        monthly_milliunits: 0,
        annual_milliunits: 0,
        one_time_milliunits: 0,
        stipends_milliunits: 0,
        savings_milliunits: 0,
        grand_total_milliunits: 0,
      },
    })
    apiMocks.updatePlanCategory.mockResolvedValue({})
    renderPage(ForecastRecommendationsCard as never, {
      pageProps: { recommendations: RECS, isLoading: false, isError: false } as never,
    })
    await userEvent.click(screen.getByRole('button', { name: /Apply/i }))
    await waitFor(() => {
      expect(apiMocks.updatePlanCategory).toHaveBeenCalledTimes(1)
    })
    const [categoryId, body] = apiMocks.updatePlanCategory.mock.calls[0]
    expect(categoryId).toBe(42)
    expect(body.plan_id).toBe(4)
    expect(body.planned_milliunits).toBe(400_000)
  })

  it('clicking Project navigates to /scenarios with axes query param', async () => {
    renderPage(ForecastRecommendationsCard as never, {
      pageProps: { recommendations: RECS, isLoading: false, isError: false } as never,
    })
    await userEvent.click(screen.getByRole('button', { name: /Project/i }))
    expect(navMocks.goto).toHaveBeenCalledTimes(1)
    const url = navMocks.goto.mock.calls[0][0] as string
    expect(url).toContain('/scenarios')
    expect(url).toContain('axes=42:33')
  })
})
