export const SELECTION_LIMIT = 2000
export const SELECTION_KEEP = 1800

export interface ReportSelectionContext {
  title: string
  runId: string
  flowName: string
  section: string
  text: string
}

export interface SelectionPrefill {
  content: string
  truncated: boolean
}

export function buildSelectionPrefill(context: ReportSelectionContext): SelectionPrefill {
  const truncated = context.text.length > SELECTION_LIMIT
  const text = truncated ? `${context.text.slice(0, SELECTION_KEEP)}...（已截断）` : context.text
  const content = [
    '【报告上下文】',
    `报告：${context.title}（run: ${context.runId}，流程：${context.flowName}）`,
    `章节：${context.section || '未命名区域'}`,
    '选中内容：',
    '"""',
    text,
    '"""',
    '请基于上述报告上下文回答我的问题：',
  ].join('\n')
  return { content, truncated }
}
