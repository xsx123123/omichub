<script setup lang="ts">
import { ref, onBeforeUnmount, onMounted } from 'vue'
import { NIcon, NButton, useMessage } from 'naive-ui'
import { RocketOutline, ShieldCheckmarkOutline, TelescopeOutline, LogoGithub, SparklesOutline, ChevronDownOutline } from '@vicons/ionicons5'
import { useRouter, RouterLink } from 'vue-router'
import { useSiteConfigStore } from '@/stores/site-config'
// 彩蛋图片：猫猫踩地球插画
import catEarthLogo from '@/assets/ChatGPT_logo.png'
// 生态组件图标（docs/logo 优化产物：256px webp）
import logoTreasureMouse from '@/assets/ecosystem/treasure-mouse.webp'
import logoPolariseq from '@/assets/ecosystem/polariseq.webp'
import logoFlowFrame from '@/assets/ecosystem/flowframe.webp'
import logoBioReport from '@/assets/ecosystem/bioreport.webp'

const router = useRouter()
const siteConfig = useSiteConfigStore()
const message = useMessage()

onMounted(() => {
  siteConfig.fetchSiteConfig()
  observeReveals()
})

// 彩蛋：点击蓝色星球触发隐藏弹窗
const showEasterEgg = ref(false)

// 打开彩蛋弹窗：顺带拉取站点文案（已加载则复用，确保文案可被 YAML 配置覆盖）
function openEasterEgg() {
  siteConfig.fetchSiteConfig()
  showEasterEgg.value = true
}

// ===== 召唤星际猫咪 =====
// 猫爪动画由全局 CatPawsOverlay 负责（App.vue 挂载），这里只派发事件 + 弹 Toast。
// playing 用于防连点：动画播放期间不重复派发。
const playing = ref(false)
let pawTimer: ReturnType<typeof setTimeout> | null = null

function summonCat() {
  if (playing.value) return
  // 确保 toast / 按钮文案已就绪（首次进入关于页即点按钮时可能尚未拉取）
  siteConfig.fetchSiteConfig()
  playing.value = true
  message.success(siteConfig.easterEggToast, { duration: 3500 })
  window.dispatchEvent(new CustomEvent('cygnusX:triggerCatPaws'))
  if (pawTimer) clearTimeout(pawTimer)
  pawTimer = setTimeout(() => {
    playing.value = false
  }, 7000)
}

onBeforeUnmount(() => {
  if (pawTimer) clearTimeout(pawTimer)
  revealObserver?.disconnect()
  revealObserver = null
})

// 负相位延迟：让每颗星"开局即处于自己呼吸周期的随机中段"。
// 若用正延迟，动画开始前元素停留在基础样式（.star 无 opacity → 1.0 全亮），
// 随后逐颗跌到呼吸下限，开页前几秒会出现"满天亮星一颗颗暗下去"的级联，
// 用户感知为"高光消失"。负延迟从首帧起就是稳态夜空，无亮→暗跳变。
const stars = Array.from({ length: 160 }, (_, i) => {
  const size = Math.random() * 1 + 0.6
  const baseOpacity = Math.random() * 0.5 + 0.35
  const duration = Math.random() * 5 + 5

  const isBright = baseOpacity > 0.7
  // 十字高光稍微多一些、亮一些：保证任意时刻都有"几处高光"稳定可见，
  // 不会因闪烁集体变暗而让夜空显得发平。
  const hasCross = isBright && Math.random() > 0.7

  const crossScale = hasCross ? (size * baseOpacity * 0.9).toFixed(2) : 0

  return {
    id: i,
    top: Math.random() * 100,
    left: Math.random() * 100,
    size: size,
    opacity: baseOpacity,
    delay: -(Math.random() * duration),
    duration,
    hasCross: hasCross,
    crossScale: crossScale
  }
})

const shootingStars = Array.from({ length: 3 }, (_, i) => ({
  id: i,
  // 每颗仅在长周期中的短暂时刻划过，保持背景安静。
  // 首颗推迟到 ~7s 后：开页瞬间先呈现稳态高光夜空，流星随后才"添光"，
  // 避免一进来就和"高光"抢视觉、重现"流星出现→高光消失"的错觉。
  delay: 7 + i * 13 + Math.random() * 4,
  duration: 36 + Math.random() * 8,
  top: Math.random() * 50,
  left: Math.random() * 60,
  scale: 0.8 + Math.random() * 0.7,
}))

// 星云带：加宽、加多，不透明度*固定*在一个清晰可见的区间、只做极慢漂移，
// 让斜向紫蓝光雾成为"恒定底色"，任何时刻（含流星划过）都不会突然消失。
// 同样用负相位延迟：避免开页前几秒星云停在基础 opacity 1.0、动画启动后再跌回
// 0.7~0.95 的闪变（与星星同理的"高光消失"来源之一）。
const nebulaLayers = Array.from({ length: 4 }, (_, i) => {
  const duration = 24 + Math.random() * 22
  return {
    id: i,
    top: 10 + Math.random() * 60,
    left: -10 + Math.random() * 40,
    width: 70 + Math.random() * 30,
    height: 16 + Math.random() * 12,
    opacity: 0.7 + Math.random() * 0.25,
    delay: -(Math.random() * duration),
    duration,
  }
})

const valueStreams = [
  { number: '01', title: 'Discovery · 科研发现', input: '科研问题、公共数据或已有实验数据', output: '关联样本信息、数据来源与文献的研究素材', icon: TelescopeOutline },
  { number: '02', title: 'Execution · 受控计算', input: '项目上下文、样本设计与分析计划', output: '经参数校验、版本化流程与质量检查的计算结果', icon: ShieldCheckmarkOutline },
  { number: '03', title: 'Evidence · 证据交付', input: '分析产物、运行记录与外部证据', output: '可核验的结果、方法记录与后续探索依据', icon: SparklesOutline },
]
const heroChips = ['科研数据与文献发现', '版本化分析流程', '权限与质量约束', '可追溯研究资产']

// 能力概览，不使用缺乏统计来源的报告数、Stars 或数据库总量。
const stats = [
  { value: 'Agent', label: '组织科研任务' },
  { value: 'Skill', label: '约束专业操作' },
  { value: 'Flow', label: '承载标准计算' },
  { value: 'Evidence', label: '关联来源与结果' },
]

// 展示范围依据当前 MCP preset / adapter；不代表各部署的实时可用性。
// 来源：infrastructure/mcp/{presets,biothings_preset,research_preset}.py
// 与 ARCHITECTURE_DESIGN/CygnusX_mcp_architecture.md §1.3。
const researchResources = [
  { title: '公共组学数据', sources: ['GEO', 'SRA', 'ENA', 'GSA'], text: '检索组学项目、样本元数据，解析公共数据登录号。' },
  { title: '基因、变异与化合物', sources: ['MyGene', 'MyVariant', 'MyChem', 'ClinVar'], text: '查询基因注释、变异记录、化合物信息与变异证据。' },
  { title: '植物基因组与重复序列', sources: ['Ensembl Plants', 'Gramene', 'Dfam'], text: '查询植物基因、同源关系、基因组区间与转座元件家族。' },
  { title: '表达研究目录', sources: ['Expression Atlas', 'Single Cell Expression Atlas'], text: '发现表达研究与单细胞研究的目录及元数据。', note: '部分 Expression Atlas 目录请求仍可能超时。' },
  { title: '蛋白、结构与通路', sources: ['UniProt', 'InterPro', 'RCSB PDB', 'AlphaFold DB', 'Reactome', 'STRING'], text: '查询蛋白功能与结构域、实验结构、预测结构和通路知识。', note: 'STRING 标识映射与关联网络查询已实现，完整调用链仍待验收。' },
  { title: '文献与靶点证据', sources: ['Europe PMC', 'Open Targets'], text: '检索论文及其元数据，查询靶点、疾病关联与证据记录。' },
]

const workingModel = [
  { name: 'Agent', title: '把问题组织成任务', text: '理解需求、补齐信息、匹配工具与流程，依据真实工具结果解释分析过程。' },
  { name: 'Skill', title: '把经验沉淀为契约', text: '明确专业操作的输入、输出、前提、方法与质量要求，让研究经验可以复用。' },
  { name: 'Flow', title: '把方法固化为流程', text: '以声明式、版本化的流程承载标准计算，记录参数、环境与运行产物。' },
]
const researchEntries = [
  { level: 'L1', name: '生信工具箱', text: '重复操作与轻量可视化' },
  { level: 'L2', name: '星尘 AI 助手', text: '需求澄清、检索与工具调用' },
  { level: 'L3', name: 'OmicStudio', text: '隔离环境中的交互式深入分析' },
  { level: 'L4', name: '多 Agent 协作室', text: '规划、委派与质量复核（受控预览）' },
]

// 项目起源与演进依据根 README；未来阶段为长期愿景，不代表现有能力。
const milestones = [
  { time: '未来 · 长期愿景', title: '从工具使用到科学创造', text: '构建跨学科的 AI 智能体协作网络，从使用工具、发现事实，走向创造科学工具、设计新型仪器与实验方法、提出概念与数学框架，探索跨领域的统一规律与新的科学范式。' },
  { time: '持续演进', title: '从组学分析到智能科研基础设施', text: '围绕真实科研需求，逐步连接数据发现、Agent 编排、标准计算与可验证成果交付。' },
  { time: '2026.06.25', title: 'OmicHub 诞生', text: '一名生命科学在读博士提交首行代码，从私有化多组学分析出发，解决流程繁琐、环境复杂与结果难以复现的问题。' },
]

// 生态职责与仓库链接依据根 README；各组件的开放范围以部署与验收状态为准。
const ecosystemModules = [
  { name: '科研寻宝鼠', text: '对话式公共组学数据发现、文献检索与来源核验。', status: '数据发现', logo: logoTreasureMouse, href: 'https://github.com/xsx123123/Treasure-Seeking_Mouse' },
  { name: 'Polariseq', text: '支持断点续传与完整性校验的测序数据传输。', status: '数据获取', logo: logoPolariseq, href: 'https://github.com/xsx123123/polariseq' },
  { name: 'FlowFrame', text: '通用组学流程架构与标准化接入约定。', status: '流程框架', logo: logoFlowFrame, href: 'https://github.com/xsx123123/FlowFrame' },
  { name: 'RNAFlow', text: 'Bulk RNA-seq 质控、比对、定量与差异分析。', status: '转录组分析', logo: null, href: 'https://github.com/xsx123123/RNAFlow' },
  { name: 'ATACFlow', text: 'ATAC-seq 质控、比对、峰识别、差异可及性与 motif 分析。', status: '染色质分析', logo: null, href: 'https://github.com/xsx123123/ATACFlow' },
  { name: 'AnnoFlow', text: '结合 eggnog-mapper 与 KofamScan 的功能注释及 KO 交叉验证。', status: '功能注释', logo: null, href: 'https://github.com/xsx123123/kegg_annotation' },
  { name: 'BioReport', text: '基于 Python / Quarto 组织分析结果，生成交互式 HTML 与 PDF 报告。', status: '报告组件', logo: logoBioReport, href: 'https://github.com/xsx123123/bioreport' },
]
function scrollToSection(id: string) { document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }

// ===== 进入视口一次性进场动效（指标格 / 里程碑节点） =====
// 仅 opacity + transform；prefers-reduced-motion 下由 CSS 直接呈现终态。
let revealObserver: IntersectionObserver | null = null

if (typeof IntersectionObserver !== 'undefined') {
  revealObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          revealObserver?.unobserve(entry.target)
        }
      }
    },
    { threshold: 0.3 },
  )
}

function observeReveals() {
  document
    .querySelectorAll('.stats-cell, .milestone-item')
    .forEach((el) => revealObserver?.observe(el))
}
</script>

<template>
  <div class="about-page" role="main" aria-label="关于 CygnusX">
    <!-- 深空背景 -->
    <div class="space-bg" />

    <!-- 常驻呼吸高光：保证内容周围始终有柔和辉光，不随流星/闪烁而消失 -->
    <div class="ambient-core" />

    <!-- 星河/星云带 -->
    <div class="milky-way">
      <div
        v-for="n in nebulaLayers"
        :key="n.id"
        class="nebula-band"
        :style="{
          top: n.top + '%',
          left: n.left + '%',
          width: n.width + '%',
          height: n.height + '%',
          '--base-opacity': n.opacity,
          animationDelay: n.delay + 's',
          animationDuration: n.duration + 's',
        }"
      />
    </div>

    <!-- 星空 -->
    <div class="starfield">
      <div
        v-for="s in stars"
        :key="s.id"
        class="star"
        :class="{ 'has-cross': s.hasCross }"
        :style="{
          top: s.top + '%',
          left: s.left + '%',
          width: s.size + 'px',
          height: s.size + 'px',
          '--star-opacity': s.opacity,
          animationDelay: s.delay + 's',
          animationDuration: s.duration + 's',
          '--cross-scale': s.crossScale
        }"
      ></div>
    </div>

    <!-- 流星 -->
    <div class="shooting-stars">
      <div
        v-for="ss in shootingStars"
        :key="ss.id"
        class="shooting-star"
        :style="{
          top: ss.top + '%',
          left: ss.left + '%',
          animationDelay: ss.delay + 's',
          animationDuration: ss.duration + 's',
          '--star-scale': ss.scale
        }"
      />
    </div>

    <!-- 浮动光球 -->
    <div class="orb orb-1" />
    <div class="orb orb-2" />

    <!-- 内容 -->
    <div class="about-content">
      <header class="about-hero">
        <!-- 旋转行星（点击触发隐藏彩蛋） -->
        <div class="planet-wrap" style="cursor: pointer" title="点我看看？" @click="openEasterEgg">
          <div class="planet" />
          <div class="planet-ring" />
          <div class="planet-orbit" aria-hidden="true"><span class="planet-moon" /></div>
        </div>

        <h1 class="about-title">CygnusX BioOps</h1>
        <p class="about-slogan">FROM STARDUST, TO DISCOVERY</p>
        <p class="about-subtitle">面向生命科学的受控科研 Agent 与可信计算交付基础设施</p>
        <p class="about-lead">从科学问题出发，找到或导入数据，组织受控分析，核验结果与文献证据，将每一次研究沉淀为可复用、可追溯的科研资产。</p>

        <ul class="hero-chips" aria-label="平台能力">
          <li v-for="chip in heroChips" :key="chip">{{ chip }}</li>
        </ul>

        <div class="about-actions">
          <NButton class="about-btn-primary" size="large" @click="router.push('/flows')">
            <template #icon>
              <NIcon><RocketOutline /></NIcon>
            </template>
            开始分析
          </NButton>
          <NButton
            v-if="siteConfig.platformGithub"
            class="about-btn-ghost"
            size="large"
            tag="a"
            :href="siteConfig.platformGithub"
            target="_blank"
            rel="noopener noreferrer"
          >
            <template #icon>
              <NIcon><LogoGithub /></NIcon>
            </template>
            GitHub
          </NButton>
        </div>

        <button class="scroll-hint" aria-label="向下了解详情" @click="scrollToSection('values')">
          <NIcon :size="20"><ChevronDownOutline /></NIcon>
        </button>
      </header>

      <section class="stats-section" aria-label="平台核心机制">
        <ul class="stats-band">
          <li
            v-for="(stat, i) in stats"
            :key="stat.label"
            class="stats-cell"
            :style="{ transitionDelay: `${i * 80}ms` }"
          >
            <span class="stats-value">{{ stat.value }}</span>
            <span class="stats-label">{{ stat.label }}</span>
          </li>
        </ul>
      </section>

      <section id="values" class="about-section" aria-labelledby="values-title">
        <p class="section-kicker">FROM QUESTION TO EVIDENCE</p>
        <h2 id="values-title">从科研问题到可复现的科学证据</h2>
        <p class="section-intro">让科研人员把时间花在科学问题上。公共数据发现与已有数据导入，共同进入项目上下文，连接标准分析、增量探索与结果核验。</p>
        <div class="value-grid">
          <template v-for="(stream, i) in valueStreams" :key="stream.number">
            <article class="value-card">
              <div class="value-card__top">
                <span class="value-card__num">{{ stream.number }}</span>
                <span class="value-card__icon"><NIcon :size="20"><component :is="stream.icon" /></NIcon></span>
              </div>
              <h3>{{ stream.title }}</h3>
              <dl class="value-io">
                <div class="value-io__row">
                  <dt>输入</dt>
                  <dd>{{ stream.input }}</dd>
                </div>
                <div class="value-io__row">
                  <dt>产出</dt>
                  <dd>{{ stream.output }}</dd>
                </div>
              </dl>
            </article>
            <span v-if="i < valueStreams.length - 1" class="value-connector" aria-hidden="true">
              <svg width="28" height="12" viewBox="0 0 28 12" fill="none">
                <path d="M0 6h24m0 0-5-5m5 5-5 5" stroke="rgba(255,255,255,0.2)" stroke-width="1" />
              </svg>
            </span>
          </template>
        </div>
      </section>

      <section id="resources" class="about-section" aria-labelledby="resources-title">
        <p class="section-kicker">CONNECTED RESEARCH RESOURCES</p>
        <h2 id="resources-title">连接数据、知识与文献证据</h2>
        <p class="section-intro">通过 MCP 将公共组学库、基因与蛋白知识库、结构与通路资源、文献和靶点证据带入科研上下文，为数据选择和结果解读提供依据。</p>
        <div class="resource-grid">
          <article v-for="resource in researchResources" :key="resource.title" class="resource-card">
            <h3>{{ resource.title }}</h3>
            <ul class="resource-sources" :aria-label="`${resource.title}资源`">
              <li v-for="source in resource.sources" :key="source">{{ source }}</li>
            </ul>
            <p>{{ resource.text }}</p>
            <p v-if="resource.note" class="resource-note">{{ resource.note }}</p>
          </article>
        </div>
        <p class="section-note">以上为当前工具覆盖的查询范围，以只读检索、元数据与证据查询为主。具体开放范围取决于部署版本、Agent 授权和外部服务状态；研究目录查询不等同于表达矩阵下载或定量分析。</p>
      </section>

      <section id="working-model" class="about-section" aria-labelledby="working-model-title">
        <p class="section-kicker">AGENT × SKILL × FLOW</p>
        <h2 id="working-model-title">让科研方法可执行、可核验、可复用</h2>
        <p class="section-intro">Agent 组织任务，Skill 约束专业动作，Flow 承载标准计算。人提出问题、判断证据，系统承担重复的工程工作并记录研究过程。</p>
        <div class="model-grid">
          <article v-for="item in workingModel" :key="item.name" class="resource-card">
            <span class="status-label">{{ item.name }}</span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
          </article>
        </div>
        <p class="section-note">正式分析由 AI 调度经过审核的工具与流程；OmicStudio 支持在能力受限的隔离沙箱内进行代码探索，探索结果须经过相应检查后进入正式交付。</p>
        <ul class="research-entries" aria-label="四级科研入口">
          <li v-for="entry in researchEntries" :key="entry.level">
            <span class="status-label">{{ entry.level }}</span>
            <h3>{{ entry.name }}</h3>
            <p>{{ entry.text }}</p>
          </li>
        </ul>
      </section>

      <section id="ecosystem" class="about-section" aria-labelledby="ecosystem-title">
        <p class="section-kicker">AI4S ECOSYSTEM</p>
        <h2 id="ecosystem-title">CygnusX AI4S Ecosystem</h2>
        <p class="section-intro">平台以共享项目上下文组织数据发现、获取、标准分析与报告，各生态组件提供专业能力，FlowFrame 提供共同的流程与接入约定。</p>
        <div class="ecosystem-band">
          <div class="ecosystem-grid">
            <article class="ecosystem-card ecosystem-card--platform">
              <span class="status-label">平台底座</span>
              <h3>CygnusX BioOps</h3>
              <p>连接项目、Agent、权限、任务、数据与运行记录，组织产物归档和证据关联，让分析过程可以追溯、研究经验能够传承。</p>
            </article>
            <article v-for="item in ecosystemModules" :key="item.name" class="ecosystem-card">
              <div class="ecosystem-card__toprow">
                <img v-if="item.logo" class="ecosystem-card__logo" :src="item.logo" :alt="`${item.name} 图标`" width="48" height="48" />
                <span v-else class="value-card__icon" aria-hidden="true"><NIcon :size="24"><RocketOutline /></NIcon></span>
                <span class="status-label">{{ item.status }}</span>
              </div>
              <h3><a :href="item.href" target="_blank" rel="noopener noreferrer">{{ item.name }} ↗</a></h3>
              <p>{{ item.text }}</p>
            </article>
          </div>
        </div>
        <p class="section-note">RNA-seq 与 ATAC-seq 流程已在实验室部署与验证。生态组件按各自版本演进，平台集成与开放状态以当前部署为准；多 Agent 协作和完整证据交付链仍按功能门禁逐项验收。</p>
      </section>

      <!-- 演进历程：未来愿景在上，当前阶段以品牌色标记 -->
      <section class="about-section milestones-section" aria-labelledby="milestones-title">
        <p class="section-kicker">MILESTONES</p>
        <h2 id="milestones-title">从 OmicHub 到 CygnusX</h2>
        <ol class="milestone-list">
          <li
            v-for="(milestone, i) in milestones"
            :key="i"
            class="milestone-item"
            :class="{ 'milestone-item--latest': milestone.time === '持续演进' }"
          >
            <span class="milestone-dot" aria-hidden="true" />
            <div class="milestone-body">
              <span class="milestone-time">{{ milestone.time }}</span>
              <h3>{{ milestone.title }}</h3>
              <p>{{ milestone.text }}</p>
            </div>
          </li>
        </ol>
      </section>

      <section class="about-section vision-section" aria-labelledby="vision-title">
        <p class="section-kicker">OUR VISION</p>
        <div class="about-quote-box vision-panel">
          <h2 id="vision-title" class="about-quote-title">We are made of star-stuff.</h2>
          <p class="about-quote">我们只是借用了宇宙中的这些碳、氢、氧原子几十年，用它们去短暂地体验了一次这个世界。组成我们大脑和身体的每一个原子，都来自几十亿年前远古恒星内部的核聚变爆炸。当生命结束时，我们并没有化为虚无，我们只是回到了那个浩瀚的宇宙中，换了一种方式继续存在。</p>
          <p class="vision-signoff">从星辰中来，向发现而去。</p>
        </div>
      </section>

      <footer class="about-footer-v2">
        <div class="footer-cols">
          <div class="footer-brand">
            <span class="footer-logo">CygnusX</span>
            <p>面向生命科学的智能科研基础设施，让科学问题连接可复现的计算与可核验的证据。</p>
          </div>
          <nav class="footer-links" aria-label="页脚导航">
            <RouterLink to="/dashboard">控制台</RouterLink>
            <RouterLink to="/flows">分析中心</RouterLink>
            <RouterLink to="/knowledge">实验室知识库</RouterLink>
            <a v-if="siteConfig.platformGithub" :href="siteConfig.platformGithub" target="_blank" rel="noopener">GitHub</a>
          </nav>
          <div v-if="siteConfig.platformEmail" class="footer-contact">
            <p>
              Contact:
              <a
                :href="`mailto:${siteConfig.platformEmail}`"
                class="footer-contact-link"
              >{{ siteConfig.platformEmail }}</a>
            </p>
          </div>
        </div>
        <div class="footer-bottom">
          <span>© 2026 CygnusX BioOps · 华中农业大学园艺林学学院</span>
          <span v-if="siteConfig.platformAuthor" class="footer-credit">Designed by {{ siteConfig.platformAuthor }}</span>
        </div>
      </footer>
    </div>

    <!-- 隐藏彩蛋弹窗：点击蓝色星球触发 -->
    <div
      v-if="showEasterEgg"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      @click="showEasterEgg = false"
    >
      <!-- 弹窗主体：深色毛玻璃，阻止点击冒泡到遮罩层 -->
      <div
        class="relative w-fit max-w-[90vw] rounded-2xl border border-white/10 bg-[#0B1121]/70 px-10 py-8 shadow-2xl backdrop-blur-md"
        @click.stop
      >
        <!-- 毛玻璃质感关闭按钮：悬浮光晕 + 旋转缩放动画 -->
        <button
          class="eg-close-btn group absolute right-4 top-4 flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border border-white/15 bg-white/5 text-slate-300 backdrop-blur-sm transition-all duration-300 hover:border-cyan-300/60 hover:bg-cyan-300/10 hover:text-cyan-200 hover:shadow-[0_0_14px_rgba(103,232,249,0.55)]"
          aria-label="关闭"
          @click="showEasterEgg = false"
        >
          <span
            class="text-lg font-light leading-none transition-transform duration-300 group-hover:scale-110 group-hover:rotate-90"
          >
            ✕
          </span>
        </button>

        <img
          :src="catEarthLogo"
          alt="星际守护者"
          class="mx-auto block h-48 w-auto object-contain"
        />
        <p class="mt-6 max-w-[36rem] text-center text-lg font-bold leading-relaxed break-words text-white">
          {{ siteConfig.easterEggMessage }}
        </p>
      </div>
    </div>

    <!-- 悬浮召唤按钮：召唤星际猫咪 -->
    <button
      class="summon-cat-btn"
      :aria-label="siteConfig.easterEggButtonText"
      @click="summonCat"
    >
      <span class="summon-cat-btn__icon">🐾</span>
      <span class="summon-cat-btn__text">{{ siteConfig.easterEggButtonText }}</span>
    </button>

    <!-- 猫爪足迹覆盖层由全局 CatPawsOverlay（App.vue）渲染，本页不再自建 -->
  </div>
</template>

<style scoped>
/* 关闭按钮：空闲呼吸光晕，悬停时由 Tailwind 接管旋转/缩放/高亮 */
.eg-close-btn {
  animation: eg-close-pulse 2.4s ease-in-out infinite;
}
@keyframes eg-close-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(103, 232, 249, 0);
  }
  50% {
    box-shadow: 0 0 10px 1px rgba(103, 232, 249, 0.28);
  }
}
@keyframes shooting {
  0% {
    transform: translateX(0) translateY(0) rotate(35deg) scaleX(0) scale(var(--star-scale, 1));
    opacity: 0;
  }
  3% {
    opacity: 0.72;
    transform: translateX(36px) translateY(25px) rotate(35deg) scaleX(0.82) scale(var(--star-scale, 1));
  }
  9% {
    opacity: 0.62;
    transform: translateX(330px) translateY(231px) rotate(35deg) scaleX(1) scale(var(--star-scale, 1));
  }
  13% {
    transform: translateX(460px) translateY(322px) rotate(35deg) scaleX(0.42) scale(var(--star-scale, 1));
    opacity: 0;
  }
  100% {
    transform: translateX(600px) translateY(420px) rotate(35deg) scaleX(0.6) scale(var(--star-scale, 1));
    opacity: 0;
  }
}

/* 呼吸下限抬高（0.87）：配合负延迟，星点最暗时也接近满亮，
   夜空高光"恒定"，不会因集体走到波谷而发平。 */
@keyframes twinkle {
  0%, 100% {
    opacity: calc(var(--star-opacity, 0.55) * 0.87);
    transform: translate(-50%, -50%) scale(0.97);
  }
  50% {
    opacity: var(--star-opacity, 0.55);
    transform: translate(-50%, -50%) scale(1.04);
  }
}

/* 十字高光用更浅的呼吸下限（0.93），星芒始终清晰，不会闪没 */
@keyframes twinkleCross {
  0%, 100% {
    opacity: calc(var(--star-opacity, 0.7) * 0.93);
    transform: translate(-50%, -50%) scale(0.97);
  }
  50% {
    opacity: var(--star-opacity, 0.7);
    transform: translate(-50%, -50%) scale(1.06);
  }
}

@keyframes nebulaDrift {
  /* 不透明固定（仅 transform 极慢漂移）：星云高光被"钉住"，不会随相位发平而消失 */
  0%, 100% { transform: translateX(0) scale(1); opacity: var(--base-opacity, 0.7); }
  50% { transform: translateX(1.2%) scale(1.01); opacity: var(--base-opacity, 0.7); }
}

@keyframes ringSheen {
  0% { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}

@keyframes orbitSpin {
  from { transform: rotateX(66deg) rotateZ(0deg); }
  to { transform: rotateX(66deg) rotateZ(360deg); }
}

.about-page {
  position: relative;
  min-height: calc(100vh - 56px);
  margin: calc(-1 * var(--page-padding));
  display: flex;
  align-items: center;
  justify-content: center;
  /* overflow:clip 不创建滚动容器：.milky-way 旋转放大后的包围盒超出底部时
     不会被算成内层滚动区（旧值 auto 曾制造 ~350px 幽灵滚动，滚轮要先滚完
     内层空白区才轮到外层 naive 滚动条）。不支持 clip 的浏览器回退为 hidden/auto。 */
  overflow-x: hidden;
  overflow-y: auto;
  overflow: clip;
  background: #11193c;
}

/* 深空蓝紫：以低饱和星云保留层次，不干扰正文阅读。 */
.space-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 56% 46% at 50% 26%, rgba(110, 140, 255, 0.16) 0%, transparent 60%),
    radial-gradient(ellipse at 16% 16%, rgba(90, 120, 255, 0.14) 0%, transparent 44%),
    radial-gradient(ellipse at 86% 82%, rgba(130, 98, 214, 0.14) 0%, transparent 48%),
    radial-gradient(ellipse at 6% 90%, rgba(80, 110, 220, 0.10) 0%, transparent 42%),
    radial-gradient(ellipse at 95% 14%, rgba(120, 104, 210, 0.10) 0%, transparent 42%),
    linear-gradient(150deg, #141d44 0%, #1c2556 50%, #221d4e 100%);
}

/* 常驻高光：在内容正中、右中、左上各铺一团柔光，不透明固定、绝不消失，
   让"几处高光"成为恒定底色，流星只是在其上叠加的瞬时光迹。 */
.ambient-core {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 60% 44% at 50% 22%, rgba(120, 150, 255, 0.32) 0%, transparent 62%),
    radial-gradient(ellipse 44% 42% at 82% 60%, rgba(152, 110, 236, 0.28) 0%, transparent 64%),
    radial-gradient(ellipse 40% 40% at 14% 26%, rgba(96, 130, 255, 0.28) 0%, transparent 62%);
  filter: blur(8px);
  /* screen 加性提亮：让辉光在较亮的暮光底上依然醒目成形（底越亮越需要 screen） */
  mix-blend-mode: screen;
  animation: ambientCoreBreathe 11s ease-in-out infinite;
  will-change: opacity, transform;
}
@keyframes ambientCoreBreathe {
  /* 不透明固定，仅 scale 微呼吸：辉光"钉住"为恒定底色，流星只是其上的瞬时光迹 */
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.03); }
}

/* 星河/星云带 */
.milky-way {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  transform: rotate(-15deg) scale(1.2);
}

.nebula-band {
  position: absolute;
  border-radius: 9999px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(150, 170, 255, 0.40) 25%,
    rgba(190, 150, 255, 0.52) 50%,
    rgba(150, 170, 255, 0.34) 75%,
    transparent 100%
  );
  filter: blur(40px);
  /* screen 加性：斜向星云在亮底上成为清晰、恒定的极光带 */
  mix-blend-mode: screen;
  animation: nebulaDrift ease-in-out infinite;
  --base-opacity: 0.85;
}

/* 星空 */
.starfield {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}

.star {
  position: absolute;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 0 4px 1px rgba(190, 209, 255, 0.34);
  animation: twinkle linear infinite alternate;
  transform: translate(-50%, -50%);
}

/* 十字星芒单独走 twinkleCross：下限更高，星芒始终清晰，分布稳定 */
.star.has-cross {
  animation-name: twinkleCross;
}

.star.has-cross::before,
.star.has-cross::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  pointer-events: none;
  transform: translate(-50%, -50%) scale(var(--cross-scale));
  /* 给星芒叠一层柔光晕，即便呼吸到低点也保留"高光"印象 */
  filter: drop-shadow(0 0 3px rgba(186, 208, 255, 0.55));
}

.star.has-cross::before {
  width: 40px;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(107, 141, 214, 0.8) 40%,
    rgba(255, 255, 255, 1) 50%,
    rgba(107, 141, 214, 0.8) 60%,
    transparent 100%
  );
}

.star.has-cross::after {
  width: 1px;
  height: 40px;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(107, 141, 214, 0.8) 40%,
    rgba(255, 255, 255, 1) 50%,
    rgba(107, 141, 214, 0.8) 60%,
    transparent 100%
  );
}

/* 流星 */
.shooting-stars {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}
.shooting-star {
  position: absolute;
  width: 112px;
  height: 1px;
  border-radius: 50%;
  opacity: 0;
  animation: shooting linear infinite;
  transform-origin: left center;
}
.shooting-star::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to left, rgba(255, 255, 255, 0.74), rgba(147, 171, 255, 0.42), transparent);
  border-radius: 50%;
  filter: drop-shadow(0 0 4px rgba(194, 211, 255, 0.52));
}
.shooting-star::after {
  content: '';
  position: absolute;
  right: -3px;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 8px 1px rgba(255, 255, 255, 0.6), 0 0 14px 3px rgba(128, 153, 255, 0.30);
}

/* 浮动光球：常驻柔光，缓慢漂移+呼吸，作为边缘恒定的高光 */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.3;
  mix-blend-mode: screen;
  pointer-events: none;
  z-index: 0;
  animation: orbBreathe 14s ease-in-out infinite;
  will-change: transform, opacity;
}
.orb-1 {
  width: 280px;
  height: 280px;
  background: #5b7cff;
  top: 8%;
  left: 3%;
}
.orb-2 {
  width: 220px;
  height: 220px;
  background: #8b6be8;
  bottom: 10%;
  right: 5%;
  animation-delay: -6s;
}
@keyframes orbBreathe {
  /* 不透明固定，仅漂移+缩放：边缘高光恒定，不随呼吸发平 */
  0%, 100% { opacity: 0.3; transform: translate3d(0, 0, 0) scale(1); }
  50% { opacity: 0.3; transform: translate3d(2%, -2%, 0) scale(1.08); }
}

/* 内容容器 */
.about-content {
  position: relative;
  z-index: 2;
  max-width: 720px;
  width: 100%;
  padding: 40px 32px;
  text-align: center;
}

/* 旋转行星：preserve-3d 让"球体圆盘(z=0)"与"倾斜 66° 的环/轨平面"
   共享同一 3D 渲染上下文，按真实深度逐像素排序——于是卫星公转到后弧时
   被不透明球体遮挡、到前弧时掠过球面，光环也呈土星式前后包裹（后弧藏于球后、
   前弧浮于球前）。perspective 给环/卫星加轻微近大远小的纵深，球体本身在 z=0 不受影响。
   注：祖先 .about-page 的 overflow:hidden 只把整个 wrap 压平合成到页面，
   wrap 内部这套 3D 遮挡在压平前已算好，故不受影响。 */
.planet-wrap {
  position: relative;
  width: 140px;
  height: 140px;
  margin: 0 auto 34px;
  transform-style: preserve-3d;
  perspective: 520px;
}
/* 发光行星：固定左上受光 + 大气辉光，静态球体（不整球自转，避免明暗面翻滚）。
   完全不透明，在 3D 上下文里充当"遮挡体"——后弧卫星/环在此圆盘之后即不可见。 */
.planet {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: radial-gradient(circle at 34% 30%, #b6c6ff 0%, #7189ef 32%, #3450c4 62%, #141a52 100%);
  box-shadow:
    0 0 22px rgba(120, 150, 255, 0.45),
    0 0 50px rgba(92, 122, 232, 0.25),
    inset -7px -8px 16px rgba(0, 0, 0, 0.5),
    inset 4px 4px 10px rgba(186, 204, 255, 0.28);
}
/* 光环：mask 裁出的连续倾斜渐变真环（66° 不再压成线），流光靠背景位移而非几何旋转。
   与球体同处 3D 上下文：环平面被球体圆盘沿水平中线切开，自动呈现土星式前后遮挡。 */
.planet-ring {
  position: absolute;
  inset: -18px;
  border-radius: 50%;
  transform: rotateX(66deg);
  padding: 2.5px;
  background: linear-gradient(
    115deg,
    rgba(205, 220, 255, 0.9) 0%,
    rgba(150, 172, 255, 0.12) 38%,
    rgba(176, 150, 255, 0.10) 62%,
    rgba(210, 222, 255, 0.85) 100%
  );
  background-size: 220% 220%;
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  mask-composite: exclude;
  filter: drop-shadow(0 0 4px rgba(150, 180, 255, 0.55));
  animation: ringSheen 7s linear infinite;
}
/* 沿环轨公转的小卫星：轨道与光环同尺寸同倾斜，故目视正好沿环椭圆运行。
   公转时 z 值正负交替：后弧落入球体圆盘之后被真实遮挡，前弧掠过球面，
   穿过球缘时由平面相交几何裁剪，呈现平滑"钻到球后/探出球前"的掠过感。 */
.planet-orbit {
  position: absolute;
  inset: -18px;
  border-radius: 50%;
  transform: rotateX(66deg);
  pointer-events: none;
  animation: orbitSpin 9s linear infinite;
}
.planet-moon {
  position: absolute;
  top: -4px;
  left: 50%;
  width: 10px;
  height: 10px;
  margin-left: -5px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #ffffff, #c2d4ff 55%, #7f9bf0 100%);
  box-shadow: 0 0 8px 2px rgba(184, 206, 255, 0.7);
}

/* 标题 */
.about-title {
  font-size: 56px;
  font-weight: 700;
  margin: 0 0 10px;
  letter-spacing: 1px;
  background: linear-gradient(90deg, #d9e2ff, #a8bbff, #d9e2ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.about-subtitle {
  font-size: 22px;
  color: #d6def8;
  margin: 0 0 28px;
  font-weight: 500;
}

/* 引言：无边框磨砂"题记"块——去掉整圈亮描边/白内高光/hover 白闪（旧版像被框选），
   仅以顶/底两条两端渐隐的细光痕 + 柔投影成形；正文靠文字阴影在星场上保持可读。 */
.about-quote-box {
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(26, 36, 80, 0.46) 0%, rgba(17, 25, 60, 0.32) 100%);
  backdrop-filter: saturate(140%) blur(14px);
  -webkit-backdrop-filter: saturate(140%) blur(14px);
  border: 0;
  box-shadow: 0 14px 44px rgba(6, 10, 34, 0.42);
  border-radius: 16px;
  padding: 26px 30px 24px;
  margin-bottom: 28px;
}
/* 顶/底渐隐光痕：有意为之的"题记框"线索，而非矩形描边 */
.about-quote-box::before,
.about-quote-box::after {
  content: '';
  position: absolute;
  left: 14%;
  right: 14%;
  height: 1px;
  pointer-events: none;
}
.about-quote-box::before {
  top: 0;
  background: linear-gradient(90deg, transparent, rgba(178, 204, 255, 0.5), transparent);
}
.about-quote-box::after {
  bottom: 0;
  background: linear-gradient(90deg, transparent, rgba(150, 178, 255, 0.26), transparent);
}

/* 题记英文行：对齐权威 StardustQuote 的 gilded 流光 + 衬线显示体，
   与正文无衬线构成"展示体/正文体"配对（§33.1#5）；辉光恒定，仅流光平移，不呼吸、不消失。 */
.about-quote-title {
  font-family: Georgia, 'Times New Roman', 'Songti SC', serif;
  font-size: 18px;
  font-weight: 600;
  font-style: italic;
  letter-spacing: 1.5px;
  margin: 0 0 18px;
  padding-bottom: 14px;
  position: relative;
  text-align: center;
  text-indent: 0;
  background: linear-gradient(
    90deg,
    rgba(238, 248, 255, 0.92) 0%,
    #ffffff 24%,
    #6fb4ff 50%,
    #ffffff 76%,
    rgba(238, 248, 255, 0.92) 100%
  );
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 0 10px rgba(112, 181, 255, 0.55));
  animation: shimmer 10s linear infinite;
}
/* 标题下一道居中渐隐细分隔线：编辑式题记节奏 */
.about-quote-title::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  width: 56px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(150, 185, 255, 0.7), transparent);
}

/* gilded 流光：与 StardustQuote 同源（scoped 样式不跨组件，此处本地定义） */
@keyframes shimmer {
  0% { background-position: 200% center; }
  100% { background-position: -200% center; }
}

.about-quote {
  font-size: 14px;
  line-height: 1.95;
  color: #eef2ff;
  text-align: justify;
  margin: 0;
  text-indent: 2em;
  /* 文字阴影晕：在更亮的星场/磨砂底上保证正文对比（对齐 StardustQuote 做法） */
  text-shadow:
    0 1px 2px rgba(4, 8, 24, 0.55),
    0 2px 10px rgba(4, 8, 24, 0.4);
}

/* 操作按钮 */
.about-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 32px;
}

/* 渐变背景上的按钮：遵循设计规范 §5.7（白底主按钮 + 毛玻璃次按钮） */
.n-button.about-btn-primary {
  background-color: rgba(255, 255, 255, 0.95);
  color: #4C6FFF;
  font-weight: 700;
  letter-spacing: 0.3px;
  border: none;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.3), 0 4px 20px rgba(0, 0, 0, 0.2);
  transition: all 0.2s ease;
}
.n-button.about-btn-primary:hover,
.n-button.about-btn-primary:focus {
  background-color: #ffffff;
  color: #4C6FFF;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.45), 0 6px 24px rgba(0, 0, 0, 0.22);
  transform: translateY(-1px);
}
.n-button.about-btn-ghost {
  background-color: rgba(255, 255, 255, 0.15);
  color: #ffffff;
  font-weight: 700;
  letter-spacing: 0.3px;
  border: 1.5px solid rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
  transition: all 0.2s ease;
}
.n-button.about-btn-ghost:hover,
.n-button.about-btn-ghost:focus {
  background-color: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.8);
  color: #ffffff;
}
/* Naive 的描边由内部两个元素绘制，隐藏以免与外发光叠成两圈（规范 §5.7 踩坑记录） */
.about-btn-primary :deep(.n-button__border),
.about-btn-primary :deep(.n-button__state-border),
.about-btn-ghost :deep(.n-button__border),
.about-btn-ghost :deep(.n-button__state-border) {
  display: none;
}
.about-btn-primary :deep(.n-button__icon),
.about-btn-ghost :deep(.n-button__icon) {
  margin-right: 8px;
}

/* 减少透明度：毛玻璃回退为实色（规范 §4.2） */
@media (prefers-reduced-transparency: reduce) {
  .about-quote-box {
    background: #1b2552;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }
  .ecosystem-card {
    background: #1e2550;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }
  .n-button.about-btn-ghost {
    background-color: #26366f;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }
}

/* ===== 页脚 v2：三列 + 底行（P1-5） ===== */
.about-footer-v2 {
  margin-top: calc(var(--section-gap-loose) - var(--section-gap));
  margin-left: -24px;
  margin-right: -24px;
  padding: 44px 24px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.25);
  text-align: left;
}
.footer-cols {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: 32px;
  max-width: 1320px;
  margin: 0 auto;
}
.footer-logo { font-size: 18px; font-weight: 700; color: #ffffff; }
.footer-brand p { margin: 10px 0 0; font-size: 13px; line-height: 1.7; color: rgba(255, 255, 255, 0.55); }
.footer-links { display: flex; flex-direction: column; gap: 10px; }
.footer-links a {
  width: fit-content;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  text-decoration: none;
  transition: color 0.2s ease;
}
.footer-links a:hover { color: rgba(255, 255, 255, 0.85); }
.footer-contact {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
}
.footer-contact-link { color: inherit; text-decoration: none; transition: color 0.2s ease; }
.footer-contact-link:hover { color: rgba(255, 255, 255, 0.85); }
.footer-bottom {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  justify-content: space-between;
  max-width: 1320px;
  margin: 32px auto 0;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  text-align: left;
}

@media (max-width: 640px) {
  .about-content { padding: 24px 20px; }
  .about-title { font-size: 36px; }
  .about-subtitle { font-size: 18px; }
  .about-quote { font-size: 13px; }
  .about-quote-title { font-size: 14px; margin-bottom: 10px; }
  .about-quote-box { padding: 16px 20px; }
  .about-actions {
    flex-direction: column;
    align-items: center;
  }
}

/* ===== 悬浮召唤按钮 ===== */
.summon-cat-btn {
  position: fixed;
  right: 36px;
  bottom: 36px;
  z-index: 90;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 22px;
  border: none;
  border-radius: 9999px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.45);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  animation: summon-pulse 2.8s ease-in-out infinite;
}
.summon-cat-btn:hover {
  transform: translateY(-2px) scale(1.04);
  box-shadow: 0 8px 28px rgba(118, 75, 162, 0.6);
}
.summon-cat-btn:active {
  transform: translateY(0) scale(0.98);
}
.summon-cat-btn__icon {
  font-size: 18px;
  display: inline-block;
  animation: paw-wiggle 1.6s ease-in-out infinite;
}
@keyframes summon-pulse {
  0%, 100% { box-shadow: 0 4px 20px rgba(102, 126, 234, 0.35); }
  50% { box-shadow: 0 4px 28px rgba(118, 75, 162, 0.65); }
}
@keyframes paw-wiggle {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(-12deg); }
  75% { transform: rotate(12deg); }
}

@media (max-width: 640px) {
  .summon-cat-btn {
    right: 16px;
    bottom: 16px;
    padding: 10px 16px;
    font-size: 13px;
  }
}

/* 减少动画：冻结背景动效，但保留静态高光，夜空不发平 */
@media (prefers-reduced-motion: reduce) {
  .nebula-band,
  .orb,
  .ambient-core,
  .star,
  .star.has-cross,
  .shooting-star,
  .planet-ring,
  .planet-orbit {
    animation: none !important;
  }
  .ambient-core { opacity: 1; }
  .orb { opacity: 0.3; }
  /* 减少动画下用各自"呼吸稳态值"钉住透明度，静态夜空与动效夜空观感一致，
     不会因动画关闭而退回基础 opacity 1.0 的过曝满亮。 */
  .star { opacity: var(--star-opacity, 0.55); }
  .star.has-cross { opacity: var(--star-opacity, 0.7); }
  .nebula-band { opacity: var(--base-opacity, 0.85); }
}
/* ===== 布局骨架（P0）：1320 容器 + 间距两档 token ===== */
.about-content {
  --section-gap: 96px;
  --section-gap-loose: 140px;
  max-width: 1320px;
  width: 100%;
  margin: 0 auto;
  padding: 48px 24px 72px;
  display: flex;
  flex-direction: column;
  gap: var(--section-gap);
  text-align: center;
}

/* Hero：整屏首屏区，垂直居中 + 底部下滑提示 */
.about-hero {
  position: relative;
  min-height: min(680px, calc(100vh - 100px));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 0 56px;
}
/* 入场：轻微上浮浮现，逐个错开 */
.about-hero > * {
  animation: hero-rise 0.7s cubic-bezier(0.2, 0.8, 0.2, 1) both;
}
.about-hero > *:nth-child(2) { animation-delay: 0.06s; }
.about-hero > *:nth-child(3) { animation-delay: 0.12s; }
.about-hero > *:nth-child(4) { animation-delay: 0.18s; }
.about-hero > *:nth-child(5) { animation-delay: 0.24s; }
.about-hero > *:nth-child(6) { animation-delay: 0.3s; }
.about-hero > *:nth-child(7) { animation-delay: 0.36s; }
@keyframes hero-rise {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Hero 能力标签：胶囊毛玻璃 */
.hero-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin: 0 0 30px;
  padding: 0;
  list-style: none;
}
.hero-chips li {
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 14px;
  color: #dbe4ff;
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(178, 204, 255, 0.24);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

/* 下滑提示：呼吸浮动的小圆钮，引导用户向下滚动 */
.scroll-hint {
  position: absolute;
  left: 50%;
  bottom: 6px;
  transform: translateX(-50%);
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 50%;
  cursor: pointer;
  color: #cdd9ff;
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(178, 204, 255, 0.28);
  transition: background 0.2s ease, color 0.2s ease;
  animation: hint-bounce 2.2s ease-in-out infinite;
}
.scroll-hint:hover {
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
}
@keyframes hint-bounce {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(6px); }
}

.about-slogan { margin: 0 0 20px; color: #b9c9ff; font-size: 15px; letter-spacing: .2em; font-weight: 600; }
.about-lead { max-width: 820px; margin: 0 auto 30px; color: #d6def8; font-size: 17px; line-height: 1.8; }

/* ===== 章节骨架：统一字阶（P0-3 / P2-2） ===== */
.about-section { scroll-margin-top: 24px; width: 100%; max-width: 1320px; margin: 0 auto; text-align: left; }
.about-section h2 { margin: 0 0 12px; color: #f2f5ff; font-size: 36px; font-weight: 700; text-align: center; }
.section-kicker { margin: 0 0 12px; color: rgba(255, 255, 255, 0.55); font-size: 13px; letter-spacing: .2em; text-align: center; }
.section-intro { max-width: 680px; margin: 0 auto 36px; color: #c4cee8; font-size: 16px; line-height: 1.7; text-align: center; }
.section-note { max-width: 900px; margin: 24px auto 0; color: #c4cee8; font-size: 14px; line-height: 1.8; text-align: center; }
.resource-grid, .model-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.model-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.resource-card {
  min-width: 0;
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  background: rgba(30, 37, 80, 0.9);
}
.resource-card h3, .research-entries h3 { margin: 0 0 14px; color: #f2f5ff; font-size: 18px; }
.resource-card > .status-label, .research-entries .status-label { margin-bottom: 16px; }
.resource-card p, .research-entries p { margin: 0; color: #e6e9f2; font-size: 14px; line-height: 1.8; }
.resource-sources { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 18px; padding: 0; list-style: none; }
.resource-sources li { padding: 4px 10px; border-radius: 6px; color: #dbe4ff; background: rgba(255, 255, 255, 0.08); font-size: 13px; }
.resource-card .resource-note { margin-top: 12px; color: #c4cee8; font-size: 13px; }
.research-entries { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px; margin: 36px 0 0; padding: 0; list-style: none; }
.research-entries li { min-width: 0; padding: 20px 0; border-top: 1px solid rgba(255, 255, 255, 0.18); }
.ecosystem-card h3 a { color: inherit; text-decoration: none; overflow-wrap: anywhere; }
.ecosystem-card h3 a:hover { color: #b9c9ff; text-decoration: underline; }
.ecosystem-card h3 a:focus-visible { outline: 2px solid var(--arco-primary); outline-offset: 3px; }
/* 生态区标题三件套常压在漂移亮星云上：叠文字阴影保证可读（与 .about-quote 同款） */
#ecosystem .section-kicker,
#ecosystem h2,
#ecosystem .section-intro {
  text-shadow:
    0 1px 2px rgba(4, 8, 24, 0.55),
    0 2px 10px rgba(4, 8, 24, 0.4);
}

/* ===== 指标条（P1-1）：1100 居中容器 + 4 格等分 + 竖分隔线 ===== */
.stats-section { width: 100%; padding: 64px 0; }
.stats-band {
  list-style: none;
  margin: 0 auto;
  padding: 0;
  max-width: 1100px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
}
.stats-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
}
.stats-cell + .stats-cell { border-left: 1px solid rgba(255, 255, 255, 0.08); }
.stats-value { font-size: 28px; font-weight: 700; line-height: 1.2; color: #f2f5ff; }
.stats-label { font-size: 13px; color: rgba(255, 255, 255, 0.55); }

/* ===== 三步流程时间线（P1-2）：桌面横排 + 连接线，移动竖排 + 左竖线 ===== */
.value-grid {
  display: grid;
  grid-template-columns: 1fr 36px 1fr 36px 1fr;
  align-items: stretch;
  gap: 0;
}
.value-connector { display: flex; align-items: center; justify-content: center; }

/* 价值/生态卡片四件套（P0-2）：加大体量 + 白系磨砂底 + hover 上浮提亮 */
.value-card, .ecosystem-card {
  padding: 30px 28px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  text-align: left;
  transition: transform 250ms ease, border-color 250ms ease, box-shadow 250ms ease;
}
.value-card:hover, .ecosystem-card:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 255, 255, 0.18);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}
.value-card__top { display: flex; justify-content: space-between; align-items: center; }
/* 序号：大号"幽灵数字"，自上而下渐隐 */
.value-card__num {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: .04em;
  line-height: 1;
  background: linear-gradient(180deg, rgba(157, 180, 255, 0.9) 0%, rgba(157, 180, 255, 0.08) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
/* 图标：品牌色渐变圆角芯片 */
.value-card__icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #cdd9ff;
  background: linear-gradient(135deg, rgba(99, 130, 255, 0.30) 0%, rgba(139, 107, 232, 0.30) 100%);
  box-shadow: inset 0 0 0 1px rgba(178, 204, 255, 0.28);
}
.value-card h3, .ecosystem-card h3 { margin: 22px 0 10px; color: #f2f5ff; font-size: 18px; font-weight: 600; }
.value-card p, .ecosystem-card p { margin: 0; color: #c4cee8; font-size: 14px; line-height: 1.7; }
/* 输入 → 产出 两行结构 */
.value-io { margin: 0; display: flex; flex-direction: column; gap: 8px; }
.value-io__row { display: flex; gap: 10px; font-size: 14px; line-height: 1.7; }
.value-io dt {
  flex-shrink: 0;
  height: fit-content;
  margin-top: 2px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 12px;
  color: #9db4ff;
  background: rgba(255, 255, 255, 0.06);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}
.value-io dd { margin: 0; color: #c4cee8; text-align: left; }

/* ===== 生态区 Bento（第四轮）：去掉带的暗色底板，卡片直接浮在星空上 =====
   卡片自带深色毛玻璃底，亮星云处文字对比仍 ~8:1，无需再垫大板；
   带只保留上下 1px 细分隔线作为章节节奏提示。 */
.ecosystem-band {
  padding: 48px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.ecosystem-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  max-width: 1320px;
  margin: 0 auto;
}
/* 深色实底 + 毛玻璃：压住亮星云背景，白字对比度稳定（正文 #E6E9F2）。
   底色提亮一档：面板带已是深色，卡片需比带亮才能撑起"带托卡"的层级 */
.ecosystem-card {
  min-height: 200px;
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  background: rgba(30, 37, 80, 0.72);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.ecosystem-card h3 { font-weight: 700; margin-top: 16px; }
.ecosystem-card p { font-size: 15px; color: #E6E9F2; }
/* 图标行：logo 与状态 pill 两端对齐；logo 圆角贴图、微投影提层次 */
.ecosystem-card__toprow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ecosystem-card__logo {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  object-fit: cover;
  box-shadow: 0 4px 14px rgba(4, 8, 24, 0.35);
}
/* BioOps 底座块：通宽、加高、大卡留白 36px */
.ecosystem-card--platform {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 220px;
  padding: 36px;
  border-radius: 16px;
}
/* 状态标签：胶囊徽章（提亮文字 + 白色系底） */
.status-label {
  display: inline-block;
  width: fit-content;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: .08em;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.10);
  box-shadow: inset 0 0 0 1px rgba(150, 182, 255, 0.30);
}

/* ===== 里程碑时间线（第二轮）：760 居中容器 + 40px 节点间距 + tabular-nums ===== */
.milestones-section { max-width: 760px; }
.milestone-list {
  list-style: none;
  position: relative;
  margin: 8px auto 0;
  padding: 0;
  max-width: 760px;
  text-align: left;
}
.milestone-list::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 10px;
  bottom: 10px;
  width: 1px;
  background: rgba(255, 255, 255, 0.12);
}
.milestone-item { position: relative; padding: 0 0 40px 32px; }
.milestone-item:last-child { padding-bottom: 0; }
.milestone-dot {
  position: absolute;
  left: 3px;
  top: 6px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
  transform: scale(0);
  transition: transform 300ms ease;
}
.milestone-item.is-visible .milestone-dot { transform: scale(1); }
.milestone-item--latest .milestone-dot {
  background: #7d9bff;
  box-shadow: 0 0 10px rgba(125, 155, 255, 0.8);
}
.milestone-time { font-size: 13px; letter-spacing: .06em; color: #9db4ff; font-variant-numeric: tabular-nums; }
.milestone-body h3 { margin: 6px 0; color: #f2f5ff; font-size: 17px; font-weight: 600; }
.milestone-body p { margin: 0; color: #c4cee8; font-size: 14px; line-height: 1.7; }

/* ===== 愿景题记（排版加宽加大，保持玻璃面板） ===== */
/* 与里程碑间距用宽松档 140px（flex gap 96 + 44，与页脚同款补差） */
.vision-section { max-width: 840px; margin-top: calc(var(--section-gap-loose) - var(--section-gap)); text-align: center; }
.vision-section .about-quote-box { margin: 0 auto; text-align: center; }
.vision-section .about-quote-title { font-size: 24px; margin: 0 0 20px; }
.vision-section .about-quote { margin: 0; color: #e8edff; font-size: 15px; line-height: 2; }
.vision-signoff { margin: 22px 0 2px; color: #b9c9ff; font-size: 14px; letter-spacing: .06em; }

/* ===== 进场动效初始态：仅 opacity + transform，进入视口一次性播放 ===== */
.stats-cell, .milestone-item {
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 500ms ease, transform 500ms ease;
}
.stats-cell.is-visible, .milestone-item.is-visible {
  opacity: 1;
  transform: none;
}

/* ===== 响应式（P0 / P1 / P2 五档走查底线：≤760px） ===== */
@media (max-width: 1100px) {
  .ecosystem-grid, .research-entries { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .resource-grid, .model-grid, .research-entries { grid-template-columns: 1fr; }
  .resource-card { padding: 24px 20px; }
  .about-content { --section-gap: 64px; padding: 32px 16px 56px; }
  .about-hero { min-height: auto; padding: 32px 0 64px; }
  .about-section h2 { font-size: 26px; }
  .stats-band { grid-template-columns: repeat(2, 1fr); row-gap: 24px; }
  .stats-cell + .stats-cell { border-left: 0; }
  .stats-cell:nth-child(even) { border-left: 1px solid rgba(255, 255, 255, 0.08); }
  .stats-cell:nth-child(-n + 2) { border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 20px; }
  /* 三步流程：连接线隐藏，改竖排 + 左侧竖线 */
  .value-grid { grid-template-columns: 1fr; gap: 16px; position: relative; padding-left: 24px; }
  .value-grid::before {
    content: '';
    position: absolute;
    left: 7px;
    top: 16px;
    bottom: 16px;
    width: 1px;
    background: rgba(255, 255, 255, 0.15);
  }
  .value-connector { display: none; }
  /* Bento 单列，BioOps 不再强制加高 */
  .ecosystem-grid { grid-template-columns: 1fr; }
  .ecosystem-card--platform { grid-column: auto; min-height: 0; }
  .ecosystem-band { padding: 32px 16px; }
  .about-footer-v2 { margin-left: -16px; margin-right: -16px; padding: 32px 16px 12px; }
  .footer-cols { grid-template-columns: 1fr; gap: 24px; }
  .footer-bottom { flex-direction: column; gap: 6px; }
  .about-actions { flex-direction: column; width: min(320px, 100%); margin: 0 auto; gap: 12px; }
  .about-actions .n-button { width: 100%; }
}

/* ===== 减少动画（P0-4 / P2）：冻结背景与进场动效，hover 去位移保留颜色 ===== */
@media (prefers-reduced-motion: reduce) {
  .about-hero > *, .scroll-hint { animation: none; }
  .about-quote-title { animation: none; }
  .stats-cell, .milestone-item { opacity: 1; transform: none; transition: none; }
  .milestone-dot { transform: none; }
  .value-card:hover, .ecosystem-card:hover { transform: none; }
}
</style>
