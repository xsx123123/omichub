<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NCard, NDatePicker, NEmpty, NInput, NInputNumber, NSelect, NSpace, NTag, useMessage } from 'naive-ui'
import { welcomeApi, type WelcomeBatch } from '@/api/welcome'

const message = useMessage()
const batches = ref<WelcomeBatch[]>([])
const selected = ref<WelcomeBatch | null>(null)
const target = ref<number | null>(null)
const audience = ref<'admin' | 'general'>('admin')
const revision = ref(1)
const note = ref('')
const busy = ref(false)
const audiences = [{ label: '管理员', value: 'admin' }, { label: '普通用户', value: 'general' }]

async function run(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  try { await action() } catch { message.error('操作失败，请检查权限、批次状态和服务状态') }
  finally { busy.value = false }
}
async function refresh() { batches.value = await welcomeApi.batches() }
async function open(id: string) { selected.value = await welcomeApi.detail(id) }
async function generate() {
  if (!target.value) { message.warning('请选择目标周的周一'); return }
  const date = new Date(target.value)
  if (date.getDay() !== 1) { message.warning('目标日期必须为周一'); return }
  const day = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  await welcomeApi.generate(day, audience.value, revision.value)
  message.success('生成任务已入队，可刷新查看进度；补生成请增加修订号')
  await refresh()
}
async function review(action: 'publish' | 'withdraw' | 'rollback') {
  if (!selected.value || !note.value.trim()) { message.warning('请填写审核说明'); return }
  await welcomeApi.review(selected.value.id, action, note.value)
  await open(selected.value.id)
  await refresh()
}
async function toggle(id: string, enabled: boolean) {
  if (!note.value.trim()) { message.warning('请填写审核说明'); return }
  await welcomeApi.setEnabled(id, enabled, note.value)
  if (selected.value) await open(selected.value.id)
}
onMounted(() => { void run(refresh) })
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="欢迎语内容池">
      <p>每周离线生成并校验，周一发布。普通用户展示开关默认关闭，首次登录引导优先。</p>
      <NSpace align="center">
        <NDatePicker v-model:value="target" type="date" aria-label="目标周一" />
        <NSelect v-model:value="audience" :options="audiences" style="width: 140px" aria-label="受众" />
        <NInputNumber v-model:value="revision" :min="1" :max="10000" aria-label="修订号" />
        <NButton :loading="busy" @click="run(generate)">生成 / 补生成</NButton>
        <NButton :disabled="busy" @click="run(refresh)">刷新</NButton>
      </NSpace>
    </NCard>
    <NEmpty v-if="!batches.length" description="暂无内容池" />
    <NSpace wrap>
      <NButton v-for="batch in batches" :key="batch.id" @click="run(() => open(batch.id))">
        {{ batch.week_start }} · {{ batch.audience }} · r{{ batch.revision }} · {{ batch.status }}
      </NButton>
    </NSpace>
    <NCard v-if="selected" :title="`${selected.week_start} · ${selected.audience} · r${selected.revision}`">
      <NTag>{{ selected.status }}</NTag>
      <p>提示词 {{ selected.prompt_version }} · {{ selected.prompt_sha256 }}</p>
      <NInput v-model:value="note" placeholder="审核、撤回、回滚或禁用说明" aria-label="审核说明" />
      <NSpace style="margin-top: 12px">
        <NButton :disabled="busy || !['scheduled', 'validated'].includes(selected.status)" @click="run(() => review('publish'))">审核并发布</NButton>
        <NButton :disabled="busy || selected.status !== 'retired'" @click="run(() => review('rollback'))">回滚至此批</NButton>
        <NButton :disabled="busy || selected.status === 'withdrawn'" @click="run(() => review('withdraw'))">撤回整批</NButton>
      </NSpace>
      <ul class="welcome-messages">
        <li v-for="item in selected.messages" :key="item.id">
          <span>{{ item.text }} <small>（{{ item.topic }}）</small></span>
          <NButton size="small" :disabled="busy" @click="run(() => toggle(item.id, !item.enabled))">{{ item.enabled ? '禁用' : '恢复' }}</NButton>
        </li>
      </ul>
      <details><summary>质量与运行审计</summary><pre>{{ JSON.stringify({ validation: selected.validation_report, run: selected.run }, null, 2) }}</pre></details>
    </NCard>
  </NSpace>
</template>

<style scoped>
.welcome-messages { padding-left: 20px; }
.welcome-messages li { padding: 8px 0; display: flex; gap: 12px; justify-content: space-between; align-items: center; }
p, pre { overflow-wrap: anywhere; white-space: pre-wrap; }
</style>
