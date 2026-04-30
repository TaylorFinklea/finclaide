<script lang="ts">
  import { Slider } from 'bits-ui'

  import { cn } from '$lib/utils'

  type Props = {
    value: number
    min: number
    max: number
    step: number
    onValueChange: (v: number) => void
    class?: string
    disabled?: boolean
  }

  let {
    value,
    min,
    max,
    step,
    onValueChange,
    class: className,
    disabled = false,
  }: Props = $props()
</script>

<Slider.Root
  type="single"
  {value}
  {min}
  {max}
  {step}
  {disabled}
  {onValueChange}
  class={cn('relative flex w-full touch-none select-none items-center', className)}
>
  {#snippet children({ thumbs })}
    <span class="relative h-1.5 w-full grow overflow-hidden rounded-full bg-muted">
      <Slider.Range class="absolute h-full bg-primary" />
    </span>
    {#each thumbs as thumb (thumb)}
      <Slider.Thumb
        index={thumb}
        class="block h-4 w-4 cursor-pointer rounded-full border border-border bg-background shadow transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
      />
    {/each}
  {/snippet}
</Slider.Root>
