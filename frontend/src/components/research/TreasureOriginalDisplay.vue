<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { loadTreasureIsland } from './treasureIslandLoader'
import type { TreasureIslandHandle, TreasureIslandProps } from '@/types/treasureIsland'
const props = withDefaults(defineProps<{
  draft: string; disabled: boolean; streaming: boolean; projectId: string | null
  mode?: 'welcome' | 'composer' | 'pet' | 'app'
  presentation?: Partial<TreasureIslandProps>
  focusDraft?: boolean
}>(), { mode: 'welcome' })
const emit = defineEmits<{
  'update:draft': [value: string]; submit: [text: string]; cancel: []; example: [text: string]
}>()
const host = ref<HTMLElement>()
const theme = ref<'light' | 'dark'>('light')
const locale = ref<'zh' | 'en'>('zh')
const failure = ref('')
let handle: TreasureIslandHandle | undefined
let disposed = false
let observer: MutationObserver | undefined
let draftFocused = false
function focusInitialDraft() {
  if (!props.focusDraft || props.disabled || draftFocused) return
  const input = host.value?.shadowRoot?.querySelector<HTMLTextAreaElement>('textarea:not(:disabled)')
  if (!input) return
  input.focus({ preventScroll: true })
  draftFocused = true
}
function syncAppearance() {
  theme.value = document.documentElement.dataset.theme === 'dark' || document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  locale.value = document.documentElement.lang.startsWith('en') ? 'en' : 'zh'
}
const view = computed<TreasureIslandProps>(() => ({
  context: { projectId: props.projectId, projectName: '', locale: locale.value, theme: theme.value },
  messages: [], mode: props.mode, modelOptions: ['平台默认模型'], selectedModel: '平台默认模型',
  draft: props.draft, streaming: props.streaming, disabled: props.disabled,
  onDraftChange: value => emit('update:draft', value), onSubmit: value => emit('submit', value),
  onPickExample: value => emit('example', value), onCancel: () => emit('cancel'),
  onSelectModel: () => {}, onOpenDataset: () => {},
  onLocaleChange: value => { locale.value = value },
  onThemeChange: () => { theme.value = theme.value === 'dark' ? 'light' : 'dark' },
  ...props.presentation,
}))
watch([view, () => props.focusDraft], ([value]) => {
  handle?.update(value)
  focusInitialDraft()
})
onMounted(async () => {
  syncAppearance()
  observer = new MutationObserver(syncAppearance)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme', 'lang'] })
  try {
    const island = await loadTreasureIsland()
    if (!disposed && host.value) {
      handle = island.mount(host.value, view.value)
      focusInitialDraft()
    }
  } catch { if (!disposed) failure.value = '寻宝鼠界面资源加载失败，请刷新页面；若仍失败，请重新构建前端。' }
})
onUnmounted(() => { disposed = true; observer?.disconnect(); handle?.unmount() })
</script>
<template>
  <div class="original-display" :class="{ 'composer-only': mode === 'composer', 'app-display': mode === 'app' }">
    <p v-if="failure" role="alert">{{ failure }}</p>
    <div v-else ref="host" class="original-display-host" />
  </div>
</template>
<style scoped>
.original-display { display: flex; flex: 1; min-height: 0; min-width: 0; }
.original-display.app-display { height: 100%; overflow: hidden; }
.original-display.app-display .original-display-host { height: 100%; }
.original-display.composer-only { flex: 0 0 auto; }
.original-display-host { flex: 1; min-width: 0; }
</style>
