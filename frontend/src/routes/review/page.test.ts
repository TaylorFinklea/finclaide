import { screen } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reviewFixture, statusFixture, summaryFixture } from '../../test/fixtures'
import { renderPage } from '../../test/render-page'
import ReviewPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getSummary: vi.fn(),
  getWeeklyReview: vi.fn(),
  getYearEndProjection: vi.fn(),
  getCashflowTimeline: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

describe('ReviewPage', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.getWeeklyReview.mockResolvedValue(reviewFixture)
    apiMocks.getYearEndProjection.mockResolvedValue({
      as_of_month: '2026-03',
      categories: [],
      totals: { projected_annual_milliunits: 8830000, projected_variance_milliunits: 160000, planned_annual_milliunits: 8670000 },
    })
    apiMocks.getCashflowTimeline.mockResolvedValue({ months: [] })
  })

  it('renders the Quartz Review chrome with all four highlight tiles', async () => {
    renderPage(ReviewPage as never)

    expect(await screen.findByText(/Month so far/i)).toBeInTheDocument()
    expect(screen.getByText(/Projected close/i)).toBeInTheDocument()
    expect(screen.getByText(/Net cash flow/i)).toBeInTheDocument()
    expect(screen.getByText(/Runway/i)).toBeInTheDocument()
  })

  it('renders the four review sections', async () => {
    renderPage(ReviewPage as never)

    expect(await screen.findByText('Plan vs actual · by group')).toBeInTheDocument()
    expect(screen.getByText('What changed')).toBeInTheDocument()
    expect(screen.getByText('Needs attention')).toBeInTheDocument()
    expect(screen.getByText('Recommended actions')).toBeInTheDocument()
  })

  it('shows the week pill and weekday subtitle', async () => {
    renderPage(ReviewPage as never)

    expect(await screen.findByText(/Review · Week/)).toBeInTheDocument()
    expect(screen.getByText(/day \d+ of \d+/)).toBeInTheDocument()
  })
})
