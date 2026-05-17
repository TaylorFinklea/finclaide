<script lang="ts">
  import { browser } from '$app/environment'
  import { createQuery } from '@tanstack/svelte-query'
  import { writable } from 'svelte/store'

  import DataTable, { type DataTableColumn } from '$components/data-table.svelte'
  import StatusChip from '$components/status-chip.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Input from '$components/ui/input.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import { getSummary, type SummaryCategory } from '$lib/api'
  import { formatMoney, formatMonthLabel } from '$lib/format'
  import { monthStore } from '$lib/stores/month.svelte'

  type Row = SummaryCategory & { group_name: string }

  let month = $derived(monthStore.value)
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

  let search = $state('')
  let groupFilter = $state('all')
  let statusFilter = $state('all')
  let cadenceFilter = $state<'all' | 'monthly' | 'annual'>('all')

  let allRows = $derived(
    $summaryQuery.data?.groups.flatMap((group) =>
      group.categories.map<Row>((category) => ({ ...category, group_name: group.group_name })),
    ) ?? [],
  )

  let groupOptions = $derived(
    Array.from(new Set(allRows.map((row) => row.group_name))).sort((a, b) => a.localeCompare(b)),
  )
  let statusOptions = $derived(
    Array.from(new Set(allRows.map((row) => row.status))).sort((a, b) => a.localeCompare(b)),
  )

  let filteredRows = $derived(
    allRows.filter((row) => {
      if (groupFilter !== 'all' && row.group_name !== groupFilter) return false
      if (statusFilter !== 'all' && row.status !== statusFilter) return false
      if (cadenceFilter === 'annual' && row.due_month === null) return false
      if (cadenceFilter === 'monthly' && row.due_month !== null) return false
      const q = search.trim().toLowerCase()
      if (q && !`${row.group_name} ${row.category_name}`.toLowerCase().includes(q)) return false
      return true
    }),
  )

  let totals = $derived({
    visible: filteredRows.length,
    planned: filteredRows.reduce((sum, row) => sum + row.planned_milliunits, 0),
    actual: filteredRows.reduce((sum, row) => sum + row.actual_milliunits, 0),
  })

  const columns: DataTableColumn<Row>[] = [
    { key: 'group_name', header: 'Group' },
    { key: 'category_name', header: 'Category' },
    { key: 'planned', header: 'Planned', cell: (row) => formatMoney(row.planned_milliunits), cellClass: 'font-mono text-sm' },
    { key: 'actual', header: 'Actual', cell: (row) => formatMoney(row.actual_milliunits), cellClass: 'font-mono text-sm' },
    { key: 'variance', header: 'Variance', cell: (row) => formatMoney(row.variance_milliunits), cellClass: 'font-mono text-sm' },
    { key: 'balance', header: 'Balance', cell: (row) => formatMoney(row.current_balance_milliunits), cellClass: 'font-mono text-sm' },
    { key: 'due', header: 'Due', cell: (row) => (row.due_month === null ? '—' : String(row.due_month)) },
    {
      key: 'status',
      header: 'Status',
      snippet: statusCell,
    },
  ]

  {/* svelte-ignore unused_export_let */}
</script>

{#snippet statusCell(row: Row)}
  <StatusChip status={row.status} />
{/snippet}

{#if $summaryQuery.isLoading}
  <Skeleton class="h-[640px] rounded-xl" />
{:else if $summaryQuery.data}
  <div class="space-y-6">
    <Card class="border-border/40 bg-card">
      <CardHeader class="space-y-4">
        <div>
          <CardTitle>Categories</CardTitle>
          <p class="mt-2 text-sm text-muted-foreground">
            Filter the {allRows.length} categories planned for {formatMonthLabel(month)}.
          </p>
        </div>
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Input bind:value={search} placeholder="Search group or category" />
          <select
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            bind:value={groupFilter}
          >
            <option value="all">All groups</option>
            {#each groupOptions as opt (opt)}
              <option value={opt}>{opt}</option>
            {/each}
          </select>
          <select
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            bind:value={statusFilter}
          >
            <option value="all">All statuses</option>
            {#each statusOptions as opt (opt)}
              <option value={opt}>{opt}</option>
            {/each}
          </select>
          <select
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            bind:value={cadenceFilter}
          >
            <option value="all">All cadences</option>
            <option value="monthly">Monthly</option>
            <option value="annual">Annual / one-time</option>
          </select>
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="flex items-center justify-between text-sm text-muted-foreground">
          <span>{totals.visible} categories visible</span>
          <span class="font-mono">
            Planned {formatMoney(totals.planned)} · Actual {formatMoney(totals.actual)}
          </span>
        </div>
        <DataTable
          data={filteredRows}
          {columns}
          emptyMessage="No categories match the current filters."
        />
      </CardContent>
    </Card>
  </div>
{/if}
