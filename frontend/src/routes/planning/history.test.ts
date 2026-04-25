import { screen, waitFor, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActivePlanResponse, PlanCategory, PlanRevisionSummary } from '$lib/api'

import { statusFixture } from '../../test/fixtures'
import { renderPage } from '../../test/render-page'
import PlanningPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getActivePlan: vi.fn(),
  createPlanCategory: vi.fn(),
  updatePlanCategory: vi.fn(),
  deletePlanCategory: vi.fn(),
  listPlanRevisions: vi.fn(),
  getPlanRevision: vi.fn(),
  restorePlanRevision: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

function makeCategory(
  overrides: Partial<PlanCategory> &
    Pick<PlanCategory, 'id' | 'group_name' | 'category_name' | 'block'>,
): PlanCategory {
  return {
    plan_id: 1,
    planned_milliunits: 50000,
    annual_target_milliunits: 0,
    due_month: null,
    notes: null,
    created_at: '2026-04-18T00:00:00+00:00',
    updated_at: '2026-04-18T00:00:00+00:00',
    ...overrides,
  }
}

const RENT_LIVE = makeCategory({
  id: 10,
  group_name: 'Bills',
  category_name: 'Rent',
  block: 'monthly',
  planned_milliunits: 1500000,
})

const planFixture: ActivePlanResponse = {
  plan: {
    id: 1,
    plan_year: 2026,
    name: '2026 Budget',
    status: 'active',
    source: 'imported',
    created_at: '2026-04-18T00:00:00+00:00',
    updated_at: '2026-04-18T00:00:00+00:00',
    archived_at: null,
    source_import_id: 5,
  },
  blocks: {
    monthly: [RENT_LIVE],
    annual: [],
    one_time: [],
    stipends: [],
    savings: [],
  },
  totals: { grand_total_milliunits: 1500000 },
}

const REVISIONS: PlanRevisionSummary[] = [
  {
    id: 22,
    plan_id: 1,
    created_at: '2026-04-25T12:00:00+00:00',
    source: 'ui_update',
    summary: 'monthly › Bills / Rent: planned $1,200.00 → $1,500.00',
    change_count: 1,
  },
  {
    id: 21,
    plan_id: 1,
    created_at: '2026-04-24T12:00:00+00:00',
    source: 'ui_update',
    summary: 'monthly › Bills / Rent: planned $1,000.00 → $1,200.00',
    change_count: 1,
  },
]

describe('PlanningPage history', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getActivePlan.mockResolvedValue(planFixture)
    apiMocks.listPlanRevisions.mockResolvedValue({ revisions: REVISIONS })
    apiMocks.getPlanRevision.mockResolvedValue({
      ...REVISIONS[1],
      snapshot: [{ ...RENT_LIVE, planned_milliunits: 1200000 }],
    })
    apiMocks.restorePlanRevision.mockResolvedValue({ plan: planFixture })
  })

  it('opens the History sheet and lists revisions newest-first', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    await screen.findByText('Rent')

    await userEvent.click(screen.getByRole('button', { name: /History/i }))

    await waitFor(() => {
      expect(apiMocks.listPlanRevisions).toHaveBeenCalledWith(1)
    })
    const list = await screen.findByRole('region', { name: 'Plan revisions' }).catch(
      async () => screen.findByLabelText(/Plan revisions/i),
    )
    expect(within(list).getByText(/\$1,200\.00 → \$1,500\.00/)).toBeInTheDocument()
    expect(within(list).getByText(/\$1,000\.00 → \$1,200\.00/)).toBeInTheDocument()
  })

  it('shows a diff preview when a revision is selected', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    await screen.findByText('Rent')

    await userEvent.click(screen.getByRole('button', { name: /History/i }))
    const olderEntry = await screen.findByText(/\$1,000\.00 → \$1,200\.00/)
    await userEvent.click(olderEntry)

    await waitFor(() => {
      expect(apiMocks.getPlanRevision).toHaveBeenCalledWith(21)
    })
    const diffHeader = await screen.findByText(/1 category differs from the current plan/i)
    const dialog = diffHeader.closest('[role="dialog"]') as HTMLElement
    expect(within(dialog).getByText('Bills / Rent')).toBeInTheDocument()
    // Delta column rendered when planned increased: live $1,500 - snapshot $1,200 = +$300.
    expect(within(dialog).getByText(/Δ −\$300\.00/)).toBeInTheDocument()
  })

  it('restores after confirmation and invalidates the plan + summary queries', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    await screen.findByText('Rent')

    await user.click(screen.getByRole('button', { name: /History/i }))
    await user.click(await screen.findByText(/\$1,000\.00 → \$1,200\.00/))
    await user.click(await screen.findByRole('button', { name: 'Restore' }))

    const confirmText = await screen.findByText('Restore this revision?')
    const confirmDialog = confirmText.closest('[role="dialog"]') as HTMLElement
    await user.click(within(confirmDialog).getByRole('button', { name: 'Restore' }))

    await waitFor(() => {
      expect(apiMocks.restorePlanRevision).toHaveBeenCalledWith(21)
    })
  })
})
