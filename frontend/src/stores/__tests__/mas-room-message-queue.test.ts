// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useMasRoomStore } from '@/stores/masRoom'

/**
 * 协作室消息排队回归：MAS run 执行期间（runActive）提交的消息进入队列，
 * run 结束（runActive 回落）后自动按序发送；可撤销；空闲时直发。
 */

const ROOM = 'bioinfo-dept'

function stubMessagePost() {
  const posts: Array<{ body: { content: string } }> = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: unknown, init?: RequestInit) => {
      if (String(url).endsWith(`/mas/rooms/${ROOM}/messages`) && init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as { content: string }
        posts.push({ body })
        const item = {
          id: `m_${posts.length}`,
          room_id: ROOM,
          run_id: null,
          agent_id: null,
          role: 'user',
          content: body.content,
          metadata: {},
          created_at: null,
        }
        return Promise.resolve(new Response(JSON.stringify(item), { status: 200 }))
      }
      return Promise.resolve(new Response('{}', { status: 200 }))
    }),
  )
  return posts
}

describe('masRoom 消息排队', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('MAS run 执行期间排队，run 结束后自动发送', async () => {
    const posts = stubMessagePost()
    const store = useMasRoomStore()

    store.runActive = true
    expect(await store.sendOrQueue(ROOM, '排队消息')).toBe('queued')
    expect(store.queuedMessages).toHaveLength(1)
    expect(posts).toHaveLength(0)

    // run 结束（done/error 事件把 runActive 置回 false）→ 自动冲刷
    store.runActive = false
    await vi.waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]!.body.content).toBe('排队消息')
    await vi.waitFor(() => expect(store.queuedMessages).toHaveLength(0))
  })

  it('排队消息可撤销，撤销后不再发送', async () => {
    const posts = stubMessagePost()
    const store = useMasRoomStore()

    store.runActive = true
    expect(await store.sendOrQueue(ROOM, '会撤销的消息')).toBe('queued')
    store.removeQueuedMessage(store.queuedMessages[0]!.id)
    expect(store.queuedMessages).toHaveLength(0)

    store.runActive = false
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(posts).toHaveLength(0)
  })

  it('clearQueuedMessages 清空指定房间队列（停止排队入口）', async () => {
    const posts = stubMessagePost()
    const store = useMasRoomStore()

    store.runActive = true
    await store.sendOrQueue(ROOM, 'A')
    await store.sendOrQueue(ROOM, 'B')
    store.clearQueuedMessages(ROOM)

    store.runActive = false
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(posts).toHaveLength(0)
    expect(store.currentQueuedSends).toHaveLength(0)
  })

  it('空闲时直发（不排队）', async () => {
    const posts = stubMessagePost()
    const store = useMasRoomStore()

    expect(await store.sendOrQueue(ROOM, '直发消息')).toBe('sent')
    await vi.waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]!.body.content).toBe('直发消息')
  })
})
