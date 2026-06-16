<template>
  <div class="state-shell" :style="shellStyle">
    <div v-if="loading" class="state-note loading">
      <span class="dot" aria-hidden="true"></span>
      <span>{{ loadingText }}</span>
    </div>
    <div v-else-if="error" class="state-note error">
      <span class="dot" aria-hidden="true"></span>
      <span class="message">{{ error }}</span>
      <button type="button" @click="$emit('retry')">重试</button>
    </div>
    <div v-else-if="empty" class="state-note empty">
      <span class="dot" aria-hidden="true"></span>
      <span>{{ emptyText }}</span>
    </div>
    <slot v-else />
  </div>
</template>

<script setup>
import { computed } from 'vue';

defineEmits(['retry']);

const props = defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  empty: { type: Boolean, default: false },
  loadingText: { type: String, default: '加载中...' },
  emptyText: { type: String, default: '暂无数据' },
  minHeight: { type: Number, default: 132 }
});

const shellStyle = computed(() => ({ minHeight: `${Math.max(96, Number(props.minHeight) || 132)}px` }));
</script>

<style scoped>
.state-note {
  margin-top: 12px;
  border: 1px dashed color-mix(in oklch, var(--line-soft) 85%, white);
  padding: 14px 16px;
  color: var(--ink-body);
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  border-radius: 12px;
  background: color-mix(in oklch, var(--bg-field) 92%, white);
  line-height: 1.5;
}

.state-note .dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 999px;
  background: color-mix(in oklch, var(--line-strong) 75%, white);
}

.state-note.loading .dot {
  background: var(--accent);
  box-shadow: 0 0 0 0 color-mix(in oklch, var(--accent) 45%, transparent);
  animation: pulse 1.2s ease infinite;
}

.state-note.empty .dot {
  background: color-mix(in oklch, var(--ink-muted) 66%, white);
}

.state-note.error {
  border-color: var(--danger);
  color: var(--danger);
  background: color-mix(in oklch, var(--danger) 7%, white);
}

.state-note.error .dot {
  background: var(--danger);
}

.state-note.error .message {
  flex: 1;
}

button {
  min-height: 34px;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0 12px;
  border-radius: 999px;
}

button:hover {
  background: color-mix(in oklch, currentColor 8%, white);
}

button:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 color-mix(in oklch, var(--accent) 45%, transparent);
  }
  100% {
    box-shadow: 0 0 0 8px transparent;
  }
}
</style>

