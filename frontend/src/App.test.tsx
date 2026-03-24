import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

import App from '@/App'
import { reviewFixture, statusFixture, summaryFixture } from '@/test/fixtures'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getSummary: vi.fn(),
  getWeeklyReview: vi.fn(),
  getTransactions: vi.fn(),
  importBudget: vi.fn(),
  syncYnab: vi.fn(),
  reconcile: vi.fn(),
  refreshAll: vi.fn(),
  getErrorMessage: vi.fn((error: unknown) => (error instanceof Error ? error.message : 'Unexpected error')),
}))

vi.mock('@/lib/api', async () => ({
  ...apiMocks,
}))

describe('App', () => {
  beforeEach(() => {
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.getWeeklyReview.mockResolvedValue(reviewFixture)
    apiMocks.getTransactions.mockResolvedValue({ transactions: [], total_count: 0, limit: 25, offset: 0 })
    window.localStorage.setItem('finclaide:selected-month', '2026-03')
    window.history.pushState({}, '', '/')
  })

  it('renders the overview workspace with navigation', async () => {
    render(<App />)

    expect(await screen.findByText('Finclaide')).toBeInTheDocument()
    expect(await screen.findByText('Plan vs Actual by Group')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Transactions/i })).toBeInTheDocument()
  })
})
