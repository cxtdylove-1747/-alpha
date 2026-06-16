<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Smart Guide</p>
      <h2>智能引导与学习辅导一体化</h2>
      <p>同一个智能体同时支持项目引导、知识讲解与案例练习。</p>
      <div class="chips">
        <span>项目 {{ planTotal }}</span>
        <span>消息 {{ messageTotal }}</span>
        <span>历史 {{ historyTotal }}</span>
      </div>
    </section>

    <section class="panel guide-panel">
      <div class="toolbar">
        <select v-model="guideMode">
          <option value="guide">项目引导模式</option>
          <option value="teach">学习讲解模式</option>
        </select>
        <button type="button" class="ghost" :disabled="asking" @click="loadLearningTopics">刷新学习主题</button>
      </div>

      <div class="topics" v-if="guideMode === 'teach' && quickTopics.length">
        <button v-for="item in quickTopics" :key="item" type="button" class="ghost" @click="selectTopic(item)">
          {{ item }}
        </button>
      </div>

      <AgentChatWindow
        title="智能引导"
        :messages="chatRecords"
        :sessions="historySessions"
        :active-session-index="activeSessionIndex"
        :model-value="answer"
        :loading="asking"
        :task-status="guideTaskStatus"
        :task-error="guideTaskError"
        placeholder="输入你的问题或当前困难"
        @update:model-value="answer = $event"
        @send="ask"
        @new-chat="startNewChat"
        @select-session="loadGuideHistory"
        @delete-session="deleteSession"
      >
        <template #composer-actions>
          <button type="button" class="primary" :disabled="asking" @click="ask">发送</button>
          <button type="button" class="ghost" :disabled="validating" @click="validate">逻辑校验</button>
        </template>
      </AgentChatWindow>

      <div v-if="issues.length" class="issues">
        <strong>逻辑校验待思考点</strong>
        <ul>
          <li v-for="(item, idx) in issues" :key="`issue-${idx}`">{{ item.question || item.description }}</li>
        </ul>
      </div>
    </section>

    <section class="panel">
      <h3>最近项目</h3>
      <div class="toolbar">
        <input v-model.trim="planKeyword" type="text" placeholder="按项目名称筛选" @input="onPlanFilterChange">
      </div>
      <AsyncState :loading="planLoading" :error="planError" :empty="!displayPlans.length" empty-text="暂无项目" @retry="loadPlans">
        <ul>
          <li v-for="item in displayPlans" :key="item.id || item.name">{{ item.name || item.title || '未命名项目' }}</li>
        </ul>
        <SimplePager :current-page="planPage" :total="planDisplayTotal" :page-size="pageSize" @update:currentPage="onPlanPageChange" />
      </AsyncState>
    </section>

    <section class="panel">
      <h3>最近消息</h3>
      <div class="toolbar">
        <input v-model.trim="messageKeyword" type="text" placeholder="按消息关键词筛选" @input="onMessageFilterChange">
      </div>
      <AsyncState :loading="messageLoading" :error="messageError" :empty="!displayMessages.length" empty-text="暂无消息" @retry="loadMessages">
        <ul>
          <li v-for="item in displayMessages" :key="item.id || item.title">{{ item.title || item.content || '系统通知' }}</li>
        </ul>
        <SimplePager :current-page="messagePage" :total="messageDisplayTotal" :page-size="pageSize" @update:currentPage="onMessagePageChange" />
      </AsyncState>
    </section>

    <section class="panel">
      <h3>最近行为</h3>
      <div class="toolbar">
        <input v-model.trim="historyKeyword" type="text" placeholder="按行为关键词筛选" @input="onHistoryFilterChange">
      </div>
      <AsyncState :loading="historyLoading" :error="historyError" :empty="!displayHistory.length" empty-text="暂无行为记录" @retry="loadHistory">
        <ul>
          <li v-for="item in displayHistory" :key="item.id || item.created_at">{{ item.action || item.title || '操作记录' }}</li>
        </ul>
        <SimplePager :current-page="historyPage" :total="historyDisplayTotal" :page-size="pageSize" @update:currentPage="onHistoryPageChange" />
      </AsyncState>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import AsyncState from '../../../components/core/AsyncState.vue';
import SimplePager from '../../../components/core/SimplePager.vue';
import { compactQuery, normalizePagedResult } from '../../../composables/list';
import AgentChatWindow from '../../../components/AgentChatWindow.vue';
import {
  createAgentTaskApi,
  historyApi,
  listMessagesApi,
  listPlansApi,
  validateLogicApi,
  waitAgentTaskApi
} from '../../../api/student';

const plans = ref([]);
const messages = ref([]);
const history = ref([]);
const planLoading = ref(false);
const messageLoading = ref(false);
const historyLoading = ref(false);
const planError = ref('');
const messageError = ref('');
const historyError = ref('');
const planKeyword = ref('');
const messageKeyword = ref('');
const historyKeyword = ref('');
const planPage = ref(1);
const messagePage = ref(1);
const historyPage = ref(1);
const pageSize = 6;
const planServerTotal = ref(0);
const messageServerTotal = ref(0);
const historyServerTotal = ref(0);
const displayPlans = computed(() => plans.value);
const displayMessages = computed(() => messages.value);
const displayHistory = computed(() => history.value);
const planDisplayTotal = computed(() => planServerTotal.value);
const messageDisplayTotal = computed(() => messageServerTotal.value);
const historyDisplayTotal = computed(() => historyServerTotal.value);
const planTotal = computed(() => planServerTotal.value);
const messageTotal = computed(() => messageServerTotal.value);
const historyTotal = computed(() => historyServerTotal.value);

const guideMode = ref('guide');
const issues = ref([]);
const asking = ref(false);
const validating = ref(false);
const quickTopics = ref([]);
const guideTaskStatus = ref('');
const guideTaskError = ref('');

const GUIDE_HISTORY_KEY = 'studentGuideChatHistory';
const TEACH_HISTORY_KEY = 'studentTeachChatHistory';
const GUIDE_PENDING_KEY = 'guidePendingTask';
const TEACH_PENDING_KEY = 'guideTeachPendingTask';

const nowText = () => new Date().toLocaleString();

const buildTeachOpeningMessage = (
  topics = quickTopics.value,
  message = '已切换到学习讲解模式。告诉我你想学的知识点，或直接点击下方主题。'
) => {
  const rows = Array.isArray(topics) ? topics.filter(Boolean) : [];
  if (!rows.length) {
    return message;
  }
  return `${message}\n\n${rows.map((item, idx) => `${idx + 1}. ${item}`).join('\n')}`;
};

const defaultChatRecords = (mode, options = {}) => {
  if (mode === 'teach') {
    return [{
      role: 'ai',
      content: buildTeachOpeningMessage(options.topics || quickTopics.value, options.message)
    }];
  }
  return [{
    role: 'ai',
    content: '你好，我会陪你完成项目推进，也可以随时切换到知识讲解模式。你最想先解决什么？'
  }];
};

const modeStore = ref({
  guide: {
    stage: 'idea',
    draft: '',
    sessions: [],
    activeSessionId: Date.now(),
    chatRecords: defaultChatRecords('guide')
  },
  teach: {
    stage: 'idea',
    draft: '',
    sessions: [],
    activeSessionId: Date.now() + 1,
    chatRecords: defaultChatRecords('teach')
  }
});

const currentModeKey = (mode = guideMode.value) => (mode === 'teach' ? 'teach' : 'guide');
const currentState = (mode = guideMode.value) => modeStore.value[currentModeKey(mode)];
const historyStorageKey = (mode = guideMode.value) => (currentModeKey(mode) === 'teach' ? TEACH_HISTORY_KEY : GUIDE_HISTORY_KEY);
const pendingStorageKey = (mode = guideMode.value) => (currentModeKey(mode) === 'teach' ? TEACH_PENDING_KEY : GUIDE_PENDING_KEY);

const answer = computed({
  get: () => currentState().draft || '',
  set: (value) => {
    currentState().draft = String(value ?? '');
  }
});

const chatRecords = computed(() => currentState().chatRecords || []);
const historySessions = computed(() => currentState().sessions || []);
const activeSessionIndex = computed(() => {
  const state = currentState();
  return (state.sessions || []).findIndex((item) => item.id === state.activeSessionId);
});
const stage = computed({
  get: () => currentState('guide').stage || 'idea',
  set: (value) => {
    currentState('guide').stage = String(value || 'idea');
  }
});

const parseStoredSessions = (...keys) => {
  for (const key of keys) {
    if (!key) continue;
    try {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed;
      }
    } catch (_) {
      // ignore broken local cache
    }
  }
  return [];
};

const restoreActiveSession = (mode) => {
  const state = currentState(mode);
  const firstSession = (state.sessions || [])[0];
  if (!firstSession) {
    state.chatRecords = defaultChatRecords(mode);
    if (mode === 'guide') {
      state.stage = 'idea';
    }
    return;
  }
  state.activeSessionId = firstSession.id;
  state.chatRecords = [...(firstSession.messages || defaultChatRecords(mode))];
  if (mode === 'guide') {
    state.stage = firstSession.stage || state.stage || 'idea';
  }
};

const buildSessionPreview = (records) => {
  const list = Array.isArray(records) ? records : [];
  const last = [...list].reverse().find((item) => String(item?.content || item?.text || '').trim());
  return String(last?.content || last?.text || '').trim().slice(0, 48);
};

const ensureModeInitialized = (mode = guideMode.value) => {
  const state = currentState(mode);
  if (!state.activeSessionId) {
    state.activeSessionId = Date.now();
  }
  if (!Array.isArray(state.chatRecords) || !state.chatRecords.length) {
    state.chatRecords = defaultChatRecords(mode);
  }
  if (!Array.isArray(state.sessions)) {
    state.sessions = [];
  }
};

const persistHistory = (mode = guideMode.value) => {
  const state = currentState(mode);
  localStorage.setItem(historyStorageKey(mode), JSON.stringify((state.sessions || []).slice(0, 20)));
};

const upsertSessionSnapshot = (mode, sessionId, records, options = {}) => {
  const state = currentState(mode);
  const nextMessages = [...(records || [])];
  let session = (state.sessions || []).find((item) => item.id === sessionId);
  if (!session) {
    session = {
      id: sessionId,
      date: nowText(),
      title: currentModeKey(mode) === 'teach' ? '学习辅导会话' : '项目引导会话',
      preview: '',
      messages: nextMessages,
      stage: options.stage || 'idea'
    };
    state.sessions.unshift(session);
  }
  session.messages = nextMessages;
  session.date = nowText();
  session.preview = buildSessionPreview(nextMessages);
  if (options.title) {
    session.title = String(options.title).slice(0, 16) || session.title;
  }
  if (currentModeKey(mode) === 'guide') {
    session.stage = options.stage || session.stage || 'idea';
  }
  persistHistory(mode);
};

const resolveSessionMessages = (mode, sessionId) => {
  const state = currentState(mode);
  if (state.activeSessionId === sessionId) {
    return [...(state.chatRecords || [])];
  }
  const session = (state.sessions || []).find((item) => item.id === sessionId);
  return [...(session?.messages || defaultChatRecords(mode))];
};

const saveCurrentSession = (title = '', mode = guideMode.value) => {
  ensureModeInitialized(mode);
  const state = currentState(mode);
  upsertSessionSnapshot(mode, state.activeSessionId, state.chatRecords, {
    title,
    stage: currentModeKey(mode) === 'guide' ? state.stage : undefined
  });
};

const deleteSession = (index) => {
  const mode = currentModeKey();
  const state = currentState(mode);
  const removed = state.sessions.splice(index, 1)[0];
  if (removed?.id === state.activeSessionId) {
    const next = state.sessions[0];
    if (next) {
      state.activeSessionId = next.id;
      state.chatRecords = [...(next.messages || defaultChatRecords(mode))];
      if (mode === 'guide') {
        state.stage = next.stage || 'idea';
      }
    } else {
      state.activeSessionId = Date.now();
      state.chatRecords = defaultChatRecords(mode);
      if (mode === 'guide') {
        state.stage = 'idea';
      }
    }
  }
  persistHistory(mode);
};

const startNewChat = () => {
  const mode = currentModeKey();
  saveCurrentSession('', mode);
  const state = currentState(mode);
  state.activeSessionId = Date.now();
  state.chatRecords = defaultChatRecords(mode);
  state.draft = '';
  if (mode === 'guide') {
    state.stage = 'idea';
  }
};

const loadGuideHistory = (index) => {
  const mode = currentModeKey();
  const state = currentState(mode);
  const session = state.sessions[index];
  if (!session) return;
  saveCurrentSession('', mode);
  state.activeSessionId = session.id;
  state.chatRecords = [...(session.messages || defaultChatRecords(mode))];
  state.draft = '';
  if (mode === 'guide') {
    state.stage = session.stage || 'idea';
  }
};

const onGuideTaskStatusChange = ({ status, error }) => {
  guideTaskStatus.value = status || '';
  guideTaskError.value = error || '';
};

const settleGuideTaskStatus = () => {
  if (guideTaskStatus.value !== 'done') return;
  setTimeout(() => {
    if (guideTaskStatus.value === 'done') {
      guideTaskStatus.value = '';
    }
  }, 1200);
};

const loadLearningTopics = async () => {
  try {
    const task = await createAgentTaskApi({
      agent: 'guide',
      payload: { mode: 'opening' }
    });
    const res = await waitAgentTaskApi(task.task_id, { onStatusChange: onGuideTaskStatusChange });
    quickTopics.value = res?.topics || [];

    const teachState = currentState('teach');
    const hasTeachInput = (teachState.chatRecords || []).some((item) => item.role === 'student');
    if (!hasTeachInput && !(teachState.sessions || []).length) {
      teachState.chatRecords = defaultChatRecords('teach', {
        topics: res?.topics || [],
        message: res?.message || '已切换到学习讲解模式。告诉我你想学的知识点，或直接点击下方主题。'
      });
    }
  } catch (_) {
    quickTopics.value = [];
  } finally {
    settleGuideTaskStatus();
  }
};

const selectTopic = async (topic) => {
  answer.value = topic;
  await ask();
};

const appendTeachResult = (res, mode = 'teach', sessionId = currentState(mode).activeSessionId) => {
  if (!res?.message) {
    throw new Error('结果为空');
  }
  const nextMessages = [...resolveSessionMessages(mode, sessionId), { role: 'ai', content: res.message }];
  upsertSessionSnapshot(mode, sessionId, nextMessages, { title: '学习辅导' });
  const state = currentState(mode);
  if (state.activeSessionId === sessionId) {
    state.chatRecords = nextMessages;
  }
};

const appendGuideResult = (res, mode = 'guide', sessionId = currentState(mode).activeSessionId) => {
  if (!res?.next?.teacher_reply) {
    throw new Error('结果为空');
  }
  const nextStage = res.next.stage || 'idea';
  const caseLine = res.next.case_pattern?.industry
    ? `案例范式：${res.next.case_pattern.industry} | ${res.next.case_pattern.innovation || ''}`
    : '';
  const nextMessages = [
    ...resolveSessionMessages(mode, sessionId),
    {
      role: 'ai',
      content: [res.next.teacher_reply, res.next.knowledge, caseLine].filter(Boolean).join('\n')
    }
  ];
  upsertSessionSnapshot(mode, sessionId, nextMessages, {
    title: res.next.chat_title || '项目引导',
    stage: nextStage
  });
  const state = currentState(mode);
  if (state.activeSessionId === sessionId) {
    state.chatRecords = nextMessages;
    state.stage = nextStage;
  }
};

const ask = async () => {
  const mode = currentModeKey();
  const state = currentState(mode);
  const question = String(answer.value || '').trim();
  if (!question) return;

  asking.value = true;
  guideTaskError.value = '';
  ensureModeInitialized(mode);
  const sessionId = state.activeSessionId;

  try {
    state.chatRecords = [...state.chatRecords, { role: 'student', content: question }];
    state.draft = '';
    upsertSessionSnapshot(mode, sessionId, state.chatRecords, {
      title: mode === 'teach' ? '学习辅导' : '项目引导',
      stage: mode === 'guide' ? state.stage : undefined
    });

    if (mode === 'teach') {
      const task = await createAgentTaskApi({
        agent: 'guide',
        payload: { mode: 'teach', message: question, history: state.chatRecords.slice(-10) }
      });
      localStorage.setItem(pendingStorageKey(mode), JSON.stringify({ taskId: task.task_id, mode, sessionId }));
      const res = await waitAgentTaskApi(task.task_id, { onStatusChange: onGuideTaskStatusChange });
      localStorage.removeItem(pendingStorageKey(mode));
      appendTeachResult(res, mode, sessionId);
      return;
    }

    const task = await createAgentTaskApi({
      agent: 'guide',
      payload: { stage: state.stage, answer: question, session_id: sessionId }
    });
    localStorage.setItem(pendingStorageKey(mode), JSON.stringify({ taskId: task.task_id, mode, sessionId }));
    const res = await waitAgentTaskApi(task.task_id, { onStatusChange: onGuideTaskStatusChange });
    localStorage.removeItem(pendingStorageKey(mode));
    appendGuideResult(res, mode, sessionId);
  } catch (e) {
    localStorage.removeItem(pendingStorageKey(mode));
    guideTaskError.value = e?.message || '出了些小问题';
  } finally {
    asking.value = false;
    settleGuideTaskStatus();
  }
};

const validate = async () => {
  validating.value = true;
  try {
    const payload = answer.value.trim() || chatRecords.value.map((item) => item.content).join('\n');
    const res = await validateLogicApi({ text: payload });
    issues.value = res.issues || [];
  } finally {
    validating.value = false;
  }
};

const resumePendingTaskForMode = async (mode) => {
  const key = pendingStorageKey(mode);
  const raw = localStorage.getItem(key);
  if (!raw) return;

  try {
    const pending = JSON.parse(raw);
    if (!pending?.taskId) {
      localStorage.removeItem(key);
      return;
    }

    const resolvedMode = currentModeKey(pending.mode || mode);
    const sessionId = Number(pending.sessionId || currentState(resolvedMode).activeSessionId || Date.now());
    const res = await waitAgentTaskApi(Number(pending.taskId), { onStatusChange: onGuideTaskStatusChange });
    localStorage.removeItem(key);

    if (resolvedMode === 'teach' || res?.message) {
      appendTeachResult(res, resolvedMode, sessionId);
      return;
    }
    appendGuideResult(res, resolvedMode, sessionId);
  } catch (e) {
    localStorage.removeItem(key);
    guideTaskError.value = e?.message || '出了些小问题';
  }
};

const resumePendingGuideTask = async () => {
  const hasPending = Boolean(localStorage.getItem(GUIDE_PENDING_KEY) || localStorage.getItem(TEACH_PENDING_KEY));
  if (!hasPending) return;

  asking.value = true;
  try {
    await resumePendingTaskForMode('guide');
    await resumePendingTaskForMode('teach');
  } finally {
    asking.value = false;
    settleGuideTaskStatus();
  }
};

const loadPlans = async () => {
  planLoading.value = true;
  planError.value = '';
  try {
    const params = compactQuery({
      page: planPage.value,
      page_size: pageSize,
      q: planKeyword.value
    });
    const normalized = normalizePagedResult(await listPlansApi(params));
    plans.value = normalized.items;
    planServerTotal.value = normalized.total;
  } catch (e) {
    plans.value = [];
    planError.value = e?.response?.data?.detail || '项目数据加载失败';
    planServerTotal.value = 0;
  } finally {
    planLoading.value = false;
  }
};

const loadMessages = async () => {
  messageLoading.value = true;
  messageError.value = '';
  try {
    const params = compactQuery({
      page: messagePage.value,
      page_size: pageSize,
      q: messageKeyword.value
    });
    const normalized = normalizePagedResult(await listMessagesApi(params));
    messages.value = normalized.items;
    messageServerTotal.value = normalized.total;
  } catch (e) {
    messages.value = [];
    messageError.value = e?.response?.data?.detail || '消息数据加载失败';
    messageServerTotal.value = 0;
  } finally {
    messageLoading.value = false;
  }
};

const loadHistory = async () => {
  historyLoading.value = true;
  historyError.value = '';
  try {
    const params = compactQuery({
      mode: 'stream',
      page: historyPage.value,
      page_size: pageSize,
      q: historyKeyword.value
    });
    const normalized = normalizePagedResult(await historyApi(params));
    history.value = normalized.items;
    historyServerTotal.value = normalized.total;
  } catch (e) {
    history.value = [];
    historyError.value = e?.response?.data?.detail || '历史数据加载失败';
    historyServerTotal.value = 0;
  } finally {
    historyLoading.value = false;
  }
};

const onPlanFilterChange = async () => {
  planPage.value = 1;
  await loadPlans();
};

const onMessageFilterChange = async () => {
  messagePage.value = 1;
  await loadMessages();
};

const onHistoryFilterChange = async () => {
  historyPage.value = 1;
  await loadHistory();
};

const onPlanPageChange = async (page) => {
  planPage.value = page;
  await loadPlans();
};

const onMessagePageChange = async (page) => {
  messagePage.value = page;
  await loadMessages();
};

const onHistoryPageChange = async (page) => {
  historyPage.value = page;
  await loadHistory();
};

watch(guideMode, (mode) => {
  ensureModeInitialized(mode);
  guideTaskError.value = '';
  issues.value = [];
  if (mode === 'guide') {
    const session = (currentState('guide').sessions || []).find((item) => item.id === currentState('guide').activeSessionId);
    stage.value = session?.stage || currentState('guide').stage || 'idea';
    return;
  }
  if (mode === 'teach' && !quickTopics.value.length) {
    loadLearningTopics();
  }
});

onMounted(async () => {
  currentState('guide').sessions = parseStoredSessions(GUIDE_HISTORY_KEY, 'studentChatHistory');
  currentState('teach').sessions = parseStoredSessions(TEACH_HISTORY_KEY, 'tutorSessions');
  ensureModeInitialized('guide');
  ensureModeInitialized('teach');
  restoreActiveSession('guide');
  restoreActiveSession('teach');

  await Promise.all([loadPlans(), loadMessages(), loadHistory(), loadLearningTopics()]);
  await resumePendingGuideTask();
});
</script>

<style scoped>
.page-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  border: 1px solid var(--line-strong);
  background: var(--bg-panel);
  padding: 18px;
}

.lead,
.guide-panel {
  grid-column: 1 / -1;
}

.kicker {
  margin: 0;
  font-size: 12px;
  color: var(--ink-muted);
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

h2,
h3 {
  margin: 10px 0 0;
  color: var(--ink-title);
  font-family: var(--font-display);
}

.toolbar {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.toolbar > input,
.toolbar > select {
  flex: 1 1 220px;
  min-width: 0;
}

input,
select {
  min-width: 0;
  height: var(--control-height);
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 0 10px;
  border-radius: var(--control-radius);
}

.chips {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chips span {
  border: 1px solid var(--line-soft);
  padding: 4px 10px;
  border-radius: 999px;
  color: var(--ink-body);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.topics {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

button.primary,
button.ghost {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--ink-title);
  cursor: pointer;
  border-radius: 999px;
}

button.primary {
  background: var(--ink-title);
  color: var(--bg-main);
}

button.ghost {
  background: transparent;
  color: var(--ink-title);
}

ul {
  margin: 12px 0 0;
  padding-left: 16px;
  display: grid;
  gap: 8px;
}

.issues {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed var(--line-soft);
  background: var(--bg-field);
  border-radius: 12px;
}

.issues strong {
  letter-spacing: 0.01em;
}

@media (max-width: 1200px) {
  .page-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
}
</style>

