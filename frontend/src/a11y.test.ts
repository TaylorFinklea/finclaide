import { render, screen, within } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LayoutHarness from './test/layout-harness.svelte'
import { reviewFixture, statusFixture, summaryFixture } from './test/fixtures'
import { resetMockPage } from './test/setup'
import { monthStore } from '$lib/stores/month.svelte'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getSummary: vi.fn(),
  getWeeklyReview: vi.fn(),
  getTransactions: vi.fn(),
  getRuns: vi.fn(),
  getRun: vi.fn(),
  getReconcilePreview: vi.fn(),
  importBudget: vi.fn(),
  syncYnab: vi.fn(),
  reconcile: vi.fn(),
  refreshAll: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

vi.mock('$components/ui/toaster.svelte', async () => import('./test/noop.svelte'))

describe('Accessibility smoke — header and navigation', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.getWeeklyReview.mockResolvedValue(reviewFixture)
    apiMocks.getTransactions.mockResolvedValue({
      transactions: [],
      total_count: 0,
      limit: 25,
      offset: 0,
    })
    apiMocks.getRuns.mockResolvedValue({ runs: [] })
    window.localStorage.setItem('finclaide:selected-month', '2026-03')
    monthStore.set('2026-03')
    resetMockPage()
  })

  it('exposes nav links with accessible names for every primary route', async () => {
    render(LayoutHarness)

    const nav = await screen.findByRole('navigation')
    expect(within(nav).getByRole('link', { name: /Overview/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Categories/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Transactions/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Operations/i })).toBeInTheDocument()
  })

  it('associates the month input with a visible label', async () => {
    render(LayoutHarness)

    const monthInput = await screen.findByLabelText(/month/i)
    expect(monthInput).toHaveAttribute('type', 'month')
    expect(monthInput).toHaveValue('2026-03')
  })

  it('labels the freshness chips with their status and staleness for screen readers', async () => {
    render(LayoutHarness)

    expect(await screen.findByLabelText(/Plan freshness: fresh/i)).toBeInTheDocument()
    expect(await screen.findByLabelText(/YNAB freshness: stale/i)).toBeInTheDocument()
  })

  it('surfaces the scheduled-refresh banner as a polite live region when last status is failed', async () => {
    render(LayoutHarness)

    const banner = await screen.findByRole('status')
    expect(banner).toHaveAttribute('aria-live', 'polite')
    expect(within(banner).getByText(/Scheduled refresh failed/i)).toBeInTheDocument()
  })

  it('renders the workspace heading so screen readers can land on the active month', async () => {
    render(LayoutHarness)

    expect(await screen.findByText('March 2026')).toBeInTheDocument()
  })
})
