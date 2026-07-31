<script setup lang="ts">
import { AlertTriangle } from '@lucide/vue'

defineProps<{
  open: boolean
  title: string
  message: string
  busy?: boolean
}>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="confirm-layer" @mousedown.self="emit('cancel')">
      <section class="confirm-dialog" role="alertdialog" aria-modal="true" :aria-label="title">
        <div class="confirm-icon"><AlertTriangle :size="22" /></div>
        <h3>{{ title }}</h3>
        <p>{{ message }}</p>
        <div class="confirm-actions">
          <button class="cancel" :disabled="busy" @click="emit('cancel')">取消</button>
          <button class="danger" :disabled="busy" @click="emit('confirm')">
            {{ busy ? '正在处理…' : '确认删除' }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
