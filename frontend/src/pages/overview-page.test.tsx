import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { OverviewPage } from '@/pages/overview-page'
import { statusFixture, summaryFixture } from '@/test/fixtures'
import { renderWithProviders } from '@/test/test-utils'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getSummary: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    getStatus: apiMocks.getStatus,
    getSummary: apiMocks.getSummary,
  }
})

describe('OverviewPage', () => {
  beforeEach(() => {
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
  })

  it('renders the overage watch panel with watched categories', async () => {
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText('Overage Watch')).toBeInTheDocument()
    expect(screen.getByText('Automation Health')).toBeInTheDocument()
    expect(screen.getAllByText('Reconciliation failed with 1 mismatches.')).not.toHaveLength(0)
    expect(screen.getByText('Expenses / Groceries')).toBeInTheDocument()
    expect(screen.getByText('Fun / Eat Out')).toBeInTheDocument()
    expect(screen.getAllByText(/Suggested floor/i)).toHaveLength(2)
  })
})
