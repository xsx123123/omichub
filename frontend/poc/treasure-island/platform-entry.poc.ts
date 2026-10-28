// @vitest-environment jsdom
import { createApp, nextTick } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import Workbench from '../../src/views/TreasureResearchWorkbench.vue'
import * as island from '@treasure-island-poc'
const calls = vi.hoisted(() => ({ capabilities: vi.fn(), projects: vi.fn(), sessions: vi.fn(), messages: vi.fn(), create: vi.fn(), update: vi.fn(), literature: vi.fn(), invoke: vi.fn(), related: vi.fn() }))
vi.mock('@/api/agentTools', () => ({ agentToolsApi: { capabilities: async () => ({ tools: ['dataset.discover', 'dataset.prepare_import', 'tasks.list_related'].map(capability_id => ({ capability_id })) }), invoke: calls.invoke, related: calls.related } }))
vi.mock('@/api/projects', () => ({ projectsApi: { listProjects: calls.projects } }))
vi.mock('@/api/researchAgent', () => ({ researchFailure: () => '科研发现入口尚未启用', researchAgentApi: { capabilities: calls.capabilities, listSessions: calls.sessions, getMessages: calls.messages, createSession: calls.create, updateSession: calls.update, literature: calls.literature }, researchStreamUrl: () => '/unused' }))
vi.mock('@/components/research/treasureIslandLoader', () => ({ loadTreasureIsland: async () => island }))
beforeAll(() => {
  window.matchMedia = vi.fn().mockImplementation(() => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
  Element.prototype.scrollIntoView = vi.fn()
})
let cleanup: (() => void) | undefined
afterEach(() => { cleanup?.(); vi.clearAllMocks(); vi.unstubAllGlobals() })
async function settle() { for (let i = 0; i < 20; i++) { await Promise.resolve(); await nextTick() } }
async function render() {
  const el = document.createElement('div'); document.body.append(el)
  const app = createApp(Workbench); app.mount(el)
  cleanup = () => { app.unmount(); el.remove() }
  await settle()
  return { el, shadow: el.querySelector<HTMLElement>('.original-display-host')!.shadowRoot! }
}
function button(shadow: ShadowRoot, label: string): HTMLButtonElement {
  return [...shadow.querySelectorAll<HTMLButtonElement>('button')].find(el => el.getAttribute('aria-label') === label || el.title === label)!
}
function allowed() {
  calls.capabilities.mockResolvedValue({ read_sessions: true, read_discovery: true })
  calls.projects.mockResolvedValue([]); calls.sessions.mockResolvedValue([])
  calls.related.mockResolvedValue([])
}
describe('actual platform uses the complete original React presentation', () => {
  it('shows the four original scenes when discovery is disabled, without protected requests or old login', async () => {
    calls.capabilities.mockResolvedValue({ read_sessions: false, read_discovery: false, reason_code: 'FEATURE_DISABLED' })
    const { el, shadow } = await render()
    expect(shadow.querySelectorAll('section')).toHaveLength(4)
    expect(shadow.querySelectorAll('section button')).toHaveLength(8)
    expect(shadow.querySelector('textarea')!.disabled).toBe(true)
    expect(shadow.textContent).toContain('入口尚未启用')
    expect(shadow.querySelector('[data-treasure-app]')).not.toBeNull()
    expect(el.querySelector('iframe')).toBeNull()
    expect(calls.projects).not.toHaveBeenCalled(); expect(calls.sessions).not.toHaveBeenCalled()
    expect(shadow.querySelector('[href*="login"]')).toBeNull()
  })
  it('restores original messages, sessions, cards, follow-ups and original composer in one tree', async () => {
    allowed(); calls.sessions.mockResolvedValue([{ session_id: 's1', title: '干扰素数据', project_id: null, updated_at: '2026-10-15T00:00:00Z' }])
    calls.messages.mockResolvedValue([
      { message_id: 'u1', role: 'user', content: '寻找干扰素数据', status: 'complete', metadata_json: {} },
      { message_id: 'a1', role: 'assistant', content: '**已检索** GSE12345\n\n:::followup\n- 进一步检索对照组\n:::', status: 'complete', metadata_json: { events: { cards: [{ tool: 'search_geo', accession: 'GSE12345', title: '真实来源的测试数据集', summary: '摘要', meta: { organism: 'Mus musculus', samples: '12' } }, { tool: 'literature_search', accession: '12345678', title: 'Evidence publication', summary: 'Published evidence', meta: { source: 'literature', literature_source: 'pubmed', pmid: '12345678', doi: '10.1234/example', authors: 'Researcher et al.', url_pubmed: 'https://pubmed.ncbi.nlm.nih.gov/12345678/', url_doi: 'https://doi.org/10.1234/example' } }], tools: [{ name: 'search_geo', label: '搜索 GEO 数据集', status: 'running' }, { name: 'search_geo', label: '搜索 GEO 数据集', status: 'done', ms: 1305 }] } } },
    ])
    const { shadow } = await render()
    expect(shadow.textContent).toContain('真实来源的测试数据集')
    expect(shadow.textContent).toContain('Mus musculus')
    expect(shadow.textContent).toContain('Evidence publication')
    expect(shadow.textContent).toContain('PMID: 12345678')
    expect(shadow.querySelector('a[href="https://doi.org/10.1234/example"]')).not.toBeNull()
    expect(shadow.querySelector('a[href="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE12345"]')).not.toBeNull()
    expect(shadow.querySelectorAll('[data-treasure-messages] > div')).toHaveLength(2)
    expect(shadow.querySelector('strong')!.textContent).toBe('已检索')
    expect(shadow.textContent).toContain('1305ms')
    expect(shadow.textContent).not.toContain(':::followup')
    expect(button(shadow, '展开会话列表')).toBeDefined()
    expect(shadow.querySelector('.session-sidebar')).toBeNull()
    button(shadow, '展开会话列表').click(); await settle()
    button(shadow, '收起会话列表').click(); await settle()
    button(shadow, '展开会话列表').click(); await settle()
    expect(shadow.textContent).toContain('干扰素数据')
    expect(shadow.querySelector('textarea')).not.toBeNull()
    expect(button(shadow, '桌宠设置')).toBeDefined()
    const sent = vi.fn(async (_url: string, _init: RequestInit) => new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('data: {"event":"end"}\n\n')); controller.close() } })))
    vi.stubGlobal('fetch', sent)
    ;[...shadow.querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent?.includes('阿寻的下一铲建议'))!.click(); await settle()
    ;[...shadow.querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent?.includes('进一步检索对照组'))!.click(); await settle()
    expect(JSON.parse(sent.mock.calls[0][1].body as string).content).toBe('进一步检索对照组')
    expect(calls.invoke).not.toHaveBeenCalled()
  })
  it('sends via the Vue owner and shows deltas before end, keeping cards/grounding/Polariseq for history parity', async () => {
    allowed(); calls.create.mockResolvedValue({ session_id: 'live', title: '新会话', project_id: null })
    let feed!: ReadableStreamDefaultController<Uint8Array>
    const body = new ReadableStream<Uint8Array>({ start(controller) { feed = controller } })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 200 })))
    const { shadow } = await render()
    const example = shadow.querySelector<HTMLButtonElement>('section button')!
    example.click(); await settle()
    await vi.waitFor(() => expect(shadow.querySelector('textarea')!.value).not.toBe(''))
    button(shadow, '下铲挖宝').click(); await settle()
    try {
      feed.enqueue(new TextEncoder().encode('data: {"delta":"已找到 GSE12345"}\n\ndata: {"event":"tool","name":"search_geo","label":"检索","status":"done","ms":10}\n\n'))
      await settle()
      expect(shadow.textContent).toContain('已找到 GSE12345')
      expect(button(shadow, '停止生成')).toBeDefined()
      feed.enqueue(new TextEncoder().encode('data: {"event":"cards","cards":[{"accession":"GSE12345","title":"实时数据卡","meta":{"organism":"Human"}}]}\n\ndata: {"event":"grounding","unconfirmed":[{"id":"GSE99999","status":"unverified"}],"confirmed":[]}\n\ndata: {"event":"polariseq","accession":"PRJNA12345"}\n\ndata: {"event":"end","cards":[]}\n\n'))
    } finally { feed.close(); await settle() }
    expect(shadow.textContent).toContain('实时数据卡')
    ;(Array.from(shadow.querySelectorAll('button')).find(button => button.textContent?.includes('编号核验提示')) as HTMLButtonElement).click()
    await settle()
    expect(shadow.querySelector('[data-treasure-app]')?.textContent).toContain('GSE99999')
    expect(shadow.textContent).not.toContain(':::followup')
  })
  it('T01/T11/W7 opens inspection from the original DatasetCard without replacing the reply', async () => {
    allowed()
    calls.sessions.mockResolvedValue([{ session_id: 's1', title: 'history', project_id: null }])
    calls.messages.mockResolvedValue([{ message_id: 'a1', role: 'assistant', content: 'GSE12345', status: 'complete', metadata_json: { events: { cards: [{ accession: 'GSE12345', title: 'Original dataset', meta: { organism: 'Human' } }] } } }])
    calls.invoke.mockResolvedValue({ result: { primary_accession: 'GSE12345', status: 'RESOLVED', samples: [{ sample_key: 'GSM1', title: ['sample evidence'] }], runs: [{ run_accession: 'SRR1', library_layout: 'PAIRED' }], files: [], confidence_flags: ['groups_need_review'] } })
    const { shadow } = await render()
    const inspect = [...shadow.querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent === '查看数据与样本')!
    inspect.click(); await settle()
    expect(calls.invoke).toHaveBeenCalledWith('s1', 'dataset.discover', { accession: 'GSE12345' })
    expect(shadow.querySelector('[role="dialog"]')?.textContent).toContain('SRR1')
    expect(shadow.querySelector('[role="dialog"]')?.textContent).toContain('全局只读发现可继续')
    expect(shadow.querySelector('[data-treasure-messages]')?.textContent).toContain('Original dataset')
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
  })
  it('W2 prepares selected authoritative runs without exposing execute or identity fields', async () => {
    allowed()
    calls.projects.mockResolvedValue([{ id: 'p1', name: 'Research project' }])
    calls.sessions.mockImplementation(async (pid: string) => pid ? [{ session_id: 'project-session', title: 'Project study', project_id: pid }] : [])
    calls.messages.mockResolvedValue([{ message_id: 'a', role: 'assistant', content: 'Dataset', status: 'complete', metadata_json: { events: { cards: [{ accession: 'GSE1', title: 'Study', meta: {} }] } } }])
    calls.invoke.mockImplementation(async (_sid: string, capability: string) => ({ result: capability === 'dataset.discover' ? { primary_accession: 'GSE1', status: 'RESOLVED', samples: [], runs: [{ run_accession: 'SRR1', library_layout: 'PAIRED' }], files: [] } : { ingestion_id: 'proposal1', state: 'PREPARED', parameters_hash: 'hash', preview: { accession: 'GSE1', max_bytes: 67108864 } } }))
    const { shadow } = await render()
    const project = shadow.querySelector<HTMLSelectElement>('select[aria-label="项目上下文"]')!
    project.value = 'p1'; project.dispatchEvent(new Event('change', { bubbles: true })); await settle()
    ;[...shadow.querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent === '查看数据与样本')!.click(); await settle()
    shadow.querySelector<HTMLInputElement>('[role="dialog"] input[type="checkbox"]')!.click(); await settle()
    ;[...shadow.querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent === '保存导入与下载预案')!.click(); await settle()
    const prepare = calls.invoke.mock.calls.find(call => call[1] === 'dataset.prepare_import')!
    expect(prepare[0]).toBe('project-session')
    expect(prepare[2].request.selected_ids).toEqual(['SRR1'])
    expect(prepare[2].request).not.toHaveProperty('project_id')
    expect(prepare[2].request).not.toHaveProperty('owner_id')
    expect(shadow.querySelector('[role="dialog"]')?.textContent).toContain('PREPARED')
    expect(calls.invoke.mock.calls.some(call => /submit|execute/.test(call[1]))).toBe(false)
  })
  it('opens the original service dialogs, about artwork and pet settings inside ShadowRoot', async () => {
    allowed()
    const { shadow } = await render()
    button(shadow, '打开寻宝排行榜').click(); await settle()
    expect(shadow.querySelector('[role="dialog"]')).not.toBeNull()
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
    button(shadow, '关闭排行榜').click(); await settle()
    button(shadow, '打开使用统计').click(); await settle()
    expect(shadow.querySelector('[role="dialog"]')).not.toBeNull()
    button(shadow, '关闭').click(); await settle()
    button(shadow, '关于').click(); await settle()
    expect(shadow.querySelector('[role="dialog"] img')).not.toBeNull()
    button(shadow, '关闭文献卡片').click(); await settle()
    button(shadow, '桌宠设置').click(); await settle()
    expect(shadow.querySelector('[data-treasure-app]')?.textContent).toContain('体型大小')
  })
  it('switches language/theme only inside the module', async () => {
    allowed()
    const { shadow } = await render()
    const lang = document.documentElement.lang, css = document.documentElement.className
    button(shadow, '切换到英文').click(); await settle()
    expect(shadow.textContent).toContain('Research')
    expect(document.documentElement.lang).toBe(lang)
    const themeButton = [...shadow.querySelectorAll<HTMLButtonElement>('button')].find(el => el.querySelector('svg.lucide-moon'))!
    themeButton.click(); await settle()
    expect(shadow.querySelector('.treasure-island-root.dark')).not.toBeNull()
    expect(document.documentElement.className).toBe(css)
  })
})
