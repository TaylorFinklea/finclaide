<script lang="ts">
  import { AlertTriangle } from 'lucide-svelte'

  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import type { StatusResponse } from '$lib/api'
  import { formatRunAt } from '$lib/format'
  import { withBasePath } from '$lib/runtime'

  type LatestRun = NonNullable<StatusResponse['latest_runs']>[string]
  type FailedRun = LatestRun & { source: string; runId: number | null }

  const SOURCE_LABEL: Record<string, string> = {
    budget_import: 'Budget Import',
    ynab_sync: 'YNAB Sync',
    reconcile: 'Reconcile',
    scheduled_refresh: 'Scheduled Refresh',
  }

  type Props = {
    status: StatusResponse | undefined
    onRetry?: (source: string) => void
    retrying?: Record<string, boolean>
  }

  let { status, onRetry, retrying }: Props = $props()

  function describeFailure(run: LatestRun): string {
    const details = run.details ?? {}
    if (typeof details.error === 'string') return details.error
    if (typeof details.reconcile_error === 'string') return details.reconcile_error
    if (typeof details.mismatch_count === 'number' && details.mismatch_count > 0) {
      return `${details.mismatch_count} reconciliation mismatches.`
    }
    return 'No detail available — open the run for full payload.'
  }

  function gatherFailures(latest: StatusResponse | undefined): FailedRun[] {
    if (!latest?.latest_runs) return []
    const failures: FailedRun[] = []
    for (const [source, run] of Object.entries(latest.latest_runs)) {
      if (run.status === 'failed') {
        const runId = typeof run.id === 'number' ? run.id : null
        failures.push({ ...run, source, runId })
      }
    }
    failures.sort((a, b) => (b.finished_at ?? '').localeCompare(a.finished_at ?? ''))
    return failures
  }

  let failures = $derived(gatherFailures(status))
</script>

{#if status && failures.length > 0}
  <Card class="border-rose-500/30 bg-rose-500/[0.06]" aria-label="Failure cause for the most recent operation runs">
    <CardHeader>
      <CardTitle class="flex items-center gap-2 text-rose-100">
        <AlertTriangle class="h-4 w-4" />
        Failure cause
      </CardTitle>
      <p class="text-sm text-rose-100/80">
        The latest run of these operations failed. Open the run for the full payload, or retry once the
        underlying issue is fixed.
      </p>
    </CardHeader>
    <CardContent class="space-y-3">
      {#each failures as failure (failure.source)}
        <div class="rounded-lg bg-rose-500/[0.08] p-4 ring-1 ring-inset ring-rose-500/20">
          <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <div class="text-sm font-medium text-rose-50">
                {SOURCE_LABEL[failure.source] ?? failure.source}
              </div>
              <div class="mt-1 text-xs text-rose-100/70">
                Failed {formatRunAt(failure.finished_at)}
              </div>
              <div class="mt-2 text-sm text-rose-50/90">{describeFailure(failure)}</div>
            </div>
            <div class="flex gap-2">
              {#if failure.runId !== null}
                <Button variant="outline" class="border-rose-200/30 text-rose-50 hover:bg-rose-500/10" href={withBasePath(`/operations/runs/${failure.runId}`)}>
                  Open run
                </Button>
              {/if}
              {#if onRetry}
                <Button
                  variant="outline"
                  class="border-rose-200/30 text-rose-50 hover:bg-rose-500/10"
                  disabled={retrying?.[failure.source] === true}
                  onclick={() => onRetry?.(failure.source)}
                >
                  {retrying?.[failure.source] ? 'Retrying…' : 'Retry'}
                </Button>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </CardContent>
  </Card>
{/if}
