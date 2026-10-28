<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NIcon } from 'naive-ui'
import {
  ArrowForwardOutline, BarChartOutline, CheckmarkCircleOutline,
  CloudUploadOutline, DocumentTextOutline, FlaskOutline,
  SearchOutline, SparklesOutline,
} from '@vicons/ionicons5'
import apiClient from '@/api/client'
import { festivalApi } from '@/api/festival'
import { useAuthStore } from '@/stores/auth'
import OmicBackgroundAnimation from '@/components/OmicBackgroundAnimation.vue'
import AnnouncementBanner from '@/components/AnnouncementBanner.vue'
import FestivalPopup from '@/components/FestivalPopup.vue'
import ResearchWorkbenchPanel from '@/components/home/ResearchWorkbenchPanel.vue'
import type { SiteContent } from '@/types/site-content'
import type { HomeQuickEntry, SiteSettings } from '@/types'
import type { FestivalConfig } from '@/types/festival'
import {
  normalizeHomeQuickEntries,
  quickEntryBgColors,
  quickEntryIconColors,
  resolveHomeQuickEntryIcon,
} from '@/config/homeQuickEntries'
import { isFestivalEffectsEnabled } from '@/utils/interfacePreferences'
import { displayName as getDisplayName } from '@/utils/displayName'

// 默认文案兜底：API 拉取失败或旧配置缺少新增字段时保证首页仍可正常渲染
const DEFAULT_CONTENT: SiteContent = {
  hero: {
    title: 'CygnusX BioOps · 天鹅座智能科研平台',
    slogan: '让科学问题，抵达可验证的发现。',
    description:
      '从公共数据发现或已有数据导入出发，以科研 Agent 组织研究任务，以标准化 Flow 承载计算分析，'
      + '以可信证据连接科研过程与成果交付。',
    tags: ['数据与文献发现', '受控计算分析', '可追溯交付', '科研资产积累'],
    vision: {
      title_en: 'FROM STARDUST, TO DISCOVERY',
      text: '让每一次科研探索，都留下可以继续前行的证据。',
      label: '平台愿景',
    },
  },
  quick_entries: [
    { key: 'treasure-mouse', title: '科研寻宝鼠', desc: '公共组学数据与文献探索' },
    { key: 'files', title: '科研数据管理', desc: '数据导入与科研资产组织' },
    { key: 'flows', title: '多组学分析', desc: '标准化、版本化分析流程' },
    { key: 'ai', title: '星尘 AI 助手', desc: '科研需求理解与智能协作' },
    { key: 'tasks', title: '计算任务中心', desc: '执行状态、日志与质量检查' },
    { key: 'reports', title: '报告与证据', desc: '分析报告、产物和来源记录' },
  ],
  guide_steps: [
    { title: '上传样本数据', desc: '将 FASTQ / BAM 等原始数据上传至数据管理' },
    { title: '选择分析流程', desc: '在分析中心选择 RNA-seq 或 ATAC-seq 流程' },
    { title: '查看分析结果', desc: '任务完成后在报告中心查看与下载结果' },
  ],
}

const router = useRouter()
const authStore = useAuthStore()

// 展示名：优先昵称，未设置或为空则降级为用户名
const displayName = computed(() => getDisplayName(authStore.user))
const isAdmin = computed(() => authStore.user?.role === 'admin')

// 根据当前时段返回问候语
const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

interface QuickEntry extends HomeQuickEntry {
  iconComponent: ReturnType<typeof resolveHomeQuickEntryIcon>
}

interface LifecycleStep {
  label: string
  icon: ReturnType<typeof resolveHomeQuickEntryIcon>
}

const lifecycleSteps: LifecycleStep[] = [
  { label: '科研问题', icon: SearchOutline },
  { label: '数据发现或导入', icon: CloudUploadOutline },
  { label: 'Agent 任务规划', icon: SparklesOutline },
  { label: 'Skill 契约与质量检查', icon: CheckmarkCircleOutline },
  { label: '标准化 Flow 受控执行', icon: FlaskOutline },
  { label: '证据与报告交付', icon: DocumentTextOutline },
  { label: '后续科研探索', icon: ArrowForwardOutline },
]

const researchQuickEntries: HomeQuickEntry[] = [
  { key: 'treasure-mouse', title: '科研寻宝鼠', desc: '公共组学数据与文献探索', to: '/treasure-mouse', icon: 'SearchOutline', icon_bg: 'blue' },
  { key: 'files', title: '科研数据管理', desc: '数据导入与科研资产组织', to: '/files', icon: 'CloudUploadOutline', icon_bg: 'cyan' },
  { key: 'flows', title: '多组学分析', desc: '标准化、版本化分析流程', to: '/flows', icon: 'FlaskOutline', icon_bg: 'purple' },
  { key: 'ai', title: '星尘 AI 助手', desc: '科研需求理解与智能协作', to: '/ai', icon: 'SparklesOutline', icon_bg: 'violet' },
  { key: 'tasks', title: '计算任务中心', desc: '执行状态、日志与质量检查', to: '/tasks', icon: 'DocumentTextOutline', icon_bg: 'orange' },
  { key: 'reports', title: '报告与证据', desc: '分析报告、产物和来源记录', to: '/reports', icon: 'DocumentTextOutline', icon_bg: 'green' },
]

const mechanismCards = [
  { key: 'agent', name: 'Agent', title: '任务理解与规划', desc: '把科研问题整理为可检查的研究任务。', icon: SparklesOutline, color: 'violet' },
  { key: 'skill', name: 'Skill', title: '专业动作约束', desc: '声明输入、输出、前置条件与质量要求。', icon: CheckmarkCircleOutline, color: 'blue' },
  { key: 'flow', name: 'Flow', title: '确定性计算执行', desc: '用版本化流程承载可复现的标准分析。', icon: FlaskOutline, color: 'purple' },
]

const pillars = [
  { key: 'agents', en: 'Research Agents', zh: '科研智能体', desc: '理解需求，组织任务与能力匹配。', icon: SparklesOutline, color: 'violet', status: '需要配置' },
  { key: 'workflows', en: 'Reproducible Workflows', zh: '可复现计算流程', desc: '版本化 Flow 与环境记录承载标准分析。', icon: FlaskOutline, color: 'blue', status: '当前可用' },
  { key: 'governed', en: 'Governed Execution', zh: '受控执行', desc: '以权限边界、隔离策略和质量校验约束执行路径。', icon: CheckmarkCircleOutline, color: 'purple', status: '需要配置' },
  { key: 'evidence', en: 'Verifiable Evidence', zh: '可验证科学证据', desc: '沉淀任务记录、质量检查、产物与报告来源。', icon: DocumentTextOutline, color: 'cyan', status: '当前可用' },
]

const ecosystem = [
  { name: 'CygnusX BioOps', role: '平台核心能力', status: '当前可用', text: '统一组织项目、Agent、任务、数据与交付。', href: '/about' },
  { name: 'Treasure-Seeking Mouse', role: '独立生态组件', status: '实验性 / 预览', text: '公共组学数据、文献发现与来源核验；执行受运行门禁约束。', href: 'https://github.com/xsx123123/Treasure-Seeking_Mouse' },
  { name: 'Polariseq', role: '独立生态组件', status: '需要配置', text: '测序数据传输、断点续传与完整性校验。', href: 'https://github.com/xsx123123/polariseq' },
  { name: 'FlowFrame', role: '独立生态组件', status: '当前可用', text: '多组学流程规范与标准化接入底座。', href: 'https://github.com/xsx123123/FlowFrame' },
  { name: 'RNAFlow', role: '标准计算管线', status: '当前可用', text: 'Bulk RNA-seq 标准分析流程。', href: 'https://github.com/xsx123123/RNAFlow' },
  { name: 'ATACFlow', role: '标准计算管线', status: '当前可用', text: 'ATAC-seq 染色质可及性分析流程。', href: 'https://github.com/xsx123123/ATACFlow' },
  { name: 'AnnoFlow', role: '功能注释管线', status: '需要配置', text: '按任务配置提供基因功能注释与参考产物。', href: 'https://github.com/xsx123123/kegg_annotation' },
  { name: 'BioReport', role: '独立生态组件', status: '需要配置', text: '组织分析结果与方法说明，形成科研报告。', href: 'https://github.com/xsx123123/bioreport' },
]

const capabilityMaturity = [
  { label: '当前可用', color: 'available', text: '标准流程表单、参数校验、项目任务与报告交付是当前主线；具体范围按流程版本和验收结果确定。' },
  { label: '需要配置', color: 'config', text: '模型、工具、数据源、存储和执行资源需结合部署配置与权限检查。' },
  { label: '实验性 / 预览', color: 'preview', text: 'AgentTeams 高级多角色协同默认关闭，需要单独部署和验收。' },
  { label: '规划中', color: 'roadmap', text: '独立证据凭证导出、专用流程治理 Agent 与自动数据回流不属于当前完整可用能力。' },
]

const content = ref<SiteContent>(DEFAULT_CONTENT)
const heroTitleLines = computed(() => {
  const slogan = content.value.hero.slogan || DEFAULT_CONTENT.hero.slogan!
  // 保留后台配置文案，仅在第一个中文逗号后建立语义断点。
  return slogan.replace('，', '，\n').split('\n')
})
const configuredQuickEntries = ref<HomeQuickEntry[] | null>(null)
const selectedHomeCards = ref<Record<'quick' | 'pillar' | 'ecosystem' | 'mechanism' | 'admin', string | null>>({
  quick: null, pillar: null, ecosystem: null, mechanism: null, admin: null,
})
const todayFestival = ref<FestivalConfig | null>(null)
const festivalClaimed = ref(false)

const showFestivalPopup = computed(() => {
  if (!isFestivalEffectsEnabled()) return false
  if (!todayFestival.value) return false
  const seen = localStorage.getItem(`festival_seen_${todayFestival.value.id}`) === '1'
  return !seen
})

const quickEntries = computed<QuickEntry[]>(() => {
  const configuredByKey = new Map(
    normalizeHomeQuickEntries(configuredQuickEntries.value || content.value.quick_entries)
      .map((entry) => [entry.key, entry]),
  )
  return researchQuickEntries.map((entry) => {
    const configured = configuredByKey.get(entry.key)
    const resolved = {
      ...entry,
      icon: configured?.icon || entry.icon,
      icon_bg: configured?.icon_bg || entry.icon_bg,
    }
    return { ...resolved, iconComponent: resolveHomeQuickEntryIcon(resolved.icon) }
  })
})

function goTo(path: string) {
  router.push(path)
}

function handleEcosystemClick(event: MouseEvent, href: string) {
  if (href.startsWith('/')) {
    event.preventDefault()
    goTo(href)
  }
}

onMounted(async () => {
  const [contentResult, settingsResult, festivalResult] = await Promise.allSettled([
    apiClient.get<SiteContent>('/site-content'),
    apiClient.get<SiteSettings>('/site-settings'),
    festivalApi.getTodayFestival(),
  ])

  if (contentResult.status === 'fulfilled') {
    const data = contentResult.value.data
    // 与兜底文案逐层合并：旧配置缺少 hero 新增字段（slogan/tags/vision）时仍能完整渲染
    content.value = {
      ...DEFAULT_CONTENT,
      ...data,
      hero: {
        ...DEFAULT_CONTENT.hero,
        ...data.hero,
        vision: { ...DEFAULT_CONTENT.hero.vision!, ...data.hero?.vision },
      },
    }
  }

  if (settingsResult.status === 'fulfilled' && settingsResult.value.data.home_quick_entries?.length) {
    configuredQuickEntries.value = normalizeHomeQuickEntries(settingsResult.value.data.home_quick_entries)
  }

  if (festivalResult.status === 'fulfilled' && festivalResult.value.hasFestival && isFestivalEffectsEnabled()) {
    todayFestival.value = festivalResult.value.festival
    festivalClaimed.value = festivalResult.value.claimed
  }
})
</script>

<template>
  <div class="home-page" role="main" aria-label="CygnusX 首页">
    <section class="hero animate-fade-in-up">
      <OmicBackgroundAnimation context="hero" />
      <div class="hero-inner">
        <div class="hero-main">
          <p class="hero-kicker">{{ content.hero.title }}</p>
          <p class="hero-greeting">{{ greeting }}{{ displayName ? '，' + displayName : '' }}</p>
          <h1 class="hero-title"><span v-for="(line, index) in heroTitleLines" :key="index" class="hero-title__line">{{ line }}</span></h1>
          <p class="hero-positioning">AI for Science Infrastructure for Life Sciences</p>
          <p class="hero-desc">{{ content.hero.description }}</p>
          <ul v-if="content.hero.tags?.length" class="hero-tags" aria-label="平台能力">
            <li v-for="tag in content.hero.tags" :key="tag" class="hero-tag">{{ tag }}</li>
          </ul>
          <div class="hero-actions">
            <NButton size="large" class="hero-btn-primary" @click="router.push({ name: 'treasure-mouse', query: { start: 'new' } })">
              <template #icon><NIcon><FlaskOutline /></NIcon></template>
              开始一项研究
            </NButton>
            <NButton size="large" class="hero-btn-secondary" @click="router.push({ name: 'treasure-mouse', query: { start: 'plan' } })">
              <template #icon><NIcon><SparklesOutline /></NIcon></template>
              AI 规划研究方案
            </NButton>
          </div>
          <p class="hero-vision-line">{{ content.hero.vision?.title_en }} · {{ content.hero.vision?.text }}</p>
        </div>
        <div class="hero-lifecycle" aria-labelledby="lifecycle-title">
          <div class="hero-lifecycle__header">
            <span class="hero-lifecycle__line" />
            <div>
              <p class="hero-lifecycle__eyebrow">RESEARCH LIFECYCLE</p>
              <h2 id="lifecycle-title">从问题到可验证的发现</h2>
            </div>
          </div>
          <ol class="lifecycle-list">
            <li v-for="(step, index) in lifecycleSteps" :key="step.label" class="lifecycle-step">
              <span class="lifecycle-step__node"><NIcon :size="16"><component :is="step.icon" /></NIcon></span>
              <span class="lifecycle-step__label">{{ step.label }}</span>
              <span v-if="index < lifecycleSteps.length - 1" class="lifecycle-step__connector" aria-hidden="true" />
            </li>
          </ol>
          <p class="hero-lifecycle__note hero-lifecycle__note--desktop">每个阶段都保留清晰的项目上下文与运行依据。</p>
          <p class="hero-lifecycle__note hero-lifecycle__note--mobile">后续：标准化 Flow 受控执行 → 证据交付 → 后续科研探索。</p>
        </div>
      </div>
    </section>

    <AnnouncementBanner remember-dismissal />
    <ResearchWorkbenchPanel />

    <section class="section quick-entry-section animate-fade-in-up delay-100" aria-labelledby="quick-entry-title">
      <div class="section-heading">
        <div>
          <p class="section-eyebrow">RESEARCH SHORTCUTS</p>
          <h2 id="quick-entry-title">科研快捷入口</h2>
          <p class="section-subtitle">从发现、数据、分析到交付，选择你现在要继续的环节。</p>
        </div>
      </div>
      <div class="entry-grid">
        <button v-for="entry in quickEntries" :key="entry.key" type="button" class="entry-card arco-card cygnusx-selectable-card" :data-selected="selectedHomeCards.quick === entry.key" @click="selectedHomeCards.quick = entry.key; goTo(entry.to)">
          <span class="entry-icon" :style="{ background: quickEntryBgColors[entry.icon_bg], color: quickEntryIconColors[entry.icon_bg] }">
            <NIcon :size="22"><component :is="entry.iconComponent" /></NIcon>
          </span>
          <span class="entry-text">
            <strong class="entry-title">{{ entry.title }}</strong>
            <span class="entry-desc">{{ entry.desc }}</span>
          </span>
          <NIcon :size="16" class="entry-arrow card-state-arrow"><ArrowForwardOutline /></NIcon>
        </button>
      </div>
    </section>

    <section class="section mechanism-section animate-fade-in-up delay-200" aria-labelledby="mechanism-title">
      <div class="section-heading">
        <div>
          <p class="section-eyebrow">CONTROLLED RESEARCH LOOP</p>
          <h2 id="mechanism-title">Agent × Skill × Flow</h2>
          <p class="section-subtitle">Agent 组织任务，Skill 约束专业动作，Flow 承载标准计算；Evidence 记录运行与交付结果。</p>
        </div>
      </div>
      <div class="mechanism-layout">
        <div class="mechanism-flow" aria-label="核心协作机制">
          <button v-for="(card, index) in mechanismCards" :key="card.key" type="button" class="mechanism-card cygnusx-selectable-card" :class="`mechanism-card--${card.color}`" :aria-pressed="selectedHomeCards.mechanism === card.key" @click="selectedHomeCards.mechanism = card.key">
            <span class="mechanism-card__icon"><NIcon :size="19"><component :is="card.icon" /></NIcon></span>
            <div>
              <p class="mechanism-card__name">{{ card.name }}</p>
              <h3>{{ card.title }}</h3>
              <p>{{ card.desc }}</p>
            </div>
            <span v-if="index < 2" class="mechanism-card__arrow card-state-arrow" aria-hidden="true"><ArrowForwardOutline /></span>
          </button>
        </div>
        <button type="button" class="evidence-note cygnusx-selectable-card" :aria-pressed="selectedHomeCards.mechanism === 'evidence'" @click="selectedHomeCards.mechanism = 'evidence'">
          <span class="evidence-note__icon"><NIcon :size="20"><DocumentTextOutline /></NIcon></span>
          <div>
            <p class="mechanism-card__name">Evidence</p>
            <h3>让结果可以被核对</h3>
            <p>Evidence 不承担执行；它沉淀运行记录、质量检查、产物与报告来源，支撑交付核验。</p>
          </div>
          <NIcon :size="16" class="evidence-note__arrow card-state-arrow" aria-hidden="true"><ArrowForwardOutline /></NIcon>
        </button>
      </div>
    </section>

    <section class="section pillars-section animate-fade-in-up delay-200" aria-labelledby="pillars-title">
      <div class="section-heading"><div><p class="section-eyebrow">PLATFORM FOUNDATIONS</p><h2 id="pillars-title">四大技术支柱</h2></div></div>
      <div class="pillars-grid">
        <button v-for="pillar in pillars" :key="pillar.key" type="button" class="pillar-card cygnusx-selectable-card" :class="`pillar-card--${pillar.color}`" :aria-pressed="selectedHomeCards.pillar === pillar.key" @click="selectedHomeCards.pillar = pillar.key">
          <span class="pillar-icon"><NIcon :size="20"><component :is="pillar.icon" /></NIcon></span>
          <div class="pillar-copy"><p class="pillar-en">{{ pillar.en }}</p><h3>{{ pillar.zh }}</h3><p>{{ pillar.desc }}</p></div>
          <span class="maturity-badge">{{ pillar.status }}</span>
          <NIcon :size="16" class="pillar-arrow card-state-arrow" aria-hidden="true"><ArrowForwardOutline /></NIcon>
        </button>
      </div>
    </section>

    <section class="section ecosystem-section animate-fade-in-up delay-200" aria-labelledby="ecosystem-title">
      <div class="section-heading">
        <div><p class="section-eyebrow">CONNECTED ECOSYSTEM</p><h2 id="ecosystem-title">科研生态</h2><p class="section-subtitle">平台核心能力与独立生态组件通过清晰的接口协作。</p></div>
        <NButton quaternary size="small" @click="goTo('/about')">查看完整生态介绍<template #icon><NIcon><ArrowForwardOutline /></NIcon></template></NButton>
      </div>
      <div class="ecosystem-grid">
        <a v-for="item in ecosystem" :key="item.name" class="ecosystem-card cygnusx-selectable-card" :data-selected="selectedHomeCards.ecosystem === item.name" :href="item.href" :target="item.href.startsWith('/') ? undefined : '_blank'" rel="noreferrer" @click="selectedHomeCards.ecosystem = item.name; handleEcosystemClick($event, item.href)">
          <span class="ecosystem-card__mark"><NIcon :size="17"><component :is="item.name === 'CygnusX BioOps' ? FlaskOutline : item.name === 'Treasure-Seeking Mouse' ? SearchOutline : item.name === 'BioReport' ? DocumentTextOutline : ArrowForwardOutline" /></NIcon></span>
          <span class="ecosystem-card__copy"><strong>{{ item.name }}</strong><small>{{ item.role }} · {{ item.status }}</small><span>{{ item.text }}</span></span>
          <NIcon :size="14" class="ecosystem-card__arrow card-state-arrow"><ArrowForwardOutline /></NIcon>
        </a>
      </div>
    </section>

    <section class="capability-boundary" aria-label="能力状态说明">
      <div><p class="section-eyebrow">CAPABILITY MATURITY</p><h2>能力范围随部署配置与验收结果而定</h2></div>
      <div class="capability-legend">
        <span v-for="item in capabilityMaturity" :key="item.label" class="capability-item" :class="`capability-item--${item.color}`">
          <span><strong><i class="legend-dot" aria-hidden="true" />{{ item.label }}</strong><small>{{ item.text }}</small></span>
        </span>
      </div>
    </section>

    <section v-if="isAdmin" class="section animate-fade-in-up delay-200">
      <div class="admin-banner cygnusx-selectable-card" :data-selected="selectedHomeCards.admin === 'admin'" @click="selectedHomeCards.admin = 'admin'; goTo('/admin/users')">
        <div class="admin-icon"><NIcon :size="20"><BarChartOutline /></NIcon></div>
        <div class="admin-text"><h4 class="admin-title">系统管理</h4><p class="admin-desc">用户、AI 模型、饼干账户与资源中心管理</p></div>
        <NButton class="admin-cta">进入管理</NButton>
      </div>
    </section>

    <FestivalPopup v-if="todayFestival && showFestivalPopup" :festival="todayFestival" :already-claimed="festivalClaimed" @claimed="festivalClaimed = true" @close="todayFestival = null" />
  </div>
</template>

<style scoped>
.home-page {
  --home-font-section: 24px;
  --home-font-card-title: 16px;
  --home-font-body: 14px;
  --home-font-small: 13px;
  --home-font-meta: 12px;
  --home-font-eyebrow: 11px;
  font-size: var(--home-font-body);
  min-height: 100%;
  overflow: visible;
  background: var(--neutral-bg);
}

.home-page .animate-fade-in-up { animation-duration: 400ms; }

.hero {
  position: relative;
  overflow: hidden;
  min-height: 380px;
  margin-bottom: 16px;
  padding: 40px 32px;
  border-radius: 16px;
  /* 统一品牌渐变：与功能通知横幅（AnnouncementBanner）同源，禁止回退到深蓝紫 */
  background: var(--cygnus-brand-gradient);
  color: #fff;
}

.hero :deep(.omic-canvas) { opacity: 0.4; }

/* 轻量压暗画布与渐变，保证白色文字与玻璃卡的对比度；
   明亮品牌渐变下仅保留局部叠层，不做大面积深色遮罩。 */
.hero::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  background: rgba(8, 11, 18, 0.2);
  pointer-events: none;
}

.hero-inner {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 1fr);
  gap: 32px;
  align-items: center;
}

.hero-main { min-width: 0; }
.hero-kicker {
  margin: 0 0 4px;
  font-size: var(--home-font-body);
  font-weight: 650;
  letter-spacing: 0.3px;
  opacity: 0.94;
}
.hero-greeting {
  margin: 0 0 6px;
  font-size: var(--home-font-body);
  opacity: 0.88;
}
.hero-title {
  margin: 0 0 8px;
  font-size: clamp(26px, 2.6vw, 38px);
  font-weight: 750;
  line-height: 1.25;
  letter-spacing: -0.4px;
  text-wrap: balance;
}
.hero-title__line { display: block; word-break: keep-all; overflow-wrap: anywhere; }
.hero-positioning {
  margin: 0 0 8px;
  font-size: var(--home-font-small);
  font-weight: 600;
  letter-spacing: 1.5px;
  opacity: 0.88;
}
.hero-desc {
  max-width: 58ch;
  margin: 0 0 12px;
  font-size: var(--home-font-body);
  line-height: 1.6;
  opacity: 0.9;
}
.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
}
.hero-tag {
  padding: 3px 11px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.11);
  font-size: var(--home-font-meta);
  line-height: 18px;
  white-space: nowrap;
}
.hero-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.hero-vision-line {
  margin: 12px 0 0;
  color: rgba(255, 255, 255, 0.88);
  font-size: var(--home-font-meta);
  line-height: 1.55;
}

.n-button.hero-btn-primary,
.n-button.hero-btn-secondary {
  height: auto;
  padding: 8px 18px;
  border-radius: 10px;
  font-size: var(--home-font-body);
  font-weight: 650;
  transition: transform 0.2s ease;
}
.n-button.hero-btn-primary {
  border: 0;
  background-color: rgba(255, 255, 255, 0.96);
  color: var(--cygnus-brand-violet);
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.18);
}
.n-button.hero-btn-primary:hover,
.n-button.hero-btn-primary:focus-visible {
  background-color: #fff;
  color: var(--cygnus-brand-violet);
  transform: translateY(-1px);
  box-shadow: 0 7px 22px rgba(0, 0, 0, 0.22);
}
.n-button.hero-btn-secondary {
  border: 1px solid rgba(255, 255, 255, 0.54);
  background-color: rgba(255, 255, 255, 0.12);
  color: #fff;
  backdrop-filter: blur(10px);
}
.n-button.hero-btn-secondary:hover,
.n-button.hero-btn-secondary:focus-visible {
  border-color: rgba(255, 255, 255, 0.82);
  background-color: rgba(255, 255, 255, 0.22);
  color: #fff;
  transform: translateY(-1px);
}
.n-button.hero-btn-primary :deep(.n-button__border),
.n-button.hero-btn-primary :deep(.n-button__state-border),
.n-button.hero-btn-secondary :deep(.n-button__border),
.n-button.hero-btn-secondary :deep(.n-button__state-border) { display: none; }
.hero-actions :deep(.n-button__icon) { margin-right: 7px; }
.n-button.hero-btn-primary :deep(.n-button__icon) { color: var(--cygnus-brand-violet); }
.n-button.hero-btn-secondary :deep(.n-button__icon) { color: #fff; }

.hero-lifecycle {
  min-width: 0;
  min-height: 340px;
  padding: 28px 28px 24px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.10);
  color: #fff;
  backdrop-filter: blur(16px);
}
.hero-lifecycle__header { display: flex; gap: 12px; align-items: flex-start; }
.hero-lifecycle__line { width: 3px; height: 44px; flex: 0 0 auto; border-radius: 3px; background: rgba(255, 255, 255, 0.68); }
.hero-lifecycle__eyebrow {
  margin: 0 0 3px;
  font-size: var(--home-font-eyebrow);
  font-weight: 700;
  letter-spacing: 1.25px;
  color: rgba(255, 255, 255, 0.85);
}
.hero-lifecycle h2 { margin: 0; font-size: 20px; font-weight: 650; line-height: 1.4; }
.lifecycle-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 20px; margin: 24px 0 0; padding: 0; list-style: none; }
.lifecycle-step { position: relative; display: flex; min-width: 0; align-items: center; gap: 10px; min-height: 44px; }
.lifecycle-step__node { display: grid; width: 30px; height: 30px; flex: 0 0 auto; place-items: center; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 50%; background: rgba(255, 255, 255, 0.13); }
.lifecycle-step__label { min-width: 0; color: rgba(255, 255, 255, 0.88); font-size: var(--home-font-body); line-height: 1.5; }
.lifecycle-step__connector { display: none; }
.hero-lifecycle__note { margin: 20px 0 0; color: rgba(255, 255, 255, 0.85); font-size: var(--home-font-small); line-height: 1.5; }
.hero-lifecycle__note--mobile { display: none; }

.section { margin-bottom: 31px; }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 15px; }
.section-eyebrow { margin: 0 0 4px; color: var(--neutral-text-3); font-size: var(--home-font-eyebrow); font-weight: 700; letter-spacing: 1.25px; }
.section-heading h2 { margin: 0; color: var(--neutral-text-1); font-size: var(--home-font-section); font-weight: 650; line-height: 1.35; }
.section-subtitle { margin: 5px 0 0; color: var(--neutral-text-2); font-size: var(--home-font-body); line-height: 1.5; }

.entry-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.entry-card {
  position: relative;
  display: flex;
  width: 100%;
  min-width: 0;
  align-items: center;
  gap: 13px;
  padding: 20px;
  border: 1px solid var(--neutral-border);
  text-align: left;
  cursor: pointer;
  font: inherit;
}
.entry-icon { display: grid; width: 44px; height: 44px; flex: 0 0 auto; place-items: center; border-radius: 11px; }
.entry-text { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }
.entry-title { overflow: hidden; color: var(--neutral-text-1); font-size: var(--home-font-card-title); font-weight: 600; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.entry-desc { overflow: hidden; color: var(--neutral-text-2); font-size: var(--home-font-body); line-height: 1.5; text-overflow: ellipsis; white-space: nowrap; }
.entry-arrow { flex: 0 0 auto; }

.mechanism-layout { display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(240px, 0.8fr); gap: 14px; }
.mechanism-flow { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.mechanism-card,
.evidence-note,
.pillar-card,
.ecosystem-card { position: relative; border: 1px solid var(--neutral-border); background: var(--neutral-card); box-shadow: var(--shadow-card); }
.mechanism-card { width: 100%; color: inherit; font: inherit; text-align: left; cursor: pointer; overflow: visible; position: relative; display: flex; min-width: 0; gap: 11px; padding: 17px 16px; border-radius: var(--radius-card); }
.mechanism-card__icon,
.evidence-note__icon,
.pillar-icon { display: grid; width: 34px; height: 34px; flex: 0 0 auto; place-items: center; border-radius: 10px; }
.mechanism-card__name { margin: 0 0 3px; color: var(--neutral-text-3); font-size: var(--home-font-meta); font-weight: 700; letter-spacing: 0.6px; text-transform: uppercase; }
.mechanism-card h3,
.evidence-note h3 { margin: 0 0 5px; color: var(--neutral-text-1); font-size: var(--home-font-card-title); font-weight: 650; line-height: 1.35; }
.mechanism-card > div > p:last-child,
.evidence-note > div > p:last-child { margin: 0; color: var(--neutral-text-2); font-size: var(--home-font-body); line-height: 1.55; }
.mechanism-card__arrow { position: absolute; top: 50%; right: -17px; z-index: 1; display: grid; width: 21px; height: 21px; place-items: center; border: 1px solid var(--neutral-border); border-radius: 50%; background: var(--neutral-card); transform: translateY(-50%); }
.mechanism-card--violet .mechanism-card__icon { color: #8059d8; background: color-mix(in srgb, #8059d8 11%, var(--neutral-card)); }
.mechanism-card--blue .mechanism-card__icon { color: var(--brand-primary); background: var(--brand-primary-light); }
.mechanism-card--purple .mechanism-card__icon { color: #722ed1; background: color-mix(in srgb, #722ed1 10%, var(--neutral-card)); }
.evidence-note { width: 100%; color: inherit; font: inherit; text-align: left; cursor: pointer; display: flex; min-width: 0; gap: 12px; align-items: flex-start; padding: 19px; border-radius: var(--radius-card); background: var(--neutral-card); }
.evidence-note__arrow { position: absolute; top: 17px; right: 17px; }
.evidence-note__icon { color: #0b9d9a; background: color-mix(in srgb, #0b9d9a 11%, var(--neutral-card)); }

.pillars-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 13px; }
.pillar-card { width: 100%; color: inherit; font: inherit; text-align: left; cursor: pointer; display: flex; min-width: 0; flex-direction: column; gap: 13px; padding: 17px; border-radius: var(--radius-card); }
.pillar-icon { width: 37px; height: 37px; }
.pillar-arrow { position: absolute; top: 17px; right: 17px; }
.pillar-copy { min-width: 0; }
.pillar-en { margin: 0 0 3px; color: var(--neutral-text-3); font-size: var(--home-font-meta); font-weight: 700; letter-spacing: 0.45px; }
.pillar-copy h3 { margin: 0 0 6px; color: var(--neutral-text-1); font-size: var(--home-font-card-title); font-weight: 650; }
.pillar-copy p:last-child { margin: 0; color: var(--neutral-text-2); font-size: var(--home-font-body); line-height: 1.55; }
.pillar-card--violet .pillar-icon { color: #8059d8; background: color-mix(in srgb, #8059d8 11%, var(--neutral-card)); }
.pillar-card--blue .pillar-icon { color: var(--brand-primary); background: var(--brand-primary-light); }
.pillar-card--purple .pillar-icon { color: #722ed1; background: color-mix(in srgb, #722ed1 10%, var(--neutral-card)); }
.pillar-card--cyan .pillar-icon { color: #0b9d9a; background: color-mix(in srgb, #0b9d9a 11%, var(--neutral-card)); }
.maturity-badge { align-self: flex-start; padding: 3px 8px; border: 1px solid var(--neutral-border); border-radius: 999px; color: var(--neutral-text-3); font-size: var(--home-font-meta); line-height: 1.3; }

.ecosystem-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.ecosystem-card { display: flex; min-width: 0; align-items: flex-start; gap: 10px; padding: 14px; border-radius: var(--radius-card); color: inherit; text-decoration: none; }
.ecosystem-card__mark { display: grid; width: 31px; height: 31px; flex: 0 0 auto; place-items: center; border-radius: 9px; background: var(--brand-primary-light); color: var(--brand-primary); }
.ecosystem-card__copy { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }
.ecosystem-card__copy strong { overflow: hidden; color: var(--neutral-text-1); font-size: var(--home-font-body); font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.ecosystem-card__copy small { color: var(--neutral-text-2); font-size: var(--home-font-meta); }
.ecosystem-card__copy > span { color: var(--neutral-text-2); font-size: var(--home-font-body); line-height: 1.45; }
.ecosystem-card__arrow { flex: 0 0 auto; margin-top: 2px; }

.capability-boundary { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-bottom: 28px; padding: 16px 18px; border: 1px solid var(--neutral-border); border-radius: var(--radius-card); background: var(--neutral-fill-2); }
.capability-boundary h2 { margin: 0; color: var(--neutral-text-2); font-size: var(--home-font-body); font-weight: 600; }
.capability-legend { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; color: var(--neutral-text-3); font-size: var(--home-font-meta); }
.capability-item { display: flex; min-width: 0; align-items: flex-start; gap: 7px; }
.capability-item > span { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.capability-item strong { display: flex; align-items: center; gap: 7px; color: var(--neutral-text-2); font-size: var(--home-font-small); font-weight: 650; line-height: 1.5; white-space: nowrap; }
.capability-item small { padding-left: 14px; color: var(--neutral-text-2); font-size: var(--home-font-meta); line-height: 1.5; }
.legend-dot { position: relative; display: block; flex: 0 0 7px; width: 7px; height: 7px; border-radius: 50%; }
.legend-dot::after { content: ''; position: absolute; inset: -3px; border-radius: inherit; background: inherit; pointer-events: none; animation: capability-dot-breathe 3.2s ease-in-out infinite; }
@keyframes capability-dot-breathe {
  0%, 100% { transform: scale(0.75); opacity: 0.08; }
  50% { transform: scale(1.15); opacity: 0.26; }
}
.capability-item--available .legend-dot { background: #2a9d68; }
.capability-item--config .legend-dot { background: #d58a24; }
.capability-item--preview .legend-dot { background: #8059d8; }
.capability-item--roadmap .legend-dot { background: var(--neutral-text-4); }

.admin-banner { position: relative; display: flex; align-items: center; gap: 16px; overflow: hidden; padding: 20px; border-radius: var(--radius-card); background: var(--neutral-card); box-shadow: var(--shadow-card); cursor: pointer; }
.admin-icon { display: grid; width: 44px; height: 44px; flex: 0 0 auto; place-items: center; border-radius: 10px; background: var(--arco-primary-light); color: var(--arco-primary); }
.admin-text { min-width: 0; flex: 1; }
.admin-title { margin: 0 0 4px; color: var(--neutral-text-1); font-size: var(--home-font-card-title); font-weight: 600; }
.admin-desc { margin: 0; color: var(--neutral-text-2); font-size: var(--home-font-body); line-height: 1.5; }
.n-button.admin-cta { flex: 0 0 auto; padding: 8px 18px; border: 0; border-radius: 10px; background: var(--brand-gradient); color: #fff; font-size: var(--home-font-body); font-weight: 650; transition: transform 200ms ease; }
.n-button.admin-cta:hover,
.n-button.admin-cta:focus-visible { transform: translateY(-1px); }
.n-button.admin-cta :deep(.n-button__border),
.n-button.admin-cta :deep(.n-button__state-border) { display: none; }

@media (max-width: 1100px) {
  .hero-inner { grid-template-columns: minmax(0, 1fr); gap: 24px; }
  .hero-lifecycle { max-width: none; }
  .pillars-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ecosystem-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 820px) {
  .entry-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .mechanism-layout { grid-template-columns: minmax(0, 1fr); }
  .mechanism-flow { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .evidence-note { min-height: 0; }
  .capability-boundary { align-items: flex-start; flex-direction: column; }
  .capability-legend { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .home-page { padding: 16px; }
  .hero { padding: 25px 20px; }
  .hero-title { font-size: clamp(21px, 5.4vw, 26px); }
  .hero-positioning { font-size: var(--home-font-meta); letter-spacing: 1px; }
  .hero :deep(.omic-canvas) { opacity: 0.24; }
  .hero-lifecycle { min-height: 0; padding: 20px; }
  .lifecycle-list { grid-template-columns: minmax(0, 1fr); row-gap: 4px; margin-top: 16px; }
  .lifecycle-step { min-height: 36px; }
  .lifecycle-step:nth-child(n + 6) { display: none; }
  .hero-lifecycle__note--desktop { display: none; }
  .hero-lifecycle__note--mobile { display: block; }
  .hero-vision-line { margin-top: 16px; }
  .section-heading { align-items: flex-start; }
  .section-heading h2 { font-size: 22px; }
  .entry-grid,
  .pillars-grid,
  .ecosystem-grid,
  .mechanism-flow { grid-template-columns: minmax(0, 1fr); }
  .mechanism-card__arrow { display: none; }
  .entry-card { padding: 14px; }
  .capability-legend { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .admin-banner { align-items: flex-start; flex-wrap: wrap; }
  .admin-cta { margin-left: 60px; }
}

@media (prefers-reduced-transparency: reduce) {
  .hero-lifecycle { background: #293c6b; backdrop-filter: none; }
}

@media (prefers-reduced-motion: reduce) {
  .legend-dot::after { animation: none; opacity: 0; }
  .home-page .animate-fade-in-up { animation: none; }
  .entry-card,
  .entry-card::after,
  .entry-icon,
  .entry-arrow,
  .ecosystem-card,
  .admin-banner,
  .n-button.admin-cta,
  .n-button.hero-btn-primary,
  .n-button.hero-btn-secondary { transition: none; }
  .entry-card:hover,
  .entry-card:focus-visible,
  .entry-card:hover .entry-icon,
  .entry-card:hover .entry-arrow,
  .admin-banner:hover,
  .n-button.admin-cta:hover,
  .n-button.admin-cta:focus-visible,
  .n-button.hero-btn-primary:hover,
  .n-button.hero-btn-primary:focus-visible,
  .n-button.hero-btn-secondary:hover,
  .n-button.hero-btn-secondary:focus-visible { transform: none; }
}
</style>
