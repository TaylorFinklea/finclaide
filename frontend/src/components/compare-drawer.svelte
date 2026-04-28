<script lang="ts">
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { createQuery } from '@tanstack/svelte-query'
  import { Columns2 } from 'lucide-svelte'
  import { writable } from 'svelte/store'

  import DialogDescription from '$components/ui/dialog-description.svelte'
  import DialogHeader from '$components/ui/dialog-header.svelte'
  import DialogTitle from '$components/ui/dialog-title.svelte'
  import SheetContent from '$components/ui/sheet-content.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import Sparkline from '$components/sparkline.svelte'
  import {
    compareScenario,
    getErrorMessage,
    type CompareResponse,
    type CompareRow,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'

  type Props = {
    open: boolean
    scenarioId: number | null
    onClose: () => void
  }
  let { open, scenarioId, onClose }: Props = $props()

  type SortKey =
    | 'name'
    | 'planned_active_milliunits'
    | 'planned_scenario_milliunits'
    | 'vs_active_milliunits'
    | 'vs_actuals_milliunits'

  let sortBy: SortKey = $state('vs_active_milliunits')
  let sortDir: 'asc' | 'desc' = $state('desc')

  type CompareOpts = {
    queryKey: readonly unknown[]
    queryFn: () => Promise<CompareResponse>
    enabled: boolean
  }
  const compareOpts = writable<CompareOpts>({
    queryKey: ['scenarios', 'compare', null],
    queryFn: () => Promise.reject(new Error('disabled')) as Promise<CompareResponse>,
    enabled: false,
  })
  $effect(() => {
    if (scenarioId === null) {
      compareOpts.set({
        queryKey: ['scenarios', 'compare', null],
        queryFn: () => Promise.reject(new Error('disabled')) as Promise<CompareResponse>,
        enabled: false,
      })
    } else {
      const id = scenarioId
      compareOpts.set({
        queryKey: ['scenarios', 'compare', id],
        queryFn: () => compareScenario(id),
        enabled: open,
      })
    }
  })
  const compareQuery = createQuery(compareOpts)

  function toggleSort(key: SortKey) {
    if (sortBy === key) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc'
    } else {
      sortBy = key
      sortDir = 'desc'
    }
  }

  function formatDelta(value: number): string {
    if (value === 0) return '—'
    const f = formatMoney(Math.abs(value))
    return value > 0 ? `+${f}` : `−${f}`
  }

  function deltaClass(value: number): string {
    if (value > 0) return 'text-rose-200'
    if (value < 0) return 'text-emerald-200'
    return 'text-muted-foreground'
  }

  let sortedRows = $derived.by(() => {
    const data = $compareQuery.data
    if (!data) return [] as CompareRow[]
    const rows = [...data.rows]
    rows.sort((a, b) => {
      const av = a[sortBy] as number | string
      const bv = b[sortBy] as number | string
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      const an = Number(av)
      const bn = Number(bv)
      return sortDir === 'asc' ? an - bn : bn - an
    })
    return rows
  })

  $effect(() => {
    if (!open) {
      sortBy = 'vs_active_milliunits'
      sortDir = 'desc'
    }
  })
</script>

<DialogPrimitive.Root bind:open={() => open, (next) => { if (!next) onClose() }}>
  <SheetContent class="border-border/40 bg-card text-card-foreground sm:max-w-3xl" side="right">
    <DialogHeader>
      <DialogTitle class="flex items-center gap-2">
        <Columns2 class="h-4 w-4" />
        Compare scenario
      </DialogTitle>
      <DialogDescription>
        Per-category drilldown vs the active plan and 6-month actuals
        average. Sortable by any column; click headers to toggle.
      </DialogDescription>
    </DialogHeader>

    <div class="mt-6 grid h-[calc(100%-7rem)] gap-4">
      <div class="overflow-y-auto rounded-md border bg-muted/15 p-3" aria-label="Compare table">
        {#if scenarioId === null}
          <div class="text-sm text-muted-foreground">No scenario selected.</div>
        {:else if $compareQuery.isLoading}
          <Skeleton class="h-[400px] rounded" />
        {:else if $compareQuery.isError}
          <div class="text-sm text-rose-200">
            Could not load comparison: {getErrorMessage($compareQuery.error)}
          </div>
        {:else if !$compareQuery.data || $compareQuery.data.rows.length === 0}
          <div class="text-sm text-muted-foreground">
            No categories in either plan.
          </div>
        {:else}
          {@const data = $compareQuery.data}
          <div class="text-[11px] uppercase tracking-wide text-muted-foreground">
            {data.window.months[0]}–{data.window.months[5]} window · {data.rows.length}
            {data.rows.length === 1 ? 'category' : 'categories'}
          </div>
          <div class="mt-3 overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th class="cursor-pointer py-2 pr-3" onclick={() => toggleSort('name')}>
                    Category
                  </th>
                  <th class="cursor-pointer py-2 pr-3 text-right" onclick={() => toggleSort('planned_active_milliunits')}>
                    Active
                  </th>
                  <th class="cursor-pointer py-2 pr-3 text-right" onclick={() => toggleSort('planned_scenario_milliunits')}>
                    Scenario
                  </th>
                  <th class="cursor-pointer py-2 pr-3 text-right" onclick={() => toggleSort('vs_active_milliunits')}>
                    Δ active
                  </th>
                  <th class="cursor-pointer py-2 pr-3 text-right" onclick={() => toggleSort('vs_actuals_milliunits')}>
                    Δ actuals
                  </th>
                  <th class="py-2 pr-1 text-right">Trend</th>
                </tr>
              </thead>
              <tbody>
                {#each sortedRows as row (row.category_id)}
                  <tr class="border-t border-border/30">
                    <td class="py-2 pr-3">
                      <div class="font-medium text-foreground">{row.name}</div>
                      <div class="text-[11px] text-muted-foreground">{row.block}</div>
                    </td>
                    <td class="py-2 pr-3 text-right font-mono text-xs">
                      {formatMoney(row.planned_active_milliunits)}
                    </td>
                    <td class="py-2 pr-3 text-right font-mono text-xs">
                      {formatMoney(row.planned_scenario_milliunits)}
                    </td>
                    <td class={`py-2 pr-3 text-right font-mono text-xs ${deltaClass(row.vs_active_milliunits)}`}>
                      {formatDelta(row.vs_active_milliunits)}
                    </td>
                    <td class={`py-2 pr-3 text-right font-mono text-xs ${deltaClass(row.vs_actuals_milliunits)}`}>
                      {formatDelta(row.vs_actuals_milliunits)}
                    </td>
                    <td class="py-2 pr-1 text-right">
                      <Sparkline values={row.sparkline} title={`${row.name} 6mo trend`} />
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <div class="mt-4 flex items-center justify-between border-t border-border/30 pt-3 text-xs">
            <span class="text-muted-foreground">
              Plan total {formatMoney(data.totals.planned_scenario_milliunits)}
            </span>
            <span class={`font-mono ${deltaClass(data.totals.vs_active_milliunits)}`}>
              {formatDelta(data.totals.vs_active_milliunits)} vs active
            </span>
          </div>
        {/if}
      </div>
    </div>
  </SheetContent>
</DialogPrimitive.Root>
