<script lang="ts">
  type Props = {
    values: number[]
    width?: number
    height?: number
    title?: string
  }

  let { values, width = 56, height = 16, title }: Props = $props()

  // Per-row normalization: each row's max becomes the top of its own
  // height. The `, 1` floor avoids divide-by-zero when every value is 0.
  let max = $derived(Math.max(...values, 1))

  let points = $derived(
    values
      .map((v, i) => {
        const x = values.length === 1 ? 0 : (i / (values.length - 1)) * width
        const y = height - (v / max) * height
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' '),
  )
</script>

<svg
  role="img"
  aria-label={title ?? 'Trend over the last 6 months'}
  {width}
  {height}
  viewBox="0 0 {width} {height}"
  class="text-muted-foreground"
>
  <polyline fill="none" stroke="currentColor" stroke-width="1.25" points={points} />
</svg>
