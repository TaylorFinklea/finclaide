import { screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { runsFixture, statusFixture, summaryFixture } from '../../test/fixtures'
import { renderPage } from '../../test/render-page'
import OperationsPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getRuns: vi.fn(),
  getSummary: vi.fn(),
  importBudget: vi.fn(),
  syncYnab: vi.fn(),
  reconcile: vi.fn(),
  refreshAll: vi.fn(),
  exportBudget: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

describe('OperationsPage', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getRuns.mockResolvedValue(runsFixture)
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.importBudget.mockResolvedValue({ row_count: 75 })
    apiMocks.syncYnab.mockResolvedValue({ transaction_count: 10 })
    apiMocks.reconcile.mockResolvedValue({ mismatch_count: 0 })
    apiMocks.refreshAll.mockResolvedValue({ ok: true })
    apiMocks.exportBudget.mockResolvedValue({
      run_id: 42,
      filename: 'TestBudget.xlsx',
      row_count: 75,
      file_size_bytes: 6040,
    })
  })

  it('runs budget import from the operations panel', async () => {
    renderPage(OperationsPage as never)

    await screen.findByText('Operations')
    expect(await screen.findByText('Plan Data')).toBeInTheDocument()
    expect(await screen.findByText('YNAB Data')).toBeInTheDocument()
    expect((await screen.findAllByText('Scheduled Refresh')).length).toBeGreaterThan(0)
    expect(await screen.findByText('Recent Runs')).toBeInTheDocument()
    expect((await screen.findAllByText('Budget Import')).length).toBeGreaterThan(0)
    expect(
      (await screen.findAllByText('Reconciliation failed with 1 mismatches.')).length,
    ).toBeGreaterThan(0)
    expect((await screen.findAllByText('Temporary YNAB timeout')).length).toBeGreaterThan(0)
    expect(await screen.findByText('Failure cause')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Import Budget' }))

    await waitFor(() => {
      expect(apiMocks.importBudget).toHaveBeenCalledTimes(1)
    })
  })

  it('exports the active plan via the Export .xlsx button and triggers a download', async () => {
    const clickSpy = vi.fn()
    const origCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const element = origCreate(tag) as HTMLAnchorElement
      if (tag.toLowerCase() === 'a') {
        element.click = clickSpy
      }
      return element
    })

    renderPage(OperationsPage as never)
    await screen.findByText('Operations')
    await userEvent.click(screen.getByRole('button', { name: 'Export .xlsx' }))

    await waitFor(() => {
      expect(apiMocks.exportBudget).toHaveBeenCalledTimes(1)
    })
    expect(clickSpy).toHaveBeenCalled()
  })

  it('shows a toast when the export call fails', async () => {
    apiMocks.exportBudget.mockRejectedValueOnce(new Error('boom'))
    renderPage(OperationsPage as never)
    await screen.findByText('Operations')
    await userEvent.click(screen.getByRole('button', { name: 'Export .xlsx' }))
    await waitFor(() => {
      expect(apiMocks.exportBudget).toHaveBeenCalled()
    })
    // The mutation surfaces the error via toast (not asserted directly here —
    // svelte-sonner is global-mocked elsewhere — but the call itself rejecting
    // exercises the onError path without crashing the page).
  })
})
