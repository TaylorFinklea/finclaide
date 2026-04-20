<script lang="ts">
  import { Toaster as Sonner } from 'svelte-sonner'

  let { ...rest }: { theme?: 'light' | 'dark' | 'system'; richColors?: boolean } = $props()
</script>

<Sonner theme={rest.theme ?? 'dark'} richColors={rest.richColors ?? true} {...rest} />
