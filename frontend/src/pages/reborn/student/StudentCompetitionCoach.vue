<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Competition Coach</p>
      <h2>竞赛评分与协作写作分离</h2>
      <p>评分区只负责评分建议；计划书协作在教练对话中完成，并支持 Word 导出。</p>
    </section>

    <section class="panel advise-panel">
      <h3>竞赛评分建议</h3>
      <div class="toolbar list-toolbar">
        <select v-model="competition">
          <option value="挑战杯">挑战杯</option>
          <option value="大创">大创</option>
          <option value="互联网+">互联网+</option>
        </select>
        <select v-model="projectType">
          <option value="auto">自动识别项目类型</option>
          <option value="commercial">商业项目</option>
          <option value="public_welfare">公益项目</option>
        </select>
        <select v-model="advisePlanId">
          <option value="">可选：选择方案作为评分上下文</option>
          <option v-for="item in plans" :key="item.id" :value="item.id">{{ item.title }} V{{ item.version }}</option>
        </select>
      </div>
      <textarea v-model="adviseText" rows="4" placeholder="可选：补充项目摘要（未选方案时建议填写）"></textarea>
      <div class="toolbar">
        <button type="button" class="primary" :disabled="advising" @click="getAdvice">生成评分建议</button>
      </div>
      <template v-if="adviseResult">
        <div class="issues">
          <strong>评分总览</strong>
          <ul>
            <li>竞赛类型：{{ adviseResult.competition || competition }}</li>
            <li>项目类型：{{ adviseResult.project_type || 'auto' }}</li>
            <li>总分预估：{{ formatFinalScore(adviseResult.total_score_estimate || adviseResult.total_score) }}</li>
          </ul>
        </div>

        <div class="issues" v-if="adviseDimensions.length">
          <strong>多维评分明细</strong>
          <div class="score-grid">
            <article v-for="(item, idx) in adviseDimensions" :key="`score-${idx}`" class="score-card">
              <p class="score-title">{{ item.dimension || item.criterion || `维度${idx + 1}` }}</p>
              <p class="score-meta">
                {{ formatScore(item.score) }} / {{ formatScore(item.max_score || item.max || 10) }}
                · 权重 {{ formatWeight(item.weight) }}
              </p>
              <p v-if="item.rationale" class="score-text">{{ item.rationale }}</p>
              <p v-if="item.optimization_suggestion" class="score-text tip">{{ item.optimization_suggestion }}</p>
            </article>
          </div>
        </div>

        <div class="issues" v-if="adviseStrengths.length">
          <strong>当前优势</strong>
          <ul>
            <li v-for="(item, idx) in adviseStrengths" :key="`strength-${idx}`">{{ item }}</li>
          </ul>
        </div>

        <div class="issues" v-if="adviseEvidenceGaps.length">
          <strong>证据缺口</strong>
          <ul>
            <li v-for="(item, idx) in adviseEvidenceGaps" :key="`gap-${idx}`">{{ item }}</li>
          </ul>
        </div>

        <div class="issues" v-if="adviseRiskAlerts.length">
          <strong>风险提示</strong>
          <ul>
            <li v-for="(item, idx) in adviseRiskAlerts" :key="`risk-${idx}`">{{ item }}</li>
          </ul>
        </div>

        <div class="issues" v-if="adviseActions.length">
          <strong>优先优化建议</strong>
          <ul>
            <li v-for="(item, idx) in adviseActions" :key="`action-${idx}`">
              {{ item.priority || idx + 1 }}. {{ item.action || item.task || '-' }}
              <small v-if="item.reason">｜{{ item.reason }}</small>
            </li>
          </ul>
        </div>

        <div class="issues" v-if="adviseResult.winning_case_reference">
          <strong>对标参考</strong>
          <p>{{ adviseResult.winning_case_reference }}</p>
        </div>

        <MarkdownBlock
          v-if="adviseResult.summary_markdown || adviseResult.summary"
          class="issues markdown-summary"
          :content="adviseResult.summary_markdown || adviseResult.summary"
        />
      </template>
    </section>

    <section class="panel coach-panel">
      <div class="toolbar">
        <h3>竞赛教练协作对话</h3>
        <button type="button" class="ghost" :disabled="exporting || !coachMessages.length" @click="downloadWord">
          {{ exporting ? '导出中...' : '导出 Word' }}
        </button>
      </div>
      <p class="kicker">在连续对话中逐步迭代计划书；评分建议与计划书共创彼此独立。</p>

      <AgentChatWindow
        title="竞赛教练智能体"
        :messages="coachMessages"
        :sessions="coachSessions"
        :model-value="coachInput"
        :loading="coachLoading"
        placeholder="例如：请作为市场分析专员和财务分析师，帮我完善执行摘要与盈利路径"
        @update:model-value="coachInput = $event"
        @send="sendCoach"
        @new-chat="newCoachChat"
        @select-session="selectCoachSession"
        @delete-session="deleteCoachSession"
      />
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import AgentChatWindow from '../../../components/AgentChatWindow.vue';
import MarkdownBlock from '../../../components/MarkdownBlock.vue';
import {
  competitionAdviseApi,
  competitionCoachChatApi,
  competitionCoachExportWordApi,
  listPlansApi
} from '../../../api/student';

const plans = ref([]);
const competition = ref('挑战杯');
const projectType = ref('auto');
const advisePlanId = ref('');
const adviseText = ref('');
const adviseResult = ref(null);
const advising = ref(false);
const exporting = ref(false);

const coachInput = ref('');
const coachLoading = ref(false);
const coachMessages = ref([
  { role: 'ai', content: '你好，我会在对话中与你协作完成计划书，并以市场分析、财务分析、文案润色三个视角给出建议。' }
]);
const coachSessions = ref([]);
const adviseDimensions = computed(() => {
  const rows = adviseResult.value?.dimension_scores || adviseResult.value?.breakdown || [];
  return Array.isArray(rows) ? rows : [];
});
const adviseStrengths = computed(() => {
  const rows = adviseResult.value?.strengths || [];
  return Array.isArray(rows) ? rows : [];
});
const adviseEvidenceGaps = computed(() => {
  const rows = adviseResult.value?.evidence_gaps || [];
  return Array.isArray(rows) ? rows : [];
});
const adviseRiskAlerts = computed(() => {
  const rows = adviseResult.value?.risk_alerts || [];
  return Array.isArray(rows) ? rows : [];
});
const adviseActions = computed(() => {
  const rows = adviseResult.value?.prioritized_actions || adviseResult.value?.quick_fixes || [];
  return Array.isArray(rows) ? rows : [];
});

const normalizeList = (raw) => {
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw?.items)) return raw.items;
  if (Array.isArray(raw?.results)) return raw.results;
  return [];
};

const nowText = () => new Date().toLocaleString();
const formatScore = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  return `${Math.round(num * 100) / 100}`;
};
const formatWeight = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  if (num > 0 && num <= 1) {
    return `${Math.round(num * 100)}%`;
  }
  return `${Math.round(num)}%`;
};
const formatFinalScore = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  return `${Math.round(num * 100) / 100}/100`;
};

const snapshotCoach = () => ({
  id: Date.now(),
  title: `${competition.value}教练会话`,
  date: nowText(),
  messages: [...coachMessages.value]
});

const persistCoachSessions = () => {
  localStorage.setItem('competitionCoachSessions', JSON.stringify(coachSessions.value.slice(0, 20)));
};

const getAdvice = async () => {
  advising.value = true;
  try {
    adviseResult.value = await competitionAdviseApi({
      competition: competition.value,
      plan_id: advisePlanId.value || undefined,
      text: adviseText.value.trim(),
      project_type: projectType.value
    });
  } finally {
    advising.value = false;
  }
};

const buildCoachPayload = () => ({
  competition: competition.value,
  project_type: projectType.value,
  plan_id: advisePlanId.value || undefined,
  text: adviseText.value.trim(),
  history: coachMessages.value.slice(-12)
});

const downloadWord = async () => {
  exporting.value = true;
  try {
    const blob = await competitionCoachExportWordApi({
      ...buildCoachPayload(),
      history: coachMessages.value.slice(-20)
    });
    const fileBlob = blob instanceof Blob ? blob : new Blob([blob], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    });
    const url = URL.createObjectURL(fileBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${competition.value}_计划书.docx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
};

const newCoachChat = () => {
  if (coachMessages.value.length > 1) {
    coachSessions.value.unshift(snapshotCoach());
    persistCoachSessions();
  }
  coachMessages.value = [{ role: 'ai', content: '新会话已创建。请告诉我你的项目阶段与当前目标。' }];
};

const selectCoachSession = (index) => {
  const row = coachSessions.value[index];
  if (!row) return;
  coachMessages.value = [...(row.messages || [])];
};

const deleteCoachSession = (index) => {
  coachSessions.value.splice(index, 1);
  persistCoachSessions();
};

const sendCoach = async () => {
  const text = coachInput.value.trim();
  if (!text) return;

  coachMessages.value.push({ role: 'student', content: text });
  coachInput.value = '';
  coachLoading.value = true;
  try {
    const res = await competitionCoachChatApi({
      ...buildCoachPayload(),
      mode: 'chat',
      question: text
    });
    coachMessages.value.push({ role: 'ai', content: res?.answer || '暂未返回文本结果' });
    coachSessions.value.unshift(snapshotCoach());
    coachSessions.value = coachSessions.value.slice(0, 20);
    persistCoachSessions();
  } finally {
    coachLoading.value = false;
  }
};

onMounted(async () => {
  plans.value = normalizeList(await listPlansApi());
  coachSessions.value = JSON.parse(localStorage.getItem('competitionCoachSessions') || '[]');
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

.lead,
.coach-panel,
.advise-panel {
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

.toolbar > select,
.toolbar > input,
.toolbar > button {
  flex: 1 1 220px;
  min-width: 0;
}

textarea {
  margin-top: 12px;
  width: 100%;
  min-height: 104px;
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  padding: 10px;
  border-radius: var(--control-radius);
}

.issues {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed var(--line-soft);
  background: var(--bg-field);
  border-radius: var(--radius-sm);
}

.score-grid {
  margin-top: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
}

.score-card {
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  padding: 8px 10px;
  background: color-mix(in oklch, var(--bg-main) 90%, white);
}

.score-title {
  margin: 0;
  font-weight: 700;
  color: var(--ink-title);
}

.score-meta {
  margin: 4px 0 0;
  color: var(--ink-muted);
  font-size: 12px;
}

.score-text {
  margin: 6px 0 0;
  line-height: 1.55;
}

.score-text.tip {
  color: #0f766e;
}

.issues ul {
  margin: 8px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
}

.issues small {
  color: var(--ink-muted);
}

.markdown-summary {
  border-style: solid;
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

@media (max-width: 900px) {
  .toolbar > select,
  .toolbar > input,
  .toolbar > button {
    flex: 1 1 100%;
  }
}
</style>

