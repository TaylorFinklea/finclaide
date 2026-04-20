<script lang="ts" module>
  export type DataTableColumn<T> = {
    key: string
    header: string
    cell?: (row: T) => string
    snippet?: import('svelte').Snippet<[T]>
    headClass?: string
    cellClass?: string
  }
</script>

<script lang="ts" generics="T">
  import Table from '$components/ui/table.svelte'
  import TableBody from '$components/ui/table-body.svelte'
  import TableCell from '$components/ui/table-cell.svelte'
  import TableHead from '$components/ui/table-head.svelte'
  import TableHeader from '$components/ui/table-header.svelte'
  import TableRow from '$components/ui/table-row.svelte'

  type Props = {
    data: T[]
    columns: DataTableColumn<T>[]
    emptyMessage?: string
    onRowClick?: (row: T) => void
  }

  let { data, columns, emptyMessage = 'No data.', onRowClick }: Props = $props()
</script>

<div class="rounded-md border bg-muted/15">
  <Table>
    <TableHeader>
      <TableRow class="bg-muted/25 hover:bg-muted/25">
        {#each columns as column (column.key)}
          <TableHead class={column.headClass ?? 'text-[11px] font-medium tracking-wide'}>
            {column.header}
          </TableHead>
        {/each}
      </TableRow>
    </TableHeader>
    <TableBody>
      {#if data.length === 0}
        <TableRow>
          <TableCell class="text-center text-sm text-muted-foreground" colspan={columns.length}>
            {emptyMessage}
          </TableCell>
        </TableRow>
      {:else}
        {#each data as row, index (index)}
          <TableRow
            class={`${index % 2 === 1 ? 'bg-muted/[0.08]' : ''} ${onRowClick ? 'cursor-pointer' : ''}`}
            onclick={onRowClick ? () => onRowClick(row) : undefined}
          >
            {#each columns as column (column.key)}
              <TableCell class={column.cellClass}>
                {#if column.snippet}
                  {@render column.snippet(row)}
                {:else if column.cell}
                  {column.cell(row)}
                {:else}
                  {(row as Record<string, unknown>)[column.key] ?? ''}
                {/if}
              </TableCell>
            {/each}
          </TableRow>
        {/each}
      {/if}
    </TableBody>
  </Table>
</div>
