import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { CategoriesPage } from '@/pages/categories-page'
import { summaryFixture } from '@/test/fixtures'
import { renderWithProviders } from '@/test/test-utils'

const apiMocks = vi.hoisted(() => ({
  getSummary: vi.fn(),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    getSummary: apiMocks.getSummary,
  }
})

describe('CategoriesPage', () => {
  beforeEach(() => {
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
  })

  it('filters categories by search text', async () => {
    renderWithProviders(<CategoriesPage />)

    expect(await screen.findByText('Rent')).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText('Search group or category'), 'invest')

    expect(screen.queryByText('Rent')).not.toBeInTheDocument()
    expect(screen.getByText('Investments')).toBeInTheDocument()
  })
})
