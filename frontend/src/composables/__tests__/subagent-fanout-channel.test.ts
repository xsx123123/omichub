/**
 * 对话内并行子 Agent fan-out 的 SSE 通道契约测试：
 * 后端 type="subagents" 的 rejected / started / child 逐子事件 / aggregated 相位 → onSubagentFanout 回调。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  useAgentChatStream,
  type AgentChatStreamOptions,
  type SubagentFanoutEvent,
} from '@/composables/useAgentChatStream'

function sseBody(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
}

function sseEvent(type: string, extra: Record<string, unknown> = {}): string {
  return `data: ${JSON.stringify({ type, ...extra })}\n\n`
}

const options: AgentChatStreamOptions = {
  agentId: 'agent-1',
  messages: [{ role: 'user', content: '并行检查 QC 与注释' }],
}

const localStorageStub = {
  getItem: vi.fn(() => ''),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
vi.stubGlobal('localStorage', localStorageStub)

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.stubGlobal('localStorage', localStorageStub)
})

function stubFetch(events: string[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        body: sseBody(events),
        text: () => Promise.resolve(''),
      }),
    ),
  )
}

async function collect(events: string[]): Promise<SubagentFanoutEvent[]> {
  stubFetch(events)
  const received: SubagentFanoutEvent[] = []
  const { streamChat } = useAgentChatStream()
  await streamChat(options, { onSubagentFanout: (event) => received.push(event) })
  return received
}

describe('useAgentChatStream subagents fan-out 通道', () => {
  it('started 相位：任务初态为 queued 并携带显示名', async () => {
    const received = await collect([
      sseEvent('subagents', {
        phase: 'started',
        tool_call_id: 'tc-1',
        tasks: [
          { index: 1, agent_id: 'agent-qc', name: '质控专家', task: '检查 QC 报告' },
          { index: 2, agent_id: 'agent-anno', name: '注释专家', task: '核对注释策略' },
        ],
      }),
      sseEvent('done', { session_id: 's1', message_id: 'm1' }),
    ])

    expect(received).toHaveLength(1)
    expect(received[0]).toMatchObject({ phase: 'started', toolCallId: 'tc-1' })
    expect(received[0].tasks).toEqual([
      { index: 1, agentId: 'agent-qc', name: '质控专家', task: '检查 QC 报告', status: 'queued' },
      { index: 2, agentId: 'agent-anno', name: '注释专家', task: '核对注释策略', status: 'queued' },
    ])
  })

  it('child_* 相位：逐子事件带状态/耗时/错误/重试次数', async () => {
    const received = await collect([
      sseEvent('subagents', {
        phase: 'child_started',
        tool_call_id: 'tc-1',
        index: 1,
        agent_id: 'agent-qc',
        name: '质控专家',
      }),
      sseEvent('subagents', {
        phase: 'child_retrying',
        tool_call_id: 'tc-1',
        index: 2,
        agent_id: 'agent-anno',
        attempt: 2,
      }),
      sseEvent('subagents', {
        phase: 'child_done',
        tool_call_id: 'tc-1',
        index: 1,
        agent_id: 'agent-qc',
        status: 'ok',
        elapsed_s: 12.5,
        error: '',
      }),
      sseEvent('done', { session_id: 's1', message_id: 'm1' }),
    ])

    expect(received.map((event) => event.phase)).toEqual([
      'child_started',
      'child_retrying',
      'child_done',
    ])
    expect(received[0].tasks[0]).toMatchObject({ index: 1, status: 'running', name: '质控专家' })
    expect(received[1].tasks[0]).toMatchObject({ index: 2, status: 'retrying', attempt: 2 })
    // 后端 ok 归一化为 succeeded；空 error 不透出
    expect(received[2].tasks[0]).toMatchObject({ index: 1, status: 'succeeded', elapsedS: 12.5 })
    expect(received[2].tasks[0].error).toBeUndefined()
  })

  it('rejected 相位：携带 code 与 reason，无任务网格', async () => {
    const received = await collect([
      sseEvent('subagents', {
        phase: 'rejected',
        tool_call_id: 'tc-9',
        code: 'SUBAGENT_MAX_PARALLEL',
        reason: '单次 fan-out 最多 4 个子任务',
      }),
      sseEvent('done', { session_id: 's1', message_id: 'm1' }),
    ])

    expect(received).toHaveLength(1)
    expect(received[0]).toMatchObject({
      phase: 'rejected',
      toolCallId: 'tc-9',
      code: 'SUBAGENT_MAX_PARALLEL',
      reason: '单次 fan-out 最多 4 个子任务',
    })
    expect(received[0].tasks).toEqual([])
  })

  it('aggregated 相位：progress 为权威终态，携带 runId/success/summary', async () => {
    const received = await collect([
      sseEvent('subagents', {
        phase: 'aggregated',
        tool_call_id: 'tc-1',
        run_id: 'run-abc',
        success: true,
        summary: '1/2 个子任务成功，总墙钟 30s（含失败/超时项，见明细）',
        progress: [
          { index: 1, agent_id: 'agent-qc', status: 'ok', elapsed_s: 20 },
          { index: 2, agent_id: 'agent-anno', status: 'timeout', elapsed_s: 30 },
        ],
      }),
      sseEvent('done', { session_id: 's1', message_id: 'm1' }),
    ])

    expect(received).toHaveLength(1)
    expect(received[0]).toMatchObject({
      phase: 'aggregated',
      runId: 'run-abc',
      success: true,
      summary: '1/2 个子任务成功，总墙钟 30s（含失败/超时项，见明细）',
    })
    expect(received[0].tasks).toEqual([
      { index: 1, agentId: 'agent-qc', task: '', status: 'succeeded', elapsedS: 20 },
      { index: 2, agentId: 'agent-anno', task: '', status: 'timeout', elapsedS: 30 },
    ])
  })

  it('兼容旧事件：无 name/phase 缺省时按 started 处理，label 透传', async () => {
    const received = await collect([
      sseEvent('subagents', {
        tool_call_id: 'tc-old',
        label: 'Skill 路由审查',
        tasks: [{ index: 1, agent_id: 'agent-a', task: '审查技能' }],
      }),
      sseEvent('done', { session_id: 's1', message_id: 'm1' }),
    ])

    expect(received[0].phase).toBe('started')
    expect(received[0].label).toBe('Skill 路由审查')
    expect(received[0].tasks[0]).toMatchObject({ agentId: 'agent-a', status: 'queued' })
    expect(received[0].tasks[0].name).toBeUndefined()
  })
})
