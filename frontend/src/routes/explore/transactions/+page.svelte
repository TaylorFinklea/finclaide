<script lang="ts">
  import { browser } from '$app/environment'
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { createQuery } from '@tanstack/svelte-query'
  import { writable } from 'svelte/store'

  import DataTable, { type DataTableColumn } from '$components/data-table.svelte'
  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import DialogDescription from '$components/ui/dialog-description.svelte'
  import DialogHeader from '$components/ui/dialog-header.svelte'
  import DialogTitle from '$components/ui/dialog-title.svelte'
  import Input from '$components/ui/input.svelte'
  import SheetContent from '$components/ui/sheet-content.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import { getSummary, getTransactions, type TransactionRow } from '$lib/api'
  import { formatDay, formatMoney } from '$lib/format'
  import { monthStore } from '$lib/stores/month.svelte'

  const PAGE_SIZE = 25

  let month = $derived(monthStore.value)
  let group = $state('all')
  let category = $state('all')
  let search = $state('')
  // svelte-ignore state_referenced_locally
  let since = $state(`${month}-01`)
  let until = $state('')
  let offset = $state(0)
  let selected: TransactionRow | null = $state(null)

  $effect(() => {
    since = `${month}-01`
    offset = 0
  })

  const summaryOpts = writable({
    queryKey: ['summary', monthStore.value] as readonly unknown[],
    queryFn: () => getSummary(monthStore.value),
    enabled: browser,
  })
  const transactionsOpts = writable<{
    queryKey: readonly unknown[]
    queryFn: () => Promise<Awaited<ReturnType<typeof getTransactions>>>
    enabled: boolean
  }>({
    queryKey: ['transactions', monthStore.value],
    queryFn: () => getTransactions({ since: `${monthStore.value}-01`, until: '', limit: PAGE_SIZE, offset: 0 }),
    enabled: browser,
  })
  $effect(() => {
    summaryOpts.set({
      queryKey: ['summary', month],
      queryFn: () => getSummary(month),
      enabled: browser,
    })
    transactionsOpts.set({
      queryKey: ['transactions', month, group, category, search, since, until, offset],
      queryFn: () =>
        getTransactions({
          since,
          until,
          group: group === 'all' ? undefined : group,
          category: category === 'all' ? undefined : category,
          q: search || undefined,
          limit: PAGE_SIZE,
          offset,
        }),
      enabled: browser,
    })
  })
  const summaryQuery = createQuery(summaryOpts)
  const transactionsQuery = createQuery(transactionsOpts)

  let groupOptions = $derived($summaryQuery.data?.groups.map((g) => g.group_name) ?? [])
  let categoryOptions = $derived(() => {
    const all =
      $summaryQuery.data?.groups.flatMap((g) =>
        g.categories.map((c) => ({ group_name: g.group_name, category_name: c.category_name })),
      ) ?? []
    return group === 'all' ? all : all.filter((item) => item.group_name === group)
  })

  const columns: DataTableColumn<TransactionRow>[] = [
    { key: 'date', header: 'Date', cell: (row) => formatDay(row.date), cellClass: 'font-mono text-sm text-muted-foreground' },
    { key: 'payee', header: 'Payee', cell: (row) => row.payee_name ?? 'No payee' },
    { key: 'group', header: 'Group', cell: (row) => row.group_name ?? '—' },
    { key: 'category', header: 'Category', cell: (row) => row.category_name ?? '—' },
    {
      key: 'amount',
      header: 'Amount',
      snippet: amountCell,
      cellClass: 'text-right',
    },
  ]
</script>

{#snippet amountCell(row: TransactionRow)}
  <span class={row.amount_milliunits < 0 ? 'font-mono text-rose-200' : 'font-mono text-emerald-200'}>
    {formatMoney(row.amount_milliunits)}
  </span>
{/snippet}

{#if $summaryQuery.isLoading || $transactionsQuery.isLoading}
  <Skeleton class="h-[640px] rounded-xl" />
{:else if $transactionsQuery.data}
  {@const page = $transactionsQuery.data}
  <div class="space-y-6">
    <Card class="border-border/40 bg-card">
      <CardHeader class="space-y-4">
        <div>
          <CardTitle>Transactions</CardTitle>
          <p class="mt-2 text-sm text-muted-foreground">Search payees and memos, then drill into individual rows.</p>
        </div>
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Input bind:value={search} placeholder="Search payee or memo" />
          <select
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            bind:value={group}
            onchange={() => { category = 'all'; offset = 0 }}
          >
            <option value="all">All groups</option>
            {#each groupOptions as opt (opt)}
              <option value={opt}>{opt}</option>
            {/each}
          </select>
          <select
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            bind:value={category}
            onchange={() => { offset = 0 }}
          >
            <option value="all">All categories</option>
            {#each categoryOptions() as opt (`${opt.group_name}-${opt.category_name}`)}
              <option value={opt.category_name}>{opt.category_name}</option>
            {/each}
          </select>
          <Input type="date" bind:value={since} />
          <Input type="date" bind:value={until} />
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="flex items-center justify-between text-sm text-muted-foreground">
          <span>Showing {page.transactions.length} of {page.total_count} transactions</span>
          <div class="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onclick={() => (offset = Math.max(offset - PAGE_SIZE, 0))}>
              Previous
            </Button>
            <Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= page.total_count} onclick={() => (offset = offset + PAGE_SIZE)}>
              Next
            </Button>
          </div>
        </div>
        <DataTable
          data={page.transactions}
          {columns}
          emptyMessage="No transactions match the current filters."
          onRowClick={(row) => (selected = row)}
        />
      </CardContent>
    </Card>
  </div>

  <DialogPrimitive.Root bind:open={() => selected !== null, (next) => { if (!next) selected = null }}>
    <SheetContent class="border-border/40 bg-card text-card-foreground sm:max-w-lg" side="right">
      {#if selected}
        <DialogHeader>
          <DialogTitle>{selected.payee_name ?? 'No payee name'}</DialogTitle>
          <DialogDescription>
            {selected.group_name ?? 'No group'} / {selected.category_name ?? 'No category'}
          </DialogDescription>
        </DialogHeader>
        <div class="mt-8 space-y-4">
          <div class="rounded-lg bg-muted/30 p-4">
            <div class="text-label">Date</div>
            <div class="mt-1.5 text-sm text-foreground">{formatDay(selected.date)}</div>
          </div>
          <div class="rounded-lg bg-muted/30 p-4">
            <div class="text-label">Amount</div>
            <div class="mt-1.5 text-sm text-foreground">{formatMoney(selected.amount_milliunits)}</div>
          </div>
          <div class="rounded-lg bg-muted/30 p-4">
            <div class="text-label">Memo</div>
            <div class="mt-1.5 text-sm text-foreground">{selected.memo ?? '—'}</div>
          </div>
          <div class="rounded-lg bg-muted/30 p-4">
            <div class="text-label">Transaction ID</div>
            <div class="mt-1.5 break-all font-mono text-sm text-foreground">{selected.id}</div>
          </div>
        </div>
      {/if}
    </SheetContent>
  </DialogPrimitive.Root>
{/if}
