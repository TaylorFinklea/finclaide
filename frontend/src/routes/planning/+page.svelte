<script lang="ts">
  import { browser } from '$app/environment'
  import { Tabs as TabsPrimitive } from 'bits-ui'
  import { createQuery } from '@tanstack/svelte-query'
  import { AlertTriangle, History, Plus } from 'lucide-svelte'

  import DataTable, { type DataTableColumn } from '$components/data-table.svelte'
  import PlanCategorySheet, { type EditorSelection } from '$components/plan-category-sheet.svelte'
  import PlanHistorySheet from '$components/plan-history-sheet.svelte'
  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import TabsContent from '$components/ui/tabs-content.svelte'
  import TabsList from '$components/ui/tabs-list.svelte'
  import TabsTrigger from '$components/ui/tabs-trigger.svelte'
  import { BLOCK_LABELS, type BlockKey, type PlanCategory, getActivePlan, getStatus } from '$lib/api'
  import { formatMoney } from '$lib/format'

  const BLOCK_ORDER: BlockKey[] = ['monthly', 'annual', 'one_time', 'stipends', 'savings']

  function blockColumns(block: BlockKey): DataTableColumn<PlanCategory>[] {
    return [
      { key: 'group_name', header: 'Group', cellClass: 'font-medium' },
      { key: 'category_name', header: 'Category' },
      {
        key: 'planned',
        header: 'Planned',
        cell: (row) => formatMoney(row.planned_milliunits),
        cellClass: 'font-mono text-sm',
      },
      {
        key: 'annual',
        header: 'Annual target',
        cell: (row) =>
          row.annual_target_milliunits === 0 && block === 'monthly'
            ? '—'
            : formatMoney(row.annual_target_milliunits),
        cellClass: 'font-mono text-sm text-muted-foreground',
      },
      {
        key: 'due',
        header: 'Due',
        cell: (row) => (row.due_month === null ? '—' : String(row.due_month).padStart(2, '0')),
        cellClass: 'font-mono text-sm',
      },
      { key: 'notes', header: 'Notes', cell: (row) => row.notes ?? '—', cellClass: 'text-sm text-muted-foreground' },
    ]
  }

  const planQuery = createQuery({
    queryKey: ['plan', 'active'],
    queryFn: () => getActivePlan(),
    enabled: browser,
  })
  const statusQuery = createQuery({ queryKey: ['status'], queryFn: getStatus, enabled: browser })

  let activeBlock: BlockKey = $state('monthly')
  let selection: EditorSelection = $state(null)
  let historyOpen = $state(false)

  let importBusy = $derived(
    $statusQuery.data?.busy === true && $statusQuery.data?.current_operation === 'budget_import',
  )
</script>

{#if $planQuery.isLoading}
  <Skeleton class="h-[640px] rounded-2xl" />
{:else if $planQuery.isError}
  <Card class="border-border/40 bg-card">
    <CardHeader><CardTitle>Planning is unavailable</CardTitle></CardHeader>
    <CardContent class="text-sm text-muted-foreground">
      {$planQuery.error instanceof Error ? $planQuery.error.message : 'Could not load the active plan.'}
      <p class="mt-3">If you have not imported a budget yet, run an import from the Operations page first.</p>
    </CardContent>
  </Card>
{:else if $planQuery.data}
  {@const data = $planQuery.data}
  <div class="space-y-6">
    {#if importBusy}
      <Card class="border-amber-500/30 bg-amber-500/[0.06]" role="status" aria-live="polite">
        <CardHeader class="space-y-1">
          <CardTitle class="flex items-center gap-2 text-amber-100">
            <AlertTriangle class="h-4 w-4" />
            Budget import in progress
          </CardTitle>
          <p class="text-sm text-amber-100/80">
            Saved edits may be overwritten when the import completes. Wait or coordinate before saving.
          </p>
        </CardHeader>
      </Card>
    {/if}

    <Card class="border-border/40 bg-card">
      <CardHeader class="space-y-3">
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle>Planning — {data.plan.name}</CardTitle>
            <p class="mt-2 text-sm text-muted-foreground">
              Active plan for {data.plan.plan_year}. Click any row to edit; use Add row to create a new
              category in the current block.
            </p>
          </div>
          <div class="text-right text-sm text-muted-foreground">
            <div>Plan total {formatMoney(Number(data.totals.grand_total_milliunits ?? 0))}</div>
            <div class="text-xs">Source: {data.plan.source}</div>
          </div>
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        <TabsPrimitive.Root bind:value={activeBlock}>
          <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <TabsList>
              {#each BLOCK_ORDER as key (key)}
                <TabsTrigger value={key}>{BLOCK_LABELS[key]}</TabsTrigger>
              {/each}
            </TabsList>
            <div class="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onclick={() => (historyOpen = true)}
                disabled={importBusy}
              >
                <History class="h-4 w-4" />
                History
              </Button>
              <Button
                size="sm"
                onclick={() => (selection = { mode: 'create', planId: data.plan.id, block: activeBlock })}
              >
                <Plus class="h-4 w-4" />
                Add row
              </Button>
            </div>
          </div>

          {#each BLOCK_ORDER as key (key)}
            <TabsContent value={key} class="mt-4">
              {@render blockPanel(key, data.blocks[key], Number(data.totals[`${key}_milliunits`] ?? 0))}
            </TabsContent>
          {/each}
        </TabsPrimitive.Root>
      </CardContent>
    </Card>

    <PlanCategorySheet {selection} onClose={() => (selection = null)} />
    <PlanHistorySheet
      open={historyOpen}
      planId={data.plan.id}
      currentBlocks={data.blocks}
      onClose={() => (historyOpen = false)}
    />
  </div>
{/if}

{#snippet blockPanel(block: BlockKey, rows: PlanCategory[], total: number)}
  {@const columns = blockColumns(block)}
  <div class="space-y-3">
    <div class="flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {rows.length} {rows.length === 1 ? 'category' : 'categories'} in {BLOCK_LABELS[block]}
      </span>
      <span class="font-mono text-foreground">Block total {formatMoney(total)}</span>
    </div>
    <DataTable
      data={rows}
      {columns}
      onRowClick={(row) => (selection = { mode: 'edit', planId: rows[0]?.plan_id ?? 0, category: row })}
      emptyMessage={`No ${BLOCK_LABELS[block]} categories yet. Click Add row to create one.`}
    />
  </div>
{/snippet}
