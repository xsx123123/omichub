import apiClient from '@/api/client'
import type { Report, ReportFilter, ReportJob, ReportListResponse, ReportPreview, ReportSnapshot, ReportStats } from '@/types/report'
import { ensureReportPreviewContext } from '@/utils/reportPreviewSession'

export const reportApi = {
  getReports: (params: ReportFilter) =>
    apiClient.get<ReportListResponse>('/reports', { params }),

  getReportStats: () =>
    apiClient.get<ReportStats>('/reports/stats'),

  getReportDetail: (id: string) =>
    apiClient.get<Report>(`/reports/${id}`),

  previewReport: (id: string) =>
    apiClient.get<string>(`/reports/${id}/preview`),

  getPreviewUrl: (id: string, language: 'zh' | 'en' = 'zh') => {
    ensureReportPreviewContext()
    return apiClient.get<ReportPreview>(`/reports/${id}/preview-url`, { params: { language } })
  },

  createCopilotSession: (id: string) =>
    apiClient.post<{ session_id: string; model_id: string; metadata: Record<string, unknown>; warning?: string | null }>(
      `/reports/${id}/copilot/session`,
    ),

  getCopilotSession: (id: string, sessionId: string) =>
    apiClient.get<{ session_id: string; model_id: string; metadata: Record<string, unknown>; warning?: string | null }>(
      `/reports/${id}/copilot/session`, { params: { session_id: sessionId } },
    ),

  downloadReport: (reportId: string, fileId: string) =>
    apiClient.get<Blob>(`/reports/${reportId}/files/${fileId}/download`, {
      responseType: 'blob',
    }),

  deleteReport: (id: string) =>
    apiClient.delete(`/reports/${id}`),

  toggleStar: (id: string, isStarred: boolean) =>
    apiClient.patch<Report>(`/reports/${id}/star`, { is_starred: isStarred }),

  markAsRead: (id: string) =>
    apiClient.patch<Report>(`/reports/${id}/read`, {}),

  createReproducibilityReport: (taskId: string, runId?: string) =>
    apiClient.post<ReportJob>(`/tasks/${taskId}/reproducibility-reports`, undefined, {
      params: runId ? { run_id: runId } : undefined,
    }),

  getReportJob: (jobId: string) =>
    apiClient.get<ReportJob>(`/reports/jobs/${jobId}`),

  retryReportJob: (jobId: string) =>
    apiClient.post<ReportJob>(`/reports/jobs/${jobId}/retry`),

  getReportSnapshot: (reportId: string) =>
    apiClient.get<ReportSnapshot>(`/reports/${reportId}/snapshot`),

  buildDeliveryPackage: (reportId: string) =>
    apiClient.post<Report>(`/reports/${reportId}/delivery`),
}

// Use the authenticated axios client; a bare anchor does not carry the Bearer token.
export async function downloadReportFile(report: Report, fileId: string): Promise<void> {
  const response = await reportApi.downloadReport(report.id, fileId)
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = report.files.find(file => file.id === fileId)?.name || 'report.html'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
