// A revocable browser login context, not a credential by itself. The server
// also requires its signed HttpOnly session cookie and a report-specific URL.
const CONTEXT_COOKIE = 'cygnusx_report_context'
export const REPORT_PREVIEW_AUTH_CLEARED = 'cygnusx:report-preview-auth-cleared'

export function ensureReportPreviewContext(): void {
  if (document.cookie.split(';').some(part =>
    new RegExp(`^${CONTEXT_COOKIE}=[a-f0-9]{64}$`).test(part.trim()),
  )) return
  const bytes = crypto.getRandomValues(new Uint8Array(32))
  const context = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  document.cookie = `${CONTEXT_COOKIE}=${context}; Path=/; SameSite=Strict${location.protocol === 'https:' ? '; Secure' : ''}`
}

export function clearReportPreviewContext(): void {
  document.cookie = `${CONTEXT_COOKIE}=; Path=/; Max-Age=0; SameSite=Strict${location.protocol === 'https:' ? '; Secure' : ''}`
  window.dispatchEvent(new Event(REPORT_PREVIEW_AUTH_CLEARED))
}
