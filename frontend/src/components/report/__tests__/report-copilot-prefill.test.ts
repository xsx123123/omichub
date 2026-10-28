// @vitest-environment jsdom
import { createApp, h, nextTick, reactive, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import ReportCopilotPanel from '../ReportCopilotPanel.vue'

vi.mock('@/api/report', () => ({ reportApi: {
  createCopilotSession: vi.fn().mockResolvedValue({ data: { session_id: 'session', model_id: 'model', metadata: {} } }),
} }))
vi.mock('@/api/client', () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }))
vi.mock('@/composables/useAgentChatStream', () => ({
  useAgentChatStream: () => ({ streamChat: vi.fn(), abortStream: vi.fn(), isStreaming: ref(false) }),
}))

describe('selection opens a new Copilot panel', () => {
  it('fills the selection received before mounting, and accepts the next selection', async () => {
    localStorage.clear()
    const props = reactive({ reportId: 'report', prefill: { content: '选中内容：15 个样本', nonce: 1 } })
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = createApp({ render: () => h(ReportCopilotPanel, props) })
    app.mount(host)
    try {
      for (let i = 0; i < 8; i++) { await Promise.resolve(); await nextTick() }
      expect(host.querySelector('textarea')?.value).toBe('选中内容：15 个样本')
      props.prefill = { content: '选中内容：Q30', nonce: 2 }
      await nextTick()
      expect(host.querySelector('textarea')?.value).toBe('选中内容：Q30')
    } finally { app.unmount(); host.remove() }
  })
})
