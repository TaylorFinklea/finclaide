<script lang="ts">
  import type {
    ActivePlanResponse,
    CompareResponse,
    PlanCategory,
    SummaryResponse,
  } from '$lib/api'
  import { accentForGroup } from '$lib/design/tokens'
  import { formatMoney } from '$lib/format'

  let {
    plan,
    summary,
    compare,
    filter = 'all',
    onEditCategory,
  }: {
    plan: ActivePlanResponse
    summary: SummaryResponse | undefined
    compare: CompareResponse | undefined
    filter?: 'all' | 'edited' | 'monthly' | 'sinking' | 'stipends'
    onEditCategory?: (category: PlanCategory) => void
  } = $props()

  type Group = {
    name: string
    categories: PlanCategory[]
    plannedTotal: number
  }

  const BLOCK_KIND_LABEL: Record<PlanCategory['block'], string> = {
    monthly: 'monthly',
    annual: 'annual',
    one_time: 'one-time',
    stipends: 'stipend',
    savings: 'sinking',
  }

  function categoryMatchesFilter(c: PlanCategory, edited: boolean): boolean {
    if (filter === 'all') return true
    if (filter === 'edited') return edited
    if (filter === 'monthly') return c.block === 'monthly'
    if (filter === 'sinking') return c.block === 'annual' || c.block === 'savings'
    if (filter === 'stipends') return c.block === 'stipends'
    return true
  }

  let editedByCategoryId = $derived.by<Map<number, number>>(() => {
    const map = new Map<number, number>()
    for (const row of compare?.rows ?? []) {
      if (row.vs_active_milliunits !== 0) {
        map.set(row.category_id, row.planned_active_milliunits)
      }
    }
    return map
  })

  let summaryByKey = $derived.by<Map<string, { balance: number; actual: number }>>(() => {
    const map = new Map<string, { balance: number; actual: number }>()
    for (const group of summary?.groups ?? []) {
      for (const cat of group.categories) {
        const key = `${group.group_name}::${cat.category_name}`
        map.set(key, {
          balance: cat.current_balance_milliunits,
          actual: cat.actual_milliunits,
        })
      }
    }
    return map
  })

  let groups = $derived.by<Group[]>(() => {
    // Cross every block into a single dimension grouped by group_name.
    const acc = new Map<string, PlanCategory[]>()
    for (const block of Object.values(plan.blocks)) {
      for (const cat of block) {
        const list = acc.get(cat.group_name) ?? []
        list.push(cat)
        acc.set(cat.group_name, list)
      }
    }
    const out: Group[] = []
    for (const [name, cats] of acc) {
      const visible = cats.filter((c) =>
        categoryMatchesFilter(c, editedByCategoryId.has(c.id)),
      )
      if (visible.length === 0) continue
      out.push({
        name,
        categories: visible,
        plannedTotal: visible.reduce((s, c) => s + c.planned_milliunits, 0),
      })
    }
    return out
  })

  let totalLines = $derived(groups.reduce((s, g) => s + g.categories.length, 0))
  let editedCount = $derived(editedByCategoryId.size)
</script>

<div class="rounded-xl border border-border bg-card">
  <div class="flex items-baseline justify-between border-b border-border px-[18px] py-3.5">
    <h3 class="m-0 text-sm font-semibold tracking-[-0.01em]">Categories</h3>
    <div class="text-[11px] text-muted-foreground">
      {totalLines} lines{editedCount > 0 ? ` · ${editedCount} edited` : ''}
    </div>
  </div>
  <div class="px-1.5 pb-1.5">
    <table class="w-full border-collapse text-[13px]">
      <thead>
        <tr class="text-[11px] uppercase tracking-[0.04em] text-muted-foreground">
          <th class="px-3 py-2 text-left font-medium">Category</th>
          <th class="px-3 py-2 text-left font-medium">Kind</th>
          <th class="w-[100px] px-3 py-2 text-right font-medium">Plan</th>
          <th class="w-[80px] px-3 py-2 text-right font-medium">Due</th>
          <th class="w-[100px] px-3 py-2 text-right font-medium">Balance</th>
          <th class="w-[100px] px-3 py-2 text-right font-medium">Actual</th>
        </tr>
      </thead>
      <tbody>
        {#each groups as group (group.name)}
          <tr class="border-y border-border bg-secondary/60">
            <td class="px-3 py-2.5" colspan={6}>
              <span class="inline-flex items-baseline gap-2 text-[13px] font-semibold">
                <span
                  class="inline-block h-2.5 w-2.5 rounded-[3px]"
                  style="background:{accentForGroup(group.name)}"
                ></span>
                {group.name}
                <span class="text-xs font-normal text-muted-foreground">
                  · {group.categories.length} · {formatMoney(group.plannedTotal).replace('.00', '')}/mo
                </span>
              </span>
            </td>
          </tr>
          {#each group.categories as cat (cat.id)}
            {@const editedPrev = editedByCategoryId.get(cat.id)}
            {@const edited = editedPrev !== undefined}
            {@const sumKey = `${cat.group_name}::${cat.category_name}`}
            {@const stats = summaryByKey.get(sumKey)}
            <tr
              class="cursor-pointer transition-colors hover:bg-secondary/40"
              style={edited ? 'background:rgba(78,70,229,0.04)' : undefined}
              onclick={() => onEditCategory?.(cat)}
            >
              <td class="px-3 py-2 pl-8">
                {cat.category_name}
                {#if edited}
                  <span
                    class="ml-2 rounded px-1.5 py-[1px] text-[10px] font-semibold text-[#4E46E5]"
                    style="background:#EDEBFF"
                  >
                    EDITED
                  </span>
                {/if}
              </td>
              <td class="px-3 py-2 text-[11px] text-muted-foreground">
                {BLOCK_KIND_LABEL[cat.block]}
              </td>
              <td class="px-3 py-2 text-right tabular-nums">
                {#if edited && editedPrev !== undefined}
                  <span class="text-muted-foreground line-through">{formatMoney(editedPrev).replace('.00', '')}</span>
                  <b class="text-[#4E46E5]">{formatMoney(cat.planned_milliunits).replace('.00', '')}</b>
                {:else}
                  {formatMoney(cat.planned_milliunits).replace('.00', '')}
                {/if}
              </td>
              <td class="px-3 py-2 text-right text-muted-foreground">
                {cat.due_month ? `M${cat.due_month}` : '—'}
              </td>
              <td class="px-3 py-2 text-right text-muted-foreground">
                {stats && stats.balance ? formatMoney(stats.balance).replace('.00', '') : '—'}
              </td>
              <td class="px-3 py-2 text-right tabular-nums">
                {stats ? formatMoney(stats.actual).replace('.00', '') : '—'}
              </td>
            </tr>
          {/each}
        {/each}
        {#if groups.length === 0}
          <tr>
            <td class="px-3 py-6 text-center text-sm text-muted-foreground" colspan={6}>
              No categories match this filter.
            </td>
          </tr>
        {/if}
      </tbody>
    </table>
  </div>
</div>
