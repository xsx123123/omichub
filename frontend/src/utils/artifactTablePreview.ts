import Papa from 'papaparse'

export const TABLE_PREVIEW_ROWS = 100
export const TABLE_CONFIRM_BYTES = 5 * 1024 * 1024
export const TABLE_EXTENSIONS = new Set(['csv', 'tsv', 'xlsx', 'xls'])

export interface ArtifactSheetPreview {
  name: string
  header: string[]
  rows: string[][]
  totalRows: number
}

/** Strict decoding avoids silently treating legacy Chinese text as broken UTF-8. */
export function decodeTableText(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let encoding = 'utf-8'
  if (bytes[0] === 0xff && bytes[1] === 0xfe) encoding = 'utf-16le'
  else if (bytes[0] === 0xfe && bytes[1] === 0xff) encoding = 'utf-16be'
  try {
    return new TextDecoder(encoding, { fatal: true }).decode(bytes).replace(/^\uFEFF/, '')
  } catch {
    return new TextDecoder('gb18030', { fatal: true }).decode(bytes)
  }
}

function sheet(name: string, records: string[][], totalRows: number): ArtifactSheetPreview {
  const width = Math.max(0, ...records.map((row) => row.length))
  return {
    name,
    header: Array.from({ length: width }, (_, index) => records[0]?.[index] || `列 ${index + 1}`),
    rows: records.slice(1, TABLE_PREVIEW_ROWS + 1).map((row) =>
      Array.from({ length: width }, (_, index) => row[index] ?? '')),
    totalRows,
  }
}

export async function parseArtifactTable(
  buffer: ArrayBuffer,
  extension: string,
): Promise<ArtifactSheetPreview[]> {
  if (extension === 'csv' || extension === 'tsv') {
    const content = decodeTableText(buffer)
    if (content.includes('\u0000')) throw new Error('Binary table')
    const records: string[][] = []
    let count = 0
    let invalid = false
    // Scan for the total count, but retain only the header and first 100 records.
    Papa.parse<string[]>(content, {
      delimiter: extension === 'tsv' ? '\t' : ',',
      skipEmptyLines: 'greedy',
      step: (result) => {
        invalid ||= result.errors.length > 0
        if (count <= TABLE_PREVIEW_ROWS) records.push(result.data)
        count++
      },
    })
    if (invalid) throw new Error('Malformed delimited table')
    return [sheet('数据表', records, Math.max(0, count - 1))]
  }

  if (!buffer.byteLength) return [sheet('数据表', [], 0)]
  const bytes = new Uint8Array(buffer)
  // SheetJS also accepts arbitrary text; require an actual Excel container.
  const zip = bytes[0] === 0x50 && bytes[1] === 0x4b
  const ole = bytes[0] === 0xd0 && bytes[1] === 0xcf
  const biff = bytes[0] === 0x09 && [0x00, 0x02, 0x04, 0x08].includes(bytes[1])
  if (!zip && !ole && !biff) throw new Error('Invalid workbook')
  const XLSX = await import('xlsx')
  const workbook = XLSX.read(buffer, {
    type: 'array', sheetRows: TABLE_PREVIEW_ROWS + 1, dense: false,
  })
  if (!workbook.SheetNames.length) throw new Error('Missing worksheets')
  return workbook.SheetNames.map((name) => {
    const worksheet = workbook.Sheets[name]
    const range = worksheet['!fullref'] || worksheet['!ref']
    const totalRows = range ? XLSX.utils.decode_range(range).e.r : 0
    const records = XLSX.utils.sheet_to_json<string[]>(worksheet, {
      header: 1, raw: false, defval: '', blankrows: true, range: 0,
    })
    return sheet(name, records, totalRows)
  })
}

export function isNumericColumn(rows: string[][], index: number): boolean {
  const samples = rows.slice(0, 30).map((row) => row[index]?.trim()).filter(Boolean)
  return samples.length > 0 && samples.every((value) =>
    /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?%?$/i.test(value!))
}
