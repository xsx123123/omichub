<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NIcon, NSpace, NSpin, useMessage } from 'naive-ui'
import { ArrowBackOutline, DownloadOutline, OpenOutline, RefreshOutline, SparklesOutline, Star, StarOutline } from '@vicons/ionicons5'
import PageHeader from '@/components/PageHeader.vue'
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
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { hour12: false })
})
const statusLabels = { completed: '已完成', generating: '生成中', failed: '生成失败', expired: '已过期' }
const headerSubtitle = computed(() => {
  const current = report.value
  if (!current) return '结果报告中心'
  const parts = [statusLabels[current.status]]
  if (current.source_kind === 'external') parts.push('外部交付')
  parts.push(`${current.flow_name} ${current.flow_version}`, generatedAt.value)
  if (current.report_kind === 'reproducibility') {
    parts.push(`执行证据报告 · v${current.version || 1} · ${current.template_version}`)
  }
  return parts.filter(Boolean).join(' · ')
})
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
    <PageHeader compact :title="report?.title || '报告查看'" :subtitle="headerSubtitle">
      <template #actions>
        <NSpace :size="8">
          <NButton secondary @click="router.push({ name: 'reports' })">
            <template #icon><NIcon :component="ArrowBackOutline" /></template>报告中心
          </NButton>
          <NButton v-if="report" secondary @click="openWindow">
            <template #icon><NIcon :component="OpenOutline" /></template>新窗口打开
          </NButton>
          <NButton v-if="report" :loading="starring" @click="toggleStar">
            <template #icon><NIcon :component="report.is_starred ? Star : StarOutline" /></template>
            {{ report.is_starred ? '取消收藏' : '收藏' }}
          </NButton>
          <NButton v-if="primary" :loading="downloading" @click="download">
            <template #icon><NIcon :component="DownloadOutline" /></template>下载
          </NButton>
        </NSpace>
      </template>
    </PageHeader>
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
/* 报告查看页专属：页头操作区在左、标题与元信息在右（§4.1 compact 变体的报告查看页约定） */
.report-viewer :deep(.page-header-actions) { order: -1; }
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
