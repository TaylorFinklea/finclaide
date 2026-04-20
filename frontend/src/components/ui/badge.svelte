<script lang="ts" module>
  import { cva, type VariantProps } from 'class-variance-authority'

  export const badgeVariants = cva(
    'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
    {
      variants: {
        variant: {
          default: 'border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80',
          secondary: 'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
          destructive: 'border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80',
          outline: 'text-foreground',
        },
      },
      defaultVariants: {
        variant: 'default',
      },
    },
  )

  export type BadgeVariants = VariantProps<typeof badgeVariants>
</script>

<script lang="ts">
  import type { Snippet } from 'svelte'
  import type { HTMLAttributes } from 'svelte/elements'

  import { cn } from '$lib/utils'

  type Props = HTMLAttributes<HTMLDivElement> & {
    variant?: BadgeVariants['variant']
    class?: string
    children?: Snippet
  }
  let { variant, class: className, children, ...rest }: Props = $props()
</script>

<div class={cn(badgeVariants({ variant }), className)} {...rest}>
  {@render children?.()}
</div>
