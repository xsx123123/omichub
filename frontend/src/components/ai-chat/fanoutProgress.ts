/**
 * 对话内并行子 Agent fan-out 的纯归约器：把 SubagentFanoutEvent 折叠进消息列表中的
 * FanoutProgress 卡片（按 tool_call_id 归属）。从 agentHub 的流回调中抽出以便单测。
 *
 * 归约语义：
 * - rejected：建"未启动"卡（无任务网格、不占配额）；
 * - started：建卡/重置，任务全部 queued（仅表示已接受分派）；
 * - child_started/child_retrying/child_done：按 index 逐子更新；
 * - aggregated：以后端 progress 为子终态权威来源，按 success + 子终态推导 run 终态，
 *   success=false 绝不呈现为完成态。
 */
import type { SubagentFanoutEvent } from '@/composables/useAgentChatStream'
import type { ChatMessage, FanoutProgress } from './types'

const TERMINAL_STATUSES = [
  'succeeded',
  'completed',
  'failed',
  'timeout',
  'partial',
  'awaiting_input',
  'approval_pending',
]
const FAILED_STATUSES = ['failed', 'timeout']
const INTERRUPTED_STATUSES = ['awaiting_input', 'approval_pending']

function recount(progress: FanoutProgress, defaultLabel: string): void {
  progress.completed = progress.tasks.filter((task) =>
    TERMINAL_STATUSES.includes(task.status),
  ).length
  progress.succeeded = progress.tasks.filter(
    (task) => task.status === 'succeeded' || task.status === 'completed',
  ).length
  progress.failed = progress.tasks.filter((task) => FAILED_STATUSES.includes(task.status)).length
  progress.label = `${defaultLabel} · 已结束 ${progress.completed}/${progress.total} · 成功 ${progress.succeeded} · 失败 ${progress.failed}`
}

export function applySubagentFanoutEvent(
  messages: ChatMessage[],
  event: SubagentFanoutEvent,
): void {
  const cardId = `fanout-${event.toolCallId || 'anon'}`
  const defaultLabel = event.label || '并行专家协作'
  let card = messages.find((item) => item.id === cardId)

  if (event.phase === 'rejected') {
    if (!card) {
      const reason = event.reason || '子任务未通过准入校验'
      messages.push({
        id: cardId,
        role: 'system',
        content: `${defaultLabel} · 未启动`,
        createdAt: new Date().toISOString(),
        fanoutProgress: {
          phase: 'rejected',
          label: `${defaultLabel} · 未启动`,
          completed: 0,
          total: 0,
          succeeded: 0,
          failed: 0,
          code: event.code,
          reason,
          tasks: [],
        },
      })
    }
    return
  }

  if (!card) {
    // 无 started 的孤立事件不建卡（历史/异常流量防御）
    if (event.phase !== 'started') return
    card = {
      id: cardId,
      role: 'system',
      content: `${defaultLabel}（${event.tasks.length} 位专家）`,
      createdAt: new Date().toISOString(),
      fanoutProgress: {
        phase: 'running',
        label: `${defaultLabel}（${event.tasks.length} 位专家）`,
        completed: 0,
        total: event.tasks.length,
        succeeded: 0,
        failed: 0,
        tasks: event.tasks.map((task) => ({
          index: task.index,
          agentId: task.agentId,
          name: task.name,
          task: task.task,
          status: 'queued',
        })),
      },
    }
    messages.push(card)
  }
  const progress = card.fanoutProgress
  if (!progress) return

  if (event.phase === 'started') {
    // 同 tool_call_id 的重复 started（如重试重建）：以最新任务清单重置
    progress.phase = 'running'
    progress.total = event.tasks.length
    progress.tasks = event.tasks.map((task) => ({
      index: task.index,
      agentId: task.agentId,
      name: task.name,
      task: task.task,
      status: 'queued',
    }))
    progress.label = `${defaultLabel}（${progress.total} 位专家）`
    progress.completed = 0
    progress.succeeded = 0
    progress.failed = 0
    card.content = progress.label
    return
  }

  if (
    event.phase === 'child_started' ||
    event.phase === 'child_retrying' ||
    event.phase === 'child_done'
  ) {
    const child = event.tasks[0]
    if (!child) return
    const target = progress.tasks.find((task) => task.index === child.index)
    if (target) {
      target.status = child.status
      if (child.name) target.name = child.name
      if (child.elapsedS !== undefined) target.elapsedS = child.elapsedS
      if (child.error) target.error = child.error
      if (child.attempt !== undefined) target.attempt = child.attempt
    }
    if (event.phase === 'child_done') {
      recount(progress, defaultLabel)
      card.content = progress.label
    }
    return
  }

  // aggregated
  if (event.runId) progress.runId = event.runId
  for (const item of event.tasks) {
    const target = progress.tasks.find((task) => task.index === item.index)
    if (target) {
      target.status = item.status
      if (item.elapsedS !== undefined) target.elapsedS = item.elapsedS
    }
  }
  recount(progress, defaultLabel)
  progress.summary = event.summary || undefined
  const interrupted = progress.tasks.filter((task) =>
    INTERRUPTED_STATUSES.includes(task.status),
  ).length
  progress.phase =
    progress.total > 0 && progress.succeeded === progress.total
      ? 'succeeded'
      : progress.succeeded === 0 && interrupted === 0
        ? 'failed'
        : 'partial'
  card.content = progress.label
}
