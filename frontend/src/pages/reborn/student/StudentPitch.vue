<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Pitch Studio</p>
      <h2>路演优化与模拟训练</h2>
      <p>优化智能体与模拟智能体分仓存储历史记录，切换后互不干扰。</p>
    </section>

    <section class="panel">
      <h3>路演设置</h3>
      <div class="toolbar list-toolbar">
        <select v-model="roadmapAgentType">
          <option value="optimize">优化智能体</option>
          <option value="simulate">路演模拟智能体</option>
        </select>
        <select v-model="selectedPlanId">
          <option value="">选择方案</option>
          <option v-for="item in plans" :key="item.id" :value="item.id">{{ item.title || '未命名方案' }} V{{ item.version || 1 }}</option>
        </select>
      </div>

      <div class="toolbar">
        <label class="file-upload-field">
          <span class="file-upload-label">上传路演PPT</span>
          <input type="file" accept=".ppt,.pptx,.pdf" @change="onPptFile">
        </label>
        <label class="file-upload-field">
          <span class="file-upload-label">上传路演文稿</span>
          <input type="file" accept=".txt,.md,.doc,.docx,.pdf" @change="onScriptFile">
        </label>
        <input v-model.trim="scriptText" type="text" placeholder="可选：补充讲稿文本">
      </div>

      <div class="toolbar" v-if="roadmapAgentType === 'simulate'">
        <select v-model="simulationExpertType">
          <option v-for="item in simulationExpertOptions" :key="item.value" :value="item.value">
            {{ item.label }}
          </option>
        </select>
        <button type="button" class="primary" :disabled="roadmapLoading || simulateMode === 'simulating'" @click="startSimulation">开始模拟</button>
        <button type="button" class="ghost" :disabled="roadmapLoading || simulateMode !== 'simulating'" @click="endSimulation">结束模拟</button>
      </div>

      <div class="status-row">
        <span class="pill">当前模式：{{ roadmapAgentType === 'optimize' ? '优化' : '模拟' }}</span>
        <span class="pill" v-if="roadmapAgentType === 'simulate'">模拟状态：{{ simulateLabel }}</span>
        <span class="pill" v-if="roadmapAgentType === 'simulate'">提问专家：{{ simulationExpertLabel }}</span>
        <span class="pill">路演PPT：{{ pptFile ? pptFile.name : '未选择' }}</span>
        <span class="pill">路演文稿：{{ scriptFile ? scriptFile.name : '未选择' }}</span>
      </div>
    </section>

    <section class="panel">
      <AgentChatWindow
        :title="roadmapAgentType === 'optimize' ? '优化智能体' : '路演模拟智能体'"
        :messages="roadmapMessages"
        :sessions="roadmapSessions"
        :model-value="roadmapInput"
        :loading="roadmapLoading"
        :task-status="roadmapTaskStatus"
        :task-error="roadmapTaskError"
        :placeholder="chatPlaceholder"
        @update:model-value="roadmapInput = $event"
        @send="sendRoadmap"
        @new-chat="newRoadmapChat"
        @select-session="selectRoadmapSession"
        @delete-session="deleteRoadmapSession"
      />

      <div v-if="simulationReport" class="issues">
        <strong>{{ simulationReport.title || '模拟报告' }}</strong>
        <ul>
          <li>回答逻辑性：{{ simulationReport.logic || '-' }}</li>
          <li>证据支撑度：{{ simulationReport.evidence || '-' }}</li>
          <li>抗压表现：{{ simulationReport.pressure || '-' }}</li>
          <li>高频薄弱点：{{ (simulationReport.weak_points || []).join('；') || '-' }}</li>
          <li>改进建议：{{ (simulationReport.improvements || []).join('；') || '-' }}</li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import AgentChatWindow from '../../../components/AgentChatWindow.vue';
import {
  createAgentTaskApi,
  listPlansApi,
  pitchSimulateApi,
  waitAgentTaskApi
} from '../../../api/student';
import { asArray } from '../../../composables/list';

const plans = ref([]);
const roadmapAgentType = ref('optimize');
const selectedPlanId = ref('');
const pptFile = ref(null);
const scriptFile = ref(null);
const scriptText = ref('');
const simulationExpertOptions = [
  { value: 'aggressive_vc', label: '激进型VC' },
  { value: 'technical_expert', label: '技术流专家' },
  { value: 'conservative_banker', label: '保守型银行家' },
  { value: 'balanced_judge', label: '综合型评委' }
];
const simulationExpertType = ref('aggressive_vc');

const roadmapInput = ref('');
const roadmapMessages = ref([]);
const roadmapSessions = ref([]);
const roadmapLoading = ref(false);
const roadmapTaskStatus = ref('');
const roadmapTaskError = ref('');

const simulateMode = ref('idle');
const simulationQuestionIndex = ref(0);
const simulationTurns = ref([]);
const simulationReport = ref(null);

const ROADMAP_PENDING_KEY = 'roadmapPendingTask';

const messagesKey = (type) => `roadmapAgentMessages:${type}`;
const sessionsKey = (type) => `roadmapAgentSessions:${type}`;

const defaultMessage = (type) => {
  if (type === 'simulate') {
    return [{ role: 'ai', content: '已进入路演模拟智能体，请先上传材料并点击“开始模拟”。' }];
  }
  return [{ role: 'ai', content: '已进入优化智能体，请输入需要优化的路演内容。' }];
};

const chatPlaceholder = computed(() => {
  if (roadmapAgentType.value === 'simulate' && simulateMode.value === 'simulating') {
    return '请回答当前评委问题';
  }
  if (roadmapAgentType.value === 'simulate' && simulateMode.value === 'idle') {
    return '请先点击“开始模拟”后再作答';
  }
  return '请输入要优化或追问的内容';
});

const simulateLabel = computed(() => {
  if (simulateMode.value === 'simulating') return '模拟中';
  if (simulateMode.value === 'ended') return '已结束';
  return '未开始';
});

const simulationExpertLabel = computed(() => {
  const hit = simulationExpertOptions.find((item) => item.value === simulationExpertType.value);
  return hit?.label || '综合型评委';
});

const readStorage = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return parsed ?? fallback;
  } catch (_) {
    return fallback;
  }
};

const persistTypeState = (type) => {
  localStorage.setItem(messagesKey(type), JSON.stringify(roadmapMessages.value || []));
  localStorage.setItem(sessionsKey(type), JSON.stringify((roadmapSessions.value || []).slice(0, 20)));
};

const loadTypeState = (type) => {
  roadmapMessages.value = readStorage(messagesKey(type), defaultMessage(type));
  roadmapSessions.value = readStorage(sessionsKey(type), []);
  if (!Array.isArray(roadmapMessages.value) || !roadmapMessages.value.length) {
    roadmapMessages.value = defaultMessage(type);
  }
  if (!Array.isArray(roadmapSessions.value)) {
    roadmapSessions.value = [];
  }
};

const onRoadmapTaskStatusChange = ({ status, error }) => {
  roadmapTaskStatus.value = status || '';
  roadmapTaskError.value = error || '';
};

const settleRoadmapTaskStatus = () => {
  if (roadmapTaskStatus.value !== 'done') return;
  setTimeout(() => {
    if (roadmapTaskStatus.value === 'done') roadmapTaskStatus.value = '';
  }, 1200);
};

const nowText = () => new Date().toLocaleString();

const buildSnapshot = () => ({
  id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
  title: roadmapAgentType.value === 'optimize' ? '优化智能体会话' : '模拟智能体会话',
  date: nowText(),
  messages: [...roadmapMessages.value]
});

const pushAiMessage = (text) => {
  roadmapMessages.value.push({ role: 'ai', content: String(text || '暂未返回文本结果') });
};

const normalizeTaskAnswer = (res) => {
  if (typeof res?.answer === 'string' && res.answer.trim()) return res.answer;
  if (typeof res?.message === 'string' && res.message.trim()) return res.message;
  if (typeof res?.summary === 'string' && res.summary.trim()) return res.summary;
  if (typeof res === 'string') return res;
  try {
    return JSON.stringify(res, null, 2);
  } catch (_) {
    return '暂未返回文本结果';
  }
};

const onPptFile = (event) => {
  pptFile.value = event.target.files?.[0] || null;
};

const onScriptFile = (event) => {
  scriptFile.value = event.target.files?.[0] || null;
};

const newRoadmapChat = () => {
  if (roadmapMessages.value.length > 1) {
    roadmapSessions.value.unshift(buildSnapshot());
    roadmapSessions.value = roadmapSessions.value.slice(0, 20);
  }
  roadmapMessages.value = defaultMessage(roadmapAgentType.value);
  if (roadmapAgentType.value === 'simulate') {
    simulateMode.value = 'idle';
    simulationQuestionIndex.value = 0;
    simulationTurns.value = [];
    simulationReport.value = null;
  }
  persistTypeState(roadmapAgentType.value);
};

const selectRoadmapSession = (index) => {
  const row = roadmapSessions.value[index];
  if (!row) return;
  roadmapMessages.value = [...(row.messages || [])];
  persistTypeState(roadmapAgentType.value);
};

const deleteRoadmapSession = (index) => {
  roadmapSessions.value.splice(index, 1);
  persistTypeState(roadmapAgentType.value);
};

const ensurePlanSelected = () => {
  if (!selectedPlanId.value) {
    ElMessage.warning('请先选择方案');
    return false;
  }
  return true;
};

const sendOptimize = async (text) => {
  const task = await createAgentTaskApi({
    agent: 'pitch_optimize',
    payload: {
      plan_id: Number(selectedPlanId.value),
      message: text,
      duration_minutes: 6,
      ppt_name: pptFile.value?.name || '',
      script_name: scriptFile.value?.name || '',
      script_text: scriptText.value.trim()
    }
  });
  localStorage.setItem(ROADMAP_PENDING_KEY, JSON.stringify({ taskId: task.task_id, type: 'optimize', mode: 'optimize' }));
  const res = await waitAgentTaskApi(task.task_id, { onStatusChange: onRoadmapTaskStatusChange });
  localStorage.removeItem(ROADMAP_PENDING_KEY);
  pushAiMessage(normalizeTaskAnswer(res));
};

const sendSimulate = async (text) => {
  if (simulateMode.value === 'idle') {
    pushAiMessage('请先点击“开始模拟”，系统会给出评委提问。');
    return;
  }

  if (simulateMode.value === 'simulating') {
    simulationTurns.value.push({ question_index: simulationQuestionIndex.value, answer: text });
    const task = await createAgentTaskApi({
      agent: 'pitch_simulate',
      payload: {
        action: 'answer',
        question_index: simulationQuestionIndex.value,
        answer: text,
        expert_type: simulationExpertType.value
      }
    });
    localStorage.setItem(ROADMAP_PENDING_KEY, JSON.stringify({ taskId: task.task_id, type: 'simulate', mode: 'simulate_answer' }));
    const res = await waitAgentTaskApi(task.task_id, { onStatusChange: onRoadmapTaskStatusChange });
    localStorage.removeItem(ROADMAP_PENDING_KEY);

    const nextQuestion = String(res?.question || '').trim();
    if (nextQuestion) {
      simulationQuestionIndex.value = Number(res?.question_index || simulationQuestionIndex.value || 0);
      pushAiMessage(nextQuestion);
    } else {
      pushAiMessage(normalizeTaskAnswer(res));
    }
    return;
  }

  const task = await createAgentTaskApi({
    agent: 'pitch_simulate',
    payload: {
      action: 'qa',
      after_end: true,
      message: text,
      expert_type: simulationExpertType.value
    }
  });
  localStorage.setItem(ROADMAP_PENDING_KEY, JSON.stringify({ taskId: task.task_id, type: 'simulate', mode: 'simulate_qa' }));
  const res = await waitAgentTaskApi(task.task_id, { onStatusChange: onRoadmapTaskStatusChange });
  localStorage.removeItem(ROADMAP_PENDING_KEY);
  pushAiMessage(normalizeTaskAnswer(res));
};

const sendRoadmap = async () => {
  const text = roadmapInput.value.trim();
  if (!text) return;
  if (!ensurePlanSelected()) return;

  roadmapMessages.value.push({ role: 'student', content: text });
  roadmapInput.value = '';
  roadmapLoading.value = true;
  roadmapTaskError.value = '';

  try {
    if (roadmapAgentType.value === 'optimize') {
      await sendOptimize(text);
    } else {
      await sendSimulate(text);
    }
  } catch (error) {
    roadmapTaskError.value = error?.message || '发送失败';
    ElMessage.error(roadmapTaskError.value);
  } finally {
    roadmapLoading.value = false;
    settleRoadmapTaskStatus();
  }

  if (roadmapMessages.value.length > 1) {
    roadmapSessions.value.unshift(buildSnapshot());
    roadmapSessions.value = roadmapSessions.value.slice(0, 20);
  }
  persistTypeState(roadmapAgentType.value);
};

const startSimulation = async () => {
  if (!ensurePlanSelected()) return;
  if (!pptFile.value || !scriptFile.value) {
    const missing = [];
    if (!pptFile.value) missing.push('路演PPT');
    if (!scriptFile.value) missing.push('路演文稿');
    await ElMessageBox.alert(
      `开始模拟前请先上传：${missing.join('、')}`,
      '材料未上传',
      { type: 'warning', confirmButtonText: '我知道了' }
    );
    return;
  }

  roadmapLoading.value = true;
  try {
    const fd = new FormData();
    fd.append('action', 'start');
    fd.append('plan_id', String(selectedPlanId.value));
    fd.append('ppt_file', pptFile.value);
    fd.append('script_file', scriptFile.value);
    fd.append('expert_type', simulationExpertType.value);
    if (scriptText.value.trim()) {
      fd.append('script_text', scriptText.value.trim());
    }

    const res = await pitchSimulateApi(fd);
    if (res?.ok === false) {
      throw new Error(res?.message || '模拟启动失败');
    }

    simulateMode.value = 'simulating';
    if (typeof res?.expert_type === 'string' && res.expert_type) {
      simulationExpertType.value = res.expert_type;
    }
    simulationQuestionIndex.value = Number(res?.question_index || 0);
    simulationTurns.value = [];
    simulationReport.value = null;
    roadmapMessages.value = [{ role: 'ai', content: String(res?.question || '模拟已开始，请回答第一个问题。') }];
    persistTypeState(roadmapAgentType.value);
  } catch (error) {
    ElMessage.error(error?.message || '模拟启动失败');
  } finally {
    roadmapLoading.value = false;
  }
};

const endSimulation = async () => {
  if (simulateMode.value !== 'simulating') return;
  roadmapLoading.value = true;
  try {
    const res = await pitchSimulateApi({
      action: 'end',
      turns: simulationTurns.value,
      expert_type: simulationExpertType.value
    });
    if (res?.ok === false) {
      throw new Error(res?.message || '模拟结束失败');
    }
    simulateMode.value = 'ended';
    simulationReport.value = res?.report || null;
    const message = String(res?.message || '').trim();
    if (message) {
      pushAiMessage(message);
    }
    persistTypeState(roadmapAgentType.value);
  } catch (error) {
    ElMessage.error(error?.message || '模拟结束失败');
  } finally {
    roadmapLoading.value = false;
  }
};

const resumePendingTask = async () => {
  const pending = readStorage(ROADMAP_PENDING_KEY, null);
  if (!pending?.taskId) return;

  const pendingType = pending?.type === 'simulate' ? 'simulate' : 'optimize';
  const previousType = roadmapAgentType.value;
  if (pendingType !== roadmapAgentType.value) {
    persistTypeState(roadmapAgentType.value);
    roadmapAgentType.value = pendingType;
    loadTypeState(pendingType);
  }

  roadmapLoading.value = true;
  roadmapTaskError.value = '';
  try {
    const res = await waitAgentTaskApi(Number(pending.taskId), { onStatusChange: onRoadmapTaskStatusChange });

    if (pending.mode === 'simulate_answer') {
      const nextQuestion = String(res?.question || '').trim();
      if (nextQuestion) {
        simulationQuestionIndex.value = Number(res?.question_index || simulationQuestionIndex.value || 0);
        pushAiMessage(nextQuestion);
      } else {
        pushAiMessage(normalizeTaskAnswer(res));
      }
    } else {
      pushAiMessage(normalizeTaskAnswer(res));
    }

    persistTypeState(roadmapAgentType.value);
  } catch (error) {
    roadmapTaskError.value = error?.message || '任务恢复失败';
  } finally {
    localStorage.removeItem(ROADMAP_PENDING_KEY);
    roadmapLoading.value = false;
    settleRoadmapTaskStatus();
  }

  if (previousType !== roadmapAgentType.value) {
    persistTypeState(roadmapAgentType.value);
    roadmapAgentType.value = previousType;
    loadTypeState(previousType);
  }
};

watch(
  roadmapAgentType,
  (nextType, prevType) => {
    if (prevType) {
      persistTypeState(prevType);
    }

    roadmapInput.value = '';
    roadmapTaskStatus.value = '';
    roadmapTaskError.value = '';

    if (nextType === 'simulate') {
      simulateMode.value = 'idle';
      simulationQuestionIndex.value = 0;
      simulationTurns.value = [];
      simulationReport.value = null;
    }

    loadTypeState(nextType);
  }
);

onMounted(async () => {
  plans.value = asArray(await listPlansApi({ page: 1, page_size: 200 }));
  loadTypeState(roadmapAgentType.value);
  await resumePendingTask();
});
</script>

<style scoped>
.page-grid {
  display: grid;
  gap: 16px;
}

.panel {
  border: 1px solid var(--line-strong);
  background: var(--bg-panel);
  padding: 18px;
  border-radius: var(--radius-md);
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

.toolbar > select,
.toolbar > input[type='text'],
.toolbar > input[type='file'] {
  flex: 1 1 220px;
  min-width: 0;
}

.file-upload-field {
  flex: 1 1 220px;
  min-width: 0;
  display: grid;
  gap: 6px;
}

.file-upload-label {
  font-size: 12px;
  color: var(--ink-muted);
}

.status-row {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 4px 10px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  font-size: 12px;
  color: var(--ink-body);
  background: color-mix(in oklch, var(--bg-field) 90%, white);
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

input[type='file'] {
  padding: 6px 10px;
}

input[type='file']::file-selector-button {
  margin-right: 8px;
  height: 30px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: color-mix(in oklch, var(--bg-panel) 92%, white);
  color: var(--ink-title);
  cursor: pointer;
}

button.primary,
button.ghost {
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid var(--ink-title);
  border-radius: 999px;
  cursor: pointer;
}

button.primary {
  background: var(--ink-title);
  color: var(--bg-main);
}

button.ghost {
  background: transparent;
  color: var(--ink-title);
}

.issues {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed var(--line-soft);
  background: var(--bg-field);
  border-radius: var(--radius-sm);
}

ul {
  margin: 10px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

@media (max-width: 980px) {
  .toolbar > select,
  .toolbar > input[type='text'],
  .toolbar > input[type='file'] {
    flex: 1 1 100%;
  }
}
</style>

