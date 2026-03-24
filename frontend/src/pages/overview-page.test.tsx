import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { OverviewPage } from '@/pages/overview-page'
import { reviewFixture, statusFixture, summaryFixture } from '@/test/fixtures'
import { renderWithProviders } from '@/test/test-utils'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getSummary: vi.fn(),
  getWeeklyReview: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    getStatus: apiMocks.getStatus,
    getSummary: apiMocks.getSummary,
    getWeeklyReview: apiMocks.getWeeklyReview,
  }
})

describe('OverviewPage', () => {
  beforeEach(() => {
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.getWeeklyReview.mockResolvedValue(reviewFixture)
  })

  it('renders the weekly review and overage watch panels', async () => {
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText('Weekly Review')).toBeInTheDocument()
    expect(screen.getByText('What Changed')).toBeInTheDocument()
    expect(screen.getByText('Needs Attention')).toBeInTheDocument()
    expect(screen.getByText('Recommended Actions')).toBeInTheDocument()
    expect(screen.getAllByText('Expenses / Groceries is over plan by $652.20 in 2026-03')).not.toHaveLength(0)
    expect(screen.getAllByText(/Run YNAB sync before relying on this review./i)).not.toHaveLength(0)
    expect(await screen.findByText('Overage Watch')).toBeInTheDocument()
    expect(screen.getByText('Automation Health')).toBeInTheDocument()
    expect(screen.getAllByText('Reconciliation failed with 1 mismatches.')).not.toHaveLength(0)
    expect(screen.getByText('Expenses / Groceries')).toBeInTheDocument()
    expect(screen.getByText('Fun / Eat Out')).toBeInTheDocument()
    expect(screen.getAllByText(/Suggested floor/i)).toHaveLength(2)
  })
})
