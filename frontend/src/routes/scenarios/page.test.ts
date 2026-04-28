import { screen, waitFor, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActivePlanResponse, ScenarioSummary } from '$lib/api'

import { renderPage } from '../../test/render-page'
import ScenariosPage from './+page.svelte'

const apiMocks = vi.hoisted(() => ({
  listScenarios: vi.fn(),
  saveScenario: vi.fn(),
  forkScenario: vi.fn(),
  commitScenario: vi.fn(),
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

function summary(over: Partial<ScenarioSummary>): ScenarioSummary {
  return {
    id: 1,
    plan_year: 2026,
    name: '2026 Budget',
    label: null,
    status: 'scenario',
    source: 'edited',
    created_at: '2026-04-26T00:00:00+00:00',
    updated_at: '2026-04-26T00:00:00+00:00',
    category_count: 12,
    ...over,
  }
}

const SAVED_A: ScenarioSummary = summary({ id: 10, label: 'Summer budget' })
const SAVED_B: ScenarioSummary = summary({ id: 11, label: 'If Daisy stops working' })
const SANDBOX: ScenarioSummary = summary({ id: 99, label: null })

const FORKED_PLAN: ActivePlanResponse = {
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
  blocks: { monthly: [], annual: [], one_time: [], stipends: [], savings: [] },
  totals: { grand_total_milliunits: 0 },
}

describe('ScenariosPage', () => {
  beforeEach(() => {
    for (const mock of Object.values(apiMocks)) mock.mockReset()
    navMocks.goto.mockReset()
  })

  it('renders saved scenarios and excludes the unnamed sandbox row', async () => {
    apiMocks.listScenarios.mockResolvedValue({
      scenarios: [SANDBOX, SAVED_A, SAVED_B],
    })
    renderPage(ScenariosPage as never)
    await screen.findByText('Summer budget')
    expect(screen.getByText('If Daisy stops working')).toBeInTheDocument()
    // Sandbox row (label = null) is not rendered with a label.
    expect(screen.queryByText('null')).not.toBeInTheDocument()
  })

  it('forks directly when no sandbox exists', async () => {
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [SAVED_A] })
    apiMocks.forkScenario.mockResolvedValue(FORKED_PLAN)
    renderPage(ScenariosPage as never)
    await screen.findByText('Summer budget')

    await userEvent.click(screen.getByRole('button', { name: 'Open' }))

    await waitFor(() => {
      expect(apiMocks.forkScenario).toHaveBeenCalledWith(10)
    })
    expect(apiMocks.saveScenario).not.toHaveBeenCalled()
  })

  it('opens the auto-park modal when a sandbox exists and Open is clicked', async () => {
    apiMocks.listScenarios.mockResolvedValue({
      scenarios: [SANDBOX, SAVED_A],
    })
    renderPage(ScenariosPage as never)
    await screen.findByText('Summer budget')

    await userEvent.click(screen.getByRole('button', { name: 'Open' }))

    await screen.findByText(/Save your sandbox before opening/i)
    expect(apiMocks.forkScenario).not.toHaveBeenCalled()
  })

  it('Save & open chains saveScenario then forkScenario in order', async () => {
    apiMocks.listScenarios.mockResolvedValue({
      scenarios: [SANDBOX, SAVED_A],
    })
    apiMocks.saveScenario.mockResolvedValue({ plan: FORKED_PLAN })
    apiMocks.forkScenario.mockResolvedValue(FORKED_PLAN)

    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(ScenariosPage as never)
    await screen.findByText('Summer budget')
    await user.click(screen.getByRole('button', { name: 'Open' }))

    const dialog = (await screen.findByText(/Save your sandbox before opening/i)).closest(
      '[role="dialog"]',
    ) as HTMLElement
    await user.click(within(dialog).getByRole('button', { name: /Save & open/i }))

    await waitFor(() => {
      expect(apiMocks.saveScenario).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(apiMocks.forkScenario).toHaveBeenCalledTimes(1)
    })
    // Save before fork.
    const saveOrder = apiMocks.saveScenario.mock.invocationCallOrder[0]
    const forkOrder = apiMocks.forkScenario.mock.invocationCallOrder[0]
    expect(saveOrder).toBeLessThan(forkOrder)
    expect(apiMocks.saveScenario).toHaveBeenCalledWith(99, expect.any(String))
    expect(apiMocks.forkScenario).toHaveBeenCalledWith(10)
  })

  it('keeps modal open with inline error when save fails', async () => {
    apiMocks.listScenarios.mockResolvedValue({
      scenarios: [SANDBOX, SAVED_A],
    })
    apiMocks.saveScenario.mockRejectedValue(
      Object.assign(new Error('A saved scenario named such-and-such already exists.'), {
        name: 'ApiError',
      }),
    )

    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(ScenariosPage as never)
    await screen.findByText('Summer budget')
    await user.click(screen.getByRole('button', { name: 'Open' }))

    const dialog = (await screen.findByText(/Save your sandbox before opening/i)).closest(
      '[role="dialog"]',
    ) as HTMLElement
    await user.click(within(dialog).getByRole('button', { name: /Save & open/i }))

    await waitFor(() => {
      expect(apiMocks.saveScenario).toHaveBeenCalled()
    })
    expect(apiMocks.forkScenario).not.toHaveBeenCalled()
    // Modal still showing.
    expect(within(dialog).getByText(/A saved scenario named such-and-such/i)).toBeInTheDocument()
  })

  it('Discard sandbox chains discardScenario then forkScenario', async () => {
    apiMocks.listScenarios.mockResolvedValue({
      scenarios: [SANDBOX, SAVED_A],
    })
    apiMocks.discardScenario.mockResolvedValue(undefined)
    apiMocks.forkScenario.mockResolvedValue(FORKED_PLAN)

    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(ScenariosPage as never)
    await screen.findByText('Summer budget')
    await user.click(screen.getByRole('button', { name: 'Open' }))

    const dialog = (await screen.findByText(/Save your sandbox before opening/i)).closest(
      '[role="dialog"]',
    ) as HTMLElement
    await user.click(within(dialog).getByRole('button', { name: /Discard sandbox/i }))

    await waitFor(() => {
      expect(apiMocks.discardScenario).toHaveBeenCalledWith(99)
    })
    await waitFor(() => {
      expect(apiMocks.forkScenario).toHaveBeenCalledWith(10)
    })
    const discardOrder = apiMocks.discardScenario.mock.invocationCallOrder[0]
    const forkOrder = apiMocks.forkScenario.mock.invocationCallOrder[0]
    expect(discardOrder).toBeLessThan(forkOrder)
  })

  it('Make active opens commit confirm and calls commitScenario', async () => {
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [SAVED_A] })
    apiMocks.commitScenario.mockResolvedValue({ plan: FORKED_PLAN })

    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(ScenariosPage as never)
    await screen.findByText('Summer budget')
    await user.click(screen.getByRole('button', { name: /Make active/i }))

    const dialog = (await screen.findByText(/Replaces your active plan/i)).closest(
      '[role="dialog"]',
    ) as HTMLElement
    await user.click(within(dialog).getByRole('button', { name: 'Make active' }))

    await waitFor(() => {
      expect(apiMocks.commitScenario).toHaveBeenCalledWith(10)
    })
  })

  it('Delete opens confirm and calls discardScenario', async () => {
    apiMocks.listScenarios.mockResolvedValue({ scenarios: [SAVED_A] })
    apiMocks.discardScenario.mockResolvedValue(undefined)

    const user = userEvent.setup({ pointerEventsCheck: 0 })
    renderPage(ScenariosPage as never)
    await screen.findByText('Summer budget')
    await user.click(screen.getByRole('button', { name: /Delete/i }))

    const dialog = (await screen.findByText(/permanently deletes/i)).closest(
      '[role="dialog"]',
    ) as HTMLElement
    await user.click(within(dialog).getByRole('button', { name: /Delete scenario/i }))

    await waitFor(() => {
      expect(apiMocks.discardScenario).toHaveBeenCalledWith(10)
    })
  })
})
