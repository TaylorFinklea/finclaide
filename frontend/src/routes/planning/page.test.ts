import { screen, waitFor, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActivePlanResponse, PlanCategory } from '$lib/api'

import { statusFixture } from '../../test/fixtures'
import { renderPage } from '../../test/render-page'
import { setMockPage } from '../../test/setup'
import PlanningPage from './+page.svelte'

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
      makeCategory({ id: 10, group_name: 'Bills', category_name: 'Rent', block: 'monthly', planned_milliunits: 1200000 }),
      makeCategory({ id: 11, group_name: 'Bills', category_name: 'Utilities', block: 'monthly', planned_milliunits: 200000 }),
    ],
    annual: [
      makeCategory({
        id: 20,
        group_name: 'Yearly',
        category_name: 'Insurance',
        block: 'annual',
        planned_milliunits: 100000,
        annual_target_milliunits: 1200000,
        due_month: 6,
      }),
    ],
    one_time: [],
    stipends: [
      makeCategory({ id: 30, group_name: 'Stipends', category_name: 'S Stipend', block: 'stipends', planned_milliunits: 100000 }),
    ],
    savings: [
      makeCategory({ id: 40, group_name: 'Savings', category_name: 'Emergency', block: 'savings', planned_milliunits: 200000 }),
    ],
  },
  totals: {
    monthly_milliunits: 1400000,
    annual_milliunits: 100000,
    one_time_milliunits: 0,
    stipends_milliunits: 100000,
    savings_milliunits: 200000,
    grand_total_milliunits: 1800000,
  },
}

describe('PlanningPage', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getActivePlan.mockResolvedValue(planFixture)
    apiMocks.updatePlanCategory.mockResolvedValue(planFixture.blocks.monthly[0])
    apiMocks.createPlanCategory.mockResolvedValue(planFixture.blocks.monthly[0])
    apiMocks.deletePlanCategory.mockResolvedValue(undefined)
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [] })
    apiMocks.commitScenario.mockResolvedValue({ plan: planFixture })
    apiMocks.discardScenario.mockResolvedValue(undefined)
  })

  it('renders the five block tabs and defaults to Monthly', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })

    expect(await screen.findByRole('tab', { name: 'Monthly' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Annual' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'One-time' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Stipends' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Savings' })).toBeInTheDocument()
    expect(await screen.findByText('Rent')).toBeInTheDocument()
    expect(await screen.findByText('Utilities')).toBeInTheDocument()
  })

  it('opens the edit Sheet with prefilled values when a row is clicked', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })

    const row = (await screen.findByText('Rent')).closest('tr')
    expect(row).not.toBeNull()
    await userEvent.click(row!)

    const sheet = await screen.findByRole('dialog')
    expect(within(sheet).getByText(/Edit category/i)).toBeInTheDocument()
    const planned = within(sheet).getByLabelText(/Planned/i) as HTMLInputElement
    expect(planned.value).toBe('1200.00')
  })

  it('opens an empty create Sheet when Add row is clicked with the active block preselected', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })

    await screen.findByText('Rent')
    await userEvent.click(screen.getByRole('tab', { name: 'Stipends' }))
    await screen.findByText('S Stipend')
    await userEvent.click(screen.getByRole('button', { name: /Add row/i }))

    const sheet = await screen.findByRole('dialog')
    expect(within(sheet).getByText(/New Stipends category/i)).toBeInTheDocument()
    const groupInput = within(sheet).getByLabelText('Group') as HTMLInputElement
    expect(groupInput.value).toBe('')
    expect(groupInput).not.toBeDisabled()
  })

  it('save flow patches the row and closes the Sheet', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })

    const row = (await screen.findByText('Rent')).closest('tr')
    await userEvent.click(row!)
    const sheet = await screen.findByRole('dialog')

    const planned = within(sheet).getByLabelText(/Planned/i) as HTMLInputElement
    await userEvent.clear(planned)
    await userEvent.type(planned, '1300.50')
    await userEvent.click(within(sheet).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(apiMocks.updatePlanCategory).toHaveBeenCalledWith(
        10,
        expect.objectContaining({ plan_id: 1, planned_milliunits: 1300500 }),
      )
    })
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('disables group/category inputs in edit mode unless rename is enabled', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })

    const row = (await screen.findByText('Rent')).closest('tr')
    await userEvent.click(row!)
    const sheet = await screen.findByRole('dialog')
    const group = within(sheet).getByLabelText('Group') as HTMLInputElement
    expect(group).toBeDisabled()

    await userEvent.click(within(sheet).getByLabelText(/Allow renaming/i))
    expect(group).not.toBeDisabled()
  })

  it('delete confirmation invokes deletePlanCategory after confirm', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    const user = userEvent.setup({ pointerEventsCheck: 0 })

    const row = (await screen.findByText('Rent')).closest('tr')
    await user.click(row!)
    const sheet = await screen.findByRole('dialog')
    await user.click(within(sheet).getByRole('button', { name: /Delete/i }))

    const confirm = await screen.findByText('Delete category?')
    const confirmContainer = confirm.closest('[role="dialog"]') as HTMLElement
    await user.click(within(confirmContainer).getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(apiMocks.deletePlanCategory).toHaveBeenCalledWith(10, 1)
    })
  })

  it('renders the empty-state message for blocks with no rows', async () => {
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })

    await screen.findByText('Rent')
    await userEvent.click(screen.getByRole('tab', { name: 'One-time' }))
    expect(await screen.findByText(/No One-time categories yet/i)).toBeInTheDocument()
  })
})

describe('PlanningPage sandbox Save flow', () => {
  const sandboxPlan: ActivePlanResponse = {
    plan: {
      id: 200,
      plan_year: 2026,
      name: '2026 Budget',
      label: null,
      status: 'scenario',
      source: 'edited',
      created_at: '2026-04-28T00:00:00+00:00',
      updated_at: '2026-04-28T00:00:00+00:00',
      archived_at: null,
      source_import_id: null,
    } as ActivePlanResponse['plan'],
    blocks: {
      monthly: [planFixture.blocks.monthly[0]],
      annual: [],
      one_time: [],
      stipends: [],
      savings: [],
    },
    totals: { grand_total_milliunits: 1200000 },
  }

  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getActivePlan.mockResolvedValue(planFixture)
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [] })
    apiMocks.createScenario.mockResolvedValue(sandboxPlan)
    apiMocks.getScenario.mockResolvedValue(sandboxPlan)
    apiMocks.saveScenario.mockResolvedValue({ plan: sandboxPlan })
    apiMocks.discardScenario.mockResolvedValue(undefined)
  })

  it('Save button on the sandbox banner opens a modal with a default label', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    await screen.findByText('Rent')

    await user.click(screen.getByRole('button', { name: /Try a what-if/i }))
    await screen.findByText(/Sandbox mode/i)

    await user.click(screen.getByRole('button', { name: /^Save$/ }))

    const dialog = (await screen.findByText(/Name this sandbox to keep its edits/i)).closest(
      '[role="dialog"]',
    ) as HTMLElement
    const input = within(dialog).getByLabelText(/Name/i) as HTMLInputElement
    expect(input.value).toMatch(/Untitled scenario/)
  })

  it('submitting Save scenario calls saveScenario with trimmed label', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    await screen.findByText('Rent')

    await user.click(screen.getByRole('button', { name: /Try a what-if/i }))
    await screen.findByText(/Sandbox mode/i)
    await user.click(screen.getByRole('button', { name: /^Save$/ }))

    const dialog = (await screen.findByText(/Name this sandbox to keep its edits/i)).closest(
      '[role="dialog"]',
    ) as HTMLElement
    const input = within(dialog).getByLabelText(/Name/i) as HTMLInputElement
    await user.clear(input)
    await user.type(input, '  Summer budget  ')
    await user.click(within(dialog).getByRole('button', { name: /Save scenario/i }))

    await waitFor(() => {
      expect(apiMocks.saveScenario).toHaveBeenCalledWith(200, 'Summer budget')
    })
  })

  it('shows inline error and stays open when saveScenario rejects', async () => {
    apiMocks.saveScenario.mockRejectedValueOnce(
      Object.assign(new Error('A saved scenario named such-and-such already exists.'), {
        name: 'ApiError',
      }),
    )
    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    await screen.findByText('Rent')

    await user.click(screen.getByRole('button', { name: /Try a what-if/i }))
    await screen.findByText(/Sandbox mode/i)
    await user.click(screen.getByRole('button', { name: /^Save$/ }))

    const dialog = (await screen.findByText(/Name this sandbox to keep its edits/i)).closest(
      '[role="dialog"]',
    ) as HTMLElement
    await user.click(within(dialog).getByRole('button', { name: /Save scenario/i }))

    await waitFor(() => {
      expect(within(dialog).getByText(/such-and-such already exists/i)).toBeInTheDocument()
    })
    // Modal still rendered (description text is unique to the Save modal).
    expect(screen.getByText(/Name this sandbox to keep its edits/i)).toBeInTheDocument()
  })
})

describe('PlanningPage ?scenario= deeplink', () => {
  const sandboxPlan: ActivePlanResponse = {
    plan: {
      id: 99,
      plan_year: 2026,
      name: '2026 Budget',
      label: null,
      status: 'scenario',
      source: 'edited',
      created_at: '2026-04-28T00:00:00+00:00',
      updated_at: '2026-04-28T00:00:00+00:00',
      archived_at: null,
      source_import_id: null,
    } as ActivePlanResponse['plan'],
    blocks: {
      monthly: [planFixture.blocks.monthly[0]],
      annual: [],
      one_time: [],
      stipends: [],
      savings: [],
    },
    totals: { grand_total_milliunits: 1200000 },
  }

  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    apiMocks.getStatus.mockResolvedValue(statusFixture)
    apiMocks.getActivePlan.mockResolvedValue(planFixture)
    apiMocks.getScenario.mockResolvedValue(sandboxPlan)
    apiMocks.discardScenario.mockResolvedValue(undefined)
  })

  it('enters sandbox mode when ?scenario=<id> matches an unnamed sandbox', async () => {
    apiMocks.listScenarios.mockResolvedValue({
      scenarios: [{ id: 99, label: null, plan_year: 2026, name: '2026 Budget', status: 'scenario', source: 'edited', created_at: '2026-04-28T00:00:00+00:00', updated_at: '2026-04-28T00:00:00+00:00', category_count: 1 }],
    })

    // renderPage calls resetMockPage internally, so we set the URL after render.
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    setMockPage({ url: new URL('http://localhost/planning?scenario=99') })

    await screen.findByText('Sandbox mode')
  })

  it('ignores ?scenario=<id> when the id does not match an unnamed sandbox', async () => {
    // Only a saved (label !== null) scenario — should not enter sandbox mode.
    apiMocks.listScenarios.mockResolvedValue({
      scenarios: [{ id: 99, label: 'Summer budget', plan_year: 2026, name: '2026 Budget', status: 'scenario', source: 'edited', created_at: '2026-04-28T00:00:00+00:00', updated_at: '2026-04-28T00:00:00+00:00', category_count: 1 }],
    })

    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    setMockPage({ url: new URL('http://localhost/planning?scenario=99') })

    await screen.findByText('Rent')
    expect(screen.queryByText('Sandbox mode')).not.toBeInTheDocument()
  })

  it('does not re-enter sandbox after discard while ?scenario=<id> is still in the URL', async () => {
    apiMocks.listScenarios.mockResolvedValue({
      scenarios: [{ id: 99, label: null, plan_year: 2026, name: '2026 Budget', status: 'scenario', source: 'edited', created_at: '2026-04-28T00:00:00+00:00', updated_at: '2026-04-28T00:00:00+00:00', category_count: 1 }],
    })

    const user = userEvent.setup({ pointerEventsCheck: 0 })
    // renderPage calls resetMockPage internally, so we set the URL after render.
    renderPage(PlanningPage as never, { selectedMonth: '2026-04' })
    setMockPage({ url: new URL('http://localhost/planning?scenario=99') })

    // Wait for sandbox mode to be active.
    await screen.findByText('Sandbox mode')

    // Discard the sandbox.
    await user.click(screen.getByRole('button', { name: /^Discard$/ }))
    const dialog = (await screen.findByText(/Discard sandbox\?/i)).closest('[role="dialog"]') as HTMLElement
    // After discard mutation, scenarios list now has no sandbox (simulate removal).
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [] })
    await user.click(within(dialog).getByRole('button', { name: /Discard sandbox/i }))

    await waitFor(() => {
      expect(apiMocks.discardScenario).toHaveBeenCalledWith(99)
    })

    // Sandbox mode must not be present after discard.
    await waitFor(() => {
      expect(screen.queryByText('Sandbox mode')).not.toBeInTheDocument()
    })
  })
})
