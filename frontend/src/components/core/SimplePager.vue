<template>
  <div v-if="total > pageSize" class="pager">
    <button type="button" :disabled="currentPage <= 1" @click="update(currentPage - 1)">上一页</button>
    <span class="pager-text">第 {{ currentPage }} / {{ pageCount }} 页</span>
    <button type="button" :disabled="currentPage >= pageCount" @click="update(currentPage + 1)">下一页</button>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  total: {
    type: Number,
    default: 0
  },
  pageSize: {
    type: Number,
    default: 8
  },
  currentPage: {
    type: Number,
    default: 1
  }
});

const emit = defineEmits(['update:currentPage']);

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));

const update = (page) => {
  emit('update:currentPage', page);
};
</script>

<style scoped>
.pager {
  margin-top: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: 1px dashed color-mix(in oklch, var(--line-soft) 86%, white);
  border-radius: 12px;
  background: color-mix(in oklch, var(--bg-panel) 90%, white);
}

button {
  min-height: 32px;
  border: 1px solid color-mix(in oklch, var(--line-strong) 80%, white);
  background: color-mix(in oklch, var(--bg-field) 84%, white);
  color: var(--ink-body);
  padding: 0 12px;
  cursor: pointer;
  border-radius: 999px;
}

button:hover:not(:disabled) {
  border-color: color-mix(in oklch, var(--accent) 54%, var(--line-strong));
  color: var(--ink-title);
}

.pager-text {
  color: var(--ink-muted);
  font-size: 13px;
  min-width: 96px;
  text-align: center;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>

