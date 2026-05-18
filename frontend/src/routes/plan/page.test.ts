import { screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActivePlanResponse, CompareResponse, PlanCategory, SummaryResponse } from '$lib/api'

import { statusFixture, summaryFixture } from '../../test/fixtures'
import { renderPage } from '../../test/render-page'
import { resetMockPage } from '../../test/setup'
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
    monthly: [
      makeCategory({ id: 10, group_name: 'Housing', category_name: 'Rent', block: 'monthly', planned_milliunits: 1200000 }),
      makeCategory({ id: 11, group_name: 'Housing', category_name: 'Utilities', block: 'monthly', planned_milliunits: 200000 }),
      makeCategory({ id: 12, group_name: 'Food', category_name: 'Groceries', block: 'monthly', planned_milliunits: 600000 }),
    ],
    annual: [
      makeCategory({
        id: 20,
        group_name: 'Housing',
        category_name: 'Insurance',
        block: 'annual',
        planned_milliunits: 100000,
        annual_target_milliunits: 1200000,
        due_month: 6,
      }),
    ],
    one_time: [],
    stipends: [],
    savings: [],
  },
  totals: {
    monthly_milliunits: 2000000,
    annual_milliunits: 100000,
    one_time_milliunits: 0,
    stipends_milliunits: 0,
    savings_milliunits: 0,
    grand_total_milliunits: 2100000,
  },
}

const scenarioFixture: ActivePlanResponse = {
  ...planFixture,
  plan: { ...planFixture.plan, id: 2, status: 'scenario' },
  blocks: {
    ...planFixture.blocks,
    monthly: [
      makeCategory({ id: 10, plan_id: 2, group_name: 'Housing', category_name: 'Rent', block: 'monthly', planned_milliunits: 1250000 }),
      ...planFixture.blocks.monthly.slice(1).map((c) => ({ ...c, plan_id: 2 })),
    ],
  },
}

const compareFixture: CompareResponse = {
  scenario_id: 2,
  active_id: 1,
  window: { since: '2025-11', through: '2026-05', months: ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04'] },
  rows: [
    {
      category_id: 10,
      name: 'Rent',
      group: 'Housing',
      block: 'monthly',
      planned_active_milliunits: 1200000,
      planned_scenario_milliunits: 1250000,
      actuals_avg_6mo_milliunits: 1200000,
      vs_actuals_milliunits: 50000,
      vs_active_milliunits: 50000,
      sparkline: [1200000, 1200000, 1200000, 1200000, 1200000, 1200000],
    },
  ],
  totals: {
    planned_active_milliunits: 2100000,
    planned_scenario_milliunits: 2150000,
    vs_active_milliunits: 50000,
  },
}

const projectionFixture = {
  as_of_month: '2026-05',
  categories: [],
  totals: {
    projected_annual_milliunits: 25200000,
    planned_annual_milliunits: 24000000,
    projected_variance_milliunits: 1200000,
  },
} as any

describe('PlanPage', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getActivePlan.mockResolvedValue(planFixture)
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [] })
    apiMocks.getSummary.mockResolvedValue(summaryFixture as SummaryResponse)
    apiMocks.getYearEndProjection.mockResolvedValue(projectionFixture)
    apiMocks.listPlanRevisions.mockResolvedValue({ revisions: [] })
    apiMocks.createScenario.mockResolvedValue(scenarioFixture)
    apiMocks.commitScenario.mockResolvedValue({ plan: scenarioFixture })
    apiMocks.discardScenario.mockResolvedValue(undefined)
    resetMockPage()
  })

  it('renders the Quartz editor header in Live mode', async () => {
    renderPage(PlanPage as never)

    expect(await screen.findByRole('heading', { name: /Editor/i })).toBeInTheDocument()
    expect(screen.getByText(/Plan · Live/)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Start sandbox/i })).toBeInTheDocument()
  })

  it('renders the five workflow tabs with edited count', async () => {
    renderPage(PlanPage as never)

    expect(await screen.findByRole('tab', { name: /All categories/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^Edited \(0\)/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^Monthly$/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^Sinking$/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^Stipends$/ })).toBeInTheDocument()
  })

  it('renders the categories table grouped by group_name', async () => {
    renderPage(PlanPage as never)

    expect(await screen.findByText('Rent')).toBeInTheDocument()
    expect(screen.getByText('Utilities')).toBeInTheDocument()
    expect(screen.getByText('Groceries')).toBeInTheDocument()
    // Group headers render with their accent swatches.
    const housingRows = screen.getAllByText('Housing')
    expect(housingRows.length).toBeGreaterThan(0)
  })

  it('starts a sandbox when the Start sandbox button is clicked', async () => {
    apiMocks.getScenario.mockResolvedValue(scenarioFixture)
    apiMocks.compareScenario.mockResolvedValue(compareFixture)
    renderPage(PlanPage as never)

    const startButton = await screen.findByRole('button', { name: /Start sandbox/i })
    await userEvent.click(startButton)

    await waitFor(() => {
      expect(apiMocks.createScenario).toHaveBeenCalledWith({ from_plan_id: 1 })
    })
  })

  it('renders the right-rail Diff, Projected impact, and Plan history cards', async () => {
    renderPage(PlanPage as never)

    expect(await screen.findByText('Diff')).toBeInTheDocument()
    expect(screen.getByText('Projected impact')).toBeInTheDocument()
    expect(screen.getByText('Plan history')).toBeInTheDocument()
  })

  it('opens the discard confirmation dialog after entering sandbox mode', async () => {
    apiMocks.getScenario.mockResolvedValue(scenarioFixture)
    apiMocks.compareScenario.mockResolvedValue(compareFixture)
    renderPage(PlanPage as never)

    const startButton = await screen.findByRole('button', { name: /Start sandbox/i })
    await userEvent.click(startButton)

    const discardButton = await screen.findByRole('button', { name: /Discard draft/i })
    await userEvent.click(discardButton)

    expect(await screen.findByRole('heading', { name: /Discard sandbox/i })).toBeInTheDocument()
  })
})
