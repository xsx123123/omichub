// @vitest-environment jsdom
/**
 * FanoutProgress 归约器与 FanoutProgressCard 渲染测试：
 * 覆盖 rejected / started / child 逐子事件 / aggregated 全相位状态机，以及
 * "success=false 不得呈现完成态"的回归约束。
 */
import { createApp } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'
import { applySubagentFanoutEvent } from '../fanoutProgress'
import FanoutProgressCard from '../FanoutProgressCard.vue'
import type { ChatMessage } from '../types'
import type { SubagentFanoutEvent } from '@/composables/useAgentChatStream'

function startedEvent(tasks: Array<{ index: number; agentId: string; name?: string }>): SubagentFanoutEvent {
  return {
    phase: 'started',
    toolCallId: 'tc-1',
    tasks: tasks.map((task) => ({ ...task, task: `任务 ${task.index}`, status: 'queued' })),
  }
}

function childEvent(
  phase: 'child_started' | 'child_retrying' | 'child_done',
  task: Partial<SubagentFanoutEvent['tasks'][number]> & { index: number },
): SubagentFanoutEvent {
  // 模拟流解析层：child_started/child_retrying 在 reducer 之前已被赋运行态
  const parsedStatus = phase === 'child_started' ? 'running' : phase === 'child_retrying' ? 'retrying' : ''
  return {
    phase,
    toolCallId: 'tc-1',
    tasks: [{ agentId: 'agent-x', task: '', status: parsedStatus, ...task }],
  }
}

describe('applySubagentFanoutEvent 归约器', () => {
  it('rejected：建"未启动"卡，无任务网格，携带 code/reason', () => {
    const messages: ChatMessage[] = []
    applySubagentFanoutEvent(messages, {
      phase: 'rejected',
      toolCallId: 'tc-1',
      code: 'SUBAGENT_MAX_PARALLEL',
      reason: '单次 fan-out 最多 4 个子任务',
      tasks: [],
    })

    expect(messages).toHaveLength(1)
    const progress = messages[0].fanoutProgress!
    expect(progress.phase).toBe('rejected')
    expect(progress.tasks).toEqual([])
    expect(progress.reason).toContain('最多 4 个')
    expect(progress.code).toBe('SUBAGENT_MAX_PARALLEL')
    expect(progress.label).toContain('未启动')
    expect(messages[0].overdriveProgress).toBeUndefined()
  })

  it('started 建卡全部 queued；child_done 逐步归约计数与标签', () => {
    const messages: ChatMessage[] = []
    applySubagentFanoutEvent(messages, startedEvent([
      { index: 1, agentId: 'agent-qc', name: '质控专家' },
      { index: 2, agentId: 'agent-anno', name: '注释专家' },
    ]))

    const progress = messages[0].fanoutProgress!
    expect(progress.phase).toBe('running')
    expect(progress.total).toBe(2)
    expect(progress.tasks.map((task) => task.status)).toEqual(['queued', 'queued'])
    expect(progress.tasks[0].name).toBe('质控专家')

    applySubagentFanoutEvent(messages, childEvent('child_started', { index: 1 }))
    expect(progress.tasks[0].status).toBe('running')
    expect(progress.completed).toBe(0)

    applySubagentFanoutEvent(messages, childEvent('child_done', {
      index: 1,
      status: 'succeeded',
      elapsedS: 12,
    }))
    expect(progress.completed).toBe(1)
    expect(progress.succeeded).toBe(1)
    expect(progress.label).toBe('并行专家协作 · 已结束 1/2 · 成功 1 · 失败 0')
    expect(progress.phase).toBe('running')
  })

  it('child_retrying 记录 attempt；aggregated 部分失败 → partial 而非完成', () => {
    const messages: ChatMessage[] = []
    applySubagentFanoutEvent(messages, startedEvent([
      { index: 1, agentId: 'agent-a' },
      { index: 2, agentId: 'agent-b' },
    ]))
    applySubagentFanoutEvent(messages, childEvent('child_retrying', { index: 2, attempt: 2 }))
    applySubagentFanoutEvent(messages, {
      phase: 'aggregated',
      toolCallId: 'tc-1',
      runId: 'run-1',
      success: true,
      summary: '1/2 个子任务成功',
      tasks: [
        { index: 1, agentId: 'agent-a', task: '', status: 'succeeded', elapsedS: 10 },
        { index: 2, agentId: 'agent-b', task: '', status: 'timeout', elapsedS: 30 },
      ],
    })

    const progress = messages[0].fanoutProgress!
    expect(progress.phase).toBe('partial')
    expect(progress.runId).toBe('run-1')
    expect(progress.succeeded).toBe(1)
    expect(progress.failed).toBe(1)
    expect(progress.summary).toBe('1/2 个子任务成功')
    // started 阶段的名称/文案不被 aggregated 覆盖掉（aggregated 无 name/task 字段）
    expect(progress.tasks[0].task).toBe('任务 1')
  })

  it('aggregated 全部失败 → failed（success=false 不显示完成态）', () => {
    const messages: ChatMessage[] = []
    applySubagentFanoutEvent(messages, startedEvent([{ index: 1, agentId: 'agent-a' }]))
    applySubagentFanoutEvent(messages, {
      phase: 'aggregated',
      toolCallId: 'tc-1',
      success: false,
      summary: '',
      tasks: [{ index: 1, agentId: 'agent-a', task: '', status: 'failed' }],
    })

    expect(messages[0].fanoutProgress!.phase).toBe('failed')
  })

  it('aggregated 全部成功 → succeeded；存在等待用户处理项 → partial', () => {
    const okMessages: ChatMessage[] = []
    applySubagentFanoutEvent(okMessages, startedEvent([{ index: 1, agentId: 'agent-a' }]))
    applySubagentFanoutEvent(okMessages, {
      phase: 'aggregated',
      toolCallId: 'tc-1',
      success: true,
      summary: '1/1 个子任务成功',
      tasks: [{ index: 1, agentId: 'agent-a', task: '', status: 'succeeded' }],
    })
    expect(okMessages[0].fanoutProgress!.phase).toBe('succeeded')

    const awaitingMessages: ChatMessage[] = []
    applySubagentFanoutEvent(awaitingMessages, startedEvent([
      { index: 1, agentId: 'agent-a' },
      { index: 2, agentId: 'agent-b' },
    ]))
    applySubagentFanoutEvent(awaitingMessages, {
      phase: 'aggregated',
      toolCallId: 'tc-1',
      success: true,
      summary: '1/2 个子任务等待用户处理',
      tasks: [
        { index: 1, agentId: 'agent-a', task: '', status: 'succeeded' },
        { index: 2, agentId: 'agent-b', task: '', status: 'awaiting_input' },
      ],
    })
    expect(awaitingMessages[0].fanoutProgress!.phase).toBe('partial')
  })

  it('无 started 的孤立 child/aggregated 事件不建卡；label 作为卡片标题', () => {
    const messages: ChatMessage[] = []
    applySubagentFanoutEvent(messages, childEvent('child_started', { index: 1 }))
    expect(messages).toHaveLength(0)

    applySubagentFanoutEvent(messages, {
      ...startedEvent([{ index: 1, agentId: 'agent-a' }]),
      label: 'Skill 路由审查',
    })
    expect(messages[0].fanoutProgress!.label).toContain('Skill 路由审查')
  })
})

describe('FanoutProgressCard', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  function mount(progress: Record<string, unknown>): HTMLElement {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = createApp({
      components: { FanoutProgressCard },
      template: '<FanoutProgressCard :progress="progress" />',
      data: () => ({ progress }),
    })
    app.mount(host)
    return host
  }

  it('running 态：渲染眉标、进度条与任务状态点', () => {
    const host = mount({
      phase: 'running',
      label: '并行专家协作（2 位专家）',
      completed: 1,
      total: 2,
      succeeded: 1,
      failed: 0,
      tasks: [
        { index: 1, agentId: 'agent-qc', name: '质控专家', status: 'succeeded', elapsedS: 12 },
        { index: 2, agentId: 'agent-anno', name: '注释专家', status: 'running' },
      ],
    })

    expect(host.textContent).toContain('◉ 并行协作')
    expect(host.textContent).toContain('协作中')
    expect(host.textContent).toContain('1/2 已结束')
    expect(host.textContent).toContain('质控专家')
    expect(host.textContent).toContain('注释专家')
    expect(host.textContent).toContain('已完成')
    expect(host.textContent).toContain('执行中')
    expect(host.querySelector('.fanout-progress-card__task-dot.is-success')).not.toBeNull()
    expect(host.querySelector('.fanout-progress-card__task-dot.is-running')).not.toBeNull()
    // 不含超频专属元素
    expect(host.textContent).not.toContain('超频')
    expect(host.textContent).not.toContain('Wave')
  })

  it('rejected 态：呈现"未启动 · 原因"与拒绝码，无进度条与任务网格', () => {
    const host = mount({
      phase: 'rejected',
      label: '并行专家协作 · 未启动',
      completed: 0,
      total: 0,
      succeeded: 0,
      failed: 0,
      code: 'SUBAGENT_DISABLED',
      reason: '子 Agent 并行分派未启用',
      tasks: [],
    })

    expect(host.textContent).toContain('未启动')
    expect(host.textContent).toContain('子 Agent 并行分派未启用')
    expect(host.textContent).toContain('SUBAGENT_DISABLED')
    expect(host.querySelector('.n-progress')).toBeNull()
    expect(host.querySelectorAll('.fanout-progress-card__task')).toHaveLength(0)
  })

  it('failed 态：状态点红色语义与失败原因透出', () => {
    const host = mount({
      phase: 'failed',
      label: '并行专家协作 · 已结束 2/2 · 成功 0 · 失败 2',
      completed: 2,
      total: 2,
      succeeded: 0,
      failed: 2,
      tasks: [
        { index: 1, agentId: 'agent-a', status: 'failed', error: '模型超时' },
        { index: 2, agentId: 'agent-b', status: 'timeout' },
      ],
    })

    expect(host.textContent).toContain('未通过')
    expect(host.textContent).toContain('模型超时')
    expect(host.textContent).toContain('超时')
    expect(host.querySelectorAll('.fanout-progress-card__task-dot.is-error')).toHaveLength(2)
  })
})
