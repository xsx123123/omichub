<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NIcon, NSpace, NSpin, NTooltip, useMessage } from 'naive-ui'
import { ArrowBackOutline, DownloadOutline, OpenOutline, RefreshOutline, SparklesOutline, Star, StarOutline } from '@vicons/ionicons5'
import { downloadReportFile, reportApi } from '@/api/report'
import type { Report, ReportPreview } from '@/types/report'
import { REPORT_PREVIEW_AUTH_CLEARED } from '@/utils/reportPreviewSession'
import { SELECTION_LIMIT, buildSelectionPrefill } from '@/utils/reportSelection'
import { useAiAssistantSidebarStore } from '@/stores/aiAssistantSidebar'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const sidebar = useAiAssistantSidebarStore()
const report = ref<Report | null>(null)
const preview = ref<ReportPreview | null>(null)
const frame = ref<HTMLIFrameElement | null>(null)
const loading = ref(false)
const error = ref('')
const starring = ref(false)
const downloading = ref(false)
const language = ref<'zh' | 'en'>('zh')
interface ReportSelection { text: string; section: string; x: number; y: number }
const selection = ref<ReportSelection | null>(null)
const selectionTruncated = computed(() => (selection.value?.text.length || 0) > SELECTION_LIMIT)
const selectionButtonStyle = computed(() => {
  const current = selection.value
  if (!current) return {}
  const el = frame.value
  const maxX = Math.max(8, (el?.clientWidth || 800) - 150)
  const maxY = Math.max(8, (el?.clientHeight || 600) - 48)
  return {
    left: `${Math.max(8, Math.min(current.x + 8, maxX))}px`,
    top: `${Math.max(8, Math.min(current.y + 8, maxY))}px`,
  }
})
const primary = computed(() => report.value?.files.find(file => file.is_primary) || report.value?.files[0])
const generatedAt = computed(() => {
  const timestamp = report.value?.completed_at || report.value?.created_at
  if (!timestamp) return '—'
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
})
const statusLabels: Record<Report['status'], string> = {
  completed: '已完成', generating: '生成中', failed: '生成失败', expired: '已过期',
}
// 头部标题组：主标题优先取项目名称，机器编号降级为等宽 chip（点击复制）。
// title 由后端拼装："项目编号 分析报告"（外部交付）/"客户 - 流程 分析报告"/"流程 分析报告"。
const titleParts = computed(() => {
  const current = report.value
  const title = current?.title.trim() || ''
  if (!current || !title) return { main: '报告查看', id: '' }
  const head = /^(.*?)\s*分析报告\s*$/.exec(title)?.[1]?.trim() ?? ''
  if (!head) return { main: title, id: '' }
  if (head.includes(' - ')) return { main: head.split(' - ')[0].trim() || title, id: '' }
  if (head === current.flow_name) return { main: '分析报告', id: '' }
  return { main: '分析报告', id: head }
})

async function copyProjectId() {
  const id = titleParts.value.id
  if (!id) return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(id)
    } else {
      const el = document.createElement('textarea')
      el.value = id
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      el.remove()
    }
    message.success('项目编号已复制')
  } catch { message.error('复制失败，请手动选择复制') }
}
let epoch = 0
let loadTimer: ReturnType<typeof setTimeout> | undefined

function stopTimer() {
  clearTimeout(loadTimer)
  loadTimer = undefined
}

function fail(status?: number, code?: string) {
  stopTimer()
  preview.value = null
  loading.value = false
  error.value = code === 'REPORT_EXPIRED' ? '报告已过期，请重新生成后查看。'
    : code === 'REPORT_TOO_LARGE' ? '报告超过在线预览大小限制，请下载查看。'
    : status === 404 ? '报告或报告文件不存在，可能已被删除。'
    : status === 401 || status === 403 ? '预览会话已失效或您暂无权限，请重新登录后重试。'
    : status === 409 ? '报告当前不可预览，请检查报告状态或下载文件。'
    : '报告加载失败，请重试或下载查看。'
}

async function loadReport() {
  const current = ++epoch
  stopTimer()
  report.value = null
  preview.value = null
  error.value = ''
  loading.value = true
  const id = String(route.params.reportId || '')
  selection.value = null
  try {
    const detail = await reportApi.getReportDetail(id)
    if (current !== epoch) return
    report.value = detail.data
    if (detail.data.status === 'expired') { fail(409, 'REPORT_EXPIRED'); return }
    if (detail.data.status !== 'completed') {
      error.value = detail.data.status === 'generating' ? '报告仍在生成中，请稍后重试。' : '报告生成失败，暂时无法预览。'
      loading.value = false
      return
    }
    if (detail.data.report_kind === 'delivery') {
      error.value = '这是一份科研交付包，请下载后查看其中的报告。'
      loading.value = false
      return
    }
    const result = await reportApi.getPreviewUrl(id, language.value)
    if (current !== epoch) return
    const url = new URL(result.data.url, window.location.origin)
    if (url.origin !== window.location.origin || url.pathname !== `/api/v1/reports/${id}/preview-content`) {
      fail()
      return
    }
    preview.value = result.data
    loadTimer = setTimeout(() => { if (current === epoch) fail() }, (result.data.load_timeout_seconds || 30) * 1000)
    if (!detail.data.is_read) void reportApi.markAsRead(id).catch(() => {})
  } catch (cause) {
    if (current !== epoch) return
    const response = (cause as { response?: { status?: number; data?: { code?: string } } })?.response
    fail(response?.status, response?.data?.code)
  }
}

function onPreviewMessage(event: MessageEvent) {
  const data = event.data
  if (!preview.value || event.source !== frame.value?.contentWindow || event.origin !== 'null'
    || !data || data.reportId !== report.value?.id || data.channel !== preview.value.channel) return
  if (data.type === 'cygnusx:report-language' && report.value?.source_kind === 'external') {
    if (data.language !== 'zh' && data.language !== 'en') return
    if (data.language === 'en' && !report.value.files.some(file => file.name.endsWith('.en.html'))) return
    language.value = data.language
    void loadReport()
    return
  }
  if (data.type === 'cygnusx:report-selection') {
    if (typeof data.text !== 'string' || !data.text.trim() || data.text.length > 4000) return
    selection.value = {
      text: data.text,
      section: typeof data.section === 'string' ? data.section : '未命名区域',
      x: typeof data.x === 'number' ? data.x : 0,
      y: typeof data.y === 'number' ? data.y : 0,
    }
    return
  }
  if (data.type !== 'cygnusx:report-preview') return
  if (data.status !== 200) { fail(typeof data.status === 'number' ? data.status : undefined); return }
  stopTimer()
  loading.value = false
}

function dismissSelection() { selection.value = null }

function openCopilot(prefillContent?: string) {
  const currentReport = report.value
  if (!currentReport) return
  sidebar.openReportCopilot(
    { reportId: currentReport.id, title: currentReport.title },
    prefillContent,
  )
}

function askAiAboutSelection() {
  const current = selection.value
  const currentReport = report.value
  if (!current || !currentReport) return
  const result = buildSelectionPrefill({
    title: currentReport.title,
    runId: currentReport.id,
    flowName: currentReport.flow_name,
    section: current.section,
    text: current.text,
  })
  if (result.truncated) message.warning('选中内容过长，已自动截断')
  openCopilot(result.content)
  selection.value = null
}

function openReportSection(section: string) {
  if (!preview.value || !frame.value?.contentWindow || section.length > 80) return
  frame.value.contentWindow.postMessage({
    type: 'cygnusx:report-section',
    reportId: report.value?.id,
    channel: preview.value.channel,
    section,
  }, '*')
}

async function download() {
  const currentReport = report.value
  const file = primary.value
  if (!currentReport || !file || downloading.value) return
  downloading.value = true
  try { await downloadReportFile(currentReport, file.id) }
  catch { message.error('报告下载失败，文件可能已不可用。') }
  finally { downloading.value = false }
}

async function toggleStar() {
  const currentReport = report.value
  const current = epoch
  if (!currentReport || starring.value) return
  starring.value = true
  try {
    const result = await reportApi.toggleStar(currentReport.id, !currentReport.is_starred)
    if (current === epoch) report.value = result.data
  } catch { message.error('收藏操作失败，请重试。') }
  finally { starring.value = false }
}

function openWindow() {
  const url = preview.value?.url
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

function authCleared() {
  ++epoch
  stopTimer()
  sidebar.closeReportCopilot()
  preview.value = null
  report.value = null
  loading.value = false
  error.value = '登录状态已失效，请重新登录后查看报告。'
}

function onStorage(event: StorageEvent) {
  if (event.key === null || (event.key === 'access_token' && !event.newValue)) authCleared()
}

watch(() => route.params.reportId, loadReport, { immediate: true })
window.addEventListener('message', onPreviewMessage)
window.addEventListener('storage', onStorage)
window.addEventListener(REPORT_PREVIEW_AUTH_CLEARED, authCleared)
onMounted(() => sidebar.setReportSectionHandler(openReportSection))
onBeforeUnmount(() => {
  ++epoch
  stopTimer()
  sidebar.setReportSectionHandler(null)
  window.removeEventListener('message', onPreviewMessage)
  window.removeEventListener('storage', onStorage)
  window.removeEventListener(REPORT_PREVIEW_AUTH_CLEARED, authCleared)
})
</script>

<template>
  <div class="report-viewer">
    <header class="report-header">
      <div class="report-header-left">
        <button type="button" class="report-back" @click="router.push({ name: 'reports' })">
          <NIcon :size="15" :component="ArrowBackOutline" />
          <span>报告中心</span>
        </button>
        <div class="report-title-group">
          <div class="report-title-row">
            <h1 class="report-title">{{ titleParts.main }}</h1>
            <button v-if="titleParts.id" type="button" class="report-id-chip"
              :title="`${titleParts.id}（点击复制）`" @click="copyProjectId">
              {{ titleParts.id }}
            </button>
          </div>
          <div v-if="report" class="report-meta-row">
            <span class="report-badge" :class="`report-badge--${report.status}`">
              {{ statusLabels[report.status] }}
            </span>
            <span v-if="report.source_kind === 'external'" class="report-badge report-badge--delivery">外部交付</span>
            <span class="report-badge report-badge--flow">{{ report.flow_name }} {{ report.flow_version }}</span>
            <span v-if="report.report_kind === 'reproducibility'" class="report-badge report-badge--flow"
              :title="report.template_version || undefined">
              执行证据报告 v{{ report.version || 1 }}
            </span>
            <time class="report-time">{{ generatedAt }}</time>
          </div>
        </div>
      </div>
      <div v-if="report" class="report-header-actions">
        <NTooltip placement="bottom" :delay="300">
          <template #trigger>
            <NButton quaternary circle class="report-action-btn" @click="openWindow">
              <template #icon><NIcon :component="OpenOutline" /></template>
              <span class="sr-only">新窗口打开</span>
            </NButton>
          </template>
          新窗口打开
        </NTooltip>
        <NTooltip placement="bottom" :delay="300">
          <template #trigger>
            <NButton quaternary circle class="report-action-btn" :loading="starring" @click="toggleStar">
              <template #icon><NIcon :component="report.is_starred ? Star : StarOutline" /></template>
              <span class="sr-only">{{ report.is_starred ? '取消收藏' : '收藏' }}</span>
            </NButton>
          </template>
          {{ report.is_starred ? '取消收藏' : '收藏' }}
        </NTooltip>
        <NTooltip v-if="primary" placement="bottom" :delay="300">
          <template #trigger>
            <NButton quaternary circle class="report-action-btn" :loading="downloading" @click="download">
              <template #icon><NIcon :component="DownloadOutline" /></template>
              <span class="sr-only">下载</span>
            </NButton>
          </template>
          下载
        </NTooltip>
      </div>
    </header>
    <NAlert v-if="report?.report_kind === 'reproducibility'" type="warning">
      {{ report.evidence_partial ? '证据不完整，请查看报告缺口。' : '仅限已记录的证据范围。' }}复现验证尚未执行（not_run）。
    </NAlert>
    <div class="viewer-content">
      <div class="viewer-frame-shell">
      <NAlert v-if="error" class="viewer-error" type="error" title="报告暂不可预览" data-testid="preview-error">
        {{ error }}
        <NSpace class="error-actions">
          <NButton secondary @click="loadReport"><template #icon><NIcon :component="RefreshOutline" /></template>重试</NButton>
          <NButton v-if="primary" :loading="downloading" @click="download">下载查看</NButton>
        </NSpace>
      </NAlert>
      <div v-if="loading" class="viewer-loading" role="status"><NSpin size="large" /><span>正在加载报告…</span></div>
      <iframe v-if="preview" ref="frame" :key="preview.channel" :src="preview.url"
        :title="report?.title || '报告预览'" sandbox="allow-scripts" referrerpolicy="no-referrer"
        class="report-frame" @error="fail()" />
      <div v-if="selection" class="selection-popover" :style="selectionButtonStyle" data-testid="selection-ask-ai">
        <NButton size="small" type="primary" round @click="askAiAboutSelection">
          <template #icon><NIcon :component="SparklesOutline" /></template>问 AI
        </NButton>
        <span v-if="selectionTruncated" class="selection-warn" title="选中内容过长，已自动截断">⚠</span>
        <button class="selection-close" aria-label="关闭" @click="dismissSelection">×</button>
      </div>
      <NButton v-if="report" class="copilot-placeholder" round @click="openCopilot()">
        <template #icon><NIcon :component="SparklesOutline" /></template>AI 解读
      </NButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.report-viewer { display: flex; flex-direction: column; gap: 8px; min-height: calc(100vh - 120px); }

/* ===== 报告详情页头部：左区（返回链接 + 两行式标题组）/ 右区（icon 操作）===== */
.report-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 64px; padding: 8px 0; }
.report-header-left { display: flex; align-items: center; gap: 16px; min-width: 0; flex: 1 1 auto; }
.report-back {
  display: inline-flex; align-items: center; gap: 4px; flex: 0 0 auto;
  padding: 4px 8px 4px 0; border: 0; background: transparent; cursor: pointer;
  color: var(--text-secondary); font-size: 14px; line-height: 1.5; white-space: nowrap;
  transition: color 200ms ease;
}
.report-back:hover { color: var(--brand-primary); }
.report-title-group { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.report-title-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
.report-title { margin: 0; color: var(--text-primary); font-size: 20px; font-weight: 600; line-height: 1.4; }
.report-id-chip {
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px; line-height: 1.5; padding: 2px 8px; border-radius: 6px;
  background: rgba(0, 0, 0, 0.04); border: 1px solid rgba(0, 0, 0, 0.08);
  color: var(--text-primary); cursor: pointer;
  max-width: min(340px, 100%); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  transition: background-color 200ms ease;
}
.report-id-chip:hover { background: rgba(0, 0, 0, 0.07); }
.report-meta-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
.report-badge {
  display: inline-flex; align-items: center; white-space: nowrap;
  font-size: 12px; font-weight: 500; line-height: 1.5; padding: 1px 8px; border-radius: 999px;
}
/* 语义色文字均按浅色底 WCAG AA（≥4.5:1）加深取值 */
.report-badge--completed { color: #237804; background: rgba(82, 196, 26, 0.1); }
.report-badge--generating { color: #0958d9; background: rgba(9, 88, 217, 0.08); }
.report-badge--failed { color: #cf1322; background: rgba(207, 19, 34, 0.08); }
.report-badge--expired { color: #595959; background: rgba(0, 0, 0, 0.06); }
.report-badge--delivery { color: #1a5fd4; border: 1px solid #1e6fff; background: transparent; border-radius: 6px; }
.report-badge--flow { color: #595959; background: rgba(0, 0, 0, 0.04); border: 1px solid rgba(0, 0, 0, 0.06); border-radius: 6px; font-weight: 400; }
.report-time { color: #767676; font-size: 12px; white-space: nowrap; }
.report-header-actions { display: flex; align-items: center; gap: 4px; flex: 0 0 auto; }
.report-action-btn {
  --n-color-hover: rgba(0, 0, 0, 0.04);
  --n-color-pressed: rgba(0, 0, 0, 0.08);
  --n-color-focus: rgba(0, 0, 0, 0.04);
}
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}
@media (max-width: 768px) {
  .report-header { flex-direction: column; align-items: stretch; gap: 8px; }
  .report-header-actions { justify-content: flex-end; }
}
@media (prefers-reduced-motion: reduce) {
  .report-back, .report-id-chip { transition: none; }
}
.viewer-content { display:flex; flex:1; min-height:70vh; border:1px solid var(--neutral-border); border-radius:12px; overflow:hidden; background:var(--neutral-card); }
.viewer-frame-shell { position:relative; flex:1; min-width:0; overflow:auto; display:flex; flex-direction:column; }
.report-frame { display: block; flex: 1; width: 100%; min-height: max(70vh, calc(100vh - 180px)); border: 0; background: white; }
.viewer-loading { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 16px; background: var(--neutral-card); z-index: 1; }
.viewer-error { margin: 24px; width: auto; }
.error-actions { margin-top: 16px; }
.copilot-placeholder { position: absolute; right: 20px; bottom: 20px; z-index: 2; }
.selection-popover { position: absolute; z-index: 3; display: flex; align-items: center; gap: 6px; }
.selection-warn { color: var(--warning-color, #f0a020); font-size: 14px; }
.selection-close { border: 0; background: transparent; cursor: pointer; color: var(--neutral-text-2); font-size: 14px; padding: 2px; }
@media (max-width: 768px) { .report-viewer { min-height: calc(100vh - 96px); } .viewer-error { margin: 16px; } }
</style>
