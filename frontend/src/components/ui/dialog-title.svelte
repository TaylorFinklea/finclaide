<script lang="ts">
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import type { Snippet } from 'svelte'

  import { cn } from '$lib/utils'

  type Props = DialogPrimitive.TitleProps & { class?: string; children?: Snippet }
  let { class: className, children, ...rest }: Props = $props()
</script>

<DialogPrimitive.Title
  class={cn('text-lg font-semibold leading-none tracking-tight', className)}
  {...rest}
>
  {@render children?.()}
</DialogPrimitive.Title>
