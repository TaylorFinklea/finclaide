import type { Handle } from '@sveltejs/kit'

function normalizeBasePath(value: string | undefined | null): string {
  if (!value || value === '/') return ''
  const trimmed = value.endsWith('/') ? value.slice(0, -1) : value
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`
}

export const handle: Handle = async ({ event, resolve }) => {
  const ingressPath = event.request.headers.get('x-ingress-path') ?? undefined
  const forwardedPrefix = event.request.headers.get('x-forwarded-prefix') ?? undefined
  const basePath = normalizeBasePath(ingressPath || forwardedPrefix)
  event.locals.basePath = basePath

  const baseHref = basePath ? `${basePath}/` : '/'
  const encodedBasePath = JSON.stringify(basePath)
  const encodedBaseHref = JSON.stringify(baseHref)
  const injection =
    `<script>window.__FINCLAIDE_BASE_PATH__ = ${encodedBasePath};` +
    `window.__FINCLAIDE_BASE_HREF__ = ${encodedBaseHref};</script>` +
    `<base href="${baseHref}">`

  return resolve(event, {
    transformPageChunk: ({ html }) => html.replace('%sveltekit.head%', `${injection}\n%sveltekit.head%`),
  })
}
