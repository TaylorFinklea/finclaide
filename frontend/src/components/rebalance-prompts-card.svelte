<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query'
  import { ArrowDown, ArrowUp, LoaderCircle, Scale, X } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'

  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    getErrorMessage,
    updatePlanCategory,
    type RebalancePrompt,
    type RebalancePrompts,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'

  type Props = {
    prompts?: RebalancePrompts
    planId: number
    isLoading?: boolean
    isError?: boolean
  }

  let { prompts, planId, isLoading = false, isError = false }: Props = $props()

  // Local dismissals — recomputed on next reload, so this is just "stop
  // showing me this until the underlying state changes". Keyed by a
  // stable signature of the prompt's two sides.
  let dismissed: Record<string, true> = $state({})

  function promptKey(p: RebalancePrompt): string {
    const inc = p.increase ? p.increase.category_id : 'none'
    const dec = p.decrease ? p.decrease.category_id : 'none'
    return `${p.kind}:${inc}:${dec}:${p.delta_milli}`
  }

  let visiblePrompts = $derived(
    (prompts?.prompts ?? []).filter((p) => !dismissed[promptKey(p)]),
  )

  const queryClient = useQueryClient()

  const applyMutation = createMutation({
    mutationFn: async (prompt: RebalancePrompt) => {
      // Sequential PATCHes — server serializes plan writes, and a single
      // logical batch is fine for the small fan-out here. Order doesn't
      // matter for cascade correctness; the recompute is idempotent.
      if (prompt.increase) {
        await updatePlanCategory(prompt.increase.category_id, {
          plan_id: planId,
          planned_milliunits: prompt.increase.suggested_milli,
        })
      }
      if (prompt.decrease) {
        await updatePlanCategory(prompt.decrease.category_id, {
          plan_id: planId,
          planned_milliunits: prompt.decrease.suggested_milli,
        })
      }
    },
    onSuccess: async () => {
      toast.success('Rebalanced.')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['plan'] }),
        queryClient.invalidateQueries({ queryKey: ['summary'] }),
        queryClient.invalidateQueries({ queryKey: ['analytics-cashflow-12'] }),
        queryClient.invalidateQueries({
          queryKey: ['analytics-cashflow-recommendations'],
        }),
        queryClient.invalidateQueries({
          queryKey: ['analytics-cashflow-rebalance'],
        }),
      ])
    },
    onError: (e) => toast.error(`Apply failed: ${getErrorMessage(e)}`),
  })
</script>

{#if isLoading}
  <Card class="border-border/40 bg-card">
    <CardContent class="py-3">
      <Skeleton class="h-20 rounded" />
    </CardContent>
  </Card>
{:else if isError}
  <Card class="border-border/40 bg-card">
    <CardContent class="py-3 text-sm text-rose-300">
      Could not load rebalance suggestions.
    </CardContent>
  </Card>
{:else if visiblePrompts.length > 0}
  <Card class="border-amber-500/30 bg-amber-500/[0.05]">
    <CardHeader class="space-y-1">
      <CardTitle class="text-base">
        <span class="inline-flex items-center gap-2 text-amber-100">
          <Scale class="h-4 w-4" aria-hidden="true" />
          Rebalance suggestions
        </span>
      </CardTitle>
      <p class="text-xs text-amber-100/80">
        Each suggestion pairs an increase with a compensating decrease so the cascade stays
        balanced. Apply for one click, or dismiss to handle manually.
      </p>
    </CardHeader>
    <CardContent class="space-y-3">
      {#each visiblePrompts as prompt (promptKey(prompt))}
        <div class="rounded-md border border-border/40 bg-card/60 p-3">
          <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div class="min-w-0 space-y-2">
              {#if prompt.increase}
                <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                  <span class="inline-flex items-center gap-1 text-rose-200">
                    <ArrowUp class="h-3.5 w-3.5" aria-hidden="true" />
                    <span class="font-medium">
                      {prompt.increase.group_name} / {prompt.increase.category_name}
                    </span>
                  </span>
                  <span class="font-mono text-xs text-muted-foreground">
                    {formatMoney(prompt.increase.current_milli)} →
                    <span class="text-foreground">
                      {formatMoney(prompt.increase.suggested_milli)}
                    </span>
                    ({prompt.increase.delta_milli > 0 ? '+' : ''}{formatMoney(
                      prompt.increase.delta_milli,
                    )}/mo)
                  </span>
                </div>
              {/if}
              {#if prompt.decrease}
                <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                  <span class="inline-flex items-center gap-1 text-emerald-200">
                    <ArrowDown class="h-3.5 w-3.5" aria-hidden="true" />
                    <span class="font-medium">
                      {prompt.decrease.group_name} / {prompt.decrease.category_name}
                    </span>
                  </span>
                  <span class="font-mono text-xs text-muted-foreground">
                    {formatMoney(prompt.decrease.current_milli)} →
                    <span class="text-foreground">
                      {formatMoney(prompt.decrease.suggested_milli)}
                    </span>
                    ({formatMoney(prompt.decrease.delta_milli)}/mo)
                  </span>
                </div>
              {/if}
              <p class="text-xs text-muted-foreground">{prompt.rationale}</p>
              {#if prompt.cushion_status === 'none_available'}
                <p class="text-xs text-rose-300">
                  No automatic cushion — drain a savings row manually or trim a
                  discretionary category.
                </p>
              {:else if prompt.decrease && !prompt.decrease.covers_full_delta}
                <p class="text-xs text-amber-200/90">
                  Partial coverage — applies what this cushion can absorb; close the
                  remaining gap manually.
                </p>
              {/if}
            </div>
            <div class="flex shrink-0 gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={$applyMutation.isPending}
                onclick={() => (dismissed = { ...dismissed, [promptKey(prompt)]: true })}
                aria-label="Dismiss"
              >
                <X class="h-3.5 w-3.5" aria-hidden="true" />
                Dismiss
              </Button>
              <Button
                size="sm"
                disabled={$applyMutation.isPending ||
                  prompt.cushion_status === 'none_available'}
                onclick={() => $applyMutation.mutate(prompt)}
              >
                {#if $applyMutation.isPending}
                  <LoaderCircle class="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                {:else}
                  <Scale class="h-3.5 w-3.5" aria-hidden="true" />
                {/if}
                Apply rebalance
              </Button>
            </div>
          </div>
        </div>
      {/each}
    </CardContent>
  </Card>
{/if}
