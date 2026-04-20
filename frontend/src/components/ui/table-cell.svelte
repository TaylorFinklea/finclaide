<script lang="ts">
  import type { Snippet } from 'svelte'
  import type { HTMLTdAttributes } from 'svelte/elements'

  import { cn } from '$lib/utils'

  type Props = HTMLTdAttributes & { class?: string; children?: Snippet }
  let { class: className, children, ...rest }: Props = $props()
</script>

<td
  class={cn('p-2 align-middle [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]', className)}
  {...rest}
>
  {@render children?.()}
</td>
