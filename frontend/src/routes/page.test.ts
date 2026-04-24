import { screen } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reviewFixture, statusFixture, summaryFixture } from '../test/fixtures'
import { renderPage } from '../test/render-page'
import OverviewPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getSummary: vi.fn(),
  getWeeklyReview: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

describe('OverviewPage', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.getWeeklyReview.mockResolvedValue(reviewFixture)
  })

  it('renders the weekly review and overage watch panels', async () => {
    renderPage(OverviewPage as never)

    expect(await screen.findByText('Weekly Review')).toBeInTheDocument()
    expect(screen.getByText('What Changed')).toBeInTheDocument()
    expect(screen.getByText('Needs Attention')).toBeInTheDocument()
    expect(screen.getByText('Recommended Actions')).toBeInTheDocument()
    expect(
      screen.getAllByText('Expenses / Groceries is over plan by $652.20 in 2026-03').length,
    ).toBeGreaterThan(0)
    expect(screen.getAllByText(/Run YNAB sync before relying on this review\./i).length).toBeGreaterThan(0)
    expect(await screen.findByText('Overage Watch')).toBeInTheDocument()
    expect(screen.getByText('Automation Health')).toBeInTheDocument()
    expect(screen.getAllByText('Reconciliation failed with 1 mismatches.').length).toBeGreaterThan(0)
    expect(screen.getByText('Expenses / Groceries')).toBeInTheDocument()
    expect(screen.getByText('Fun / Eat Out')).toBeInTheDocument()
    expect(screen.getAllByText(/Current target is lagging actual run rate/i)).toHaveLength(2)
  })
})
