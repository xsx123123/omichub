import { describe, expect, it } from 'vitest'
import { SELECTION_KEEP, SELECTION_LIMIT, buildSelectionPrefill } from '@/utils/reportSelection'

const base = {
  title: '番茄转录组分析报告',
  runId: 'X101SC26098749-Z01-J001',
  flowName: 'RNA-seq',
  section: '差异表达分析',
  text: 'Salt_A 组上调基因 751 个',
}

describe('buildSelectionPrefill', () => {
  it('follows the F8 context template', () => {
    const { content, truncated } = buildSelectionPrefill(base)
    expect(truncated).toBe(false)
    expect(content).toContain('【报告上下文】')
    expect(content).toContain('报告：番茄转录组分析报告（run: X101SC26098749-Z01-J001，流程：RNA-seq）')
    expect(content).toContain('章节：差异表达分析')
    expect(content).toContain('"""\nSalt_A 组上调基因 751 个\n"""')
    expect(content.endsWith('请基于上述报告上下文回答我的问题：')).toBe(true)
  })

  it('truncates overlong selections with a marker', () => {
    const text = 'a'.repeat(SELECTION_LIMIT + 500)
    const { content, truncated } = buildSelectionPrefill({ ...base, text })
    expect(truncated).toBe(true)
    expect(content).toContain(`${'a'.repeat(SELECTION_KEEP)}...（已截断）`)
    expect(content).not.toContain('a'.repeat(SELECTION_KEEP + 1))
  })

  it('falls back to 未命名区域 when section is empty', () => {
    const { content } = buildSelectionPrefill({ ...base, section: '' })
    expect(content).toContain('章节：未命名区域')
  })
})
