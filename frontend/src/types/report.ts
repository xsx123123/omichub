export type ReportStatus = 'generating' | 'completed' | 'failed' | 'expired'

export interface ReportPreview {
  url: string
  expires_at: string
  channel: string
  load_timeout_seconds?: number
}

export interface ReportFile {
  id: string
  report_id: string
  name: string
  type: 'html' | 'pdf' | 'png' | 'zip' | 'csv' | 'md' | 'json' | 'sha256'
  size: number
  path: string
  is_primary: boolean
  created_at: string
  sha256?: string | null
}

export interface Report {
  id: string
  task_id: string | null
  source_kind?: 'task' | 'external'
  user_id: string
  flow_id: string
  flow_name: string
  flow_version: string
  flow_icon: string
  title: string
  description: string
  status: ReportStatus
  sample_count: number
  duration: number
  created_at: string
  completed_at: string | null
  is_read: boolean
  is_starred: boolean
  files: ReportFile[]
  parent_id?: string | null
  version?: number
  report_kind?: 'scientific' | 'reproducibility' | 'delivery'
  template_version?: string | null
  evidence_partial?: boolean | null
  snapshot_id?: string | null
}

export interface ReportFilter {
  task_id?: string
  keyword?: string
  flow_id?: string
  status?: ReportStatus | ''
  date_range?: '7d' | '30d' | '90d' | ''
  is_starred?: boolean
  page?: number
  page_size?: number
}

export interface ReportListResponse {
  items: Report[]
  total: number
}

export interface ReportStats {
  total: number
  starred: number
  generating: number
  today: number
}

export interface ReportJob {
  id: string
  task_id: string
  status: 'queued' | 'collecting' | 'rendering' | 'publishing' | 'ready' | 'failed'
  template_version: string
  snapshot_id: string | null
  report_id: string | null
  error_message: string
  error_code: string | null
  retryable: boolean
  evidence_partial: boolean
  finished_at: string | null
  attempt_count: number
  created_at: string
  updated_at: string
}

export interface ReportSnapshot {
  id: string
  task_id: string
  run_id: string | null
  schema_version: string
  snapshot_digest: string
  captured_at: string
  payload: Record<string, unknown>
}
