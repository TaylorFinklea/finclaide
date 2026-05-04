<script lang="ts">
  import { goto } from '$app/navigation'
  import { createMutation, useQueryClient } from '@tanstack/svelte-query'
  import { ArrowRight, LoaderCircle, Lightbulb, Telescope, Wand2 } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'

  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    getActivePlan,
    getErrorMessage,
    updatePlanCategory,
    type CashflowRecommendation,
    type CashflowRecommendations,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'
  import { withBasePath } from '$lib/runtime'

  type Props = {
    recommendations?: CashflowRecommendations
    isLoading?: boolean
    isError?: boolean
  }

  let { recommendations, isLoading = false, isError = false }: Props = $props()

  const queryClient = useQueryClient()

  function shortMonth(month: string | null): string {
    if (!month) return '—'
    const [y, m] = month.split('-')
    const names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return `${names[Number(m)]} ${y.slice(2)}`
  }

  const applyMutation = createMutation({
    mutationFn: async (rec: CashflowRecommendation) => {
      const plan = await getActivePlan()
      return updatePlanCategory(rec.category.id, {
        plan_id: plan.plan.id,
        planned_milliunits: rec.suggested_planned_milliunits,
      })
    },
    onSuccess: async (_data, rec) => {
      toast.success(
        `Updated ${rec.category.group_name} / ${rec.category.category_name} to ${formatMoney(rec.suggested_planned_milliunits)}/mo.`,
      )
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['analytics-cashflow-12'] }),
        queryClient.invalidateQueries({ queryKey: ['analytics-cashflow-recommendations'] }),
        queryClient.invalidateQueries({ queryKey: ['plan-active'] }),
        queryClient.invalidateQueries({ queryKey: ['plan'] }),
        queryClient.invalidateQueries({ queryKey: ['summary'] }),
      ])
    },
    onError: (e) => toast.error(`Apply failed: ${getErrorMessage(e)}`),
  })

  function projectRecommendation(rec: CashflowRecommendation) {
    // Encode the recommendation as a percent_delta axis. Pure
    // calibration suggests raising plan from `current` → `suggested`,
    // so the delta_pct is (suggested / current - 1) × 100. Plan = 0
    // edge case: if current is 0, we can't compute a percent; fall
    // back to navigating with no axes (operator can adjust manually).
    if (rec.current_planned_milliunits === 0) {
      goto(withBasePath('/scenarios'))
      return
    }
    const deltaPct = Math.round(
      (rec.suggested_planned_milliunits / rec.current_planned_milliunits - 1) * 100,
    )
    const axes = `${rec.category.id}:${deltaPct}`
    goto(withBasePath(`/scenarios?axes=${axes}`))
  }
</script>

<Card class="border-border/40 bg-card">
  <CardHeader>
    <CardTitle>
      <span class="inline-flex items-center gap-2">
        <Lightbulb class="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        Plan calibration suggestions
      </span>
    </CardTitle>
    <p class="text-sm text-muted-foreground">
      Discretionary categories where the 6-month run-rate has consistently exceeded
      the plan. Apply a suggestion to raise the plan to match reality, or project the
      change in a sandbox first.
    </p>
  </CardHeader>
  <CardContent class="space-y-3">
    {#if isLoading}
      <Skeleton class="h-32 rounded" />
    {:else if isError}
      <p class="text-sm text-rose-300">Could not load recommendations.</p>
    {:else if !recommendations || recommendations.recommendations.length === 0}
      <p class="text-sm text-muted-foreground">
        No plan calibrations needed — your discretionary categories are tracking
        their plans within tolerance.
      </p>
    {:else}
      <ul class="space-y-3">
        {#each recommendations.recommendations as rec (rec.category.id)}
          <li class="rounded-md bg-muted/15 p-3">
            <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div class="min-w-0 space-y-1">
                <div class="font-medium text-foreground">{rec.headline}</div>
                <div class="text-xs text-muted-foreground">{rec.rationale}</div>
                <div class="flex items-center gap-2 text-[11px] font-mono text-muted-foreground">
                  <span>{formatMoney(rec.current_planned_milliunits)}/mo</span>
                  <ArrowRight class="h-3 w-3" aria-hidden="true" />
                  <span class="text-foreground">{formatMoney(rec.suggested_planned_milliunits)}/mo</span>
                  <span class="text-muted-foreground/60">·</span>
                  <span>+{formatMoney(rec.annual_impact_milliunits)}/yr</span>
                </div>
                {#if rec.projected_impact.first_negative_month_before !== rec.projected_impact.first_negative_month_after}
                  <div class="text-[11px] text-rose-300">
                    First negative: {shortMonth(rec.projected_impact.first_negative_month_before)}
                    <ArrowRight class="inline h-3 w-3" aria-hidden="true" />
                    {shortMonth(rec.projected_impact.first_negative_month_after)}
                  </div>
                {/if}
              </div>
              <div class="flex shrink-0 gap-2">
                <Button
                  variant="outline"
                  class="border-border/60"
                  disabled={$applyMutation.isPending}
                  onclick={() => projectRecommendation(rec)}
                >
                  <Telescope class="h-3.5 w-3.5" aria-hidden="true" />
                  Project
                </Button>
                <Button
                  variant="outline"
                  class="border-amber-200/30 text-amber-50 hover:bg-amber-500/10"
                  disabled={$applyMutation.isPending}
                  onclick={() => $applyMutation.mutate(rec)}
                >
                  {#if $applyMutation.isPending}
                    <LoaderCircle class="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  {:else}
                    <Wand2 class="h-3.5 w-3.5" aria-hidden="true" />
                  {/if}
                  Apply
                </Button>
              </div>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </CardContent>
</Card>
