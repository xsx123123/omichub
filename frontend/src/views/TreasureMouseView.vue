<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TreasureResearchWorkbench from './TreasureResearchWorkbench.vue'

const route = useRoute()
const router = useRouter()
const entry = route.query.start === 'new' || route.query.start === 'plan' ? route.query.start : undefined
onMounted(() => {
  if (!entry) return
  // Consume the launch intent without adding a history entry or replaying it on refresh.
  const { start: _start, ...query } = route.query
  void router.replace({ path: route.path, query, hash: route.hash })
})
</script>

<template>
  <TreasureResearchWorkbench :entry="entry" />
</template>
