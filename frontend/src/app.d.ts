declare global {
  namespace App {
    interface Locals {
      basePath: string
    }
  }

  interface Window {
    __FINCLAIDE_BASE_PATH__?: string
    __FINCLAIDE_BASE_HREF__?: string
  }
}

export {}
