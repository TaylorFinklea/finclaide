import type { RequestEvent, ResolveOptions } from '@sveltejs/kit'
import { describe, expect, it, vi } from 'vitest'

import { handle } from './hooks.server'

type HandleInput = Parameters<typeof handle>[0]

interface RunResult {
  locals: { basePath?: string; [key: string]: unknown }
  transform: (html: string) => string
}

async function runHandle(headers: Record<string, string>): Promise<RunResult> {
  const request = new Request('http://localhost/', { headers })
  const locals: { basePath?: string } = {}
  const event = { request, locals } as unknown as RequestEvent

  let capturedOpts: ResolveOptions | undefined
  const resolve = vi.fn(
    (_event: RequestEvent, opts?: ResolveOptions): Response => {
      capturedOpts = opts
      return new Response('')
    },
  )

  await handle({ event, resolve } as HandleInput)

  const transformPageChunk = capturedOpts?.transformPageChunk
  if (!transformPageChunk) throw new Error('hook did not install transformPageChunk')

  return {
    locals,
    transform: (html) => {
      const result = transformPageChunk({ html, done: true })
      if (typeof result !== 'string') {
        throw new Error('transformPageChunk returned non-string in test')
      }
      return result
    },
  }
}

describe('hooks.server handle', () => {
  it('injects base href and globals when X-Ingress-Path is present', async () => {
    const { locals, transform } = await runHandle({ 'x-ingress-path': '/finclaide' })
    const html = transform('<html><head></head><body></body></html>')

    expect(locals.basePath).toBe('/finclaide')
    expect(html).toContain('<base href="/finclaide/">')
    expect(html).toContain('window.__FINCLAIDE_BASE_PATH__ = "/finclaide"')
    expect(html).toContain('window.__FINCLAIDE_BASE_HREF__ = "/finclaide/"')
  })

  it('falls back to root base href when no ingress headers are set', async () => {
    const { locals, transform } = await runHandle({})
    const html = transform('<html><head></head><body></body></html>')

    expect(locals.basePath).toBe('')
    expect(html).toContain('<base href="/">')
    expect(html).toContain('window.__FINCLAIDE_BASE_PATH__ = ""')
    expect(html).toContain('window.__FINCLAIDE_BASE_HREF__ = "/"')
  })

  it('uses X-Forwarded-Prefix when X-Ingress-Path is absent', async () => {
    const { locals, transform } = await runHandle({ 'x-forwarded-prefix': '/api/hassio_ingress/abc' })
    const html = transform('<html><head></head><body></body></html>')

    expect(locals.basePath).toBe('/api/hassio_ingress/abc')
    expect(html).toContain('<base href="/api/hassio_ingress/abc/">')
  })

  it('prefers X-Ingress-Path over X-Forwarded-Prefix when both are set', async () => {
    const { locals, transform } = await runHandle({
      'x-ingress-path': '/ingress-wins',
      'x-forwarded-prefix': '/forwarded-loses',
    })
    const html = transform('<html><head></head><body></body></html>')

    expect(locals.basePath).toBe('/ingress-wins')
    expect(html).toContain('<base href="/ingress-wins/">')
    expect(html).not.toContain('/forwarded-loses')
  })

  it.each([
    { input: '/', expectedBasePath: '', expectedBaseHref: '/' },
    { input: '/finclaide/', expectedBasePath: '/finclaide', expectedBaseHref: '/finclaide/' },
    { input: 'nested', expectedBasePath: '/nested', expectedBaseHref: '/nested/' },
  ])(
    'normalizes ingress path $input → basePath=$expectedBasePath',
    async ({ input, expectedBasePath, expectedBaseHref }) => {
      const { locals, transform } = await runHandle({ 'x-ingress-path': input })
      const html = transform('<html><head></head><body></body></html>')

      expect(locals.basePath).toBe(expectedBasePath)
      expect(html).toContain(`<base href="${expectedBaseHref}">`)
    },
  )

  it('matches </head>, not %sveltekit.head%, so the placeholder passes through untouched', async () => {
    const { transform } = await runHandle({ 'x-ingress-path': '/finclaide' })
    const chunk = '<html><head>%sveltekit.head%</head><body></body></html>'
    const html = transform(chunk)

    expect(html).toContain('%sveltekit.head%')
    expect(html).toMatch(/<base href="\/finclaide\/">[\s\S]*<\/head>/)
    const injectionIndex = html.indexOf('<base href="/finclaide/">')
    const placeholderIndex = html.indexOf('%sveltekit.head%')
    const closeHeadIndex = html.indexOf('</head>')
    expect(injectionIndex).toBeGreaterThan(placeholderIndex)
    expect(injectionIndex).toBeLessThan(closeHeadIndex)
  })
})
