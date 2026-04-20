<script lang="ts">
  import type { SummaryGroup } from '$lib/api'
  import { formatCompactMoney } from '$lib/format'

  type Props = { groups: SummaryGroup[] }
  let { groups }: Props = $props()

  const PLANNED_COLOR = 'oklch(0.68 0.12 245)'
  const ACTUAL_COLOR = 'oklch(0.72 0.14 160)'
  const HEIGHT = 420
  const BAR_GROUP_GAP = 0.4
  const BAR_GAP = 0.15

  let normalized = $derived(
    groups.map((group) => ({
      group_name: group.group_name,
      planned: Math.max(group.planned_milliunits, 0),
      actual: Math.max(group.actual_milliunits, 0),
    })),
  )
  let maxValue = $derived(
    Math.max(1, ...normalized.flatMap((row) => [row.planned, row.actual])),
  )
</script>

<div class="rounded-md border bg-muted/20 p-4" style:height="{HEIGHT}px">
  {#if normalized.length === 0}
    <div class="flex h-full items-center justify-center text-sm text-muted-foreground">
      No groups to chart yet.
    </div>
  {:else}
    {@const chartHeight = HEIGHT - 80}
    {@const cellWidth = 100 / normalized.length}
    {@const innerCellWidth = cellWidth * (1 - BAR_GROUP_GAP)}
    {@const barWidth = (innerCellWidth - innerCellWidth * BAR_GAP) / 2}
    <div class="flex h-full flex-col">
      <div class="relative grow" style:height="{chartHeight}px">
        <svg
          role="img"
          aria-label="Plan vs actual by group"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          class="absolute inset-0 h-full w-full"
        >
          {#each normalized as row, index (row.group_name)}
            {@const cellLeft = index * cellWidth + (cellWidth * BAR_GROUP_GAP) / 2}
            {@const plannedHeight = (row.planned / maxValue) * 100}
            {@const actualHeight = (row.actual / maxValue) * 100}
            <rect
              x={cellLeft}
              y={100 - plannedHeight}
              width={barWidth}
              height={plannedHeight}
              fill={PLANNED_COLOR}
              rx="0.4"
            >
              <title>Planned {formatCompactMoney(row.planned)}</title>
            </rect>
            <rect
              x={cellLeft + barWidth + innerCellWidth * BAR_GAP}
              y={100 - actualHeight}
              width={barWidth}
              height={actualHeight}
              fill={ACTUAL_COLOR}
              rx="0.4"
            >
              <title>Actual {formatCompactMoney(row.actual)}</title>
            </rect>
          {/each}
        </svg>
      </div>
      <div class="grid gap-1 pt-3 text-xs text-muted-foreground" style:grid-template-columns="repeat({normalized.length}, minmax(0, 1fr))">
        {#each normalized as row (row.group_name)}
          <div class="truncate text-center" title={row.group_name}>{row.group_name}</div>
        {/each}
      </div>
      <div class="mt-3 flex items-center justify-end gap-4 text-xs text-muted-foreground">
        <span class="flex items-center gap-1.5">
          <span class="inline-block h-2.5 w-2.5 rounded-sm" style:background-color={PLANNED_COLOR}></span>
          Planned
        </span>
        <span class="flex items-center gap-1.5">
          <span class="inline-block h-2.5 w-2.5 rounded-sm" style:background-color={ACTUAL_COLOR}></span>
          Actual
        </span>
      </div>
    </div>
  {/if}
</div>
