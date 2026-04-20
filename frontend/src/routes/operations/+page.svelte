<script lang="ts">
  import { browser } from '$app/environment'
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query'
  import { LoaderCircle, RefreshCw } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'
  import { writable } from 'svelte/store'

  import AutomationStatusCard from '$components/automation-status-card.svelte'
  import FailureCauseCard from '$components/failure-cause-card.svelte'
  import ReconcilePreviewCard from '$components/reconcile-preview-card.svelte'
  import StatusChip from '$components/status-chip.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import {
    getErrorMessage,
    getReconcilePreview,
    getRuns,
    getStatus,
    getSummary,
    importBudget,
    reconcile,
    refreshAll,
    syncYnab,
    type RunEntry,
    type StatusResponse,
  } from '$lib/api'
  import { formatMonthLabel, formatRunAt } from '$lib/format'
  import { withBasePath } from '$lib/runtime'
  import { monthStore } from '$lib/stores/month.svelte'

  let month = $derived(monthStore.value)
  let latestPayload: Record<string, unknown> | null = $state(null)

  const queryClient = useQueryClient()
  const statusQuery = createQuery({ queryKey: ['status'], queryFn: getStatus, enabled: browser })
  const summaryOpts = writable({
    queryKey: ['summary', monthStore.value] as readonly unknown[],
    queryFn: () => getSummary(monthStore.value),
    enabled: browser,
  })
  $effect(() => {
    summaryOpts.set({
      queryKey: ['summary', month],
      queryFn: () => getSummary(month),
      enabled: browser,
    })
  })
  const summaryQuery = createQuery(summaryOpts)
  const runsQuery = createQuery({ queryKey: ['runs'], queryFn: () => getRuns(12), enabled: browser })

  async function invalidateAll() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['status'] }),
      queryClient.invalidateQueries({ queryKey: ['runs'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
      queryClient.invalidateQueries({ queryKey: ['transactions'] }),
    ])
  }

  function makeMutation<T>(label: string, mutationFn: () => Promise<T>) {
    return createMutation({
      mutationFn,
      onSuccess: async (payload: unknown) => {
        latestPayload = payload as Record<string, unknown>
        toast.success(`${label} completed`)
        await invalidateAll()
      },
      onError: (error) => toast.error(getErrorMessage(error)),
    })
  }

  const importMutation = makeMutation('Budget import', importBudget)
  const syncMutation = makeMutation('YNAB sync', syncYnab)
  const reconcileMutation = makeMutation('Reconcile', reconcile)
  const refreshMutation = createMutation({
    mutationFn: () => refreshAll(month),
    onSuccess: async (payload: unknown) => {
      latestPayload = payload as Record<string, unknown>
      toast.success('Refresh all completed')
      await invalidateAll()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  let busy = $derived(
    $importMutation.isPending || $syncMutation.isPending || $reconcileMutation.isPending || $refreshMutation.isPending,
  )
  let recentRuns = $derived($runsQuery.data?.runs ?? [])

  let reconcileFailed = $derived($statusQuery.data?.latest_runs?.reconcile?.status === 'failed')
  let planImported = $derived(
    $statusQuery.data?.last_budget_import_id !== null &&
      $statusQuery.data?.last_budget_import_id !== undefined,
  )
  const previewOpts = writable({
    queryKey: ['reconcile-preview'] as readonly unknown[],
    queryFn: getReconcilePreview,
    enabled: false,
    retry: false,
  })
  $effect(() => {
    previewOpts.set({
      queryKey: ['reconcile-preview'],
      queryFn: getReconcilePreview,
      enabled: reconcileFailed && planImported && browser,
      retry: false,
    })
  })
  const previewQuery = createQuery(previewOpts)

  function handleRetry(source: string) {
    if (source === 'budget_import') $importMutation.mutate()
    else if (source === 'ynab_sync') $syncMutation.mutate()
    else $reconcileMutation.mutate()
  }

  let retrying = $derived({
    budget_import: $importMutation.isPending,
    ynab_sync: $syncMutation.isPending,
    reconcile: $reconcileMutation.isPending,
    scheduled_refresh: $reconcileMutation.isPending,
  })

  function describeRun(run: RunEntry): string {
    const details = run.details ?? {}
    if (typeof details.error === 'string') return details.error
    if (run.source === 'budget_import' && typeof details.row_count === 'number') return `Imported ${details.row_count} planned rows`
    if (run.source === 'ynab_sync' && typeof details.transaction_count === 'number') return `Synced ${details.transaction_count} transactions`
    if (run.source === 'reconcile' && typeof details.mismatch_count === 'number') {
      return details.mismatch_count === 0 ? 'No mismatches found' : `${details.mismatch_count} mismatches detected`
    }
    if (run.source === 'scheduled_refresh' && typeof details.reconcile_error === 'string') return details.reconcile_error
    return 'No additional details'
  }

  function formatRunSource(source: string) {
    switch (source) {
      case 'budget_import': return 'Budget Import'
      case 'ynab_sync': return 'YNAB Sync'
      case 'reconcile': return 'Reconcile'
      case 'scheduled_refresh': return 'Scheduled Refresh'
      default: return source
    }
  }

  function describeFreshness(status: string | undefined) {
    switch (status) {
      case 'fresh': return 'Fresh'
      case 'warning': return 'Warning'
      case 'critical': return 'Critical'
      case 'missing': return 'Missing'
      default: return 'Unknown'
    }
  }

  function describeActualsFreshness(status: StatusResponse | undefined) {
    const freshness = status?.actuals_freshness
    if (!freshness) return 'No sync state available'
    if (freshness.status === 'missing') return 'YNAB has not been synced yet'
    if (typeof freshness.hours_stale === 'number') return `${freshness.hours_stale.toFixed(1)} hours stale`
    return `Last sync ${formatRunAt(freshness.last_updated_at)}`
  }

  function basename(value: string | undefined) {
    if (!value) return 'Budget.xlsx'
    const parts = value.split(/[\\/]/)
    return parts[parts.length - 1] || value
  }
</script>

<div class="space-y-6">
  <FailureCauseCard status={$statusQuery.data} onRetry={handleRetry} {retrying} />

  {#if reconcileFailed && planImported}
    <ReconcilePreviewCard
      preview={$previewQuery.data}
      isLoading={$previewQuery.isLoading}
      isError={$previewQuery.isError}
      error={$previewQuery.error}
      onRefresh={() => $previewQuery.refetch()}
      onRetryReconcile={() => $reconcileMutation.mutate()}
      retrying={$reconcileMutation.isPending}
    />
  {/if}

  <AutomationStatusCard status={$statusQuery.data} />

  <Card class="border-border/40 bg-card">
    <CardHeader>
      <CardTitle>Operations</CardTitle>
      <p class="text-sm text-muted-foreground">
        Trigger data refreshes and reconciliation for {formatMonthLabel(month)}.
      </p>
    </CardHeader>
    <CardContent class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {@render opButton('Import Budget', 'Reload the current workbook export into SQLite.', $importMutation.isPending, () => $importMutation.mutate())}
      {@render opButton('Sync YNAB', 'Pull new accounts, categories, and transaction deltas.', $syncMutation.isPending, () => $syncMutation.mutate())}
      {@render opButton('Reconcile', 'Verify imported sheet categories still match YNAB exactly.', $reconcileMutation.isPending, () => $reconcileMutation.mutate())}
      {@render opButton('Refresh All', 'Run import, sync, and reconcile sequentially.', $refreshMutation.isPending, () => $refreshMutation.mutate())}
    </CardContent>
  </Card>

  <div class="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
    <Card class="border-border/40 bg-card">
      <CardHeader><CardTitle>Recent Runs</CardTitle></CardHeader>
      <CardContent class="space-y-3">
        {#if recentRuns.length}
          {#each recentRuns as run (run.id)}
            <a
              href={withBasePath(`/operations/runs/${run.id}`)}
              class="block rounded-lg bg-muted/30 p-4 transition-colors duration-150 hover:bg-muted/50"
              aria-label={`Open details for ${formatRunSource(run.source)} run #${run.id}`}
            >
              <div class="flex items-center justify-between gap-4">
                <div class="text-label-upper">{formatRunSource(run.source)}</div>
                <StatusChip status={run.status} />
              </div>
              <div class="mt-2 flex items-center justify-between gap-4">
                <div class="font-medium text-foreground">{formatRunAt(run.finished_at)}</div>
                <div class="text-sm text-muted-foreground">{formatRunAt(run.started_at)}</div>
              </div>
              <div class="mt-2 text-sm text-muted-foreground">{describeRun(run)}</div>
            </a>
          {/each}
        {:else}
          <p class="text-sm text-muted-foreground">No operation history yet.</p>
        {/if}
      </CardContent>
    </Card>

    <Card class="border-border/40 bg-card">
      <CardHeader><CardTitle>Current Status</CardTitle></CardHeader>
      <CardContent class="space-y-4 text-sm text-muted-foreground">
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Busy State</div>
          <div class="mt-2 text-foreground">
            {$statusQuery.data?.busy ? `Running ${$statusQuery.data.current_operation ?? 'operation'}` : 'Idle'}
          </div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Plan Data</div>
          <div class="mt-2 text-foreground">{describeFreshness($statusQuery.data?.plan_freshness.status)}</div>
          <div class="mt-1 text-sm text-muted-foreground">Last import {formatRunAt($statusQuery.data?.plan_freshness.last_updated_at)}</div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">YNAB Data</div>
          <div class="mt-2 text-foreground">{describeFreshness($statusQuery.data?.actuals_freshness.status)}</div>
          <div class="mt-1 text-sm text-muted-foreground">{describeActualsFreshness($statusQuery.data)}</div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Mismatch Count</div>
          <div class="mt-2 text-foreground">{$summaryQuery.data?.mismatches.length ?? 0}</div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Budget Import ID</div>
          <div class="mt-2 font-mono text-foreground">{$statusQuery.data?.last_budget_import_id ?? '—'}</div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Plan Source</div>
          <div class="mt-2 text-foreground">{basename($statusQuery.data?.plan_provenance.workbook_path ?? $statusQuery.data?.budget_sheet)}</div>
          <div class="mt-1 text-sm text-muted-foreground">Sheet {$statusQuery.data?.plan_provenance.sheet_name ?? '—'}</div>
        </div>
      </CardContent>
    </Card>
  </div>

  <Card class="border-border/40 bg-card">
    <CardHeader><CardTitle>Latest Operation Payload</CardTitle></CardHeader>
    <CardContent>
      <pre class="overflow-x-auto rounded-lg bg-muted/25 p-4 font-mono text-xs text-slate-100 ring-1 ring-inset ring-border/30">
{JSON.stringify(latestPayload ?? { message: 'No operation triggered in this session.' }, null, 2)}
      </pre>
    </CardContent>
  </Card>
</div>

{#snippet opButton(label: string, description: string, pending: boolean, onClick: () => void)}
  <div class="rounded-xl bg-muted/30 p-5 transition-colors duration-150 hover:bg-muted/50">
    <div class="text-base font-medium text-foreground">{label}</div>
    <p class="mt-2 min-h-12 text-sm text-muted-foreground">{description}</p>
    <button
      class="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
      disabled={busy}
      onclick={onClick}
      type="button"
    >
      {#if pending}<LoaderCircle class="h-4 w-4 animate-spin" />{:else}<RefreshCw class="h-4 w-4" />{/if}
      {label}
    </button>
  </div>
{/snippet}
