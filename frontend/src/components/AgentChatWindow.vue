<template>
  <el-card class="agent-chat-card">
    <template #header>
      <div class="card-header">
        <span>{{ title }}</span>
        <slot name="header-actions" />
      </div>
    </template>

    <div class="agent-chat-layout">
      <aside class="session-panel">
        <button type="button" class="chat-btn primary new-chat-btn" @click="$emit('new-chat')">
          {{ newChatLabel }}
        </button>
        <el-scrollbar max-height="460px" class="history-scroll">
          <el-empty v-if="!sessions.length" :description="emptySessionText" />
          <template v-else>
            <div
              v-for="(session, idx) in sessions"
              :key="session.id || idx"
              class="session-item"
              :class="{ active: idx === activeSessionIndex }"
              @click="$emit('select-session', idx)"
            >
              <div class="session-line">
                <div class="session-title">{{ session.title || `对话 ${idx + 1}` }}</div>
                <button type="button" class="chat-btn text danger" @click.stop="$emit('delete-session', idx)">删除</button>
              </div>
              <div class="session-date">{{ formatSessionDate(session.date) }}</div>
            </div>
          </template>
        </el-scrollbar>
      </aside>

      <section class="dialog-panel">
        <div ref="dialogWindowRef" class="dialog-window">
          <div
            v-for="(item, idx) in messages"
            :key="idx"
            class="chat-row"
            :class="[roleClass(item.role), { 'chat-hit': focusedMessageIndex === idx }]"
            :data-chat-idx="idx"
          >
            <span class="role-icon">{{ item.role === 'ai' ? 'AI' : '我' }}</span>
            <MarkdownBlock
              v-if="item.role === 'ai'"
              class="bubble markdown-body"
              :content="item.content || item.text"
            />
            <div v-else class="bubble">{{ item.content || item.text }}</div>
          </div>
        </div>

        <div class="composer">
          <slot name="composer-extra" />
          <div v-if="taskStatus" class="task-status-row">
            <el-tag size="small" :type="taskStatusTag">{{ taskStatusLabel }}</el-tag>
            <span class="task-status-text">{{ taskStatusHint }}</span>
          </div>
          <textarea
            v-model="inputProxy"
            class="composer-input"
            :rows="inputRows"
            :placeholder="placeholder"
            @keydown="onKeydown"
          />
          <div class="composer-actions">
            <slot name="composer-actions">
              <button type="button" class="chat-btn primary" :disabled="loading" @click="$emit('send')">
                {{ loading ? '发送中...' : '发送消息' }}
              </button>
            </slot>
          </div>
        </div>
      </section>
    </div>
  </el-card>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { formatDateTime } from '../utils/datetime';
import MarkdownBlock from './MarkdownBlock.vue';

const props = defineProps({
  title: { type: String, default: '智能体对话' },
  messages: { type: Array, default: () => [] },
  sessions: { type: Array, default: () => [] },
  modelValue: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  placeholder: { type: String, default: '输入问题，按 Enter 发送，Shift+Enter 换行' },
  newChatLabel: { type: String, default: '开启新对话' },
  emptySessionText: { type: String, default: '暂无历史对话' },
  inputRows: { type: Number, default: 3 },
  activeSessionIndex: { type: Number, default: -1 },
  taskStatus: { type: String, default: '' },
  taskStatusText: { type: String, default: '' },
  taskError: { type: String, default: '' },
  focusKeyword: { type: String, default: '' }
});

const emit = defineEmits(['update:modelValue', 'update:model-value', 'send', 'new-chat', 'select-session', 'delete-session']);
const dialogWindowRef = ref(null);
const focusedMessageIndex = ref(-1);
const activeFocusKeyword = ref('');

const emitModelUpdate = (value) => {
  emit('update:modelValue', value);
  emit('update:model-value', value);
};

const inputProxy = computed({
  get: () => props.modelValue,
  set: (value) => emitModelUpdate(value)
});

const formatSessionDate = (value) => formatDateTime(value);
const roleClass = (role) => (role === 'ai' ? 'ai' : 'student');

const textHit = (a, b) => {
  const left = String(a || '').trim().toLowerCase();
  const right = String(b || '').trim().toLowerCase();
  if (!left || !right || right.length < 2) return false;
  return left.includes(right) || right.includes(left);
};

const focusByText = async (keyword) => {
  const key = String(keyword || '').trim();
  if (!key) {
    focusedMessageIndex.value = -1;
    activeFocusKeyword.value = '';
    return false;
  }

  const idx = (props.messages || []).findIndex((item) => {
    const content = item?.content || item?.text;
    return item?.role === 'ai' && textHit(content, key);
  });
  if (idx < 0) return false;

  activeFocusKeyword.value = key;
  focusedMessageIndex.value = idx;
  await nextTick();
  const wrap = dialogWindowRef.value;
  const target = wrap?.querySelector(`[data-chat-idx="${idx}"]`);
  target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  return true;
};

defineExpose({ focusByText });

const onKeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    event.stopPropagation();
    if (!props.loading) emit('send');
  }
};

watch(
  () => props.messages.length,
  async () => {
    await nextTick();
    const wrap = dialogWindowRef.value;
    if (wrap) wrap.scrollTop = wrap.scrollHeight;
    if (activeFocusKeyword.value) {
      await focusByText(activeFocusKeyword.value);
    }
  },
  { immediate: true }
);

watch(
  () => props.focusKeyword,
  async (val) => {
    if (!val) {
      activeFocusKeyword.value = '';
      focusedMessageIndex.value = -1;
      return;
    }
    await focusByText(val);
  }
);

const statusTextMap = {
  queued: '排队中',
  running: '运行中',
  done: '已完成',
  error: '失败'
};

const taskStatusLabel = computed(() => statusTextMap[props.taskStatus] || props.taskStatus || '处理中');
const taskStatusTag = computed(() => {
  if (props.taskStatus === 'done') return 'success';
  if (props.taskStatus === 'error') return 'danger';
  if (props.taskStatus === 'running') return 'warning';
  return 'info';
});

const taskStatusHint = computed(() => {
  if (props.taskStatusText) return props.taskStatusText;
  if (props.taskStatus === 'error') return props.taskError || '任务执行失败，请稍后重试';
  if (props.taskStatus === 'done') return '任务已完成';
  if (props.taskStatus === 'running') return '智能体正在生成结果';
  if (props.taskStatus === 'queued') return '任务已提交，等待执行';
  return '';
});
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-family: var(--font-display);
  font-size: 19px;
  letter-spacing: 0.018em;
  font-weight: 760;
  color: var(--ink-title);
}

.agent-chat-layout {
  display: grid;
  grid-template-columns: minmax(236px, 292px) minmax(0, 1fr);
  gap: 16px;
  min-height: clamp(540px, 70vh, 740px);
}

.session-panel {
  border: 1px solid color-mix(in oklch, var(--line-soft) 80%, white);
  border-radius: var(--radius-md);
  padding: 16px;
  background:
    linear-gradient(172deg, color-mix(in oklch, var(--accent) 18%, white), color-mix(in oklch, var(--bg-panel) 97%, white));
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-shadow: 0 14px 28px color-mix(in oklch, var(--accent) 16%, transparent);
}

.new-chat-btn {
  width: 100%;
  margin-bottom: 12px;
}

.history-scroll {
  flex: 1;
  min-height: 280px;
  max-height: none;
}

.session-item {
  border: 1px solid color-mix(in oklch, var(--line-soft) 82%, white);
  border-radius: var(--radius-sm);
  padding: 11px 12px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: border-color 0.18s ease, transform 0.18s ease, background 0.18s ease, box-shadow 0.22s ease;
  background: color-mix(in oklch, var(--bg-panel) 88%, white);
}

.session-item:hover {
  transform: translateY(-2px);
  border-color: color-mix(in oklch, var(--accent) 42%, var(--line-strong));
  box-shadow: 0 10px 18px color-mix(in oklch, var(--accent) 14%, transparent);
}

.session-item.active {
  border-color: color-mix(in oklch, var(--accent) 78%, var(--line-strong));
  background: color-mix(in oklch, var(--accent) 20%, white);
  box-shadow: 0 12px 22px color-mix(in oklch, var(--accent) 24%, transparent);
}

.session-title {
  font-size: 14px;
  font-weight: 680;
  letter-spacing: 0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink-title);
}

.session-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.session-date {
  color: var(--ink-muted);
  font-size: 11px;
  letter-spacing: 0.02em;
  margin-top: 5px;
}

.dialog-panel {
  border: 1px solid color-mix(in oklch, var(--line-soft) 82%, white);
  border-radius: var(--radius-md);
  background: color-mix(in oklch, var(--bg-panel) 96%, white);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-mid);
}

.dialog-window {
  flex: 1;
  min-height: clamp(340px, 45vh, 540px);
  max-height: clamp(420px, 56vh, 660px);
  overflow-y: auto;
  padding: 16px 15px;
  background:
    linear-gradient(180deg, color-mix(in oklch, var(--bg-field) 82%, white), color-mix(in oklch, var(--bg-field) 94%, white));
}

.chat-row {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-bottom: 11px;
}

.chat-row.student {
  justify-content: flex-end;
}

.chat-row.student .role-icon {
  order: 2;
}

.chat-row.student .bubble {
  order: 1;
  background: color-mix(in oklch, var(--accent-2) 14%, white);
  white-space: pre-wrap;
}

.chat-row.ai .bubble {
  background:
    linear-gradient(158deg, color-mix(in oklch, var(--accent) 24%, white), color-mix(in oklch, var(--accent-3) 18%, white));
}

.chat-row.chat-hit .bubble {
  box-shadow: 0 0 0 2px color-mix(in oklch, var(--accent) 36%, white);
}

.role-icon {
  margin-top: 2px;
  display: inline-flex;
  min-width: 28px;
  min-height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid color-mix(in oklch, var(--line-soft) 84%, white);
  color: color-mix(in oklch, var(--ink-muted) 90%, var(--ink-body));
  font-size: 12px;
  font-weight: 650;
  background: color-mix(in oklch, var(--bg-panel) 92%, white);
}

.bubble {
  max-width: 85%;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  display: block;
  line-height: 1.66;
  font-size: 15px;
  text-align: left;
  white-space: normal;
  border: 1px solid color-mix(in oklch, var(--line-soft) 72%, white);
  box-shadow: 0 8px 14px color-mix(in oklch, var(--accent) 8%, transparent);
}

.chat-btn {
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: var(--bg-panel);
  color: var(--ink-title);
  font-size: 13px;
  font-weight: 620;
  cursor: pointer;
}

.chat-btn.primary {
  border-color: var(--accent);
  background: linear-gradient(145deg, color-mix(in oklch, var(--accent) 86%, white), var(--accent));
  color: #fff;
}

.chat-btn.primary:hover:not(:disabled) {
  box-shadow: 0 10px 18px color-mix(in oklch, var(--accent) 28%, transparent);
}

.chat-btn.text {
  min-height: 28px;
  padding: 0 8px;
  border-color: transparent;
  background: transparent;
  color: var(--ink-muted);
}

.chat-btn.danger {
  color: var(--danger);
}

.markdown-body :deep(p) {
  margin: 0 0 6px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.2em 0 0;
  padding-left: 18px;
}

.composer {
  border-top: 1px solid color-mix(in oklch, var(--line-soft) 82%, white);
  padding: 16px;
  background: color-mix(in oklch, var(--bg-panel) 95%, white);
}

.composer-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.composer-input {
  width: 100%;
  min-height: 104px;
  border: 1px solid var(--line-strong);
  border-radius: var(--control-radius);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 10px 12px;
  resize: vertical;
  line-height: 1.64;
  font-size: 14px;
}

.composer-input:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

.task-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.task-status-text {
  font-size: 13px;
  color: var(--ink-muted);
}

@media (max-width: 960px) {
  .agent-chat-layout {
    grid-template-columns: 1fr;
    min-height: unset;
  }

  .session-panel {
    padding: 14px;
  }

  .new-chat-btn {
    min-height: var(--touch-target);
  }

  .history-scroll {
    min-height: 220px;
  }

  .session-item {
    padding: 12px;
  }

  .chat-btn {
    min-height: var(--touch-target);
  }

  .bubble {
    max-width: 92%;
    font-size: 14px;
  }

  .composer {
    padding: 12px;
  }

  .composer-actions {
    justify-content: stretch;
  }

  .composer-actions > * {
    flex: 1 1 100%;
  }

  .dialog-window {
    min-height: clamp(300px, 44vh, 460px);
    max-height: clamp(360px, 52vh, 520px);
  }
}

@media (max-width: 640px) {
  .card-header {
    font-size: 17px;
    gap: 8px;
  }

  .session-panel {
    padding: 10px;
  }

  .dialog-window {
    padding: 12px 10px;
  }

  .chat-row {
    gap: 7px;
    margin-bottom: 10px;
  }

  .role-icon {
    min-width: 26px;
    min-height: 26px;
    font-size: 11px;
  }

  .bubble {
    border-radius: 12px;
    padding: 10px 11px;
  }
}
</style>
