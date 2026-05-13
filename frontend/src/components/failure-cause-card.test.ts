import { render, screen } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'

import { statusFixture } from '../test/fixtures'
import FailureCauseCard from './failure-cause-card.svelte'

describe('FailureCauseCard', () => {
  it('keeps a scheduled refresh reconcile failure visible until reconcile succeeds later', async () => {
    render(FailureCauseCard as never, {
      props: {
        status: {
          ...statusFixture,
          latest_runs: {
            scheduled_refresh: {
              status: 'failed',
              started_at: '2026-03-15T12:15:00+00:00',
              finished_at: '2026-03-15T12:15:08+00:00',
              details: { reconcile_error: 'Reconciliation failed with 1 mismatches.' },
            },
            reconcile: {
              status: 'success',
              started_at: '2026-03-15T12:02:00+00:00',
              finished_at: '2026-03-15T12:02:01+00:00',
              details: { mismatch_count: 0 },
            },
          },
        },
      } as never,
    })

    expect(await screen.findByText('Failure cause')).toBeInTheDocument()
    expect(await screen.findByText('Scheduled Refresh')).toBeInTheDocument()
  })

  it('hides a scheduled refresh reconcile failure after a newer reconcile success', () => {
    render(FailureCauseCard as never, {
      props: {
        status: {
          ...statusFixture,
          latest_runs: {
            scheduled_refresh: {
              status: 'failed',
              started_at: '2026-03-15T12:15:00+00:00',
              finished_at: '2026-03-15T12:15:08+00:00',
              details: { reconcile_error: 'Reconciliation failed with 1 mismatches.' },
            },
            reconcile: {
              status: 'success',
              started_at: '2026-03-15T12:20:00+00:00',
              finished_at: '2026-03-15T12:20:01+00:00',
              details: { mismatch_count: 0 },
            },
          },
        },
      } as never,
    })

    expect(screen.queryByText('Failure cause')).not.toBeInTheDocument()
    expect(screen.queryByText('Scheduled Refresh')).not.toBeInTheDocument()
  })
})
