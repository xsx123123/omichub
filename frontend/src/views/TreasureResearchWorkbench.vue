<script setup lang="ts">
import { useResearchWorkflow } from '@/components/research/adapters/useResearchWorkflow'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { applyResearchEvent, consumeResearchStream, researchMessageView, safeSourceUrl } from '@/components/research/adapters/researchPresentation'
import type { ResearchActionV1, TreasureIslandProps } from '@/types/treasureIsland'
import { projectsApi, type ProjectItem } from '@/api/projects'
import { researchAgentApi, researchFailure, researchStreamUrl, type ResearchCapabilities, type ResearchMessage, type ResearchSession } from '@/api/researchAgent'
import TreasureOriginalDisplay from '@/components/research/TreasureOriginalDisplay.vue'
import { generateId } from '@/utils/id'
import { shouldGenerateSessionTitle } from '@/utils/sessionTitle'

const props = defineProps<{ entry?: 'new' | 'plan' }>()
let pendingEntry = props.entry
const focusDraft = ref(false)
const capabilities = ref<ResearchCapabilities | null>(null)
const accessError = ref('')
const historyError = ref('')
const canReadSessions = computed(() => !loading.value && capabilities.value?.read_sessions === true)
const canDiscover = computed(() => !loading.value && capabilities.value?.read_discovery === true)
const projects = ref<ProjectItem[]>([])
const sessions = ref<ResearchSession[]>([])
const selectedProjectId = ref<string | null>(null)
const currentSession = ref<ResearchSession | null>(null)
const messages = ref<ResearchMessage[]>([])
const workflow = useResearchWorkflow(currentSession)
const draft = ref('')
const loading = ref(true)
const sending = ref(false)
const streamError = ref('')
const controller = ref<AbortController | null>(null)
let sessionGeneration = 0
let focusCheckRevision = 0

function stopCurrentStream() {
  sessionGeneration++
  controller.value?.abort()
  controller.value = null
  sending.value = false
}

async function loadSessions(restoreLatest = true) {
  const generation = sessionGeneration
  const project = selectedProjectId.value
  const restored = await researchAgentApi.listSessions(project || undefined)
  if (generation !== sessionGeneration || project !== selectedProjectId.value) return
  sessions.value = restored
  if (restoreLatest && sessions.value.length && !currentSession.value) await selectSession(sessions.value[0])
}

async function selectSession(session: ResearchSession) {
  if (!canReadSessions.value || (session.project_id || null) !== selectedProjectId.value) return
  stopCurrentStream()
  const generation = sessionGeneration
  currentSession.value = session
  messages.value = []
  try {
    const restored = await researchAgentApi.getMessages(session.session_id)
    if (generation === sessionGeneration) {
      messages.value = restored
      await workflow.action({ type: 'capabilities.refresh' }, true)
      if (generation !== sessionGeneration) return
      if (workflow.view.allowedTools?.includes('tasks.list_related')) void workflow.action({ type: 'records.refresh' }, true)
    }
  } catch (error) {
    if (generation === sessionGeneration) historyError.value = researchFailure(error)
  }
}

async function createSession() {
  if (!canDiscover.value) return
  stopCurrentStream()
  const generation = sessionGeneration
  let session: ResearchSession
  try { session = await researchAgentApi.createSession(selectedProjectId.value || undefined) }
  catch (error) { if (generation === sessionGeneration) streamError.value = researchFailure(error); return }
  if (generation !== sessionGeneration) return
  currentSession.value = session
  messages.value = []
  void workflow.action({ type: 'capabilities.refresh' }, true)
  sessions.value = [currentSession.value, ...sessions.value]
  streamError.value = ''
}

async function send(submitted?: string) {
  const content = (submitted ?? draft.value).trim()
  if (!content || sending.value || !canDiscover.value) return
  if (!currentSession.value) await createSession()
  if (!currentSession.value) return
  const generation = sessionGeneration
  const sessionId = currentSession.value.session_id
  const requestId = generateId()
  draft.value = ''
  streamError.value = ''
  messages.value.push({ message_id: `local-${Date.now()}`, role: 'user', content, status: 'complete', metadata_json: {}, created_at: new Date().toISOString() })
  const assistant = reactive<ResearchMessage>({ message_id: `stream-${Date.now()}`, role: 'assistant', content: '', status: 'streaming', metadata_json: {}, created_at: new Date().toISOString() })
  messages.value.push(assistant)
  sending.value = true
  let hasPlatformTool = false
  let hasProposal = false
  let streamEnded = false
  try {
    let cursor = 0
    let lastError: unknown
    for (let attempt = 0; attempt < 4 && !streamEnded; attempt++) {
      if (attempt > 0) await new Promise(resolve => setTimeout(resolve, 250 * 2 ** (attempt - 1)))
      if (generation !== sessionGeneration) return
      const activeController = new AbortController()
      controller.value = activeController
      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
        }
        if (cursor > 0) headers['Last-Event-ID'] = String(cursor)
        const response = await fetch(researchStreamUrl(sessionId), {
          method: 'POST', headers,
          body: JSON.stringify({ content, request_id: requestId }), signal: activeController.signal,
        })
        if (!response.ok || !response.body) {
          const data = await response.json().catch(() => ({})) as { code?: string }
          throw { response: { status: response.status, data } }
        }
        const result = await consumeResearchStream(response.body, event => {
          if (generation !== sessionGeneration) return
          applyResearchEvent(assistant, event)
          if (event.event === 'platform_tool') {
            hasPlatformTool = true
            const envelope = event.result as { result?: { proposal_id?: unknown; ingestion_id?: unknown; analysis_proposal_id?: unknown } } | undefined
            const result = envelope?.result
            if (result && [result.proposal_id, result.ingestion_id, result.analysis_proposal_id].some(id => typeof id === 'string' && id.length > 0)) hasProposal = true
          }
          if (event.event === 'error' || event.error) {
            streamError.value = researchFailure({ code: event.code || 'NODE_UNAVAILABLE' })
            assistant.metadata_json.events ??= {}
            assistant.metadata_json.events.error = streamError.value
          }
        }, cursor)
        cursor = result.lastEventId
        streamEnded = result.ended
        if (!streamEnded && attempt === 3) break
      } catch (error) {
        lastError = error
        if ((error as Error).name === 'AbortError') throw error
        const status = (error as { response?: { status?: number } }).response?.status
        if (status || attempt === 3) throw error
      }
    }
    if (generation === sessionGeneration && !streamEnded && assistant.status === 'streaming') {
      assistant.status = 'interrupted'
      streamError.value = lastError
        ? researchFailure(lastError)
        : '连接已中断，已保留收到的部分回复；可重新连接查看同一轮结果。'
    } else if (streamError.value) assistant.status = 'error'
  } catch (error) {
    if (generation === sessionGeneration && (error as Error).name !== 'AbortError') streamError.value = researchFailure(error)
    assistant.status = 'error'
  } finally {
    if (generation === sessionGeneration) {
      sending.value = false
      controller.value = null
      const userMessageCount = messages.value.filter(item => item.role === 'user').length
      if (
        streamEnded && !streamError.value
        && shouldGenerateSessionTitle(userMessageCount, currentSession.value?.title_locked)
      ) {
        try {
          const title = await researchAgentApi.generateSessionTitle(sessionId)
          if (generation === sessionGeneration && title) {
            const session = sessions.value.find(item => item.session_id === sessionId)
            if (session) session.title = title
            if (currentSession.value?.session_id === sessionId) currentSession.value.title = title
          }
        } catch {
          // Title generation is best-effort and must not affect the completed reply.
        }
      }
      if (hasPlatformTool && workflow.view.allowedTools?.includes('tasks.list_related')) void workflow.action({ type: 'records.refresh' }, !hasProposal && !workflow.view.open)
    }
    await nextTick()
  }
}

async function cancel() {
  if (!currentSession.value) return
  const sessionId = currentSession.value.session_id
  controller.value?.abort()
  const result = await researchAgentApi.cancel(sessionId).catch(() => ({ status: 'unknown' as const }))
  sending.value = false
  streamError.value = result.status === 'accepted'
    ? '已向当前服务进程发送停止信号；任务是否已停止尚未确认。重新打开会话可查看已保存内容。'
    : '已停止接收回复，但当前服务未确认任务状态；任务可能由其他进程处理。重新打开会话可查看已保存内容。'
}

async function changeProject(value: string) {
  if (!canReadSessions.value) return
  stopCurrentStream()
  selectedProjectId.value = value || null
  currentSession.value = null
  messages.value = []
  historyError.value = ''
  sessions.value = []
  const generation = sessionGeneration
  try { await loadSessions() } catch (error) { if (generation === sessionGeneration) historyError.value = researchFailure(error) }
}

async function refreshAccess() {
  stopCurrentStream()
  const generation = sessionGeneration
  capabilities.value = null
  accessError.value = ''
  historyError.value = ''
  loading.value = true
  sessions.value = []
  currentSession.value = null
  messages.value = []
  try {
    const access = await researchAgentApi.capabilities()
    if (generation !== sessionGeneration) return
    capabilities.value = access
    if (!access.read_sessions) { accessError.value = researchFailure({ code: access.reason_code || 'FEATURE_DISABLED' }); return }
    if (!access.read_discovery) accessError.value = researchFailure({ code: access.reason_code || 'NODE_NOT_CONFIGURED' })
    const restoredProjects = await projectsApi.listProjects()
    if (generation !== sessionGeneration) return
    projects.value = restoredProjects
    loading.value = false
    await loadSessions(!pendingEntry)
    if (generation !== sessionGeneration) return
    if (pendingEntry && canDiscover.value) {
      const entry = pendingEntry
      pendingEntry = undefined
      draft.value = entry === 'plan' ? '请帮我规划一项研究方案，先和我确认研究问题、研究对象、已有数据与预期目标。' : ''
      await createSession()
      if (currentSession.value) focusDraft.value = true
    }
  } catch (error) {
    if (generation === sessionGeneration) historyError.value = researchFailure(error)
  } finally { if (generation === sessionGeneration) loading.value = false }
}

function clearPrivateHistory() {
  stopCurrentStream()
  sessions.value = []
  currentSession.value = null
  messages.value = []
  historyError.value = ''
}

async function revalidateAccessOnFocus() {
  // Initial preflight can restart, but an existing conversation must stay mounted.
  if (loading.value) { await refreshAccess(); return }
  const generation = sessionGeneration
  const revision = ++focusCheckRevision
  const projectId = selectedProjectId.value
  const current = () => generation === sessionGeneration && revision === focusCheckRevision
  try {
    const access = await researchAgentApi.capabilities()
    if (!current()) return
    if (!access.read_sessions) {
      capabilities.value = access
      clearPrivateHistory()
      accessError.value = researchFailure({ code: access.reason_code || 'FEATURE_DISABLED' })
      return
    }
    const availableProjects = await projectsApi.listProjects()
    if (!current()) return
    capabilities.value = access
    projects.value = availableProjects
    if (projectId && !availableProjects.some(project => project.id === projectId)) {
      clearPrivateHistory()
      selectedProjectId.value = null
      accessError.value = researchFailure({ code: 'PROJECT_FORBIDDEN' })
      return
    }
    if (!access.read_discovery) {
      if (sending.value) stopCurrentStream()
      accessError.value = researchFailure({ code: access.reason_code || 'NODE_NOT_CONFIGURED' })
    } else accessError.value = ''
  } catch (error) {
    if (!current()) return
    const status = (error as { response?: { status?: number } }).response?.status
    if (status === 401 || status === 403) {
      capabilities.value = null
      clearPrivateHistory()
    }
    accessError.value = researchFailure(error)
  }
}
async function editSession(id: string, title?: string) {
  const generation = sessionGeneration
  try {
    await researchAgentApi.updateSession(id, title ? { title } : { status: 'archived' })
    if (generation !== sessionGeneration) return
    if (title) {
      const row = sessions.value.find(item => item.session_id === id)
      if (row) {
        row.title = title
        row.title_locked = true
      }
      if (currentSession.value?.session_id === id) currentSession.value.title_locked = true
    } else {
      sessions.value = sessions.value.filter(item => item.session_id !== id)
      if (currentSession.value?.session_id === id) { stopCurrentStream(); currentSession.value = null; messages.value = [] }
    }
  } catch (error) { if (generation === sessionGeneration) historyError.value = researchFailure(error) }
}
async function literature(kind: string, id: string) {
  if (!currentSession.value) throw new Error('No platform session')
  const value = await researchAgentApi.literature(currentSession.value.session_id, kind, id)
  if (value.urls) value.urls = Object.fromEntries(Object.entries(value.urls).map(([key, url]) => [key, safeSourceUrl(url)]))
  return value
}
function regenerate(id: string) {
  const index = messages.value.findIndex(item => item.message_id === id)
  const question = messages.value.slice(0, index).reverse().find(item => item.role === 'user')
  if (question && !sending.value) void send(question.content)
}
async function handleResearchAction(intent: ResearchActionV1) {
  if (!currentSession.value && !['workflow.close', 'task.open', 'report.open'].includes(intent.type)) await createSession()
  await workflow.action(intent)
}
const presentation = computed<Partial<TreasureIslandProps>>(() => ({
  messages: messages.value.map(researchMessageView),
  sessions: sessions.value.map(item => ({ id: item.session_id, title: item.title, updated_at: item.updated_at })),
  activeSessionId: currentSession.value?.session_id ?? null,
  projects: projects.value.map(item => ({ id: item.id, name: item.name })),
  loading: loading.value, accessError: accessError.value, historyError: historyError.value, streamError: streamError.value,
  onSelectSession: id => { const row = sessions.value.find(item => item.session_id === id); if (row) void selectSession(row) },
  onNewSession: () => { void createSession() },
  onRenameSession: (id, title) => { void editSession(id, title) },
  onArchiveSession: id => { void editSession(id) },
  onChangeProject: id => { void changeProject(id) }, onRefresh: () => { void refreshAccess() },
  onRegenerate: regenerate, loadLiterature: literature,
  loadLeaderboard: researchAgentApi.leaderboard,
  loadUsage: researchAgentApi.usageStats,
  updateNickname: researchAgentApi.updateNickname,
  workflow: { ...workflow.view }, onResearchAction: intent => { void handleResearchAction(intent) },
}))
onMounted(() => {
  void refreshAccess()
  window.addEventListener('focus', revalidateAccessOnFocus)
})
onUnmounted(() => { stopCurrentStream(); window.removeEventListener('focus', revalidateAccessOnFocus) })
</script>

<template>
  <main class="treasure-native-module" aria-label="科研寻宝鼠">
    <TreasureOriginalDisplay mode="app" v-model:draft="draft" :focus-draft="focusDraft" :disabled="!canDiscover" :streaming="sending" :project-id="selectedProjectId" :presentation="presentation" @submit="send" @example="draft = $event" @cancel="cancel" />
  </main>
</template>
<style scoped>
.treasure-native-module { display: flex; flex: 1; flex-direction: column; min-height: 0; min-width: 0; height: 100%; overflow: hidden; }
</style>
