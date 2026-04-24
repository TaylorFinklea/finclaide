import { screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { summaryFixture } from '../../test/fixtures'
import { renderPage } from '../../test/render-page'
import CategoriesPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  getSummary: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, getSummary: apiMocks.getSummary }
})

describe('CategoriesPage', () => {
  beforeEach(() => {
    apiMocks.getSummary.mockReset()
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
  })

  it('filters categories by search text', async () => {
    renderPage(CategoriesPage as never)

    expect(await screen.findByText('Rent')).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText('Search group or category'), 'invest')

    expect(screen.queryByText('Rent')).not.toBeInTheDocument()
    expect(screen.getByText('Investments')).toBeInTheDocument()
  })
})
