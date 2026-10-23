<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton, NDatePicker, NEmpty, NInput, NSelect, NSpin, NTag,
} from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import { useScheduleStore } from '@/stores/schedule'

type TagType = 'default' | 'success' | 'info' | 'warning' | 'error'

const store = useScheduleStore()
const title = ref('')
const startAt = ref<number | null>(null)
const reminderMinutes = ref(0)
const creating = ref(false)
const error = ref('')
const selected = computed(() => store.selectedSchedule)

const reminderOptions = [
  { label: '准时提醒', value: 0 },
  { label: '提前 5 分钟', value: 5 },
  { label: '提前 15 分钟', value: 15 },
  { label: '提前 1 小时', value: 60 },
]

const scheduleStatusLabels: Record<string, string> = {
  active: '进行中',
  completed: '已完成',
  canceled: '已取消',
  cancelled: '已取消',
}

const deliveryStatusLabels: Record<string, string> = {
  pending: '待提醒',
  sent: '已发送',
  completed: '已完成',
  snoozed: '已推迟',
  failed: '发送失败',
}

function formatDateTime(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function scheduleTagType(status: string): TagType {
  if (status === 'active') return 'info'
  if (status === 'completed') return 'success'
  if (status === 'canceled' || status === 'cancelled') return 'default'
  return 'default'
}

function deliveryTagType(status: string): TagType {
  if (status === 'pending') return 'warning'
  if (status === 'sent') return 'info'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  return 'default'
}

function toErrorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback
}

async function create() {
  error.value = ''
  if (!title.value.trim() || startAt.value === null) {
    error.value = '请填写标题和开始时间'
    return
  }
  creating.value = true
  try {
    const schedule = await store.createSchedule({
      title: title.value.trim(),
      start_at: new Date(startAt.value).toISOString(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      reminder_offsets_minutes: [Number(reminderMinutes.value)],
    })
    title.value = ''
    startAt.value = null
    reminderMinutes.value = 0
    await store.fetchDeliveries(schedule.id)
  } catch (reason) {
    error.value = toErrorMessage(reason, '创建日程失败')
  } finally {
    creating.value = false
  }
}

async function selectSchedule(id: string) {
  error.value = ''
  try {
    await store.fetchDeliveries(id)
  } catch (reason) {
    error.value = toErrorMessage(reason, '加载提醒记录失败')
  }
}

async function cancel(id: string) {
  error.value = ''
  try {
    await store.cancelSchedule(id)
  } catch (reason) {
    error.value = toErrorMessage(reason, '取消日程失败')
  }
}

async function snooze(id: string) {
  error.value = ''
  try {
    await store.snoozeReminder(id, 10)
  } catch (reason) {
    error.value = toErrorMessage(reason, '推迟提醒失败')
  }
}

async function complete(id: string) {
  error.value = ''
  try {
    await store.completeReminder(id)
  } catch (reason) {
    error.value = toErrorMessage(reason, '完成提醒失败')
  }
}

onMounted(() => {
  void store.fetchSchedules()
})
</script>

<template>
  <div class="schedule-page">
    <PageHeader
      title="日程与提醒"
      subtitle="管理实验室会议、收样和分析节点提醒。"
    >
      <template #actions>
        <NButton secondary :loading="store.loading" @click="store.fetchSchedules">
          刷新
        </NButton>
      </template>
    </PageHeader>

    <section class="card editor-card">
      <h2>创建日程</h2>
      <div class="form-grid">
        <label>
          <span>标题</span>
          <NInput v-model:value="title" placeholder="例如：开组会" @keyup.enter="create" />
        </label>
        <label>
          <span>开始时间</span>
          <NDatePicker
            v-model:value="startAt"
            type="datetime"
            clearable
            placeholder="选择开始时间"
            class="form-control"
          />
        </label>
        <label>
          <span>提醒方式</span>
          <NSelect v-model:value="reminderMinutes" :options="reminderOptions" />
        </label>
        <NButton type="primary" :loading="creating" class="create-btn" @click="create">
          创建
        </NButton>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>

    <main class="content-grid">
      <section class="card">
        <h2>我的日程 <small v-if="store.loading">加载中…</small></h2>
        <NSpin :show="store.loading">
          <NEmpty v-if="!store.schedules.length" description="暂无日程" />
          <ul v-else class="schedule-list">
            <li
              v-for="item in store.schedules"
              :key="item.id"
              :class="{ active: selected?.id === item.id }"
              @click="selectSchedule(item.id)"
            >
              <div class="item-main">
                <strong>{{ item.title }}</strong>
                <span>{{ formatDateTime(item.start_at) }}</span>
              </div>
              <div class="item-actions">
                <NTag size="small" :type="scheduleTagType(item.status)">
                  {{ scheduleStatusLabels[item.status] ?? item.status }}
                </NTag>
                <NButton
                  v-if="item.status === 'active'"
                  size="tiny"
                  secondary
                  type="error"
                  @click.stop="cancel(item.id)"
                >
                  取消
                </NButton>
              </div>
            </li>
          </ul>
        </NSpin>
      </section>

      <section class="card">
        <h2>提醒记录</h2>
        <NEmpty v-if="!selected" description="选择左侧日程查看提醒记录" />
        <NEmpty v-else-if="!store.deliveries.length" description="该日程暂无提醒记录" />
        <ul v-else class="delivery-list">
          <li v-for="delivery in store.deliveries" :key="delivery.id">
            <div class="item-main">
              <strong>{{ formatDateTime(delivery.due_at) }}</strong>
              <span>{{ delivery.channel }} · 提前 {{ delivery.reminder_offset_minutes }} 分钟</span>
            </div>
            <div class="item-actions">
              <NTag size="small" :type="deliveryTagType(delivery.status)">
                {{ deliveryStatusLabels[delivery.status] ?? delivery.status }}
              </NTag>
              <NButton
                v-if="delivery.status === 'pending'"
                size="tiny"
                secondary
                @click="snooze(delivery.id)"
              >
                推迟 10 分钟
              </NButton>
              <NButton
                v-if="delivery.status !== 'completed'"
                size="tiny"
                type="primary"
                secondary
                @click="complete(delivery.id)"
              >
                完成
              </NButton>
            </div>
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>

<style scoped>
.schedule-page {
  min-height: 100%;
  background: var(--neutral-bg);
}

.card {
  padding: var(--card-padding);
  border: 1px solid var(--neutral-border);
  border-radius: var(--radius-card);
  background: var(--neutral-card);
  box-shadow: var(--shadow-card);
}

h2 {
  margin: 0 0 var(--space-lg);
  color: var(--text-primary);
  font-size: var(--font-card-title-size);
  font-weight: var(--font-card-title-weight);
  line-height: var(--font-card-title-height);
}

h2 small {
  color: var(--text-tertiary);
  font-size: var(--font-caption-size);
  font-weight: 400;
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 2fr) minmax(0, 1fr) auto;
  gap: var(--space-md);
  align-items: end;
}

.form-grid label {
  display: grid;
  gap: var(--space-xs);
  color: var(--text-secondary);
  font-size: var(--font-body-size);
}

.form-control {
  width: 100%;
}

.create-btn {
  min-width: 88px;
}

.error {
  margin: var(--space-md) 0 0;
  color: var(--arco-danger);
  font-size: var(--font-body-size);
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--card-gap);
  margin-top: var(--card-gap);
}

ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-md) 0;
  border-bottom: 1px solid var(--neutral-border);
  cursor: pointer;
}

li:last-child {
  border-bottom: none;
}

li.active .item-main strong {
  color: var(--brand-primary);
}

.item-main {
  display: grid;
  min-width: 0;
  gap: var(--space-xs);
}

.item-main strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-body-size);
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-main span {
  color: var(--text-tertiary);
  font-size: var(--font-caption-size);
}

.item-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--space-sm);
}

@media (max-width: 900px) {
  .form-grid,
  .content-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
