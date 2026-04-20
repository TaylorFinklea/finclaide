<script lang="ts">
  import { Select as SelectPrimitive } from 'bits-ui'
  import { ChevronDown } from 'lucide-svelte'
  import type { Snippet } from 'svelte'

  import { cn } from '$lib/utils'

  type Props = SelectPrimitive.TriggerProps & { class?: string; children?: Snippet }
  let { class: className, children, ...rest }: Props = $props()
</script>

<SelectPrimitive.Trigger
  class={cn(
    'flex h-9 w-full items-center justify-between whitespace-nowrap rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background data-[placeholder]:text-muted-foreground [&>span]:line-clamp-1 focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
    className,
  )}
  {...rest}
>
  {@render children?.()}
  <ChevronDown class="h-4 w-4 opacity-50" />
</SelectPrimitive.Trigger>
