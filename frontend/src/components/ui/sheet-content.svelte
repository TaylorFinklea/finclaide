<script lang="ts" module>
  import { cva, type VariantProps } from 'class-variance-authority'

  export const sheetVariants = cva(
    'fixed z-50 gap-4 bg-card p-6 shadow-lg transition ease-in-out data-[state=closed]:duration-300 data-[state=open]:duration-500 data-[state=open]:animate-in data-[state=closed]:animate-out',
    {
      variants: {
        side: {
          top: 'inset-x-0 top-0 border-b data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top',
          bottom:
            'inset-x-0 bottom-0 border-t data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom',
          left: 'inset-y-0 left-0 h-full w-3/4 border-r data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left sm:max-w-sm',
          right:
            'inset-y-0 right-0 h-full w-3/4 border-l data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right sm:max-w-sm',
        },
      },
      defaultVariants: {
        side: 'right',
      },
    },
  )

  export type SheetVariants = VariantProps<typeof sheetVariants>
</script>

<script lang="ts">
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { X } from 'lucide-svelte'
  import type { Snippet } from 'svelte'

  import { cn } from '$lib/utils'

  type Props = DialogPrimitive.ContentProps & {
    class?: string
    side?: SheetVariants['side']
    children?: Snippet
  }

  let { class: className, side = 'right', children, ...rest }: Props = $props()
</script>

<DialogPrimitive.Portal>
  <DialogPrimitive.Overlay
    class="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
  />
  <DialogPrimitive.Content class={cn(sheetVariants({ side }), className)} {...rest}>
    {@render children?.()}
    <DialogPrimitive.Close
      class="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none"
    >
      <X class="h-4 w-4" />
      <span class="sr-only">Close</span>
    </DialogPrimitive.Close>
  </DialogPrimitive.Content>
</DialogPrimitive.Portal>
