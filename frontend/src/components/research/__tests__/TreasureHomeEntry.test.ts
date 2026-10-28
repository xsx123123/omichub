// @vitest-environment jsdom
import { createApp, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Workbench from '@/views/TreasureResearchWorkbench.vue'

const calls = vi.hoisted(() => ({ capabilities: vi.fn(), projects: vi.fn(), sessions: vi.fn(), messages: vi.fn(), create: vi.fn() }))
vi.mock('@/api/projects', () => ({ projectsApi: { listProjects: calls.projects } }))
vi.mock('@/api/researchAgent', async original => ({
  ...await original<typeof import('@/api/researchAgent')>(),
  researchAgentApi: { capabilities: calls.capabilities, listSessions: calls.sessions, getMessages: calls.messages, createSession: calls.create },
}))
vi.mock('@/components/research/adapters/useResearchWorkflow', () => ({ useResearchWorkflow: () => ({ view: {}, action: vi.fn() }) }))
vi.mock('@/components/research/TreasureOriginalDisplay.vue', () => ({ default: {
  props: ['presentation', 'draft', 'focusDraft', 'disabled'],
  template: '<div><output>{{ presentation.activeSessionId }}</output><textarea :value="draft" :disabled="disabled" :data-focus="focusDraft" /><p role="alert">{{ presentation.accessError || presentation.streamError }}</p><article v-for="message in presentation.messages">{{ message.content }}</article></div>',
} }))
let cleanup: (() => void) | undefined
async function settle() { for (let i = 0; i < 20; i++) { await Promise.resolve(); await nextTick() } }
async function mount(entry?: 'new' | 'plan') {
  const host = document.createElement('div')
  document.body.append(host)
  const app = createApp(Workbench, { entry })
  app.mount(host)
  cleanup = () => { app.unmount(); host.remove() }
  await settle()
  return host
}
beforeEach(() => {
  vi.resetAllMocks()
  calls.capabilities.mockResolvedValue({ read_sessions: true, read_discovery: true })
  calls.projects.mockResolvedValue([])
  calls.sessions.mockResolvedValue([{ session_id: 'old', project_id: null, title: '历史研究' }])
  calls.messages.mockResolvedValue([{ message_id: 'old-message', role: 'user', content: '旧的问题', metadata_json: {} }])
  calls.create.mockResolvedValue({ session_id: 'new', project_id: null, title: '新对话' })
})
afterEach(() => { cleanup?.(); cleanup = undefined })
describe('home research launch', () => {
  it.each(['new', 'plan'] as const)('%s creates a new session instead of restoring old messages', async entry => {
    const host = await mount(entry)
    expect(calls.create).toHaveBeenCalledExactlyOnceWith(undefined)
    expect(calls.messages).not.toHaveBeenCalled()
    expect(host.querySelector('output')?.textContent).toBe('new')
    const input = host.querySelector('textarea')!
    expect(input.dataset.focus).toBe('true')
    expect(input.value).toBe(entry === 'new' ? '' : '请帮我规划一项研究方案，先和我确认研究问题、研究对象、已有数据与预期目标。')
    expect(host.querySelector('article')).toBeNull()
    window.dispatchEvent(new Event('focus'))
    await settle()
    expect(calls.create).toHaveBeenCalledTimes(1)
  })
  it('normal navigation still restores the latest session', async () => {
    const host = await mount()
    expect(calls.create).not.toHaveBeenCalled()
    expect(calls.messages).toHaveBeenCalledWith('old')
    expect(host.textContent).toContain('旧的问题')
  })
  it('does not create a session without discovery permission', async () => {
    calls.capabilities.mockResolvedValue({ read_sessions: true, read_discovery: false, reason_code: 'NODE_NOT_CONFIGURED' })
    const host = await mount('plan')
    expect(calls.create).not.toHaveBeenCalled()
    expect(calls.messages).not.toHaveBeenCalled()
    expect(host.querySelector('textarea')?.disabled).toBe(true)
    expect(host.querySelector('textarea')?.dataset.focus).toBe('false')
  })
  it('keeps a failed launch out of the old session and shows the existing error', async () => {
    calls.create.mockRejectedValue({ response: { status: 503 } })
    const host = await mount('plan')
    expect(host.querySelector('output')?.textContent).toBe('')
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('暂不可用')
    expect(host.querySelector('textarea')?.dataset.focus).toBe('false')
    expect(calls.messages).not.toHaveBeenCalled()
  })
  it('does not create a session after navigation away during preflight', async () => {
    let resolve!: (value: unknown[]) => void
    calls.sessions.mockReturnValue(new Promise(done => { resolve = done }))
    await mount('new')
    cleanup?.(); cleanup = undefined
    resolve([])
    await settle()
    expect(calls.create).not.toHaveBeenCalled()
  })
})
