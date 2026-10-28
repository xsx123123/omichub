<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NAlert, NButton, NInput, NSpin } from 'naive-ui'
import apiClient from '@/api/client'
import { reportApi } from '@/api/report'
import { useAgentChatStream } from '@/composables/useAgentChatStream'

const props = defineProps<{ reportId: string }>()
const emit = defineEmits<{ section: [title: string] }>()
interface CopilotMessage { role: 'user' | 'assistant'; content: string }
const messages = ref<CopilotMessage[]>([])
const draft = ref('')
const loading = ref(false)
const loadingHistory = ref(false)
const error = ref('')
const warning = ref('')
const metadata = ref<Record<string, unknown> | null>(null)
const sessionId = ref('')
const modelId = ref('')
const { streamChat, isStreaming, abortStream } = useAgentChatStream()
const quickQuestions = [
  '这份报告的核心结论是什么？',
  '这项分析用了几个样本，分组是什么？',
  '质控结果有哪些需要关注的地方？',
  '按调整 p 值列出 top 20 差异基因。',
]
let generation = 0
const canSend = computed(() => Boolean(draft.value.trim()) && !isStreaming.value && Boolean(sessionId.value))

async function initialize() {
  const current = ++generation
  abortStream()
  sessionId.value = ''
  modelId.value = ''
  messages.value = []
  error.value = ''
  warning.value = ''
  metadata.value = null
  loadingHistory.value = true
  try {
    const key = `report-copilot-session:${props.reportId}`
    let savedId = localStorage.getItem(key) || ''
    let session
    if (!savedId) {
      const created = await reportApi.createCopilotSession(props.reportId)
      session = created.data
      savedId = session.session_id
      localStorage.setItem(key, savedId)
    } else session = (await reportApi.getCopilotSession(props.reportId, savedId)).data
    if (current !== generation) return
    modelId.value = session.model_id
    warning.value = session.warning || ''
    metadata.value = session.metadata
    sessionId.value = savedId
    const history = await apiClient.get<Array<{ role: string; content: string }>>(`/chat/sessions/${savedId}/messages`)
    if (current !== generation) return
    messages.value = history.data
      .filter(item => item.role === 'user' || item.role === 'assistant')
      .map(item => ({ role: item.role as CopilotMessage['role'], content: item.content || '' }))
  } catch (cause) {
    if (current === generation) {
      const detail = (cause as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = detail || '报告解读暂时无法启动，请稍后重试。'
      if (/不匹配|无权|不存在/.test(error.value)) localStorage.removeItem(`report-copilot-session:${props.reportId}`)
    }
  } finally {
    if (current === generation) loadingHistory.value = false
  }
}

async function send(question?: string) {
  const content = (question || draft.value).trim()
  if (!content || !sessionId.value || isStreaming.value) return
  draft.value = ''
  error.value = ''
  const current = generation
  const conversation: CopilotMessage[] = [...messages.value, { role: 'user', content }, { role: 'assistant', content: '' }]
  messages.value = conversation
  const payload = conversation.slice(0, -1).map(item => ({ role: item.role, content: item.content }))
  await streamChat({
    agentId: 'agent-general',
    endpoint: `/api/v1/reports/${props.reportId}/copilot/stream`,
    sessionId: sessionId.value,
    modelId: modelId.value || undefined,
    messages: payload,
    mode: 'chat',
    mcpMode: 'off',
    multiAgent: false,
    overdrive: false,
    enableWebSearch: false,
    enableCodeExecution: false,
    autoApprove: false,
  }, {
    onText: text => {
      if (current === generation) conversation[conversation.length - 1].content += text
    },
    onError: detail => { if (current === generation) error.value = detail },
  })
}

function citationSegments(content: string): Array<{ text: string; section?: string }> {
  return content.split(/(\[报告章节: [^\]]+\])/g).filter(Boolean).map(text => {
    const match = text.match(/^\[报告章节: (.{1,80})\]$/)
    return match ? { text, section: match[1].trim() } : { text }
  })
}

function scrollToLatest() {
  const el = document.querySelector('.copilot-messages')
  if (el) el.scrollTop = el.scrollHeight
}

watch(() => props.reportId, initialize, { immediate: true })
watch(messages, scrollToLatest, { deep: true, flush: 'post' })
onBeforeUnmount(() => { generation++; abortStream() })
</script>

<template>
  <aside class="copilot-panel" aria-label="报告 AI 解读">
    <header class="copilot-header">
      <div><strong>AI 报告解读</strong><small>仅读取当前报告关联的数据</small></div>
      <NSpin v-if="loadingHistory || isStreaming" size="small" />
    </header>
    <NAlert v-if="warning" type="warning" :show-icon="false" class="copilot-alert">{{ warning }}</NAlert>
    <div v-if="metadata" class="copilot-context">{{ metadata.flow || '报告' }} · {{ metadata.sample_count ?? '样本数缺失' }} 个样本</div>
    <div class="quick-questions">
      <button v-for="item in quickQuestions" :key="item" :disabled="isStreaming || loadingHistory" @click="send(item)">{{ item }}</button>
    </div>
    <div class="copilot-messages" aria-live="polite">
      <div v-if="!messages.length && !loadingHistory" class="copilot-empty">可以询问报告结论、样本分组、质控或结果表。</div>
      <article v-for="(item, index) in messages" :key="index" :class="['copilot-message', item.role]">
        <strong>{{ item.role === 'user' ? '你' : 'Copilot' }}</strong>
        <p v-for="(part, partIndex) in citationSegments(item.content)" :key="partIndex" class="message-part">
          <button v-if="part.section" class="citation" @click="emit('section', part.section)">{{ part.section }}</button>
          <span v-else>{{ part.text }}</span>
        </p>
      </article>
      <NAlert v-if="error" type="error" :show-icon="false">{{ error }}</NAlert>
    </div>
    <form class="copilot-compose" @submit.prevent="send()">
      <NInput v-model:value="draft" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="询问这份报告…" :disabled="isStreaming || !sessionId" @keydown.enter.exact.prevent="send()" />
      <NButton type="primary" attr-type="submit" :disabled="!canSend">发送</NButton>
    </form>
  </aside>
</template>

<style scoped>
.copilot-panel { display:flex; flex-direction:column; height:100%; min-width:300px; background:var(--neutral-card); border-left:1px solid var(--neutral-border); }
.copilot-header { display:flex; justify-content:space-between; align-items:center; padding:16px; border-bottom:1px solid var(--neutral-border); }
.copilot-header strong,.copilot-header small { display:block; }.copilot-header small,.copilot-context { color:var(--neutral-text-2); font-size:12px; margin-top:4px; }
.copilot-alert,.copilot-context { margin:10px 12px 0; }.quick-questions { display:flex; flex-wrap:wrap; gap:6px; padding:10px 12px; }
.quick-questions button,.citation { border:1px solid var(--neutral-border); background:transparent; color:var(--brand-primary); border-radius:14px; padding:5px 9px; cursor:pointer; text-align:left; font-size:12px; }
.quick-questions button:disabled { opacity:.5; cursor:default; }.copilot-messages { flex:1; overflow:auto; padding:12px; display:flex; flex-direction:column; gap:12px; }
.copilot-message { max-width:100%; border-radius:10px; padding:10px 12px; background:var(--neutral-bg); overflow-wrap:anywhere; }.copilot-message.user { align-self:flex-end; background:color-mix(in srgb,var(--brand-primary) 12%,var(--neutral-card)); }
.copilot-message strong { font-size:12px; color:var(--neutral-text-2); }.message-part { margin:6px 0 0; white-space:pre-wrap; line-height:1.6; }.citation { display:inline-block; }
.copilot-empty { color:var(--neutral-text-2); font-size:13px; text-align:center; margin:auto; }.copilot-compose { padding:12px; border-top:1px solid var(--neutral-border); display:flex; align-items:flex-end; gap:8px; }
</style>
