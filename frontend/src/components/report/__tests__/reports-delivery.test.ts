// @vitest-environment jsdom
import { createApp, h, nextTick } from 'vue'
import { NMessageProvider } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import ReportsView from '@/views/ReportsView.vue'
import type { Report } from '@/types/report'

const calls = vi.hoisted(() => ({ detail: vi.fn(), preview: vi.fn(), download: vi.fn(), read: vi.fn(),
  list: vi.fn(), stats: vi.fn(), push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { reportId: 'published-report' } }),
  useRouter: () => ({ push: calls.push }),
}))
vi.mock('@/api/report', () => ({ reportApi: {
  getReportDetail: calls.detail, previewReport: calls.preview, markAsRead: calls.read,
  getReports: calls.list, getReportStats: calls.stats,
}, downloadReportFile: calls.download }))

const report: Report = {
  id: 'published-report', task_id: 'task-1', user_id: 'owner', title: 'RNA-seq 执行证据',
  flow_id: 'rna_seq', flow_name: 'RNA-seq', flow_version: '', flow_icon: '', description: '',
  status: 'completed', sample_count: 2, duration: 0, created_at: '', completed_at: null,
  is_read: false, is_starred: false, report_kind: 'reproducibility', version: 2,
  template_version: 'audit-v1.0.0', evidence_partial: true,
  files: [{ id: 'html-file', report_id: 'published-report', name: 'index.html', type: 'html',
    size: 30, path: 'output/index.html', is_primary: true, created_at: '' }],
}

describe('现有报告中心交付入口', () => {
  it('按生成后的 Report ID 进入平台查看页，保留列表证据标识', async () => {
    calls.detail.mockResolvedValue({ data: report })
    calls.preview.mockResolvedValue({ data: '<h1>Frozen task-1 audit</h1>' })
    calls.list.mockResolvedValue({ data: { items: [report], total: 1 } })
    calls.stats.mockResolvedValue({ data: { total: 1, starred: 0, generating: 0, today: 1 } })
    calls.read.mockResolvedValue({})
    calls.download.mockResolvedValue(undefined)
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = createApp({ render: () => h(NMessageProvider, null, { default: () => h(ReportsView) }) })
    app.mount(host)
    try {
      for (let i = 0; i < 8; i++) { await Promise.resolve(); await nextTick() }
      expect(calls.detail).toHaveBeenCalledWith('published-report')
      expect(calls.push).toHaveBeenCalledWith({ name: 'report-viewer', params: { reportId: report.id } })
      expect(document.querySelector('iframe')).toBeNull()
      expect(document.body.textContent).toContain('证据不完整')
      expect(calls.preview).not.toHaveBeenCalled()
    } finally { app.unmount(); host.remove() }
  })
})
