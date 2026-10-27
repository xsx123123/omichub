import { describe, expect, it, vi } from 'vitest'
import { fetchTablePreviewBlob, TablePreviewSizeError } from '@/api/artifactPreview'
import { TABLE_CONFIRM_BYTES } from '@/utils/artifactTablePreview'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/client', () => ({ default: { get } }))

function response(length?: number, chunks = [new Uint8Array([1, 2, 3])]) {
  let index = 0
  const reader = {
    read: vi.fn(async () => index < chunks.length
      ? { value: chunks[index++], done: false }
      : { value: undefined, done: true }),
    cancel: vi.fn(async () => {}),
    releaseLock: vi.fn(),
  }
  get.mockResolvedValue({
    headers: { 'content-length': length, 'content-type': 'text/csv' },
    data: { getReader: () => reader },
  })
  return reader
}

describe('preview-only streaming size guard', () => {
  it('cancels before reading the body when Content-Length exceeds 5 MB', async () => {
    const reader = response(TABLE_CONFIRM_BYTES + 100)
    await expect(fetchTablePreviewBlob('/sample.csv', false)).rejects.toBeInstanceOf(TablePreviewSizeError)
    expect(reader.read).not.toHaveBeenCalled()
    expect(reader.cancel).toHaveBeenCalledOnce()
    expect(reader.releaseLock).toHaveBeenCalledOnce()
  })

  it('also cancels chunked responses that exceed the limit without a length header', async () => {
    const reader = response(undefined, [new Uint8Array(TABLE_CONFIRM_BYTES), new Uint8Array(10)])
    await expect(fetchTablePreviewBlob('/sample.csv', false)).rejects.toBeInstanceOf(TablePreviewSizeError)
    expect(reader.cancel).toHaveBeenCalledOnce()
  })

  it('loads complete data after confirmation through the authenticated API client', async () => {
    const reader = response(TABLE_CONFIRM_BYTES + 100)
    const blob = await fetchTablePreviewBlob('/sample.csv', true, { path: 'sample.csv' })
    expect([...new Uint8Array(await blob.arrayBuffer())]).toEqual([1, 2, 3])
    expect(reader.cancel).not.toHaveBeenCalled()
    expect(get).toHaveBeenLastCalledWith('/sample.csv', {
      adapter: 'fetch', responseType: 'stream', params: { path: 'sample.csv' },
    })
  })
})
