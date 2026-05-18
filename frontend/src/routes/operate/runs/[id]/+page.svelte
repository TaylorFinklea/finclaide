<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { createQuery } from '@tanstack/svelte-query'
  import { ArrowLeft } from 'lucide-svelte'

  import StatusChip from '$components/status-chip.svelte'
  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import { writable } from 'svelte/store'

  import { ApiError, getErrorMessage, getRun, type RunEntry } from '$lib/api'
  import { formatRunAt } from '$lib/format'
  import { withBasePath } from '$lib/runtime'

  const SOURCE_LABEL: Record<string, string> = {
    budget_import: 'Budget Import',
    ynab_sync: 'YNAB Sync',
    reconcile: 'Reconcile',
    scheduled_refresh: 'Scheduled Refresh',
  }

  let runId = $derived(Number.parseInt($page.params.id ?? '', 10))
  let isValidId = $derived(Number.isFinite(runId) && runId > 0)

  const initialRunId = Number.parseInt($page.params.id ?? '', 10)
  const runOpts = writable({
    queryKey: ['run', initialRunId] as readonly unknown[],
    queryFn: () => getRun(initialRunId),
    enabled: false,
    retry: false,
  })
  $effect(() => {
    runOpts.set({
      queryKey: ['run', runId],
      queryFn: () => getRun(runId),
      enabled: isValidId && browser,
      retry: false,
    })
  })
  const runQuery = createQuery(runOpts)

  function summarizeSuccess(run: RunEntry): string {
    const details = run.details ?? {}
    if (run.source === 'budget_import' && typeof details.row_count === 'number') return `Imported ${details.row_count} planned rows.`
    if (run.source === 'ynab_sync' && typeof details.transaction_count === 'number') return `Synced ${details.transaction_count} transactions.`
    if (run.source === 'reconcile' && typeof details.mismatch_count === 'number') {
      return details.mismatch_count === 0 ? 'Reconciliation passed with no mismatches.' : `Reconciliation flagged ${details.mismatch_count} mismatches.`
    }
    if (run.source === 'scheduled_refresh') return 'Scheduled refresh completed.'
    return 'Run completed.'
  }
</script>

<div class="space-y-6">
  <Button variant="outline" class="w-fit" href={withBasePath('/operations')}>
    <ArrowLeft class="h-4 w-4" />
    Back to Operations
  </Button>

  {#if !isValidId}
    <Card class="border-border/40 bg-card">
      <CardHeader><CardTitle>Invalid run id</CardTitle></CardHeader>
      <CardContent><p class="text-sm text-muted-foreground">The run id in the URL is not a number.</p></CardContent>
    </Card>
  {:else if $runQuery.isLoading}
    <Skeleton class="h-[480px] rounded-2xl" />
  {:else if $runQuery.isError}
    {@const err = $runQuery.error}
    <Card class="border-border/40 bg-card">
      <CardHeader>
        <CardTitle>{err instanceof ApiError && err.status === 404 ? 'Run not found' : 'Could not load run'}</CardTitle>
      </CardHeader>
      <CardContent>
        <p class="text-sm text-muted-foreground">
          {err instanceof ApiError && err.status === 404 ? `Run #${runId} does not exist.` : getErrorMessage(err)}
        </p>
      </CardContent>
    </Card>
  {:else if $runQuery.data}
    {@const run = $runQuery.data}
    <Card class="border-border/40 bg-card">
      <CardHeader class="space-y-3">
        <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div class="text-label">Run #{run.id}</div>
            <CardTitle class="mt-1">{SOURCE_LABEL[run.source] ?? run.source}</CardTitle>
            <p class="mt-2 text-sm text-muted-foreground">
              Started {formatRunAt(run.started_at)} · Finished {formatRunAt(run.finished_at)}
            </p>
          </div>
          <StatusChip status={run.status} />
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        {#if run.status === 'failed'}
          {@const detail = run.details ?? {}}
          {@const message = (typeof detail.error === 'string' && detail.error) || (typeof detail.reconcile_error === 'string' && detail.reconcile_error) || 'Run failed without a captured error message.'}
          <div class="rounded-lg bg-rose-500/[0.08] p-4 ring-1 ring-inset ring-rose-500/20">
            <div class="text-label-upper text-rose-100">Failure</div>
            <p class="mt-2 text-sm text-rose-50">{message}</p>
          </div>
        {:else if run.status === 'skipped'}
          {@const detail = run.details ?? {}}
          {@const message = typeof detail.error === 'string' ? detail.error : 'Operation was skipped.'}
          <div class="rounded-lg bg-amber-500/[0.08] p-4 ring-1 ring-inset ring-amber-500/20">
            <div class="text-label-upper text-amber-100">Skipped</div>
            <p class="mt-2 text-sm text-amber-50">{message}</p>
          </div>
        {:else}
          <div class="rounded-lg bg-emerald-500/[0.06] p-4 ring-1 ring-inset ring-emerald-500/15">
            <div class="text-label-upper text-emerald-100">Succeeded</div>
            <p class="mt-2 text-sm text-emerald-50">{summarizeSuccess(run)}</p>
          </div>
        {/if}

        {#if Object.keys(run.details ?? {}).length > 0}
          <div class="space-y-3">
            <div class="text-label-upper">Details payload</div>
            <pre
              class="overflow-x-auto rounded-lg bg-muted/25 p-4 font-mono text-xs text-slate-100 ring-1 ring-inset ring-border/30"
              aria-label="Raw details payload"
            >{JSON.stringify(run.details, null, 2)}</pre>
          </div>
        {:else}
          <p class="text-sm text-muted-foreground">No additional details captured for this run.</p>
        {/if}
      </CardContent>
    </Card>
  {/if}
</div>
