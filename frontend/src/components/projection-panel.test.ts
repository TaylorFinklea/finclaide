import { screen, waitFor, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActivePlanResponse, ScenarioSummary } from '$lib/api'

import { renderPage } from '../test/render-page'
import ProjectionPanel from './projection-panel.svelte'

const apiMocks = vi.hoisted(() => ({
  getActivePlan: vi.fn(),
  listScenarios: vi.fn(),
  compareProjection: vi.fn(),
  applyProjectionToSandbox: vi.fn(),
  saveScenario: vi.fn(),
  discardScenario: vi.fn(),
}))

const navMocks = vi.hoisted(() => ({
  goto: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

vi.mock('$app/navigation', () => navMocks)

function makePlan(overrides: Partial<ActivePlanResponse['plan']> = {}): ActivePlanResponse {
  return {
    plan: {
      id: 1,
      plan_year: 2026,
      name: '2026 Budget',
      label: null,
      status: 'active',
      source: 'edited',
      created_at: '2026-01-01T00:00:00+00:00',
      updated_at: '2026-01-01T00:00:00+00:00',
      archived_at: null,
      source_import_id: null,
      ...overrides,
    },
    blocks: {
      monthly: [
        {
          id: 10,
          plan_id: 1,
          group_name: 'Bills',
          category_name: 'Rent',
          block: 'monthly',
          planned_milliunits: 1200000,
          annual_target_milliunits: 0,
          due_month: null,
          notes: null,
          created_at: '2026-01-01T00:00:00+00:00',
          updated_at: '2026-01-01T00:00:00+00:00',
        },
        {
          id: 11,
          plan_id: 1,
          group_name: 'Bills',
          category_name: 'Utilities',
          block: 'monthly',
          planned_milliunits: 200000,
          annual_target_milliunits: 0,
          due_month: null,
          notes: null,
          created_at: '2026-01-01T00:00:00+00:00',
          updated_at: '2026-01-01T00:00:00+00:00',
        },
      ],
      annual: [],
      one_time: [],
      stipends: [],
      savings: [],
    },
    totals: { grand_total_milliunits: 1400000 },
  }
}

function makeSandbox(id = 99): ScenarioSummary {
  return {
    id,
    plan_year: 2026,
    name: '2026 Budget',
    label: null,
    status: 'scenario',
    source: 'edited',
    created_at: '2026-04-01T00:00:00+00:00',
    updated_at: '2026-04-01T00:00:00+00:00',
    category_count: 2,
  }
}

describe('ProjectionPanel', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    navMocks.goto.mockReset()
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [] })
  })

  it('renders sliders for each active category', async () => {
    apiMocks.getActivePlan.mockResolvedValue(makePlan())
    renderPage(ProjectionPanel as never)
    const sliders = await screen.findAllByRole('slider')
    // Two categories = two sliders (one per slider thumb).
    expect(sliders.length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('Rent')).toBeInTheDocument()
    expect(screen.getByText('Utilities')).toBeInTheDocument()
  })

  it('Add hypothetical line button reveals form; submit pushes to list', async () => {
    apiMocks.getActivePlan.mockResolvedValue(makePlan())
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(ProjectionPanel as never)
    await screen.findByText('Rent')

    await user.click(screen.getByRole('button', { name: /Add hypothetical line/i }))

    expect(screen.getByLabelText('Group')).toBeInTheDocument()
    expect(screen.getByLabelText('Category')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Group'), 'Expenses')
    await user.type(screen.getByLabelText('Category'), 'Emergency')
    await user.type(screen.getByLabelText('$/mo'), '500')
    await user.click(screen.getByRole('button', { name: 'Add' }))

    // After submit, the new line should appear in the list.
    await screen.findByText(/Expenses \/ Emergency/i)
  })

  it('Apply mutation success calls goto with /planning?scenario=<id>', async () => {
    const newPlan = makePlan({ id: 42, status: 'scenario' })
    apiMocks.getActivePlan.mockResolvedValue(makePlan())
    apiMocks.applyProjectionToSandbox.mockResolvedValue(newPlan)
    renderPage(ProjectionPanel as never)
    await screen.findByText('Rent')

    await userEvent.click(
      screen.getByRole('button', { name: /Apply to Sandbox/i }),
    )

    await waitFor(() => {
      expect(apiMocks.applyProjectionToSandbox).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(navMocks.goto).toHaveBeenCalledWith(
        expect.stringContaining('/planning?scenario=42'),
      )
    })
  })

  it('Apply with "sandbox already exists" error opens auto-park modal', async () => {
    apiMocks.getActivePlan.mockResolvedValue(makePlan())
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [makeSandbox(99)] })
    apiMocks.applyProjectionToSandbox.mockRejectedValue(
      new Error('A sandbox already exists. Save it as a scenario or discard it before starting a new sandbox.'),
    )
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(ProjectionPanel as never)
    await screen.findByText('Rent')

    await user.click(screen.getByRole('button', { name: /Apply to Sandbox/i }))

    await screen.findByText(/Save your sandbox before applying projection/i)
    expect(apiMocks.saveScenario).not.toHaveBeenCalled()
  })

  it('auto-park Save & apply chains saveScenario then applyProjectionToSandbox', async () => {
    const newPlan = makePlan({ id: 55, status: 'scenario' })
    apiMocks.getActivePlan.mockResolvedValue(makePlan())
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [makeSandbox(99)] })
    // First applyProjectionToSandbox call throws; second (after save) succeeds.
    apiMocks.applyProjectionToSandbox
      .mockRejectedValueOnce(
        new Error('A sandbox already exists. Save it as a scenario or discard it before starting a new sandbox.'),
      )
      .mockResolvedValueOnce(newPlan)
    apiMocks.saveScenario.mockResolvedValue({ plan: { plan: { id: 99, label: 'Saved' } } })

    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(ProjectionPanel as never)
    await screen.findByText('Rent')

    await user.click(screen.getByRole('button', { name: /Apply to Sandbox/i }))

    const dialog = (
      await screen.findByText(/Save your sandbox before applying projection/i)
    ).closest('[role="dialog"]') as HTMLElement

    await user.click(within(dialog).getByRole('button', { name: /Save & apply/i }))

    await waitFor(() => {
      expect(apiMocks.saveScenario).toHaveBeenCalledWith(99, expect.any(String))
    })
    await waitFor(() => {
      expect(apiMocks.applyProjectionToSandbox).toHaveBeenCalledTimes(2)
    })
    await waitFor(() => {
      expect(navMocks.goto).toHaveBeenCalledWith(
        expect.stringContaining('/planning?scenario=55'),
      )
    })
  })

  it('compareProjection is called when axes have non-zero delta (debounced)', async () => {
    apiMocks.getActivePlan.mockResolvedValue(makePlan())
    apiMocks.compareProjection.mockResolvedValue({
      scenario_id: null,
      active_id: 1,
      window: {
        since: '2025-10',
        through: '2026-04',
        months: ['2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03'],
      },
      rows: [],
      totals: {
        planned_active_milliunits: 1400000,
        planned_scenario_milliunits: 1200000,
        vs_active_milliunits: -200000,
      },
    })

    renderPage(ProjectionPanel as never)
    const sliders = await screen.findAllByRole('slider')
    // Fire keyboard event on first slider to simulate movement.
    const firstSlider = sliders[0]
    firstSlider.focus()
    // Simulate ArrowRight to increase value.
    await userEvent.keyboard('{ArrowRight}')

    // Wait for debounce + query.
    await waitFor(
      () => {
        expect(apiMocks.compareProjection).toHaveBeenCalled()
      },
      { timeout: 1000 },
    )
  })
})
