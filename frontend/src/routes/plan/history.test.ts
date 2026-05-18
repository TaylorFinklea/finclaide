import { screen, waitFor, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActivePlanResponse, PlanCategory, PlanRevisionSummary } from '$lib/api'

import { statusFixture, summaryFixture } from '../../test/fixtures'
import { renderPage } from '../../test/render-page'
import PlanPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getActivePlan: vi.fn(),
  createPlanCategory: vi.fn(),
  updatePlanCategory: vi.fn(),
  deletePlanCategory: vi.fn(),
  listScenarios: vi.fn(),
  createScenario: vi.fn(),
  getScenario: vi.fn(),
  saveScenario: vi.fn(),
  commitScenario: vi.fn(),
  discardScenario: vi.fn(),
  compareScenario: vi.fn(),
  getSummary: vi.fn(),
  getYearEndProjection: vi.fn(),
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
    kind: 'outflow',
    tithe_percent: null,
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
  group_name: 'Housing',
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
    summary: 'monthly › Housing / Rent: planned $1,200.00 → $1,500.00',
    change_count: 1,
  },
  {
    id: 21,
    plan_id: 1,
    created_at: '2026-04-24T12:00:00+00:00',
    source: 'ui_update',
    summary: 'monthly › Housing / Rent: planned $1,000.00 → $1,200.00',
    change_count: 1,
  },
]

describe('PlanPage history', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getActivePlan.mockResolvedValue(planFixture)
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [] })
    apiMocks.getSummary.mockResolvedValue(summaryFixture)
    apiMocks.getYearEndProjection.mockResolvedValue({
      as_of_month: '2026-04',
      categories: [],
      totals: {
        projected_annual_milliunits: 18000000,
        planned_annual_milliunits: 18000000,
        projected_variance_milliunits: 0,
      },
    } as any)
    apiMocks.listPlanRevisions.mockResolvedValue({ revisions: REVISIONS })
    apiMocks.getPlanRevision.mockResolvedValue({
      ...REVISIONS[1],
      snapshot: [{ ...RENT_LIVE, planned_milliunits: 1200000 }],
    })
    apiMocks.restorePlanRevision.mockResolvedValue({ plan: planFixture })
  })

  it('inlines recent revisions in the Plan history card', async () => {
    renderPage(PlanPage as never)

    expect(await screen.findByText('Plan history')).toBeInTheDocument()
    await waitFor(() => {
      expect(apiMocks.listPlanRevisions).toHaveBeenCalledWith(1, 10)
    })
    expect(await screen.findByText(/r22/)).toBeInTheDocument()
    expect(screen.getByText(/r21/)).toBeInTheDocument()
    expect(screen.getByText(/Housing \/ Rent: planned \$1,200\.00/)).toBeInTheDocument()
  })

  it('opens the full History sheet via the Open timeline action', async () => {
    renderPage(PlanPage as never)
    await screen.findByText('Plan history')

    await userEvent.click(await screen.findByRole('button', { name: /Open timeline/i }))

    // The deeper PlanHistorySheet renders the same revisions list inside a dialog.
    const dialogs = await screen.findAllByRole('dialog')
    const sheet = dialogs[dialogs.length - 1] as HTMLElement
    expect(within(sheet).getByText(/\$1,200\.00 → \$1,500\.00/)).toBeInTheDocument()
  })

  // Deeper restore-flow coverage lives in the PlanHistorySheet's own
  // component tests; the page test only proves the trigger renders.
})
