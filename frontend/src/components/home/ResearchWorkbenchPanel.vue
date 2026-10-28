<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { NButton, NEmpty, NIcon, NTag } from 'naive-ui'
import {
  AlertCircleOutline,
  ChevronForwardOutline,
  DocumentTextOutline,
  FolderOpenOutline,
  RefreshOutline,
  TimeOutline,
} from '@vicons/ionicons5'
import apiClient from '@/api/client'
import { projectsApi, type ProjectItem } from '@/api/projects'
import { reportApi } from '@/api/report'
import type { Report } from '@/types/report'
import type { Task } from '@/types'

const projects = ref<ProjectItem[]>([])
const runningTasks = ref<Task[]>([])
const recentReports = ref<Report[]>([])
const selectedCard = ref<string | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const projectsUnavailable = ref(false)
const tasksUnavailable = ref(false)
const reportsUnavailable = ref(false)
const tasksPartial = ref(false)

function mostRecent<T extends { created_at?: string | null; updated_at?: string | null }>(
  items: T[],
  limit: number,
): T[] {
  return [...items]
    .sort((a, b) => {
      const aDate = new Date(a.updated_at || a.created_at || 0).getTime()
      const bDate = new Date(b.updated_at || b.created_at || 0).getTime()
      return bDate - aDate
    })
    .slice(0, limit)
}

async function loadData() {
  if (refreshing.value) return
  refreshing.value = true
  loading.value = true

  const results = await Promise.allSettled([
    projectsApi.listProjects(),
    apiClient.get<{ items: Task[] }>('/tasks', { params: { status: 'running', limit: 5 } }),
    apiClient.get<{ items: Task[] }>('/tasks', { params: { status: 'queued', limit: 5 } }),
    reportApi.getReports({ page: 1, page_size: 5 }),
  ])

  const [projectResult, runningResult, queuedResult, reportResult] = results

  projectsUnavailable.value = projectResult.status === 'rejected'
  projects.value = projectResult.status === 'fulfilled'
    ? mostRecent(projectResult.value, 3)
    : []

  const taskResults = [runningResult, queuedResult]
  const successfulTaskResults = taskResults.filter((result) => result.status === 'fulfilled')
  tasksUnavailable.value = successfulTaskResults.length === 0
  tasksPartial.value = successfulTaskResults.length > 0 && successfulTaskResults.length < taskResults.length
  runningTasks.value = mostRecent(
    successfulTaskResults.flatMap((result) => result.status === 'fulfilled' ? result.value.data.items ?? [] : []),
    5,
  )

  reportsUnavailable.value = reportResult.status === 'rejected'
  recentReports.value = reportResult.status === 'fulfilled'
    ? mostRecent(reportResult.value.data.items ?? [], 3)
    : []

  loading.value = false
  refreshing.value = false
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '时间未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未记录'
  return date.toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function taskStatusLabel(status: Task['status']): string {
  if (status === 'running') return '运行中'
  if (status === 'queued') return '排队中'
  if (status === 'pending') return '待启动'
  if (status === 'success') return '已完成'
  if (status === 'failed') return '失败'
  return '已取消'
}

function taskStatusTone(status: Task['status']): string {
  if (status === 'running') return 'running'
  if (status === 'success') return 'completed'
  if (status === 'queued' || status === 'pending') return 'pending'
  if (status === 'failed') return 'failed'
  return 'expired'
}

onMounted(() => void loadData())
</script>

<template>
  <section class="workbench-section" aria-labelledby="workbench-title" :aria-busy="loading">
    <div class="section-heading">
      <div>
        <p class="section-eyebrow">YOUR RESEARCH DESK</p>
        <h2 id="workbench-title">我的科研工作台</h2>
        <p class="section-subtitle">最近项目、执行中的任务和报告，都从这里继续。</p>
      </div>
      <NButton quaternary size="small" :loading="refreshing" @click="loadData">
        <template #icon><NIcon><RefreshOutline /></NIcon></template>
        刷新
      </NButton>
    </div>

    <div class="workbench-grid" aria-live="polite">
      <section class="workbench-card cygnusx-selectable-card" :data-selected="selectedCard === 'projects'" aria-labelledby="recent-projects-title" @click.capture="selectedCard = 'projects'" @focusin="selectedCard = 'projects'">
        <header class="workbench-card__header">
          <div class="workbench-card__heading">
            <span class="workbench-card__icon workbench-card__icon--blue">
              <NIcon :size="17"><FolderOpenOutline /></NIcon>
            </span>
            <h3 id="recent-projects-title">最近项目</h3>
          </div>
          <RouterLink class="workbench-card__more" :to="{ name: 'projects' }">
            全部 <NIcon :size="14" class="card-state-arrow"><ChevronForwardOutline /></NIcon>
          </RouterLink>
        </header>

        <div v-if="loading" class="workbench-skeleton" aria-label="正在加载项目">
          <span /><span /><span />
        </div>
        <div v-else-if="projectsUnavailable" class="workbench-unavailable">
          <NIcon :size="17"><AlertCircleOutline /></NIcon>
          <span>项目暂时无法加载</span>
          <NButton text type="primary" size="tiny" @click="loadData">重试</NButton>
        </div>
        <NEmpty v-else-if="projects.length === 0" size="small" description="还没有科研项目">
          <template #extra>
            <RouterLink class="workbench-empty-link" :to="{ name: 'projects' }">创建第一个项目</RouterLink>
          </template>
        </NEmpty>
        <div v-else class="workbench-items">
          <RouterLink
            v-for="project in projects"
            :key="project.id"
            class="workbench-item"
            :to="{ name: 'project-detail', params: { projectId: project.id } }"
          >
            <span class="workbench-item__main">
              <strong :title="project.name">{{ project.name }}</strong>
              <small>{{ project.description || '项目工作区' }}</small>
            </span>
            <span class="workbench-item__meta">{{ formatTime(project.updated_at || project.created_at) }}</span>
          </RouterLink>
        </div>
      </section>

      <section class="workbench-card cygnusx-selectable-card" :data-selected="selectedCard === 'tasks'" aria-labelledby="running-tasks-title" @click.capture="selectedCard = 'tasks'" @focusin="selectedCard = 'tasks'">
        <header class="workbench-card__header">
          <div class="workbench-card__heading">
            <span class="workbench-card__icon workbench-card__icon--violet">
              <NIcon :size="17"><TimeOutline /></NIcon>
            </span>
            <h3 id="running-tasks-title">运行任务</h3>
          </div>
          <RouterLink class="workbench-card__more" :to="{ name: 'tasks' }">
            全部 <NIcon :size="14" class="card-state-arrow"><ChevronForwardOutline /></NIcon>
          </RouterLink>
        </header>

        <div v-if="loading" class="workbench-skeleton" aria-label="正在加载任务">
          <span /><span /><span />
        </div>
        <div v-else-if="tasksUnavailable" class="workbench-unavailable">
          <NIcon :size="17"><AlertCircleOutline /></NIcon>
          <span>任务暂时无法加载</span>
          <NButton text type="primary" size="tiny" @click="loadData">重试</NButton>
        </div>
        <template v-else>
          <p v-if="tasksPartial" class="workbench-partial-note">部分任务状态暂不可用</p>
          <NEmpty v-if="runningTasks.length === 0" size="small" description="当前没有排队或运行中的任务">
            <template #extra>
              <RouterLink class="workbench-empty-link" :to="{ name: 'flows' }">选择分析流程</RouterLink>
            </template>
          </NEmpty>
          <div v-else class="workbench-items">
            <RouterLink
              v-for="task in runningTasks"
              :key="task.id"
              class="workbench-item"
              :to="{ name: 'task-detail', params: { taskId: task.id } }"
            >
              <span class="workbench-item__main">
                <strong :title="task.name">{{ task.name }}</strong>
                <small>{{ task.flow_id }} · {{ formatTime(task.created_at) }}</small>
              </span>
              <NTag size="small" round :bordered="false" class="status-badge" :class="`status-badge--${taskStatusTone(task.status)}`">
                {{ taskStatusLabel(task.status) }}
              </NTag>
            </RouterLink>
          </div>
        </template>
      </section>

      <section class="workbench-card cygnusx-selectable-card" :data-selected="selectedCard === 'reports'" aria-labelledby="recent-reports-title" @click.capture="selectedCard = 'reports'" @focusin="selectedCard = 'reports'">
        <header class="workbench-card__header">
          <div class="workbench-card__heading">
            <span class="workbench-card__icon workbench-card__icon--cyan">
              <NIcon :size="17"><DocumentTextOutline /></NIcon>
            </span>
            <h3 id="recent-reports-title">最近报告</h3>
          </div>
          <RouterLink class="workbench-card__more" :to="{ name: 'reports' }">
            全部 <NIcon :size="14" class="card-state-arrow"><ChevronForwardOutline /></NIcon>
          </RouterLink>
        </header>

        <div v-if="loading" class="workbench-skeleton" aria-label="正在加载报告">
          <span /><span /><span />
        </div>
        <div v-else-if="reportsUnavailable" class="workbench-unavailable">
          <NIcon :size="17"><AlertCircleOutline /></NIcon>
          <span>报告暂时无法加载</span>
          <NButton text type="primary" size="tiny" @click="loadData">重试</NButton>
        </div>
        <NEmpty v-else-if="recentReports.length === 0" size="small" description="完成分析后，报告会显示在这里">
          <template #extra>
            <RouterLink class="workbench-empty-link" :to="{ name: 'reports' }">打开报告中心</RouterLink>
          </template>
        </NEmpty>
        <div v-else class="workbench-items">
          <RouterLink
            v-for="report in recentReports"
            :key="report.id"
            class="workbench-item"
            :to="{ name: 'reports', query: { reportId: report.id } }"
          >
            <span class="workbench-item__main">
              <strong :title="report.title">{{ report.title }}</strong>
              <small>{{ report.flow_name }} · {{ formatTime(report.created_at) }}</small>
            </span>
            <NTag size="small" round :bordered="false" class="status-badge" :class="`status-badge--${report.status === 'generating' ? 'running' : report.status}`">
              {{ report.status === 'completed' ? '已完成' : report.status === 'generating' ? '生成中' : report.status === 'failed' ? '失败' : '已过期' }}
            </NTag>
          </RouterLink>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.workbench-section {
  margin: 0 0 32px;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 16px;
}

.section-eyebrow {
  margin: 0 0 4px;
  color: var(--neutral-text-3);
  font-size: var(--home-font-eyebrow, 11px);
  font-weight: 700;
  letter-spacing: 1.2px;
}

.section-heading h2 {
  margin: 0;
  color: var(--neutral-text-1);
  font-size: var(--home-font-section, 24px);
  font-weight: 650;
  line-height: 1.35;
}

.section-subtitle {
  margin: 5px 0 0;
  color: var(--neutral-text-2);
  font-size: var(--home-font-body, 14px);
  line-height: 1.5;
}

.workbench-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.workbench-card {
  position: relative;
  min-width: 0;
  min-height: 264px;
  padding: 20px 20px 12px;
  border: 1px solid var(--neutral-border);
  border-radius: var(--radius-card);
  background: var(--neutral-card);
  box-shadow: var(--shadow-card);
}

.workbench-card__header,
.workbench-card__heading {
  display: flex;
  align-items: center;
}

.workbench-card__header {
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 13px;
}

.workbench-card__heading {
  min-width: 0;
  gap: 9px;
}

.workbench-card__heading h3 {
  overflow: hidden;
  margin: 0;
  color: var(--neutral-text-1);
  font-size: var(--home-font-card-title, 16px);
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workbench-card__icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 9px;
}

.workbench-card__icon--blue {
  color: var(--brand-primary);
  background: var(--brand-primary-light);
}

.workbench-card__icon--violet {
  color: #8059d8;
  background: color-mix(in srgb, #8059d8 11%, var(--neutral-card));
}

.workbench-card__icon--cyan {
  color: #0b9d9a;
  background: color-mix(in srgb, #0b9d9a 11%, var(--neutral-card));
}

.workbench-card__more {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 2px;
  color: var(--neutral-text-2);
  font-size: var(--home-font-small, 13px);
  text-decoration: none;
}

.workbench-card__more:hover,
.workbench-empty-link:hover {
  color: var(--brand-primary);
}

.workbench-items {
  display: flex;
  flex-direction: column;
}

.workbench-item {
  display: flex;
  min-width: 0;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 2px;
  border-top: 1px solid color-mix(in srgb, var(--neutral-border) 70%, transparent);
  color: inherit;
  text-decoration: none;
}

.workbench-item:hover strong {
  color: var(--brand-primary);
}

.workbench-item__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 4px;
}

.workbench-item__main strong,
.workbench-item__main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workbench-item__main strong {
  line-height: 1.5;
  color: var(--neutral-text-1);
  font-size: var(--home-font-body, 14px);
  font-weight: 600;
}

.workbench-item__main small {
  line-height: 1.5;
  color: var(--neutral-text-2);
  font-size: var(--home-font-meta, 12px);
}

.workbench-item__meta {
  flex: 0 0 auto;
  color: var(--neutral-text-2);
  font-size: var(--home-font-meta, 12px);
}

.workbench-skeleton {
  display: flex;
  flex-direction: column;
  gap: 13px;
  padding: 12px 2px;
}

.workbench-skeleton span {
  height: 10px;
  border-radius: 6px;
  background: var(--neutral-fill-2);
  animation: skeleton-pulse 1.4s ease-in-out infinite;
}

.workbench-skeleton span:nth-child(2) { width: 76%; }
.workbench-skeleton span:nth-child(3) { width: 88%; }

.workbench-unavailable {
  display: flex;
  min-height: 130px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: var(--neutral-text-2);
  font-size: var(--home-font-body, 14px);
}

.workbench-unavailable > :first-child {
  color: var(--color-warning, #d58a24);
}

.workbench-partial-note {
  margin: -3px 0 4px;
  color: var(--neutral-text-2);
  font-size: var(--home-font-meta, 12px);
}

.workbench-empty-link {
  color: var(--brand-primary);
  font-size: var(--home-font-body, 14px);
  text-decoration: none;
}

.status-badge {
  flex: 0 0 auto;
  height: 26px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--badge-bg);
  color: var(--badge-color);
  font-size: var(--home-font-meta, 12px);
  font-weight: 600;
  line-height: 24px;
}

.status-badge--running { --badge-bg: rgba(76, 141, 255, 0.12); --badge-color: #2459ad; }
.status-badge--completed { --badge-bg: rgba(52, 211, 153, 0.12); --badge-color: #12734f; }
.status-badge--expired { --badge-bg: rgba(148, 163, 184, 0.12); --badge-color: #526074; }
.status-badge--pending { --badge-bg: rgba(245, 158, 11, 0.12); --badge-color: #875407; }
.status-badge--failed { --badge-bg: rgba(248, 113, 113, 0.12); --badge-color: #af3030; }

[data-theme="dark"] .status-badge--running { --badge-color: #7fb0ff; }
[data-theme="dark"] .status-badge--completed { --badge-color: #34d399; }
[data-theme="dark"] .status-badge--expired { --badge-color: #b8c2d1; }
[data-theme="dark"] .status-badge--pending { --badge-color: #fcd37b; }
[data-theme="dark"] .status-badge--failed { --badge-color: #fca5a5; }

.section-heading > .n-button {
  font-size: var(--home-font-body, 14px);
}

.workbench-card :deep(.n-empty__description) {
  font-size: var(--home-font-body, 14px);
}

.workbench-card :deep(.n-empty) {
  padding-top: 18px;
}

@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.52; }
  50% { opacity: 1; }
}

@media (width < 1280px) {
  .workbench-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 680px) {
  .section-heading {
    align-items: flex-start;
  }

  .section-heading h2 { font-size: 22px; }

  .workbench-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
  }

  .workbench-card,
  .workbench-card:last-child {
    min-height: 0;
    grid-column: auto;
    padding: 15px 15px 10px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workbench-card { transition: none; }
  .workbench-skeleton span {
    animation: none;
  }
}
</style>
