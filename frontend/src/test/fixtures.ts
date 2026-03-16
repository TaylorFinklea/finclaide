import type { StatusResponse, SummaryResponse, TransactionsPageResponse } from '@/lib/api'

export const statusFixture: StatusResponse = {
  plan_id: 'plan-123',
  budget_sheet: '2026 Budget',
  busy: false,
  current_operation: null,
  last_budget_import_at: '2026-03-15T12:00:00+00:00',
  last_budget_import_id: 5,
  last_ynab_sync_at: '2026-03-15T12:01:00+00:00',
  last_server_knowledge: 2334,
  last_reconcile_at: '2026-03-15T12:02:00+00:00',
  last_reconcile_status: 'success',
  latest_runs: {
    budget_import: {
      status: 'success',
      started_at: '2026-03-15T12:00:00+00:00',
      finished_at: '2026-03-15T12:00:02+00:00',
      details: { row_count: 75 },
    },
  },
}

export const summaryFixture: SummaryResponse = {
  as_of: '2026-03-15T12:05:00+00:00',
  plan_year: 2026,
  month: '2026-03',
  groups: [
    {
      group_name: 'Bills',
      planned_milliunits: 1200000,
      actual_milliunits: 1210000,
      variance_milliunits: 10000,
      categories: [
        {
          category_name: 'Rent',
          planned_milliunits: 1000000,
          actual_milliunits: 1000000,
          variance_milliunits: 0,
          current_balance_milliunits: 1200000,
          due_month: null,
          status: 'on_target',
        },
        {
          category_name: 'Utilities',
          planned_milliunits: 200000,
          actual_milliunits: 210000,
          variance_milliunits: 10000,
          current_balance_milliunits: 220000,
          due_month: null,
          status: 'over',
        },
      ],
    },
    {
      group_name: 'Savings',
      planned_milliunits: 300000,
      actual_milliunits: 200000,
      variance_milliunits: -100000,
      categories: [
        {
          category_name: 'Emergency',
          planned_milliunits: 200000,
          actual_milliunits: 200000,
          variance_milliunits: 0,
          current_balance_milliunits: 400000,
          due_month: 10,
          status: 'ahead',
        },
        {
          category_name: 'Investments',
          planned_milliunits: 100000,
          actual_milliunits: 0,
          variance_milliunits: -100000,
          current_balance_milliunits: 150000,
          due_month: null,
          status: 'under',
        },
      ],
    },
  ],
  recent_transactions: [
    {
      id: 'txn-1',
      date: '2026-03-07',
      payee_name: 'Transfer',
      memo: 'Emergency fund',
      amount_milliunits: -200000,
      group_name: 'Savings',
      category_name: 'Emergency',
    },
  ],
  mismatches: [],
  sync_status: statusFixture,
}

export const transactionsFixture: TransactionsPageResponse = {
  transactions: [
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
  total_count: 1,
  limit: 25,
  offset: 0,
}
