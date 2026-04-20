<script lang="ts">
  import { Select as SelectPrimitive } from 'bits-ui'
  import { Check } from 'lucide-svelte'
  import type { Snippet } from 'svelte'

  import { cn } from '$lib/utils'

  type Props = SelectPrimitive.ItemProps & { class?: string; children?: Snippet }
  let { class: className, children, value, label, ...rest }: Props = $props()
</script>

<SelectPrimitive.Item
  {value}
  {label}
  class={cn(
    'relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
    className,
  )}
  {...rest}
>
  {#snippet children({ selected })}
    <span class="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      {#if selected}<Check class="h-4 w-4" />{/if}
    </span>
    {label ?? value}
  {/snippet}
</SelectPrimitive.Item>
