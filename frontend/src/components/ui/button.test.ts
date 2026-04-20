import { render, screen } from '@testing-library/svelte'
import { createRawSnippet } from 'svelte'
import { describe, expect, it } from 'vitest'

import Button from './button.svelte'

function textSnippet(text: string) {
  return createRawSnippet(() => ({
    render: () => `<span>${text}</span>`,
  }))
}

describe('Button', () => {
  it('renders a <button> with default type when no href is provided', () => {
    render(Button, { props: { children: textSnippet('Click me') } })
    const btn = screen.getByRole('button', { name: 'Click me' })
    expect(btn.tagName).toBe('BUTTON')
    expect(btn).toHaveAttribute('type', 'button')
  })

  it('renders an <a> when href is provided', () => {
    render(Button, { props: { href: '/foo', children: textSnippet('Go') } })
    const link = screen.getByRole('link', { name: 'Go' })
    expect(link).toHaveAttribute('href', '/foo')
  })
})
