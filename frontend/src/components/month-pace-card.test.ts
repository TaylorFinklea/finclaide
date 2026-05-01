import { render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { MonthPace } from '$lib/api'

import MonthPaceCard from './month-pace-card.svelte'

const baseTotals = {
  planned_milliunits: 0,
  actual_milliunits: 0,
  projected_month_end_milliunits: 0,
}

describe('MonthPaceCard', () => {
  it('renders the warming-up message when warming_up is true', () => {
    const pace: MonthPace = {
      month: '2026-04',
      days_elapsed: 1,
      days_total: 30,
      days_remaining: 29,
      warming_up: true,
      categories: [],
      totals: baseTotals,
    }
    render(MonthPaceCard as never, { props: { pace } as never })
    expect(
      screen.getByText(/Pace data warming up/i),
    ).toBeInTheDocument()
  })

  it('renders rows with status chips for surfaced categories', () => {
    const pace: MonthPace = {
      month: '2026-04',
      days_elapsed: 15,
      days_total: 30,
      days_remaining: 15,
      warming_up: false,
      categories: [
        {
          category_id: 1,
          group_name: 'Bills',
          category_name: 'Rent',
          block: 'monthly',
          planned_milliunits: 1_000_000,
          actual_milliunits: 700_000,
          pace_factor: 1.4,
          pace_status: 'over_pace',
          projected_month_end_milliunits: 1_400_000,
          projected_overage_milliunits: 400_000,
        },
      ],
      totals: baseTotals,
    }
    render(MonthPaceCard as never, { props: { pace } as never })
    expect(screen.getByText('Rent')).toBeInTheDocument()
    expect(screen.getByText('Over pace')).toBeInTheDocument()
  })

  it('expands beyond five rows when "Show all" is clicked', async () => {
    const categories = Array.from({ length: 7 }, (_, i) => ({
      category_id: i + 1,
      group_name: 'Bills',
      category_name: `Cat${i + 1}`,
      block: 'monthly' as const,
      planned_milliunits: 100_000,
      actual_milliunits: 80_000,
      pace_factor: 1.6,
      pace_status: 'at_risk' as const,
      projected_month_end_milliunits: 160_000,
      projected_overage_milliunits: 60_000,
    }))
    const pace: MonthPace = {
      month: '2026-04',
      days_elapsed: 15,
      days_total: 30,
      days_remaining: 15,
      warming_up: false,
      categories,
      totals: baseTotals,
    }
    render(MonthPaceCard as never, { props: { pace } as never })
    expect(screen.queryByText('Cat6')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Show all 7/i }))
    expect(screen.getByText('Cat6')).toBeInTheDocument()
  })
})
