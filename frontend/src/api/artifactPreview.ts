import apiClient from './client'
import { TABLE_CONFIRM_BYTES } from '@/utils/artifactTablePreview'

export class TablePreviewSizeError extends Error {
  constructor(public readonly size: number, public readonly exact = true) {
    super('Table preview requires confirmation')
  }
}

/** Preview-only streaming transport. The existing download transport stays separate. */
export async function fetchTablePreviewBlob(
  url: string,
  confirmed: boolean,
  params?: Record<string, string>,
): Promise<Blob> {
  const response = await apiClient.get<ReadableStream<Uint8Array>>(url, {
    ...(params ? { params } : {}),
    adapter: 'fetch',
    responseType: 'stream',
  })
  const length = Number(response.headers['content-length'])
  const reader = response.data.getReader()
  const chunks: BlobPart[] = []
  let received = 0
  try {
    // Inspect response headers before buffering the body, even without manifest metadata.
    if (!confirmed && length > TABLE_CONFIRM_BYTES) {
      await reader.cancel()
      throw new TablePreviewSizeError(length)
    }
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      received += value.byteLength
      if (!confirmed && received > TABLE_CONFIRM_BYTES) {
        await reader.cancel()
        throw new TablePreviewSizeError(received, false)
      }
      chunks.push(value.slice().buffer)
    }
  } finally {
    reader.releaseLock()
  }
  return new Blob(chunks, { type: String(response.headers['content-type'] || '') })
}
