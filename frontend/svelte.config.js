import adapter from '@sveltejs/adapter-node'
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte'

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
    alias: {
      '$components': 'src/components',
      '$lib': 'src/lib',
    },
  },
  // Note: runes mode is auto-detected per file. We intentionally do not set
  // `compilerOptions.runes: true` here because that forces every .svelte file
  // (including those in node_modules, e.g. @tanstack/svelte-query's
  // HydrationBoundary) to use runes syntax. Our own files use $state/$props
  // and Svelte detects them as runes mode automatically.
}

export default config
