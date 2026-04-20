<script lang="ts">
  import StatusChip from '$components/status-chip.svelte'

  type FreshnessLike = {
    status: string
    hours_stale: number | null
    last_updated_at: string | null
  }

  const FRESHNESS_LABEL: Record<string, string> = {
    fresh: 'fresh',
    warning: 'stale',
    critical: 'critical',
    missing: 'missing',
  }

  type Props = { label: string; freshness: FreshnessLike }
  let { label, freshness }: Props = $props()

  let normalizedStatus = $derived(FRESHNESS_LABEL[freshness.status] ?? freshness.status)
  let detailText = $derived(
    typeof freshness.hours_stale === 'number'
      ? `${freshness.hours_stale.toFixed(1)}h`
      : freshness.last_updated_at
        ? 'unknown'
        : 'never',
  )
</script>

<div class="flex items-center gap-2" aria-label={`${label} freshness: ${normalizedStatus}, ${detailText}`}>
  <span class="text-label">{label}</span>
  <StatusChip status={freshness.status} />
  <span class="font-mono text-xs text-muted-foreground">{detailText}</span>
</div>
