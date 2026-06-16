<template>
  <div class="page-grid">
    <section class="panel lead">
      <p class="kicker">Financial Designer Agent</p>
      <h2>财务设计智能体</h2>
      <p>围绕同一项目持续对话，反复校准预算假设、盈利结构与风险控制。</p>
    </section>

    <section class="panel">
      <h3>对话上下文</h3>
      <div class="toolbar">
        <select v-model="form.planId">
          <option value="">选择项目方案</option>
          <option v-for="item in plans" :key="item.id" :value="item.id">{{ item.title }} V{{ item.version }}</option>
        </select>
        <select v-model="form.projectType">
          <option value="auto">自动识别项目类型</option>
          <option value="commercial">商业项目</option>
          <option value="public_welfare">公益项目</option>
        </select>
      </div>
      <p class="hint">建议先选择方案，再通过多轮追问不断修订预算参数。</p>
    </section>

    <section class="panel">
      <h3>预算对话</h3>
      <AgentChatWindow
        title="财务预算协作"
        :messages="messages"
        :sessions="history"
        :model-value="chatQuestion"
        :loading="chatLoading"
        placeholder="例如：把渠道获客成本按三档预算重算，并给出现金流风险线。"
        @update:model-value="chatQuestion = $event"
        @send="askAgent"
        @new-chat="newChat"
        @select-session="loadHistory"
        @delete-session="deleteSession"
      >
        <template #composer-extra>
          <p class="chat-hint">
            当前项目：{{ selectedPlanLabel }} ｜ 当前类型：{{ form.projectType }}
          </p>
        </template>
        <template #composer-actions>
          <button type="button" class="chat-send-btn" :disabled="chatLoading || !form.planId" @click="askAgent">
            {{ chatLoading ? '智能体思考中...' : '发送并迭代预算' }}
          </button>
        </template>
      </AgentChatWindow>
    </section>

    <section class="panel" v-if="hasResult">
      <h3>当前预算方案（持续更新）</h3>
      <div class="summary-box">
        <strong>项目类型</strong>
        <p>{{ result.project_type || '-' }}</p>
      </div>
      <div class="summary-box" v-if="result.tam_sam_som">
        <strong>TAM / SAM / SOM</strong>
        <ul>
          <li>TAM：{{ result.tam_sam_som.tam || '-' }}</li>
          <li>SAM：{{ result.tam_sam_som.sam || '-' }}</li>
          <li>SOM：{{ result.tam_sam_som.som || '-' }}</li>
        </ul>
      </div>
      <div class="row-grid">
        <div class="summary-box" v-if="revenueStreams.length">
          <strong>收入结构</strong>
          <ul>
            <li v-for="(item, idx) in revenueStreams" :key="`rs-${idx}`">{{ item }}</li>
          </ul>
        </div>
        <div class="summary-box" v-if="fundingSources.length">
          <strong>资金来源</strong>
          <ul>
            <li v-for="(item, idx) in fundingSources" :key="`fs-${idx}`">{{ item }}</li>
          </ul>
        </div>
      </div>
      <div class="row-grid">
        <div class="summary-box" v-if="(result.financial_plan?.['3_month'] || []).length">
          <strong>3个月动作</strong>
          <ul>
            <li v-for="(item, idx) in result.financial_plan['3_month']" :key="`m3-${idx}`">{{ item }}</li>
          </ul>
        </div>
        <div class="summary-box" v-if="(result.financial_plan?.['12_month'] || []).length">
          <strong>12个月动作</strong>
          <ul>
            <li v-for="(item, idx) in result.financial_plan['12_month']" :key="`m12-${idx}`">{{ item }}</li>
          </ul>
        </div>
      </div>
      <div class="summary-box" v-if="(result.action_list || []).length">
        <strong>优先行动清单</strong>
        <ul>
          <li v-for="(item, idx) in result.action_list" :key="`ac-${idx}`">
            [{{ item.priority || 'P2' }}] {{ item.task || '-' }}（{{ item.owner || '-' }} · {{ item.deadline || '-' }}）
          </li>
        </ul>
      </div>
      <MarkdownBlock v-if="result.summary" class="markdown-summary" :content="result.summary" />
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import AgentChatWindow from '../../../components/AgentChatWindow.vue';
import MarkdownBlock from '../../../components/MarkdownBlock.vue';
import { financialDesignApi, listPlansApi } from '../../../api/student';

const HISTORY_KEY = 'studentFinanceAgentHistory';

const plans = ref([]);
const chatLoading = ref(false);
const chatQuestion = ref('');
const result = ref({});
const history = ref([]);
const messages = ref([{ role: 'ai', text: '你好，我会和你一起迭代预算。你可以直接提出修改目标。' }]);

const form = reactive({
  planId: '',
  projectType: 'auto'
});

const normalizeList = (raw) => {
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw?.items)) return raw.items;
  if (Array.isArray(raw?.results)) return raw.results;
  return [];
};

const hasResult = computed(() => Object.keys(result.value || {}).length > 0);
const revenueStreams = computed(() => result.value?.profit_model?.revenue_streams || []);
const fundingSources = computed(() => result.value?.funding_strategy?.sources || []);

const selectedPlanLabel = computed(() => {
  if (!form.planId) return '未选择';
  const row = (plans.value || []).find((item) => String(item.id) === String(form.planId));
  if (!row) return `方案#${form.planId}`;
  return `${row.title || row.name || row.id} V${row.version || 1}`;
});

const persistHistory = () => {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value.slice(0, 20)));
};

const buildHistoryPayload = () => {
  return (messages.value || []).slice(-14).map((item) => ({
    role: item.role === 'ai' ? 'assistant' : 'student',
    content: String(item.content || item.text || '').trim()
  })).filter((item) => item.content);
};

const buildReplyText = (payload) => {
  const lines = [];
  const reply = String(payload?.assistant_reply || '').trim();
  const summary = String(payload?.summary || '').trim();
  if (reply) lines.push(reply);
  if (summary && summary !== reply) lines.push(summary);
  const tam = payload?.tam_sam_som || {};
  if (tam.tam || tam.sam || tam.som) {
    lines.push(`TAM/SAM/SOM：${tam.tam || '-'} / ${tam.sam || '-'} / ${tam.som || '-'}`);
  }
  const actions = payload?.action_list || [];
  if (actions.length) {
    lines.push(`关键行动：${actions.slice(0, 2).map((item) => item.task || '-').join('；')}`);
  }
  return lines.filter(Boolean).join('\n');
};

const archiveCurrent = () => {
  const validMessages = (messages.value || []).filter((item) => String(item?.content || item?.text || '').trim());
  if (validMessages.length < 2) return;
  history.value.unshift({
    id: Date.now(),
    title: selectedPlanLabel.value,
    date: new Date().toISOString(),
    planId: form.planId ? Number(form.planId) : '',
    projectType: form.projectType,
    messages: [...messages.value],
    result: { ...(result.value || {}) }
  });
  persistHistory();
};

const newChat = () => {
  archiveCurrent();
  result.value = {};
  chatQuestion.value = '';
  messages.value = [{ role: 'ai', text: '新预算会话已创建。告诉我你希望优先优化哪一块。' }];
};

const loadHistory = (index) => {
  const session = history.value[index];
  if (!session) return;
  messages.value = [...(session.messages || [])];
  result.value = { ...(session.result || {}) };
  if (session.planId) {
    form.planId = String(session.planId);
  }
  if (session.projectType) {
    form.projectType = session.projectType;
  }
};

const deleteSession = (index) => {
  history.value.splice(index, 1);
  persistHistory();
};

const askAgent = async () => {
  if (!form.planId || !chatQuestion.value.trim()) return;
  const question = chatQuestion.value.trim();
  messages.value.push({ role: 'student', text: question });
  chatLoading.value = true;
  try {
    const payload = await financialDesignApi({
      plan_id: form.planId,
      project_type: form.projectType,
      question,
      history: buildHistoryPayload(),
      current_plan: result.value || null
    });
    result.value = payload || {};
    messages.value.push({ role: 'ai', text: buildReplyText(payload) || '已完成预算迭代。' });
    chatQuestion.value = '';
  } catch (error) {
    const detail = error?.response?.data?.message || error?.response?.data?.detail || error?.message || '财务预算智能体暂时不可用，请稍后重试。';
    messages.value.push({ role: 'ai', text: `本轮预算迭代未完成：${detail}` });
  } finally {
    chatLoading.value = false;
  }
};

onMounted(async () => {
  plans.value = normalizeList(await listPlansApi());
  history.value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
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

.toolbar > select {
  flex: 1 1 220px;
  min-width: 0;
}

select {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--line-strong);
  background: var(--bg-field);
  color: var(--ink-title);
  border-radius: var(--control-radius);
  height: var(--control-height);
  padding: 0 10px;
}

.hint {
  margin-top: 8px;
  color: var(--ink-muted);
  font-size: 13px;
}

.chat-hint {
  margin: 0 0 8px;
  color: var(--ink-muted);
  font-size: 12px;
}

.chat-send-btn {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--ink-title);
  background: var(--ink-title);
  color: var(--bg-main);
  border-radius: 999px;
  cursor: pointer;
}

.chat-send-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.row-grid {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-box {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: color-mix(in oklch, var(--bg-field) 90%, white);
}

.summary-box > strong {
  color: var(--ink-title);
}

.summary-box > p {
  margin: 8px 0 0;
}

.summary-box ul {
  margin: 8px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
}

.markdown-summary {
  margin-top: 12px;
}

@media (max-width: 860px) {
  .row-grid {
    grid-template-columns: 1fr;
  }
}
</style>
