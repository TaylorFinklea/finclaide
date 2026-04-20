<script lang="ts">
  import { ScanSearch } from 'lucide-svelte'

  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import { getErrorMessage, type ReconcilePreviewResponse } from '$lib/api'

  type Props = {
    preview: ReconcilePreviewResponse | undefined
    isLoading: boolean
    isError: boolean
    error: unknown
    onRefresh?: () => void
    onRetryReconcile?: () => void
    retrying?: boolean
  }

  let { preview, isLoading, isError, error, onRefresh, onRetryReconcile, retrying }: Props = $props()
</script>

<Card class="border-amber-500/30 bg-amber-500/[0.05]">
  <CardHeader class="space-y-3">
    <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div>
        <CardTitle class="flex items-center gap-2 text-amber-100">
          <ScanSearch class="h-4 w-4" />
          Reconcile preview
        </CardTitle>
        <p class="mt-2 text-sm text-amber-100/80">
          Read-only diff of the imported plan against current YNAB categories. No data is changed.
        </p>
      </div>
      <div class="flex gap-2">
        {#if onRefresh}
          <Button variant="outline" class="border-amber-200/30 text-amber-50 hover:bg-amber-500/10" onclick={onRefresh}>
            Refresh preview
          </Button>
        {/if}
        {#if onRetryReconcile}
          <Button
            variant="outline"
            class="border-amber-200/30 text-amber-50 hover:bg-amber-500/10"
            disabled={retrying}
            onclick={onRetryReconcile}
          >
            {retrying ? 'Re-running…' : 'Re-run reconcile'}
          </Button>
        {/if}
      </div>
    </div>
  </CardHeader>
  <CardContent class="space-y-4">
    {#if isLoading}
      <Skeleton class="h-32 rounded-lg" />
    {:else if isError}
      <div class="rounded-lg bg-rose-500/[0.08] p-4 text-sm text-rose-100 ring-1 ring-inset ring-rose-500/20">
        Could not load reconcile preview: {getErrorMessage(error)}
      </div>
    {:else if preview}
      <div class="grid gap-3 md:grid-cols-3">
        <div class="rounded-lg p-4 ring-1 ring-inset border-emerald-400/30 bg-emerald-500/[0.06] text-emerald-100">
          <div class="text-label-upper">Exact matches</div>
          <div class="mt-2 font-mono text-2xl font-semibold">{preview.counts.exact}</div>
        </div>
        <div class="rounded-lg p-4 ring-1 ring-inset border-rose-400/30 bg-rose-500/[0.08] text-rose-100">
          <div class="text-label-upper">Missing in YNAB</div>
          <div class="mt-2 font-mono text-2xl font-semibold">{preview.counts.missing_in_ynab}</div>
        </div>
        <div class="rounded-lg p-4 ring-1 ring-inset border-cyan-400/30 bg-cyan-500/[0.06] text-cyan-100">
          <div class="text-label-upper">Extra in YNAB</div>
          <div class="mt-2 font-mono text-2xl font-semibold">{preview.counts.extra_in_ynab}</div>
        </div>
      </div>

      <div class="rounded-lg bg-amber-500/[0.04] p-4">
        <div class="flex items-baseline justify-between gap-3">
          <div class="text-sm font-medium text-amber-50">Missing in YNAB</div>
          <div class="text-label">{preview.missing_in_ynab.length}</div>
        </div>
        <p class="mt-1 text-sm text-amber-100/70">
          In your plan but not present in YNAB. These are the cause of reconcile failure.
        </p>
        {#if preview.missing_in_ynab.length === 0}
          <div class="mt-3 rounded-lg p-3 text-sm bg-emerald-500/[0.06] text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
            No missing categories. Plan rows all map to a YNAB category.
          </div>
        {:else}
          <ul class="mt-3 space-y-1.5">
            {#each preview.missing_in_ynab as row (row.group_name + '/' + row.category_name)}
              <li class="flex items-center justify-between gap-3 rounded-md bg-muted/30 px-3 py-2 text-sm">
                <span class="text-foreground">{row.group_name} / {row.category_name}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <div class="rounded-lg bg-amber-500/[0.04] p-4">
        <div class="flex items-baseline justify-between gap-3">
          <div class="text-sm font-medium text-amber-50">Extra in YNAB</div>
          <div class="text-label">{preview.extra_in_ynab.length}</div>
        </div>
        <p class="mt-1 text-sm text-amber-100/70">
          Present in YNAB but not in your plan. Often a renamed category or a YNAB-side addition.
        </p>
        {#if preview.extra_in_ynab.length === 0}
          <div class="mt-3 rounded-lg p-3 text-sm bg-emerald-500/[0.06] text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
            No extra YNAB categories outside the plan.
          </div>
        {:else}
          <ul class="mt-3 space-y-1.5">
            {#each preview.extra_in_ynab as row (row.group_name + '/' + row.category_name)}
              <li class="flex items-center justify-between gap-3 rounded-md bg-muted/30 px-3 py-2 text-sm">
                <span class="text-foreground">{row.group_name} / {row.category_name}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}
  </CardContent>
</Card>
