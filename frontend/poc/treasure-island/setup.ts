import { beforeEach, vi } from 'vitest'

// jsdom lacks the browser media-query API used by the shared touch/pet hooks.
beforeEach(() => vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
  matches: false, media: query, onchange: null,
  addEventListener: vi.fn(), removeEventListener: vi.fn(),
  addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn(),
}))))
