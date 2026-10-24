// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { AgentTemplate } from '@/types/agent'
import { useAgentHubStore } from '@/stores/agentHub'

/**
 * 消息排队（流式期间可继续输入，回复完成后自动发送）回归：
 * - 流式期间 sendOrQueue 进入队列而不是被丢弃（旧行为：handleSend 静默 return）
 * - 当前回复结束（done）后自动发送队列消息，请求体内容正确
 * - 队列条目可撤销；撤销后回复结束不再发起请求
 */

const ENCODER = new TextEncoder()

function stubStreams() {
  const streams: Array<{
    controller: ReadableStreamDefaultController<Uint8Array>
    request: RequestInit
  }> = []
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, request: RequestInit) => {
      let controller!: ReadableStreamDefaultController<Uint8Array>
      const stream = new ReadableStream<Uint8Array>({
        start(value) {
          controller = value
        },
      })
      streams.push({ controller, request })
      return Promise.resolve(new Response(stream, { status: 200 }))
    }),
  )
  return streams
}

function finishStream(
  stream: { controller: ReadableStreamDefaultController<Uint8Array> },
): void {
  stream.controller.enqueue(ENCODER.encode('data: {"type":"done","usage":{}}\n\n'))
  stream.controller.close()
}

function lastMessageContent(stream: { request: RequestInit }): string {
  const payload = JSON.parse(String(stream.request.body)) as {
    messages: { role: string; content: string }[]
  }
  const last = payload.messages[payload.messages.length - 1]
  return last.content
}

describe('消息排队（流式期间提交，回复完成后自动发送）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function setupStore() {
    const store = useAgentHubStore()
    store.agents = [
      { id: 'agent-chat', agent_id: 'agent-chat', name: '星尘 AI', is_active: true },
    ] as unknown as AgentTemplate[]
    store.startSessionFromAgent('agent-chat')
    return store
  }

  it('流式期间排队，回复结束后自动发送队列消息', async () => {
    const streams = stubStreams()
    const store = setupStore()

    const first = store.sendMessage('第一条')
    await vi.waitFor(() => expect(streams).toHaveLength(1))
    await vi.waitFor(() => expect(store.isStreaming).toBe(true))

    // 旧行为在这里被丢弃；现在应进入队列
    const outcome = await store.sendOrQueue('排队消息')
    expect(outcome).toBe('queued')
    expect(store.queuedMessages).toHaveLength(1)
    expect(store.currentQueuedSends.map((item) => item.content)).toEqual(['排队消息'])

    finishStream(streams[0])
    await first

    // 队列自动冲刷：第二条请求发起且内容正确
    await vi.waitFor(() => expect(streams).toHaveLength(2))
    expect(lastMessageContent(streams[1])).toBe('排队消息')
    await vi.waitFor(() => expect(store.isStreaming).toBe(true))

    finishStream(streams[1])
    await vi.waitFor(() => expect(store.isStreaming).toBe(false))
    await vi.waitFor(() => expect(store.queuedMessages).toHaveLength(0))
  })

  it('排队消息可撤销，撤销后不再发送', async () => {
    const streams = stubStreams()
    const store = setupStore()

    const first = store.sendMessage('第一条')
    await vi.waitFor(() => expect(streams).toHaveLength(1))
    await vi.waitFor(() => expect(store.isStreaming).toBe(true))

    expect(await store.sendOrQueue('会撤销的消息')).toBe('queued')
    store.removeQueuedMessage(store.queuedMessages[0]!.id)
    expect(store.queuedMessages).toHaveLength(0)

    finishStream(streams[0])
    await first
    await vi.waitFor(() => expect(store.isStreaming).toBe(false))

    // 给可能的错误冲刷留一个微任务窗口
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(streams).toHaveLength(1)
  })

  it('多条排队消息按顺序依次发送', async () => {
    const streams = stubStreams()
    const store = setupStore()

    const first = store.sendMessage('第一条')
    await vi.waitFor(() => expect(streams).toHaveLength(1))
    await vi.waitFor(() => expect(store.isStreaming).toBe(true))

    expect(await store.sendOrQueue('排队A')).toBe('queued')
    expect(await store.sendOrQueue('排队B')).toBe('queued')

    finishStream(streams[0])
    await first
    await vi.waitFor(() => expect(streams).toHaveLength(2))
    expect(lastMessageContent(streams[1])).toBe('排队A')

    finishStream(streams[1])
    await vi.waitFor(() => expect(streams).toHaveLength(3))
    expect(lastMessageContent(streams[2])).toBe('排队B')

    finishStream(streams[2])
    await vi.waitFor(() => expect(store.queuedMessages).toHaveLength(0))
  })
})
