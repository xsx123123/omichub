import { h, onScopeDispose } from 'vue'
import { useNotification } from 'naive-ui'
import { welcomeApi, type WelcomeClaim } from '@/api/welcome'
import { useAuthStore } from '@/stores/auth'

const pending = new Set<string>()
const flagKey = (id: string) => `cygnusx:welcome:shown:${id}`

export function useWelcomeToast() {
  const notification = useNotification()
  const auth = useAuthStore()
  let alive = true
  let observer: MutationObserver | null = null
  onScopeDispose(() => { alive = false; observer?.disconnect() })

  function present(item: WelcomeClaim, id: string, key: string) {
    if (!alive || auth.user?.id !== id || !auth.isLoggedIn || auth.pendingOnboarding || sessionStorage.getItem(key)) return
    const expiresAt = Date.parse(item.reservation_expires_at)
    if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) return
    if (document.querySelector('[role="dialog"][aria-modal="true"], [role="alertdialog"], .n-modal-container .n-modal, .n-message-container .n-message')) {
      // Wait for dialogs and existing success/error messages to leave explicitly.
      // In particular, the login confirmation must not cover the toast on mobile.
      observer?.disconnect()
      observer = new MutationObserver(() => {
        observer?.disconnect()
        observer = null
        present(item, id, key)
      })
      observer.observe(document.body, { childList: true, subtree: true, attributes: true })
      return
    }
    notification.create({
      title: item.title,
      content: () => h('div', { role: 'status', 'aria-live': 'polite', 'aria-atomic': 'true',
        style: { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: '40vh', overflowY: 'auto' },
      }, item.message),
      type: 'success',
      duration: item.duration_ms,
      closable: true,
      keepAliveOnHover: true,
    })
    sessionStorage.setItem(key, '1')
    void welcomeApi.impression(item.delivery_id).catch(() => {})
  }

  function skipThisSession() {
    if (auth.user) sessionStorage.setItem(flagKey(auth.user.id), 'onboarding')
  }

  async function triggerWelcome() {
    const id = auth.user?.id
    if (!id || !auth.isLoggedIn || !alive) return
    if (auth.pendingOnboarding) {
      skipThisSession()
      return
    }
    const key = flagKey(id)
    if (sessionStorage.getItem(key) || pending.has(id)) return
    pending.add(id)
    try {
      const item = await welcomeApi.claim()
      if (!item || !alive || auth.user?.id !== id || !auth.isLoggedIn || auth.pendingOnboarding || sessionStorage.getItem(key)) return
      present(item, id, key)
    } catch {
      // An optional welcome must never interrupt authentication or show an error dialog.
    } finally {
      pending.delete(id)
    }
  }

  return { triggerWelcome, skipThisSession }
}
