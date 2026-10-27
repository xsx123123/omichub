<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NAlert, NButton, NDataTable, NEmpty, NSpin, NTabPane, NTabs } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { TablePreviewSizeError } from '@/api/artifactPreview'
import {
  decodeTableText, isNumericColumn, parseArtifactTable,
  TABLE_CONFIRM_BYTES, TABLE_PREVIEW_ROWS,
  type ArtifactSheetPreview,
} from '@/utils/artifactTablePreview'

const props = defineProps<{
  fileName: string
  size?: number
  loadBlob: (confirmed: boolean) => Promise<Blob>
}>()
const loading = ref(false)
const error = ref('')
const sheets = ref<ArtifactSheetPreview[]>([])
const activeSheet = ref(0)
const fallback = ref<string | null>(null)
const needsConfirmation = ref(false)
const fileSize = ref(0)
const exactSize = ref(true)
let pendingBlob: Blob | undefined
let generation = 0

const currentSheet = computed(() => sheets.value[activeSheet.value])
type TableRow = Record<string, string | number>
const columns = computed<DataTableColumns<TableRow>>(() => {
  const data = currentSheet.value
  if (!data) return []
  return data.header.map((label, index) => {
    const longest = Math.max(label.length, ...data.rows.map((row) => row[index]?.length || 0))
    return {
      title: label,
      key: `c${index}`,
      width: Math.min(240, Math.max(100, longest * 9 + 28)),
      align: isNumericColumn(data.rows, index) ? 'right' : 'left',
      ellipsis: { tooltip: true },
    }
  })
})
const rows = computed<TableRow[]>(() => currentSheet.value?.rows.map((row, index) =>
  Object.fromEntries([['__index', index], ...row.map((cell, i) => [`c${i}`, cell])])) || [])
const scrollWidth = computed(() => columns.value.reduce((sum, column) => sum + Number(column.width), 0))

async function load(confirmed = false) {
  const run = ++generation
  loading.value = false
  error.value = ''
  sheets.value = []
  fallback.value = null
  activeSheet.value = 0
  fileSize.value = pendingBlob?.size ?? props.size ?? 0
  exactSize.value = true
  needsConfirmation.value = !confirmed && fileSize.value > TABLE_CONFIRM_BYTES
  if (needsConfirmation.value) return
  loading.value = true
  try {
    const blob = pendingBlob ?? await props.loadBlob(confirmed)
    if (run !== generation) return
    fileSize.value = blob.size
    // Also protect artifacts whose manifest has no size (or a stale size).
    if (!confirmed && blob.size > TABLE_CONFIRM_BYTES) {
      pendingBlob = blob
      needsConfirmation.value = true
      return
    }
    pendingBlob = undefined
    const buffer = await blob.arrayBuffer()
    const ext = props.fileName.split('.').pop()?.toLowerCase() || ''
    try {
      const parsed = await parseArtifactTable(buffer, ext)
      if (run === generation) sheets.value = parsed
    } catch {
      // A broken table must still be readable through the existing text fallback.
      let text: string
      try { text = decodeTableText(buffer) } catch { text = new TextDecoder().decode(buffer) }
      if (run === generation) fallback.value = text.slice(0, 200_000)
    }
  } catch (cause) {
    if (run !== generation) return
    if (cause instanceof TablePreviewSizeError) {
      fileSize.value = cause.size
      exactSize.value = cause.exact
      needsConfirmation.value = true
    } else error.value = '预览加载失败，请尝试下载后查看'
  } finally {
    if (run === generation) loading.value = false
  }
}

watch(() => props.fileName, () => {
  pendingBlob = undefined
  void load()
}, { immediate: true })
onBeforeUnmount(() => { generation++; pendingBlob = undefined })
</script>

<template>
  <section class="artifact-table-preview" aria-label="表格预览" aria-live="polite">
    <NAlert v-if="needsConfirmation" type="info" :show-icon="false">
      {{ exactSize ? `该产物大小为 ${(fileSize / 1024 / 1024).toFixed(2)} MB，超过 5 MB` : '该产物超过 5 MB（服务器未提供总大小）' }}，加载可能需要一些时间。
      <div class="artifact-table-preview__confirm">
        <NButton size="small" type="primary" @click="load(true)">确认加载</NButton>
        <span>也可关闭预览，下载查看完整数据</span>
      </div>
    </NAlert>
    <div v-else-if="loading" class="artifact-table-preview__status"><NSpin size="small" />正在加载预览…</div>
    <div v-else-if="error" class="artifact-table-preview__status">{{ error }}</div>
    <pre v-else-if="fallback !== null" class="artifact-code-preview">{{ fallback }}</pre>
    <template v-else-if="currentSheet">
      <NTabs v-if="sheets.length > 1" v-model:value="activeSheet" type="line" size="small" class="artifact-table-preview__tabs">
        <NTabPane v-for="(item, index) in sheets" :key="index" :name="index" :tab="item.name" />
      </NTabs>
      <div class="artifact-table-preview__meta">
        <strong>{{ currentSheet.name }}</strong>
        <span>{{ currentSheet.header.length }} 列 · {{ currentSheet.totalRows }} 行</span>
      </div>
      <NEmpty v-if="!currentSheet.totalRows" description="该产物为空表格" class="artifact-table-preview__empty" />
      <NDataTable
        v-else
        :columns="columns" :data="rows" :row-key="(row: TableRow) => row.__index"
        :max-height="480" :scroll-x="scrollWidth" :single-line="false"
        size="small" striped
      />
      <p class="artifact-table-preview__hint">
        共 {{ currentSheet.totalRows }} 行，{{ currentSheet.totalRows > TABLE_PREVIEW_ROWS ? `预览前 ${TABLE_PREVIEW_ROWS} 行，` : '' }}下载查看完整数据
      </p>
    </template>
  </section>
</template>

<style scoped>
.artifact-table-preview { width: 100%; min-width: 0; }
.artifact-table-preview__status { display: flex; align-items: center; justify-content: center; gap: 12px; min-height: 160px; color: var(--text-secondary); }
.artifact-table-preview__confirm { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 12px; }
.artifact-table-preview__tabs { margin-bottom: 12px; }
.artifact-table-preview__meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; margin-bottom: 12px; color: var(--text-secondary); font-size: 12px; }
.artifact-table-preview__meta strong { color: var(--text-primary); }
.artifact-table-preview__empty { padding: 48px 0; }
.artifact-table-preview__hint { margin: 12px 0 0; color: var(--text-secondary); font-size: 12px; }
/* Keep the component library's table states inside the platform's card styles. */
.artifact-table-preview :deep(.n-data-table .n-data-table-th) { font-weight: 600; color: var(--n-th-text-color); background-color: var(--n-merged-th-color); }
.artifact-table-preview :deep(.n-data-table .n-data-table-td) { color: var(--n-td-text-color); background-color: var(--n-merged-td-color); }
.artifact-table-preview :deep(.n-data-table .n-data-table-tr--striped .n-data-table-td) { background-color: var(--n-merged-td-color-striped); }
.artifact-table-preview :deep(.n-data-table .n-data-table-tr:hover .n-data-table-td) { background-color: var(--n-merged-td-color-hover); }
.artifact-code-preview { max-height: 55vh; overflow: auto; padding: 12px; border: 1px solid var(--stardust-border-soft); border-radius: var(--radius-md, 8px); background: var(--bg-card); color: var(--text-primary); font-family: var(--font-mono, monospace); font-size: 12px; white-space: pre; }
</style>
