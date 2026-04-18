import { StatusChip } from '@/components/status-chip'

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

export function FreshnessChip({ label, freshness }: { label: string; freshness: FreshnessLike }) {
  const status = FRESHNESS_LABEL[freshness.status] ?? freshness.status
  const detail =
    typeof freshness.hours_stale === 'number'
      ? `${freshness.hours_stale.toFixed(1)}h`
      : freshness.last_updated_at
        ? 'unknown'
        : 'never'

  return (
    <div
      className="flex items-center gap-2"
      aria-label={`${label} freshness: ${status}, ${detail}`}
    >
      <span className="text-label">{label}</span>
      <StatusChip status={freshness.status} />
      <span className="font-mono text-xs text-muted-foreground">{detail}</span>
    </div>
  )
}
