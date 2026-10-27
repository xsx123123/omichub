// @vitest-environment jsdom
/**
 * KimiChatInput roomMode（协作室纯消息场景）发送链路回归测试（jsdom 真实挂载）
 *
 * 背景 bug：P3 复用 KimiChatInput 后，协作室房间内在已有 Case 中按 Enter / 点发送
 * 均无法发出消息。这里以真实挂载 + DOM 事件驱动，验证 roomMode 下
 * Enter 键与发送按钮都能触发 send emit。
 */
import { describe, it, expect, vi } from 'vitest'
import { createApp, h, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { NDialogProvider, NMessageProvider } from 'naive-ui'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))
const apiClientMocks = vi.hoisted(() => ({
  get: vi.fn().mockResolvedValue({ data: {} }),
  post: vi.fn().mockResolvedValue({ data: {} }),
}))
vi.mock('@/api/client', () => ({ default: apiClientMocks }))

import KimiChatInput from '@/components/ai-chat/KimiChatInput.vue'

function mountComposer(props: Record<string, unknown>, onSend: (...args: unknown[]) => void) {
  setActivePinia(createPinia())
  const el = document.createElement('div')
  document.body.appendChild(el)
  const app = createApp({
    render() {
      return h(NMessageProvider, null, {
        default: () =>
          h(NDialogProvider, null, {
            default: () =>
              h(KimiChatInput, {
                modelValue: '',
                'onUpdate:modelValue': () => undefined,
                onSend,
                ...props,
              } as never),
          }),
      })
    },
  })
  app.mount(el)
  return { el, app }
}

async function typeText(el: HTMLElement, text: string) {
  const textarea = el.querySelector<HTMLTextAreaElement>('textarea')!
  textarea.value = text
  textarea.dispatchEvent(new Event('input', { bubbles: true }))
  await nextTick()
  return textarea
}

describe('KimiChatInput roomMode 发送链路', () => {
  it('输入框不再展示创建协作 Case 入口', async () => {
    const { el } = mountComposer({}, () => undefined)
    await nextTick()

    expect(el.textContent).not.toContain('创建协作 Case')
    expect(el.querySelector('[aria-label="更多操作"]')).toBeNull()
  })

  it('roomMode 下按 Enter 触发 send emit', async () => {
    const sends: unknown[][] = []
    const { el } = mountComposer({ roomMode: true }, (...args) => sends.push(args))
    await nextTick()
    const textarea = await typeText(el, '帮我做一下系统发育树呀')
    textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await nextTick()
    expect(sends.length).toBe(1)
    expect(sends[0][0]).toBe('帮我做一下系统发育树呀')
  })

  it('首次打开的普通输入框即使 Enter 被标记为 isComposing 也会发送', async () => {
    const sends: unknown[][] = []
    const { el } = mountComposer({}, (...args) => sends.push(args))
    await nextTick()
    const textarea = await typeText(el, 'hi')
    textarea.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter',
      bubbles: true,
      isComposing: true,
    }))
    await nextTick()
    expect(sends.length).toBe(1)
    expect(sends[0][0]).toBe('hi')
  })

  it('输入法组合态或 keyCode=229 的候选确认不会发送', async () => {
    const sends: unknown[][] = []
    const { el } = mountComposer({ roomMode: true }, (...args) => sends.push(args))
    await nextTick()
    const textarea = await typeText(el, '你好')
    textarea.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }))
    textarea.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter',
      bubbles: true,
      isComposing: true,
    }))
    textarea.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }))
    textarea.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter',
      bubbles: true,
      keyCode: 229,
    }))
    await nextTick()
    expect(sends.length).toBe(0)
  })

  it('Shift+Enter 保留换行行为，不触发发送', async () => {
    const sends: unknown[][] = []
    const { el } = mountComposer({}, (...args) => sends.push(args))
    await nextTick()
    const textarea = await typeText(el, '第一行')
    const event = new KeyboardEvent('keydown', {
      key: 'Enter',
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    })
    textarea.dispatchEvent(event)
    await nextTick()
    expect(event.defaultPrevented).toBe(false)
    expect(sends.length).toBe(0)
  })

  it('roomMode 下点击发送按钮触发 send emit', async () => {
    const sends: unknown[][] = []
    const { el } = mountComposer({ roomMode: true }, (...args) => sends.push(args))
    await nextTick()
    await typeText(el, '@workspace/chat-uploads/a.treefile 帮我做一下系统发育树呀')
    const btn = el.querySelector<HTMLButtonElement>('.send-btn')!
    expect(btn.disabled).toBe(false)
    btn.click()
    await nextTick()
    expect(sends.length).toBe(1)
  })

  it('roomMode 下输入框中的 @ 文件引用会渲染为高亮 pill', async () => {
    const { el } = mountComposer({ roomMode: true }, () => undefined)
    await nextTick()
    await typeText(el, '@workspace/chat-uploads/a.treefile 帮我可视化')
    const highlight = el.querySelector<HTMLElement>('.input-highlight')
    expect(highlight).not.toBeNull()
    expect(highlight!.innerHTML).toContain('mention-chip')
    expect(highlight!.textContent).toContain('@workspace/chat-uploads/a.treefile')
  })

  it('普通文字输入不创建高亮覆盖层，避免每个字符触发覆盖层重绘', async () => {
    const { el } = mountComposer({ roomMode: true }, () => undefined)
    await nextTick()
    await typeText(el, '解卷积解卷积')

    expect(el.querySelector('.input-highlight')).toBeNull()
    expect(el.querySelector('.input-wrapper')?.classList.contains('has-highlight')).toBe(false)
  })
})

describe('KimiChatInput 消息排队条可见性', () => {
  it('AI 回复中且输入框为空时不显示排队提示', async () => {
    const { el } = mountComposer({ isStreaming: true, queuedItems: [] }, () => undefined)
    await nextTick()

    expect(el.querySelector('.queue-strip')).toBeNull()
    expect(el.textContent).not.toContain('AI 正在回复')
  })

  it('AI 回复中输入内容后才显示排队提示', async () => {
    const { el } = mountComposer({ isStreaming: true, queuedItems: [] }, () => undefined)
    await nextTick()
    expect(el.querySelector('.queue-strip')).toBeNull()

    await typeText(el, '再补充一个分析')
    expect(el.querySelector('.queue-strip')).not.toBeNull()
    expect(el.textContent).toContain('AI 正在回复，现在发送的消息将排队等待')
  })

  it('已有排队消息时无论输入框是否为空都显示排队条', async () => {
    const { el } = mountComposer(
      { isStreaming: true, queuedItems: [{ id: 'q1', content: '先前排队的消息' }] },
      () => undefined,
    )
    await nextTick()

    const strip = el.querySelector('.queue-strip')
    expect(strip).not.toBeNull()
    expect(strip!.textContent).toContain('已排队 1 条，当前回复完成后自动发送')
  })

  it('回复结束且无排队消息后排队条消失', async () => {
    const { el, app } = mountComposer(
      { isStreaming: true, queuedItems: [{ id: 'q1', content: '先前排队的消息' }] },
      () => undefined,
    )
    await nextTick()
    expect(el.querySelector('.queue-strip')).not.toBeNull()

    // 模拟流式结束：更新 props 需要重渲染，这里直接换挂一个非流式实例验证默认隐藏
    app.unmount()
    const remounted = mountComposer({ isStreaming: false, queuedItems: [] }, () => undefined)
    await nextTick()
    expect(remounted.el.querySelector('.queue-strip')).toBeNull()
  })
})
