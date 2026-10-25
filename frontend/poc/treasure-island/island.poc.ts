// @vitest-environment jsdom
import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, type TreasureIslandProps } from '@treasure-island-poc'
import App from './App.vue'
const cleanups: (() => void)[] = []
afterEach(() => { cleanups.splice(0).reverse().forEach(fn => fn()); vi.restoreAllMocks() })
function props(): TreasureIslandProps {
  return {
    context: { projectId: null, projectName: '只读', locale: 'zh', theme: 'light' },
    messages: [], modelOptions: ['A', 'B'], selectedModel: 'A', draft: '', streaming: false, disabled: false,
    onDraftChange: vi.fn(), onSubmit: vi.fn(), onPickExample: vi.fn(), onCancel: vi.fn(),
    onSelectModel: vi.fn(), onOpenDataset: vi.fn(),
  }
}
function host() { const el = document.createElement('div'); document.body.append(el); cleanups.push(() => el.remove()); return el }
describe('original React display island contract', () => {
  it('S5-B renders blocked catalog and disables business actions without server grants', () => {
    const el = host(), p = props()
    const workflow = {
      open: true, busy: false, projectSelected: true, allowedTools: [], catalogStatus: 'AVAILABLE' as const,
      downloadCapabilities: [{ source: 'ftp', states: ['CODE_AVAILABLE', 'EXECUTION_BLOCKED'], reasons: ['TRANSPORT_RUNTIME_UNVERIFIED'], executionAllowed: false as const }],
      gaps: [], samples: [], relations: [], files: [], datasets: [], assets: [], workflows: [], proposals: [], tasks: [], reports: [], sources: [], deliveryStatus: 'UNKNOWN',
    }
    const handle = mount(el, { ...p, mode: 'app', workflow, onResearchAction: vi.fn() })
    cleanups.push(handle.unmount)
    const shadow = el.shadowRoot!
    expect(shadow.textContent).toContain('EXECUTION_BLOCKED')
    expect(shadow.textContent).toContain('TRANSPORT_RUNTIME_UNVERIFIED')
    const assets = [...shadow.querySelectorAll<HTMLButtonElement>('button')].filter(button => button.textContent?.includes('项目数据资产'))
    expect(assets.length).toBeGreaterThan(0)
    expect(assets.every(button => button.disabled)).toBe(true)
    expect(shadow.querySelector('textarea')).not.toBeNull()
    expect(shadow.textContent).not.toContain('下载成功')
  })
  it('renders four original scenes and eight examples with callbacks', () => {
    const el = host(), p = props(), handle = mount(el, p)
    cleanups.push(handle.unmount)
    const scenes = el.shadowRoot!.querySelectorAll('section')
    expect(scenes).toHaveLength(4)
    expect(el.querySelector('textarea')).toBeNull()
    scenes.forEach(scene => (scene.querySelector('button') as HTMLButtonElement).click())
    expect(p.onPickExample).toHaveBeenCalledTimes(4)
    expect(el.shadowRoot!.querySelectorAll('section button')).toHaveLength(8)
    expect(el.shadowRoot!.querySelector('img')?.src).toMatch(/mouse-base.*\.webp/)
  })
  it('uses controlled draft, model, disabled and stop callbacks', () => {
    const el = host(), p = props(), handle = mount(el, { ...p, draft: 'GSE123' })
    cleanups.push(handle.unmount)
    const shadow = el.shadowRoot!
    ;(shadow.querySelector('textarea')!.nextElementSibling as HTMLButtonElement).click()
    expect(p.onSubmit).toHaveBeenCalledWith('GSE123')
    expect(p.onDraftChange).toHaveBeenCalledWith('')
    const select = shadow.querySelector('select')!
    select.value = 'B'; select.dispatchEvent(new Event('change', { bubbles: true }))
    expect(p.onSelectModel).toHaveBeenCalledWith('B')
    handle.update({ ...p, streaming: true })
    ;(shadow.querySelector('textarea')!.nextElementSibling as HTMLButtonElement).click()
    expect(p.onCancel).toHaveBeenCalledTimes(1)
    handle.update({ ...p, disabled: true })
    expect(shadow.querySelector('textarea')!.disabled).toBe(true)
    expect([...shadow.querySelectorAll('section button')].every(el => (el as HTMLButtonElement).disabled)).toBe(true)
  })
  it('updates locale and theme without platform language, title or storage mutations', () => {
    const title = document.title, lang = document.documentElement.lang, htmlClass = document.documentElement.className
    const spy = vi.spyOn(Storage.prototype, 'setItem')
    const reads = vi.spyOn(Storage.prototype, 'getItem')
    const el = host(), p = props(), handle = mount(el, p)
    cleanups.push(handle.unmount)
    handle.update({ ...p, context: { ...p.context, locale: 'en', theme: 'dark' } })
    expect(el.shadowRoot!.querySelector('.dark')?.getAttribute('lang')).toBe('en')
    expect(el.shadowRoot!.querySelector('h1')!.textContent).not.toMatch(/[\u4e00-\u9fff]/)
    expect(document.title).toBe(title)
    expect(document.documentElement.lang).toBe(lang)
    expect(document.documentElement.className).toBe(htmlClass)
    expect(spy).not.toHaveBeenCalled()
    expect(reads).not.toHaveBeenCalled()
    const fonts = document.head.querySelector('[data-treasure-island-fonts]')?.textContent
    expect(fonts).toMatch(/^@font-face/)
    expect(fonts).not.toContain('.dark')
  })
  it('keeps the easter-egg portal inside the shadow tree and cleans focus guards', async () => {
    const el = host(), p = props(), handle = mount(el, p)
    cleanups.push(handle.unmount)
    const bodyStyle = document.body.getAttribute('style')
    const trigger = el.shadowRoot!.querySelector('button')!
    for (let i = 0; i < 3; i++) trigger.click()
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(el.shadowRoot!.querySelector('[role=dialog]')).not.toBeNull()
    expect(el.shadowRoot!.querySelector('[data-treasure-dialog-backdrop]')).not.toBeNull()
    expect(document.querySelector('[role=dialog]')).toBeNull()
    expect(document.body.getAttribute('style')).toBe(bodyStyle)
    handle.unmount()
    expect(document.querySelector('[data-radix-focus-guard]')).toBeNull()
    expect(document.querySelector('[aria-hidden=true]')).toBeNull()
  })
  it('wraps Tab inside the shadow dialog and restores the avatar on close', async () => {
    const el = host(), handle = mount(el, props())
    cleanups.push(handle.unmount)
    const shadow = el.shadowRoot!, trigger = shadow.querySelector('button')!
    trigger.focus()
    for (let i = 0; i < 3; i++) trigger.click()
    await new Promise(resolve => setTimeout(resolve, 20))
    const dialog = shadow.querySelector<HTMLElement>('[role=dialog]')!
    const buttons = dialog.querySelectorAll('button')
    expect(shadow.activeElement).toBe(buttons[0])
    buttons[buttons.length - 1].focus()
    buttons[buttons.length - 1].dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, composed: true, cancelable: true }))
    expect(shadow.activeElement).toBe(buttons[0])
    buttons[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, composed: true, cancelable: true }))
    expect(shadow.activeElement).toBe(buttons[buttons.length - 1])
    buttons[0].click()
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(shadow.querySelector('[role=dialog]')).toBeNull()
    expect(shadow.querySelector('[data-treasure-dialog-backdrop]')).toBeNull()
    expect(shadow.activeElement).toBe(trigger)
  })
  it('requires app mode for message rendering instead of silently dropping messages', () => {
    const el = host(), p = props()
    expect(() => mount(el, { ...p, messages: [{ id: 'm', role: 'assistant', content: 'preserve me' }] })).toThrow('app presentation mode')
    expect(el.shadowRoot).toBeNull()
  })
  it('unmounts idempotently and remounts without retained styles or DOM', () => {
    const el = host(), p = props()
    for (let i = 0; i < 2; i++) {
      const handle = mount(el, p)
      expect(() => mount(el, p)).toThrow('already mounted')
      expect(document.head.querySelectorAll('[data-treasure-island-fonts]')).toHaveLength(1)
      handle.unmount(); handle.unmount()
      expect(el.shadowRoot!.childNodes).toHaveLength(0)
      expect(document.head.querySelectorAll('[data-treasure-island-fonts]')).toHaveLength(0)
      expect(() => handle.update(p)).toThrow('unmounted')
    }
  })
  it('enters and leaves the Vue wrapper twice without network requests', async () => {
    const network = vi.spyOn(globalThis, 'fetch')
    const el = host(), app = createApp(App)
    app.mount(el); cleanups.push(() => app.unmount())
    for (let i = 0; i < 2; i++) {
      await nextTick()
      expect(el.querySelector('#treasure-island-host')!.shadowRoot!.querySelectorAll('section')).toHaveLength(4)
      ;(el.querySelector('#route-toggle') as HTMLButtonElement).click(); await nextTick()
      expect(el.querySelector('#treasure-island-host')).toBeNull()
      expect(document.head.querySelector('[data-treasure-island-fonts]')).toBeNull()
      ;(el.querySelector('#route-toggle') as HTMLButtonElement).click()
    }
    await nextTick()
    expect(network).not.toHaveBeenCalled()
  })
})
