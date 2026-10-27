// @vitest-environment jsdom
import { createApp, h, nextTick } from 'vue'
import { NConfigProvider } from 'naive-ui'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as XLSX from 'xlsx'
import ArtifactTablePreview from '../ArtifactTablePreview.vue'
import { decodeTableText, parseArtifactTable, TABLE_CONFIRM_BYTES } from '@/utils/artifactTablePreview'

vi.setConfig({ testTimeout: 15_000 })
const apps: ReturnType<typeof createApp>[] = []
afterEach(() => {
  apps.forEach((app) => app.unmount())
  apps.length = 0
  document.body.innerHTML = ''
})
const bytes = (text: string) => new TextEncoder().encode(text).buffer
async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 30))
  await nextTick()
}
async function mount(fileName: string, blob: Blob, size?: number) {
  const loadBlob = vi.fn(async () => blob)
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp({ render: () => h(NConfigProvider, null, {
    default: () => h(ArtifactTablePreview, { fileName, loadBlob, size }),
  }) })
  apps.push(app)
  app.mount(host)
  await vi.waitFor(() => expect(host.querySelector('.n-spin')).toBeNull(), { timeout: 10_000 })
  await nextTick()
  return { host, loadBlob }
}

describe('structured artifact tables', () => {
  it('keeps quoted delimiters/newlines, counts all records, retains only 100 rows', async () => {
    const content = 'gene,description,value\r\n' + Array.from({ length: 125 }, (_, i) =>
      `TP${i},"Chinese, platform\nsecond line",${i / 10}`).join('\r\n')
    const [sheet] = await parseArtifactTable(bytes(content), 'csv')
    expect(sheet.totalRows).toBe(125)
    expect(sheet.rows).toHaveLength(100)
    expect(sheet.rows[0]).toEqual(['TP0', 'Chinese, platform\nsecond line', '0'])
  })

  it('decodes BOM, UTF-16 and GBK Chinese without replacement characters', () => {
    expect(decodeTableText(bytes('\uFEFF样本,数值'))).toBe('样本,数值')
    expect(decodeTableText(new Uint8Array([0xff, 0xfe, 0x37, 0x68, 0x2c, 0x00]).buffer)).toBe('样,')
    expect(decodeTableText(new Uint8Array([0xd1, 0xf9, 0xb1, 0xbe]).buffer)).toBe('样本')
  })

  it('renders a wide uppercase TSV as aligned columns with capped widths and numeric alignment', async () => {
    const header = Array.from({ length: 16 }, (_, i) => `column${i}`)
    const data = Array.from({ length: 130 }, (_, i) =>
      [String(i), '长平台名'.repeat(40), ...Array(14).fill('sample')].join('\t'))
    const { host } = await mount('GSE280781_sample_manifest.TSV', new Blob([[header.join('\t'), ...data].join('\n')]))
    expect(host.querySelectorAll('th')).toHaveLength(16)
    expect(host.querySelectorAll('tbody tr')).toHaveLength(100)
    expect(host.textContent).toContain('共 130 行，预览前 100 行，下载查看完整数据')
    expect(host.querySelector('td')?.style.textAlign).toBe('right')
    expect(host.querySelectorAll('col')[1]?.getAttribute('style')).toContain('240px')
  })

  it.each(['xlsx', 'xls'] as const)('previews %s, limits parsed worksheet rows and switches all sheets', async (bookType) => {
    const workbook = XLSX.utils.book_new()
    for (let index = 0; index < 4; index++) {
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([
        ['gene', 'score'], ...Array.from({ length: 120 }, (_, i) => [`sheet${index}-gene${i}`, i]),
      ]), `Sheet${index + 1}`)
    }
    const buffer = XLSX.write(workbook, { type: 'array', bookType })
    const parsed = await parseArtifactTable(buffer, bookType)
    expect(parsed).toHaveLength(4)
    expect(parsed[0].rows).toHaveLength(100)
    expect(parsed[0].totalRows).toBe(120)
    const { host } = await mount(`results.${bookType}`, new Blob([buffer]))
    expect(host.textContent).toContain('sheet0-gene0')
    const tabs = host.querySelectorAll<HTMLElement>('.n-tabs-tab')
    expect(tabs).toHaveLength(4)
    tabs[3].click()
    await settle()
    expect(host.textContent).toContain('sheet3-gene0')
    expect(host.textContent).not.toContain('sheet0-gene0')
  })

  it.each(['', 'gene,score\n'])('shows the empty placeholder for zero data rows', async (content) => {
    const { host } = await mount('empty.csv', new Blob([content]))
    expect(host.textContent).toContain('该产物为空表格')
    expect(host.querySelector('table')).toBeNull()
  })

  it.each([
    ['broken.csv', 'gene,value\n"unterminated'],
    ['broken.xlsx', '<script>alert("bad")</script>'],
  ])('silently falls back to safe plain text for %s', async (name, content) => {
    const { host } = await mount(name, new Blob([content]))
    expect(host.querySelector('pre')?.textContent).toBe(content)
    expect(host.querySelector('script')).toBeNull()
    expect(host.textContent).not.toContain('预览加载失败')
  })

  it('requires confirmation before fetching a known large file', async () => {
    const { host, loadBlob } = await mount('large.csv', new Blob(['gene,value\nTP53,2']), TABLE_CONFIRM_BYTES + 1)
    expect(loadBlob).not.toHaveBeenCalled()
    expect(host.textContent).toContain('超过 5 MB')
    host.querySelector<HTMLButtonElement>('button')!.click()
    await settle()
    expect(loadBlob).toHaveBeenCalledTimes(1)
    expect(host.textContent).toContain('TP53')
  })

  it('also requires confirmation before parsing an unreported large blob', async () => {
    const { host, loadBlob } = await mount('large.csv', new Blob(['gene,value\nTP53,2\n', ' '.repeat(TABLE_CONFIRM_BYTES)]))
    expect(host.querySelector('table')).toBeNull()
    expect(host.textContent).toContain('超过 5 MB')
    host.querySelector<HTMLButtonElement>('button')!.click()
    await settle()
    expect(loadBlob).toHaveBeenCalledTimes(1)
    expect(host.textContent).toContain('TP53')
  })
})
