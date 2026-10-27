import apiClient from '@/api/client'

export interface WelcomeClaim {
  delivery_id: string
  reservation_expires_at: string
  title: string
  message: string
  source: string
  duration_ms: number
}

export interface WelcomeMessage {
  id: string
  text: string
  topic: string
  tone: string
  enabled: boolean
  agent_run_id: string
}

export interface WelcomeBatch {
  id: string
  week_start: string
  audience: 'admin' | 'general'
  revision: number
  status: string
  prompt_version: string
  prompt_sha256: string
  validation_report: Record<string, unknown>
  messages?: WelcomeMessage[]
  run?: Record<string, unknown>
}

export const welcomeApi = {
  async claim(): Promise<WelcomeClaim | null> {
    const response = await apiClient.post<WelcomeClaim>('/welcome/claim', { locale: 'zh-CN' }, { timeout: 3000 })
    return response.status === 204 ? null : response.data
  },
  async impression(deliveryId: string): Promise<void> {
    await apiClient.post('/welcome/impression', { delivery_id: deliveryId }, { timeout: 3000 })
  },
  async batches(): Promise<WelcomeBatch[]> {
    return (await apiClient.get<WelcomeBatch[]>('/admin/welcome/batches')).data
  },
  async detail(id: string): Promise<WelcomeBatch> {
    return (await apiClient.get<WelcomeBatch>(`/admin/welcome/batches/${id}`)).data
  },
  async generate(targetWeek: string, audience: 'admin' | 'general', revision: number): Promise<void> {
    await apiClient.post('/admin/welcome/generate', { target_week: targetWeek, audience, revision })
  },
  async review(id: string, action: 'publish' | 'withdraw' | 'rollback', note: string): Promise<void> {
    await apiClient.post(`/admin/welcome/batches/${id}/${action}`, { note })
  },
  async setEnabled(id: string, enabled: boolean, note: string): Promise<void> {
    await apiClient.patch(`/admin/welcome/messages/${id}`, { enabled, note })
  },
}
