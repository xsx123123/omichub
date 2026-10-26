<script setup lang="ts">
import { computed, ref } from 'vue'
import { NIcon, NProgress } from 'naive-ui'
import { ChevronDownOutline } from '@vicons/ionicons5'
import type { FanoutProgress } from './types'

const props = defineProps<{
  progress: FanoutProgress
}>()

const collapsed = ref(false)

const percent = computed(() =>
  props.progress.total > 0
    ? Math.round((props.progress.completed / props.progress.total) * 100)
    : 0,
)

const progressStatus = computed(() => {
  if (props.progress.phase === 'failed') return 'error'
  if (props.progress.phase === 'succeeded') return 'success'
  if (props.progress.phase === 'partial') return 'warning'
  return 'default'
})

const phaseBadge = computed(() => {
  const badges: Record<FanoutProgress['phase'], { label: string; className: string }> = {
    rejected: { label: '未启动', className: 'is-rejected' },
    running: { label: '协作中', className: 'is-running' },
    succeeded: { label: '已完成', className: 'is-succeeded' },
    partial: { label: '部分完成', className: 'is-partial' },
    failed: { label: '未通过', className: 'is-failed' },
  }
  return badges[props.progress.phase]
})

function taskStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: '排队中',
    running: '执行中',
    retrying: '重试中',
    succeeded: '已完成',
    completed: '已完成',
    partial: '部分完成',
    awaiting_input: '等待你',
    approval_pending: '待审批',
    failed: '失败',
    timeout: '超时',
  }
  return labels[status] || status
}

function taskStatusClass(status: string): string {
  if (['succeeded', 'completed'].includes(status)) return 'is-success'
  if (['failed', 'timeout'].includes(status)) return 'is-error'
  if (['awaiting_input', 'approval_pending', 'partial'].includes(status)) return 'is-waiting'
  if (['running', 'retrying'].includes(status)) return 'is-running'
  return 'is-queued'
}

function formatElapsed(elapsedS?: number): string {
  if (elapsedS === undefined) return ''
  return elapsedS >= 60 ? `${Math.floor(elapsedS / 60)}m${Math.round(elapsedS % 60)}s` : `${elapsedS}s`
}

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}
</script>

<template>
  <section class="fanout-progress-card" :class="`phase-${progress.phase}`">
    <header class="fanout-progress-card__header" @click="toggleCollapsed">
      <span class="fanout-progress-card__eyebrow">◉ 并行协作</span>
      <strong class="fanout-progress-card__title">{{ progress.label }}</strong>
      <span class="fanout-progress-card__badge" :class="phaseBadge.className">
        {{ phaseBadge.label }}
      </span>
      <NIcon class="fanout-progress-card__chevron" :class="{ 'is-collapsed': collapsed }">
        <ChevronDownOutline />
      </NIcon>
    </header>

    <div v-if="progress.phase === 'rejected'" v-show="!collapsed" class="fanout-progress-card__rejected">
      <p class="fanout-progress-card__reason">未启动 · {{ progress.reason || '子任务未通过准入校验' }}</p>
      <p v-if="progress.code" class="fanout-progress-card__code">{{ progress.code }}</p>
    </div>

    <template v-else>
      <div v-show="!collapsed" class="fanout-progress-card__body">
        <div class="fanout-progress-card__meter">
          <NProgress
            type="line"
            :percentage="percent"
            :status="progressStatus"
            :show-indicator="false"
            processing
          />
          <span class="fanout-progress-card__meter-text">
            {{ progress.completed }}/{{ progress.total }} 已结束
          </span>
        </div>

        <ul v-if="progress.tasks.length" class="fanout-progress-card__tasks">
          <li
            v-for="task in progress.tasks"
            :key="task.index"
            class="fanout-progress-card__task"
          >
            <span class="fanout-progress-card__task-dot" :class="taskStatusClass(task.status)" />
            <div class="fanout-progress-card__task-copy">
              <strong>{{ task.name || task.agentId }}</strong>
              <span v-if="task.task" class="fanout-progress-card__task-brief">{{ task.task }}</span>
              <span v-if="task.error" class="fanout-progress-card__task-error">{{ task.error }}</span>
            </div>
            <span class="fanout-progress-card__task-meta">
              <em v-if="task.attempt && task.attempt > 1">第 {{ task.attempt }} 次</em>
              <em v-if="formatElapsed(task.elapsedS)">{{ formatElapsed(task.elapsedS) }}</em>
              {{ taskStatusLabel(task.status) }}
            </span>
          </li>
        </ul>

        <p v-if="progress.summary" class="fanout-progress-card__summary">{{ progress.summary }}</p>
      </div>
    </template>
  </section>
</template>

<style scoped lang="scss">
.fanout-progress-card {
  border: 1px solid var(--chat-border);
  border-radius: var(--radius-lg, 14px);
  background: var(--chat-bg);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fanout-progress-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.fanout-progress-card__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--chat-accent);
  white-space: nowrap;
}

.fanout-progress-card__title {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--chat-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fanout-progress-card__badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
  color: var(--chat-text-secondary);
  background: color-mix(in srgb, var(--chat-text-primary) 7%, transparent);
}

.fanout-progress-card__badge.is-running { color: var(--chat-accent); background: color-mix(in srgb, var(--chat-accent) 12%, transparent); }
.fanout-progress-card__badge.is-succeeded { color: var(--success-color, #18a058); background: color-mix(in srgb, var(--success-color, #18a058) 12%, transparent); }
.fanout-progress-card__badge.is-partial { color: var(--warning-color, #d97706); background: color-mix(in srgb, var(--warning-color, #d97706) 12%, transparent); }
.fanout-progress-card__badge.is-failed,
.fanout-progress-card__badge.is-rejected { color: var(--error-color, #d03050); background: color-mix(in srgb, var(--error-color, #d03050) 10%, transparent); }

.fanout-progress-card__chevron {
  color: var(--chat-text-muted);
  transition: transform 0.2s ease;
}

.fanout-progress-card__chevron.is-collapsed { transform: rotate(-90deg); }

.fanout-progress-card__rejected {
  border: 1px solid color-mix(in srgb, var(--chat-border) 75%, transparent);
  border-radius: 10px;
  padding: 10px 12px;
}

.fanout-progress-card__reason {
  margin: 0;
  font-size: 12px;
  color: var(--chat-text-secondary);
}

.fanout-progress-card__code {
  margin: 4px 0 0;
  font-size: 11px;
  font-family: monospace;
  color: var(--chat-text-muted);
}

.fanout-progress-card__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fanout-progress-card__meter {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fanout-progress-card__meter :deep(.n-progress) { flex: 1; }

.fanout-progress-card__meter-text {
  font-size: 11px;
  color: var(--chat-text-secondary);
  white-space: nowrap;
}

.fanout-progress-card__tasks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

@media (max-width: 720px) {
  .fanout-progress-card__tasks { grid-template-columns: minmax(0, 1fr); }
}

.fanout-progress-card__task {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border: 1px solid color-mix(in srgb, var(--chat-border) 75%, transparent);
  border-radius: 10px;
  padding: 8px 10px;
  background: color-mix(in srgb, var(--chat-surface) 94%, var(--chat-accent) 6%);
}

.fanout-progress-card__task-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 4px;
  flex-shrink: 0;
  background: var(--chat-text-muted);
}

.fanout-progress-card__task-dot.is-running { background: var(--chat-accent); animation: fanout-pulse 1.4s ease-in-out infinite; }
.fanout-progress-card__task-dot.is-success { background: var(--success-color, #18a058); }
.fanout-progress-card__task-dot.is-waiting { background: var(--warning-color, #d97706); }
.fanout-progress-card__task-dot.is-error { background: var(--error-color, #d03050); }
.fanout-progress-card__task-dot.is-queued { background: var(--chat-text-muted); }

@keyframes fanout-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.fanout-progress-card__task-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.fanout-progress-card__task-copy strong {
  color: var(--chat-text-primary);
  font-size: 12px;
}

.fanout-progress-card__task-brief {
  color: var(--chat-text-muted);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.fanout-progress-card__task-error {
  color: var(--error-color, #d03050);
  font-size: 11px;
}

.fanout-progress-card__task-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-size: 11px;
  color: var(--chat-text-secondary);
  white-space: nowrap;
}

.fanout-progress-card__task-meta em {
  font-style: normal;
  color: var(--chat-text-muted);
}

.fanout-progress-card__summary {
  margin: 0;
  font-size: 11px;
  color: var(--chat-text-secondary);
  border-top: 1px solid color-mix(in srgb, var(--chat-border) 70%, transparent);
  padding-top: 8px;
}
</style>
