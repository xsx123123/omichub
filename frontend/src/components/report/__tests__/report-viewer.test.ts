// @vitest-environment jsdom
import { createApp, h, nextTick, reactive } from 'vue'
import { NMessageProvider } from 'naive-ui'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ReportViewerView from '@/views/ReportViewerView.vue'
import { clearReportPreviewContext, ensureReportPreviewContext } from '@/utils/reportPreviewSession'
import type { Report, ReportPreview } from '@/types/report'

const calls = vi.hoisted(() => ({ detail: vi.fn(), preview: vi.fn(), read: vi.fn(), star: vi.fn(),
  download: vi.fn(), push: vi.fn(), resolve: vi.fn() }))
const route = reactive({ params: { reportId: 'report-1' } })
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({
  push: calls.push, resolve: calls.resolve,
}) }))
vi.mock('@/api/report', () => ({ reportApi: {
  getReportDetail: calls.detail, getPreviewUrl: calls.preview, markAsRead: calls.read, toggleStar: calls.star,
}, downloadReportFile: calls.download }))
vi.mock('@/stores/aiAssistantSidebar', () => ({ useAiAssistantSidebarStore: () => ({
  openReportCopilot: vi.fn(), closeReportCopilot: vi.fn(), setReportSectionHandler: vi.fn(),
}) }))

function report(id = 'report-1', extra: Partial<Report> = {}): Report {
  return { id, task_id: 'task', user_id: 'owner', title: `报告 ${id}`, description: '',
    flow_id: 'rna_seq', flow_name: 'RNA-seq', flow_version: '1', flow_icon: '', status: 'completed',
    sample_count: 2, duration: 10, created_at: '2026-10-26', completed_at: null,
    is_read: false, is_starred: false, report_kind: 'scientific',
    files: [{ id: `file-${id}`, report_id: id, name: 'index.html', path: 'output/index.html',
      type: 'html', size: 50, is_primary: true, created_at: '' }], ...extra }
}

function preview(id = 'report-1'): ReportPreview {
  return { url: `/api/v1/reports/${id}/preview-content?token=signed-${id}`,
    expires_at: '2026-10-26T12:00:00Z', channel: `channel-${id}` }
}

async function flush() {
  for (let i = 0; i < 8; i++) { await Promise.resolve(); await nextTick() }
}

let dispose: (() => void) | undefined
async function mountViewer() {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp({ render: () => h(NMessageProvider, null, { default: () => h(ReportViewerView) }) })
  app.mount(host)
  dispose = () => { app.unmount(); host.remove() }
  await flush()
  return host
}

function ready(iframe: HTMLIFrameElement, changes: Record<string, unknown> = {}, source = iframe.contentWindow) {
  window.dispatchEvent(new MessageEvent('message', { origin: 'null', source,
    data: { type: 'cygnusx:report-preview', reportId: route.params.reportId,
      channel: `channel-${route.params.reportId}`, status: 200, ...changes } }))
}

beforeEach(() => {
  vi.clearAllMocks()
  route.params.reportId = 'report-1'
  calls.detail.mockImplementation((id: string) => Promise.resolve({ data: report(id) }))
  calls.preview.mockImplementation((id: string) => Promise.resolve({ data: preview(id) }))
  calls.read.mockResolvedValue({})
  calls.download.mockResolvedValue(undefined)
  calls.resolve.mockReturnValue({ href: '/reports/report-1/view' })
})
afterEach(() => { dispose?.(); dispose = undefined; vi.useRealTimers() })

describe('平台报告查看页', () => {
  it('等待受控加载消息，拒绝其他窗口及旧通道消息', async () => {
    const host = await mountViewer()
    const iframe = host.querySelector('iframe')!
    expect(iframe.getAttribute('sandbox')).toBe('allow-scripts')
    expect(iframe.getAttribute('sandbox')).not.toContain('allow-same-origin')
    expect(iframe.getAttribute('referrerpolicy')).toBe('no-referrer')
    expect(iframe.src).toContain('/api/v1/reports/report-1/preview-content?token=')
    expect(iframe.getAttribute('srcdoc')).toBeNull()
    iframe.dispatchEvent(new Event('load'))
    ready(iframe, {}, window)
    ready(iframe, { channel: 'old-channel' })
    await flush()
    expect(host.textContent).toContain('正在加载报告')
    ready(iframe)
    await flush()
    expect(host.textContent).not.toContain('正在加载报告')
    expect(calls.read).toHaveBeenCalledWith('report-1')
  })

  it('文件404显示明确文案、下载兜底与重试', async () => {
    calls.preview.mockRejectedValueOnce({ response: { status: 404 } })
    const host = await mountViewer()
    expect(host.textContent).toContain('报告或报告文件不存在')
    expect(host.querySelector('iframe')).toBeNull()
    const download = Array.from(host.querySelectorAll('button')).find(b => b.textContent?.includes('下载查看'))!
    download.click()
    await flush()
    expect(calls.download).toHaveBeenCalledWith(report(), 'file-report-1')
    Array.from(host.querySelectorAll('button')).find(b => b.textContent?.trim() === '重试')!.click()
    await flush()
    expect(host.querySelector('iframe')).not.toBeNull()
  })

  it('直达过期报告拒绝签发预览', async () => {
    calls.detail.mockResolvedValue({ data: report('report-1', { status: 'expired' }) })
    const host = await mountViewer()
    expect(host.textContent).toContain('报告已过期')
    expect(calls.preview).not.toHaveBeenCalled()
    expect(host.querySelector('iframe')).toBeNull()
  })

  it('HTML到达后报告文件删除的错误消息不会被当成加载成功', async () => {
    const host = await mountViewer()
    ready(host.querySelector('iframe')!, { status: 404 })
    await flush()
    expect(host.textContent).toContain('报告或报告文件不存在')
    expect(host.querySelector('iframe')).toBeNull()
  })

  it('加载超时清理iframe并提供重试', async () => {
    vi.useFakeTimers()
    const host = await mountViewer()
    vi.advanceTimersByTime(30000)
    await flush()
    expect(host.textContent).toContain('报告加载失败')
    expect(host.querySelector('iframe')).toBeNull()
  })

  it('切换报告后迟到的签名响应不能覆盖新报告', async () => {
    let finish!: (value: { data: ReportPreview }) => void
    calls.preview.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const host = await mountViewer()
    route.params.reportId = 'report-2'
    await flush()
    expect(host.querySelector('iframe')?.src).toContain('report-2')
    finish({ data: preview('report-1') })
    await flush()
    expect(host.querySelector('iframe')?.src).toContain('report-2')
    expect(host.textContent).not.toContain('报告 report-1')
  })

  it('保留执行证据缺口语义并复用收藏和受控新窗口', async () => {
    calls.detail.mockResolvedValue({ data: report('report-1', {
      report_kind: 'reproducibility', evidence_partial: true, template_version: 'audit-v1',
    }) })
    calls.star.mockResolvedValue({ data: report('report-1', { is_starred: true }) })
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const host = await mountViewer()
    expect(host.textContent).toContain('not_run')
    expect(host.textContent).toContain('证据不完整')
    Array.from(host.querySelectorAll('button')).find(b => b.textContent?.trim() === '收藏')!.click()
    await flush()
    expect(calls.star).toHaveBeenCalledWith('report-1', true)
    expect(host.textContent).toContain('取消收藏')
    Array.from(host.querySelectorAll('button')).find(b => b.textContent?.trim() === '新窗口打开')!.click()
    expect(open).toHaveBeenCalledWith(
      '/api/v1/reports/report-1/preview-content?token=signed-report-1', '_blank', 'noopener,noreferrer')
    open.mockRestore()
  })

  it('同步退出登录清除浏览器绑定并立即移除报告iframe', async () => {
    ensureReportPreviewContext()
    expect(document.cookie).toContain('cygnusx_report_context=')
    const host = await mountViewer()
    clearReportPreviewContext()
    await flush()
    expect(document.cookie).not.toContain('cygnusx_report_context=')
    expect(host.querySelector('iframe')).toBeNull()
    expect(host.textContent).toContain('登录状态已失效')
  })
})
