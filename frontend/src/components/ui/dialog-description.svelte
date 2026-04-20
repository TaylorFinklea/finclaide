<script lang="ts">
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import type { Snippet } from 'svelte'

  import { cn } from '$lib/utils'

  type Props = DialogPrimitive.DescriptionProps & { class?: string; children?: Snippet }
  let { class: className, children, ...rest }: Props = $props()
</script>

<DialogPrimitive.Description class={cn('text-sm text-muted-foreground', className)} {...rest}>
  {@render children?.()}
</DialogPrimitive.Description>
