<script lang="ts">
  import { Tabs as TabsPrimitive } from 'bits-ui'
  import type { Snippet } from 'svelte'

  import { cn } from '$lib/utils'

  type Props = TabsPrimitive.ContentProps & { class?: string; children?: Snippet }
  let { class: className, children, ...rest }: Props = $props()
</script>

<TabsPrimitive.Content
  class={cn(
    'mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
    className,
  )}
  {...rest}
>
  {@render children?.()}
</TabsPrimitive.Content>
