import apiClient from './client'
import { chatApi } from './chat'
import type { TreasureIslandProps } from '@/types/treasureIsland'
import type { PlatformLeaderboard, PlatformUsageStats } from '../../treasure-island/platformStats'

export interface ResearchCapabilities {
  native_ui_enabled: boolean
  enabled: boolean
  read_discovery: boolean
  read_sessions: boolean
  prepare_import: boolean
  prepare_analysis: boolean
  project_required_for_prepare: true
  write_execution: false
  write_tools_enabled: false
  reason_code: string | null
  cancellation_mode: 'browser_abort_with_best_effort_signal'
}

export interface ResearchCancelResponse {
  status: 'accepted' | 'unknown'
}

/** Keep server detail/stack traces out of the UI; codes describe the next action. */
export function researchFailure(error: unknown): string {
  const failure = error as { response?: { status?: number; data?: { code?: string } }; code?: string }
  const status = failure?.response?.status
  const code = failure?.response?.data?.code || failure?.code
  if (code === 'FEATURE_DISABLED') return '科研发现入口尚未启用，请联系管理员确认只读服务状态。'
  if (code === 'MODULE_LOCKED') return '你尚无寻宝鼠模块权限，请联系管理员开通。'
  if (code === 'PROJECT_FORBIDDEN') return '当前项目授权已变更，请重新选择有权访问的项目。'
  if (code === 'PROVIDER_UNAVAILABLE') return '平台模型暂不可用，请联系管理员检查模型配置。'
  if (status === 401) return '登录状态已失效，请重新登录后重试。'
  if (status === 403) return '当前操作未获授权，请刷新权限或重新选择项目。'
  if (status === 404) return '会话或项目已不可用，请刷新列表后重试。'
  if (status === 422) return '请求参数不符合要求，请检查项目与输入内容。'
  if (code === 'NODE_NOT_CONFIGURED' || code === 'NODE_UNAVAILABLE' || status === 503) return '科研发现服务暂不可用，已保存的会话可在服务恢复后查看。'
  return '无法连接科研发现服务，请检查网络后重试。'
}

export interface DiscoveryProposal {
  schema_version: '1.0'
  proposal_id: string
  source: string
  accession: string | null
  title: string
  summary: string
  organism: string | null
  assay_type: string | null
  sample_count: number | null
  metadata_status: 'unverified' | 'agent_asserted' | 'platform_verified'
  source_links: string[]
  evidence_refs: string[]
  retrieved_at: string | null
  project_id: string | null
  conversation_id: string
  provenance: Record<string, unknown>
  next_actions: string[]
}

export interface ResearchSession {
  session_id: string
  title: string
  title_locked?: boolean
  project_id: string | null
  model_id: string
  status: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface ResearchMessage {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  status: string
  metadata_json: {
    proposals?: DiscoveryProposal[]
    events?: { cards?: unknown[]; tools?: unknown[]; grounding?: unknown; polariseq?: { accession: string | null }; error?: string }
  }
  created_at: string
}

export const researchAgentApi = {
  async leaderboard(period: 'all' | 'week' = 'all'): Promise<PlatformLeaderboard> {
    return (await apiClient.get<PlatformLeaderboard>('/research-agent/leaderboard', { params: { period } })).data
  },
  async usageStats(): Promise<PlatformUsageStats> {
    return (await apiClient.get<PlatformUsageStats>('/research-agent/stats')).data
  },
  async updateNickname(nickname: string): Promise<{ ok: boolean }> {
    return (await apiClient.patch<{ ok: boolean }>('/research-agent/nickname', { nickname })).data
  },
  async capabilities(): Promise<ResearchCapabilities> {
    return (await apiClient.get<ResearchCapabilities>('/research-agent/capabilities')).data
  },
  async listSessions(projectId?: string): Promise<ResearchSession[]> {
    const response = await apiClient.get<ResearchSession[]>('/research-agent/sessions', {
      params: projectId ? { project_id: projectId } : undefined,
    })
    return response.data
  },
  async createSession(projectId?: string): Promise<ResearchSession> {
    const response = await apiClient.post<ResearchSession>('/research-agent/sessions', {
      project_id: projectId || undefined,
    })
    return response.data
  },
  async getMessages(sessionId: string): Promise<ResearchMessage[]> {
    const response = await apiClient.get<ResearchMessage[]>(`/research-agent/sessions/${sessionId}/messages`)
    return response.data
  },
  async updateSession(sessionId: string, value: { title?: string; status?: 'archived' }): Promise<ResearchSession> {
    return (await apiClient.patch<ResearchSession>(`/research-agent/sessions/${encodeURIComponent(sessionId)}`, value)).data
  },
  async generateSessionTitle(sessionId: string): Promise<string> {
    return chatApi.generateSessionTitle(sessionId)
  },
  async literature(sessionId: string, kind: string, id: string): ReturnType<NonNullable<TreasureIslandProps['loadLiterature']>> {
    return (await apiClient.post(`/research-agent/sessions/${encodeURIComponent(sessionId)}/literature`, { kind, id })).data
  },
  async cancel(sessionId: string): Promise<ResearchCancelResponse> {
    return (await apiClient.post<ResearchCancelResponse>(
      `/research-agent/sessions/${encodeURIComponent(sessionId)}/cancel`,
    )).data
  },
}

export function researchStreamUrl(sessionId: string): string {
  return `/api/v1/research-agent/sessions/${encodeURIComponent(sessionId)}/messages:stream`
}
