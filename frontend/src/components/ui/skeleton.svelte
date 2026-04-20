<script lang="ts">
  import type { HTMLAttributes } from 'svelte/elements'

  import { cn } from '$lib/utils'

  type Props = HTMLAttributes<HTMLDivElement> & { class?: string }
  let { class: className, ...rest }: Props = $props()
</script>

<div class={cn('animate-pulse rounded-md bg-muted', className)} {...rest}></div>
