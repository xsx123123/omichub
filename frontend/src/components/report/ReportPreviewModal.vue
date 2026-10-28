<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Report } from '@/types/report'
import { reportApi, downloadReportFile } from '@/api/report'
import {
  NModal, NButton, NSpace, NSpin, NIcon, NAlert, useMessage,
} from 'naive-ui'
import {
  DownloadOutline, ExpandOutline, ContractOutline,
  CloseOutline,
} from '@vicons/ionicons5'

const props = defineProps<{
  report: Report | null
}>()

const emit = defineEmits<{
  close: []
}>()

const message = useMessage()
let requestEpoch = 0
const htmlContent = ref('')
const loading = ref(false)
const isFullscreen = ref(false)
const deliveryLoading = ref(false)

async function loadPreview() {
  if (!props.report) return
  const token = ++requestEpoch
  const reportId = props.report.id
  htmlContent.value = ''
  loading.value = true
  try {
    const res = await reportApi.previewReport(reportId)
    if (token === requestEpoch) htmlContent.value = res.data
  } catch {
    if (token === requestEpoch) htmlContent.value = '<p style="color:var(--neutral-text-3, #999);text-align:center;padding:40px 0;">报告加载失败，请尝试下载查看</p>'
  } finally {
    if (token === requestEpoch) loading.value = false
  }
}

async function handleDownload() {
  if (!props.report) return
  const report = props.report
  const primary = report.files.find(f => f.is_primary) || report.files[0]
  if (!primary) return
  try { await downloadReportFile(report, primary.id) }
  catch { message.error('报告下载失败，文件可能已不可用。') }
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

async function buildDelivery() {
  if (!props.report || deliveryLoading.value) return
  deliveryLoading.value = true
  try {
    await reportApi.buildDeliveryPackage(props.report.id)
    message.success('科研交付包已生成，请在报告中心下载。')
  } catch {
    message.error('科研交付包生成失败，请确认该任务已有执行证据报告。')
  } finally {
    deliveryLoading.value = false
  }
}

watch(() => props.report, (report) => {
  if (report) {
    loadPreview()
  } else {
    ++requestEpoch
    htmlContent.value = ''
    loading.value = false
    isFullscreen.value = false
  }
}, { immediate: true })
</script>

<template>
  <NModal
    :show="!!report"
    :title="report?.title || '报告预览'"
    preset="card"
    :style="{
      width: isFullscreen ? '100vw' : '90vw',
      maxWidth: isFullscreen ? '100vw' : '1200px',
      height: isFullscreen ? '100vh' : 'auto',
      margin: isFullscreen ? 0 : 'auto',
      top: isFullscreen ? 0 : '5vh',
    }"
    :closable="true"
    :mask-closable="false"
    @close="emit('close')"
    @update:show="(v: boolean) => { if (!v) emit('close') }"
  >
    <template #header-extra>
      <NSpace :size="8">
        <NButton size="small" @click="handleDownload">
          <template #icon>
            <NIcon :component="DownloadOutline" />
          </template>
          下载
        </NButton>
        <NButton
          v-if="report?.report_kind !== 'delivery' && report?.task_id"
          size="small"
          :loading="deliveryLoading"
          @click="buildDelivery"
        >
          生成交付包
        </NButton>
        <NButton size="small" @click="toggleFullscreen">
          <template #icon>
            <NIcon :component="isFullscreen ? ContractOutline : ExpandOutline" />
          </template>
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </NButton>
        <NButton size="small" quaternary circle @click="emit('close')">
          <template #icon>
            <NIcon :component="CloseOutline" />
          </template>
        </NButton>
      </NSpace>
    </template>

    <NAlert v-if="report?.report_kind === 'reproducibility'" type="warning" style="margin-bottom: 12px">
      执行证据报告 · 版本 {{ report.version || 1 }} · {{ report.template_version }}。
      {{ report.evidence_partial ? '证据不完整，请查看 M8 的缺口和限制。' : '仅限已记录的证据范围。' }}
      复现验证尚未执行（not_run）。
    </NAlert>
    <NSpin :show="loading" style="width: 100%;">
      <div
        class="preview-container"
        :style="{ height: isFullscreen ? 'calc(100vh - 120px)' : '70vh' }"
      >
        <iframe
          v-if="htmlContent"
          :srcdoc="htmlContent"
          :title="report?.title || '报告预览'"
          class="preview-iframe"
          sandbox=""
        />
      </div>
    </NSpin>
  </NModal>
</template>

<style scoped>
.preview-container {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: var(--neutral-card);
}
.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
</style>
