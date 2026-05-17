import { render, screen, within } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LayoutHarness from './test/layout-harness.svelte'
import { statusFixture } from './test/fixtures'
import { resetMockPage } from './test/setup'

const apiMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
}))

vi.mock('$lib/api', async () => {
  const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api')
  return { ...actual, ...apiMocks }
})

vi.mock('$components/ui/toaster.svelte', async () => import('./test/noop.svelte'))

// A bare-bones fetch stub so the AI availability probe in +layout.svelte
// resolves without surprising the test harness with a network call.
const fetchMock = vi.hoisted(() => vi.fn(async () => new Response('', { status: 503 })))

beforeEach(() => {
  for (const mock of Object.values(apiMocks)) mock.mockReset()
  apiMocks.getStatus.mockResolvedValue(statusFixture)
  vi.stubGlobal('fetch', fetchMock)
  resetMockPage()
})

describe('Accessibility smoke — Quartz shell', () => {
  it('exposes nav links for the three workflow routes', async () => {
    render(LayoutHarness)

    const nav = await screen.findByRole('navigation')
    expect(within(nav).getByRole('link', { name: /Review/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Plan/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Operate/i })).toBeInTheDocument()
  })

  it('exposes the explore sub-routes', async () => {
    render(LayoutHarness)

    const nav = await screen.findByRole('navigation')
    expect(within(nav).getByRole('link', { name: /Categories/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Transactions/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Forecast/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Scenarios/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Insights/i })).toBeInTheDocument()
  })

  it('renders a Jump-to-anything search affordance', async () => {
    render(LayoutHarness)

    const search = await screen.findByRole('button', { name: /Jump to anything/i })
    expect(search).toBeInTheDocument()
  })

  it('mounts the AI rail composer with a labelled send button', async () => {
    render(LayoutHarness)

    // Composer input is present even when the rail is disabled — only the
    // submit button is gated.
    expect(await screen.findByPlaceholderText(/Ask Finclaide/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Send/i })).toBeInTheDocument()
  })

  it('shows a degraded-state banner when the AI rail is unavailable', async () => {
    render(LayoutHarness)

    expect(await screen.findByText(/ANTHROPIC_API_KEY/i)).toBeInTheDocument()
  })
})
