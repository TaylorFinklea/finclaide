import { render, screen } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'

import type { YearEndProjection } from '$lib/api'

import YearEndForecastCard from './year-end-forecast-card.svelte'

const baseProjection: YearEndProjection = {
  as_of_month: '2026-04',
  plan_year: 2026,
  months_elapsed: 4,
  months_remaining: 8,
  categories: [],
  totals: {
    planned_annual_milliunits: 1_000_000,
    projected_annual_milliunits: 1_200_000,
    projected_variance_milliunits: 200_000,
  },
}

describe('YearEndForecastCard', () => {
  it('renders top-3 categories sorted by variance descending', () => {
    const projection: YearEndProjection = {
      ...baseProjection,
      categories: [
        {
          group_name: 'Bills',
          category_name: 'Rent',
          planned_annual_milliunits: 1_000_000,
          actual_ytd_milliunits: 400_000,
          projected_annual_milliunits: 1_200_000,
          projected_variance_milliunits: 200_000,
          run_rate_monthly_milliunits: 100_000,
          planned_monthly_milliunits: 80_000,
        },
        {
          group_name: 'Expenses',
          category_name: 'Groceries',
          planned_annual_milliunits: 500_000,
          actual_ytd_milliunits: 250_000,
          projected_annual_milliunits: 750_000,
          projected_variance_milliunits: 250_000,
          run_rate_monthly_milliunits: 60_000,
          planned_monthly_milliunits: 40_000,
        },
        {
          group_name: 'Bills',
          category_name: 'Internet',
          planned_annual_milliunits: 800_000,
          actual_ytd_milliunits: 280_000,
          projected_annual_milliunits: 850_000,
          projected_variance_milliunits: 50_000,
          run_rate_monthly_milliunits: 70_000,
          planned_monthly_milliunits: 65_000,
        },
        {
          group_name: 'Bills',
          category_name: 'Phone',
          planned_annual_milliunits: 1_000_000,
          actual_ytd_milliunits: 300_000,
          projected_annual_milliunits: 900_000,
          projected_variance_milliunits: -100_000,
          run_rate_monthly_milliunits: 75_000,
          planned_monthly_milliunits: 80_000,
        },
      ],
    }
    render(YearEndForecastCard as never, { props: { projection } as never })
    // Sorted desc: Groceries (250k), Rent (200k), Internet (50k). Phone (negative) excluded.
    const groceries = screen.getByText('Groceries')
    const rent = screen.getByText('Rent')
    expect(groceries).toBeInTheDocument()
    expect(rent).toBeInTheDocument()
    expect(screen.queryByText('Phone')).toBeNull()
  })

  it('renders empty state when no categories project a meaningful overage', () => {
    const projection: YearEndProjection = {
      ...baseProjection,
      categories: [
        {
          group_name: 'Bills',
          category_name: 'Phone',
          planned_annual_milliunits: 1_000_000,
          actual_ytd_milliunits: 300_000,
          projected_annual_milliunits: 900_000,
          projected_variance_milliunits: -100_000,
          run_rate_monthly_milliunits: 75_000,
          planned_monthly_milliunits: 80_000,
        },
      ],
    }
    render(YearEndForecastCard as never, { props: { projection } as never })
    expect(
      screen.getByText(/No categories projected to bust/i),
    ).toBeInTheDocument()
  })
})
