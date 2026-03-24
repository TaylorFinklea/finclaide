import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const STATUS_STYLES: Record<string, string> = {
  success: 'border-emerald-400/30 bg-emerald-400/15 text-emerald-200',
  failed: 'border-rose-400/30 bg-rose-400/15 text-rose-100',
  skipped: 'border-amber-400/30 bg-amber-400/15 text-amber-100',
  fresh: 'border-emerald-400/30 bg-emerald-400/15 text-emerald-200',
  healthy: 'border-emerald-400/30 bg-emerald-400/15 text-emerald-200',
  missing: 'border-slate-300/20 bg-slate-300/10 text-slate-100',
  funded: 'border-emerald-400/30 bg-emerald-400/15 text-emerald-200',
  ahead: 'border-cyan-400/30 bg-cyan-400/15 text-cyan-100',
  behind: 'border-amber-400/30 bg-amber-400/15 text-amber-100',
  over: 'border-rose-400/30 bg-rose-400/15 text-rose-100',
  under: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100',
  on_target: 'border-slate-300/20 bg-slate-300/10 text-slate-100',
  warning: 'border-amber-400/30 bg-amber-400/15 text-amber-100',
  critical: 'border-rose-400/30 bg-rose-400/15 text-rose-100',
  info: 'border-cyan-400/30 bg-cyan-400/15 text-cyan-100',
  underplanned: 'border-amber-400/30 bg-amber-400/15 text-amber-100',
  unplanned: 'border-rose-400/30 bg-rose-400/15 text-rose-100',
}

export function StatusChip({ status }: { status: string }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        'rounded-full px-2 py-0.5 text-[11px] font-medium capitalize tracking-wide',
        STATUS_STYLES[status] ?? 'border-border bg-muted text-muted-foreground',
      )}
    >
      {status.replace('_', ' ')}
    </Badge>
  )
}
