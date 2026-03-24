declare global {
  interface Window {
    __FINCLAIDE_BASE_PATH__?: string
  }
}

function normalizeBasePath(value: string | undefined): string {
  if (!value || value === '/') {
    return ''
  }
  return value.endsWith('/') ? value.slice(0, -1) : value
}

export function getBasePath(): string {
  if (typeof window === 'undefined') {
    return ''
  }
  return normalizeBasePath(window.__FINCLAIDE_BASE_PATH__)
}

export function withBasePath(path: string): string {
  const basePath = getBasePath()
  if (!basePath) {
    return path
  }
  if (path.startsWith('/')) {
    return `${basePath}${path}`
  }
  return `${basePath}/${path}`
}
