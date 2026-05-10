import { screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActivePlanResponse, ReconcilePreviewResponse } from '$lib/api'

import { renderPage } from '../test/render-page'
import ReconcilePreviewCard from './reconcile-preview-card.svelte'

const apiMocks = vi.hoisted(() => ({
  createPlanCategory: vi.fn(),
  updatePlanCategory: vi.fn(),
  deletePlanCategory: vi.fn(),
  applyPlanToYnab: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

const PLAN: ActivePlanResponse = {
  plan: {
    id: 4,
    plan_year: 2026,
    name: '2026 Budget',
    label: null,
    status: 'active',
    source: 'edited',
    created_at: '2026-04-01T00:00:00+00:00',
    updated_at: '2026-04-01T00:00:00+00:00',
    archived_at: null,
    source_import_id: 1,
  },
  blocks: {
    monthly: [
      {
        id: 100,
        plan_id: 4,
        group_name: 'Bills',
        category_name: '22nd - Claude',
        block: 'monthly',
        kind: 'outflow',
        tithe_percent: null,
        planned_milliunits: 250000,
        annual_target_milliunits: 200000,
        due_month: null,
        notes: null,
        created_at: '2026-04-01T00:00:00+00:00',
        updated_at: '2026-04-01T00:00:00+00:00',
      },
      {
        id: 101,
        plan_id: 4,
        group_name: 'Bills',
        category_name: 'Phone',
        block: 'monthly',
        kind: 'outflow',
        tithe_percent: null,
        planned_milliunits: 0,
        annual_target_milliunits: 0,
        due_month: null,
        notes: null,
        created_at: '2026-04-01T00:00:00+00:00',
        updated_at: '2026-04-01T00:00:00+00:00',
      },
    ],
    annual: [],
    one_time: [],
    stipends: [],
    savings: [],
  },
  totals: {
    monthly_milliunits: 250000,
    annual_milliunits: 0,
    one_time_milliunits: 0,
    stipends_milliunits: 0,
    savings_milliunits: 0,
    grand_total_milliunits: 250000,
  },
}

function previewWith({
  extra = [] as ReconcilePreviewResponse['extra_in_ynab'],
  missing = [] as ReconcilePreviewResponse['missing_in_ynab'],
}: {
  extra?: ReconcilePreviewResponse['extra_in_ynab']
  missing?: ReconcilePreviewResponse['missing_in_ynab']
} = {}): ReconcilePreviewResponse {
  return {
    previewed_at: '2026-05-03T20:00:00+00:00',
    planned_count: 2,
    ynab_count: 2,
    exact_matches: [],
    missing_in_ynab: missing,
    extra_in_ynab: extra,
    counts: {
      exact: 0,
      missing_in_ynab: missing.length,
      extra_in_ynab: extra.length,
    },
  }
}

describe('ReconcilePreviewCard actions', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
  })

  it('renders source-choice buttons for an extra_in_ynab item with a high-confidence suggestion', () => {
    const preview = previewWith({
      extra: [
        {
          group_name: 'Bills',
          category_name: '23rd - Claude',
          suggested_match: {
            group_name: 'Bills',
            category_name: '22nd - Claude',
            confidence: 0.95,
            plan_category_id: 100,
          },
        },
      ],
    })
    renderPage(ReconcilePreviewCard as never, {
      pageProps: { preview, plan: PLAN, isLoading: false, isError: false, error: null } as never,
    })
    expect(screen.getByRole('button', { name: /Use YNAB/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Use plan/i })).toBeInTheDocument()
    expect(screen.getByText(/22nd - Claude/i)).toBeInTheDocument()
    expect(screen.getByText(/95% confidence/i)).toBeInTheDocument()
  })

  it('clicking Use YNAB calls updatePlanCategory with the matched plan id', async () => {
    apiMocks.updatePlanCategory.mockResolvedValue({})
    const preview = previewWith({
      extra: [
        {
          group_name: 'Bills',
          category_name: '23rd - Claude',
          suggested_match: {
            group_name: 'Bills',
            category_name: '22nd - Claude',
            confidence: 0.95,
            plan_category_id: 100,
          },
        },
      ],
    })
    renderPage(ReconcilePreviewCard as never, {
      pageProps: { preview, plan: PLAN, isLoading: false, isError: false, error: null } as never,
    })
    await userEvent.click(screen.getByRole('button', { name: /Use YNAB/i }))
    await waitFor(() => {
      expect(apiMocks.updatePlanCategory).toHaveBeenCalledTimes(1)
    })
    const [categoryId, body] = apiMocks.updatePlanCategory.mock.calls[0]
    expect(categoryId).toBe(100)
    expect(body.rename).toEqual({ group_name: 'Bills', category_name: '23rd - Claude' })
  })

  it('clicking Use plan asks the backend to rename the YNAB category', async () => {
    apiMocks.applyPlanToYnab.mockResolvedValue({
      target: 'ynab',
      operation: 'rename_category',
      action: {},
      ynab_sync: {},
      reconcile: { mismatch_count: 0 },
      reconcile_error: null,
    })
    const preview = previewWith({
      extra: [
        {
          group_name: 'Bills',
          category_name: '23rd - Claude',
          suggested_match: {
            group_name: 'Bills',
            category_name: '22nd - Claude',
            confidence: 0.95,
            plan_category_id: 100,
          },
        },
      ],
    })
    renderPage(ReconcilePreviewCard as never, {
      pageProps: { preview, plan: PLAN, isLoading: false, isError: false, error: null } as never,
    })
    await userEvent.click(screen.getByRole('button', { name: /Use plan/i }))
    await waitFor(() => {
      expect(apiMocks.applyPlanToYnab).toHaveBeenCalledTimes(1)
    })
    expect(apiMocks.applyPlanToYnab.mock.calls[0][0]).toEqual({
      operation: 'rename_category',
      source: { group_name: 'Bills', category_name: '23rd - Claude' },
      target: { group_name: 'Bills', category_name: '22nd - Claude' },
    })
  })

  it('renders Add to plan for an extra item without a suggestion', () => {
    const preview = previewWith({
      extra: [
        {
          group_name: 'Expenses',
          category_name: 'Homeschool',
          suggested_match: null,
        },
      ],
    })
    renderPage(ReconcilePreviewCard as never, {
      pageProps: { preview, plan: PLAN, isLoading: false, isError: false, error: null } as never,
    })
    expect(screen.queryByRole('button', { name: /Use YNAB/i })).toBeNull()
    expect(screen.getByRole('button', { name: /Add to plan/i })).toBeInTheDocument()
  })

  it('clicking Add to plan POSTs a new plan_category at $0', async () => {
    apiMocks.createPlanCategory.mockResolvedValue({})
    const preview = previewWith({
      extra: [
        {
          group_name: 'Expenses',
          category_name: 'Homeschool',
          suggested_match: null,
        },
      ],
    })
    renderPage(ReconcilePreviewCard as never, {
      pageProps: { preview, plan: PLAN, isLoading: false, isError: false, error: null } as never,
    })
    await userEvent.click(screen.getByRole('button', { name: /Add to plan/i }))
    await waitFor(() => {
      expect(apiMocks.createPlanCategory).toHaveBeenCalledTimes(1)
    })
    const [body] = apiMocks.createPlanCategory.mock.calls[0]
    expect(body.group_name).toBe('Expenses')
    expect(body.category_name).toBe('Homeschool')
    expect(body.planned_milliunits).toBe(0)
    expect(body.annual_target_milliunits).toBe(0)
    // No Bills sibling; falls back to monthly.
    // Actually Expenses isn't represented in PLAN.blocks at all, so the
    // inferBlock fallback returns 'monthly'.
    expect(body.block).toBe('monthly')
  })

  it('clicking Delete on a $0 plan category fires DELETE without a modal', async () => {
    apiMocks.deletePlanCategory.mockResolvedValue(undefined)
    const preview = previewWith({
      missing: [
        {
          group_name: 'Bills',
          category_name: 'Phone', // Phone has planned 0 in PLAN
          suggested_match: null,
        },
      ],
    })
    renderPage(ReconcilePreviewCard as never, {
      pageProps: { preview, plan: PLAN, isLoading: false, isError: false, error: null } as never,
    })
    await userEvent.click(screen.getByRole('button', { name: /Delete from plan/i }))
    await waitFor(() => {
      expect(apiMocks.deletePlanCategory).toHaveBeenCalledTimes(1)
    })
    const [categoryId, planId] = apiMocks.deletePlanCategory.mock.calls[0]
    expect(categoryId).toBe(101)
    expect(planId).toBe(4)
  })

  it('clicking Create in YNAB asks the backend to create the missing category', async () => {
    apiMocks.applyPlanToYnab.mockResolvedValue({
      target: 'ynab',
      operation: 'create_category',
      action: {},
      ynab_sync: {},
      reconcile: { mismatch_count: 0 },
      reconcile_error: null,
    })
    const preview = previewWith({
      missing: [
        {
          group_name: 'Bills',
          category_name: 'Phone',
          suggested_match: null,
        },
      ],
    })
    renderPage(ReconcilePreviewCard as never, {
      pageProps: { preview, plan: PLAN, isLoading: false, isError: false, error: null } as never,
    })
    await userEvent.click(screen.getByRole('button', { name: /Create in YNAB/i }))
    await waitFor(() => {
      expect(apiMocks.applyPlanToYnab).toHaveBeenCalledTimes(1)
    })
    expect(apiMocks.applyPlanToYnab.mock.calls[0][0]).toEqual({
      operation: 'create_category',
      target: { group_name: 'Bills', category_name: 'Phone' },
    })
  })

  it('clicking Delete on a non-zero plan category opens the confirm modal', async () => {
    apiMocks.deletePlanCategory.mockResolvedValue(undefined)
    const preview = previewWith({
      missing: [
        {
          group_name: 'Bills',
          category_name: '22nd - Claude', // planned 250000 in PLAN
          suggested_match: null,
        },
      ],
    })
    renderPage(ReconcilePreviewCard as never, {
      pageProps: { preview, plan: PLAN, isLoading: false, isError: false, error: null } as never,
    })
    await userEvent.click(screen.getByRole('button', { name: /Delete from plan/i }))
    // A confirm dialog should appear; the API should NOT have been called yet.
    expect(apiMocks.deletePlanCategory).not.toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: /Delete category/i })).toBeInTheDocument()
  })
})
