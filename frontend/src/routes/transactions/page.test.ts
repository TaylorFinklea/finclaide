import { screen, waitFor, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { TransactionsPageResponse } from '$lib/api'

import { summaryFixture } from '../../test/fixtures'
import { renderPage } from '../../test/render-page'
import TransactionsPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  getSummary: vi.fn(),
  getTransactions: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

function pageOf(
  transactions: TransactionsPageResponse['transactions'],
  total: number,
  offset: number,
): TransactionsPageResponse {
  return { transactions, total_count: total, limit: 25, offset }
}

const FIRST_PAGE = pageOf(
  [
    {
      id: 'txn-1',
      date: '2026-03-08',
      payee_name: 'Coffee Shop',
      memo: 'Latte',
      amount_milliunits: -7500,
      group_name: 'Expenses',
      category_name: 'Eat Out',
    },
    {
      id: 'txn-2',
      date: '2026-03-06',
      payee_name: 'Gas Station',
      memo: null,
      amount_milliunits: -160000,
      group_name: 'Expenses',
      category_name: 'Fuel',
    },
  ],
  60,
  0,
)

const SECOND_PAGE = pageOf(
  [
    {
      id: 'txn-30',
      date: '2026-02-20',
      payee_name: 'Whole Foods',
      memo: null,
      amount_milliunits: -94000,
      group_name: 'Expenses',
      category_name: 'Groceries',
    },
  ],
  60,
  25,
)

const FILTERED_BILLS = pageOf(
  [
    {
      id: 'txn-rent',
      date: '2026-03-01',
      payee_name: 'Landlord',
      memo: null,
      amount_milliunits: -1000000,
      group_name: 'Bills',
      category_name: 'Rent',
    },
  ],
  1,
  0,
)

describe('TransactionsPage', () => {
  beforeEach(() => {
    apiMocks.getSummary.mockReset()
    apiMocks.getTransactions.mockReset()
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.getTransactions.mockResolvedValue(FIRST_PAGE)
  })

  it('paginates forward and back through transaction history', async () => {
    renderPage(TransactionsPage as never)

    await screen.findByText('Coffee Shop')
    expect(screen.getByText('Showing 2 of 60 transactions')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()

    apiMocks.getTransactions.mockResolvedValueOnce(SECOND_PAGE)
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    await screen.findByText('Whole Foods')
    await waitFor(() => {
      expect(apiMocks.getTransactions).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 25, limit: 25 }),
      )
    })
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()

    apiMocks.getTransactions.mockResolvedValueOnce(FIRST_PAGE)
    await userEvent.click(screen.getByRole('button', { name: 'Previous' }))

    await screen.findByText('Coffee Shop')
    await waitFor(() => {
      expect(apiMocks.getTransactions).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 0 }),
      )
    })
  })

  it('filters by group and resets pagination offset', async () => {
    renderPage(TransactionsPage as never)

    await screen.findByText('Coffee Shop')

    apiMocks.getTransactions.mockResolvedValueOnce(FILTERED_BILLS)
    const groupSelect = screen.getAllByRole('combobox')[0] as HTMLSelectElement
    await userEvent.selectOptions(groupSelect, 'Bills')

    await screen.findByText('Landlord')
    await waitFor(() => {
      expect(apiMocks.getTransactions).toHaveBeenLastCalledWith(
        expect.objectContaining({ group: 'Bills', offset: 0 }),
      )
    })
  })

  it('opens a detail sheet when a row is clicked and closes it', async () => {
    renderPage(TransactionsPage as never)

    const row = (await screen.findByText('Coffee Shop')).closest('tr')
    expect(row).not.toBeNull()
    await userEvent.click(row!)

    const sheet = await screen.findByRole('dialog')
    expect(within(sheet).getByText('Coffee Shop')).toBeInTheDocument()
    expect(within(sheet).getByText('Latte')).toBeInTheDocument()
    expect(within(sheet).getByText('txn-1')).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })
})
