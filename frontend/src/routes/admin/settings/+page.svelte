<script lang="ts">
  /*
   * Settings shell — the legacy theme picker has been removed. This page will
   * move to /admin/settings during the IA reorg and gain account / data
   * controls. Left as a stub so the route still resolves until then.
   */
</script>

<svelte:head>
  <title>Settings · Finclaide</title>
</svelte:head>

<div class="mx-auto max-w-2xl space-y-3 py-12">
  <h1 class="text-2xl font-semibold tracking-tight">Settings</h1>
  <p class="text-sm text-muted-foreground">
    The Quartz redesign collapsed twelve color themes into one and removed the
    theme picker. Account, data, and integration controls are moving to
    <code class="rounded bg-secondary px-1.5 py-0.5">/admin/settings</code>.
  </p>
</div>
