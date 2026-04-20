<script lang="ts">
  import { CalendarClock, PauseCircle } from 'lucide-svelte'

  import StatusChip from '$components/status-chip.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import type { StatusResponse } from '$lib/api'
  import { formatRunAt } from '$lib/format'

  type Props = { status: StatusResponse | undefined }
  let { status }: Props = $props()

  function describeLastStatus(lastStatus: string): string {
    switch (lastStatus) {
      case 'success':
        return 'Succeeded'
      case 'failed':
        return 'Failed'
      case 'skipped':
        return 'Skipped (operation already running)'
      case 'unknown':
        return 'No run history yet'
      default:
        return lastStatus
    }
  }

  function formatRelativeMinutes(isoTimestamp: string): string {
    const target = new Date(isoTimestamp).getTime()
    const now = Date.now()
    const diffMinutes = Math.round((target - now) / 60_000)
    if (diffMinutes < 0) return `${Math.abs(diffMinutes)} min overdue`
    if (diffMinutes < 1) return 'less than a minute'
    if (diffMinutes < 60) return `${diffMinutes} min`
    const hours = Math.round(diffMinutes / 60)
    return `${hours}h`
  }

  function headerTone(lastStatus: string): string {
    if (lastStatus === 'failed') return 'border-rose-500/30'
    if (lastStatus === 'skipped') return 'border-amber-500/30'
    if (lastStatus === 'success') return 'border-emerald-500/30'
    return 'border-border/40'
  }
</script>

{#if status}
  {@const schedule = status.scheduled_refresh}
  {#if !schedule.enabled}
    <Card class="border-border/40 bg-card">
      <CardHeader>
        <CardTitle class="flex items-center gap-2">
          <PauseCircle class="h-4 w-4 text-muted-foreground" />
          Scheduled refresh — disabled
        </CardTitle>
        <p class="mt-2 text-sm text-muted-foreground">
          Set <code class="font-mono text-xs">FINCLAIDE_SCHEDULED_REFRESH_ENABLED=true</code> to run import,
          sync, and reconcile automatically.
        </p>
      </CardHeader>
    </Card>
  {:else}
    {@const lastStatus = schedule.last_status ?? 'unknown'}
    <Card class={`border bg-card ${headerTone(lastStatus)}`}>
      <CardHeader>
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle class="flex items-center gap-2">
              <CalendarClock class="h-4 w-4 text-muted-foreground" />
              Scheduled refresh
            </CardTitle>
            <p class="mt-2 text-sm text-muted-foreground">
              Runs every {schedule.interval_minutes ?? '—'} minutes. Last status drives the chip below.
            </p>
          </div>
          <StatusChip status={lastStatus} />
        </div>
      </CardHeader>
      <CardContent class="grid gap-3 md:grid-cols-3">
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Next run</div>
          <div class="mt-2 text-foreground">{formatRunAt(schedule.next_run_at)}</div>
          <div class="mt-1 text-sm text-muted-foreground">
            {schedule.next_run_at ? `In ${formatRelativeMinutes(schedule.next_run_at)}` : 'No run scheduled'}
          </div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Last finished</div>
          <div class="mt-2 text-foreground">{formatRunAt(schedule.last_finished_at)}</div>
          <div class="mt-1 text-sm text-muted-foreground">
            {schedule.last_started_at ? `Started ${formatRunAt(schedule.last_started_at)}` : 'Never run yet'}
          </div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Last status</div>
          <div class="mt-2 text-foreground">{describeLastStatus(lastStatus)}</div>
          <div class="mt-1 text-sm text-muted-foreground">{schedule.last_error ?? 'No error reported'}</div>
        </div>
      </CardContent>
    </Card>
  {/if}
{/if}
