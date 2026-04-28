import { render } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'

import Sparkline from './sparkline.svelte'

describe('Sparkline', () => {
  it('renders a polyline whose point count equals values length', () => {
    const { container } = render(Sparkline as never, {
      props: { values: [10, 20, 30, 40, 50, 60] } as never,
    })
    const polyline = container.querySelector('polyline')
    expect(polyline).not.toBeNull()
    const pointsAttr = polyline?.getAttribute('points') ?? ''
    const segments = pointsAttr.trim().split(/\s+/)
    expect(segments).toHaveLength(6)
  })

  it('normalizes per-row: equal values render at constant y', () => {
    const { container } = render(Sparkline as never, {
      props: { values: [50, 50, 50, 50, 50, 50] } as never,
    })
    const points = container.querySelector('polyline')?.getAttribute('points') ?? ''
    const ys = points
      .trim()
      .split(/\s+/)
      .map((p) => Number(p.split(',')[1]))
    const allSame = ys.every((y) => y === ys[0])
    expect(allSame).toBe(true)
  })

  it('handles all-zero values without producing NaN coordinates', () => {
    const { container } = render(Sparkline as never, {
      props: { values: [0, 0, 0, 0, 0, 0] } as never,
    })
    const points = container.querySelector('polyline')?.getAttribute('points') ?? ''
    expect(points).not.toMatch(/NaN/)
    expect(points.trim().length).toBeGreaterThan(0)
  })
})
