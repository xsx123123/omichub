// @vitest-environment jsdom
import { createApp, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Workbench from '@/views/TreasureResearchWorkbench.vue'

const calls = vi.hoisted(() => ({ capabilities: vi.fn(), projects: vi.fn(), sessions: vi.fn(), messages: vi.fn(), title: vi.fn() }))
vi.mock('@/api/projects', () => ({ projectsApi: { listProjects: calls.projects } }))
vi.mock('@/api/researchAgent', async original => ({
  ...await original<typeof import('@/api/researchAgent')>(),
  researchAgentApi: { capabilities: calls.capabilities, listSessions: calls.sessions, getMessages: calls.messages, generateSessionTitle: calls.title },
}))
vi.mock('@/components/research/adapters/useResearchWorkflow', () => ({ useResearchWorkflow: () => ({ view: {}, action: vi.fn() }) }))
vi.mock('@/components/research/TreasureOriginalDisplay.vue', () => ({ default: {
  props: ['presentation', 'streaming', 'disabled'], emits: ['submit'],
  template: `<div><output>{{ presentation.activeSessionId }}</output><p role="alert">{{ presentation.accessError || presentation.historyError }}</p><button class="send" @click="$emit('submit', '新的研究问题')">发送</button><button class="project" @click="presentation.onChangeProject('p1')">选择项目</button><button v-for="session in presentation.sessions" class="history" @click="presentation.onSelectSession(session.id)">{{ session.title }}</button><span class="streaming">{{ streaming }}</span><article v-for="message in presentation.messages">{{ message.content }}</article></div>`,
} }))
const allowed = { read_sessions: true, read_discovery: true }
const a = { session_id: 'a', title: '较新的会话', project_id: null }
const b = { session_id: 'b', title: '当前正在阅读的会话', project_id: null }
const message = (content: string) => [{ message_id: content, role: 'assistant', content, metadata_json: {}, status: 'complete' }]
async function settle() { for (let i = 0; i < 18; i++) { await Promise.resolve(); await nextTick() } }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done }); return { promise, resolve } }
let cleanup: (() => void) | undefined
async function mount() {
  const host = document.createElement('div'); document.body.append(host)
  const app = createApp(Workbench); app.mount(host)
  cleanup = () => { app.unmount(); host.remove() }
  await settle(); return host
}
beforeEach(() => {
  vi.resetAllMocks(); calls.capabilities.mockResolvedValue(allowed); calls.projects.mockResolvedValue([])
  calls.sessions.mockResolvedValue([a, b]); calls.messages.mockImplementation(id => Promise.resolve(message('回复-' + id)))
  calls.title.mockResolvedValue('研究标题')
})
afterEach(() => { cleanup?.(); cleanup = undefined; vi.unstubAllGlobals() })
describe('non-destructive focus permission checks', () => {
  it('keeps the selected conversation visible while focus preflight is pending and does not reopen the latest session', async () => {
    const host = await mount(); host.querySelectorAll<HTMLButtonElement>('.history')[1].click(); await settle()
    const gate = deferred<typeof allowed>(); calls.capabilities.mockReturnValueOnce(gate.promise)
    window.dispatchEvent(new Event('focus')); await settle()
    expect(host.textContent).toContain('回复-b'); expect(host.querySelector('output')?.textContent).toBe('b')
    gate.resolve(allowed); await settle()
    expect(host.textContent).toContain('回复-b'); expect(calls.sessions).toHaveBeenCalledTimes(1)
    expect(calls.messages).toHaveBeenCalledTimes(2)
  })
  it('does not interrupt streaming or lose late deltas when the window regains focus', async () => {
    calls.messages.mockResolvedValue([])
    let feed!: ReadableStreamDefaultController<Uint8Array>
    const stream = new ReadableStream<Uint8Array>({ start(c) { feed = c } })
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, body: stream }); vi.stubGlobal('fetch', fetchMock)
    const host = await mount(); host.querySelector<HTMLButtonElement>('.send')!.click(); await settle()
    feed.enqueue(new TextEncoder().encode('data: {"delta":"回答前半段"}\n\n')); await settle()
    const signal = (fetchMock.mock.calls[0][1] as RequestInit).signal!
    window.dispatchEvent(new Event('focus')); await settle()
    expect(signal.aborted).toBe(false); expect(host.textContent).toContain('回答前半段')
    feed.enqueue(new TextEncoder().encode('data: {"delta":"，回答后半段"}\n\ndata: {"event":"end"}\n\n')); feed.close(); await settle()
    expect(host.textContent).toContain('回答前半段，回答后半段'); expect(host.querySelector('.streaming')?.textContent).toBe('false')
  })
  it('preserves a finished reply while title generation and a focus check finish', async () => {
    calls.messages.mockResolvedValue([]); const title = deferred<string>(); calls.title.mockReturnValue(title.promise)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, body: new ReadableStream<Uint8Array>({ start(c) { c.enqueue(new TextEncoder().encode('data: {"delta":"最终完整回复"}\n\ndata: {"event":"end"}\n\n')); c.close() } }) }))
    const host = await mount(); host.querySelector<HTMLButtonElement>('.send')!.click(); await settle()
    expect(host.textContent).toContain('最终完整回复')
    window.dispatchEvent(new Event('focus')); await settle(); title.resolve('最终研究标题'); await settle()
    expect(host.textContent).toContain('最终完整回复'); expect(host.querySelector('output')?.textContent).toBe('a')
    expect(calls.messages).toHaveBeenCalledTimes(1)
  })
  it('still clears private history on revoked read access', async () => {
    const host = await mount(); calls.capabilities.mockResolvedValue({ read_sessions: false, read_discovery: false, reason_code: 'MODULE_LOCKED' })
    window.dispatchEvent(new Event('focus')); await settle()
    expect(host.querySelector('article')).toBeNull(); expect(host.textContent).toContain('尚无寻宝鼠模块权限')
  })
  it.each([401, 403])('clears private history on HTTP %s during focus validation', async status => {
    const host = await mount(); calls.capabilities.mockRejectedValue({ response: { status } })
    window.dispatchEvent(new Event('focus')); await settle()
    expect(host.querySelector('article')).toBeNull(); expect(host.querySelector('output')?.textContent).toBe('')
  })
  it('keeps the reply on transient preflight failure', async () => {
    const host = await mount(); calls.capabilities.mockRejectedValue(new Error('network'))
    window.dispatchEvent(new Event('focus')); await settle()
    expect(host.textContent).toContain('回复-a'); expect(host.querySelector('[role="alert"]')?.textContent).toContain('无法连接')
  })
  it('drops a stale focus response after switching conversations', async () => {
    const host = await mount(); const gate = deferred<{ read_sessions: boolean; read_discovery: boolean }>(); calls.capabilities.mockReturnValueOnce(gate.promise)
    window.dispatchEvent(new Event('focus')); await settle(); host.querySelectorAll<HTMLButtonElement>('.history')[1].click(); await settle()
    gate.resolve({ read_sessions: false, read_discovery: false }); await settle()
    expect(host.textContent).toContain('回复-b'); expect(host.querySelector('output')?.textContent).toBe('b')
  })
  it('clears project-private history when refreshed project access is revoked', async () => {
    calls.projects.mockResolvedValue([{ id: 'p1', name: '项目一' }]); calls.sessions.mockImplementation(project => Promise.resolve(project ? [{ ...a, project_id: project }] : [a, b]))
    const host = await mount(); host.querySelector<HTMLButtonElement>('.project')!.click(); await settle()
    expect(host.textContent).toContain('回复-a'); calls.projects.mockResolvedValue([])
    window.dispatchEvent(new Event('focus')); await settle()
    expect(host.querySelector('article')).toBeNull(); expect(host.textContent).toContain('项目授权已变更')
  })
})
