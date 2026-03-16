import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { OperationsPage } from '@/pages/operations-page'
import { statusFixture, summaryFixture } from '@/test/fixtures'
import { renderWithProviders } from '@/test/test-utils'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getSummary: vi.fn(),
  importBudget: vi.fn(),
  syncYnab: vi.fn(),
  reconcile: vi.fn(),
  refreshAll: vi.fn(),
  getErrorMessage: vi.fn((error: unknown) => (error instanceof Error ? error.message : 'Unexpected error')),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    ...apiMocks,
  }
})

describe('OperationsPage', () => {
  beforeEach(() => {
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.importBudget.mockResolvedValue({ row_count: 75 })
    apiMocks.syncYnab.mockResolvedValue({ transaction_count: 10 })
    apiMocks.reconcile.mockResolvedValue({ mismatch_count: 0 })
    apiMocks.refreshAll.mockResolvedValue({ ok: true })
  })

  it('runs budget import from the operations panel', async () => {
    renderWithProviders(<OperationsPage />)

    await screen.findByText('Operations')
    await userEvent.click(screen.getByRole('button', { name: 'Import Budget' }))

    await waitFor(() => {
      expect(apiMocks.importBudget).toHaveBeenCalledTimes(1)
    })
  })
})
