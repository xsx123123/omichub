<script setup lang="ts">
import DatasetWorkspace from '@/components/research/DatasetWorkspace.vue'
import type { FlowDefinition } from '@/types'
import apiClient from '@/api/client'
import { useApi } from '@/composables/useApi'
import AppLoading from '@/components/AppLoading.vue'
import PageHeader from '@/components/PageHeader.vue'
import { NButton, NIcon, NModal } from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Component } from 'vue'
import { PENDING_WORKFLOWS } from '@/config/workflows'
import {
  AnalyticsOutline,
  ArrowForwardOutline,
  BeakerOutline,
  ClipboardOutline,
  CodeSlashOutline,
  DocumentTextOutline,
  FlameOutline,
  FlaskOutline,
  GlobeOutline,
  InformationCircleOutline,
  LogoGithub,
  MagnetOutline,
  FolderOutline,
  SettingsOutline,
  StatsChartOutline,
  LayersOutline,
  GitBranchOutline,
} from '@vicons/ionicons5'

interface Pipeline {
  id: string
  name: string
  desc: string
  icon: Component | string
  tags: string[]
  version: string
  githubUrl: string | null
  isReady: boolean
  status?: string
  badge?: string
  docsUrl: string | null
}

const route = useRoute()
const router = useRouter()
const flowFrameInfoVisible = ref(false)

const activeType = computed(() => (route.query.type as string) || '')

const {
  data: flows,
  loading,
  error,
  execute: fetchFlows,
} = useApi<FlowDefinition[]>(
  async () => {
    const res = await apiClient.get<{ items: FlowDefinition[]; total: number }>('/flows')
    return res.data.items
  },
  { initialData: [] },
)

const typeLabels: Record<string, string> = {
  'rna-seq': 'RNA-seq 分析',
  'atac-seq': 'ATAC-seq 分析',
  'sc-rna': '单细胞分析',
  'spatial': '空间转录组',
  'chip-seq': 'ChIP-seq 分析',
  'hic': 'Hi-C 三维基因组',
  'methylation': '甲基化分析',
  '16s-amplicon': '扩增子分析',
  'metagenomics': '宏基因组分析',
  'proteomics': '蛋白质组分析',
  'metabolomics': '代谢组分析',
  'multi-omics': '多组学联合',
  'denovo-assembly': '基因组组装',
  'wgs': '全基因组测序',
  'wes': '全外显子测序',
  'gwas': 'GWAS 分析',
}

/** 流程图标兜底映射（兼容旧 YAML 中 icon 为字符串 key 的情况） */
const FALLBACK_MAP: Record<string, Component> = {
  rna: BeakerOutline,
  atac: FlaskOutline,
  scrna: AnalyticsOutline,
  chip: MagnetOutline,
  wgs: FolderOutline,
  wes: FolderOutline,
  jbrowse: GlobeOutline,
  proteomics: FlaskOutline,
  metabolomics: FlaskOutline,
  default: StatsChartOutline,
}

/** 将历史流程元数据中的常见 Emoji 图标迁移到稳定的矢量图标；未知自定义图标仍原样展示。 */
const LEGACY_ICON_MAP: Record<string, Component> = {
  '🧬': BeakerOutline,
  '🧪': FlaskOutline,
  '🔬': AnalyticsOutline,
  '🧲': MagnetOutline,
  '🗂️': FolderOutline,
  '🌐': GlobeOutline,
  '🧫': FlaskOutline,
  '⚗️': FlaskOutline,
  '⚙️': SettingsOutline,
}

/** 按 category 动态主题色 key */
function flowIcon(flow: FlowDefinition): Component | string {
  const icon = flow.icon
  if (icon && icon.trim().length > 0) {
    if (LEGACY_ICON_MAP[icon]) return LEGACY_ICON_MAP[icon]
    if (/[^\x00-\x7F]/.test(icon)) return icon
    return FALLBACK_MAP[icon.toLowerCase()] || FALLBACK_MAP[flow.category] || FALLBACK_MAP.default
  }
  return FALLBACK_MAP[flow.category] || FALLBACK_MAP.default
}

function isGithubUrl(url?: string | null): boolean {
  return !!url && url.includes('github.com')
}

function resolveGithubUrl(flow: FlowDefinition): string | null {
  if (isGithubUrl(flow.github_url)) return flow.github_url as string
  if (isGithubUrl(flow.docs_url)) return flow.docs_url as string
  return null
}

const pipelines = computed<Pipeline[]>(() => {
  const apiFlows = (flows.value || []).map((f) => ({
    id: f.id,
    name: f.name,
    desc: f.description,
    icon: flowIcon(f),
    tags: f.tags?.length ? f.tags : [f.category],
    version: f.version,
    githubUrl: resolveGithubUrl(f),
    isReady: true,
    status: f.status,
    badge: f.badge,
    docsUrl: f.docs_url || null,
  }))
  const apiIds = new Set(apiFlows.map((flow) => flow.id))
  const pendingFlows = PENDING_WORKFLOWS
    .filter((flow) => !apiIds.has(flow.id))
    .map((flow) => ({
      id: flow.id,
      name: flow.name,
      desc: flow.description,
      icon: flowIcon({ ...flow, icon: 'default' }),
      tags: flow.tags,
      version: flow.version,
      githubUrl: null,
      isReady: false,
      status: flow.status,
      badge: flow.badge,
      docsUrl: null,
    }))
  return [...apiFlows, ...pendingFlows]
})

const filteredPipelines = computed(() => {
  if (!activeType.value) return pipelines.value
  const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')
  const target = norm(activeType.value)
  return pipelines.value.filter((p) => {
    const key = norm(`${p.id} ${p.tags.join(' ')}`)
    return key.includes(target)
  })
})

const featuredPipeline = computed(() =>
  filteredPipelines.value.find((p) => p.id === 'rna_seq' && p.isReady) ||
  filteredPipelines.value.find((p) => p.id.includes('rna') && p.isReady),
)

const gridPipelines = computed(() => {
  if (activeType.value) return filteredPipelines.value
  return filteredPipelines.value.filter((p) => p.id !== featuredPipeline.value?.id)
})

function handleCardClick(p: Pipeline) {
  if (!canStart(p)) return
  router.push({ name: 'flow-submit', params: { flowId: p.id } })
}

function canStart(p: Pipeline): boolean {
  return p.isReady && p.status !== 'UNDER_REVIEW' && p.badge !== '专家审核中'
}

function flowStatus(p: Pipeline): string {
  return canStart(p) ? '可开始' : p.badge || '暂未开放'
}

function displayVersion(version: string): string {
  return version.startsWith('v') ? version : `v${version}`
}

watch(() => route.query.type, fetchFlows)
onMounted(fetchFlows)
</script>

<template>
  <div class="flows-page" role="main" aria-label="分析流程中心">
    <DatasetWorkspace v-if="typeof route.query.dataset === 'string'" :project-id="typeof route.query.project === 'string' ? route.query.project : null" :dataset-id="route.query.dataset" :version-id="typeof route.query.version === 'string' ? route.query.version : undefined" analysis-mode />
    <PageHeader
      class="animate-fade-in-up"
      :title="activeType ? typeLabels[activeType] || '分析流程' : '分析中心'"
      :subtitle="activeType ? '查看当前分类的流程与开放状态' : '选择适合研究需求的分析流程，快速启动多组学分析'"
    >
      <template #actions>
        <div class="flows-header-actions">
        <NButton v-if="activeType" class="header-btn-secondary" @click="router.push('/flows')">
          查看全部流程
        </NButton>
        <NButton class="header-btn-secondary" tag="a" href="https://github.com/xsx123123/omichub" target="_blank" rel="noopener noreferrer">
          <template #icon><component :is="CodeSlashOutline" /></template>
          GitHub 开源代码
        </NButton>
        <NButton class="header-btn-secondary" tag="a" href="https://github.com/xsx123123/FlowFrame#readme" target="_blank" rel="noopener noreferrer">
          <template #icon><component :is="DocumentTextOutline" /></template>
          开发者文档
        </NButton>
        </div>
      </template>
    </PageHeader>

    <button class="flowframe-card focus-ring" type="button" @click="flowFrameInfoVisible = true">
      <span class="flowframe-icon" aria-hidden="true">
        <NIcon :component="InformationCircleOutline" :size="22" />
      </span>
      <span class="flowframe-copy">
        <span class="flowframe-eyebrow">流程架构说明</span>
        <strong>所有分析流程均基于 FlowFrame 构建</strong>
        <span class="flowframe-summary">统一的声明式配置、样本表规范与可复现执行环境，让不同组学流程拥有一致的使用体验。</span>
      </span>
      <NIcon class="flowframe-arrow" :component="ArrowForwardOutline" :size="20" aria-hidden="true" />
    </button>

    <!-- 加载态 -->
    <div v-if="loading && !flows?.length" class="flows-loading">
      <AppLoading text="加载分析流程..." />
    </div>
    <div v-else-if="error" class="flows-empty" role="alert">
      <p>流程列表加载失败：{{ error }}</p>
      <NButton secondary @click="fetchFlows()">重试</NButton>
    </div>

    <template v-else-if="pipelines.length">
      <!-- 推荐流程 -->
      <section v-if="!activeType && featuredPipeline" class="featured-section animate-fade-in-up delay-100">
        <h2 class="section-label">
          <NIcon :component="FlameOutline" class="section-icon" aria-hidden="true" />
          推荐流程
        </h2>
        <div class="hero-card">
          <div class="hero-inner">
            <div class="hero-icon">
              <NIcon v-if="typeof featuredPipeline.icon !== 'string'" :component="featuredPipeline.icon" :size="22" />
              <span v-else>{{ featuredPipeline.icon }}</span>
            </div>
            <div class="hero-body">
              <div class="hero-title-row">
                <h3 class="hero-title">{{ featuredPipeline.name }}</h3>
                <span class="recommended-badge">推荐</span>
              </div>
              <span class="flow-status">{{ flowStatus(featuredPipeline) }}</span>
              <span class="flow-version">{{ displayVersion(featuredPipeline.version) }}</span>
            </div>
            <div class="hero-description">
              <p class="hero-desc">{{ featuredPipeline.desc }}</p>
              <div class="flow-tags"><span v-for="tag in featuredPipeline.tags.slice(0, 3)" :key="tag" class="flow-tag">{{ tag }}</span><span v-if="featuredPipeline.tags.length > 3" class="flow-tag">+{{ featuredPipeline.tags.length - 3 }}</span></div>
            </div>
            <div class="hero-actions">
              <NButton type="primary" @click="handleCardClick(featuredPipeline)">开始分析</NButton>
              <NButton v-if="featuredPipeline.docsUrl || featuredPipeline.githubUrl" tag="a" :href="featuredPipeline.docsUrl || featuredPipeline.githubUrl || undefined" target="_blank" rel="noopener noreferrer" secondary>了解流程</NButton>
              <NButton v-else secondary @click="handleCardClick(featuredPipeline)">查看流程配置</NButton>
            </div>
          </div>
        </div>
      </section>

      <!-- 全部流程 -->
      <section class="all-flows-section animate-fade-in-up delay-200">
        <h2 class="section-label">
          <NIcon :component="ClipboardOutline" class="section-icon" aria-hidden="true" />
          {{ activeType ? '筛选结果' : '全部流程' }}
        </h2>

        <div v-if="!gridPipelines.length" class="flows-empty flows-filter-empty">
          <p>该分类暂无匹配流程</p>
          <NButton secondary @click="router.push('/flows')">查看全部流程</NButton>
        </div>
        <div v-else v-animate-list class="flow-grid">
          <article v-for="p in gridPipelines" :key="p.id" class="flow-card">
            <div class="flow-card-header">
              <div class="flow-icon">
                <NIcon v-if="typeof p.icon !== 'string'" :component="p.icon" :size="20" />
                <span v-else>{{ p.icon }}</span>
              </div>
              <h3 class="flow-title">{{ p.name }}</h3>
              <span class="flow-status" :class="{ 'flow-status--review': !canStart(p) }">{{ flowStatus(p) }}</span>
            </div>
            <p class="flow-desc" :title="p.desc">{{ p.desc }}</p>
            <div class="flow-metadata">
              <span class="flow-version">{{ displayVersion(p.version) }}</span>
              <div class="flow-tags"><span v-for="tag in p.tags.slice(0, 3)" :key="tag" class="flow-tag">{{ tag }}</span><span v-if="p.tags.length > 3" class="flow-tag">+{{ p.tags.length - 3 }}</span></div>
            </div>
            <div class="flow-actions">
              <NButton v-if="canStart(p)" type="primary" size="small" @click="handleCardClick(p)">开始分析</NButton>
              <NButton v-if="p.docsUrl || p.githubUrl" tag="a" :href="p.docsUrl || p.githubUrl || undefined" target="_blank" rel="noopener noreferrer" text>了解流程</NButton>
              <NButton v-else-if="canStart(p)" text @click="handleCardClick(p)">查看配置</NButton>
              <span v-else class="flow-unavailable">{{ p.status === 'UNDER_REVIEW' ? '审核完成后开放' : '暂未开放' }}</span>
            </div>
          </article>
        </div>
      </section>
    </template>

    <!-- 空状态 -->
    <div v-else-if="!loading && !pipelines.length" class="flows-empty">
      <NIcon :size="64" class="text-gray-300 mb-4"><FlaskOutline /></NIcon>
      <p class="text-sm font-medium text-gray-500 mb-1">暂无分析流程</p>
      <p class="text-xs text-gray-400">请联系管理员配置流程 YAML 文件</p>
    </div>

    <NModal
      v-model:show="flowFrameInfoVisible"
      preset="card"
      title="FlowFrame 流程框架"
      :bordered="false"
      :style="{ width: 'min(840px, calc(100vw - 32px))', maxHeight: '85vh', overflowY: 'auto' }"
      aria-label="FlowFrame 流程框架说明"
    >
      <div class="flowframe-modal-content">
        <div class="flowframe-modal-intro">
          <span class="flowframe-modal-eyebrow">分析中心的流程基座</span>
          <p class="flowframe-modal-subtitle">标准化、可复现的科研分析工作流</p>
          <p class="flowframe-modal-lead">FlowFrame 是 CygnusX 分析中心采用的流程规范。每个流程以版本化 YAML 描述参数、样本表、比较组和执行映射，平台据此生成输入文件并提交到标准化运行环境。</p>
        </div>
        <div class="flowframe-points">
          <div class="flowframe-point">
            <span class="flowframe-point-index">01</span>
            <NIcon :component="LayersOutline" :size="22" aria-hidden="true" />
            <div><strong>声明式配置</strong><p>以版本化配置描述流程参数和输入契约。</p></div>
          </div>
          <div class="flowframe-point">
            <span class="flowframe-point-index">02</span>
            <NIcon :component="ClipboardOutline" :size="22" aria-hidden="true" />
            <div><strong>统一数据规范</strong><p>样本表、比较组和运行目录遵循统一契约。</p></div>
          </div>
          <div class="flowframe-point">
            <span class="flowframe-point-index">03</span>
            <NIcon :component="GitBranchOutline" :size="22" aria-hidden="true" />
            <div><strong>可复现执行</strong><p>流程版本随任务保存，由平台调度和监控执行。</p></div>
          </div>
        </div>
        <div class="flowframe-architecture">
          <strong>从流程定义到分析结果</strong>
          <ol>
            <li>流程配置</li><li>输入规范化</li><li>任务执行</li><li>结果产物</li>
          </ol>
        </div>
        <div class="flowframe-modal-actions">
          <NButton tag="a" href="https://github.com/xsx123123/FlowFrame" target="_blank" rel="noopener noreferrer" type="primary">
            <template #icon><NIcon :component="LogoGithub" /></template>
            查看 FlowFrame
          </NButton>
          <NButton tag="a" href="https://github.com/xsx123123/FlowFrame#readme" target="_blank" rel="noopener noreferrer" secondary>
            <template #icon><NIcon :component="DocumentTextOutline" /></template>
            阅读 README
          </NButton>
        </div>
      </div>
    </NModal>
  </div>
</template>

<style scoped>
.flows-page {
  padding: 0;
  min-height: 100%;
  background: var(--neutral-bg);
}

.flows-loading,
.flows-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
}

.flows-header-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.flowframe-card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 0 0 28px;
  padding: 16px 18px;
  border: 1px solid color-mix(in srgb, var(--brand-primary) 24%, var(--neutral-border));
  border-radius: var(--radius-card);
  background: color-mix(in srgb, var(--brand-primary-light) 52%, var(--neutral-card));
  color: var(--neutral-text-1);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.flowframe-card:hover {
  border-color: var(--brand-primary);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}

.flowframe-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  border-radius: 10px;
  color: var(--brand-primary);
  background: var(--neutral-card);
}

.flowframe-copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.flowframe-eyebrow {
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 600;
}

.flowframe-copy strong {
  font-size: 15px;
  font-weight: 600;
}

.flowframe-summary {
  color: var(--neutral-text-2);
  font-size: 13px;
  line-height: 1.45;
}

.flowframe-arrow {
  flex: 0 0 auto;
  color: var(--neutral-text-3);
  transition: transform 0.2s ease, color 0.2s ease;
}

.flowframe-card:hover .flowframe-arrow {
  color: var(--brand-primary);
  transform: translateX(3px);
}

.flowframe-modal-content {
  color: var(--neutral-text-2);
}

.flowframe-modal-intro {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--neutral-border);
}

.flowframe-modal-eyebrow {
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.flowframe-modal-lead {
  margin: 6px 0 0;
  color: var(--neutral-text-2);
  font-size: 14px;
  line-height: 22px;
}

.flowframe-points {
  display: grid;
  gap: 16px;
  padding: 20px 0 4px;
}

.flowframe-point {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.flowframe-point-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  border: 1px solid var(--neutral-border);
  border-radius: 8px;
  background: var(--neutral-hover);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.flowframe-point strong {
  color: var(--neutral-text-1);
  font-size: 16px;
  font-weight: 500;
  line-height: 24px;
}

.flowframe-point p {
  margin: 4px 0 0;
  color: var(--neutral-text-2);
  font-size: 13px;
  line-height: 20px;
}

.flowframe-modal-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--neutral-border);
}

.header-btn-secondary {
  --n-text-color: var(--neutral-text-2);
  --n-text-color-hover: var(--neutral-text-2);
  --n-border: 1px solid var(--neutral-border);
  --n-border-hover: 1px solid var(--neutral-border);
  --n-color: var(--neutral-card);
  --n-color-hover: var(--neutral-hover);
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  line-height: 26px;
  color: var(--neutral-text-1);
  margin: 0 0 16px;
}

.section-icon {
  font-size: 20px;
  color: var(--brand-primary);
}

.featured-section {
  margin-bottom: 32px;
}

/* Workflow catalog surface */
.hero-card, .flow-card { background: var(--neutral-card); border: 1px solid var(--neutral-border); border-radius: var(--radius-card); box-shadow: none; padding: 20px; transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; }
.hero-card { border-color: color-mix(in srgb, var(--brand-primary) 30%, var(--neutral-border)); }
.hero-card:hover, .flow-card:hover { border-color: color-mix(in srgb, var(--brand-primary) 45%, var(--neutral-border)); box-shadow: var(--shadow-card); }
.hero-inner { display: grid; grid-template-columns: 48px minmax(180px, 1fr) minmax(220px, 1.2fr) auto; align-items: center; gap: 18px; }
.hero-body, .hero-description { min-width: 0; }
.hero-icon, .flow-icon { background: var(--brand-primary-light); color: var(--brand-primary); border-radius: 10px; }
.hero-icon, .flow-icon { display: grid; place-items: center; flex: none; }
.hero-icon { width: 48px; height: 48px; }
.flow-icon { width: 40px; height: 40px; }
.hero-title-row { display: flex; align-items: center; gap: 8px; }
.hero-title { margin: 0; color: var(--neutral-text-1); font-size: 17px; }
.recommended-badge { display: inline-flex; padding: 2px 8px; border-radius: 999px; background: var(--brand-primary-light); color: var(--brand-primary); font-size: 12px; font-weight: 600; }
.hero-title-row { flex-wrap: wrap; }
.hero-title, .flow-title { white-space: normal; overflow: visible; overflow-wrap: anywhere; font-weight: 600; }
.hero-desc { margin: 0 0 10px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
.hero-desc, .flow-desc { color: var(--neutral-text-2); font-size: 13px; line-height: 1.55; }
.hero-actions { display: flex; flex-direction: column; gap: 8px; min-width: 116px; }
.flow-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  column-gap: 18px;
  row-gap: 18px;
}
.flow-card { display: flex; flex-direction: column; min-width: 0; }
.flow-card-header { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 10px; }
.flow-title { flex: 1; min-width: 140px; line-height: 1.45; }
.flow-title { margin: 0; color: var(--neutral-text-1); font-size: 15px; }
.flow-status { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px; background: var(--neutral-hover); color: var(--neutral-text-2); font-size: 12px; white-space: nowrap; }
.flow-status--review { color: var(--arco-warning); background: color-mix(in srgb, var(--arco-warning) 10%, var(--neutral-card)); }
.flow-desc { margin: 16px 0; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
.flow-metadata { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 8px; margin-top: auto; }
.flow-version { color: var(--neutral-text-2); font-size: 12px; white-space: nowrap; }
.flow-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.flow-tag { padding: 2px 8px; border-radius: 5px; font-size: 11px; }
.flow-tag { background: var(--neutral-hover); color: var(--neutral-text-2); }
.flow-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--neutral-border); }
.flow-unavailable { color: var(--neutral-text-2); font-size: 12px; }
.flowframe-points { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.flowframe-point { position: relative; flex-direction: column; gap: 8px; min-width: 0; padding: 16px; border: 1px solid var(--neutral-border); border-radius: var(--radius-card); }
.flowframe-point > .n-icon { color: var(--brand-primary); }
.flowframe-point-index { position: absolute; right: 14px; top: 14px; }
.flowframe-point strong { font-size: 14px; font-weight: 600; }
.flowframe-architecture { margin-top: 20px; padding: 18px; border-radius: var(--radius-card); background: var(--neutral-hover); color: var(--neutral-text-1); font-size: 13px; }
.flowframe-architecture ol { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; padding: 0; margin: 14px 0 0; list-style: none; counter-reset: stage; }
.flowframe-architecture li { counter-increment: stage; padding: 10px; border: 1px solid var(--neutral-border); border-radius: 8px; background: var(--neutral-card); text-align: center; }
.flowframe-architecture li::before { content: counter(stage, decimal-leading-zero) ' '; color: var(--brand-primary); font-weight: 700; }
.flowframe-architecture li:not(:last-child)::after { content: '→'; margin-left: 8px; color: var(--brand-primary); }
.flowframe-modal-subtitle { margin: 6px 0 0; color: var(--neutral-text-1); font-size: 16px; font-weight: 600; }
@media (max-width: 1180px) { .flow-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .hero-inner { grid-template-columns: 48px minmax(0, 1fr) auto; } .hero-description { grid-column: 2; } .hero-actions { grid-column: 3; grid-row: 1 / 3; } }
@media (max-width: 768px) { .hero-inner { grid-template-columns: 48px minmax(0, 1fr); } .hero-description, .hero-actions { grid-column: 1 / -1; grid-row: auto; } .hero-actions { flex-direction: row; flex-wrap: wrap; } .flowframe-points { grid-template-columns: 1fr; } .flowframe-architecture ol { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.flows-header-actions { gap: 12px; }
@media (max-width: 768px) { .flows-header-actions { width: 100%; flex-wrap: wrap; } .header-btn-secondary { flex: 1; } .flowframe-card { align-items: flex-start; } .flowframe-arrow { margin-top: 10px; } }
@media (max-width: 420px) { .flows-page { padding: 16px; } .flow-grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .hero-card, .flow-card, .flowframe-card, .flowframe-arrow { transition: none; } .hero-card:hover, .flow-card:hover, .flowframe-card:hover { transform: none; } }
</style>
