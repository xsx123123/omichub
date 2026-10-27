// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { useWelcomeToast } from '@/composables/useWelcomeToast'

const state = vi.hoisted(() => ({
  auth: { user: { id: 'user-a' } as { id: string } | null, isLoggedIn: true, pendingOnboarding: false },
  create: vi.fn(), claim: vi.fn(), impression: vi.fn(),
}))
vi.mock('naive-ui', () => ({ useNotification: () => ({ create: state.create }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => state.auth }))
vi.mock('@/api/welcome', () => ({ welcomeApi: { claim: state.claim, impression: state.impression } }))
const scopes: ReturnType<typeof effectScope>[] = []
function setup() {
  const scope = effectScope()
  scopes.push(scope)
  return scope.run(() => useWelcomeToast())!
}
beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  document.body.innerHTML = ''
  state.auth.user = { id: 'user-a' }
  state.auth.isLoggedIn = true
  state.auth.pendingOnboarding = false
  state.claim.mockResolvedValue({ delivery_id: 'delivery-a', reservation_expires_at: new Date(Date.now() + 300000).toISOString(), title: '欢迎回来', message: '<b>安全文本</b>', duration_ms: 5000 })
  state.impression.mockResolvedValue(undefined)
})
afterEach(() => { scopes.splice(0).forEach(s => s.stop()) })

describe('欢迎语交付', () => {
  it('展示安全字符串并回执；刷新和重复 mount 不重复领取', async () => {
    const welcome = setup()
    await Promise.all([welcome.triggerWelcome(), welcome.triggerWelcome(), setup().triggerWelcome()])
    expect(state.claim).toHaveBeenCalledTimes(1)
    expect(state.create).toHaveBeenCalledWith(expect.objectContaining({ closable: true }))
    const content = state.create.mock.calls[0][0].content()
    expect(content.children).toBe('<b>安全文本</b>')
    expect(content.props['aria-live']).toBe('polite')
    expect(state.impression).toHaveBeenCalledWith('delivery-a')
    await setup().triggerWelcome()
    expect(state.claim).toHaveBeenCalledTimes(1)
  })
  it('首次登录会话即使消费 onboarding 标记或重新 mount 也跳过', async () => {
    state.auth.pendingOnboarding = true
    await setup().triggerWelcome()
    state.auth.pendingOnboarding = false
    await setup().triggerWelcome()
    expect(state.claim).not.toHaveBeenCalled()
  })
  it('布局显式跳过标记保持到会话结束，账号之间隔离', async () => {
    setup().skipThisSession()
    await setup().triggerWelcome()
    expect(state.claim).not.toHaveBeenCalled()
    state.auth.user = { id: 'user-b' }
    await setup().triggerWelcome()
    expect(state.claim).toHaveBeenCalledTimes(1)
  })
  it('服务无内容或失败时静默，不展示固定兜底', async () => {
    state.claim.mockResolvedValueOnce(null)
    await setup().triggerWelcome()
    state.claim.mockRejectedValueOnce(new Error('offline'))
    await setup().triggerWelcome()
    expect(state.create).not.toHaveBeenCalled()
    expect(state.impression).not.toHaveBeenCalled()
  })
  it('请求过程中退出或切换账号时丢弃响应', async () => {
    let resolve!: (value: unknown) => void
    state.claim.mockReturnValueOnce(new Promise(r => { resolve = r }))
    const pending = setup().triggerWelcome()
    state.auth.user = { id: 'user-b' }
    resolve({ delivery_id: 'stale', message: 'stale', title: 'stale' })
    await pending
    expect(state.create).not.toHaveBeenCalled()
  })
})

it('等待强制交互对话框关闭后再展示，不依赖延时', async () => {
  const modal = document.createElement('div')
  modal.setAttribute('role', 'dialog')
  modal.setAttribute('aria-modal', 'true')
  document.body.append(modal)
  await setup().triggerWelcome()
  expect(state.create).not.toHaveBeenCalled()
  modal.remove()
  await Promise.resolve()
  expect(state.create).toHaveBeenCalledTimes(1)
  expect(state.impression).toHaveBeenCalledWith('delivery-a')
})

it('等待已有消息关闭后展示，避免登录反馈或重要错误盖住欢迎语', async () => {
  const container = document.createElement('div')
  container.className = 'n-message-container'
  const feedback = document.createElement('div')
  feedback.className = 'n-message'
  container.append(feedback)
  document.body.append(container)
  await setup().triggerWelcome()
  expect(state.create).not.toHaveBeenCalled()
  expect(state.impression).not.toHaveBeenCalled()
  feedback.remove()
  await Promise.resolve()
  expect(state.create).toHaveBeenCalledTimes(1)
  expect(state.impression).toHaveBeenCalledWith('delivery-a')
})
